# Assets — Moon Traveler Terminal

## TUI Screenshots

Auto-generated using the Textual TUI screenshot script. Run it to regenerate after code changes:

```bash
uv run python scripts/tui_screenshots.py
```

Screenshots are saved as `tui-*.svg` files. Old CLI-mode screenshots are archived in `old/`.

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
