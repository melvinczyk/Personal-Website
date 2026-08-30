"""Where song2vec's corpus lives.

A module of its own, and a deliberately empty one: data.py imports numpy,
sklearn and PIL at module level, so anything that only wants to know where the
data is - or whether it is there at all - would drag the whole numerical stack
in behind it. Django's ready() hook needs exactly that answer, in every process
it starts, including ones that will never serve a request from this app.
"""

import os

# Coursework data that sits outside this repo, so the path is a setting rather
# than a constant: the default is the folder it occupies on the machine this
# was written on, and SONG2VEC_DATA overrides it anywhere else. Hard-coded, it
# threw FileNotFoundError on every process on the deployed host, for a Desktop
# folder that only exists on a laptop.
DATA_ROOT = os.path.normpath(os.path.expanduser(
    os.environ.get('SONG2VEC_DATA')
    or '~/Desktop/CS_CLASS/CS665sp26/Musical-Blob/data'))


def available():
    """Whether the corpus is actually on this machine."""
    return os.path.isfile(os.path.join(DATA_ROOT, 'csv', 'songs.csv'))
