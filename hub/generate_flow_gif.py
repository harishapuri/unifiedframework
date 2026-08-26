"""Looping GIF: outer completed flow, then the internal agent workflow.

Outer: Ingest → CRC → ZeroGuard → InfraAgent → DSA → Audit
Inner: CRC sensors, ZeroGuard ICA/ZTPA/IAEA/GRA, InfraAgent T-GAN/CFA/RPA,
       shared bus → orchestrator → DQN → audit.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
BG = (13, 15, 22)
PANEL = (23, 26, 36)
INK = (231, 233, 240)
MUTED = (138, 143, 163)
LINE = (42, 46, 61)
ACCENT = (91, 127, 255)
OK = (62, 207, 142)
TEAL = (94, 176, 186)

OUT = Path(__file__).resolve().parent / "static" / "flow.gif"
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONTB = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

STAGES = [
    ("Ingest", "Checkov + telemetry", "read the scan"),
    ("CRC", "η  ·  residual", "policy adherence"),
    ("ZeroGuard", "Ψ  ·  Ξ  ·  Γ", "zero-trust IaC"),
    ("InfraAgent", "Ω  ·  φ  ·  κ", "predictive ops"),
    ("DSA gate", "ALLOW / BLOCK", "one decision"),
    ("Audit", "SHA-256 chain", "append-only log"),
]

LANES = [
    ("CRC sensors", [("Code GB", "snippet risk"), ("Container", "image ensemble"), ("IsoForest", "chat telemetry"), ("η residual", "policy score")]),
    ("ZeroGuard", [("ICA", "resource graph"), ("ZTPA", "7 pillars"), ("IAEA", "IAM excess Γ"), ("GRA", "patch + Rego")]),
    ("InfraAgent", [("T-GAN", "φ 1h/6h/24h"), ("CFA", "capacity κ"), ("RPA", "rollout"), ("DSA", "α2 gate")]),
    ("Shared backbone", [("Bus", "priority queue"), ("MAWS hive", "named agents"), ("DSA α2", "ALLOW/BLOCK"), ("Audit", "SHA-256")]),
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONTB if bold else FONT, size)


def lerp(a, b, t: float):
    t = max(0.0, min(1.0, t))
    if isinstance(a, tuple):
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))
    return a + (b - a) * t


def center_text(draw: ImageDraw.ImageDraw, xy, text, f, fill=INK) -> None:
    x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=f)
    draw.text((xy[0] - (x1 - x0) / 2, xy[1] - (y1 - y0) / 2), text, font=f, fill=fill)


def arrow(draw, p1, p2, color=LINE, width=3, head=9) -> None:
    draw.line([p1, p2], fill=color, width=width)
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = max((dx * dx + dy * dy) ** 0.5, 1)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    left = (p2[0] - ux * head + px * head * 0.55, p2[1] - uy * head + py * head * 0.55)
    right = (p2[0] - ux * head - px * head * 0.55, p2[1] - uy * head - py * head * 0.55)
    draw.polygon([p2, left, right], fill=color)


def chrome(draw, subtitle: str, caption: str, badge: str | None = None) -> None:
    draw.rectangle((0, 0, W, 72), fill=(17, 19, 28))
    draw.line((0, 72, W, 72), fill=LINE, width=1)
    draw.text((32, 14), "How a bank ships a customer chatbot", font=font(20, True), fill=INK)
    draw.text((32, 44), subtitle, font=font(13), fill=ACCENT)
    draw.rectangle((0, H - 48, W, H), fill=(17, 19, 28))
    draw.line((0, H - 48, W, H - 48), fill=LINE, width=1)
    draw.text((32, H - 30), caption, font=font(13), fill=MUTED)
    if badge:
        draw.text((W - 32, H - 30), badge, font=font(13, True), fill=OK, anchor="rt")


def box(draw, cx, cy, w, h, title, sub, active: float, done: bool = False) -> None:
    outline = lerp(LINE, OK if done else ACCENT, active)
    fill = lerp(PANEL, (28, 42, 38) if done else (28, 32, 52), active)
    draw.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 8, fill=fill, outline=outline, width=2)
    center_text(draw, (cx, cy - 10), title, font(13, True), INK)
    center_text(draw, (cx, cy + 12), sub, font(10), MUTED)


def node_xy(i: int) -> tuple[int, int]:
    gap = W / (len(STAGES) + 1)
    return int(gap * (i + 1)), 200


def draw_outer(draw, lit: int, pulse: float, completed: bool) -> None:
    for i in range(len(STAGES)):
        title, sub, _ = STAGES[i]
        cx, cy = node_xy(i)
        if completed or i < lit:
            box(draw, cx, cy, 164, 78, title, sub, 1.0, True)
        elif i == lit:
            box(draw, cx, cy, 164, 78, title, sub, pulse, False)
        else:
            box(draw, cx, cy, 164, 78, title, sub, 0.12, False)
        if i < len(STAGES) - 1:
            x1, y = node_xy(i)
            x2, _ = node_xy(i + 1)
            hot = completed or i < lit
            arrow(draw, (x1 + 86, y), (x2 - 86, y), OK if hot else lerp(LINE, ACCENT, 0.3 if i == lit else 0.12), 3)


def lane_cell(lane: int, step: int) -> tuple[int, int]:
    y = 340 + lane * 80
    x = 220 + step * 260
    return x, y


def draw_internal(draw, lit: int, pulse: float, completed: bool) -> None:
    for li, (lane_name, steps) in enumerate(LANES):
        draw.text((28, 328 + li * 80), lane_name, font=font(12, True), fill=TEAL)
        for si, (title, sub) in enumerate(steps):
            idx = li * 4 + si
            cx, cy = lane_cell(li, si)
            if completed or idx < lit:
                box(draw, cx, cy, 150, 56, title, sub, 1.0, True)
            elif idx == lit:
                box(draw, cx, cy, 150, 56, title, sub, pulse, False)
            else:
                box(draw, cx, cy, 150, 56, title, sub, 0.12, False)
            if si < 3:
                x1, y = lane_cell(li, si)
                x2, _ = lane_cell(li, si + 1)
                hot = completed or idx < lit
                arrow(draw, (x1 + 78, y), (x2 - 78, y), OK if hot else LINE, 2)


def compose() -> list[Image.Image]:
    frames: list[Image.Image] = []

    def add(im: Image.Image, n: int = 2) -> None:
        for _ in range(n):
            frames.append(im.copy())

    for i, (_t, _s, hint) in enumerate(STAGES):
        for pulse in (0.4, 0.8, 1.0):
            im = Image.new("RGB", (W, H), BG)
            d = ImageDraw.Draw(im)
            chrome(d, "Outer flow  ·  Ingest → CRC → ZeroGuard → InfraAgent → DSA → Audit", f"{i + 1}/{len(STAGES)}  {STAGES[i][0]} — {hint}")
            draw_outer(d, i, pulse, False)
            add(im, 2)

    hold = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(hold)
    chrome(d, "Outer flow complete — now the internal agent workflow", "One fused gate, then the planes inside each box", "customers stay on blue until ALLOW")
    draw_outer(d, len(STAGES), 1.0, True)
    add(hold, 8)

    total_inner = sum(len(steps) for _n, steps in LANES)
    for idx in range(total_inner):
        lane, step = divmod(idx, 4)
        title, sub = LANES[lane][1][step]
        for pulse in (0.45, 1.0):
            im = Image.new("RGB", (W, H), BG)
            d = ImageDraw.Draw(im)
            chrome(d, "Internal workflow  ·  sensors, ZeroGuard, InfraAgent, shared backbone", f"{LANES[lane][0]}  ·  {title} — {sub}")
            draw_outer(d, len(STAGES), 1.0, True)
            draw_internal(d, idx, pulse, False)
            add(im, 2)

    done = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(done)
    chrome(d, "Completed  ·  outer flow + internal workflow", "Bus merges CRC + ZeroGuard + InfraAgent → DSA → audit chain", "ALLOW  ·  customers may move to green")
    draw_outer(d, len(STAGES), 1.0, True)
    draw_internal(d, total_inner, 1.0, True)
    add(done, 18)
    return frames


def main() -> None:
    frames = compose()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
        optimize=False,
        disposal=2,
    )
    print(f"Wrote {OUT} ({len(frames)} frames, {OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
