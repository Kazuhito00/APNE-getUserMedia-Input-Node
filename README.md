> [!WARNING]
> APNE-getUserMedia-Input-Node は [Audio-Processing-Node-Editor](https://github.com/Kazuhito00/Audio-Processing-Node-Editor) の追加用ノードです。<br>
> このリポジトリ単体では動作しません。

# APNE-getUserMedia-Input-Node
[Audio-Processing-Node-Editor](https://github.com/Kazuhito00/Audio-Processing-Node-Editor) で動作するマイク入力用ノードです。<br>
WebブラウザのgetUserMedia()で取得したデータをWebSocketでPython側に送信します。

<img src="https://github.com/user-attachments/assets/edf9bec6-4df0-43b1-894e-b8b558ccd50e" loading="lazy" width="45%"> <img src="https://github.com/user-attachments/assets/fd7bad26-fd43-45b1-9af0-285be184af4e" loading="lazy" width="45%">

# Requirement
[Audio-Processing-Node-Editor](https://github.com/Kazuhito00/Audio-Processing-Node-Editor) の依存パッケージに加えて、以下のパッケージのインストールが必要です。
```
pip install aiohttp
```

# Installation
「node/input_node/node_input_get_user_media_mic.py」を <br>
[Audio-Processing-Node-Editor](https://github.com/Kazuhito00/Audio-Processing-Node-Editor) の 「[node/input_node](https://github.com/Kazuhito00/Audio-Processing-Node-Editor/tree/main/node/input_node)」にコピーしてください。

# Node
<details open>
<summary>Input Node</summary>

<table>
    <tr>
        <td width="200">
            Mic (getUserMedia())
        </td>
        <td width="320">
            <img src="https://github.com/user-attachments/assets/a5231445-5c0c-4f43-92dd-c1e1d913c108" loading="lazy" width="300px">
        </td>
        <td width="760">
            WebブラウザのgetUserMedia()経由で取得したマイク入力を扱うノード<br>
            ノードを生成するとブラウザが立ち上がります。<br>
          　「1. Prepare Microphone」を押下後、マイク使用を許可し、「Start Recording」を押下してください。
        </td>
    </tr>
</table>

</details>

# Author
高橋かずひと(https://twitter.com/KzhtTkhs)
 
# License 
APNE-getUserMedia-Input-Node is under [Apache-2.0 license](LICENSE).<br><br>
