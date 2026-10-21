"""
wa_capitalize.py - capitalise the first letter of each sentence, only inside WhatsApp.
Windows only, no pip installs needed.

    python wa_capitalize.py            run it
    python wa_capitalize.py --debug    also print which window/process you are typing in

    Ctrl+Alt+F11   pause / resume
    Ctrl+Alt+F12   quit
"""
import ctypes
import os
import sys
from ctypes import wintypes

from sentence_engine import SentenceTracker

DEBUG = "--debug" in sys.argv

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


# ---------------------------------------------------------------------------
# Win32 plumbing
# ---------------------------------------------------------------------------
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0100, 0x0101, 0x0104, 0x0105
LLKHF_INJECTED = 0x10
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x0002, 0x0004
VK_SHIFT, VK_CONTROL, VK_MENU, VK_CAPITAL = 0x10, 0x11, 0x12, 0x14
VK_LWIN, VK_RWIN, VK_F11, VK_F12 = 0x5B, 0x5C, 0x7A, 0x7B
MODIFIER_VKS = {0x10, 0x11, 0x12, 0x14, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5}

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
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))


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


def send_char(ch):
    """Type one Unicode character via SendInput."""
    def make(flags):
        u = _INPUTUNION()
        u.ki = KEYBDINPUT(0, ord(ch), flags, 0, 0)
        return INPUT(INPUT_KEYBOARD, u)
    events = (INPUT * 2)(make(KEYEVENTF_UNICODE), make(KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
    user32.SendInput(2, events, ctypes.sizeof(INPUT))


# ---------------------------------------------------------------------------
# The hook
# ---------------------------------------------------------------------------
tracker = SentenceTracker()
enabled = True
was_in_target = False
swallowed = set()     # keys whose real key-down we replaced (so we also hide key-up / repeats)


def handle_keydown(kb):
    """Return True to block the real key press."""
    global enabled, was_in_target
    vk = kb.vkCode
    ctrl, alt = key_down(VK_CONTROL), key_down(VK_MENU)
    win = key_down(VK_LWIN) or key_down(VK_RWIN)

    if ctrl and alt and vk == VK_F12:
        user32.PostQuitMessage(0)
        return True
    if ctrl and alt and vk == VK_F11:
        enabled = not enabled
        print("resumed" if enabled else "paused")
        return True
    if not enabled or vk in MODIFIER_VKS:
        return False

    proc, title = foreground_info()
    if not is_target(proc, title):
        was_in_target = False
        return False
    if not was_in_target:                # just switched into WhatsApp
        tracker.reset()
        was_in_target = True

    if vk in swallowed:                  # auto-repeat of a key we already replaced
        return True

    combo = ctrl or alt or win
    shift = key_down(VK_SHIFT)
    caps = bool(user32.GetKeyState(VK_CAPITAL) & 1)
    ch = "" if combo else vk_to_char(vk, kb.scanCode, shift, caps)

    if tracker.feed(vk, ch, combo):
        swallowed.add(vk)
        send_char(ch.upper())
        return True
    return False


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


def main():
    hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, hook_proc, kernel32.GetModuleHandleW(None), 0)
    if not hook:
        raise ctypes.WinError(ctypes.get_last_error())
    print("WhatsApp auto-capitalise running.  Ctrl+Alt+F11 pause, Ctrl+Alt+F12 quit.")
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    user32.UnhookWindowsHookEx(hook)


if __name__ == "__main__":
    main()