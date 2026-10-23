# 6. Speech: STT and TTS on the M10

> Reviewed 2026-10-19. Assumes firmware v0.4.2, `unihiker` 0.0.27+ and `pinpong` 0.6.1; version-specific claims are flagged inline.

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

> **Measured on this board:** Piper `medium` is ~8 s per short sentence
> (voice load dominates). Plan UI latency for seconds, not milliseconds —
> see the Piper section below.

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
`libstdc++6` on the board and preload it (do **not** install system-wide).

`m10-offline-install.py` does this end-to-end from a manifest — push the deb,
`dpkg-deb -x` it, install the wheel offline, then load the real model under
`LD_PRELOAD` to prove the ABI works (`references/system.md` has the manifest
schema). The manual steps, for when you are doing it by hand:

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
`FinalResult()`:

```python
import json, wave, vosk

SAMPLE_RATE = 16000
CHUNK = 4000                                  # samples per read = 0.25 s
model = vosk.Model("/root/speech-models/vosk-model-small-en-us-0.15")  # load ONCE

def transcribe_wav(path):
    rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)   # fresh per utterance
    parts = []
    with wave.open(path, "rb") as wf:
        while True:
            data = wf.readframes(CHUNK)
            if not data:
                break
            if rec.AcceptWaveform(data):                  # an utterance final
                text = json.loads(rec.Result()).get("text", "").strip()
                if text:
                    parts.append(text)
    parts.append(json.loads(rec.FinalResult()).get("text", "").strip())
    return " ".join(p for p in parts if p).strip()
```

The **model loads once** (~300 MB, seconds) and recognizers are cheap — never
re-load the model per clip. For a button-driven UI, record-then-decode beats
streaming VAD: the press decision *is* the utterance boundary. The worked
example — mic thread owning the `pyaudio` stream, `queue.Queue` UI hand-off,
`--file` headless test mode — is `templates/push_to_talk.py`.

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

**Verified on this board (v1.2.0 bundle, 2026-10):**

| | |
|---|---|
| Bundle | `piper_arm64.tar.gz` = `piper` + `libespeak-ng.so.1`, `libonnxruntime.so.1.14.1`, `libpiper_phonemize.so`, `espeak-ng-data/` (~48 MB) |
| Linking | `RUNPATH=$ORIGIN` — the bundled `.so`s are found next to the binary, nothing goes in `/usr/lib` |
| **No `LD_PRELOAD` needed** | needs `GLIBC_2.25` + `GLIBCXX_3.4.21`; buster has glibc 2.28 / libstdc++ 3.4.25. Unlike Vosk, Piper needs no Debian-11 `libstdc++` |
| Text input | **stdin** in v1.2.0 (`echo text \| piper ...`); the positional `-- "text"` form only exists from piper1-gpl 1.3.0 |
| Phonemizer data | pass `--espeak_data <bundle>/espeak-ng-data` so it does not depend on cwd |
| Output | `medium`/`high` = 22.05 kHz mono 16-bit; `low` = 16 kHz |
| Speed | **measured on the RK3308 bench:** voice load **4.2–5.8 s per invocation** (the CLI is one-shot — it reloads the model every call) + inference at **RTF ≈ 1.97**, i.e. ~2x *slower* than real time; "Hello world!" is ~8 s end to end. A Pi 4 manages 0.1–0.5 RTF — the A35 cores are the difference. Use `low` (16 kHz, ~20 MB) when latency matters, `medium` for quality; `high` is pointless here |

**Upstream moved:** `rhasspy/piper` is archived; development is
`OHF-Voice/piper1-gpl`, **GPLv3 from v1.3.0** (the v1.2.0 binary above is still
MIT). The `piper-tts` wheel is now 3.9+, so on Py 3.7 the binary is the only
route.

Install it offline with a manifest `untar` entry rather than a `files` push —
SFTP `put` would drop the exec bit and flatten the bundled `.so` symlinks
(`system.md`, "Installing packages without Wi-Fi").

Playback is a separate choice, and it follows the speaker rather than the TTS:

| Output | Call | Why |
|---|---|---|
| Bluetooth A2DP | `paplay out.wav` | the sink is `bluez_sink.<MAC>.a2dp_sink` — **Pulse-only**, invisible to ALSA (`bluetooth.md` §2) |
| USB speaker | `aplay -q -D hw:N,0 out.wav` | a real ALSA card; Pulse may be masked |
| anything, Pulse up | `unihiker.Audio().play(...)` | Pulse client, so it follows the default sink |

Idiom: dispatch on `pactl` — `paplay out.wav` when Pulse answers,
`aplay -q -D hw:N,0 out.wav` otherwise — and take a `--device` flag to force a
card.

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
