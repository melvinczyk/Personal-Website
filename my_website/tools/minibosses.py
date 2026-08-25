"""Build the portal's miniboss roster, the same way bosses.py builds the boss one.

Same pipeline end to end (jar indexing, geckolib/vanilla model reading, texture
ranking) against a different tag and a separate output folder, so minibosses
get their own gallery without disturbing the boss one.

    python tools/minibosses.py            # build everything the tag lists
    python tools/minibosses.py --list     # say what would happen, write nothing
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bosses as B

# This machine's mods folder lives directly under the user profile, not under
# Documents like bosses.py assumes - both tools need this override.
B.MODS = os.path.expanduser(
    '~/curseforge/minecraft/Instances/Groid Pack OG/mods')
B.TAG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'data', 'minibosses.json')
B.OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'static', 'minecraft', 'minibosses')

# Hand-pinned minibosses, filled in as the general heuristics get one wrong -
# the same reasoning as bosses.py's OVERRIDES, kept separate so a miniboss fix
# never collides with a boss id.
MINIBOSS_OVERRIDES = {}
B.OVERRIDES = MINIBOSS_OVERRIDES

if __name__ == '__main__':
    B.main()
