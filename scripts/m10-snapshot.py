#!/usr/bin/env python3
"""Capture the M10 framebuffer and pull it to the PC as a PNG.

Usage:
    ./m10-snapshot.py                      # -> m10-frame.png (unrotated)
    ./m10-snapshot.py --rotate 90          # landscape (Xorg Rotate="CW")
    ./m10-snapshot.py --crop 0,0,120,60 --zoom 4   # legible detail crop
    ./m10-snapshot.py --census             # print dominant colours
    ./m10-snapshot.py --raw                # pull the raw /dev/fb0 bytes too

The point of this script is that the PNG is **for looking at**: open it with
the read tool / an image viewer. No ASCII approximation, no guessing from
colour counts alone — you see exactly what the panel shows. --crop/--zoom exist
so small features (glyphs, a 12 px legend, a single widget) stay readable when
upscaled instead of having to be described in text.

Why a script: /dev/fb0 is 240x320 RGB565 with a 480-byte stride, and the PIL
on the board cannot decode RGB565 ("unknown raw mode"). The decode has to run
on the board; the rotation belongs on the PC (X rotates in userspace, so the
framebuffer stays 240x320 in landscape).

Env: M10_HOST, M10_USER, M10_PASS (defaults 10.1.2.3 / root / dfrobot).
See references/verify-gui.md for how to read the result.
"""
import argparse
import os
import sys
import time

try:
    import paramiko
except ImportError:
    sys.exit("paramiko is required: pip install paramiko")

HOST = os.environ.get("M10_HOST", "10.1.2.3")
USER = os.environ.get("M10_USER", "root")
PASS = os.environ.get("M10_PASS", "dfrobot")

# Runs on the board. Writes /tmp/m10-frame.png and prints the byte count.
SNAP = r'''
import struct
from PIL import Image

W, H, STRIDE = 240, 320, 480
with open("/dev/fb0", "rb") as f:
    data = f.read()
compact = b"".join(data[y * STRIDE:y * STRIDE + W * 2] for y in range(H))
px = struct.unpack("<%dH" % (W * H), compact)
buf = bytearray(W * H * 3)
for i, p in enumerate(px):
    buf[i * 3] = (p >> 11) << 3
    buf[i * 3 + 1] = ((p >> 5) & 0x3F) << 2
    buf[i * 3 + 2] = (p & 0x1F) << 3
Image.frombytes("RGB", (W, H), bytes(buf)).save("/tmp/m10-frame.png")
print("ok", len(data))
'''


def client():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=10)
    return c


def run(c, cmd, t=30):
    _, so, se = c.exec_command(cmd, timeout=t)
    return (so.read() + se.read()).decode(errors="replace").strip()


def main():
    global HOST
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="m10-frame.png")
    ap.add_argument("--rotate", type=int, choices=(0, 90, 180, 270), default=0,
                    help="rotate on the PC to match the panel; 90 = Rotate CW")
    ap.add_argument("--crop", metavar="X,Y,W,H",
                    help="keep only this rectangle (applied after --rotate)")
    ap.add_argument("--zoom", type=int, default=1, metavar="N",
                    help="nearest-neighbour upscale by N so detail is legible")
    ap.add_argument("--census", action="store_true", help="print top colours")
    ap.add_argument("--raw", action="store_true", help="also pull raw /dev/fb0")
    ap.add_argument("--host", default=HOST)
    args = ap.parse_args()

    HOST = args.host
    c = client()
    try:
        # Upload the decoder (idempotent), run it, pull the PNG.
        sftp = c.open_sftp()
        with sftp.file("/tmp/m10-snap.py", "w") as fh:
            fh.write(SNAP)
        out = run(c, "python3 /tmp/m10-snap.py")
        if not out.startswith("ok"):
            sys.exit("snapshot failed on the board:\n" + out)
        sftp.get("/tmp/m10-frame.png", args.out)
        if args.raw:
            raw = args.out.rsplit(".", 1)[0] + ".fb0"
            sftp.get("/dev/fb0", raw)
            print("raw:", raw, os.path.getsize(raw), "bytes")
        sftp.close()
    finally:
        c.close()

    print("frame:", args.out, os.path.getsize(args.out), "bytes",
          "at", time.strftime("%H:%M:%S"))

    try:
        from PIL import Image
    except ImportError:
        if args.rotate or args.census:
            print("PIL not installed on the PC — skipping rotate/census")
        return

    im = Image.open(args.out)
    touched = False
    if args.rotate:
        im = im.rotate(args.rotate, expand=True)
        print("rotated", args.rotate, "->", im.size)
        touched = True
    if args.crop:
        try:
            box = tuple(int(v) for v in args.crop.split(","))
            if len(box) != 4:
                raise ValueError
        except ValueError:
            sys.exit("--crop wants X,Y,W,H (four integers), got %r" % args.crop)
        x, y, cw, ch = box
        # Clamp rather than raise: a hand-typed box is usually approximate.
        big = im.crop((max(0, x), max(0, y),
                       min(im.size[0], x + cw), min(im.size[1], y + ch)))
        if big.size == (0, 0):
            sys.exit("crop %r selected no pixels of %dx%d" % (args.crop, *im.size))
        if big.size != (cw, ch):
            print("crop clamped %dx%d -> %dx%d" % (cw, ch, big.size[0], big.size[1]))
        im = big
        touched = True
    if args.zoom > 1:
        im = im.resize((im.size[0] * args.zoom, im.size[1] * args.zoom),
                       Image.NEAREST)
        touched = True
    if touched:
        im.save(args.out)
        print("saved", args.out, im.size)
    if args.census:
        from collections import Counter
        # Pillow >=12 deprecates Image.getdata() (it warns on every census), but
        # the board-ish hosts still run older Pillows, so try the new name first.
        pixels = getattr(im, "get_flattened_data", None)
        top = Counter(pixels() if pixels else im.getdata()).most_common(8)
        for colour, n in top:
            print("  %-18s %6d px  (#%02X%02X%02X)" % (colour, n, *colour))


if __name__ == "__main__":
    main()
