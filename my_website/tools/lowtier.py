"""Build the low-tier summon roster, the same way minibosses.py builds the miniboss one.

Third driver over bosses.py's pipeline. The roster is the Summoner Scrolls fork's
own low-tier scroll list (its tools/lowtier.json), plus the vanilla mobs the mod
re-implements as its base summons and the remaining bipeds its fusion parts table
names -- so that every mob the mod can summon has geometry to map, not only the
bosses and minibosses.

The tag beside this file is generated rather than unzipped from a datapack, because
unlike bosses and minibosses there is no groid: tag for this set: it is defined by
the mod, not by the pack.

    python tools/lowtier.py            # build everything the roster lists
    python tools/lowtier.py --list     # say what would happen, write nothing
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bosses as B

B.TAG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'data', 'lowtier.json')
B.OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'static', 'minecraft', 'lowtier')
# em.build()/build_dragon() write to entity_model's own OUT, which B.OUT does not
# reach on its own -- the same line minibosses.py needs for the same reason.
B.em.OUT = B.OUT


# mobcompack's Jawbreaker is drawn by JawsModel, a class named after the jaw
# rather than the mob, so kin() cannot find it from the entity id. Only the
# geo file carries the mob's own name, so it is pinned outright.
B.OVERRIDES = dict(getattr(B, 'OVERRIDES', {}))
B.OVERRIDES['mobcompack:jawbreaker'] = {
    'model': 'geo/jawbreaker.geo.json',
    'texture': 'textures/entity/jawbreaker.png',
}

if __name__ == '__main__':
    B.main()
