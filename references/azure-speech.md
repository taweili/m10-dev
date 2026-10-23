# 7. Azure Speech on the M10

> Reviewed 2026-10-20. **Use SDK 1.34.0** — 1.38.0+ links against
> `GLIBC_2.29` and won't load on the M10's glibc 2.28 (`OSError: version
> 'GLIBC_2.29' not found`). 1.34.0 is the newest that still imports cleanly
> on this board. It predates `SpeechConfig.from_endpoint()` (added later),
> so use the equivalent `SpeechConfig(subscription=KEY, endpoint=URL)`
> constructor. Python ≥ 3.7; `manylinux2014_aarch64` wheel is ~3.1 MB.
> Requires **Wi-Fi** (`wifi.md`) — there is no offline mode.

## 7.1 Why Azure Speech on the M10

Cloud STT + neural TTS from one SDK. Free tier (F0) gives **5 audio hours of
STT** and **0.5 M characters of neural TTS per month** — a demo day of ~100
utterances and ~30 TTS turns is nowhere near either cap.

| | Vosk (on-device) | Azure STT (F0) |
|---|---|---|
| Offline? | ✅ | ❌ Wi-Fi required |
| Latency per clip | 0.2–0.5 s | 300–800 ms (network-dominated) |
| Word accuracy | ~80 % (small en-US) | ~95 %+ (neural) |
| Languages | per model | 100+ via `en-US` string |
| RAM | ~300 MB model | ~30–50 MB SDK |
| Free quota | ∞ | 5 h / month |
| Extras | — | push-stream, continuous, word timings, translation, custom models (S0) |

Azure wins on accuracy and is the only real *voice-out* option at M10 scale
(Vosk is STT only). The practical limit on F0 is the **20 real-time TTS
transactions per 60 seconds** throttle, not the character cap — batch short
replies into one SSML string to stay under it.

## 7.2 Compatibility with this board

SDK 1.34.0 ships a prebuilt **`py3-none-manylinux2014_aarch64`** wheel (3.1 MB):

| Tag | Needs | M10 has | OK |
|---|---|---|---|
| `py3` | Python ≥3.7 | 3.7.3 | ✅ |
| `none` | pure Python | — | ✅ |
| `manylinux2014` | glibc ≥2.17 | 2.28 | ✅ |
| `aarch64` | ARM64 | RK3308 | ✅ |
| OpenSSL | 1.x or 3.x | 1.1 | ✅ |
| `libasound2` | any | present | ✅ |
| `ca-certificates` | any | present | ✅ |

**glibc 2.28 pin.** The M10's Debian 10 ships glibc 2.28. Starting at SDK
1.38.0 the `libMicrosoft.CognitiveServices.Speech.core.so` was rebuilt against
`GLIBC_2.29` and fails to load on this board with
`OSError: /lib/aarch64-linux-gnu/libm.so.6: version 'GLIBC_2.29' not found`.
1.34.0 is the newest that works; 1.30.0 and 1.25.0 also import cleanly if
you need to go further back. Debian 10 is not on Microsoft's official list
(their minimum is Debian 11), but the wheel is glibc-based so it loads.
**No `LD_PRELOAD` shim is needed** — that `libstdc++` trick is Vosk-only
(`speech.md` §6).

**API drift vs newer SDKs.** 1.34.0 predates some convenience methods:

| Newer SDK (≥ 1.43) | 1.34.0 equivalent |
|---|---|
| `SpeechConfig.from_endpoint(endpoint, key)` | `SpeechConfig(subscription=key, endpoint=endpoint)` |
| `sdk.Translator` | `sdk.translation.TranslationRecognizer` |
| `sdk.SpeechTranslationConfig` | `sdk.translation.SpeechTranslationConfig` |

Everything in this reference (push-stream STT, neural TTS, word boundaries,
SSML, translation, custom voices) works on 1.34.0. Translation is just
imported from the `translation` submodule rather than the top-level namespace.

**ARM64 keyword-spotting bug.** On Linux ARM64 the SDK's built-in keyword
detector raises `SPXERR_EXTENSION_LIBRARY_NOT_FOUND`. Button-driven
utterance boundaries (§7.4) sidestep this entirely — don't use keyword
spotting.

**OpenSSL on newer hosts.** SDK 1.40 fixed OpenSSL 3.x detection on
arm64; anything ≥ 1.40 is safe if you later move to a modern distro. The
M10's OpenSSL 1.1 is unaffected.

## 7.3 Setup and install

### Account

1. Create a **Foundry Tools → Speech** resource at tier **F0** (free).
2. Copy **key 1** and the **region** (`eastus`, `westus2`,
   `australiacentral`, `francecentral`, …). Pick the geographically closest to
   your IP.
3. Note the **endpoint URL** — it looks like
   `https://eastus.api.cognitive.microsoft.com/`. Passing `endpoint=` directly
   to the `SpeechConfig` constructor is more robust than `region=` if the
   resource is later renamed or its region is ambiguous. (SDK 1.43+ added a
   convenience classmethod `SpeechConfig.from_endpoint(endpoint, key)` for
   this; 1.34.0 does not have it, so use the constructor form shown below.)
4. Do **not** enable auto-rotation — the SDK only uses one key at a time.

Keep the key off the repo: read from `$AZURE_SPEECH_KEY` and
`$AZURE_SPEECH_ENDPOINT` on the board, with a gitignored
`/root/g-buddy/llm.env` fallback (same pattern `g-buddy` uses for OpenAI).

```python
import azure.cognitiveservices.speech as sdk
cfg = sdk.SpeechConfig(subscription=KEY, endpoint=ENDPOINT)
```

### Install — online

```bash
pip3 install 'azure-cognitiveservices-speech==1.34.0'
python3 -c "import azure.cognitiveservices.speech as s; print(s.__version__)"
```

Pin the version. The default `pip install azure-cognitiveservices-speech`
pulls the latest (1.52.0) which requires `azure-core>=1.33`, and azure-core
1.33 requires Python ≥ 3.8 — pip will backtrack but you'll get a version
that needs glibc 2.29 and fails on import. On the M10's Python 3.7 / glibc
2.28, only 1.34.0 and earlier import cleanly (§7.2).

### Install — offline

Add the wheel + `azure-core` to `offline/manifest.json` on the PC, then run
the skill's `scripts/m10-offline-install.py`. Reachability smoke test once
installed (should print `401` — reachable at the DNS layer):

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  https://speech.platform.bing.com/speech/recognize
```

**Expected result on a healthy install: `1.34.0`.** If you see anything else,
`ldd` the `.so` under `site-packages/azure/cognitiveservices/speech/` to see
which glibc version it wants, and pin to an older SDK.

## 7.4 STT

### Choose a mode

| Mode | Use case | API |
|---|---|---|
| One-shot | press button → SDK waits for silence → text | `recognize_once_async().get()` |
| Push-stream | press button → feed mic frames → release → text | `PushAudioInputStream` + `start_continuous_recognition()` |
| Continuous | always-on, wake word, long meeting | same as push-stream, no stop |

The M10's button-driven UX maps cleanly to **push-stream**: the button
decides the utterance boundary, so you don't rely on Azure's end-silence
heuristic. One-shot is fine for a smoke test but has a **15-second ceiling**
and no early-stop — bad UX for a companion.

### Push-stream with the M10 mic (pyaudio)

```python
import azure.cognitiveservices.speech as sdk
import pyaudio

SAMPLE_RATE = 16000
CHUNK = 4000  # samples per read = 0.25 s

cfg = sdk.SpeechConfig(subscription=KEY, endpoint=ENDPOINT)
cfg.speech_recognition_language = "en-US"
cfg.set_property(sdk.PropertyId.SpeechServiceResponse_PostProcessingOption,
                 "PostRefinement")   # better accuracy on long/noisy streams

fmt = sdk.audio.AudioStreamFormat(
    samples_per_second=SAMPLE_RATE, bits_per_sample=16, channels=1)
push = sdk.audio.PushAudioInputStream(stream_format=fmt)
audio = sdk.audio.AudioConfig(stream=push)
rec = sdk.SpeechRecognizer(speech_config=cfg, audio_config=audio)

def on_recognizing(evt):           # interim text while the user talks
    if evt.result.text:
        events.put(("interim", evt.result.text))

def on_recognized(evt):            # final result for the utterance
    if evt.result.text:
        events.put(("final", evt.result.text))

def on_canceled(evt):
    d = evt.cancellation_details
    events.put(("error", d.error_details or str(d.reason)))

rec.recognizing.connect(on_recognizing)
rec.recognized.connect(on_recognized)
rec.canceled.connect(on_canceled)
rec.start_continuous_recognition()

# ── mic thread ──
p = pyaudio.PyAudio()
dev = next(i for i in range(p.get_device_count())
           if p.get_device_info_by_index(i)["maxInputChannels"] > 0
           and "loopback" not in
              p.get_device_info_by_index(i)["name"].lower())
stream = p.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
                input=True, input_device_index=dev,
                frames_per_buffer=CHUNK)

recording = True
while recording:
    push.write(stream.read(CHUNK, exception_on_overflow=False))
push.close()                      # end-of-stream → Azure flushes finals
rec.stop_continuous_recognition().get()
```

**Why push-stream over `AudioConfig(use_default_microphone=True)`?**
On this bench `pulseaudio` is masked, and the ALSA default card is `hw:1,0`
but `arecord -D hw:1,0` refuses anything other than 8 channels
(`m10-api.md` §5). SDK paths that try to open the "default" device land on
a channel count the codec rejects. Push-stream + pyaudio sidesteps both
problems and lets you reuse the recording loop from
`templates/push_to_talk.py` verbatim.

**`PushAudioInputStream.write(buffer)` needs raw bytes** — no audio header.
Replay from a WAV file? Slice off the RIFF header first, or read via
`wave.open()` and hand over `readframes()` output.

### One-shot for the fastest smoke test

```python
rec = sdk.SpeechRecognizer(
    speech_config=cfg,
    audio_config=sdk.audio.AudioConfig(use_default_microphone=True))
r = rec.recognize_once_async().get()
if r.reason == sdk.ResultReason.RecognizedSpeech:
    text = r.text
```

Do this against pyaudio-driven input first if `use_default_microphone=True`
hangs on the bench — you'll know whether the failure is authentication or the
mic path.

### Recognize from a file (headless test)

The M10's `hw:1,0` is finicky, so keep a `--file speech.wav` mode that
replays a captured clip through the same push-stream path:

```python
import wave
def recognize_file(path):
    fmt = sdk.audio.AudioStreamFormat(samples_per_second=16000,
                                      bits_per_sample=16, channels=1)
    push = sdk.audio.PushAudioInputStream(stream_format=fmt)
    audio = sdk.audio.AudioConfig(stream=push)
    rec = sdk.SpeechRecognizer(speech_config=cfg, audio_config=audio)
    with wave.open(path, "rb") as wf:
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            push.write(data)
    push.close()
    r = rec.recognize_once_async().get()
    return r.text if r.reason == sdk.ResultReason.RecognizedSpeech else None
```

### Options

- `cfg.speech_recognition_language = "en-US"` (or any supported language)
- Auto language detect via
  `sdk.languageconfig.AutoDetectSourceLanguageConfig(["en-US", "fr-FR"])`
- Better accuracy for long streams:
  `cfg.set_property(sdk.PropertyId.SpeechServiceResponse_PostProcessingOption,
                    "PostRefinement")`

### Result fields

`.text`, `.confidence`, `.offset`, `.duration`, `.json` (full JSON with
word-level timings), `.nbest_results`.

### Error handling

`.reason` is the primary discriminator. On the M10 you'll mostly see three:

| `.reason` | Detail | Typical cause on this bench |
|---|---|---|
| `RecognizedSpeech` | success → `.text` | — |
| `NoMatch` | `.no_match_details.kind` ∈ `Babble` (noise) / `InitialSilenceTimeout` (silence) / `EndSilenceTimeout` | button pressed with no speech, or room noise on the small mic |
| `Canceled` | `.cancellation_details.error_code` / `.error_details` | `SPXERR_NO_DATA` = Wi-Fi down; certificate errors = stale clock; `SPXERR_EXTENSION_LIBRARY_NOT_FOUND` = wrong endpoint/key **or** the ARM64 keyword-spotting bug |

Latency on a warm Wi-Fi connection: **300–800 ms** from end-of-speech to
`RecognizedSpeech`. Cold first recognition adds ~200 ms for TLS setup.

### Quota

F0: **5 audio hours / month** shared across standard + custom STT (batch is
not in F0). Every *second of audio sent* counts — silence included. At 100
utterances of 5 s a day that's ~8 h/month — still within budget.

## 7.5 TTS

### Output format — pick raw PCM

`SpeechSynthesisResult.audio_data` is a `bytes` object of whatever format you
configured. To skip WAV header parsing and feed straight to pyaudio:

```python
cfg.set_speech_synthesis_output_format(
    sdk.SpeechSynthesisOutputFormat.Raw24Khz16BitMonoPcm)
```

`Raw24Khz16BitMonoPcm` is the natural pick: 24 kHz sounds good on any USB DAC,
16-bit mono matches pyaudio's default, and no RIFF header means the bytes can
be written to the output stream directly. If quality is not a concern,
`Raw16Khz16BitMonoPcm` is smaller and matches the mic sample rate.

Full synthesis → play helper:

```python
import pyaudio
import azure.cognitiveservices.speech as sdk

cfg = sdk.SpeechConfig(subscription=KEY, endpoint=ENDPOINT)
cfg.speech_synthesis_voice_name = "en-US-JennyNeural"
cfg.speech_synthesis_language = "en-US"
cfg.set_speech_synthesis_output_format(
    sdk.SpeechSynthesisOutputFormat.Raw24Khz16BitMonoPcm)

def speak(text):
    synth = sdk.SpeechSynthesizer(speech_config=cfg, audio_config=None)
    result = synth.speak_text_async(text).get()
    if result.reason != sdk.ResultReason.SynthesizingAudioCompleted:
        raise RuntimeError(result.cancellation_details)

    pcm = result.audio_data          # raw PCM, no header
    p = pyaudio.PyAudio()
    out = p.open(format=pyaudio.paInt16, channels=1, rate=24000,
                 output=True, frames_per_buffer=4800)
    out.write(pcm)                   # blocks until written
    out.close()
    p.terminate()
```

### Why not `use_default_speaker=True`

The quickstart shows `AudioOutputConfig(use_default_speaker=True)`, which on
a stock Ubuntu box routes through PulseAudio. On this bench pulseaudio is
masked and the M10 has no onboard speaker, so you'd need to:

```bash
systemctl unmask pulseaudio
systemctl enable --now pulseaudio
aplay -l                                    # confirm a USB speaker is a sink
pactl set-default-sink <speaker-name>
```

Then `use_default_speaker=True` should just work — but you take on one more
daemon and one more failure mode. Synthesize to raw bytes and play via
pyaudio (the same library `03` uses for input) and skip PulseAudio entirely.

### Word boundaries for a karaoke UI

For a `g-buddy`-style animated face or mouth, per-word highlighting is the
biggest "wow" from Azure TTS. No offline voice can do it:

```python
cfg.set_property(sdk.PropertyId.SpeechServiceResponse_RequestSentenceBoundary,
                 "true")

synth = sdk.SpeechSynthesizer(speech_config=cfg, audio_config=None)

def on_word(evt):
    if evt.boundary_type == sdk.SpeechSynthesisBoundaryType.Word:
        # audio_offset and duration are in TICKS (1 tick = 100 ns), not samples
        events.put(("word", evt.text, evt.audio_offset, evt.duration))

synth.synthesis_word_boundary.connect(on_word)
result = synth.speak_text_async(text).get()
```

`SpeechSynthesisBoundaryType` has three values: `Word`, `Punctuation`,
`Sentence`. Only `Word` is useful for karaoke — filter the rest.
`audio_offset` and `duration` are in ticks (100 ns units), not samples —
divide by `240` (100 ns × 24 000 Hz) to get samples for 24 kHz output.

The callback fires from an **SDK worker thread** — never touch Tk widgets
directly from it. Push to an `events` queue and let the main loop apply the
update on the next frame.

### Voice selection (F0)

F0 exposes the full neural voice roster but **not** the HD variants
(`*.DragonHDLatestNeural` are S0-only). Popular English options:

| Voice name | Character |
|---|---|
| `en-US-JennyNeural` | warm default female |
| `en-US-GuyNeural` | upbeat male |
| `en-US-AriaNeural` | friendly female |
| `en-US-DavisNeural` | youthful |
| `en-US-ChristopherNeural` | neutral |
| `en-US-AvaNeural` | soft female |
| `en-GB-SoniaNeural` | UK female |
| `en-AU-NatashaNeural` | Australian |

Voice priority: SSML `<voice>` > `speech_synthesis_voice_name` >
`speech_synthesis_language` default. Multiple `<voice>` blocks in one SSML
string switch voices mid-utterance.

### SSML recipes

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

Use `synth.speak_ssml_async(ssml).get()`.

### Other output formats

The full enum (`SpeechSynthesisOutputFormat`) spans ~35 entries. Common
useful ones:

| Format | Use |
|---|---|
| `Raw16Khz16BitMonoPcm` | smallest, no header; matches mic rate |
| `Raw24Khz16BitMonoPcm` | **recommended** for pyaudio playback |
| `Riff16Khz16BitMonoPcm` | WAV header, 16 kHz |
| `Riff24Khz16BitMonoPcm` | WAV header, 24 kHz |
| `Audio24Khz48KBitRateMonoMp3` | tiny file, needs an MP3 decoder (M10 image doesn't ship one) |
| `Audio16Khz128KBitRateMonoMp3` | Azure's default; still needs MP3 decoding |
| `Audio48Khz192KBitRateMonoMp3` | highest MP3 quality |
| `AmrWb16000Hz` | telephony codec |

Raw formats have **no header** — pass them straight to a decoder. RIFF formats
have a WAV header — you must parse it before feeding pyaudio. Prefer raw
unless you need to write a `.wav` file to disk.

### Translation

On 1.34.0 the translation API lives in the `translation` submodule
(newer SDKs re-export it at the top level as `Translator` / `SpeechTranslationConfig`):

```python
import azure.cognitiveservices.speech.translation as st

tcfg = st.SpeechTranslationConfig(subscription=KEY, endpoint=ENDPOINT)
tcfg.speech_recognition_language = "en-US"
tcfg.addTargetLanguage("ja-JP")
tr = st.TranslationRecognizer(
    config=tcfg,
    audio_config=sdk.audio.AudioConfig(use_default_microphone=True))
r = tr.translate_once_async().get()     # r.text + r.translation_text
```

### Quota & throttling

F0: **0.5 M billable characters / month**. Billable characters count only
the text between tags, not SSML markup. At 500 chars per turn that's
~1000 turns/day of headroom.

The practical limit is the **20 real-time TTS transactions / 60 s** throttle
per F0 resource. Batching 4 greetings for a test loop can hit `429`; back
off ~1 s and retry, or combine them into a single SSML string so the
transaction count drops.

Max audio per TTS request is **10 minutes** (truncated beyond that). Max
50 distinct `<voice>` and `<p>` tags in one SSML WebSocket message, 64 KB
SSML payload.

## 7.6 Latency budget for a round trip

For a `mic → Azure STT → LLM → Azure TTS → USB speaker` pipeline on a warm
Wi-Fi connection:

| Stage | Time |
|---|---|
| Button press → recognizer.start() | ~30 ms |
| STT final result after end-of-speech | 300–800 ms |
| LLM first token | 300–800 ms (network-dominated) |
| LLM full short reply | 1–3 s |
| TTS first audio byte | 200–500 ms |
| TTS full audio + playback | reply length |
| **Total button → spoken reply** | **~3–8 s** |

If end-to-end latency matters more than accuracy, keep Vosk for STT
(sub-second on-device) and use Azure only for TTS. For any animated mouth or
karaoke effect, drive the animation from word-boundary events — they line
up with what the speaker actually says, not what the LLM streamed.

## 7.7 Troubleshooting (M10-specific)

| Symptom | First move |
|---|---|
| TLS `CERTIFICATE_VERIFY_FAILED` on first call | Board clock is stale. `date -u` on the board; the M10 has no RTC so a stale clock is common. Fix with `date -s "$(curl -sI https://www.google.com \| grep '^Date:' \| cut -d' ' -f2-)"` or set from the host |
| `SPXERR_NO_DATA` | Wi-Fi down, or endpoint is wrong. `ping -c3 8.8.8.8`; `curl -sI <endpoint>` |
| `SPXERR_FORMAT_NOT_SUPPORTED` | Format mismatch — must be 16 kHz / 16-bit / mono PCM |
| Recognizer opens but never gets a result | Mic path. Push-stream with pyaudio frames, not `use_default_microphone=True` |
| `use_default_microphone=True` hangs | PulseAudio is masked. Use push-stream (§7.4) |
| TTS to speaker is silent | `aplay -l` shows nothing → no USB speaker, or PulseAudio is masked. Use the pyaudio path (§7.5) |
| Word-boundary callback never fires | `SpeechServiceResponse_RequestSentenceBoundary` must be set to `"true"` *before* creating the `SpeechSynthesizer` |
| `429` from TTS | Hit the 20-tx/60-s F0 throttle. Back off ~1 s and retry; batch short phrases into one SSML string |
| `SPXERR_EXTENSION_LIBRARY_NOT_FOUND` | Usually bad endpoint/key. Also the signature of the ARM64 keyword-spotting bug (§7.2) — don't use keyword spotting |
| `Connection refused` / DNS | Wi-Fi + `ping -c3 8.8.8.8`; DNS server set (`wifi.md`) |

Reachability check (expect **401**):
`curl -s -o /dev/null -w "%{http_code}" https://speech.platform.bing.com/speech/recognize`

## 7.8 Checklist

```
[ ] Wi-Fi up (wifi.md)
[ ] Board clock sane (TLS needs it): date -u
[ ] Speech resource created (F0); key + region + endpoint noted
[ ] pip3 install 'azure-cognitiveservices-speech==1.34.0' (pinned — see §7.2)
[ ] python3 -c "import azure.cognitiveservices.speech as s; print(s.__version__)"
[ ] recognize_once_async() returns text against the M10 mic
[ ] TTS synthesis to Raw24Khz16BitMonoPcm plays through a USB speaker via pyaudio
[ ] Word-boundary callback fires and updates a widget via the events queue
[ ] 20-Tx/60s throttle handled (back off + retry)
[ ] $AZURE_SPEECH_KEY + $AZURE_SPEECH_ENDPOINT in /root/g-buddy/llm.env
```

## Sources

- PyPI `azure-cognitiveservices-speech` — pinned at **1.34.0** for the M10
  (glibc 2.28 constraint; see §7.2). Python ≥ 3.7, wheel
  `py3-none-manylinux2014_aarch64` (~3.1 MB). `SpeechConfig(subscription,
  endpoint)` constructor (not `from_endpoint()` — that arrived in 1.43+).
  Translation lives under `azure.cognitiveservices.speech.translation`.
- Microsoft Learn — Foundry Tools Speech pricing + quotas (F0: 5 h STT +
  0.5 M chars TTS / month; 20 real-time TTS transactions per 60 s; 10 min
  max audio per TTS request).
- Microsoft Learn — `SpeechSynthesisOutputFormat` enum, `AudioStreamFormat`
  signature, `PushAudioInputStream.write(buffer: bytes)`,
  `SpeechSynthesisBoundaryType` enum (Word / Punctuation / Sentence),
  `SpeechSynthesisWordBoundaryEventArgs` (`audio_offset`/`duration` in ticks).
- Microsoft Learn — how-to-use-audio-input-streams (raw PCM, little-endian,
  no audio header in `write()`).
- Azure Samples `speech_sample.py` — reference push-stream and one-shot
  patterns.
- Skill `references/m10-api.md` §5 — mic device, `hw:1,0` channel quirks,
  PulseAudio behaviour on this bench.
- Skill `references/speech.md` — decision table, model sizes, offline
  pipelines, and the Vosk ABI shim context.
