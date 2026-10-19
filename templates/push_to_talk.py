#!/usr/bin/env python3
"""Template: push-to-talk speech-to-text (Vosk) with a one-circle UI.

Hold the B button, speak, release: the clip is decoded and the transcript is
shown. Architecture worth keeping:

  - one mic thread owns the pyaudio stream and reads continuously, so there is
    no open-gap when you press B;
  - decode runs in a short-lived thread, so the mic keeps draining meanwhile;
  - the UI thread only talks to the workers through two queues;
  - one `state` string drives everything, and `render()` maps it to the screen.

    python3 push_to_talk.py              # live mic
    python3 push_to_talk.py --file x.wav # decode a file, no mic

Requires the Vosk model (speech.md) and, on Debian 10, the libstdc++ preload.
Assumes landscape 320x240; set PORTRAIT for 240x320.
"""
import argparse
import json
import os
import queue
import sys
import threading
import time
import wave

# ── Vosk needs a newer libstdc++ than Debian 10 ships (speech.md) ──────────
LIBSTDCPP = ("/root/speech-models/extracted_libstdc++"
             "/usr/lib/aarch64-linux-gnu/libstdc++.so.6")
if os.path.isfile(LIBSTDCPP) and os.environ.get("_VOSK_PRELOADED") != "1":
    os.environ["_VOSK_PRELOADED"] = "1"
    os.environ["LD_PRELOAD"] = LIBSTDCPP + os.pathsep + os.environ.get("LD_PRELOAD", "")
    os.execv(sys.executable, [sys.executable] + sys.argv)

import vosk
import pyaudio
from unihiker import GUI
from pinpong.board import Board
from pinpong.extension.unihiker import button_b

MODEL_PATH = "/root/speech-models/vosk-model-small-en-us-0.15"
RATE, CHUNK = 16000, 4000                   # 16 kHz mono, 0.25 s chunks
RECORD_DIR = "/tmp/voice"
MAX_SECONDS = 8

PORTRAIT = False
W, H = (240, 320) if PORTRAIT else (320, 240)
BG, GREEN, YELLOW, RED = "#101418", "#4CAF50", "#FFEB3B", "#F44336"
RADIUS = 52

Board().begin()
gui = GUI(w=W, h=H)
gui.fill_rect(x=0, y=0, w=W, h=H, color=BG)
circle = gui.fill_circle(x=W // 2, y=H // 2, r=RADIUS, color=GREEN)
text = gui.draw_text(text="hold B", x=W // 2, y=H // 2, font_size=14,
                     color="white", origin="center")

jobs, events = queue.Queue(), queue.Queue()


def open_mic():
    p = pyaudio.PyAudio()
    pick = None
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0 and "loopback" not in info["name"].lower():
            pick = i
            break
    if pick is None:
        return p, None
    return p, p.open(format=pyaudio.paInt16, channels=1, rate=RATE,
                     input=True, input_device_index=pick,
                     frames_per_buffer=CHUNK)


def transcribe(path, model):
    rec = vosk.KaldiRecognizer(model, RATE)
    parts = []
    with wave.open(path, "rb") as wf:
        while True:
            data = wf.readframes(CHUNK)
            if not data:
                break
            if rec.AcceptWaveform(data):
                t = json.loads(rec.Result()).get("text", "").strip()
                if t:
                    parts.append(t)
    parts.append(json.loads(rec.FinalResult()).get("text", "").strip())
    return " ".join(x for x in parts if x).strip()


def mic_worker(stream, model):
    frames, recording, started, path = [], False, 0.0, ""
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False) if stream else b""
        if recording:
            frames.append(data)
        while True:
            try:
                cmd, payload = jobs.get_nowait()
            except queue.Empty:
                break
            if cmd == "start":
                frames, recording, started, path = [], True, time.time(), payload
            elif cmd == "stop" and recording:
                recording = False
                blob, frames = b"".join(frames), []
                threading.Thread(target=decode_job,
                                 args=(path, blob, model), daemon=True).start()
        if recording and time.time() - started >= MAX_SECONDS:
            recording = False
            blob, frames = b"".join(frames), []
            threading.Thread(target=decode_job,
                             args=(path, blob, model), daemon=True).start()


def decode_job(path, blob, model):
    try:
        os.makedirs(RECORD_DIR, exist_ok=True)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(RATE)
            wf.writeframes(blob)
        events.put(("result", transcribe(path, model) if len(blob) > 9600
                    else "(nothing heard)"))
    except Exception as exc:
        events.put(("result", "error: %s" % exc))


def render(state, transcript=""):
    colour = {"idle": GREEN, "recording": YELLOW,
              "transcribing": RED, "result": GREEN}[state]
    circle.config(color=colour)
    if state == "recording":
        text.config(text="listening")
    elif state == "transcribing":
        text.config(text="...")
    elif transcript:
        text.config(text=transcript[:80])
    else:
        text.config(text="hold B")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    args = ap.parse_args()

    model = vosk.Model(MODEL_PATH)
    if args.file:                            # headless test path
        print(transcribe(args.file, model))
        return

    stream = open_mic()[1]
    if stream is None:
        print("no capture device found", file=sys.stderr)
        return
    threading.Thread(target=mic_worker, args=(stream, model), daemon=True).start()

    state, transcript, prev_b = "idle", "", False
    try:
        while True:
            while True:
                try:
                    ev, payload = events.get_nowait()
                except queue.Empty:
                    break
                if ev == "result":
                    transcript, state = payload, "result"
            b = button_b.is_pressed()
            if b and not prev_b and state in ("idle", "result"):
                os.makedirs(RECORD_DIR, exist_ok=True)
                path = os.path.join(RECORD_DIR, "voice_%d.wav" % int(time.time()))
                jobs.put(("start", path))
                state = "recording"
            elif not b and prev_b and state == "recording":
                jobs.put(("stop", None))
                state = "transcribing"
            prev_b = b
            render(state, transcript)
            time.sleep(1 / 30)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
