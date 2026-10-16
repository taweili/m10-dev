# 8. Verifying a GUI without looking at it

When you deploy a screen app over SSH, nobody is watching the panel. These are
the techniques for proving it rendered correctly.

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

Match with a tolerance (~12–25 per channel): antialiased edges blend into the
background.

## Technique 1 — colour census

Count pixels per colour over the whole frame. Stable states have very
characteristic counts, so **one number tells you the state**:

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

## Technique 2 — ASCII art (the single most useful trick)

Downsample to ~96 × 48 cells, classify each cell by dominant colour, print
`. G R Y g ?`. The whole layout becomes legible in text — circle state, meter
fill, dividers, even rough text blocks. For small features (glyphs, eyelids)
render a crop at 1 char per 2×2 px and count dark pixels per cell.

## Technique 3 — frame diffing

`ImageChops.difference(before, after)` isolates exactly what changed — e.g. the
transcript appearing, or pupils shifting down. Use it to assert "this state
added text and nothing else".

## Technique 4 — correlate with app logs (for fast states)

A state lasting <1 s is hard to catch by polling, and snapshot timing is fuzzy
because the decode is slow. Instrument a **throwaway copy** (never the repo
file) to print transitions with `time.time()` to stderr, then align snapshot
mtimes with the log:

```python
# on the board, in /tmp/dbg.py only
import sys as _s
print("[%.2f] MODE -> %s" % (time.time(), new_state), file=_s.stderr, flush=True)
```

Board and PC clocks were within ~0.7 s, which is close enough. Also note that
**state-driven snapshots beat fixed sleeps**: poll the rendered state, and
capture when it changes (`examples.md` shows the state-machine shape).

## Landscape mapping (GUI ↔ framebuffer)

Under `Rotate="CW"`, a **GUI-horizontal** line (constant GUI `y`) becomes a
**vertical** line in the framebuffer, and the two eyes (same GUI `y`, different
GUI `x`) end up at the **same `fb_x`**, stacked vertically. Approximate
(±10 px — Tk window offset makes it inexact):

```
fb_x ≈ gui_y + 54
fb_y ≈ 308 - gui_x        # note the inverted axis
```

**Don't trust the formula blindly.** Calibrate with one known marker, or better,
use **feature detection** (count the colour you care about) instead of absolute
coordinates. For a centred text widget at GUI `(160, y)`, glyphs land around
`fb_x ≈ 234 - y`, `fb_y ≈ 308 - x` (text runs vertically — rotate the crop 90°
to read it).

## Gotchas that cost time

1. **Tearing.** Reading `/dev/fb0` is not synchronised with Tk redraws; an
   animating frame can be caught half-drawn → arbitrary colour counts. Prefer
   stable states; take several snapshots and trust the repeated value; treat
   isolated odd values as tears.
2. **`pkill -f` self-match** — use the bracket trick (`[0]5_app.py`).
3. **Launch via a subshell with `DISPLAY=:0`**, or `exec_command` may hang.
4. **Check for duplicate instances** before trusting any screenshot.
5. **stdout is block-buffered** when redirected; `execv` drops `-u`, so use
   `PYTHONUNBUFFERED=1`.
6. **`Loopback` is not a mic** — see `m10-api.md` §5.
7. **Vosk needs the libstdc++ preload** — see `speech.md`.
