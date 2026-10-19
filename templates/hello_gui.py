#!/usr/bin/env python3
"""Template: minimal GUI screen.

Copy this next to your project, rename it, deploy it. It is deliberately tiny:
one window, one background item, one text widget, one render loop.

    python3 hello_gui.py

Landscape by default (the board must be rotated, see m10-api.md §7). Set
PORTRAIT = True for a 240x320 screen without rotation.
"""
from unihiker import GUI
import time

PORTRAIT = False
W, H = (240, 320) if PORTRAIT else (320, 240)

BG = "#101418"
FG = "#FFFFFF"

gui = GUI(w=W, h=H)                     # must match the X screen size
bg = gui.fill_rect(x=0, y=0, w=W, h=H, color=BG)
label = gui.draw_text(text="Hello", x=W // 2, y=H // 2, font_size=24,
                      color=FG, origin="center")

try:
    while True:                         # Tk runs on its own thread; stay alive
        label.config(text="Hello")
        time.sleep(1 / 30)
except KeyboardInterrupt:               # Ctrl+C / SIGINT is a clean exit
    pass
