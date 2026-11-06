"""
autocorrect.py - contraction / "i" fixes, plus your own list from my_corrections.txt.

Only whole words are touched, and only when you finish them (space, punctuation, Enter).
Words containing digits, dots or @ (links, emails) are never touched.

The replacement text is typed into your chats, so the custom file is treated as untrusted:
size-capped, entry-capped, keys must be plain letters, values must be short printable text.
"""
import os
import re

DEFAULTS = {
    # I
    "i": "I", "im": "I'm", "ive": "I've",
    "i'm": "I'm", "i've": "I've", "i'll": "I'll", "i'd": "I'd",
    # negatives
    "dont": "don't", "doesnt": "doesn't", "didnt": "didn't", "cant": "can't",
    "wont": "won't", "isnt": "isn't", "arent": "aren't", "wasnt": "wasn't",
    "werent": "weren't", "hasnt": "hasn't", "havent": "haven't", "hadnt": "hadn't",
    "wouldnt": "wouldn't", "couldnt": "couldn't", "shouldnt": "shouldn't",
    # have
    "wouldve": "would've", "couldve": "could've", "shouldve": "should've",
    "weve": "we've", "youve": "you've", "theyve": "they've",
    # is / are / will
    "lets": "let's", "thats": "that's", "whats": "what's", "heres": "here's",
    "theres": "there's", "wheres": "where's", "hows": "how's", "whos": "who's",
    "hes": "he's", "shes": "she's", "youre": "you're", "theyre": "they're",
    "youll": "you'll", "theyll": "they'll", "itll": "it'll",
}
# Deliberately NOT included because they are real words: ill, id, hell, well, were, its, wed, shed.
# Add them yourself in my_corrections.txt if you want them.

MAX_FILE_BYTES = 64 * 1024
MAX_ENTRIES = 500
MAX_VALUE_LEN = 120
KEY_RE = re.compile(r"^[a-z']{1,40}$")
WORD_RE = re.compile(r"^([\"'(\[]*)([A-Za-z']+)$")

CORRECTIONS = dict(DEFAULTS)
_path = None
_mtime = None


def clean_entry(key, value):
    """Return a safe (key, value) pair, or None if the entry should be ignored."""
    key, value = key.strip().lower(), value.strip()
    if not KEY_RE.match(key):
        return None
    if not (1 <= len(value) <= MAX_VALUE_LEN) or not value.isprintable():
        return None        # also rejects tabs, newlines, zero-width and other invisible characters
    return key, value


def set_folder(folder):
    """Look for my_corrections.txt in this folder (re-read automatically when you save it)."""
    global _path
    _path = os.path.join(folder, "my_corrections.txt")
    _reload(force=True)


def _reload(force=False):
    global _mtime
    if not _path:
        return
    try:
        mtime = os.path.getmtime(_path)
    except OSError:
        mtime = None
    if not force and mtime == _mtime:
        return
    _mtime = mtime
    CORRECTIONS.clear()
    CORRECTIONS.update(DEFAULTS)
    if mtime is None:
        return
    try:
        if os.path.getsize(_path) > MAX_FILE_BYTES:
            return
        with open(_path, encoding="utf-8") as f:
            added = 0
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                entry = clean_entry(key, value)
                if entry:
                    CORRECTIONS[entry[0]] = entry[1]
                    added += 1
                    if added >= MAX_ENTRIES:
                        break
    except (OSError, UnicodeDecodeError):
        CORRECTIONS.clear()
        CORRECTIONS.update(DEFAULTS)


def fix_for(word):
    """word = everything typed since the last space. Returns (prefix, original, replacement) or None."""
    _reload()
    m = WORD_RE.match(word)
    if not m:
        return None
    prefix, core = m.groups()
    target = CORRECTIONS.get(core.lower())
    if not target:
        return None
    if len(core) > 1 and core.isupper():
        target = target.upper()
    elif core[0].isupper():
        target = target[0].upper() + target[1:]
    if target == core:
        return None
    return prefix, core, target