# Steam Distribution

## Prerequisites

1. Create a Steamworks developer account at https://partner.steamgames.com
2. Pay the $100 app registration fee
3. Create an App in the Steamworks dashboard
4. Download SteamCMD from https://developer.valvesoftware.com/wiki/SteamCMD

## Setup

1. Replace the placeholder App ID (`0000000`) and Depot IDs in `app_build.vdf` with your actual IDs from Steamworks
2. Build the game for all platforms:
   ```bash
   python scripts/build_release.py --platform all
   ```
3. Organize the output:
   ```
   content/
     windows/   <- copy from dist/moon-traveler-windows/
     macos/     <- copy from dist/moon-traveler-macos/
     linux/     <- copy from dist/moon-traveler-linux/
   ```

## Upload

```bash
steamcmd +login <username> +run_app_build ../packaging/steam/app_build.vdf +quit
```

## Steam Store Page

Required assets for the Steam store page:
- **Header Capsule**: 460x215 (use `assets/banner.svg` as base, export to PNG)
- **Small Capsule**: 231x87
- **Large Capsule**: 467x181
- **Hero**: 1920x620
- **Library Hero**: 3840x1240
- **Logo**: 1280x720

The game's SVG banner and screenshots can be converted to PNG at the required dimensions.

## Launch Options

In Steamworks, set the launch option to the platform-specific executable:
- **Windows**: `moon-traveler.exe`
- **macOS**: `moon-traveler`
- **Linux**: `moon-traveler`

Mark as "Launch in Terminal" since this is a CLI game.
