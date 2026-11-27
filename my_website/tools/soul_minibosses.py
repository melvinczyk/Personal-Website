"""The GroidCinematics soul minibosses that share a model with something else.

minibosses.py cannot pin a model that lives in another mod's jar, and four of
GroidCinematics' five soul minibosses are exactly that: the mutant souls are
Mutant Monsters / Mutant More models in a soul-sea skin, and the Pale Soul
Rider is the Soul Rider's own rig in a pale one. Unpinned they fall back to an
armour rig and a hand mob's sheet, so each is built here instead: take the
finished model of the mob it wears, and put GroidCinematics' sheet on it.

    python tools/minibosses.py soul_rider    # builds the Soul Rider itself first
    python tools/soul_minibosses.py
"""

import glob
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), 'static', 'minecraft', 'minibosses')
MODS = os.path.expanduser('~/curseforge/minecraft/Instances/Groid Pack OG/mods')
HOST = 'assets/groidcinematics/textures/entity/host/'

# id -> (model it wears, sheet in the GroidCinematics jar, display name)
SKINS = {
    'groidcinematics:pale_soul_rider':
        ('groidcinematics__soul_rider', 'soul_rider_pale.png', 'Pale Soul Rider'),
    'groidcinematics:mutant_soul_zombie':
        ('mutantmonsters__mutant_zombie', 'mutant_soul_zombie.png', 'Mutant Soul Zombie'),
    'groidcinematics:mutant_soul_skeleton':
        ('mutantmonsters__mutant_skeleton', 'mutant_soul_skeleton.png', 'Mutant Soul Skeleton'),
    'groidcinematics:mutant_soul_knight':
        ('mutantmore__mutant_wither_skeleton', 'mutant_soul_knight.png', 'Mutant Soul Knight'),
}


def main():
    jar = zipfile.ZipFile(glob.glob(os.path.join(MODS, 'groidcinematics*.jar'))[0])
    for mob, (base, sheet, name) in SKINS.items():
        with open(os.path.join(OUT, base + '.model.json')) as fh:
            model = json.load(fh)
        key = mob.replace(':', '__')
        model.update(id=mob, name=name, mod='groidcinematics', texture=key + '.png',
                     sheet=HOST + sheet)
        # the skeleton carries a crossbow on a sheet of its own: skin 0 is the
        # mob, the next is the crossbow, which the soul variant has its own of
        if 'skins' in model:
            model['skins'][0]['texture'] = key + '.png'
            if len(model['skins']) > 1:
                model['skins'][1]['texture'] = key + '_crossbow.png'
                with open(os.path.join(OUT, key + '_crossbow.png'), 'wb') as fh:
                    fh.write(jar.read(HOST + 'mutant_soul_crossbow.png'))
        with open(os.path.join(OUT, key + '.model.json'), 'w') as fh:
            json.dump(model, fh)
        with open(os.path.join(OUT, key + '.png'), 'wb') as fh:
            fh.write(jar.read(HOST + sheet))
        print(f'  {mob:<40} {base}')


if __name__ == '__main__':
    main()
