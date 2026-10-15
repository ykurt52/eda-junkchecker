"""Regenerate the application icon (development only, needs Pillow: pip install pillow).

    python tools\\make_icon.py

Design: an IC package whose top shows a trash bin drawn with copper traces and vias.

Writes junkchecker/assets/icon.ico (16-256 px, used by Windows and PyInstaller)
and icon-16/32/48/256.png (used by Tk's iconphoto). The running program itself
only reads these files and does not need Pillow.
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "junkchecker", "assets")

BODY, BODY_EDGE = (36, 39, 46), (62, 66, 76)
PIN = (196, 200, 208)
COPPER = (230, 168, 60)
S = 1024  # draw large, then downsample


def draw():
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    # pins on all four sides (QFP-like), 4 per side
    for i in range(4):
        c = 302 + i * 140
        d.rounded_rectangle((60, c - 30, 190, c + 30), radius=10, fill=PIN)          # left
        d.rounded_rectangle((834, c - 30, 964, c + 30), radius=10, fill=PIN)         # right
        d.rounded_rectangle((c - 30, 60, c + 30, 190), radius=10, fill=PIN)          # top
        d.rounded_rectangle((c - 30, 834, c + 30, 964), radius=10, fill=PIN)         # bottom

    # package body
    d.rounded_rectangle((150, 150, 874, 874), radius=70, fill=BODY_EDGE)
    d.rounded_rectangle((168, 168, 856, 856), radius=56, fill=BODY)

    # trash bin drawn with traces, vias at every corner
    w = 44

    def via(x, y, r=46):
        d.ellipse((x - r, y - r, x + r, y + r), fill=COPPER)
        d.ellipse((x - r * 0.42, y - r * 0.42, x + r * 0.42, y + r * 0.42), fill=BODY)

    lid_y, top_y, bot_y = 360, 430, 760
    tl, tr, bl, br = (350, top_y), (674, top_y), (392, bot_y), (632, bot_y)
    d.line([(300, lid_y), (724, lid_y)], fill=COPPER, width=w)                         # lid
    d.line([(450, lid_y), (450, 290), (574, 290), (574, lid_y)], fill=COPPER, width=w, joint="curve")  # handle
    d.line([tl, bl, br, tr], fill=COPPER, width=w, joint="curve")                      # body outline
    d.line([(512, 490), (512, 700)], fill=COPPER, width=w)                             # centre trace
    for p in ((300, lid_y), (724, lid_y), bl, br, (512, 490), (512, 700)):
        via(*p)
    return im


def main():
    os.makedirs(OUT, exist_ok=True)
    big = draw()
    sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = {n: big.resize((n, n), Image.LANCZOS) for n in sizes}
    imgs[256].save(os.path.join(OUT, "icon.ico"), sizes=[(n, n) for n in sizes])
    for n in (16, 32, 48, 256):
        imgs[n].save(os.path.join(OUT, f"icon-{n}.png"))
    print("written:", OUT)


if __name__ == "__main__":
    main()
