# Glossary

> Reviewed 2026-10-19. Version-agnostic; see `health-check.md` for what is actually on the board.

Terms that appear throughout the references without explanation.

## Hardware

| Term | Meaning |
|---|---|
| **M10 / K10** | DFRobot UNIHIKER board. M10 adds the camera and USB-A; K10 is the cut-down variant. Everything here is M10 unless stated. |
| **RK3308** | Rockchip ARM SoC: 4× Cortex-A35 @1.2 GHz, 512 MB RAM, 16 GB eMMC. Runs Debian 10 on the board. |
| **GD32VF103** | RISC-V coprocessor that actually drives the pins: GPIO, ADC/PWM, buttons, IMU, buzzer. `pinpong` talks to it over Linux devices. |
| **NS2009** | Resistive-touch ADC on I2C2 (`0x48`). Exposes raw 12-bit X/Y counts, not pixels. |
| **P25** | Pin name for the on-board blue LED. All pin names follow the micro:bit-style edge connector (`P0`…`P28`). |
| **IMU** | 6-axis accelerometer/gyroscope on the board (`accelerometer`, `gyroscope`). |
| **eMMC** | The 16 GB soldered flash. `/root` and installed packages live here; a reflash rewrites it. |
| **maskrom** | Rockchip boot-ROM mode used for flashing. A board in maskrom is always recoverable. |

## Linux / network

| Term | Meaning |
|---|---|
| **RNDIS** | USB protocol that makes the board appear as an ethernet NIC on the PC (`rndis_host` driver). |
| **br0** | The board's bridge interface that carries `10.1.2.3/24` over USB. |
| **NetworkManager profile** | Stored connection config in `/etc/NetworkManager/system-connections/`; this is what survives re-enumeration (not `ip addr add`). |
| **udev / sysfs** | Kernel device view under `/sys/class/net/…`; used to identify the gadget NIC by product id/MAC. |
| **TUN** | Userspace VPN interface. A TUN-mode proxy can capture `10.0.0.0/24` and hide the board — exclude `10.1.2.0/24`. |
| **tmpfs** | RAM-backed filesystem. `/tmp` and `/run` live in RAM, so large models/clips there consume the 512 MB budget. |
| **pkexec** | PolicyKit privilege escalation. Works without a TTY password prompt where a polkit rule exists. |
| **ABI / preload** | Binary interface. Vosk's `libvosk.so` wants a newer `libstdc++` than Debian 10 ships; `LD_PRELOAD` injects one extracted from Debian 11. |

## Display

| Term | Meaning |
|---|---|
| **framebuffer (`/dev/fb0`)** | Raw pixels of the panel: 240×320, RGB565, 16 bpp, 480-byte stride. |
| **RGB565** | 5 bits red, 6 green, 5 blue per pixel. Colours quantise; dark glows can round down to the background. |
| **fbdev** | Xorg driver writing to the framebuffer. The board's X config uses it with a `Rotate` option. |
| **Xorg `Rotate`** | Userspace rotation (`CW`/`CCW`) that makes a 240×320 panel present as 320×240. The framebuffer stays portrait. |
| **lightdm** | The display manager that starts X. Restarting it resets the GUI session. |
| **origin/anchor** | Where a widget's `(x, y)` sits inside it (`nw`, `center`, …). Circles use the centre; rects use the top-left. |
| **`.config()`** | Mutate an existing widget. Recreating widgets each frame is what causes flicker. |

## Audio / speech

| Term | Meaning |
|---|---|
| **dBFS** | Decibels relative to full scale; 0 is clipping, ≈ −51 is this board's mic noise floor. |
| **Loopback** | ALSA card whose playback does **not** reach its capture side. Never use it as a mic or to inject test audio. |
| **hw:1,0** | The on-board RK3308 codec: card 1, device 0. The mic is ADC group 0 (`Work`). |
| **STT / TTS** | Speech-to-text / text-to-speech. |
| **Vosk** | Offline STT engine. Small model ≈ 40 MB, ≈ 300 MB resident. |
| **Piper** | Offline neural TTS; use the C++ binary on Python 3.7. |
| **Azure Speech** | Cloud STT + neural TTS; needs Wi-Fi. |

## DFRobot software

| Term | Meaning |
|---|---|
| **`unihiker`** | Python package for the screen and audio (`GUI`, `Audio`, `UNIConfig`). Wraps Tkinter + ttk, not a framebuffer. |
| **`pinpong`** | Python package for hardware: `Board().begin()`, `Pin`, `Servo`, and the `pinpong.extension.unihiker` globals. |
| **`firstRun.sh`** | DFRobot first-boot script that burns the GD32 firmware. If it does not run, every `pinpong` call no-ops. |
| **DFRobot image** | The vendor Debian snapshot; everything outside `/root` and site-packages is replaced by a reflash. |
| **tslib / pointercal** | Touch calibration stack. The image ships tslib but no `/etc/pointercal`, so touch is uncalibrated until fitted. |
| **pyboard / SIoT** | DFRobot's web IDE / IoT daemons. Disabled to free RAM (`system.md`). |
