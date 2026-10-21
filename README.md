# WhatsAppCapitalize

Automatically capitalize the first letter of sentences while typing.

WhatsAppCapitalize is a lightweight background utility designed to make everyday typing cleaner and more convenient.

## Features

- **Automatic capitalization:** Capitalizes the first letter of sentences while typing.
- **Background operation:** Runs in the system tray on supported platforms.
- **Lightweight:** Packaged as a standalone application.
- **Easy to use:** Launch the application and type normally.

## Download

Visit the [Releases](../../releases) page and download the appropriate build for your operating system.

### Windows

1. Download `WhatsAppCapitalize-Windows-x64.zip`.
2. Extract the ZIP file.
3. Run `WhatsAppCapitalize.exe`.
4. Keep the `_internal` folder alongside the executable.

### macOS

A macOS build must be generated separately on a Mac. Check the Releases page for an available macOS download.

## System Requirements

- Windows 10 or Windows 11, 64-bit, for the Windows release.
- macOS, for a separately built and tested macOS release.
- Python is not required to run a packaged release.

## Usage

1. Launch the application.
2. Allow it to run in the background.
3. Type normally in supported applications.
4. Access available controls through the system tray or menu bar, depending on the platform and implementation.

## Built With

- Python
- [Pystray](https://github.com/moses-palmer/pystray)
- [Pillow](https://python-pillow.org/)
- [PyInstaller](https://pyinstaller.org/)

## Building from Source

### Prerequisites

Install Python 3 and pip for your operating system.

### Windows

Open PowerShell in the project directory.

Install dependencies:

```powershell
python -m pip install pystray pillow pyinstaller
```

Generate the application icon:

```powershell
python wa_capitalize.py --make-icon
```

Build the application:

```powershell
python -m PyInstaller --noconsole --onedir --icon icon.ico --name WhatsAppCapitalize wa_capitalize.py
```

The output will be available in:

```text
dist/WhatsAppCapitalize/
```

### macOS

Open Terminal in the project directory.

Install dependencies:

```bash
python3 -m pip install pystray pillow pyinstaller
```

Build the application:

```bash
python3 -m PyInstaller --noconsole --onedir --name WhatsAppCapitalize wa_capitalize.py
```

The output will be available in:

```text
dist/WhatsAppCapitalize/
```

**Note:** The macOS build must be created and tested on macOS. The Windows-specific `icon.ico` option is omitted here. macOS permissions, accessibility requirements, and menu bar behavior may require additional implementation and configuration.

## License

See the repository's license file for usage and redistribution terms.
