# Assets — Moon Traveler CLI

## Generated Screenshots (from game walkthrough)

These are auto-generated using Rich's SVG export via `scripts/screenshot_walkthrough.py`. Run it to regenerate after code changes:

```bash
uv run python scripts/screenshot_walkthrough.py
```

| File | Content |
|------|---------|
| `screenshot-title-screen.svg` | ASCII art title banner |
| `screenshot-crash-site--first-look.svg` | Starting location with status bar and ship bays |
| `screenshot-scanning-for-locations.svg` | Scan results discovering 3 locations |
| `screenshot-gps-map-view.svg` | GPS table with distances and coordinates |
| `screenshot-drone-status.svg` | Drone stats panel |
| `screenshot-traveling-to-a-location.svg` | Travel narration and ARIA summary |
| `screenshot-location-with-creature-and-items.svg` | Cave with items and creature |
| `screenshot-taking-items-and-inventory.svg` | Picking up items, inventory table |
| `screenshot-player-status.svg` | Food/water/suit/time + repair checklist |
| `screenshot-giving-a-gift-to-build-trust.svg` | Trust increase from gift |
| `screenshot-creature-conversation.svg` | Dialogue with drone whispers |
| `screenshot-escort-system.svg` | Escort command and ARIA approval |
| `screenshot-status-bar-with-follower.svg` | Status bar showing followers |
| `screenshot-ship-bays-menu.svg` | Ship repair checklist + all 5 bays |
| `screenshot-ship-repair-progress.svg` | Partial repair progress |
| `screenshot-dev-mode-diagnostics.svg` | Dev panel with location table and scan tree |
| `screenshot-help-screen.svg` | Full command list |

## Hand-Crafted Graphics

| File | Purpose | Notes |
|------|---------|-------|
| `banner.svg` | README header | Enceladus landscape with Saturn, crashed ship, title |
| `icon.svg` | App icon | Moon with drone scan beam and ship silhouette |
| `creature-archetypes.svg` | Archetype reference | All 8 creature types with abilities and tips |
| `map-example.svg` | World map visualization | Scan chain connectivity diagram |
| `og-image.svg` | Social media preview | Title with feature badges |
| `splash.svg` | Splash screen | Minimalist title with ship and ARIA init text |

## Still Needed (for distribution)

| File | Purpose | Notes |
|------|---------|-------|
| `icon.png` | App icon for PyInstaller builds | Convert from icon.svg, 512x512 |
| `icon.ico` | Windows app icon | Convert from icon.svg, 256x256 |

## Art Direction Notes

- **Color palette:** Icy blues, cyans, deep purples, with warm amber/magenta accents (matching Rich terminal theme)
- **Mood:** Isolated, atmospheric, alien but beautiful — not horror
- **Style suggestions:** Pixel art, retro sci-fi illustration, or minimalist vector
- **Key visual elements:** Saturn's rings in background, icy terrain, crystalline structures, small drone silhouette, alien creatures (vaguely bioluminescent)
- **Avoid:** Photorealistic renders (clashes with terminal aesthetic), horror imagery, militaristic themes
