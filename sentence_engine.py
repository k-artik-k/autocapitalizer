"""
sentence_engine.py - decides WHAT to type: sentence-start capitals and contraction fixes.

Pure logic, no Windows calls. The Windows layer feeds it one key at a time and
carries out the returned Plan.
"""
from dataclasses import dataclass

import autocorrect

NEUTRAL, START, AFTER_PUNCT = "neutral", "start", "after_punct"

VK_BACK, VK_RETURN = 0x08, 0x0D

# Tab, Esc, PgUp, PgDn, End, Home, arrows, Delete: the caret may have jumped,
# so we no longer know where we are in the sentence.
NAV_KEYS = {0x09, 0x1B, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2E}

# A period after these does NOT end a sentence.
ABBREVIATIONS = {"e.g.", "i.e.", "mr.", "mrs.", "ms.", "dr.", "vs.", "approx."}

OPENERS = set("\"'([{\u00bf\u00a1")   # allowed between ". " and the first letter
CLOSERS = set("\"')]}")               # allowed between "." and the space
BOUNDARY_CHARS = set(" .,!?;:")       # finishing a word with one of these triggers autocorrect


@dataclass
class Fix:
    prefix: str
    original: str
    replacement: str


@dataclass
class Plan:
    """Swallow the real key and instead: press Backspace N times, type text, then press vk_after."""
    backspaces: int = 0
    text: str = ""
    vk_after: int = 0


class SentenceTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        """Call when focus enters the target app: assume an empty message box."""
        self.state = START
        self.hard = True          # True = start of box/line, False = after ". "
        self.word = ""            # what is on screen since the last space
        self.seg_len = 0          # chars typed since the last capital we applied
        self.seg_kind = True      # the 'hard' flag to restore if all of them get deleted
        self.last_fix = None      # the autocorrect we just did (Backspace undoes it)
        self.blocked_word = ""    # a word the user un-corrected; don't fix it again

    def apply_fix(self, n, replacement):
        """The last n chars of the current word were replaced on screen."""
        new = self.word[:-n] + replacement
        self.word = new.rsplit(" ", 1)[-1]
        if self.seg_len:
            self.seg_len += len(replacement) - n

    def undo_fix(self):
        fix, self.last_fix = self.last_fix, None
        if fix:
            self.word = fix.prefix + fix.original
            self.blocked_word = self.word
            self.state = NEUTRAL
            self.seg_len = 0

    def feed(self, vk, ch, combo=False, capitalize=True):
        """
        Process one key press.
        vk    - virtual key code
        ch    - the character this key produces right now ("" if none)
        combo - True if Ctrl/Alt/Win is held (shortcut, not typing)
        capitalize - False = still track sentences but never ask for an uppercase letter
        Returns True if `ch` should be typed as an uppercase letter instead.
        """
        self.last_fix = None

        if combo or vk in NAV_KEYS:
            self.state, self.word, self.seg_len, self.blocked_word = NEUTRAL, "", 0, ""
            return False

        if vk == VK_RETURN:                       # message sent, or Shift+Enter newline
            self.state, self.hard, self.word, self.seg_len = START, True, "", 0
            self.blocked_word = ""
            return False

        if vk == VK_BACK:
            self.word = self.word[:-1]
            if self.seg_len:
                self.seg_len -= 1
                if self.seg_len == 0:             # deleted everything since our capital
                    self.state, self.hard = START, self.seg_kind
                else:
                    self.state = NEUTRAL
            elif not (self.state == START and self.hard):
                self.state = NEUTRAL
            return False

        if not ch or not ch.isprintable():
            return False

        if self.seg_len:
            self.seg_len += 1

        if ch == " ":
            if self.state == AFTER_PUNCT:
                self.state, self.hard = START, False
            self.word, self.blocked_word = "", ""
            return False

        if ch in ".?!":
            ends_sentence = True
            if ch == ".":
                ellipsis = self.word.endswith(".")
                abbreviation = (self.word + ch).lower() in ABBREVIATIONS
                ends_sentence = not (ellipsis or abbreviation)
            self.word += ch
            self.state = AFTER_PUNCT if ends_sentence else NEUTRAL
            return False

        if self.state == AFTER_PUNCT and ch in CLOSERS:   # e.g.  He said "ok."
            self.word += ch
            return False

        if self.state == START and ch.isalpha():
            self.seg_len, self.seg_kind = 1, self.hard
            self.state = NEUTRAL
            upper = ch.upper() if capitalize else ch
            self.word += upper
            return upper != ch

        self.word += ch
        if self.state == START and ch in OPENERS:
            return False
        self.state = NEUTRAL
        return False


class Typist:
    """Tracker + autocorrect. process() says what to do about each key press."""

    MAX_BACKSPACES = 64

    def __init__(self):
        self.t = SentenceTracker()
        self.capitalize = True     # tray switch: capital at sentence start
        self.fix_words = True      # tray switch: let's / don't / I'm ...

    def reset(self):
        self.t.reset()

    def lose_track(self):
        """Forget everything typed so far (left the app, paused, or someone else typed for us)."""
        t = self.t
        t.state, t.word, t.seg_len, t.blocked_word, t.last_fix = NEUTRAL, "", 0, "", None

    def process(self, vk, ch, combo=False):
        """Returns None to let the key through, or a Plan to carry out instead."""
        t = self.t

        # Backspace right after an autocorrected word + space = undo the correction.
        fix = t.last_fix
        if vk == VK_BACK and fix and not combo:
            t.undo_fix()
            return Plan(backspaces=len(fix.replacement) + 1, text=fix.original)

        # Finishing a word: maybe fix it first.
        finishing = not combo and (ch in BOUNDARY_CHARS or vk == VK_RETURN)
        if self.fix_words and finishing and t.word and t.word != t.blocked_word:
            found = autocorrect.fix_for(t.word)
            if found and len(found[1]) <= self.MAX_BACKSPACES:
                prefix, core, replacement = found
                t.apply_fix(len(core), replacement)
                t.feed(vk, ch, combo)
                if ch == " ":
                    t.last_fix = Fix(prefix, core, replacement)
                if vk == VK_RETURN:
                    return Plan(len(core), replacement, VK_RETURN)
                return Plan(len(core), replacement + ch)

        if t.feed(vk, ch, combo, self.capitalize):
            return Plan(text=ch.upper())
        return None