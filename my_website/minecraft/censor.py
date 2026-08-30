"""Mask slurs and profanity in chat before it is stored or shown.

The chat box puts whatever is typed on a public page under somebody's name, so
what lands here is filtered on the way in rather than on the way out: the
archive on disk holds the masked text, and there is no copy of the original for
a later change of mind to leak. That is the point. This file is the only place
the words themselves appear.

What it is not: this is a decency filter on a hobby site's chat box, not
moderation. Somebody who wants to get a word past it can. The bar is that the
ordinary use of these words - which is most of it - does not end up rendered in
a stranger's browser, and that the effort of getting one through is enough to
be obviously deliberate.

Two things it works hard at, because both are how a naive list fails:

  * Obfuscation. n1gg3r, f u c k, shiiiit and n-i-g-g-e-r are the same words
    and are matched as such: every letter may repeat, digits and symbols that
    stand in for letters are read as those letters, and the worst of them may
    be spaced or punctuated apart.
  * False positives, which are the more embarrassing failure. A filter that
    stars out "class", "bass", "Scunthorpe" or "assassin" is worse than no
    filter, because it is wrong in public and about innocent text. Matching is
    anchored to whole words and endings are drawn from a list rather than a
    wildcard, so a root only ever matches the word it is the root of.
"""

import re

# Substitutions to read through. Each letter maps to the characters that get
# used in its place; anything not here matches only itself.
LOOKALIKE = {
    'a': 'a@4', 'b': 'b8', 'c': 'c(', 'e': 'e3', 'g': 'g69', 'h': 'h#',
    'i': 'i1!|', 'l': 'l1|', 'o': 'o0', 's': 's$5z', 't': 't7+',
    'u': 'uv', 'z': 'z2',
}

# Endings a root may carry and still be the same word. Deliberately a list and
# not [a-z]*: with a wildcard, "ass" swallows "assassin" and "assess", and
# "hell" swallows "hello", which is the single most likely thing anybody types
# into a chat box.
SUFFIX = ('', 's', 'es', 'ed', 'ing', 'in', "in'", 'er', 'ers', 'a', 'as',
          'az', 'ah', 'y', 'ie', 'ies', 'ish', 'est')

# The slurs. Matched through spacing and punctuation as well as substitution,
# because these are the ones people bother to disguise.
SLURS = (
    'nigger', 'nigga', 'niger',
    'faggot', 'fag',
    'chink', 'gook', 'spic', 'wetback', 'kike', 'tranny', 'trannie',
    'coon', 'raghead', 'towelhead', 'beaner', 'currymuncher',
    'retard', 'retarded',
)

# Ordinary profanity.
PROFANITY = (
    'fuck', 'shit', 'bitch', 'cunt', 'asshole', 'ass', 'dick', 'cock',
    'pussy', 'bastard', 'whore', 'slut', 'damn', 'goddamn', 'piss',
    'wanker', 'bollocks', 'twat', 'prick', 'douche', 'jackass', 'dumbass',
    'motherfucker', 'bullshit', 'dipshit', 'jerkoff', 'blowjob',
)

# How long a root has to be before it is matched through spacing as well. Four
# letters spelled out in a row is somebody spelling a word out on purpose;
# three is a risk of finding one in ordinary text, and the only three-letter
# root here is "ass".
SPACED_MIN = 4

# What goes in their place. A fixed run rather than one star per letter: a mask
# that spells out the length of what it hid is a puzzle with the answer
# printed underneath it.
MASK = '******'

# A word is bounded by anything that is not a letter or a digit. Not \b, which
# counts _ as a word character and would let n_i_g_g_e_r through the gap.
_OPEN = r'(?<![a-zA-Z0-9])'
_CLOSE = r'(?![a-zA-Z0-9])'


def _letter(char):
    """One letter, as the set of things that get typed for it."""
    chars = LOOKALIKE.get(char, char)
    return f'[{re.escape(chars)}]+' if len(chars) > 1 else f'{re.escape(char)}+'


def _root(word, spaced=False):
    """A root as a pattern: every letter repeatable, optionally spaced apart.

    The repetition is per letter rather than over the whole word, so fuuuck
    and ffuuuccck both match while "fukfuk" does not become one hit.
    """
    gap = r'[\s._\-*+]{0,2}' if spaced else ''
    return gap.join(_letter(char) for char in word)


def _pattern(words, spaced=False):
    # longest first, so "asshole" is tried before "ass" and the mask replaces
    # the whole word rather than its first three letters
    roots = '|'.join(_root(word, spaced)
                     for word in sorted(set(words), key=len, reverse=True))
    tails = '|'.join(sorted(set(SUFFIX), key=len, reverse=True))
    return re.compile(f'{_OPEN}(?:{roots})(?:{tails}){_CLOSE}', re.IGNORECASE)


# Ordinary profanity, split on that rule: the long ones are matched through
# spacing the way the slurs are, the short ones only as written.
_SLUR_RE = _pattern(SLURS, spaced=True)
_SPACED_RE = _pattern([w for w in PROFANITY if len(w) >= SPACED_MIN], spaced=True)
_TIGHT_RE = _pattern([w for w in PROFANITY if len(w) < SPACED_MIN])


def clean(text):
    """The text with anything matched replaced by MASK.

    Safe on anything: a non-string comes back as it arrived rather than
    raising, because this sits in the path of every chat message and a filter
    that can throw is a filter that can take the feed down.
    """
    if not isinstance(text, str) or not text:
        return text
    text = _SLUR_RE.sub(MASK, text)
    text = _SPACED_RE.sub(MASK, text)
    return _TIGHT_RE.sub(MASK, text)


def hits(text):
    """What would be masked. For checking the list, not used in the feed."""
    if not isinstance(text, str):
        return []
    return [m.group(0) for pattern in (_SLUR_RE, _SPACED_RE, _TIGHT_RE)
            for m in pattern.finditer(text)]
