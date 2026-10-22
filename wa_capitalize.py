"""Cross-platform entry point for WhatsApp Capitalise.

The platform backend is loaded lazily so a Windows build never needs macOS
frameworks, and a macOS build never imports Win32-only modules.
"""
import importlib
import sys


def main():
    if sys.platform == "win32":
        module_name = "windows_app"
    elif sys.platform == "darwin":
        module_name = "macos_app"
    else:
        raise SystemExit("WhatsApp Capitalise currently supports Windows and macOS only.")

    importlib.import_module(module_name).main()


if __name__ == "__main__":
    main()
