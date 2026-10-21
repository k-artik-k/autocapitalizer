"""
sentence_engine.py - decides WHEN the next letter should be capitalised.

Pure logic, no Windows calls. The Windows layer feeds it one key at a time.
"""

NEUTRAL, START, AFTER_PUNCT = "neutral", "start", "after_punct"

VK_BACK, VK_RETURN = 0x08, 0x0D

# Tab, Esc, PgUp, PgDn, End, Home, arrows, Delete: the caret may have jumped,
# so we no longer know where we are in the sentence.
NAV_KEYS = {0x09, 0x1B, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2E}

# A period after these does NOT end a sentence.
ABBREVIATIONS = {"e.g.", "i.e.", "mr.", "mrs.", "ms.", "dr.", "vs.", "approx."}

OPENERS = set("\"'([{\u00bf\u00a1")   # allowed between ". " and the first letter
CLOSERS = set("\"')]}")               # allowed between "." and the space


class SentenceTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        """Call when focus enters the target app: assume an empty message box."""
        self.state = START
        self.hard = True          # True = start of box/line, False = after ". "
        self.word = ""            # characters since the last space
        self.seg_len = 0          # chars typed since the last capital we applied
        self.seg_kind = True      # the 'hard' flag to restore if all of them get deleted

    def feed(self, vk, ch, combo=False):
        """
        Process one key press.
        vk    - virtual key code
        ch    - the character this key produces right now ("" if none)
        combo - True if Ctrl/Alt/Win is held (shortcut, not typing)
        Returns True if `ch` should be typed as an uppercase letter instead.
        """
        if combo or vk in NAV_KEYS:
            self.state, self.word, self.seg_len = NEUTRAL, "", 0
            return False

        if vk == VK_RETURN:                       # message sent, or Shift+Enter newline
            self.state, self.hard, self.word, self.seg_len = START, True, "", 0
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
            self.word = ""
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

        self.word += ch
        if self.state == START:
            if ch.isalpha():
                self.seg_len, self.seg_kind = 1, self.hard
                self.state = NEUTRAL
                return ch.upper() != ch
            if ch in OPENERS:
                return False
        self.state = NEUTRAL
        return False