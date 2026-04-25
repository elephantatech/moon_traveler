#!/usr/bin/env python3
"""Drone sprite evolution demo — shows the drone upgrading from base to fully loaded.

Run:  python scripts/drone_evolution_demo.py
Record: use a screen recorder or `asciinema rec` to capture for Twitter/social media.
"""

import sys
import time

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
WHITE = "\033[97m"
BG_BLACK = "\033[40m"

UPGRADES = [
    "range_module",
    "translator_chip",
    "cargo_rack",
    "thruster_pack",
    "battery_cell",
]


def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def move_to(row, col):
    sys.stdout.write(f"\033[{row};{col}H")
    sys.stdout.flush()


def build_drone(upgrade_count: int) -> tuple[str, str]:
    """Build the drone sprite for a given upgrade count. Returns (top, bottom)."""
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


def print_centered(row: int, text: str, color: str = ""):
    col = max(1, (60 - len(text)) // 2)
    move_to(row, col)
    sys.stdout.write(f"{color}{text}{RESET}")
    sys.stdout.flush()


def draw_header():
    print_centered(2, "MOON TRAVELER TERMINAL", f"{BOLD}{WHITE}")
    print_centered(3, "Drone Upgrade Evolution", f"{DIM}{CYAN}")
    print_centered(4, "-" * 30, f"{DIM}")


def draw_upgrade_label(count: int):
    if count == 0:
        label = "Base Drone — freshly deployed"
    elif count < 5:
        label = f"Upgrade {count}/5 — {UPGRADES[count - 1].replace('_', ' ')}"
    else:
        label = "FULLY UPGRADED — all systems online"
    # Clear old label
    move_to(7, 1)
    sys.stdout.write(" " * 60)
    print_centered(7, label, f"{YELLOW}{BOLD}" if count == 5 else f"{CYAN}")


def draw_drone(count: int, color: str = MAGENTA):
    top, bottom = build_drone(count)
    # Clear old drone
    move_to(10, 1)
    sys.stdout.write(" " * 60)
    move_to(11, 1)
    sys.stdout.write(" " * 60)
    # Draw new drone
    print_centered(10, top, f"{BOLD}{color}")
    print_centered(11, bottom, f"{BOLD}{color}")


def draw_stats(count: int):
    move_to(14, 1)
    sys.stdout.write(" " * 60)
    move_to(15, 1)
    sys.stdout.write(" " * 60)
    move_to(16, 1)
    sys.stdout.write(" " * 60)

    eye_label = "O (enhanced)" if count > 0 else "  (basic)"
    belly_filled = min(count, 5)

    print_centered(14, f"Eyes: {eye_label}", f"{DIM}")
    print_centered(15, f"Modules: {'[*]' * belly_filled}{'[ ]' * (5 - belly_filled)}", f"{DIM}")
    if count > 0:
        installed = ", ".join(u.replace("_", " ") for u in UPGRADES[:count])
        # Truncate if too long
        if len(installed) > 50:
            installed = installed[:47] + "..."
        print_centered(16, installed, f"{DIM}{GREEN}")


def flash_upgrade():
    """Brief flash effect when upgrading."""
    for char in [".", "..", "...", "INSTALLING", "...", "OK"]:
        move_to(9, 1)
        sys.stdout.write(" " * 60)
        print_centered(9, char, f"{GREEN}{BOLD}")
        sys.stdout.flush()
        time.sleep(0.15)
    move_to(9, 1)
    sys.stdout.write(" " * 60)
    sys.stdout.flush()


def travel_animation(count: int):
    """Show the drone moving across the screen."""
    top, bottom = build_drone(count)
    field = 44
    sprite_w = 13
    travel_w = field - sprite_w

    move_to(19, 1)
    sys.stdout.write(" " * 60)
    print_centered(19, "-- travel demo --", f"{DIM}")

    for i in range(travel_w + 1):
        move_to(20, 1)
        sys.stdout.write(" " * 60)
        move_to(21, 1)
        sys.stdout.write(" " * 60)

        pad = " " * (5 + i)
        move_to(20, 1)
        sys.stdout.write(f"{BOLD}{MAGENTA}{pad}{top}{RESET}")
        move_to(21, 1)
        sys.stdout.write(f"{BOLD}{MAGENTA}{pad}{bottom}{RESET}")
        sys.stdout.flush()
        time.sleep(0.08)

    # Arrival
    move_to(19, 1)
    sys.stdout.write(" " * 60)
    print_centered(19, "Arrived at Frost Ridge.", f"{GREEN}")
    sys.stdout.flush()
    time.sleep(1.0)

    # Clear travel area
    for row in range(19, 23):
        move_to(row, 1)
        sys.stdout.write(" " * 60)
    sys.stdout.flush()


def main():
    # Hide cursor
    sys.stdout.write("\033[?25l")
    clear_screen()

    try:
        draw_header()

        # Show base drone
        draw_upgrade_label(0)
        draw_drone(0)
        draw_stats(0)
        time.sleep(2.0)

        # Travel with base drone
        travel_animation(0)
        time.sleep(0.5)

        # Upgrade sequence
        for i in range(1, 6):
            flash_upgrade()
            draw_upgrade_label(i)
            draw_drone(i, YELLOW if i == 5 else MAGENTA)
            draw_stats(i)
            time.sleep(1.5)

        # Final travel with fully upgraded drone
        time.sleep(0.5)
        travel_animation(5)

        # Finale
        draw_drone(5, YELLOW)
        move_to(19, 1)
        print_centered(19, "v0.5.2 — Animations, Upgrades & Diagnostics", f"{BOLD}{CYAN}")
        print_centered(20, "github.com/elephantatech/moon_traveler", f"{DIM}")
        time.sleep(3.0)

    finally:
        # Show cursor, move below output
        move_to(23, 1)
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        print()


if __name__ == "__main__":
    main()
