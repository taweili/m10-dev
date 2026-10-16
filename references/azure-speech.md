# 7. Azure Speech on the M10

The recommended **cloud** speech option: real-time STT + neural TTS, 5 h STT and
500 K chars TTS free per month. Requires **Wi-Fi** (`wifi.md`) — there is no
offline mode.

## Compatibility

The SDK ships a prebuilt **`py3-none-manylinux2014_aarch64`** wheel (≈2.6 MB):

| Tag | Needs | M10 has | OK |
|---|---|---|---|
| `py3` | Python ≥3.7 | 3.7.3 | ✅ |
| `none` | pure Python | — | ✅ |
| `manylinux2014` | glibc ≥2.17 | 2.28 | ✅ |
| `aarch64` | ARM64 | RK3308 | ✅ |

Debian 10 is *not* officially supported (docs say 11/12, Ubuntu 20.04+) but the
wheel works; DFRobot's community project (`zzzqww/DFRobot`) proves it.
Prereqs already present: `libasound2`, `libssl1.1`, `ca-certificates`.

⚠️ Known bug since SDK 1.11: **keyword detection fails on ARM64**
(`SPXERR_EXTENSION_LIBRARY_NOT_FOUND`). Don't use keyword spotting (or pin 1.10).

```bash
pip install azure-cognitiveservices-speech
python3 -c "import azure.cognitiveservices.speech as s; print(s.__version__)"
```

Offline pip? Download the wheel on the PC, SFTP it over, add `azure-core`, then
`pip install /path/to/*.whl`.

## Setup

Create a **Speech** resource (Free tier **F0**) in the Azure portal and note
**key**, **region** (`eastus`, `westus`, …) and **endpoint**.

F0 quotas: 5 audio h/month STT, 500 K chars/month neural TTS. Free tier *stops*
at the cap (no surprise billing).

```python
import azure.cognitiveservices.speech as sdk
cfg = sdk.SpeechConfig(subscription="KEY", region="eastus")
```

## STT

**One-shot from the mic** — waits for silence, **max 15 s**:

```python
audio = sdk.audio.AudioConfig(use_default_microphone=True)
rec = sdk.SpeechRecognizer(speech_config=cfg, audio_config=audio)
r = rec.recognize_once_async().get()
if r.reason == sdk.ResultReason.RecognizedSpeech:
    print(r.text)
```

**From a file** (record with `unihiker.Audio`, or reuse a saved clip — the M10's
16 kHz mono 16-bit matches Azure's expected format):

```python
audio = sdk.audio.AudioConfig(filename="/tmp/voice_input.wav")
```

**Continuous / streaming** — connect `recognizing` (interim) and `recognized`
(final), then `start_continuous_recognition()` and poll a done flag.

**Push stream** — feed frames yourself (pyaudio/`unihiker.Audio`), when you
don't want the system default mic:

```python
fmt = sdk.audio.AudioStreamFormat(16000, 16, 1)          # 16 kHz, 16-bit, mono
push = sdk.audio.PushAudioInputStream(stream_format=fmt)
audio = sdk.audio.AudioConfig(stream=push)
# ... recognizer.start_continuous_recognition(); then in a loop:
push.write(stream.read(4000, exception_on_overflow=False))
```

**Options:** `cfg.speech_recognition_language = "en-US"`; auto language detect
via `sdk.languageconfig.AutoDetectSourceLanguageConfig()`; better accuracy for
long streams with
`cfg.set_property(sdk.PropertyId.SpeechServiceResponse_PostProcessingOption, "PostRefinement")`.

**Result fields:** `.text`, `.confidence`, `.offset`, `.duration`, `.json`,
`.nbest_results`.

**Error handling** — check `.reason`:

| `.reason` | Meaning |
|---|---|
| `RecognizedSpeech` | success → `.text` |
| `NoMatch` | `.no_match_details.kind` ∈ `Babble` (noise), `InitialSilenceTimeout`, `EndSilenceTimeout` |
| `Canceled` | `.cancellation_details.error_details` / `.error_code` — usually network or bad key/region |

## TTS

```python
cfg.speech_synthesis_language = "en-US"
cfg.speech_synthesis_voice_name = "en-US-JennyNeural"

# to the USB speaker (see m10-api.md §5 — there is no onboard speaker)
synth = sdk.SpeechSynthesizer(speech_config=cfg,
        audio_config=sdk.audio.AudioOutputConfig(use_default_speaker=True))
synth.speak_text_async("Hello from the M10").get()

# or to a file, then play/keep it
synth = sdk.SpeechSynthesizer(speech_config=cfg,
        audio_config=sdk.audio.AudioOutputConfig(filename="/tmp/out.wav"))
```

**Voice priority:** SSML `<voice>` > `speech_synthesis_voice_name` >
`speech_synthesis_language` default. Common free-tier voices:
`en-US-JennyNeural` (warm), `GuyNeural` (upbeat), `AriaNeural`, `DavisNeural`,
`ChristopherNeural`, `AvaNeural`. HD voices (`*:DragonHDLatestNeural`) need S0.

**Word boundaries for a karaoke/GUI effect** — request boundaries, then update a
label per word:

```python
cfg.set_property(sdk.PropertyId.SpeechServiceResponse_RequestSentenceBoundary, "true")
synth.synthesis_word_boundary.connect(
    lambda evt: label.config(text=evt.text)
    if evt.boundary_type != sdk.SpeechSynthesisBoundaryType.Sentence else None)
```

**Output formats:** default is 16 kHz 16-bit PCM WAV; change with
`cfg.set_speech_synthesis_output_format(sdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm)`
(or `…Audio24Khz160KBitRateMonoMp3`, etc.).

### SSML recipes

Use `synth.speak_ssml_async(ssml).get()`:

```xml
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
  <voice name="en-US-GuyNeural">
    <prosody rate="fast" pitch="+10%" volume="loud">Loud and quick</prosody>
    <prosody rate="slow" pitch="-5%" volume="soft">slow and quiet.</prosody>
    Wait<break time="500ms"/>then continue.
    This is <emphasis level="strong">important</emphasis>.
    Date: <say-as interpret-as="date">2025-07-06</say-as>,
    time: <say-as interpret-as="time">14:30</say-as>.
  </voice>
</speak>
```

Multiple `<voice>` blocks in one SSML string switch voices mid-utterance.

## Translation

```python
tcfg = sdk.SpeechTranslationConfig(subscription="KEY", region="eastus")
tcfg.speech_recognition_language = "en-US"; tcfg.addTargetLanguage("ja-JP")
tr = sdk.Translator(config=tcfg, audio_config=sdk.audio.AudioConfig(use_default_microphone=True))
r = tr.translate_once_async().get()     # r.text + r.translation_text
```

## Full assistant pipeline

`mic → Azure STT → GPT → Azure TTS → USB speaker`:

```python
text = recognize()                       # Azure
if text:
    reply = ask_gpt(text)                # openai.chat.completions.create(...)
    speak(reply)                         # Azure TTS
```

Add a `GUI(w=240, h=320)` status/transcript label and drive it from the
callbacks. Latency: STT ~0.5–2 s, TTS first audio ~0.2–0.5 s, full round trip
~3–8 s. SDK memory is negligible (~30–50 MB RSS); audio is processed server-side.

## Troubleshooting

| Error | Fix |
|---|---|
| `SPXERR_FORMAT_NOT_SUPPORTED` | Must be 16 kHz / 16-bit / mono PCM |
| `SPXERR_MICROPHONE_NOT_FOUND` | `arecord -l`; check the device / ALSA default |
| `SPXERR_NO_DATA` | No network, or bad key/region |
| `SPXERR_EXTENSION_LIBRARY_NOT_FOUND` | ARM64 keyword-spotting bug — don't use keyword spotting |
| `Connection refused` / DNS | Wi-Fi + `ping -c3 8.8.8.8` |
| SSL error | `apt install ca-certificates`; `openssl version` should be 1.1.x |

Reachability check:
`curl -s -o /dev/null -w "%{http_code}" https://speech.platform.bing.com/speech/recognize`
→ **401** means reachable.

## Checklist

```
[ ] Wi-Fi up (wifi.md)
[ ] Speech resource created (F0), key + region noted
[ ] pip install azure-cognitiveservices-speech
[ ] import + version prints
[ ] recognize_once_async() returns text
[ ] speak_text_async() audible on a USB speaker
[ ] (optional) GPT integration, word-boundary GUI
```
