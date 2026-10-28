"""Regenerates the fictional Northstar sample creatives and logo (deterministic output).

Run from the repo root:  python samples/generate_samples.py
Fonts: uses DejaVu Sans if available, then Arial, then Pillow's built-in font.
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TEAL, NAVY, WHITE = "#0F9D91", "#101B2D", "#FFFFFF"


def font(size, bold=False):
    names = (["DejaVuSans-Bold.ttf", "arialbd.ttf"] if bold else ["DejaVuSans.ttf", "arial.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def logo(size=(460, 120)) -> Image.Image:
    img = Image.new("RGB", size, WHITE)
    d = ImageDraw.Draw(img)
    h = size[1]
    cx, cy, r = h // 2, h // 2, h * 0.36
    pts = []
    import math
    for i in range(8):
        ang = math.pi / 2 + i * math.pi / 4
        rr = r if i % 2 == 0 else r * 0.38
        pts.append((cx + rr * math.cos(ang), cy - rr * math.sin(ang)))
    d.polygon(pts, fill=TEAL)
    d.text((h + 4, h * 0.26), "NORTHSTAR", font=font(int(h * 0.36), True), fill=NAVY)
    return img


def creative(name, bg, lines, with_logo=True, blob=None):
    img = Image.new("RGB", (1080, 1080), bg)
    d = ImageDraw.Draw(img)
    if blob:
        d.rectangle(blob["box"], fill=blob["color"])
    if with_logo:
        img.paste(logo(), (60, 60))
    for (x, y), text, size, color, bold in lines:
        d.text((x, y), text, font=font(size, bold), fill=color)
    path = os.path.join(HERE, "creatives", name)
    img.save(path, optimize=True)
    return path


def main():
    os.makedirs(os.path.join(HERE, "creatives"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "brand"), exist_ok=True)
    logo().save(os.path.join(HERE, "brand", "northstar-logo.png"))

    disclaimer = "Results may vary based on client workload"
    creative("01-compliant-atlas.png", WHITE, [
        ((80, 300), "Meet Atlas Pro", 84, NAVY, True),
        ((80, 430), "Accelerate workload throughput", 50, NAVY, False),
        ((80, 500), "by up to 34% within 90 days.", 50, NAVY, False),
        ((80, 900), disclaimer, 30, NAVY, False),
        ((80, 945), "and infrastructure configurations.", 30, NAVY, False),
    ])
    creative("02-violations-guarantee.png", NAVY, [
        ((80, 300), "Northstar guarantees results", 64, WHITE, True),
        ((80, 420), "100% risk-free migration!!!", 56, WHITE, True),
        ((80, 560), "Ask your account team today", 44, "#3A4656", False),
    ], with_logo=False, blob={"box": (0, 760, 1080, 1080), "color": "#F26B1D"})
    creative("03-terminology-uptime.png", WHITE, [
        ((80, 300), "Our users love Atlas Pro", 64, NAVY, True),
        ((80, 420), "Northstar delivers 99.9% uptime", 50, NAVY, False),
        ((80, 490), "backed by multi-region failover.", 50, NAVY, False),
    ])
    creative("04-low-contrast.png", "#E9EEF2", [
        ((80, 300), "Cloud governance, simplified", 60, "#B9C3CC", True),
        ((80, 420), "Discover automated policy guardrails", 42, "#AEB8C1", False),
        ((80, 900), disclaimer, 30, NAVY, False),
        ((80, 945), "and infrastructure configurations.", 30, NAVY, False),
    ])
    print("Sample creatives written to", os.path.join(HERE, "creatives"))


if __name__ == "__main__":
    main()
