"""
wa_capitalize.py - WhatsApp helper (Windows): capital letter at the start of each sentence,
and contraction fixes (lets -> let's, dont -> don't, i -> I ...). Lives in the system tray.

    pythonw wa_capitalize.py            run silently (no console window)
    python  wa_capitalize.py --debug    run with a console and print which window you are typing in
    python  wa_capitalize.py --make-icon    write icon.ico (for building the .exe) and exit

Left-click the tray icon = pause / resume.  Right-click = menu.
Hotkeys: Ctrl+Alt+F11 pause/resume     Ctrl+Alt+F12 quit

Needs:  pip install pystray pillow
Privacy: no network code, nothing you type is logged or saved. The only thing kept (in memory)
is the current word, and it is wiped when you leave WhatsApp or pause.
"""
import ctypes
import os
import re
import shutil
import sys
import threading
import winreg
from ctypes import wintypes

import pystray
from PIL import Image, ImageDraw

import autocorrect
import settings as settings_store
from sentence_engine import Typist, VK_BACK

DEBUG = "--debug" in sys.argv
APP_NAME = "WhatsAppCapitalize"
TRAY_TITLE = "WhatsApp Capitalise"

# ---------------------------------------------------------------------------
# What counts as "WhatsApp"  (edit these after running with --debug)
# ---------------------------------------------------------------------------
WHATSAPP_PROCESSES = {"whatsapp.exe", "whatsapp.root.exe"}          # desktop app
TITLE_MATCH_PROCESSES = {                                           # WhatsApp Web / UWP frame
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
    "opera.exe", "vivaldi.exe", "applicationframehost.exe",
}


def web_title_ok(title):
    """'WhatsApp', '(3) WhatsApp - Google Chrome', 'WhatsApp and 1 more page - ...' but NOT
    'Is WhatsApp safe? - Google Chrome' or 'whatsappfake.com'."""
    t = re.sub(r"^\(\d+\)\s*", "", title.lower().strip())     # drop unread-count prefix
    if not t.startswith("whatsapp"):
        return False
    rest = t[len("whatsapp"):]
    return rest == "" or rest[:3] in (" - ", " \u2014 ", " \u2013 ") or rest.startswith(" and ")


def is_target(proc, title):
    if proc in WHATSAPP_PROCESSES:
        return True
    return proc in TITLE_MATCH_PROCESSES and web_title_ok(title)


# Your own data lives in %APPDATA%\WhatsAppCapitalize (per-user, always writable).
DATA_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "WhatsAppCapitalize")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
CORRECTIONS_PATH = os.path.join(DATA_DIR, "my_corrections.txt")


def program_dir():
    base = sys.executable if getattr(sys, "frozen", False) else __file__
    return os.path.dirname(os.path.abspath(base))


# ---------------------------------------------------------------------------
# Win32 plumbing
# ---------------------------------------------------------------------------
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WM_QUIT, WM_APP_RESTART = 0x0012, 0x8001
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0100, 0x0101, 0x0104, 0x0105
LLKHF_INJECTED = 0x10
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x0002, 0x0004
VK_SHIFT, VK_CONTROL, VK_MENU, VK_CAPITAL = 0x10, 0x11, 0x12, 0x14
VK_LWIN, VK_RWIN, VK_F11, VK_F12 = 0x5B, 0x5C, 0x7A, 0x7B
MODIFIER_VKS = {0x10, 0x11, 0x12, 0x14, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5}
ERROR_ALREADY_EXISTS = 183
MAGIC = 0x57414341          # tags the keys WE inject, so we never react to them (or to nobody else's)

LRESULT = ctypes.c_ssize_t
ULONG_PTR = wintypes.WPARAM
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HMODULE, wintypes.DWORD)
user32.SetWindowsHookExW.restype = wintypes.HANDLE
user32.CallNextHookEx.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = (wintypes.HANDLE,)
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetKeyState.argtypes = (ctypes.c_int,)
user32.GetKeyState.restype = ctypes.c_short
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetKeyboardLayout.argtypes = (wintypes.DWORD,)
user32.GetKeyboardLayout.restype = wintypes.HANDLE
user32.ToUnicodeEx.argtypes = (wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ubyte),
                               wintypes.LPWSTR, ctypes.c_int, wintypes.UINT, wintypes.HANDLE)
user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.CreateMutexW.restype = wintypes.HANDLE


def key_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def process_name(pid):
    """Looked up fresh every time (no cache), so a re-used process id can never be mistaken for WhatsApp."""
    if not pid:
        return ""
    handle = kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(handle)
    return ""


_last_seen = None


def foreground_info():
    global _last_seen
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    proc = process_name(pid.value)
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    if DEBUG and (proc, buf.value) != _last_seen:
        _last_seen = (proc, buf.value)
        # titles only matter (and are only shown) for browsers / frame hosts, cut short
        shown = buf.value[:40] if proc in TITLE_MATCH_PROCESSES else "-"
        print(f"[focus] process={proc!r} title={shown!r} target={is_target(proc, buf.value)}")
    return proc, buf.value


def vk_to_char(vk, scan, shift, caps):
    """The character this key would type right now, respecting layout, Shift and Caps."""
    state = (ctypes.c_ubyte * 256)()
    if shift:
        state[VK_SHIFT] = 0x80
    if caps:
        state[VK_CAPITAL] = 0x01
    hwnd = user32.GetForegroundWindow()
    layout = user32.GetKeyboardLayout(user32.GetWindowThreadProcessId(hwnd, None))
    buf = ctypes.create_unicode_buffer(8)
    n = user32.ToUnicodeEx(vk, scan, state, buf, len(buf), 0x4, layout)  # 0x4 = don't alter key state
    return buf.value[:1] if n >= 1 else ""


def _ki(vk=0, scan=0, flags=0):
    u = _INPUTUNION()
    u.ki = KEYBDINPUT(vk, scan, flags, 0, MAGIC)
    return INPUT(INPUT_KEYBOARD, u)


def send_sequence(backspaces=0, text="", vk_after=0):
    """Press Backspace N times, type `text`, then tap one more key - all in ONE SendInput call
    so nothing the user types can slip in between."""
    events = []
    for _ in range(max(0, min(backspaces, 64))):
        events += [_ki(vk=VK_BACK), _ki(vk=VK_BACK, flags=KEYEVENTF_KEYUP)]
    if text:
        data = text.encode("utf-16-le")                      # emoji = two UTF-16 units
        for i in range(0, len(data), 2):
            unit = int.from_bytes(data[i:i + 2], "little")
            events += [_ki(scan=unit, flags=KEYEVENTF_UNICODE),
                       _ki(scan=unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    if vk_after:
        events += [_ki(vk=vk_after), _ki(vk=vk_after, flags=KEYEVENTF_KEYUP)]
    if events:
        batch = (INPUT * len(events))(*events)
        user32.SendInput(len(events), batch, ctypes.sizeof(INPUT))


# ---------------------------------------------------------------------------
# State shared between the hook thread and the tray thread
# ---------------------------------------------------------------------------
typist = Typist()
tray = None
enabled = True            # master pause switch (always starts ON)
hook_ok = False           # is the keyboard hook installed right now?
in_target = False         # is WhatsApp the focused window?
hook_tid = 0
settings = dict(settings_store.DEFAULTS)


# ---------------------------------------------------------------------------
# Tray icon
# ---------------------------------------------------------------------------
_icons = {}


def make_icon(state="on", size=64):
    """state: on (green A) / paused (grey bars) / error (red !). Drawn big, shrunk for smooth edges."""
    key = (state, size)
    if key in _icons:
        return _icons[key]
    S = 256
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    colour = {"on": (37, 211, 102), "paused": (120, 124, 130), "error": (222, 62, 62)}[state]
    white = (255, 255, 255, 255)
    d.rounded_rectangle((8, 8, S - 8, S - 8), radius=56, fill=colour + (255,))
    if state == "on":
        d.line([(62, 200), (128, 56), (194, 200)], fill=white, width=30, joint="curve")
        d.line([(88, 152), (168, 152)], fill=white, width=24)
    elif state == "paused":
        d.rectangle((84, 64, 116, 192), fill=white)
        d.rectangle((140, 64, 172, 192), fill=white)
    else:
        d.rounded_rectangle((112, 56, 144, 150), radius=14, fill=white)
        d.ellipse((108, 172, 148, 212), fill=white)
    _icons[key] = img.resize((size, size), Image.LANCZOS)
    return _icons[key]


def tray_state():
    if not hook_ok:
        return "error"
    return "on" if enabled else "paused"


def status_text(_item=None):
    if not hook_ok:
        return "Keyboard hook not running"
    if not enabled:
        return "Paused"
    return "Active in WhatsApp" if in_target else "On - waiting for WhatsApp"


def refresh_tray():
    if not tray:
        return
    try:
        state = tray_state()
        tray.icon = make_icon(state)
        tray.title = f"{TRAY_TITLE} - {status_text()}"
        tray.update_menu()
    except Exception as exc:
        print("tray refresh failed:", exc)


def notify(message):
    try:
        if tray:
            tray.notify(message, TRAY_TITLE)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Menu actions
# ---------------------------------------------------------------------------
def set_enabled(value):
    global enabled
    enabled = value
    refresh_tray()


def toggle_enabled(*_):
    set_enabled(not enabled)


def _save_settings():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        settings_store.save(SETTINGS_PATH, settings)
    except OSError as exc:
        print("could not save settings:", exc)


def toggle_capitalize(*_):
    settings["capitalize"] = not settings["capitalize"]
    typist.capitalize = settings["capitalize"]
    _save_settings()
    refresh_tray()


def toggle_fix_words(*_):
    settings["fix_words"] = not settings["fix_words"]
    typist.fix_words = settings["fix_words"]
    _save_settings()
    refresh_tray()


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def startup_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    return f'"{pythonw}" "{os.path.abspath(__file__)}"'


def startup_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except OSError:
        return False


def toggle_startup(*_):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if startup_enabled():
                winreg.DeleteValue(key, APP_NAME)
            else:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, startup_command())
    except OSError as exc:
        notify(f"Could not change startup setting: {exc}")
    refresh_tray()


def open_corrections(*_):
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CORRECTIONS_PATH):
        with open(CORRECTIONS_PATH, "w", encoding="utf-8") as f:
            f.write("# One per line:   what you type = what it becomes\n"
                    "# Keys: letters only. Lines starting with # are ignored.\n"
                    "# Save the file and it works immediately (no restart).\n"
                    "# omw = on my way\n"
                    "# ill = I'll\n")
    os.startfile(CORRECTIONS_PATH)


def open_data_folder(*_):
    os.makedirs(DATA_DIR, exist_ok=True)
    os.startfile(DATA_DIR)


def restart_hook(*_):
    if hook_tid:
        user32.PostThreadMessageW(hook_tid, WM_APP_RESTART, 0, 0)


def quit_app(*_):
    if hook_tid:
        user32.PostThreadMessageW(hook_tid, WM_QUIT, 0, 0)
    if tray:
        tray.stop()


def build_menu():
    return pystray.Menu(
        pystray.MenuItem(status_text, lambda *_: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Enabled", toggle_enabled, checked=lambda item: enabled, default=True),
        pystray.MenuItem("Capital at start of sentences", toggle_capitalize,
                         checked=lambda item: settings["capitalize"]),
        pystray.MenuItem("Fix words (let's, don't, I'm...)", toggle_fix_words,
                         checked=lambda item: settings["fix_words"]),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Start with Windows", toggle_startup, checked=lambda item: startup_enabled()),
        pystray.MenuItem("Edit my corrections...", open_corrections),
        pystray.MenuItem("Open settings folder", open_data_folder),
        pystray.MenuItem("Restart keyboard hook", restart_hook),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_app),
    )


# ---------------------------------------------------------------------------
# The keyboard hook (runs in its own thread; keep it FAST and never touch the tray from here)
# ---------------------------------------------------------------------------
swallowed = set()     # keys whose real key-down we replaced (so we also hide key-up / repeats)


def leave_target():
    """Called whenever the active window is not WhatsApp (or we are paused): forget typed text."""
    global in_target
    if in_target:
        typist.lose_track()
        in_target = False
        threading.Thread(target=refresh_tray, daemon=True).start()


def handle_keydown(kb):
    """Return True to block the real key press."""
    global in_target
    vk = kb.vkCode
    ctrl, alt = key_down(VK_CONTROL), key_down(VK_MENU)
    win = key_down(VK_LWIN) or key_down(VK_RWIN)

    if ctrl and alt and vk == VK_F12:
        threading.Thread(target=quit_app, daemon=True).start()
        return True
    if ctrl and alt and vk == VK_F11:
        threading.Thread(target=toggle_enabled, daemon=True).start()
        return True
    if not enabled:
        leave_target()
        return False
    if vk in MODIFIER_VKS:
        return False

    proc, title = foreground_info()
    if not is_target(proc, title):
        leave_target()
        return False
    if not in_target:                    # just switched into WhatsApp
        typist.reset()
        in_target = True
        threading.Thread(target=refresh_tray, daemon=True).start()

    if vk in swallowed:                  # auto-repeat of a key we already replaced
        return True

    combo = ctrl or alt or win
    shift = key_down(VK_SHIFT)
    caps = bool(user32.GetKeyState(VK_CAPITAL) & 1)
    ch = "" if combo else vk_to_char(vk, kb.scanCode, shift, caps)

    plan = typist.process(vk, ch, combo)
    if plan is None:
        return False
    swallowed.add(vk)
    send_sequence(plan.backspaces, plan.text, plan.vk_after)
    return True


@HOOKPROC
def hook_proc(n_code, w_param, l_param):
    try:
        if n_code == 0:
            kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if kb.flags & LLKHF_INJECTED:
                # Our own keys pass untouched. Keys injected by OTHER programs (text expanders,
                # password managers, voice typing...) mean we no longer know what is on screen.
                if kb.dwExtraInfo != MAGIC and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN) and in_target:
                    typist.lose_track()
            elif w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                if handle_keydown(kb):
                    return 1
            elif w_param in (WM_KEYUP, WM_SYSKEYUP) and kb.vkCode in swallowed:
                swallowed.discard(kb.vkCode)
                return 1
    except Exception as exc:                             # never break the user's typing
        print("error:", exc)
    return user32.CallNextHookEx(None, n_code, w_param, l_param)


def _install_hook():
    return user32.SetWindowsHookExW(WH_KEYBOARD_LL, hook_proc, kernel32.GetModuleHandleW(None), 0)


def _set_hook_ok(value):
    global hook_ok
    hook_ok = value
    if tray:
        threading.Thread(target=refresh_tray, daemon=True).start()
        if not value:
            notify("The keyboard hook could not start. Use 'Restart keyboard hook' in the tray menu.")


def hook_thread():
    """The hook needs its own thread with a message loop."""
    global hook_tid
    hook_tid = kernel32.GetCurrentThreadId()
    msg = wintypes.MSG()
    user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)    # make sure this thread has a queue
    hook = _install_hook()
    _set_hook_ok(bool(hook))
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == WM_APP_RESTART:
            if hook:
                user32.UnhookWindowsHookEx(hook)
            typist.lose_track()
            swallowed.clear()
            hook = _install_hook()
            _set_hook_ok(bool(hook))
            continue
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    if hook:
        user32.UnhookWindowsHookEx(hook)
    _set_hook_ok(False)


def _migrate_old_corrections():
    """Earlier versions kept my_corrections.txt next to the program; move it to the data folder."""
    old = os.path.join(program_dir(), "my_corrections.txt")
    if os.path.exists(old) and not os.path.exists(CORRECTIONS_PATH):
        try:
            shutil.copyfile(old, CORRECTIONS_PATH)
        except OSError:
            pass


def main():
    global tray, settings
    if "--make-icon" in sys.argv:
        make_icon("on", 256).save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                                    (64, 64), (128, 128), (256, 256)])
        print("wrote icon.ico")
        return

    mutex = kernel32.CreateMutexW(None, False, "Local\\WhatsAppCapitalizeSingleton")
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:   # already running: don't double-type
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    _migrate_old_corrections()
    autocorrect.set_folder(DATA_DIR)
    settings = settings_store.load(SETTINGS_PATH)
    typist.capitalize, typist.fix_words = settings["capitalize"], settings["fix_words"]

    threading.Thread(target=hook_thread, daemon=True).start()

    tray = pystray.Icon(APP_NAME, make_icon("error"), TRAY_TITLE, build_menu())

    def setup(icon):
        icon.visible = True
        refresh_tray()

    tray.run(setup)            # blocks until Quit
    del mutex


if __name__ == "__main__":
    main()