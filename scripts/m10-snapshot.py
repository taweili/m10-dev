#!/usr/bin/env python3
"""Capture the M10 framebuffer and pull it to the PC as a PNG.

Usage:
    ./m10-snapshot.py                      # -> m10-frame.png (unrotated)
    ./m10-snapshot.py --rotate 90          # landscape (Xorg Rotate="CW")
    ./m10-snapshot.py --census             # print dominant colours
    ./m10-snapshot.py --raw                # pull the raw /dev/fb0 bytes too

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
    if args.rotate:
        im = im.rotate(args.rotate, expand=True)
        im.save(args.out)
        print("rotated", args.rotate, "->", im.size)
    if args.census:
        from collections import Counter
        top = Counter(im.getdata()).most_common(8)
        for colour, n in top:
            print("  %-18s %6d px  (#%02X%02X%02X)" % (colour, n, *colour))


if __name__ == "__main__":
    main()
