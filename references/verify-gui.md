# 8. Verifying a GUI from the framebuffer

> Reviewed 2026-10-20. Assumes firmware v0.4.2, `unihiker` 0.0.27+ and `pinpong` 0.6.1; version-specific claims are flagged inline.

When you deploy a screen app over SSH, nobody is watching the panel. The way to
verify it is to **grab the framebuffer as a PNG and look at the image**. One
snapshot shows layout, clipping, colour, alignment and text in a single glance —
no downsampling, no colour-counting, no guessing.

```bash
scripts/m10-snapshot.py --rotate 90                      # -> m10-frame.png
scripts/m10-snapshot.py --rotate 90 --crop 0,0,320,62 --zoom 4   # legible detail
```

That captures `/dev/fb0`, decodes RGB565 **on the board** (the board's PIL
cannot), pulls the PNG to the PC and rotates it to match the panel. Open the
result with the `read` tool (or any image viewer). `--crop`/`--zoom` exist so a
12 px legend row or a single widget can be upscaled and read directly instead of
being approximated in text.

Use the rest of this file for the framebuffer facts (why the decode is not
one line), the RGB565 palette, and the numeric checks worth running *after* you
have looked at the image.

## Framebuffer facts

- `/dev/fb0` (`fb_ili9341`): **240 × 320, RGB565 (16 bpp)**, stride **480 bytes**,
  153 600 bytes total.
- It stays **240 × 320 even when Xorg is rotated** — X rotates in userspace
  (shadow framebuffer). So with `GUI(w=320, h=240)` + `Rotate="CW"`, the
  framebuffer holds the **portrait** image and you must rotate it back.
- `xdpyinfo | grep dimensions` reports `320x240` in landscape — that's the *X*
  screen, **not** the framebuffer.
- `Image.frombuffer(...)` / `frombytes(..., "raw", "RGB565", 0)` **do not work**
  on this board's PIL 9.0.1 (`ValueError: unknown raw mode`); every raw variant
  fails. Decode by hand:

```python
# /tmp/snap.py — run ON the board, writes /tmp/frame.png
import struct
from PIL import Image
W, H, STRIDE = 240, 320, 480
with open("/dev/fb0", "rb") as f:
    data = f.read()
compact = b"".join(data[y*STRIDE : y*STRIDE + W*2] for y in range(H))
px = struct.unpack("<%dH" % (W*H), compact)
buf = bytearray(W*H*3)
for i, p in enumerate(px):
    buf[i*3]   = (p >> 11) << 3            # R (5 bits)
    buf[i*3+1] = ((p >> 5) & 0x3F) << 2    # G (6 bits)
    buf[i*3+2] = (p & 0x1F) << 3           # B (5 bits)
Image.frombytes("RGB", (W, H), bytes(buf)).save("/tmp/frame.png")
```

Grab it and rotate on the PC:

```python
c = client()
c.exec_command("python3 /tmp/snap.py", timeout=30)[1].read()
c.open_sftp().get("/tmp/frame.png", "frame.png")
Image.open("frame.png").rotate(90, expand=True)     # matches Rotate="CW"
```

A snapshot + transfer costs **~2 s**. The raw 153 600-byte read is fast; the
pixel decode is the slow part — if you need timing accuracy, capture the raw
bytes at the moment of interest and decode on the PC.

## Reading the image

Rotate first (portrait framebuffer → landscape panel), then check in this order.
The order matters: each step rules out a whole class of failure before you spend
time on the next.

1. **Is it our app at all?** A stock DFRobot `pyboardgui` screen (blue "Exit"
   button, globe icon) means the app died and the board fell back to its
   launcher — read `/tmp/<app>.err` before anything else. A crashed app is not a
   rendering bug.
2. **Orientation and clipping.** Landscape content in a portrait frame, or
   anything cut off on the right/bottom, means the `Rotate=` config and
   `GUI(w=, h=)` disagree (`m10-api.md` §7).
3. **Layout.** Bars where you expect bars, nothing overlapping, nothing running
   off an edge. Compare against the dimensions you asked for — a legend row that
   computes to 244 px cannot fit a 240 px portrait width.
4. **Colour.** Does each element have the colour you assigned? RGB565 rounds
   every hex value (table below), so a designed colour can look slightly
   different but never *wrong*.
5. **Text.** Legible at arm's length, not clipped, not overlapping. Use
   `--crop/--zoom` on the text region to read it exactly.
6. **State.** The thing you just triggered (button press, mood change, chat
   token) is actually on screen.

A PNG also gives you exact pixel coordinates when you need them: `--crop` around
a guess, `--zoom 4`, and the upscaled image tells you precisely where the widget
edge sits.

## Colour is quantised to RGB565

Hex GUI colours come back rounded to 5/6/5 bits. Reference table:

| GUI hex | Role | Framebuffer RGB |
|---|---|---|
| `#FFF6E9` | background | `(248, 244, 224)` |
| `#FFFFFF` | sclera white | `(248, 252, 248)` |
| `#FFB6C1` | pink iris | `(248, 180, 184)` |
| `#B57AB8` | purple iris | `(176, 120, 176)` |
| `#3B2A2A` | brown pupil/lash/text | `(56, 40, 40)` |
| `#4CAF50` | green | `(72, 172, 80)` |
| `#F44336` | red | `(240, 64, 56)` |
| `#FF9800` | orange | `(248, 148, 0)` |
| `#FFEB3B` | yellow | `(248, 232, 56)` |
| `#101418` | dark background | `(16, 20, 24)` |

This matters most when **two colours must stay distinguishable** — a gesture
legend, a state palette, a glow ring against a dark background. Quantise the
palette on the PC and check pairwise distance in 5/6/5 space *before* deploying,
rather than discovering on the panel that two "different" colours collide:

```python
def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
```

The dimmest ring of a glow must stay brighter than the background, or it rounds
*down* to the background and the glow reads as a dark halo.

## Technique 1 — colour census (numeric, for assertions)

After looking at the image, a census is a cheap *quantitative* check: count
pixels per colour and compare with the expected state. It is how you verify
without a human in the loop — in `--census`, in a test, or when polling for a
state change.

| State (one big circle, r=52, dark bg) | Dominant | Pixels |
|---|---|---|
| idle / result (green circle) | green | ~8 685 |
| recording (yellow circle) | yellow | ~8 347 |
| transcribing (red circle) | red | ~8 616 |
| result + transcript | green | ~8 097 (+ ~90 white glyph px) |

```python
from collections import Counter
Counter(im.getdata()).most_common(4)
```

Stable states have characteristic counts, so one number tells you the state —
useful for **polling** (wait until green appears, then snapshot) and for
catching "the right layout in the wrong colour".

## Technique 2 — frame diffing

`ImageChops.difference(before, after)` isolates exactly what changed — e.g. the
transcript appearing, or pupils shifting down. Use it to assert "this state
added text and nothing else":

```python
from PIL import ImageChops
box = ImageChops.difference(before, after).getbbox()   # None == identical
```

## Technique 3 — correlate with app logs (for fast states)

A state lasting <1 s is hard to catch by polling, and snapshot timing is fuzzy
because the decode is slow. Instrument a **throwaway copy** (never the repo
file) to print transitions with `time.time()` to stderr, then align snapshot
mtimes with the log:

```python
# on the board, in /tmp/dbg.py only
import sys as _s
print("[%.2f] MODE -> %s" % (time.time(), new_state), file=_s.stderr, flush=True)
```

Board and PC clocks were within ~0.7 s, which is close enough. **State-driven
snapshots beat fixed sleeps**: poll the rendered state (census), and capture when
it changes (`gui-drawing.md` §6.7 shows the state-machine shape).

## Landscape mapping (GUI ↔ framebuffer)

You normally do not need this: rotate with `--rotate 90` and the PNG is already
in GUI coordinates, so a pixel you pick in the image is a GUI coordinate. Reach
for the arithmetic only when reading `/dev/fb0` yourself.

Under `Rotate="CW"`, a **GUI-horizontal** line (constant GUI `y`) becomes a
**vertical** line in the framebuffer, and the two eyes (same GUI `y`, different
GUI `x`) end up at the **same `fb_x`**, stacked vertically. Approximate
(±10 px — Tk window offset makes it inexact):

```
fb_x ≈ gui_y + 54
fb_y ≈ 308 - gui_x        # note the inverted axis
```

**Don't trust the formula blindly.** Prefer the rotated PNG, or feature
detection (count the colour you care about) over absolute coordinates.

## Gotchas that cost time

1. **Tearing.** Reading `/dev/fb0` is not synchronised with Tk redraws; an
   animating frame can be caught half-drawn. Snapshot a stable state, or take
   two and ignore an obviously torn one. A half-drawn frame in the image is a
   capture artefact, not a bug in your layout.
2. **A dead app looks like a rendering bug.** The stock launcher screen means the
   process exited — check the log first.
3. **`pkill -f` self-match** — use the bracket trick (`[0]5_app.py`).
4. **Launch via a subshell with `DISPLAY=:0`**, or `exec_command` may hang.
5. **Check for duplicate instances** before trusting any screenshot.
6. **stdout is block-buffered** when redirected; `execv` drops `-u`, so use
   `PYTHONUNBUFFERED=1`.
7. **`Loopback` is not a mic** — see `m10-api.md` §5.
8. **Vosk needs the libstdc++ preload** — see `speech.md`.
