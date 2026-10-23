# Bluetooth (pair an A2DP speaker / Classic RFCOMM)

The on-board radio is an **RTL8723DS** dual-mode chip on UART (`hci0`). On the
M10 image it does both **Classic RFCOMM** (data) and **A2DP** (audio to a
speaker) — the latter is verified on this bench (an "M2" speaker paired,
connected, and played through PulseAudio). **BLE is a separate surface** and the
stock wiki examples need the DFRobot BLELink accessory; for BLE on Linux use
BlueZ via `bleak`/`bluepy`.

> **A2DP audio needs PulseAudio.** The default bench trim (`m10-trim-services.py`)
> disables `bluetooth` *and* masks `pulseaudio`. A `bluetoothctl connect` to a
> speaker fails with `org.bluez.Error.Failed` until PulseAudio is running and
> `module-bluetooth-discover` is loaded — BlueZ has no audio endpoint to attach
> the A2DP stream to otherwise. See §2.

## 0. Bring the adapter up

```bash
ssh root@10.1.2.3                       # password: dfrobot
hciconfig hci0 up
hciconfig hci0 piscan                   # discoverable + connectable
hciconfig hci0                           # must show UP RUNNING PSCAN ISCAN
```

If `hci0` is missing or `rfkill` blocks it: `rfkill unblock bluetooth` and
`systemctl status bluetooth` (it may be disabled by the trim — see §2).

## 1. Scan and pair (classic A2DP speaker)

```bash
bluetoothctl
[bluetooth]# power on
[bluetooth]# agent NoInputNoOutput      # headless-capable agent
[bluetooth]# default-agent
[bluetooth]# scan on                     # leave it ~10s; watch for Name: lines
[bluetooth]# devices                     # list what was seen
[bluetooth]# info <MAC>                  # confirm Icon: audio-card + UUID: Audio Sink
[bluetooth]# pair <MAC>
[bluetooth]# trust <MAC>                 # auto-reconnect
[bluetooth]# connect <MAC>
[bluetooth]# quit
```

**Is it really a speaker?** Trust the Class of Device (CoD) and the BlueZ
`Icon`, not the name. Decode: major service bit `0x200000` = Rendering,
`0x040000` = Audio; major device class `0x04xx` (`0x240400` family) = Audio/Video;
`Icon: audio-card` is BlueZ's verdict. A phone shows `Icon: phone` with
A2DP *source* UUIDs — pair the phone *to the board*, not the other way.
Random-MAC BLE beacons (Apple `0x004c`, `fcf1`, etc.) are not audio devices.

Non-interactive (scripted) pairing — `bluetoothctl` reads commands from stdin,
gaps are `sleep`s so the state machine settles:

```bash
MAC=41:42:28:F1:3A:B3
(echo power on; sleep 1; echo "agent NoInputNoOutput"; sleep .5; \
 echo default-agent; sleep .5; echo "pair $MAC"; sleep 6; \
 echo "trust $MAC"; sleep 1; echo "connect $MAC"; sleep 6; \
 echo "info $MAC"; sleep 1; echo quit) | bluetoothctl
```

## 2. The PulseAudio un-mask (required for A2DP audio)

The `pulseaudio-module-bluetooth` package is **already installed** on the image
(`/usr/lib/pulse-12.2/modules/module-bluetooth-discover.so`,
`-policy.so`), and `/etc/pulse/default.pa` loads both modules when PulseAudio
starts. The only blocker is that the bench masks PulseAudio. The X/lightdm
session runs as **root**, so PulseAudio belongs to **root's user session**
(`XDG_RUNTIME_DIR=/run/user/0`).

```bash
systemctl --user unmask pulseaudio
systemctl --user daemon-reload
systemctl --user enable --now pulseaudio      # enables across reboot
# confirm it's up and owns the A2DP endpoint:
pactl list short sinks                        # see alsa + (later) bluez sinks
pgrep -af pulseaudio
```

Now (re-)connect the speaker; PulseAuto creates the sink on connect:

```bash
bluetoothctl -- connect <MAC>
pactl list short sinks                        # a bluez_sink.<MAC>.a2dp_sink appears
```

Pin the A2DP profile and make it the default output:

```bash
CARD=bluez_card.$(echo $MAC | tr ':' '_')           # e.g. bluez_card.41_42_28_F1_3A_B3
SINK=bluez_sink.$(echo $MAC | tr ':' '_').a2dp_sink
pactl set-card-profile "$CARD" a2dp_sink            # force A2DP, not HSP/HFP
pactl set-default-sink "$SINK"                      # route everything to the speaker
pactl info | grep 'Default Sink'                    # confirm
```

Test: `speaker-test -c2 -t sine -f 440 -l 1` → a 440 Hz blip through the
speaker. `paplay file.wav` and PulseAudio-routed `pyaudio` go to M2 too.

**Connected but no sink** (the usual "it worked, then went silent"):
`bluetoothctl info <MAC>` says `Connected: yes`, but
`pactl list short sinks` has **no** `bluez_sink.*` and Pulse has quietly
fallen back to `alsa_output.platform-acodec-sound` — which has no transducer,
so playback returns 0 and nothing is heard. `module-bluez5-device` only
creates the card when it sees the transport appear, so a reconnect while the
ACL link is already up is a no-op. Cycle the link **with Pulse running**:

```bash
bluetoothctl -- disconnect <MAC>; sleep 3
bluetoothctl -- connect <MAC>;    sleep 4
pactl list short cards | grep bluez        # card index CHANGES — that's the proof
pactl list short sinks | grep bluez        # bluez_sink.<MAC>.a2dp_sink back
```

A speaker that idle-disconnects will do this after a period of silence; check
the sink, not just `Connected:`, before blaming the player. Log the sink name
from your app (`pactl info | grep 'Default Sink'`) so a silent run is
diagnosable after the fact — `examples/08_hello_world_tts.py` prints
`play paplay -> bluez_sink.…a2dp_sink` for exactly this reason.

## 3. Auto-reconnect after reboot

Trusted A2DP devices reconnect automatically **only if PulseAudio is running**
at boot. With `--enable` set in §2 that holds. To force a reconnect when the
speaker was off at boot:

```bash
bluetoothctl -- connect <MAC>          # or: pactl set-default-sink after connect
```

## 4. Classic RFCOMM (data, not audio)

For serial-over-BT to a phone/PC, the board is the server:

```python
import bluetooth, time
# hciconfig hci0 piscan on the shell first
s = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
s.bind(("", 1))                         # port 1
s.listen(1)
conn, addr = s.accept()                 # peer dials connect(("board_mac", 1))
while True:
    data = conn.recv(1024)
    conn.send(b"ack\n")
    time.sleep(0.1)
```

Client side (board dials out): `s.connect(("PEER_MAC", 1))`.

## Red lines / gotchas

1. **`connect` failing with `org.bluez.Error.Failed` = PulseAudio not running.**
   Pairing succeeds without it; the A2DP profile does not. Un-mask per §2.
2. **Un-masking PulseAudio reverses a deliberate trim.** It costs the ~? MB and
   the reason the trim disabled it — no `g-buddy` demo uses the `unihiker`
   Audio API. Revert with `m10-trim-services.py` (or `systemctl --user
   disable --now pulseaudio` + `systemctl disable --now bluetooth`) when the
   bench no longer needs BT audio.
3. **Trust `Icon`/CoD over the device name** to tell a speaker from a phone or
   a BLE beacon. Phones expose A2DP *source*; beacons have no audio UUIDs at all.
4. **HSP/HFP needs a mic endpoint** — the board's mic is `hw:1,0` ALSA, not
   wired into the BT HFP gateway by default. Prefer the `a2dp_sink` profile;
   forcing `headset_head_unit` usually fails to produce audio here.
5. **No onboard speaker.** The ALSA `acodec` card (`alsa_output.platform-
   acodec-sound`) has no transducer — only a BT (or USB) sink makes sound.
6. **`pactl get-default-sink` is unsupported** on PulseAudio 12.2 (it returns
   "No valid command specified"). Confirm the default with `pactl info |
   grep 'Default Sink'` instead.
7. **"Connected: yes" does not mean "audible".** The sink can be missing while
   the ACL link is up, and Pulse falls back to the silent on-board card (§2).
