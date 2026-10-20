# 4a. Using M10 functions

> Reviewed 2026-10-19. Assumes firmware v0.4.2, `unihiker` 0.0.27+ and `pinpong` 0.6.1; version-specific claims are flagged inline.

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
| `add_text_box / add_list_box` | scrollable entry / list (undocumented in the wiki) |
| `on_mouse_move(handler)` | touch/drag → `handler(x, y)` |
| `on_key_click(event, onclick)` | USB keyboard — **two positional args** |
| `GUI.clear()`, `w.remove()`, `GUI.remove(w)` | destroy |

**Mutate, don't recreate:** `w.config(text=…, x=…, y=…, r=…, color=…)`. Redrawing
in a loop flickers. `.remove()` is final — hide by moving off-screen
(`x=-9999, y=-9999`), not by removing.

**Anchors:** `origin=` exists on **text, image, emoji, QR, button, text box and
list box only** — the shape primitives ignore it. Values: `center`, `top`,
`bottom`, `left`, `right`, `nw|ne|sw|se`, `n|s|w|e`.

**Colours:** `#RRGGBB`, `(r,g,b)`, or Tk names (`"red"`).

**The two hard-won quirks:**

1. **`fill_rect` / `draw_rect` have no radius.** `r=` is silently ignored at
   creation; `w.config(r=X)` raises `_tkinter.TclError: unknown option "-r"`.
   Use **`fill_round_rect` / `draw_round_rect`** for rounded corners — they do
   take `r=` (clamped to half the short side).
2. **`fill_circle`'s `x, y` are the centre**, not a corner (rects use top-left).

> The full, source-verified API — every primitive, per-widget `.config()`
> options, `draw_emoji` as a real sprite animator, widget state, threading helpers,
> fonts/brightness and the animation patterns — is in **`gui-drawing.md`**.

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
press/release semantics (push-to-talk, toggles) out of a polling loop. The
full press/release shape, including the state guard:

```python
b = button_b.is_pressed()
if b and not prev_b and state in ("idle", "result"):   # rising edge → start
    start()
elif not b and prev_b and state == "recording":        # falling edge → stop
    stop()
prev_b = b
```

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

**Audio plumbing (host-side checks, run on the board):**

```bash
aplay -l                              # sinks — the USB speaker appears here
arecord -l                            # capture — card 1 = rk3308-acodec
pactl list short sinks; pactl list short sources
pactl set-default-sink <sink-name>    # what Audio.play() will use

amixer -c 1 scontrols                 # find the capture control name
alsamixer -c 1                        # adjust gain interactively
alasctl store                         # persist the mixer state
```

If the mic is quiet, raise the capture gain rather than moving closer; if it
clips, check group 0 is `Work` (groups 1–3 are `Mute`, see above). `Audio()`
uses PulseAudio, so a dead `pulseaudio` looks like a dead mic — restart it
(`recovery.md` §4).

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

`/dev/fb0` (`fb_ili9341`) is **240×320, RGB565, 16 bpp**, stride **480 bytes**,
153 600 bytes total. Two things trip people up:

- **PIL 9.0.1 on the board cannot decode RGB565** (`Image.frombuffer` and
  `frombytes(..., "raw", "RGB565", 0)` raise `ValueError: unknown raw mode`), so
  the decode has to be done by hand.
- The framebuffer **stays 240×320 in landscape** — X rotates in userspace, so a
  `GUI(w=320, h=240)` screen comes back sideways in the raw pixels.

You do not need to write the decoder: `scripts/m10-snapshot.py` uploads it,
captures the frame, pulls it over SFTP, rotates it on the PC
(`--rotate 90` for `Rotate="CW"`) and can print a colour census (`--census`).

```bash
scripts/m10-snapshot.py --rotate 90 --census
```

Reading the raw 153 600 bytes is fast; the pixel decode is not — if you need
timing accuracy, capture raw bytes at the moment of interest and decode on the
PC. The full verification playbook (the PNG grab and how to read it, colour
census, frame diff, GUI↔framebuffer mapping, tearing) is in **`verify-gui.md`**.

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

> **A firmware flash wipes this file** — the board returns to portrait 240×320.
> Re-apply it (and re-calibrate touch) after every flash → `flash-firmware.md`.
> Symptom of forgetting: landscape GUIs render with their content **clipped on
> the right** (`verify-gui.md`).

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

## 9. Touch & pointer input

The panel is a **4-wire resistive** digitizer driven by an **NS2009** on I2C2
(`0x48`); the kernel exposes it as `/dev/input/eventN` with **raw 12-bit ADC
counts**:

```
ABS_X 0..4095   ABS_Y 0..4095   BTN_TOUCH 0/1
```

**Nothing maps those counts to pixels by default.** The image ships tslib
(`/etc/ts.conf` + `TSLIB_CALIBFILE=/etc/pointercal`) and an X InputClass bound
to the tslib driver, but **no `/etc/pointercal`** and no `TSLIB_*` in X's
environment — so the X-level touch path is unusable until someone calibrates.

Three ways touch reaches Python:

| Path | API | Notes |
|---|---|---|
| **evdev** (works out of the box) | `/dev/input/eventN` → raw counts, map yourself | no X/tslib dependency; do not grab the device, X keeps working too |
| X + tslib | calibrated pointer coords, after `ts_calibrate` | needs `/etc/pointercal`; restart X apps after writing it |
| `unihiker` GUI | `on_mouse_move(fn)`, `add_button(onclick=)`, `draw_*(onclick=)` | no generic canvas press/release → bind `gui.canvas` for tap/drag/release |

**Hardware facts that shape the code:** single touch, no pressure axis
(`BTN_TOUCH` is a contact bit), no hover, driver polls at ~30 ms (~33 samples/s,
so fast strokes quantise), and it wants a firm press (fingernail/stylus).
In landscape, X has already rotated the coordinates — Tk coordinates are panel
coordinates; the framebuffer is still 240×320 (`verify-gui.md`).

**Calibration is an affine fit, not a swap.** Axis order/inversion are panel
wiring properties — do not hardcode them. Fit six coefficients by least squares
from ≥3 (5 is better) raw↔pixel pairs:

```python
# panel_x = a*rx + b*ry + c ;  panel_y = d*rx + e*ry + f

# pointercal is 7 integers: the six coefficients in fixed point (scale 65536),
# then the scale itself — tslib's "linear" module format.
open("/etc/pointercal", "w").write(
    " ".join(str(int(round(v * 65536))) for v in coef) + " 65536\n")
```

Locate the device by capability (`ABS_X`+`ABS_Y`+`BTN_TOUCH`, or name
`ns2009_ts`), never by hardcoded event number. A fabricated full-range
guess-calibration is usually wrong in offset and sometimes in axis order — fine
as a fallback, not as the answer.

**Gestures are yours to derive** on release, from duration + travel +
displacement: tap (`<0.35 s`, `<14 px`), long press (`≥0.6 s`, small travel),
drag, swipe (≥24 px travel, dominant axis). Use the **release** position, not
the press position, or every swipe measures 0 px.

Worked implementation (evdev reader thread, in-process calibration, 5-point
tslib-compatible `--calibrate`, hand-rolled canvas buttons, gesture recogniser):
`examples/05_touch_playground.py` in the `g-buddy` repo (notes in its
`examples/README.md`). The `unihiker` widgets cover taps only —
`add_button(onclick=)` and `draw_*(onclick=)` are `<Button-1>` bindings on one
item, and `on_mouse_move` gives you motion without contact state.

## 10. Expansion ports, camera and comms

Pin names follow the micro:bit-compatible edge connector (`P0`…`P28` style).
**Logic is 3.3 V only.** A 5 V sensor output on a GPIO pin can damage the
pin or the coprocessor — use a level shifter for 5 V parts.

```python
d  = Pin(Pin.P20, Pin.IN);   d.value()          # digital in
led = Pin(Pin.P25, Pin.OUT); led.write_digital(1)
pwm = Pin(Pin.P21, Pin.PWM); pwm.write_analog(200)   # 0..255
adc = Pin(Pin.P12, Pin.ADC); adc.value()
s  = Servo(Pin(Pin.P21));   s.angle(90)             # 0..180
```

Servo-capable pins: `P0 P2 P3 P8 P9 P10 P16 P21 P22 P23`. `pinpong.libs.*`
supplies the modules the wiki uses: `RGB_LEDStrip`, `DHT11`, `Ultrasonic`,
`OLED2864`, `ColorRecognition`, `Uart`, `I2c`, `Spi`.

**Camera** — the M10 has no on-board camera; a USB camera works and feeds the
GUI directly (note the rotation: the panel is portrait, the camera is not):

```python
import cv2
from PIL import Image

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 240); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 320)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
bg = gui.draw_image(image="", x=0, y=0)          # create the item once
while True:
    ok, frame = cap.read()
    if ok:
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        bg.config(image=Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
```

**Bluetooth** — the on-board RTL8723DS does Classic RFCOMM (`bluetooth`
module, enable with `hciconfig hci0 piscan`, server `BluetoothSocket(RFCOMM)`
on port 1, client `connect(("MAC", 1))`). **BLE is not the same thing** and the
stock API set does not cover it properly; the wiki's BLE examples use the
DFRobot BLELink accessory. Linux BlueZ (`bleak`, `bluepy`) is the honest path.

**UART / I²C / SPI** — plain Debian devices plus `pinpong.libs.{Uart,I2c,Spi}`;
overlays are already in `/boot/uEnv.txt` (`uart0`, `i2c1`, `i2c2`, `uart3`,
`spi-spidev`). `i2c2` is shared with the touch controller and `amic`. Bus tools
worth installing once Wi-Fi is up: `i2c-tools` (`i2cdetect -y 2`), `spi-tools`,
`minicom`. Use the 3.3 V rail from the board's own header, not a 5 V supply.

## 11. Gotcha summary

1. `Board().begin()` first, always.
2. End with `while True: time.sleep(...)`; SIGINT is a clean exit.
3. `fill_rect` has no radius → use `fill_round_rect` (or `fill_circle`, whose
   x,y is the centre).
4. `on_key_click(event, onclick)` — two positional args, and it's a USB keyboard.
5. `buzzer.pitch` beat is an int count and blocks.
6. No onboard speaker; there *is* an onboard mic.
7. Skip `Loopback` capture devices.
8. PIL can't decode RGB565 here.
9. `config()` to update, not recreate (flicker); `remove()` is final.
10. Image files live next to the running script.
11. `apt` is broken on this image (Debian 10 EOL) until you repoint it to
    `archive.debian.org` → `system.md`.
12. Cloud speech needs Wi-Fi; on-device models are deployed by SFTP → `speech.md`.
13. Raw touch is uncalibrated 12-bit ADC — fit the affine yourself → §9.
14. The rest of the GUI API, and the source-verified corrections to the wiki,
    are in `gui-drawing.md`.

## Sources

- Wiki home: <https://www.unihiker.com/wiki/>
- `unihiker` library: <https://www.unihiker.com/wiki/LanguageReference/UNIHIKER_Library/>
- `pinpong` library: <https://www.unihiker.com/wiki/LanguageReference/PinPong_Library/>
- Screen coordinates/origins: <https://www.unihiker.com/wiki/LanguageReference/UNIHIKER_Library/GeneralKnowledgeAndFeatures/>
- Hardware reference: <https://www.unihiker.com/wiki/HardwareReference/hardware_reference_specification/>
- Python examples index: <https://www.unihiker.com/wiki/Examples/PythonCodingExamples/>
- GUI source (authoritative): `github.com/UNIHIKER/unihiker-pypi-lib`,
  `unihiker/src/unihiker/GUI.py`

The wiki's prose is older than the shipped source in several places — where they
disagree, trust `gui-drawing.md`.
