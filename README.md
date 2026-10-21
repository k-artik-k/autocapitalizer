# WhatsAppCapitalize

Automatically capitalize the first letter of sentences while typing on Windows.

WhatsAppCapitalize runs in the system tray and helps make your typing cleaner without manually correcting every sentence.

## Features

- **Automatic capitalization:** Capitalizes the first letter of sentences while typing.
- **System tray integration:** Runs in the background without keeping a console window open.
- **Lightweight:** Built with Python and packaged as a standalone Windows application.
- **Simple operation:** Launch the application and continue typing as usual.

## Download

1. Open the [Releases](../../releases) page.
2. Download `WhatsAppCapitalize-Windows-x64.zip` from the latest release.
3. Extract the ZIP file.
4. Run `WhatsAppCapitalize.exe`.

Keep the `_internal` folder alongside the executable. It contains required application dependencies.

## System Requirements

- Windows 10 or Windows 11, 64-bit
- No separate Python installation required for the packaged release

## Usage

1. Launch `WhatsAppCapitalize.exe`.
2. Allow the application to run in the background.
3. Type normally in supported applications.
4. Use the system tray icon to access the application's available controls.

## Built With

- Python
- [Pystray](https://github.com/moses-palmer/pystray)
- [Pillow](https://python-pillow.org/)
- [PyInstaller](https://pyinstaller.org/)

## Building from Source

Install the dependencies:

```powershell
python -m pip install pystray pillow pyinstaller
```

Generate the application icon:

```powershell
python wa_capitalize.py --make-icon
```

Build the Windows application:

```powershell
python -m PyInstaller --noconsole --onedir --icon icon.ico --name WhatsAppCapitalize wa_capitalize.py
```

The packaged application will be available in:

```text
dist/WhatsAppCapitalize/
```

## License

See the repository's license file for usage and redistribution terms.
