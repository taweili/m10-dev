# Starter kit: the official Python Starter Kit for UNIHIKER M10

What the **DFRobot KIT0194** expansion kit is, what's in the box, and how to
use its modules — especially the **USB speaker**. Everything here is
board-generic (any M10); the kit is **not** bundled with the board and does not
affect flashing or services.

## What the kit is

*Python Starter Kit for UNIHIKER M10 (Learn AI & IoT with 15 Lessons, Board Not
Included)* — DFRobot **KIT0194**, ~$79.90. An expansion ecosystem that turns the
M10 into an AIoT dev station; the **board is not included** (separate purchase,
DFRobot product-2691). Modules use the **Gravity PH2.0 3-pin / 4-pin**
connectors — no breadboard or soldering. Works with **Mind+** (block) and
**standard Python**.

## What's in the box

12 electronic modules on Gravity PH2.0 connectors, plus cabling and power.

**Sensors (6)**

| Module | Interface | Notes |
|---|---|---|
| TCS34725 Color Sensor | I2C | RGB color recognition (lesson 06) |
| URM09 Ultrasonic Sensor | Analog | distance 2–500 cm (lesson 05) |
| DHT11 Temp & Humidity | Digital | classic DHT11 |
| Soil Moisture Sensor | Analog | capacitive (lesson 09) |
| PIR Motion Sensor | Digital | human presence (lesson 02) |
| Digital Push Button w/ blue LED | Digital | input |

**Actuators (5)**

| Module | Interface | Notes |
|---|---|---|
| WS2812 RGB LED Ring (12 LEDs) | Digital | mood light (lesson 03) |
| Metal 9g Servo | PH2.0 | 3-pin |
| Simple Relay Module | Digital | |
| DC Water Pump (DC2.1 plug + pipe) | DC | irrigation (lesson 09) |
| Speaker Module (USB interface) | USB | voice out (lesson 07/13) |

**Vision (1):** USB Camera — AI lessons 11/12/15 (traffic e-eye, access control).

**Power / cabling:** 4×AA battery holder (DC2.1 plug + switch), 2× Type-C/micro
USB cables, 4× PH2.0-3P + 2× PH2.0-4P silicone cables (20 cm), plastic box.

The "16 components" marketing count = 12 modules + battery holder + cables/box.

## The 15-lesson curriculum (Hardware → IoT → AI)

Full lesson list and the tutorial index live at https://learn.dfrobot.com/course-703.html
(localized per-lesson posts on the DFRobot wiki / Maker Community; see Sources).

| # | Lesson | # | Lesson |
|---|---|---|---|
| 01 | Light Up the UNIHIKER M10 | 09 | IoT Plant Irrigation System |
| 02 | Human-Sensing Billboard | 10 | IoT Campus Network Big Screen System |
| 03 | Mood Ambience Light | 11 | AI Pedestrian Traffic E-Eye |
| 04 | Food Recommendation Robot | 12 | AI Access Control Security Monitor |
| 05 | Lake Water-Level Monitor | 13 | AI Multi-function Voice Switch |
| 06 | Color-Picking Game | 14 | AIoT Plant Growth Journal |
| 07 | Mini Karaoke | 15 | AIoT Community Parking-Sharing System |
| 08 | IoT Indoor Environment Monitor | | |

Lessons 01–06 hardware control, 07–10 IoT, 11–15 AI/AIoT.

## Using the kit's USB speaker

**Hardware** — the M10 has **no onboard speaker**; the kit's speaker is a **USB
speaker** that plugs into the board's **USB-A port** with a USB cable. The kit
ships the **USB speaker expansion 2-in-1 module** (new version, lesson 07+),
which adds a **headphone jack** and a **USB output port** for daisy-chaining
(e.g. the USB camera). The older **USB plug-and-play 3W speaker** is
**software-identical** — drop-in replacement, no code changes.

**Software — the `unihiker.Audio` class** (full API in `m10-api.md` §5):

```python
from unihiker import Audio

audio = Audio()
audio.play('track.wav')          # blocking; WAV / MP3; file in cwd
audio.start_play('track.mp3')    # non-blocking (background)
audio.pause_play(); audio.resume_play(); audio.stop_play()
audio.play_time_remain()         # seconds remaining
```

**How playback actually routes** (from `unihiker/src/unihiker/Audio.py`):

* `play()`/`start_play()` use **`pygame.mixer`** (SDL_mixer), initialised in
  `Audio.__init__()` via `pygame.mixer.init()` → the **default audio device**.
* Recording (mic) is separate — **pyaudio**, 16 kHz mono 16-bit.
* So `Audio().play()`, `paplay file.wav` (via Pulse) and `aplay file.wav`
  (direct ALSA) all reach the speaker — but **only one at a time**: if Pulse
  owns the device, `aplay -D hw:2,0` fails *Device or resource busy* (expected;
  use `paplay`).

**Gotchas (verified on the board):**

* The USB speaker enumerates as **`card 2: Device [USB Sound Device]`**
  (C-Media CM103+, `0d8c:0104`) and Pulse creates sink
  `alsa_output.usb-C-Media_INC._USB_Sound_Device-00.analog-stereo`.
* It is **not automatically the default sink** if another sink (e.g. a Bluetooth
  A2DP unit) is present — switch it with `pactl set-sink-volume 1 70%`-style
  commands. Note this board's **`pactl` 12.2 has no `get-default-sink` /
  `get-sink-volume`** subcommands ("No valid command specified" is harmless;
  use the sink **index** not the name for `set-sink-volume`).
* **Volume defaults low** (~24% / −37 dB). Raise it:
  `pactl set-sink-volume 1 70%` (index) or `amixer -c 2 sset PCM 70%`.
* Sanity check a tone without a file: generate a WAV on the board with the
  `wave` module and `paplay` it; confirm routing mid-play with
  `pactl list sink-inputs short` (should show a `protocol-native.c` row).

## Using the kit's USB camera

The kit's camera is a **driverless USB camera** (old: plug-and-play USB; new:
**TypeC-USB**, supports daisy-chaining with the speaker). New vs old are
**software-identical**. It appears as a V4L2 device; use OpenCV / `cv2.VideoCapture(0)`
or the wiki USB-camera reference. DFRobot's update note: new camera + speaker
2-in-1 module replaced the old ones without code changes.

## Getting started toolchains

All of these drive the M10 with Python (from https://www.unihiker.com/wiki/get-started/):

* **Jupyter Notebook** (built-in) — no install; best for beginners.
* **Mind+** — graphical/block coding + Python.
* **VS Code** — remote/Python development.
* **Thonny** — beginner Python IDE.
* **Python IDLE** — built into the board.
* **SSH tools** — terminal over the network link (this bench's path; see `paramiko.md`).

FAQ: WiFi setup → `Troubleshooting/How_to_connect_wifi/`; run programs without a
computer → `SystemAndConfiguration/system_and_configuration_home_menu/`.

## Official Python example catalog

From https://www.unihiker.com/wiki/Examples/PythonCodingExamples/ (the bench's own
worked examples are in `examples.md`).

* **Basic (20):** Hello Unihiker, System Time, Starry Sky, Emoticon Master,
  Interactive Button Screen, Draw a Clock, QR Code Display, Draw a Hexagon,
  Color Picker, Olympic Rings, Where is the Mouse, Switch Albums with Keyboard,
  Recorder, Music Player, LED Flashing, Button Light, Luminosity Detector,
  Digital Piano, Noise Monitor, Pedometer.
* **Intermediate (10):** Blinking LED, Colourful Light Strip, Smart Home
  Temp/Humidity Monitor, RGB LED Color Palette, Plant Moisture Monitoring,
  Ultrasonic Distance Meter, Servo Motor Control, Bluetooth (UNIHIKER↔UNIHIKER /
  BLELink / APP).
* **Advance (6):** AI Voice Light, Speech Synthesis Assistant, DIY Camera,
  Smart Home Monitoring, Color-Following Car, IoT Smart Home.

## Sources

* Kit product: https://www.dfrobot.com/product-3067.html (CN mirror
  https://www.dfrobot.com.cn/goods-3663.html); parts list / package includes:
  https://www.fabtolab.com/dfrobot-python-starter-kit-unihiker-m10-learn-ai-iot-15-lessons-board-not-included
* Curriculum index: https://learn.dfrobot.com/course-703.html ; lesson table
  https://www.decatron.hk/unihiker-m10-python-learning-kits
* M10 docs: https://www.unihiker.com/wiki/ ; getting started
  https://www.unihiker.com/wiki/get-started/ ; examples
  https://www.unihiker.com/wiki/Examples/PythonCodingExamples/
* UNIHIKER lib: https://www.unihiker.com/wiki/LanguageReference/UNIHIKER_Library/
  (Audio.play reference:
  .../AudioClass/reference_unihiker_audio_playback_play/)
* PinPong lib: https://www.unihiker.com/wiki/LanguageReference/PinPong_Library/
* `unihiker` PyPI: https://pypi.org/project/unihiker/ ; source
  https://github.com/UNIHIKER/unihiker-pypi-lib
* USB camera + speaker update note: https://mc.dfrobot.com.cn/thread-399235-1-1.html
