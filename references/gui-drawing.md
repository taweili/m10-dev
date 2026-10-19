# 4c. Drawing and animation (the whole `unihiker` GUI)

> Reviewed 2026-10-19. Assumes firmware v0.4.2, `unihiker` 0.0.27+ and `pinpong` 0.6.1; version-specific claims are flagged inline.

Ground truth for the on-screen API, read off the shipped source rather than the
DFRobot wiki. Where this file and `m10-api.md` §1 disagree, **this file wins**.

Source read: `unihiker` **v0.0.29.0**
(`github.com/UNIHIKER/unihiker-pypi-lib`, `unihiker/src/unihiker/GUI.py`, 1185
lines). The stock v0.4.0 firmware ships an older wheel (0.0.27), so check
`pip3 show unihiker` before relying on a specific extra.

## 0. TL;DR

```python
from unihiker import GUI
import math, time

gui = GUI()                               # 240x320 portrait; GUI(w=320, h=240) landscape

bg   = gui.fill_rect(x=0, y=0, w=240, h=320, color="#000")
ball = gui.fill_circle(x=120, y=160, r=20, color="#0f0")    # x,y = CENTRE
lbl  = gui.draw_text(text="0", x=120, y=20, font_size=14,
                     color="white", origin="center")

frame = 0
while True:
    frame += 1
    ball.config(y=160 + 80 * math.sin(frame / 15))   # mutate, don't recreate
    lbl.config(text=str(frame))
    time.sleep(1 / 30)                               # Tk loop runs on its own thread
```

The three rules everything else follows:

1. **Create widgets once, update with `.config()`** — recreating in a loop
   flickers and tanks the frame rate.
2. **Keep the process alive** with `while True: time.sleep(...)`. The Tk event
   loop is a daemon thread the library started for you.
3. **`.remove()` / `gui.remove(w)` destroys a widget** — you cannot `config()`
   it afterwards. To hide, move it off-screen: `w.config(x=-9999, y=-9999)`.

## 1. What is actually installed

`unihiker` wraps **Tkinter + ttk** (not a framebuffer, not SDL). The wheel pulls
in `fontTools, pillow, numpy, qrcode, pydub, pygame, pyaudio`.

**`pygame` is a hard dependency and is installed.** If Tk's canvas cannot hit the
frame rate you need (full-screen particle fx, game loop), a pygame
`display.set_mode((240,320), display=...)` surface is a legitimate fallback —
nothing in `unihiker` blocks it. `pydub` (audio editing) and `numpy` (image
pipeline) are there too.

Two fonts ship inside the wheel:

| File | Use |
|---|---|
| `HYQiHei_50S.ttf` | default UI font, family `HYQiHei` / `汉仪旗黑 50S` |
| `Segment7-4Gml.otf` | 7-segment "digital" font, used by `draw_digit()` |

They are installed on first `GUI()` — the library copies them into `~/.fonts`
and **`os.execl()` re-execs the whole Python process** so Tk picks them up (see
§5 for the guard).

## 2. The drawing API (exhaustive)

Every call returns a widget object you keep and later mutate with `.config()`.

`origin=` accepts `center`, `top|bottom|left|right`, `nw|ne|sw|se`, `n|s|w|e`,
or the long forms `top_left`, `top_right`, `bottom_left`, `bottom_right`.
Unrecognised anchors print a warning and fall back to `nw`.

**`origin=` only exists on Text, Image, Emoji, QRCode, Button, TextBox and
ListBox** — the shape primitives (line, rect, circle, round_rect, clock,
point) ignore it.

### 2.1 Canvas primitives

| Call | Purpose | Notes |
|---|---|---|
| `draw_text(x, y, text, color, origin, font_size, font_family, onclick)` | text | default font_size=14, color black, origin nw |
| `draw_digit(x, y, text, color, origin, font_size)` | 7-seg digits | forces `font_family='Segment7'` |
| `draw_image(x, y, w, h, image, origin, onclick)` | image | `image` = path, PIL `Image`, or `np.ndarray` (BGR→RGB automatic) |
| `draw_emoji(x, y, w, h, emoji, duration, onclick, origin)` | animated sprite | see §4 |
| `draw_clock(x, y, r, h, m, s, color, style, onclick)` | analog clock | `style='light'/'dark'/'customize'` |
| `fill_clock(...)` | filled clock | fill defaults to white |
| `draw_qr_code(x, y, w, h, text, onclick, origin)` | QR code | `text` is the payload |
| `add_button(x, y, w, h, origin, onclick, text)` | ttk button | any ttk.Button kw works (`text`, `style`, `foreground`, …) |
| `add_text_box(x, y, w, h, text, origin)` | scrollable text entry | undocumented in the wiki |
| `add_list_box(x, y, w, h, list, onclick, origin)` | scrollable list | undocumented in the wiki |

### 2.2 Shapes

| Call | Purpose | Notes |
|---|---|---|
| `draw_line(x0, y0, x1, y1, color, width, onclick)` | line | default `width=1`, fill black |
| `draw_rect(x, y, w, h, color, width, onclick)` | outline rect | no radius |
| `fill_rect(x, y, w, h, color, fill, width, onclick)` | filled rect | **no `r=` — silently ignored** |
| `draw_round_rect(x, y, w, h, r, color, width, onclick, state)` | outline rounded rect | **`r=` works**; clamped to `min(w/2, h/2)` |
| `fill_round_rect(x, y, w, h, r, color, fill, width, onclick, state)` | filled rounded rect | use this for buttons/badges |
| `draw_circle(x, y, r, color, width, onclick)` | outline circle | `x, y` = **centre** |
| `fill_circle(x, y, r, color, fill, width, onclick)` | filled circle | `x, y` = **centre** |
| `draw_point(x, y, color, onclick)` | dot | `fill_circle` with `r=0` |

There is **no `arc()` primitive**. `fill_round_rect` uses Tk's
`canvas.create_arc` internally for its corners, and `gui.canvas` is a live Tk
`Canvas`, so reach in directly for arcs, polygons, bitmaps, windows,
`postscript`, etc.:

```python
gui.canvas.create_arc(x0, y0, x1, y1, start=0, extent=180, style="arc",
                      outline="#3AF", width=2)
```

That is how the repo's cartoon mouths/eyebrows are drawn without a chain of
circles — cheaper and smoother than a parabola of `fill_circle`s.

### 2.3 Events

| Call | Purpose |
|---|---|
| `gui.on_mouse_move(fn)` | `fn(x, y)` on `<Motion>`; Tk screen coords = panel coords |
| `gui.on_key_click(event, onclick)` | raw Tk binding, e.g. `gui.on_key_click('<KeyPress-a>', cb)` |
| `gui.on_a_click(cb)` / `gui.on_b_click(cb)` | bind Tk key events `'a'` / `'b'` |
| `gui.wait_a_click()` / `gui.wait_b_click()` | blocking wait on the same |
| `widget.onclick=cb` (any drawing call) | `cb()` on `<Button-1>` on that item |

**`on_key_click` takes two positional args** — `on_key_click(event, onclick)` —
not `on_key_click(onclick=fn)` as the wiki suggests. It is for a **USB
keyboard**, not the on-board A/B buttons: the Tk `'a'`/`'b'` events only fire if
the firmware maps the buttons as HID keystrokes, which it generally does not.
Use `pinpong`'s `button_a` / `button_b` (`m10-api.md` §2) or raw evdev
(`m10-api.md` §9) for the physical buttons and the touch panel.

### 2.4 Threading helpers

```python
t = gui.start_thread(lambda: heavy_work(arg1, arg2))   # ONE zero-arg callable
gui.stop_thread(t)                                     # needs that Thread back
```

`start_thread` takes a single callable — pass a closure or lambda, not
`(fn, args)`. `stop_thread` raises `SystemExit` in the target via
`ctypes.pythonapi`; it is a hard kill, so never call it on a thread holding a Tk
lock.

## 3. `.config()` options per widget

`.config()` is keyword-only. Unlisted kwargs are forwarded to
`canvas.itemconfigure()`, so Tk-native options (`width`, `stipple`, `dash`,
`smooth`, `tags`) leak through when Tk accepts them for that item type.

| Widget | Config-able beyond the obvious |
|---|---|
| CanvasText | `x, y, text, color, onclick, origin, font_size, font_family` |
| CanvasImage | `x, y, w, h, image, onclick, origin` |
| CanvasEmoji | `x, y, w, h, emoji, duration, onclick, origin` |
| CanvasLine | `x0, y0, x1, y1, color, width, onclick` |
| CanvasCircle | `x, y, r, color, fill, width, onclick` |
| CanvasRect | `x, y, w, h, color, fill, width, onclick` |
| CanvasRoundRect | `x, y, w, h, r, color, fill, width, onclick, state` |
| CanvasClock | `x, y, r, h, m, s, color, fill, style, onclick, state` |
| CanvasQRCode | `x, y, w, h, text, onclick, origin` |
| WidgetButton | `x, y, w, h, origin, onclick, state`, plus all of ttk.Button |
| WidgetTextBox | `x, y, w, h, text, origin`, plus ttk.Frame options |
| WidgetListBox | `x, y, w, h, list, origin, callback`, plus ttk.Frame options |

**Colours** — all accepted everywhere: `"#RRGGBB"`, `(r, g, b)`, Tk names. Tuples
are converted by `rgb2hex()` before hitting Tk.

**`state`** on button / clock / round_rect: `"normal"`, `"disabled"`,
`"hidden"`. `hidden` calls `place_forget` on the ttk widget — use it to hide
buttons; `remove()` is not reversible.

### The two shape quirks that bite

1. **`fill_rect` / `draw_rect` have no `r=`.** Passing `r=8` is silently ignored
   at creation and raises `_tkinter.TclError: unknown option "-r"` on
   `.config()`. For rounded corners use `fill_round_rect` / `draw_round_rect`,
   which do take `r=` (clamped to half the smaller side).
2. **`fill_circle` / `draw_circle` take `x, y` as the centre**, while
   `draw_rect` / `fill_rect` take it as the top-left. Mixing these up is the
   most common off-by-a-radius bug.

## 4. `draw_emoji` — the hidden sprite animator

`draw_emoji()` is a real multi-frame animator, not a sticker:

```python
class CanvasEmoji(CanvasImage):
    def __init__(self, parent, **kw):
        self.emoji    = kw.pop('emoji', 'Smile')
        self.duration = kw.pop('duration', 0.5)   # seconds per frame
        self.images   = parent.emoji(self.emoji)  # list of PIL Images
        ...
        def emoji_update():
            self.index = (self.index + 1) % len(self.images)
            self.config(image=self.images[self.index])
            self.emoji_thread = self.parent.master.after(int(self.duration*1000), emoji_update)
        self.emoji_thread = self.parent.master.after(int(self.duration*1000), emoji_update)
```

It is a self-driving loop on `tkinter.after()` — no `time.sleep` in your main
loop, no frame counter, no flicker. The nine built-in emojis ship **5 frames
each** (45 pre-rendered sprites):

```
Angry   Nerve   Peace   Shock   Sleep
Smile   Sweat   Think   Wink
```

**You can bring your own sprites.** The loader looks for PNGs matching
`<name>-*.png` case-insensitively, first in `unihiker/emojis/`, then in the
current working directory:

```python
# drop Walk-1.png … Walk-6.png next to the script
sprite = gui.draw_emoji(x=120, y=200, w=40, h=40, emoji='Walk', duration=0.12)

sprite.config(emoji='Jump', duration=0.15)   # swap the whole animation
sprite.config(image=my_pil_frame)            # or just the current frame
```

`duration` is per-frame seconds: 0.10–0.15 reads snappy cartoon, 0.25–0.5 reads
idle breathing. This is the best primitive for character animation on the board
and the least used — a `Walk-N.png` set plus button-triggered state changes gets
you a lot of character for very little code.

## 5. Fonts, brightness, misc

```python
gui = GUI()

gui.show_fonts()                                       # every family Tk knows
gui.draw_text(text="Hi", x=10, y=10, font_family='HYQiHei', font_size=20)
gui.draw_text(text="88", x=120, y=200, origin="center",
              font_family='Segment7', font_size=48)    # 7-seg without draw_digit

from unihiker import UNIConfig
UNIConfig().set_brightness(60)                         # LCD backlight 0..100
```

`load_font(path)` copies the file into `~/.fonts` and then **`os.execl()`
restarts the Python process**. Put it at the very top and guard the restart:

```python
import os
if not os.environ.get('_FONT_LOADED'):
    os.environ['_FONT_LOADED'] = '1'
    gui.load_font('/root/fonts/PressStart2P.ttf')      # script re-execs here
```

The bundled fonts do not need the guard — the constructor installs them lazily.
`set_brightness` shells out to the `brightness` binary and only works on M10.

## 6. Animation on a 240×320 Tk canvas

RK3308 @ 1.2 GHz, 512 MB RAM, 240×320 panel. Tkinter is slow-ish but **~30 FPS
with `.config()` updates is comfortably achievable**; creating and deleting
widgets inside the render loop is what kills you (Tk allocates, places, redraws
the background, deallocates → flicker and single-digit FPS).

### 6.1 Two render loops

**Loop A — `while True` + `sleep` (the standard):**

```python
while True:
    render()                      # your config() calls
    time.sleep(1 / 30)
```

The Tk mainloop is a daemon thread; `sleep` just keeps the Python process alive.
Simple, easy to reason about, used by every example.

**Loop B — Tk-native `after()`:**

```python
def render():
    ball.config(x=x, y=y)
    gui.canvas.after(int(1000 / 30), render)   # reschedule; no sleep, no while

render()
```

Loop B is what `draw_emoji` uses. Cleaner for "draw a frame, then wait for the
next event" screens (menus, button demos); not required for a game-style loop.

### 6.2 Easing toolbox

```python
def clamp(v, lo, hi): return max(lo, min(hi, v))
def lerp(a, b, t):    return a + (b - a) * t
def smoothstep(t):    return t * t * (3 - 2 * t)

def ease_out_bounce(t):          # no walrus/3.8 syntax — the board is 3.7
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375
```

Two idioms cover almost everything:

- **Exponential smoothing** (gaze, meters): `v += (target - v) * 0.20` per
  frame. `0.20` settles in ~5 frames at 30 FPS (snappy), `0.08` reads floaty,
  `0.4` is very snappy. Framerate-dependent, fine for this board.
- **Timed**: `t = (now - start) / duration`, then `smoothstep(t)` over
  `t ∈ [0, 1]`. Sin-eased blink is `sin(t * pi)` — 0→1→0 in one cycle.

### 6.3 Flicker: three causes

1. **Recreating widgets in the loop** → create once, `.config()` per frame.
2. **`GUI.clear()` / `w.remove()` mid-animation** → move off-screen instead
   (`w.config(x=-9999, y=-9999)`).
3. **Full-canvas background redraws** → draw onto one persistent background
   rect and only update the foreground items (matters for trails, e.g. a paint
   canvas).

### 6.4 Keep `PhotoImage` references alive

`PIL.ImageTk.PhotoImage` can be garbage-collected while Tk still holds the item,
which shows up as a blank/corrupt image. `CanvasImage` already caches photos on
the GUI instance (`cache_images[id]`). If you build items via
`gui.canvas.create_image` yourself, keep a module-level list and never let it
fall out of scope.

### 6.5 Z-order

`gui.canvas` is a real Tk canvas, so tags work:

```python
bg = gui.fill_rect(x=0, y=0, w=240, h=320, color="#000", tags="bg")
fg = gui.draw_text(text="Hi", x=120, y=160, origin="center", tags="fg")
gui.canvas.tag_raise("fg")
```

Pass `tags=` through the `**kw`. The wrapper only tracks the *first* Tk item id
per widget, so `tag_raise` needs your own tag string, not the widget object.

### 6.6 Which drawing style

| Style | When |
|---|---|
| **`draw_emoji` + your own `Walk-N.png`** | character sprites, walk cycles, blinks |
| **`.config()` in a loop** | eyes that follow touch, gauges, scrolling text, procedural faces |
| **PIL → `draw_image`** | sprites you want to scale/tint at load, camera preview |
| **`gui.canvas.create_*`** | arcs, polygons, bitmaps, anything the wrapper omits |

Procedural faces (a dict of per-mood geometry + eased `config()` updates) are
the right tool for a small expressive character. Past ~30 simultaneously
animating widgets, Tk's per-item `itemconfigure` overhead starts to show — that
is the point to switch to one full-screen `draw_image` fed from PIL (or pygame).

### 6.7 Structure: one state machine, one render function

For anything with modes (idle / recording / busy / result), keep a single
`state` string and a `render(state, …)` that maps it to colours and text. The
loop then only mutates `state`; drawing stays in one place, which makes the
screen easy to reason about and easy to verify from a screenshot (`verify-gui.md`
— a stable state has a characteristic colour census).

```python
state, state_since = "idle", time.time()
while True:
    # ... drain events, handle buttons, auto-transitions ...
    render(state, state_since)
    time.sleep(1 / 30)
```

### 6.8 Worker threads → UI queue

Only the main thread touches widgets. Background work (decoding, network,
sensors) reports back through a `queue.Queue` the loop drains each frame — no
locks, no Tk calls from a worker:

```python
events = queue.Queue(64)
threading.Thread(target=worker, args=(events,), daemon=True).start()

while True:
    while True:
        try:
            ev, payload = events.get_nowait()
        except queue.Empty:
            break
        handle(ev, payload)          # UI thread only
    render(...)
    time.sleep(1 / 30)
```

Give each direction its own queue (`jobs` to the worker, `events` back) and let
the worker **own** its mutable data (a frame buffer, a list of samples) so
nothing is shared. Keep the worker reading its input continuously even while it
has no work — a mic or serial stream that pauses fills the driver buffer and the
next read starts stale. The worked example is `examples/04_push_to_talk_stt.py`
in the `g-buddy` repo (see its `examples/README.md`).

### 6.9 Text that fits

The canvas does not wrap. Split text yourself and `.config(text=…)` one widget
with `\n`-joined lines (or a list of text widgets) — wrapping by character count
is close enough at these font sizes:

```python
def wrap_text(text, width=20):
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    if cur:
        lines.append(cur)
    return lines
```

Measure against the real widget when it matters: render one line, read
`bbox`, and adjust the character count — `HYQiHei` at size 14 is not monospace.

## 7. Verifying it rendered

Nobody is watching the panel when you deploy over SSH. Every GUI change should
end with a framebuffer check — colour census, ASCII render, frame diff — see
`verify-gui.md`. Landscape GUIs additionally depend on the Xorg `Rotate`
configuration in `m10-api.md` §7.
