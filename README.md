# WhatsApp Capitalise

WhatsApp Capitalise is a small, local background app that capitalizes the first letter of messages and sentences while you type in WhatsApp. It also fixes selected contractions such as `dont` → `don't` and supports your own corrections.

It runs from the Windows notification area or the macOS menu bar. It only changes text when WhatsApp Desktop, or a WhatsApp Web tab in a supported browser, is in front.

## Download and install

Get the latest files from the [GitHub Releases page](https://github.com/k-artik-k/autocapitalizer/releases/latest). Python is not needed to run a release build.

| Your computer | Download this | Then do this |
| --- | --- | --- |
| Windows 10/11 (64-bit) | `WhatsAppCapitalize-Setup-<version>-win64.exe` | Run it to install the app. |
| Windows 10/11 (64-bit), portable | `WhatsAppCapitalize.exe` | Run it directly; no installer. |
| Mac with Apple silicon (M1/M2/M3/M4) | `WhatsAppCapitalize-<version>-macos-arm64.dmg` | Open it and drag the app to Applications. |
| Intel Mac | `WhatsAppCapitalize-<version>-macos-x86_64.dmg` | Open it and drag the app to Applications. |

On a Mac, the **`.app` is the application** and the **`.dmg` is the download/install disk image that contains it**. Download the matching `.dmg`; do not look for a macOS `.exe`.

### Windows

Run the setup file and follow the wizard. It installs for the current user, adds a Start Menu shortcut, optionally adds a desktop shortcut, and includes an uninstaller.

For an unattended install:

```powershell
.\WhatsAppCapitalize-Setup-2.1.0-win64.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
```

### macOS

Open the downloaded DMG, drag `WhatsAppCapitalize.app` to the Applications folder, then open it from Applications.

At first launch, grant the app access under **System Settings → Privacy & Security → Accessibility**. macOS requires this permission for the app to replace a typed character. If you enable it while the app is already open, use **Restart keyboard listener** from the menu.

An unsigned development build can trigger a Gatekeeper or SmartScreen warning. Public releases should be signed; see [release signing](docs/releasing.md#production-signing-and-notarization).

## What it does

- Capitalizes the start of a message and the first letter after a sentence.
- Fixes common contractions, including `im`, `dont`, `cant`, and `youre`.
- Works with WhatsApp Desktop and WhatsApp Web in Chrome, Edge, Firefox, Brave, Opera, and Vivaldi; macOS also supports Safari.
- Keeps settings and custom corrections on your device. It has no network code and does not log or save message content.

Launch it once, then leave it in the notification area/menu bar. The icon is green while active, grey while paused, and red if the keyboard listener needs attention.

| Platform | Pause/resume | Quit |
| --- | --- | --- |
| Windows | `Ctrl + Alt + F11` | `Ctrl + Alt + F12` |
| macOS | `Command + Option + F11` | `Command + Option + F12` |

## Custom corrections

Choose **Edit my corrections** from the app menu. Add one correction per line:

```text
omw = on my way
ill = I'll
```

Saving the file takes effect immediately.

| Platform | Settings folder |
| --- | --- |
| Windows | `%APPDATA%\WhatsAppCapitalize` |
| macOS | `~/Library/Application Support/WhatsAppCapitalize` |

The Windows uninstaller deliberately leaves this folder in place so upgrades retain your settings and corrections.

## Build from source

### Windows

Install Python 3.12+ and [Inno Setup 6](https://jrsoftware.org/isinfo.php), then run:

```powershell
python -m pip install -r requirements\windows.txt
.\scripts\build-windows.ps1 -Version 2.1.0
```

This produces:

```text
dist\windows\WhatsAppCapitalize.exe
dist\windows\WhatsAppCapitalize-Setup-2.1.0-win64.exe
```

To make only the portable EXE (useful when Inno Setup is not installed):

```powershell
.\scripts\build-windows.ps1 -Version 2.1.0 -SkipInstaller
```

### macOS

Build macOS packages on a Mac; they cannot be built on Windows. On the target architecture, run:

```bash
bash scripts/build-macos.sh 2.1.0
```

This creates both the application bundle and DMG:

```text
dist/macos/WhatsAppCapitalize.app
dist/macos/WhatsAppCapitalize-2.1.0-macos-arm64.dmg
```

The default architecture is the architecture of the Mac running the build. For a universal build, use a universal Python installation:

```bash
TARGET_ARCH=universal2 bash scripts/build-macos.sh 2.1.0
```

## Project layout

```text
assets/                 Application icons
docs/                   Release and signing guidance
packaging/windows/      Inno Setup installer definition
requirements/           Windows, macOS, and test dependencies
scripts/                Repeatable release build scripts
src/whatsapp_capitalize/
  sentence_engine.py    Platform-independent typing logic
  windows_app.py        Windows tray and keyboard-hook backend
  macos_app.py          macOS menu-bar and event-tap backend
tests/                  Automated tests for the core behavior
```

## Test and release

Run the local test suite with:

```powershell
python -m pip install -r requirements\dev.txt
python -m pytest -q
```

Pushing to `main` runs the automated checks. Pushing a version tag such as `v2.1.0` creates a GitHub Release containing the Windows EXE, installer, both macOS DMGs, and SHA-256 checksum files. The macOS packages are built on GitHub’s Apple-silicon and Intel runners. See [release automation](docs/releasing.md) for signing, notarization, and checksum verification.
