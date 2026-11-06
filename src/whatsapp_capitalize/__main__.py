"""Cross-platform entry point for WhatsApp Capitalise."""
import importlib
from pathlib import Path
import sys


if __package__ in (None, ""):
    # Also support launching this source file directly from the Windows startup
    # registry entry used during development.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    """Load only the backend for the operating system currently in use."""
    if sys.platform == "win32":
        module_name = "whatsapp_capitalize.windows_app"
    elif sys.platform == "darwin":
        module_name = "whatsapp_capitalize.macos_app"
    else:
        raise SystemExit("WhatsApp Capitalise currently supports Windows and macOS only.")

    importlib.import_module(module_name).main()


if __name__ == "__main__":
    main()
