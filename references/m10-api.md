# 4a. Using M10 functions

Two libraries, two layers:

```
unihiker   GUI(), Audio()          → Tkinter screen, WAV record/playback
pinpong    Board().begin()         → GPIO, buttons, buzzer, sensors, IMU
           pinpong.extension.unihiker  → the board's pre-wired objects
```

```python
from unihiker import GUI, Audio
from pinpong.board import Board, Pin, Servo
from pinpong.extension.unihiker import *   # button_a, button_b, buzzer, light, ...
Board().begin()                            # MUST come before touching hardware
```

The coprocessor is a GD32VF103 RISC-V; pinpong ≥0.6 talks to it through native
Linux IO (not Firmata).

## 1. Screen & GUI

Portrait is **240×320**; origin top-left, +x right, +y down, centre ≈ (120,160).
Landscape (320×240, centre (160,120)) needs the Xorg rotation in §7.

```python
gui = GUI()                    # or GUI(w=320, h=240) in landscape
```

| Call | Purpose |
|---|---|
| `draw_text(text, x, y, font_size, color, origin)` | text |
| `fill_rect / draw_rect / fill_circle / draw_circle / fill_round_rect / draw_round_rect / draw_line` | shapes |
| `draw_image(x, y, w, h, image, origin, onclick)` | PNG/JPG **filename or PIL `Image`** |
| `draw_digit`, `draw_emoji`, `draw_clock / fill_clock`, `draw_qr_code` | extras |
| `add_button(text, x, y, w, h, onclick, state)` | touch button |
| `on_mouse_move(handler)` | touch/drag → `handler(x, y)` |
| `on_key_click(onclick=fn)` | USB keyboard (**keyword arg only**) |
| `GUI.clear()`, `w.remove()`, `GUI.remove(w)` | destroy |

**Mutate, don't recreate:** `w.config(text=…, x=…, y=…, r=…, color=…)`. Redrawing
in a loop flickers.

**Anchors:** every widget accepts `origin=` — `center`, `top`, `bottom`, `left`,
`right`, `nw|ne|sw|se`, or `n|s|w|e`.

**Colours:** `#RRGGBB`, `(r,g,b)`, or Tk names (`"red"`).

**The two hard-won quirks:**

1. **`fill_rect` has no radius.** `fill_rect(..., r=X)` is silently ignored at
   creation; `w.config(r=X)` raises `_tkinter.TclError: unknown option "-r"`.
   For anything round use **`fill_circle`** (which does accept `r=`).
2. **`fill_circle`'s `x, y` are the centre**, not a corner.

**Image files must sit in the same directory as the running `.py`.** A PIL
`Image` also works for `image=` (good for camera frames).

**Main loop:** every script ends with `while True: time.sleep(...)`. The Tk event
loop runs on its own thread; the main process just has to stay alive. Ctrl+C
(SIGINT) is a clean exit — the library installs an `exit_handler`.

## 2. Buttons

On the front: **Home**, **A**, **B**. Poll or interrupt:

```python
# poll (fine for UI state machines)
if button_b.is_pressed() and not prev_b: ...        # rising edge
prev_b = button_b.is_pressed()

# interrupt (latency-sensitive)
from pinpong.board import Pin
button_a.irq(trigger=Pin.IRQ_RISING, handler=lambda pin: ...)
#   Pin.IRQ_RISING | Pin.IRQ_FALLING
```

Edge detection with a previous-state variable is the standard way to get
press/release semantics (push-to-talk, toggles) out of a polling loop.

`gui.on_key_click` is for a **USB keyboard**, not the on-board A button.

## 3. Sensors & GPIO

```python
light.read()                                    # 0..~4096 (PT0603)
accelerometer.get_x(); .get_y(); .get_z(); .get_strength()
gyroscope.get_x(); .get_y(); .get_z()

led = Pin(Pin.P25, Pin.OUT);  led.write_digital(1)   # P25 = onboard blue LED
d = Pin(Pin.P20, Pin.IN);     d.value()
pwm = Pin(Pin.P21, Pin.PWM);  pwm.write_analog(200)  # 0..255
adc = Pin(Pin.P12, Pin.ADC);  adc.value()
s = Servo(Pin(Pin.P21));      s.angle(90)            # 0..180
```

Servo-capable pins: `P0 P2 P3 P8 P9 P10 P16 P21 P22 P23`. Pin names follow the
micro:bit-compatible edge connector. `pinpong.libs.*` adds `DHT11`, `Ultrasonic`,
`OLED2864`, `RGB_LEDStrip`, `ColorRecognition`, `Uart`, `I2c`, `Spi`.

## 4. Buzzer

Passive piezo, PWM-driven — **works without any speaker**.

```python
buzzer.pitch(880)          # non-blocking background tone  ← use this in UI loops
buzzer.pitch(880, 4)       # BLOCKS until the 4-beat tone ends
buzzer.stop()
buzzer.play(buzzer.DADADADUM, buzzer.Once)
buzzer.set_tempo(4, 60)    # ticks per beat, bpm
```

⚠️ **`beat` is an integer beat count, not milliseconds.** `pitch(freq, ms/1000.0)`
raises `TypeError: unsupported operand type(s) for &: 'float' and 'int'`. In a
GUI loop always use `pitch(freq)` (non-blocking) or the UI will freeze.

Melodies: `DADADADUM, ENTERTAINER, PRELUDE, ODE, NYAN, RINGTONE, FUNK, BLUES,
BIRTHDAY, WEDDING, FUNERAL, PUNCHLINE, BADDY, CHASE, BA_DING, WAWAWAWAA,
JUMP_UP, JUMP_DOWN, POWER_UP, POWER_DOWN`. Modes: `Once, Forever,
OnceInBackground, ForeverInBackground`.

## 5. Audio & the microphone

```python
from unihiker import Audio
audio = Audio()                        # opens 16 kHz mono 16-bit capture

audio.sound_level()                    # 0..100 %, for voice-activity detection
audio.sound_dBFS()                     # raw dBFS, -96..0  (≈ -51 = noise floor)

audio.start_record("/tmp/clip.wav")    # async start
audio.stop_record()                    # stop + save
audio.record("/tmp/clip.wav", 3)       # blocking, 3 s

audio.play("/tmp/clip.wav")            # blocking
audio.start_play("/tmp/clip.wav")      # non-blocking
audio.pause_play(); audio.resume_play(); audio.stop_play()
```

**There is an onboard capacitive mic** (despite older notes claiming otherwise).
It is wired to the internal RK3308 codec's MIC1, biased by `MICBIAS1` at
`VREFx0.85`, and appears as **`card 1: rockchip,rk3308-acodec` (`hw:1,0`)**, ADC
MIC **group 0 = `Work`** (groups 1–3 are `Mute` and read stuck at ±32768).
Verified acoustically: sounding the buzzer lifts capture from −50.7 to
−28.0 dBFS.

**There is no onboard speaker** — `audio.play()` needs a USB speaker in the
USB-A port. The buzzer is separate and always works.

**Opening a mic yourself (pyaudio):**

```python
import pyaudio
p = pyaudio.PyAudio()
# skip devices whose name contains "loopback" — card 0 is a non-routing loopback
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0 and "loopback" not in info["name"].lower():
        break
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                input=True, input_device_index=i, frames_per_buffer=4000)
```

Two gotchas: the ALSA **`Loopback`** card's playback does *not* reach its capture
side (pure silence), so never rely on it to inject test audio; and
`arecord -D hw:1,0` accepts **only 8 channels** (1/2 → `Channels count non
available`) while pyaudio downmixes to mono fine.

**Testing without a mic:** add a `--file speech.wav` mode that streams a 16 kHz
mono 16-bit WAV through the same code path. `espeak -w out.wav "…"` is installed
on the board — resample 22050 → 16000 with `audioop.ratecv` first.

## 6. Framebuffer (screenshots / visual debug)

`/dev/fb0` (`fb_ili9341`): **240×320, RGB565, 16 bpp**, stride **480 bytes**, no
padding. **This board's PIL 9.0.1 cannot decode RGB565** — `Image.frombuffer` and
`frombytes(..., "raw", "RGB565", 0)` both raise `ValueError: unknown raw mode`.
Decode by hand:

```python
# run ON the board → /tmp/frame.png
import struct
from PIL import Image
W, H, STRIDE = 240, 320, 480
with open("/dev/fb0", "rb") as f:
    data = f.read()
compact = b"".join(data[y*STRIDE : y*STRIDE + W*2] for y in range(H))
px = struct.unpack("<%dH" % (W*H), compact)
buf = bytearray(W*H*3)
for i, p in enumerate(px):
    buf[i*3]   = (p >> 11) << 3            # R
    buf[i*3+1] = ((p >> 5) & 0x3F) << 2    # G
    buf[i*3+2] = (p & 0x1F) << 3           # B
Image.frombytes("RGB", (W, H), bytes(buf)).save("/tmp/frame.png")
```

Fetch it over SFTP, then verify with a colour census / ASCII render / frame diff.
Reading the raw 153 600 bytes is fast; the pixel decode is not — if you need
timing accuracy, capture raw bytes at the moment of interest and decode on the
PC. The framebuffer stays 240×320 even in landscape (X rotates in userspace).

Full playbook — colour census, ASCII art, frame diffing, log correlation, the
GUI↔framebuffer rotation mapping and the tearing pitfall — is in
**`verify-gui.md`**.

## 7. Landscape mode (320×240)

The LCD is physically 240×320. The supported way to rotate is **Xorg's `Rotate`
option** (userspace shadow framebuffer, no reboot, touch remapped by tslib).

Edit `/etc/X11/xorg.conf.d/20-modesetting.conf`:

```
Section "Device"
   Identifier  "Rockchip Graphics"
   Driver      "fbdev"
   Option      "fbdev"   "/dev/fb0"
   Option      "DRI"     "2"
   Option      "Rotate"  "CW"
EndSection

Section "Screen"
   Identifier  "Default Screen"
   Device      "Rockchip Graphics"
   Option      "Rotate"  "CW"
EndSection
```

`systemctl restart lightdm`. `"CW"` = buttons on the left, `"CCW"` = buttons on
the right. Afterwards `xdpyinfo` reports 320×240 and Tk sees the new size.

Then build the GUI in landscape:

```python
gui = GUI(w=320, h=240)
gui.fill_rect(x=0, y=0, w=320, h=240, color=BG)
```

Revert with the `.bak` copy + `systemctl restart lightdm`. A kernel-level
alternative (fbtft `rotate=90` modprobe option + reboot) exists but needs
patching `unihiker.GUI`'s hardcoded 240×320; the `/sys/class/graphics/fb0/rotate`
sysfs is **read-only** here.

**Screenshot orientation:** the framebuffer is still 240×320, so rotate the
fetched image on the PC with `img.rotate(90, expand=True)` to match what the user
sees.

## 8. Speech (STT/TTS)

Short version: **Vosk small** for real-time offline STT, **Piper C++ binary**
for natural offline TTS, **Azure Speech** for the best quality cloud option
(needs Wi-Fi). The `piper-tts` and `elevenlabs` pip packages require Python ≥3.8
and will not install here. There is no onboard speaker, so TTS output needs a
USB speaker; the onboard mic is what you record from.

Vosk is the one piece needing a C++ ABI fix — extract a Debian 11 `libstdc++6`
on the board and `LD_PRELOAD` it (scripts self-restart via `os.execv`, guarded
by `_VOSK_PRELOADED=1`). Models are downloaded on the PC and pushed by SFTP;
the board is offline until Wi-Fi is up (`wifi.md`).

Everything else — option and decision tables, the exact ABI-fix commands, the
canonical decode loop, the model download/deploy recipe, pipeline strategies and
Azure integration — is in **`speech.md`** and **`azure-speech.md`**.

## 9. Gotcha summary

1. `Board().begin()` first, always.
2. End with `while True: time.sleep(...)`; SIGINT is a clean exit.
3. `fill_rect` has no radius → use `fill_circle` (x,y = centre).
4. `on_key_click(onclick=…)` — keyword only, and it's a USB keyboard.
5. `buzzer.pitch` beat is an int count and blocks.
6. No onboard speaker; there *is* an onboard mic.
7. Skip `Loopback` capture devices.
8. PIL can't decode RGB565 here.
9. `config()` to update, not recreate (flicker).
10. Image files live next to the running script.
11. `apt` is broken on this image (Debian 10 EOL) until you repoint it to
    `archive.debian.org` → `system.md`.
12. Cloud speech needs Wi-Fi; on-device models are deployed by SFTP → `speech.md`.
