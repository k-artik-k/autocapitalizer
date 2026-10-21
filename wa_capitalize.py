"""
wa_capitalize.py - WhatsApp helper (Windows): capital letter at the start of each sentence,
and contraction fixes (lets -> let's, dont -> don't, i -> I ...). Lives in the system tray.

    pythonw wa_capitalize.py            run silently (no console window)
    python  wa_capitalize.py --debug    run with a console and print which window you are typing in

Tray icon menu: pause/resume, Start with Windows, edit your own corrections, Quit.
Hotkeys:        Ctrl+Alt+F11 pause/resume     Ctrl+Alt+F12 quit

Needs:  pip install pystray pillow
"""
import ctypes
import os
import sys
import threading
import winreg
from ctypes import wintypes

import pystray
from PIL import Image, ImageDraw

import autocorrect
from sentence_engine import Typist, VK_BACK

DEBUG = "--debug" in sys.argv
APP_NAME = "WhatsAppCapitalize"

# ---------------------------------------------------------------------------
# What counts as "WhatsApp"  (edit these after running with --debug)
# ---------------------------------------------------------------------------
WHATSAPP_PROCESSES = {"whatsapp.exe", "whatsapp.root.exe"}          # desktop app
TITLE_MATCH_PROCESSES = {                                           # WhatsApp Web / UWP frame
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
    "opera.exe", "vivaldi.exe", "applicationframehost.exe",
}


def is_target(proc, title):
    if proc in WHATSAPP_PROCESSES:
        return True
    if proc in TITLE_MATCH_PROCESSES:
        # Web titles look like "WhatsApp - Google Chrome" or "(3) WhatsApp - ..."
        return title.lower().lstrip("(0123456789) ").startswith("whatsapp")
    return False


def app_dir():
    base = sys.executable if getattr(sys, "frozen", False) else __file__
    return os.path.dirname(os.path.abspath(base))


# ---------------------------------------------------------------------------
# Win32 plumbing
# ---------------------------------------------------------------------------
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WM_QUIT = 0x0012
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0100, 0x0101, 0x0104, 0x0105
LLKHF_INJECTED = 0x10
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x0002, 0x0004
VK_SHIFT, VK_CONTROL, VK_MENU, VK_CAPITAL = 0x10, 0x11, 0x12, 0x14
VK_LWIN, VK_RWIN, VK_F11, VK_F12 = 0x5B, 0x5C, 0x7A, 0x7B
MODIFIER_VKS = {0x10, 0x11, 0x12, 0x14, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5}
ERROR_ALREADY_EXISTS = 183

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


_proc_cache = {}


def process_name(pid):
    cached = _proc_cache.get(pid)
    if cached:
        return cached
    handle = kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            name = os.path.basename(buf.value).lower()
            _proc_cache[pid] = name
            return name
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
        print(f"[focus] process={proc!r} title={buf.value!r} target={is_target(proc, buf.value)}")
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
    u.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    return INPUT(INPUT_KEYBOARD, u)


def send_sequence(backspaces=0, text="", vk_after=0):
    """Press Backspace N times, type `text`, then tap one more key - all in ONE SendInput call
    so nothing the user types can slip in between."""
    events = []
    for _ in range(backspaces):
        events += [_ki(vk=VK_BACK), _ki(vk=VK_BACK, flags=KEYEVENTF_KEYUP)]
    for ch in text:
        events += [_ki(scan=ord(ch), flags=KEYEVENTF_UNICODE),
                   _ki(scan=ord(ch), flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    if vk_after:
        events += [_ki(vk=vk_after), _ki(vk=vk_after, flags=KEYEVENTF_KEYUP)]
    if events:
        batch = (INPUT * len(events))(*events)
        user32.SendInput(len(events), batch, ctypes.sizeof(INPUT))


# ---------------------------------------------------------------------------
# Tray icon, enable/disable, autostart
# ---------------------------------------------------------------------------
tray = None
enabled = True
hook_tid = 0

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def make_icon(on=True):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, 62, 62), radius=14, fill=(37, 211, 102, 255) if on else (128, 128, 128, 255))
    d.line([(17, 50), (32, 13), (47, 50)], fill="white", width=6, joint="curve")   # an "A"
    d.line([(23, 38), (41, 38)], fill="white", width=5)
    return img


def set_enabled(value):
    global enabled
    enabled = value
    if tray:
        tray.icon = make_icon(value)
        tray.title = "WhatsApp Capitalise - " + ("on" if value else "paused")
    print("resumed" if value else "paused")


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
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if startup_enabled():
            winreg.DeleteValue(key, APP_NAME)
        else:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, startup_command())


def open_corrections(*_):
    path = os.path.join(app_dir(), "my_corrections.txt")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("# One per line:   what you type = what it becomes\n"
                    "# Lines starting with # are ignored. Save the file and it works immediately.\n"
                    "# omw = on my way\n"
                    "# ill = I'll\n")
    os.startfile(path)


def quit_app(*_):
    if hook_tid:
        user32.PostThreadMessageW(hook_tid, WM_QUIT, 0, 0)
    if tray:
        tray.stop()


# ---------------------------------------------------------------------------
# The hook
# ---------------------------------------------------------------------------
typist = Typist()
was_in_target = False
swallowed = set()     # keys whose real key-down we replaced (so we also hide key-up / repeats)


def handle_keydown(kb):
    """Return True to block the real key press."""
    global was_in_target
    vk = kb.vkCode
    ctrl, alt = key_down(VK_CONTROL), key_down(VK_MENU)
    win = key_down(VK_LWIN) or key_down(VK_RWIN)

    if ctrl and alt and vk == VK_F12:
        threading.Thread(target=quit_app, daemon=True).start()
        return True
    if ctrl and alt and vk == VK_F11:
        set_enabled(not enabled)
        return True
    if not enabled or vk in MODIFIER_VKS:
        return False

    proc, title = foreground_info()
    if not is_target(proc, title):
        was_in_target = False
        return False
    if not was_in_target:                # just switched into WhatsApp
        typist.reset()
        was_in_target = True

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
            if not (kb.flags & LLKHF_INJECTED):          # ignore our own injected keys
                if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    if handle_keydown(kb):
                        return 1
                elif w_param in (WM_KEYUP, WM_SYSKEYUP) and kb.vkCode in swallowed:
                    swallowed.discard(kb.vkCode)
                    return 1
    except Exception as exc:                             # never break the user's typing
        print("error:", exc)
    return user32.CallNextHookEx(None, n_code, w_param, l_param)


def hook_thread():
    """The keyboard hook needs its own thread with a message loop."""
    global hook_tid
    hook_tid = kernel32.GetCurrentThreadId()
    hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, hook_proc, kernel32.GetModuleHandleW(None), 0)
    if not hook:
        print("could not install keyboard hook:", ctypes.WinError(ctypes.get_last_error()))
        quit_app()
        return
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    user32.UnhookWindowsHookEx(hook)


def main():
    global tray
    mutex = kernel32.CreateMutexW(None, False, "Local\\WhatsAppCapitalizeSingleton")
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:   # already running: don't double-type
        return
    autocorrect.set_folder(app_dir())
    threading.Thread(target=hook_thread, daemon=True).start()

    menu = pystray.Menu(
        pystray.MenuItem("Capitalise + fix words", lambda *_: set_enabled(not enabled),
                         checked=lambda item: enabled, default=True),
        pystray.MenuItem("Start with Windows", toggle_startup, checked=lambda item: startup_enabled()),
        pystray.MenuItem("Edit my corrections...", open_corrections),
        pystray.MenuItem("Quit", quit_app),
    )
    tray = pystray.Icon(APP_NAME, make_icon(True), "WhatsApp Capitalise - on", menu)
    tray.run()                 # blocks until Quit
    del mutex


if __name__ == "__main__":
    main()