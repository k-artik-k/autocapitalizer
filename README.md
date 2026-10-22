# WhatsApp Capitalise

WhatsApp Capitalise is a lightweight background utility that capitalizes the first letter of sentences and fixes selected contractions while you type in WhatsApp. It runs from the Windows system tray or the macOS menu bar and only acts while WhatsApp is the active application or browser tab.

## Features

- Capitalizes the first letter at the start of a message or sentence.
- Corrects common contractions, including `dont` to `don't` and `im` to `I'm`.
- Supports custom corrections through a local text file.
- Works with WhatsApp Desktop and WhatsApp Web in supported browsers.
- Keeps preferences and custom corrections on the local device. It does not send, log, or save message content.

## Supported platforms

| Platform | Package | Supported environments |
| --- | --- | --- |
| Windows 10/11, 64-bit | `WhatsAppCapitalize-Setup-<version>-win64.exe` | WhatsApp Desktop, Chrome, Edge, Firefox, Brave, Opera, Vivaldi |
| macOS, Apple silicon or Intel | `WhatsAppCapitalize-<version>-macos-<architecture>.dmg` | WhatsApp Desktop, Safari, Chrome, Edge, Firefox, Brave, Opera, Vivaldi |

Python is not required to run either packaged release.

## Install on Windows

Download `WhatsAppCapitalize-Setup-<version>-win64.exe` from the project release assets and run it. The wizard installs the app for the current user, creates a Start Menu entry, offers an optional desktop shortcut, and includes an uninstaller.

From PowerShell, run the installer with:

```powershell
Start-Process -FilePath .\WhatsAppCapitalize-Setup-1.0.0-win64.exe -Wait
```

For an unattended installation:

```powershell
.\WhatsAppCapitalize-Setup-1.0.0-win64.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
```

To run the portable release instead of installing it:

```powershell
.\WhatsAppCapitalize.exe
```

## Install on macOS

Download the DMG that matches the target Mac's architecture, open it, and drag `WhatsAppCapitalize.app` to the Applications folder. Then open it from Applications.

The equivalent Terminal commands are:

```bash
hdiutil attach "WhatsAppCapitalize-1.0.0-macos-arm64.dmg"
sudo ditto "/Volumes/WhatsApp Capitalise/WhatsAppCapitalize.app" "/Applications/WhatsAppCapitalize.app"
hdiutil detach "/Volumes/WhatsApp Capitalise"
open -a "/Applications/WhatsAppCapitalize.app"
```

On first launch, grant the app access in **System Settings > Privacy & Security > Accessibility**. This permission is required for macOS to let the app observe and replace the relevant keyboard events. If you grant permission after the app is already running, choose **Restart keyboard listener** from its menu.

Unsigned or ad-hoc-signed development builds can trigger a Gatekeeper warning. Use a Developer ID-signed and notarized DMG for distribution outside your own Mac.

## Using the application

Launch the app and leave it running in the notification area or menu bar. Its icon is green while active, grey while paused, and red if the keyboard listener is unavailable.

The menu lets you:

- Pause or resume processing.
- Enable or disable sentence capitalization.
- Enable or disable contraction fixing.
- Edit custom corrections.
- Open the local settings folder.

Keyboard shortcuts:

| Platform | Pause/resume | Quit |
| --- | --- | --- |
| Windows | `Ctrl + Alt + F11` | `Ctrl + Alt + F12` |
| macOS | `Command + Option + F11` | `Command + Option + F12` |

## Custom corrections and settings

Choose **Edit my corrections** from the menu to create or open `my_corrections.txt`. Add one correction per line:

```text
omw = on my way
ill = I'll
```

Changes take effect when the file is saved; restarting the app is not required.

Settings and custom corrections are stored here:

| Platform | Location |
| --- | --- |
| Windows | `%APPDATA%\WhatsAppCapitalize` |
| macOS | `~/Library/Application Support/WhatsAppCapitalize` |

Uninstalling the application intentionally preserves this folder so personal corrections and preferences are retained when upgrading or reinstalling.

## Build from source

### Windows

Prerequisites:

- Python 3.12 or later
- [Inno Setup 6](https://jrsoftware.org/isinfo.php)

Install the Python dependencies:

```powershell
python -m pip install --upgrade pyinstaller pystray pillow
```

Build the portable executable and installer wizard:

```powershell
.\build-release.ps1 -Version 1.0.0
```

Outputs:

```text
dist\WhatsAppCapitalize.exe
installer\output\WhatsAppCapitalize-Setup-1.0.0-win64.exe
```

### macOS

Build macOS releases on macOS. PyInstaller packages must be produced on their target operating system.

```bash
chmod +x build-macos.sh
./build-macos.sh 1.0.0
```

The script creates an isolated `.venv-macos` environment, installs the dependencies in `requirements-macos.txt`, builds the app bundle, and creates a DMG.

Outputs:

```text
dist/WhatsAppCapitalize.app
release/WhatsAppCapitalize-1.0.0-macos-arm64.dmg
```

The default architecture is the architecture of the Mac performing the build. For a universal build, use a universal Python installation and run:

```bash
TARGET_ARCH=universal2 ./build-macos.sh 1.0.0
```

To sign a release with a Developer ID certificate:

```bash
CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" ./build-macos.sh 1.0.0
```

## Development notes

- `wa_capitalize.py` selects the appropriate platform backend at runtime.
- `windows_app.py` contains the Windows keyboard hook and tray implementation.
- `macos_app.py` contains the macOS Quartz event tap and menu-bar implementation.
- `sentence_engine.py` contains platform-independent capitalization and correction logic.

## License

See the repository license for use and redistribution terms.
