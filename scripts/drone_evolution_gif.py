#!/usr/bin/env python3
"""Generate an animated GIF of the drone evolving mid-travel.

The drone flies across the screen and upgrades happen during flight —
eyes wake up, belly fills with modules, color shifts at full upgrade.

Output: media/drone-evolution.gif

Usage: python scripts/drone_evolution_gif.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# --- Config ---
WIDTH = 640
HEIGHT = 220
BG_COLOR = (6, 9, 18)  # --void
FIELD_Y = 70  # vertical center for the drone
FRAME_DELAY_MS = 60  # ms per frame
UPGRADE_FLASH_MS = 300
HOLD_END_MS = 2000

# Colors (from Moon Traveler palette)
MAGENTA = (196, 120, 208)
CYAN = (92, 168, 200)
AMBER = (200, 148, 80)
GREEN = (90, 200, 112)
DIM = (90, 98, 128)
TEXT_BRIGHT = (220, 224, 238)
TEXT_MUTED = (90, 98, 128)
SURFACE = (19, 24, 48)

UPGRADES = [
    "range module",
    "translator chip",
    "cargo rack",
    "thruster pack",
    "battery cell",
]


def get_mono_font(size: int):
    """Try to load a monospace font, fall back to default."""
    mono_paths = [
        "/System/Library/Fonts/SFMono-Regular.otf",
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.dfont",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "C:\\Windows\\Fonts\\consola.ttf",
    ]
    for p in mono_paths:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def build_drone(upgrade_count: int) -> tuple[str, str]:
    """Build the drone sprite for a given upgrade count."""
    eye = "O" if upgrade_count > 0 else " "
    top = f"[{eye}]--(+)--[{eye}]"

    belly = list("___________")  # 11 chars
    slots = [0, 9, 2, 7, 4]
    for i in range(min(upgrade_count, 5)):
        s = slots[i]
        belly[s] = "["
        belly[s + 1] = "]"
    bottom = "\\" + "".join(belly) + "/"

    return top, bottom


def draw_frame(
    draw: ImageDraw.Draw,
    font: ImageFont.FreeTypeFont,
    font_sm: ImageFont.FreeTypeFont,
    x: int,
    upgrade_count: int,
    label: str = "",
    flash: bool = False,
    show_title: bool = True,
    show_ground: bool = True,
    finale: bool = False,
):
    """Draw a single frame of the drone at position x."""
    # Background
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=BG_COLOR)

    # Title
    if show_title:
        title = "MOON TRAVELER TERMINAL"
        draw.text((WIDTH // 2, 14), title, fill=TEXT_MUTED, font=font_sm, anchor="mt")

    # Ground line
    if show_ground:
        ground_y = FIELD_Y + 58
        draw.line([(30, ground_y), (WIDTH - 30, ground_y)], fill=SURFACE, width=1)
        # Ground dots
        for gx in range(40, WIDTH - 30, 20):
            draw.text((gx, ground_y + 2), ".", fill=(40, 46, 70), font=font_sm)

    # Drone color
    if finale:
        color = AMBER
    elif flash:
        color = GREEN
    elif upgrade_count > 0:
        color = MAGENTA
    else:
        color = CYAN

    # Draw drone
    top, bottom = build_drone(upgrade_count)
    draw.text((x, FIELD_Y), top, fill=color, font=font)
    draw.text((x, FIELD_Y + 24), bottom, fill=color, font=font)

    # Upgrade flash effect
    if flash:
        draw.text(
            (x + 20, FIELD_Y - 22),
            "+ UPGRADE",
            fill=GREEN,
            font=font_sm,
        )

    # Label bar at bottom
    if label:
        bar_y = HEIGHT - 38
        draw.rectangle([0, bar_y - 4, WIDTH, HEIGHT], fill=(12, 16, 32))
        draw.text((WIDTH // 2, bar_y + 8), label, fill=TEXT_MUTED, font=font_sm, anchor="mt")

    # Module indicators at bottom-right
    if upgrade_count > 0:
        indicator_y = FIELD_Y + 56
        for i in range(5):
            ix = WIDTH - 140 + i * 18
            if i < upgrade_count:
                draw.rectangle([ix, indicator_y, ix + 12, indicator_y + 8], fill=GREEN)
            else:
                draw.rectangle(
                    [ix, indicator_y, ix + 12, indicator_y + 8],
                    outline=(40, 46, 70),
                )
        draw.text(
            (WIDTH - 148, indicator_y - 14),
            f"modules {upgrade_count}/5",
            fill=DIM,
            font=font_sm,
        )


def main():
    font = get_mono_font(20)
    font_sm = get_mono_font(12)

    frames: list[Image.Image] = []
    durations: list[int] = []

    total_travel_frames = 120
    # Upgrades happen at these positions during travel
    upgrade_at = [20, 40, 60, 80, 100]

    start_x = 30
    end_x = WIDTH - 180
    current_upgrades = 0

    # --- Opening: base drone static ---
    for _ in range(15):
        img = Image.new("RGB", (WIDTH, HEIGHT))
        draw = ImageDraw.Draw(img)
        draw_frame(
            draw,
            font,
            font_sm,
            x=start_x,
            upgrade_count=0,
            label="base drone — deploying...",
        )
        frames.append(img)
        durations.append(FRAME_DELAY_MS)

    # --- Travel with mid-flight upgrades ---
    for i in range(total_travel_frames):
        # Check for upgrade
        flash = False
        if i in upgrade_at:
            current_upgrades += 1
            flash = True

        # Drone position (ease in-out)
        t = i / (total_travel_frames - 1)
        # Smooth ease
        t_ease = t * t * (3 - 2 * t)
        x = int(start_x + (end_x - start_x) * t_ease)

        # Label
        if flash:
            label = f"+ {UPGRADES[current_upgrades - 1]} installed"
        elif current_upgrades == 5:
            label = "FULLY UPGRADED — all systems online"
        elif current_upgrades > 0:
            label = f"upgrade {current_upgrades}/5 — {UPGRADES[current_upgrades - 1]}"
        else:
            label = "traveling to Frost Ridge..."

        img = Image.new("RGB", (WIDTH, HEIGHT))
        draw = ImageDraw.Draw(img)
        draw_frame(
            draw,
            font,
            font_sm,
            x=x,
            upgrade_count=current_upgrades,
            label=label,
            flash=flash,
        )
        frames.append(img)
        durations.append(UPGRADE_FLASH_MS if flash else FRAME_DELAY_MS)

    # --- Finale: hold fully upgraded drone ---
    for _ in range(25):
        img = Image.new("RGB", (WIDTH, HEIGHT))
        draw = ImageDraw.Draw(img)
        draw_frame(
            draw,
            font,
            font_sm,
            x=end_x,
            upgrade_count=5,
            label="v0.5.2 — github.com/elephantatech/moon_traveler",
            finale=True,
        )
        frames.append(img)
        durations.append(80)

    # Save GIF
    out_dir = Path(__file__).parent.parent / "media"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "drone-evolution.gif"

    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )

    # File size
    size_kb = out_path.stat().st_size / 1024
    print(f"Saved: {out_path} ({size_kb:.0f} KB, {len(frames)} frames)")
    print(f"Duration: ~{sum(durations) / 1000:.1f}s")


if __name__ == "__main__":
    main()
