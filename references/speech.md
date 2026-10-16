# 6. Speech: STT and TTS on the M10

Cloud integration: `azure-speech.md`.

## Constraints that decide everything

| Constraint | Consequence |
|---|---|
| Python **3.7.3** | Blocks `piper-tts` pip and `elevenlabs` (need 3.8+); `vosk`, `sherpa-onnx`, `azure-*`, `openai` are fine |
| **512 MB RAM** | Vosk small ≈ **300 MB** resident — works, but tight. No Whisper small+ |
| **16 GB eMMC** | Plenty for models (40–160 MB each) |
| **No onboard speaker** | All TTS/Chat *output* needs a USB speaker in the USB-A port |
| **Onboard mic, 16 kHz mono 16-bit** | Matches STT models' native rate; nothing to resample |
| **No Wi-Fi by default** | Cloud = Wi-Fi first (`wifi.md`); pip needs Wi-Fi too |
| Passive buzzer | Beeps only, cannot play voice |

## Decision table

**STT**

| Option | Where | Real-time | Py 3.7 | RAM | Model |
|---|---|---|---|---|---|
| **Vosk** ⭐ | on-device | ✅ | ✅ | ~300 MB | 40 MB (small) / 130 MB |
| sherpa-onnx | on-device | ✅ (~160 ms) | ✅ | ~200 MB | 60–80 MB |
| Whisper.cpp | on-device | ❌ (1.2–1.8×) | C++ bin | ~158 MB | 74–485 MB |
| Azure STT | cloud | ✅ | ✅ | minimal | — |
| OpenAI Whisper | cloud | ❌ (file upload) | ✅ | minimal | — |
| Google STT | cloud | ✅ | ✅ | minimal | — |

**TTS**

| Option | Where | Py 3.7 | RAM | Quality |
|---|---|---|---|---|
| **Piper (C++ binary)** ⭐ | on-device | ✅ (subprocess) | ~150 MB | Natural |
| sherpa-onnx TTS (VITS) | on-device | ✅ | ~150 MB | Natural |
| pyttsx3 + espeak-ng | on-device | ✅ | ~15 MB | Robotic |
| Flite | on-device | C++ bin | ~11 MB | Synthetic |
| Piper (pip) | on-device | ❌ 3.8+ | — | — |
| Azure TTS | cloud | ✅ | minimal | Excellent neural |
| OpenAI TTS | cloud | ✅ | minimal | Excellent |
| ElevenLabs | cloud | ❌ 3.8+ (use REST) | — | Best |

`pip install piper-tts` **will not install on Python 3.7** — use the ARM64 C++
binary via `subprocess`, or sherpa-onnx if you want a Python API.

## On-device STT

### Vosk (recommended)

```bash
pip install vosk
# model: download on PC, deploy via SFTP (see below)
```

⚠️ **Debian 10 C++ ABI fix required** — the wheel's `libvosk.so` fails with
`undefined symbol: _ZNSt7__cxx1119basic_ostringstream…`. Extract a Debian 11
`libstdc++6` on the board and preload it (do **not** install system-wide):

```bash
# on PC
curl -L https://ftp.debian.org/debian/pool/main/g/gcc-10/libstdc++6_10.2.1-6_arm64.deb -o libstdc++6.deb
# on board
dpkg-deb -x libstdc++6.deb /root/speech-models/extracted_libstdc++
export LD_PRELOAD=/root/speech-models/extracted_libstdc++/usr/lib/aarch64-linux-gnu/libstdc++.so.6
```

Scripts should self-restart with `LD_PRELOAD` set (guard with
`_VOSK_PRELOADED=1` to avoid a loop):

```python
import os, sys
SO = "/root/speech-models/extracted_libstdc++/usr/lib/aarch64-linux-gnu/libstdc++.so.6"
if os.path.isfile(SO) and os.environ.get("_VOSK_PRELOADED") != "1":
    os.environ["_VOSK_PRELOADED"] = "1"
    os.environ["LD_PRELOAD"] = SO + os.pathsep + os.environ.get("LD_PRELOAD", "")
    os.execv(sys.executable, [sys.executable] + sys.argv)
```

Models: `vosk-model-small-en-us-0.15` (40 MB, ~80 % word accuracy, real-time) vs
`vosk-model-en-us-0.22` (130 MB, ~90 %, slower). Others:
<https://alphacephei.com/vosk/models>.

Decode loop — one recognizer per utterance, join `Result()`s with
`FinalResult()`; see `m10-api.md` §8 for the canonical snippet and the
push-to-talk record-then-decode pattern (`examples.md`, example 05).

### Others

- **sherpa-onnx** — `pip install sherpa-onnx`, streaming Zipformer ~60–80 MB,
  also does VAD/diarization/enhancement and TTS in one package.
- **Whisper.cpp** — best accuracy, but ~12–15 s per 10 s audio → **batch only**:

```bash
sudo apt install build-essential cmake git
git clone https://github.com/ggml-org/whisper.cpp && cd whisper.cpp
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DWHISPER_USE_NEON=ON && cmake --build . -j4
./bin/whisper-cli -m ../../models/ggml-tiny.en.bin -f in.wav -nt
```

## On-device TTS

```bash
sudo apt install espeak-ng espeak-ng-data   # needed by pyttsx3 *and* Piper
pip install pyttsx3
```

```python
import pyttsx3
e = pyttsx3.init(); e.setProperty('rate', 150)
e.say("Hello from the M10"); e.runAndWait()
e.save_to_file("hi", "/tmp/hi.wav"); e.runAndWait()   # note: 2nd arg is filename
```

**Piper (best offline quality)** — C++ binary + voice model, called via
`subprocess`:

```bash
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_arm64.tar.gz
tar xzf piper_arm64.tar.gz && sudo mv piper /usr/local/bin/
# voice: huggingface.co/rhasspy/piper-voices  (en_US-amy-medium.onnx + .onnx.json)
```

```python
import subprocess
subprocess.run(["piper", "--model", "en_US-amy-medium.onnx",
                "--output_file", "/tmp/out.wav"], input=b"Hello from the M10", check=True)
from unihiker import Audio; Audio().play("/tmp/out.wav")
```

**Flite** (English, native **16 kHz** output — matches the mic):

```bash
flite -t "Hello" -r 16000 -w /tmp/hi.wav
```

## Cloud (needs Wi-Fi)

| Service | STT | TTS | Free tier | Py 3.7 |
|---|---|---|---|---|
| **Azure Speech** ⭐ | ✅ real-time | ✅ neural | 5 h STT + 500 K chars / mo | ✅ |
| OpenAI | ✅ file | ✅ | none | ✅ |
| Google Cloud | ✅ streaming | ✅ separate API | 60 min STT / mo | ✅ |
| ElevenLabs | ❌ | ✅ best | 10 K credits | ❌ (REST only) |

Azure is the recommended cloud option — full guide in `azure-speech.md`.

**OpenAI — simplest cloud, file-based** (needs Wi-Fi):

```python
import openai
openai.api_key = "sk-..."

with open("/tmp/clip.wav", "rb") as f:
    text = openai.audio.transcriptions.create(model="whisper-1", file=f,
                                              response_format="text")
r = openai.audio.speech.create(model="tts-1", voice="alloy", input=text)
r.stream_to_file("/tmp/out.mp3")
from unihiker import Audio; Audio().play("/tmp/out.mp3")
```

## Recommended pipelines

| Goal | Pipeline |
|---|---|
| **Best offline** | mic → Vosk → logic → Piper binary → USB speaker (~1–2 s) |
| **Best quality** (Wi-Fi) | mic → Azure STT → GPT → Azure TTS → USB speaker (~3–8 s round trip) |
| **Simplest** | mic → OpenAI Whisper → logic → pyttsx3 → USB speaker |
| **Single dependency** | sherpa-onnx for both STT and TTS (Py 3.7 ✅, ~120 MB) |
| **Fully offline assistant** | Whisper.cpp tiny → SmolLM2-360M → Flite (~267 MB peak, ~40 s — not interactive) |

## Models: download on PC, deploy by SFTP

The board is offline until Wi-Fi is up, so pre-download and push. Standard
target is `/root/speech-models/`:

```python
import urllib.request, zipfile, os, paramiko

os.makedirs("/tmp/sm", exist_ok=True)
urllib.request.urlretrieve(
    "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
    "/tmp/vosk.zip")
with zipfile.ZipFile("/tmp/vosk.zip") as z: z.extractall("/tmp")

c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.1.2.3", username="root", password="dfrobot", timeout=10)
sftp = c.open_sftp()

def copy_tree(local, remote):                     # recursive SFTP put
    c.exec_command("mkdir -p " + remote)
    for item in os.listdir(local):
        lp, rp = os.path.join(local, item), remote + "/" + item
        copy_tree(lp, rp) if os.path.isdir(lp) else sftp.put(lp, rp)

copy_tree("/tmp/vosk-model-small-en-us-0.15",
          "/root/speech-models/vosk-model-small-en-us-0.15")
sftp.close(); c.close()
```

## Package availability (Debian 10 arm64)

| Package | Buster arm64 | Py 3.7 |
|---|---|---|
| `espeak-ng`, `espeak-ng-data`, `flite` | ✅ apt | C++ |
| `pyttsx3` | ✅ pip | ✅ |
| `vosk` | ✅ pip (manylinux2014_aarch64) | ✅ |
| `sherpa-onnx` | ✅ pip | ✅ |
| `azure-cognitiveservices-speech` | ✅ pip | ✅ |
| `openai`, `google-cloud-speech` | ✅ pip | ✅ |
| `piper-tts` | ⚠️ | ❌ use C++ binary |
| `elevenlabs` | ❌ | ❌ use REST |
