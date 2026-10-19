#!/usr/bin/env python3
"""Template: procedural animated character (eyes that blink, look and react).

The pattern in three lines: build every widget once, keep a mood table, and
mutate widgets with .config() in a 30 FPS loop. Recreating widgets flickers.

    python3 animated_face.py

Buttons: A cycles moods. Touch makes the eyes look at your finger.
Assumes landscape 320x240 (m10-api.md §7); set PORTRAIT for 240x320.
"""
from unihiker import GUI
from pinpong.board import Board
from pinpong.extension.unihiker import button_a
import math
import random
import time

Board().begin()                         # must precede any pinpong object

PORTRAIT = False
W, H = (240, 320) if PORTRAIT else (320, 240)

BG = "#101418"
SCLERA = "#F4F6F8"
MOODS = {
    #            sclera  iris  pupil  iris colour
    "default":   dict(rs=38, ri=22, rp=11, iris="#3A7BD5"),
    "happy":     dict(rs=36, ri=22, rp=11, iris="#33C27F"),
    "surprised": dict(rs=44, ri=26, rp=9,  iris="#3A7BD5"),
    "sleepy":    dict(rs=30, ri=18, rp=10, iris="#7A6BB5"),
    "love":      dict(rs=38, ri=24, rp=15, iris="#E0556E"),
}
MOOD_ORDER = ["default", "happy", "surprised", "sleepy", "love"]

EYE_Y = H // 2
EYE_DX = W // 4                         # eye centres at W/2 ± EYE_DX

gui = GUI(w=W, h=H)
gui.fill_rect(x=0, y=0, w=W, h=H, color=BG)

eyes = []
for sign in (-1, 1):
    cx = W // 2 + sign * EYE_DX
    eyes.append(dict(
        cx=cx,
        sclera=gui.fill_circle(x=cx, y=EYE_Y, r=38, color=SCLERA),
        iris=gui.fill_circle(x=cx, y=EYE_Y, r=22, color=MOODS["default"]["iris"]),
        pupil=gui.fill_circle(x=cx, y=EYE_Y, r=11, color="#101418"),
        glint=gui.fill_circle(x=cx + 6, y=EYE_Y - 6, r=3, color="#FFFFFF"),
    ))

label = gui.draw_text(text="default", x=W // 2, y=H - 18, font_size=12,
                      color="#8090A0", origin="center")

state = dict(mood="default", since=time.time(), touch=(W // 2, H // 2),
             blink_at=time.time() + random.uniform(2, 5), blink_t=None,
             iris_dx=0.0, prev_a=False)


def on_touch(x, y):
    state["touch"] = (x, y)
    state["mood"], state["since"] = "surprised", time.time()


gui.on_mouse_move(on_touch)


def render(now):
    mood = MOODS[state["mood"]]
    # blink: 0 -> 1 -> 0 over 0.18 s
    if state["blink_t"] is None and now >= state["blink_at"]:
        state["blink_t"] = now
    k = 0.0
    if state["blink_t"] is not None:
        t = (now - state["blink_t"]) / 0.18
        if t >= 1:
            state["blink_t"] = None
            state["blink_at"] = now + random.uniform(2, 5)
        else:
            k = math.sin(t * math.pi)          # 0 -> 1 -> 0

    # gaze eases toward the last touch, clamped to the sclera
    tx = max(-8, min(8, (state["touch"][0] - W // 2) / 12.0))
    ty = max(-6, min(6, (state["touch"][1] - EYE_Y) / 12.0))
    state["iris_dx"] += (tx - state["iris_dx"]) * 0.20
    for e in eyes:
        e["sclera"].config(r=mood["rs"])
        e["iris"].config(r=mood["ri"] * (1 - 0.55 * k), color=mood["iris"],
                         x=e["cx"] + state["iris_dx"])
        e["pupil"].config(r=mood["rp"] * (1 - 0.55 * k),
                          x=e["cx"] + state["iris_dx"], y=EYE_Y + ty * 0.4)
        if k < 0.8:                      # hide the glint by moving it off-screen
            e["glint"].config(x=e["cx"] + state["iris_dx"] + 6,
                              y=EYE_Y + ty * 0.4 - 6)
        else:
            e["glint"].config(x=-9999, y=-9999)
    label.config(text=state["mood"])


try:
    while True:
        now = time.time()
        a = button_a.is_pressed()
        if a and not state["prev_a"]:
            i = (MOOD_ORDER.index(state["mood"]) + 1) % len(MOOD_ORDER)
            state["mood"], state["since"] = MOOD_ORDER[i], now
        state["prev_a"] = a
        if state["mood"] == "surprised" and now - state["since"] > 1.5:
            state["mood"] = "default"           # touch reaction is transient
        render(now)
        time.sleep(1 / 30)
except KeyboardInterrupt:
    pass
