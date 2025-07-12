#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import threading
import time
import webbrowser
from queue import Queue
from typing import Any, Dict, List, Optional

import dearpygui.dearpygui as dpg  # type: ignore
import numpy as np
from aiohttp import web
from node_editor.util import dpg_set_value, get_tag_name_list  # type: ignore

from node.node_abc import DpgNodeABC  # type: ignore

# HTML content
HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <title>Microphone Audio to Python</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f4f7f6;
            color: #333;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            font-size: 2rem; /* Increased base font size */
        }
        #container {
            background: white;
            padding: 3rem 4rem;
            border-radius: 12px;
            box-shadow: 0 8px 30px rgba(0,0,0,0.12);
            width: 100%;
            max-width: 900px; /* Increased width for larger text */
            text-align: center;
        }
        h1 {
            color: #1a73e8;
            margin-bottom: 1.5rem;
            font-size: 3.5rem; /* Increased font size */
        }
        #status {
            margin: 1.5rem 0;
            padding: 1.5rem;
            border-radius: 8px;
            background-color: #e8f0fe;
            border: 1px solid #d2e3fc;
            font-weight: 500;
            min-height: 2.5em;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        button {
            background-color: #1a73e8;
            color: white;
            border: none;
            padding: 18px 36px;
            border-radius: 8px;
            font-size: 1.8rem; /* Increased font size */
            cursor: pointer;
            transition: background-color 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
            margin: 0.5rem;
        }
        button:hover:not(:disabled) {
            background-color: #185abc;
            box-shadow: 0 4px 15px rgba(26, 115, 232, 0.2);
        }
        button:disabled {
            background-color: #d2e3fc;
            cursor: not-allowed;
        }
        #main-controls {
            margin-top: 2rem;
            text-align: left;
            border-top: 1px solid #e0e0e0;
            padding-top: 2rem;
        }
        #main-controls div {
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            flex-wrap: wrap;
        }
        #main-controls label.inline-label {
            margin-right: 1rem;
            flex-basis: 300px;
            flex-shrink: 0;
        }
        #main-controls input[type="checkbox"] {
            margin-right: 0.5rem;
            transform: scale(1.8);
        }
        select {
            padding: 12px;
            border-radius: 6px;
            border: 1px solid #ccc;
            font-size: 1.5rem; /* Increased font size */
            flex-grow: 1;
        }
        .button-group {
            text-align: center;
            margin-top: 1.5rem;
        }
    </style>
</head>
<body>
    <div id="container">
        <h1>Send Microphone Audio to Python Server</h1>

        <p id="status">Status: Click the button below to start.</p>
        <button id="initButton">1. Prepare Microphone</button>

        <div id="main-controls" style="display: none;">
            <p><strong>Step 2: Select device and record</strong></p>
            <div>
                <label for="micSelect" class="inline-label">Microphone:</label>
                <select id="micSelect"></select>
            </div>
            <div>
                <label for="sampleRateSelect" class="inline-label">Sample Rate (Hz):</label>
                <select id="sampleRateSelect">
                    <option value="16000" selected>16000 Hz</option>
                    <option value="44100">44100 Hz</option>
                    <option value="48000">48000 Hz</option>
                </select>
            </div>
            <div>
                <input type="checkbox" id="echoCancellation">
                <label for="echoCancellation">Enable Echo Cancellation</label>
            </div>
            <div>
                <input type="checkbox" id="noiseSuppression" checked>
                <label for="noiseSuppression">Enable Noise Suppression</label>
            </div>
            <div>
                <input type="checkbox" id="autoGainControl" checked>
                <label for="autoGainControl">Enable Auto Gain Control</label>
            </div>
            <div class="button-group">
                <button id="startButton">Start Recording</button>
                <button id="stopButton" disabled>Stop Recording</button>
            </div>
        </div>
    </div>

    <script>
        // All UI elements
        const initButton = document.getElementById('initButton');
        const status = document.getElementById('status');
        const mainControls = document.getElementById('main-controls');
        const micSelect = document.getElementById('micSelect');
        const startButton = document.getElementById('startButton');
        const stopButton = document.getElementById('stopButton');
        const echoCancellationCheckbox = document.getElementById('echoCancellation');
        const noiseSuppressionCheckbox = document.getElementById('noiseSuppression');
        const autoGainControlCheckbox = document.getElementById('autoGainControl');
        const sampleRateSelect = document.getElementById('sampleRateSelect');

        let audioContext;
        let microphone;
        let processorNode;
        let websocket;
        let stream; // Keep stream to stop tracks

        let reconnectIntervalId = null;
        let reconnectAttempts = 0;
        const MAX_RECONNECT_ATTEMPTS = 30; // Max retries before giving up
        const RECONNECT_DELAY_MS = 2000; // 2 seconds

        // This function gets and populates the mic list.
        const getAndPopulateMicList = async () => {
            console.log('Attempting to get and populate microphone list...');
            status.textContent = 'Status: Finding microphone devices...';
            
            micSelect.innerHTML = '';

            try {
                const devices = await navigator.mediaDevices.enumerateDevices();
                console.log('Raw devices found:', devices);

                const audioDevices = devices.filter(device => device.kind === 'audioinput');
                console.log('Filtered audio devices:', audioDevices);

                if (audioDevices.length === 0) {
                    status.textContent = 'Status: No microphones found!';
                    console.warn('No audio input devices were found.');
                    return;
                }

                audioDevices.forEach(device => {
                    const option = document.createElement('option');
                    option.value = device.deviceId;
                    option.text = device.label || `Unnamed Microphone (ID: ${device.deviceId.slice(0, 8)})`;
                    console.log(`Adding device to list: Label='${device.label}', ID='${device.deviceId}'`);
                    micSelect.appendChild(option);
                });

                mainControls.style.display = 'block';
                status.textContent = 'Status: Ready. Select a microphone and start recording.';
                initButton.style.display = 'none';

            } catch (err) {
                console.error('Error in getAndPopulateMicList:', err);
                status.textContent = `Status: Error finding devices. ${err.message}`;
            }
        };

        // 1. User clicks the "Prepare" button
        initButton.onclick = async () => {
            console.log('"Prepare Microphone" button clicked.');
            initButton.disabled = true;
            status.textContent = 'Status: Waiting for you to grant microphone permission...';

            try {
                // 2. Request permission.
                const tempStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                console.log('Microphone permission granted.');

                // 3. Now that we have permission, get the list with proper labels.
                await getAndPopulateMicList();

                // 4. Stop the temporary stream.
                tempStream.getTracks().forEach(track => {
                    track.stop();
                    console.log('Temporary stream stopped.');
                });
                
                navigator.mediaDevices.ondevicechange = getAndPopulateMicList;

            } catch (err) {
                console.error('Error requesting microphone permission:', err);
                status.textContent = `Status: Permission denied or error. Please refresh and allow access. Error: ${err.name}`;
                initButton.disabled = false;
            }
        };

        // Function to establish WebSocket connection
        const connectWebSocket = () => {
            if (websocket && (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING)) {
                console.log('WebSocket already open or connecting.');
                return;
            }

            console.log('Attempting to connect WebSocket...');
            status.textContent = `Status: Connecting to server... (Attempt ${reconnectAttempts + 1})`;

            // Use the same port as the HTTP server
            websocket = new WebSocket('ws://' + window.location.host + '/ws');

            websocket.onopen = () => {
                console.log('WebSocket connection established.');
                status.textContent = 'Status: Recording...';
                reconnectAttempts = 0; // Reset attempts on successful connection
                if (reconnectIntervalId) {
                    clearInterval(reconnectIntervalId);
                    reconnectIntervalId = null;
                }
                // Start audio context only after successful connection
                if (audioContext && audioContext.state === 'suspended') {
                    audioContext.resume();
                }
            };

            websocket.onclose = (event) => {
                console.log('WebSocket connection closed:', event.code, event.reason);
                if (event.code === 1000) { // Normal closure
                    status.textContent = 'Status: Connection closed. Ready to start again.';
                } else { // Abnormal closure
                    status.textContent = 'Status: Connection lost. Reconnecting...';
                    reconnectAttempts++;
                    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                        if (!reconnectIntervalId) { // Only set interval if not already set
                            reconnectIntervalId = setInterval(connectWebSocket, RECONNECT_DELAY_MS);
                        }
                    } else {
                        status.textContent = 'Status: Connection failed after multiple retries. Please check server.';
                        startButton.disabled = false;
                        stopButton.disabled = true;
                        micSelect.disabled = false;
                        echoCancellationCheckbox.disabled = false;
                        noiseSuppressionCheckbox.disabled = false;
                        autoGainControlCheckbox.disabled = false;
                        if (reconnectIntervalId) {
                            clearInterval(reconnectIntervalId);
                            reconnectIntervalId = null;
                        }
                    }
                }
            };

            websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                // onclose will typically be called after onerror, so reconnection logic is there.
                status.textContent = 'Status: WebSocket error. Attempting to reconnect...';
            };
        };

        // AudioWorklet Processor code (embedded)
        const audioWorkletProcessorCode = `
            class AudioProcessor extends AudioWorkletProcessor {
                constructor() {
                    super();
                    this.port.onmessage = (event) => {
                        // Handle messages from the main thread if needed
                    };
                }

                process(inputs, outputs, parameters) {
                    const input = inputs[0];
                    if (input.length > 0) {
                        const audioData = input[0]; // Get the first channel (mono)
                        // Send the raw Float32Array data as a binary message
                        this.port.postMessage(audioData.buffer, [audioData.buffer]);
                    }
                    return true; // Keep the processor alive
                }
            }
            registerProcessor('audio-processor', AudioProcessor);
        `;

        // Recording logic
        startButton.onclick = async () => {
            if (!micSelect.value) {
                alert('Please select a microphone.');
                return;
            }
            try {
                const selectedSampleRate = parseInt(sampleRateSelect.value);
                audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: selectedSampleRate });
                await audioContext.audioWorklet.addModule(URL.createObjectURL(new Blob([audioWorkletProcessorCode], { type: 'application/javascript' })));

                const audioConstraints = {
                    deviceId: { exact: micSelect.value },
                    echoCancellation: echoCancellationCheckbox.checked,
                    noiseSuppression: noiseSuppressionCheckbox.checked,
                    autoGainControl: autoGainControlCheckbox.checked,
                    sampleRate: selectedSampleRate
                };

                stream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
                microphone = audioContext.createMediaStreamSource(stream);
                processorNode = new AudioWorkletNode(audioContext, 'audio-processor');

                processorNode.port.onmessage = (event) => {
                    if (websocket && websocket.readyState === WebSocket.OPEN) {
                        websocket.send(event.data); // event.data is the ArrayBuffer
                    }
                };

                microphone.connect(processorNode).connect(audioContext.destination);

                // Attempt to connect WebSocket. AudioContext will resume on successful connection.
                connectWebSocket();

                status.textContent = 'Status: Recording...';
                startButton.disabled = true;
                stopButton.disabled = false;
                micSelect.disabled = true;
                echoCancellationCheckbox.disabled = true;
                noiseSuppressionCheckbox.disabled = true;
                autoGainControlCheckbox.disabled = true;

            } catch (error) {
                console.error('Error during recording setup:', error);
                status.textContent = `Status: Error starting recording. ${error.name}`;
                startButton.disabled = false; // Re-enable start button on error
                if (audioContext) {
                    audioContext.close();
                }
                if (stream) {
                    stream.getTracks().forEach(track => track.stop());
                }
            }
        };

        stopButton.onclick = () => {
            if (audioContext && audioContext.state !== 'closed') {
                audioContext.close();
                console.log('AudioContext closed.');
            }
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                console.log('Microphone stream stopped.');
            }
            // Only close websocket if it's not already closed or reconnecting
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.close(1000, 'User stopped recording'); // Normal closure
            }
            status.textContent = 'Status: Stopped. Ready to start again.';
            startButton.disabled = false;
            stopButton.disabled = true;
            micSelect.disabled = false;
            echoCancellationCheckbox.disabled = false;
            noiseSuppressionCheckbox.disabled = false;
            autoGainControlCheckbox.disabled = false;
            if (reconnectIntervalId) { // Clear any pending reconnection attempts
                clearInterval(reconnectIntervalId);
                reconnectIntervalId = null;
            }
        };
    </script>
</body>
</html>
"""


class Node(DpgNodeABC):
    _ver: str = "0.0.1"

    node_label: str = "Mic (getUserMedia)"
    node_tag: str = "MicGetUserMedia"

    def __init__(self) -> None:
        self._node_data = {}
        self._audio_queue = (
            Queue()
        )  # Queue to pass audio data from WebSocket to DPG thread
        self._app = None
        self._runner = None
        self._site = None
        self._server_thread = None
        self._loop = None

    async def _index_handler(self, request):
        """Serves the HTML content."""
        return web.Response(text=HTML_CONTENT, content_type="text/html")

    async def _websocket_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        print("Client connected via WebSocket.")

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.BINARY:
                    audio_data_bytes = msg.data
                    # print(f"Received raw audio chunk with size: {len(audio_data_bytes)} bytes")

                    try:
                        y = np.frombuffer(audio_data_bytes, dtype=np.float32)
                        self._audio_queue.put(y)  # Put audio data into the queue
                    except Exception as e:
                        print(f"  Error processing raw audio chunk: {e}")

                elif msg.type == web.WSMsgType.TEXT:
                    print(f"Received text message: {msg.text}")
                elif msg.type == web.WSMsgType.ERROR:
                    print(
                        f"WebSocket connection closed with exception: {ws.exception()}"
                    )

        except Exception as e:
            print(f"WebSocket handler error: {e}")
        finally:
            print("Client disconnected from WebSocket.")
        return ws

    async def _start_server_async(self):
        self._app = web.Application()
        self._app.router.add_get("/", self._index_handler)  # Add HTML handler
        self._app.router.add_get("/ws", self._websocket_handler)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "localhost", 8765)
        print("Starting server on http://localhost:8765")
        await self._site.start()

        # Open the browser automatically
        webbrowser.open("http://localhost:8765")

        # Keep the server running indefinitely
        await asyncio.Future()

    def _run_server_in_thread(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._start_server_async())

    def add_node(
        self,
        parent: str,
        node_id: int,
        pos: List[int] = [0, 0],
        setting_dict: Optional[Dict[str, Any]] = None,
        callback: Optional[Any] = None,
    ) -> str:
        # Tag names
        tag_name_list: List[Any] = get_tag_name_list(
            node_id,
            self.node_tag,
            [self.TYPE_TEXT],
            [self.TYPE_SIGNAL_CHUNK, self.TYPE_TIME_MS],
        )
        tag_node_name: str = tag_name_list[0]
        input_tag_list = tag_name_list[1]
        output_tag_list = tag_name_list[2]

        # Settings
        self._setting_dict = setting_dict or {}
        waveform_w: int = self._setting_dict.get("waveform_width", 200)
        waveform_h: int = self._setting_dict.get("waveform_height", 400)
        self._default_sampling_rate: int = self._setting_dict.get(
            "default_sampling_rate", 16000
        )
        self._chunk_size: int = self._setting_dict.get("chunk_size", 1024)
        self._use_pref_counter: bool = self._setting_dict["use_pref_counter"]

        self._node_data[str(node_id)] = {
            "buffer": np.array([]),
            "chunk": np.array([]),
            "chunk_index": -1,
            "display_x_buffer": np.array([]),
            "display_y_buffer": np.array([]),
            "input_id": -1,  # Not used for WebSocket, but kept for compatibility
        }

        # Prepare display buffer
        buffer_len: int = self._default_sampling_rate * 5
        self._node_data[str(node_id)]["display_y_buffer"] = np.zeros(
            buffer_len, dtype=np.float32
        )
        self._node_data[str(node_id)]["display_x_buffer"] = (
            np.arange(len(self._node_data[str(node_id)]["display_y_buffer"]))
            / self._default_sampling_rate
        )

        # Node
        with dpg.node(
            tag=tag_node_name,
            parent=parent,
            label=self.node_label,
            pos=pos,
        ):
            # Mic selection (kept for UI consistency, but not functional for WebSocket)
            with dpg.node_attribute(
                tag=input_tag_list[0][0],
                attribute_type=dpg.mvNode_Attr_Static,
            ):
                dpg.add_text("WebSocket Input (Port 8765)", tag=input_tag_list[0][1])
            # Plot area
            with dpg.node_attribute(
                tag=output_tag_list[0][0],
                attribute_type=dpg.mvNode_Attr_Output,
            ):
                with dpg.plot(
                    height=waveform_h,
                    width=waveform_w,
                    no_inputs=False,
                    tag=f"{node_id}:audio_plot_area",
                ):
                    dpg.add_plot_axis(
                        dpg.mvXAxis,
                        label="Time(s)",
                        no_label=True,
                        no_tick_labels=True,
                        tag=f"{node_id}:xaxis",
                    )
                    dpg.add_plot_axis(
                        dpg.mvYAxis,
                        label="Amplitude",
                        no_label=True,
                        no_tick_labels=True,
                        tag=f"{node_id}:yaxis",
                    )
                    dpg.set_axis_limits(f"{node_id}:xaxis", 0.0, 5.0)
                    dpg.set_axis_limits(f"{node_id}:yaxis", -1.0, 1.0)

                    dpg.add_line_series(
                        [],
                        [],
                        parent=f"{node_id}:yaxis",
                        tag=f"{node_id}:audio_line_series",
                    )
            # Processing time
            if self._use_pref_counter:
                with dpg.node_attribute(
                    tag=output_tag_list[1][0],
                    attribute_type=dpg.mvNode_Attr_Output,
                ):
                    dpg.add_text(
                        tag=output_tag_list[1][1],
                        default_value="elapsed time(ms)",
                    )

        # Start the WebSocket server in a separate thread when the node is added
        if self._server_thread is None:
            self._server_thread = threading.Thread(
                target=self._run_server_in_thread, daemon=True
            )
            self._server_thread.start()

        return tag_node_name

    def update(
        self,
        node_id: str,
        connection_list: List[Any],
        player_status_dict: Dict[str, Any],
        node_result_dict: Dict[str, Any],
    ) -> Any:
        tag_name_list: List[Any] = get_tag_name_list(
            node_id,
            self.node_tag,
            [self.TYPE_TEXT],
            [self.TYPE_SIGNAL_CHUNK, self.TYPE_TIME_MS],
        )
        output_tag_list = tag_name_list[2]

        # Start measurement
        if self._use_pref_counter:
            start_time = time.perf_counter()

        chunk: Optional[np.ndarray] = np.array([])
        current_status = player_status_dict.get("current_status", False)

        if current_status == "play":
            # Get audio data from the queue
            if not self._audio_queue.empty():
                new_audio = self._audio_queue.get()
                self._node_data[node_id]["buffer"] = np.concatenate(
                    (self._node_data[node_id]["buffer"], new_audio)
                )

            if len(self._node_data[node_id]["buffer"]) >= self._chunk_size:
                # Extract chunk
                chunk = self._node_data[node_id]["buffer"][: self._chunk_size]
                self._node_data[node_id]["chunk"] = chunk
                self._node_data[node_id]["buffer"] = self._node_data[node_id]["buffer"][
                    self._chunk_size :
                ]

                # Update chunk index
                self._node_data[str(node_id)]["chunk_index"] += 1

                # Update plot
                temp_display_y_buffer = self._node_data[str(node_id)][
                    "display_y_buffer"
                ]
                temp_display_y_buffer = np.roll(
                    temp_display_y_buffer, -self._chunk_size
                )
                temp_display_y_buffer[-self._chunk_size :] = chunk
                self._node_data[str(node_id)]["display_y_buffer"] = (
                    temp_display_y_buffer
                )
                dpg.set_value(
                    f"{node_id}:audio_line_series",
                    [
                        self._node_data[str(node_id)]["display_x_buffer"],
                        temp_display_y_buffer,
                    ],
                )
        elif current_status == "pause":
            pass
        elif current_status == "stop":
            # Discard buffered data if not playing
            while not self._audio_queue.empty():
                self._audio_queue.get()

            # Initialize buffer
            self._node_data[str(node_id)]["buffer"] = np.zeros(0, dtype=np.float32)

            # Initialize plot area
            self._node_data[str(node_id)]["chunk_index"] = -1

            buffer_len: int = self._default_sampling_rate * 5
            self._node_data[str(node_id)]["display_y_buffer"] = np.zeros(
                buffer_len, dtype=np.float32
            )
            self._node_data[str(node_id)]["display_x_buffer"] = (
                np.arange(len(self._node_data[str(node_id)]["display_y_buffer"]))
                / self._default_sampling_rate
            )
            dpg.set_value(
                f"{node_id}:audio_line_series",
                [
                    self._node_data[str(node_id)]["display_x_buffer"].tolist(),
                    list(self._node_data[str(node_id)]["display_y_buffer"]),
                ],
            )

        result_dict = {
            "chunk_index": self._node_data[str(node_id)].get("chunk_index", -1),
            "chunk": self._node_data[node_id]["chunk"],
        }

        # End measurement
        if self._use_pref_counter:
            elapsed_time = time.perf_counter() - start_time
            elapsed_time = int(elapsed_time * 1000)
            dpg_set_value(output_tag_list[1][1], str(elapsed_time).zfill(4) + "ms")

        return result_dict

    def close(self, node_id: str) -> None:
        # Clean up buffer
        self._node_data[str(node_id)]["buffer"] = np.zeros(0, dtype=np.float32)

        # Shut down the aiohttp server
        if self._site:
            print("Shutting down WebSocket server...")
            self._loop.call_soon_threadsafe(self._site.stop)
            self._loop.call_soon_threadsafe(self._runner.cleanup)
            # self._server_thread.join() # Don't join here, it will block DPG main loop
            print("WebSocket server shut down.")

    def get_setting_dict(self, node_id: str) -> Dict[str, Any]:
        tag_name_list: List[Any] = get_tag_name_list(
            node_id,
            self.node_tag,
            [self.TYPE_TEXT],
            [self.TYPE_SIGNAL_CHUNK, self.TYPE_TIME_MS],
        )
        tag_node_name: str = tag_name_list[0]

        pos: List[int] = dpg.get_item_pos(tag_node_name)

        setting_dict: Dict[str, Any] = {
            "ver": self._ver,
            "pos": pos,
        }
        return setting_dict

    def set_setting_dict(self, node_id: int, setting_dict: Dict[str, Any]) -> None:
        pass

    # This callback is no longer functional for WebSocket input, but kept for compatibility
    def _on_mic_select(self, sender, app_data, user_data):
        node_id = sender.split(":")[0]
        print(
            "Mic selection changed in GUI, but WebSocket input is fixed to port 8765."
        )
