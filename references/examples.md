# 4b. Examples and the patterns they teach

All of these live in the `g-buddy` repo under `examples/`, numbered for reading
order. 02–04 are GUI scripts (`while True`), meant to be deployed and run in the
background (`paramiko.md`).

| File | What it is | Teaches |
|---|---|---|
| `01_hello_world.py` | 14-line smoke test: centred "Hello Buddy!" | Minimal shape of every GUI script |
| `02_animated_eyes_portrait.py` | Animated buddy face, **portrait 240×320** | Shape animation, mood table, touch-follow, idle behaviour |
| `03_animated_eyes_landscape.py` | Same face, **landscape 320×240** | Landscape layout + mood label; requires Xorg rotate |
| `04_push_to_talk_stt.py` | Push-to-talk Vosk STT in one circle | Record-then-decode, thread + queue UI, Vosk ABI preload, `--file` test mode |

## 01 — hello world

```python
from unihiker import GUI
import time

gui = GUI(w=320, h=240)                       # landscape
gui.draw_text(text='Hello Buddy!', x=160, y=120, font_size=20,
              color='#0000FF', origin='center')

while True:                                   # keep the process (and Tk) alive
    time.sleep(1)
```

## 02 / 03 — animated eyes

Portrait and landscape versions of the same idea: a dict of per-mood geometry,
eased iris movement, and a sin-eased blink.

- Eyes are `fill_circle` **centre + radius** triplets (sclera / iris / pupil /
  highlight), plus a `fill_rect` lid whose height follows the blink.
- **Mood table** — `MOODS = {name: {r_s, r_i, r_p, sclera, iris}}`,
  `MOOD_ORDER = ["default", "happy", "surprised", "sleepy", "love"]`. The A
  button cycles the order; touch forces a brief `surprised`; 15 s idle → `sleepy`.
- **Blink** — `next_blink = now + random.uniform(2, 5)`; `shrink =
  sin(blink_t * pi)` scales radii and grows the lid.
- **Gaze** — irises ease toward the touch point (`iris_dx += (target - iris_dx) * 0.2`)
  and wander randomly after a few idle seconds.
- 03 spreads the eyes horizontally for 320×240 and adds a bottom mood label.

Reusable: everything is a `widget.config(...)` update per frame at ~30 FPS
(`time.sleep(1/30)`), never a redraw.

## 04 — push-to-talk STT (the most complete reference)

One circle is the whole UI: **green** idle → **yellow** while B is held and the
mic records → **red** while Vosk decodes → **green** with the transcript.

Architecture worth copying:

- **Record to a file, then decode it.** The button press *is* the utterance
  boundary, so no voice-activity detection is needed. Clips are kept in
  `/tmp/04-voice/voice_<timestamp>.wav` (16 kHz mono 16-bit).
- **One mic thread owns the pyaudio stream** and reads continuously (so pressing
  B has no open-gap); it appends frames only while recording.
- **Decode runs in a short-lived thread** so the mic keeps draining while Vosk
  works — otherwise the input buffer backs up and the next clip starts with
  stale audio.
- Main loop ↔ worker communicate **only** through two `queue.Queue`s (`jobs`,
  `events`); the worker owns `frames`, so no locks.
- `--file speech.wav` runs the same decode headlessly, for testing without a mic.
- Self-restarts with `LD_PRELOAD` via `os.execv` for the Vosk ABI fix, guarded by
  `_VOSK_PRELOADED=1`.
- 15 s hold cap; `(nothing heard)` when the clip is empty/short.

## Patterns to reuse

**State machine + single render function.** Keep one `state` string and a
`render(state, …)` that maps it to colours/text. Easy to reason about, easy to
verify from a screenshot.

```python
state, state_since = "idle", time.time()
while True:
    # ... drain events, handle buttons, auto-transitions ...
    render(state, state_since)
    time.sleep(1/30)
```

**Push-to-talk edge detection** (polling loop):

```python
b = button_b.is_pressed()
if b and not prev_b and state in ("idle", "result"):   # rising edge → start
    start()
elif not b and prev_b and state == "recording":        # falling edge → stop
    stop()
prev_b = b
```

**Background worker → UI queue:**

```python
events = queue.Queue(64)
threading.Thread(target=worker, args=(events,), daemon=True).start()
while True:
    while True:
        try: ev, payload = events.get_nowait()
        except queue.Empty: break
        handle(ev, payload)          # UI thread only touches widgets
```

**Word-wrap text into a circle:**

```python
def wrap_text(text, width=20):
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur); cur = word
        else:
            cur = (cur + " " + word).strip()
    if cur: lines.append(cur)
    return lines
```

**Model-loaded-once, recognizer-per-utterance** — see `m10-api.md` §8.

## Running them

```python
c.open_sftp().put("examples/04_push_to_talk_stt.py",
                  "/root/g-buddy/04_push_to_talk_stt.py")
run("pkill -KILL -f '04_push_to_talk_stt'; sleep 1", 5)
run("cd /root/g-buddy && (python3 04_push_to_talk_stt.py > /tmp/t04.out 2> /tmp/t04.err &)", 5)
```

Expect a confirmed green idle circle on the panel before trusting anything else.
`python3 -m py_compile` the file locally first — cheap, catches syntax errors
before a round trip.
