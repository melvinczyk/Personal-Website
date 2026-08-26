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


def _enderman_arm(prefix, right, lower):
    """The ten bones of one of the Mutant Enderman's four arms, ported from
    MutantEndermanModel$Arm.createArmLayer.

    The model calls this static helper once per arm with a name prefix and a
    pair of flags; the bytecode reader can follow a class's own method, not
    one it calls out to, so all four arms vanish and the four calls that
    build them get misread as bones of their own, one stray cube apiece.
    """
    sign = -1.0 if right else 1.0
    parts = [
        (prefix + 'arm', 'chest', (4.0 * sign, -14.0, 0.0),
         (-1.5, 6.0 if lower else 0.0, -1.5, 3.0, 22.0, 3.0), (92, 0), not right),
        (prefix + 'fore_arm', prefix + 'arm', (0.0, 21.0, 1.0),
         (-1.5, 0.0, -1.5, 3.0, 18.0, 3.0), (104, 0), not right),
        (prefix + 'hand', prefix + 'fore_arm', (0.0, 17.5, 0.0), None, (0, 0)),
    ]
    for i, z in enumerate((-1.0, 0.0, 1.0)):
        h = 6.0 if i == 1 else 5.0
        finger = f'{prefix}finger{i}'
        parts.append((finger, prefix + 'hand', (0.5 * sign, 0.0, z),
                      (-0.5, 0.0, -0.5, 1.0, h, 1.0), (76, 0), not right))
        parts.append((f'{prefix}fore_finger{i}', finger, (0.0, 0.5 + h, 0.0),
                      (-0.5, 0.0, -0.5, 1.0, h, 1.0), (76, 0), not right))
    parts.append((prefix + 'thumb', prefix + 'hand', (-0.5 * sign, 0.0, -0.5),
                  (-0.5, 0.0, -0.5, 1.0, 5.0, 1.0), (76, 0), right))
    return parts


# All four. The lower pair are the mob: they hang off the same point on the
# chest as the upper pair and are told apart by the six pixels their boxes
# start further down the arm, and by the turn setAngles gives each of them
# after building it.
ENDERMAN_ARMS = (
    _enderman_arm('right_', True, False) + _enderman_arm('left_', False, False)
    + _enderman_arm('lower_right_', True, True)
    + _enderman_arm('lower_left_', False, True)
)


def _enderman_arm_rest(prefix, right, lower):
    """What MutantEndermanModel$Arm.setAngles leaves the arm at, plus the
    nudge setAngles gives each lower arm after calling it."""
    s = -1.0 if right else 1.0
    x, z = -0.5235988, 0.5235988 * -s
    if lower:                       # arm.xRot += 0.1; zRot -= 0.2 (right)
        x, z = x + 0.1, z - 0.2 * -s
    rest = {
        prefix + 'arm':      (x, 0.0, z),
        prefix + 'fore_arm': (-0.62831855, 0.0, 0.0),
        prefix + 'hand':     (0.0, 0.3926991 * -s, 0.0),
        prefix + 'thumb':    (-0.62831855, 0.0, 0.3926991 * -s),
    }
    for i, (fx, fz) in enumerate(((-0.2617994, 0.0), (0.0, 0.17453294 * -s),
                                  (0.2617994, 0.0))):
        rest[f'{prefix}finger{i}'] = (fx, 0.0, fz)
    for i, fz in enumerate((-0.2617994, -0.3926991, -0.2617994)):
        rest[f'{prefix}fore_finger{i}'] = (0.0, 0.0, fz * -s)
    return rest


# MutantEndermanModel.setAngles(): the mob stands hunched with four arms held
# out and its legs folded back. Built flat it is a post.
ENDERMAN_REST = {
    'abdomen': (0.31415927, 0.0, 0.0),
    'chest':   (0.3926991, 0.0, 0.0),
    'neck':    (0.19634955, 0.0, 0.0),
    'head':    (-0.7853982, 0.0, 0.0),
    'leg1':     (-0.8975979, 0.0, 0.2617994),
    'leg2':     (-0.8975979, 0.0, -0.2617994),
    'fore_leg1': (0.7853982, 0.0, -0.1308997),
    'fore_leg2': (0.7853982, 0.0, 0.1308997),
}
for _p, _r, _l in (('right_', True, False), ('left_', False, False),
                   ('lower_right_', True, True), ('lower_left_', False, True)):
    ENDERMAN_REST.update(_enderman_arm_rest(_p, _r, _l))


def _skeleton_spine_segment(index, parent):
    """The seven bones of one of the Mutant Skeleton's three spine segments,
    ported from MutantSkeletonModel.Spine.createSpineLayer - a static helper
    the model's own createBodyLayer calls three times in a loop, which the
    reader sees once and cannot tell was meant three times over.
    """
    n = str(index + 1)
    mid = f'middle{n}'
    parts = [(mid, parent, (0.0, -7.0 if index == 0 else -5.0, 0.0),
              (-2.5, -4.0, -2.0, 5.0, 4.0, 4.0), (50, 0))]
    side = mid
    for i, (pivot, mirror) in enumerate((((-3.0, -1.0, 1.75), False),
                                         ((-6.5, 0.0, 0.0), True),
                                         ((-6.4, 0.0, 0.0), False))):
        name = f'side1{i + 1}{n}'
        parts.append((name, side, pivot, (-6.0, -2.0, -2.0, 6.0, 2.0, 2.0), (32, 12), mirror))
        side = name
    side = mid
    for i, (pivot, mirror) in enumerate((((3.0, -1.0, 1.75), True),
                                         ((6.5, 0.0, 0.0), False),
                                         ((6.4, 0.0, 0.0), True))):
        name = f'side2{i + 1}{n}'
        parts.append((name, side, pivot, (0.0, -2.0, -2.0, 6.0, 2.0, 2.0), (32, 12), mirror))
        side = name
    return parts


# waist carries the first segment; each later segment rides the last one's
# own middle bone, the same chain createBodyLayer's loop builds by hand
SKELETON_SPINE = (
    _skeleton_spine_segment(0, 'waist') + _skeleton_spine_segment(1, 'middle1')
    + _skeleton_spine_segment(2, 'middle2')
)

# MutantSkeletonModel.setAngles(): the ribs are the whole of this mob's
# shape and every one of them is swung out by hand. Left at rest they are
# three straight bars run through a spine, which is what the card showed.
SKELETON_REST = {
    'pelvis': (-0.31415927, 0.0, 0.0),
    'waist':  (0.22439948, 0.0, 0.0),
    'neck':   (-0.1308997, 0.0, 0.0),
    'head':   (-0.1308997, 0.0, 0.0),
    'jaw':    (0.09817477, 0.0, 0.0),
    'shoulder1': (-0.7853982, 0.0, 0.0),
    'shoulder2': (-0.7853982, 0.0, 0.0),
    'inner_arm1': (0.5235988, 0.0, 0.31415927),
    'inner_arm2': (0.5235988, 0.0, -0.31415927),
    'inner_fore_arm1': (-0.5235988, 0.0, 0.0),
    'inner_fore_arm2': (-0.5235988, 0.0, 0.0),
    # leg1.xRot is written as -0.2617994 - pelvis.xRot, and the pelvis is
    # already leaning back by then
    'leg1': (-0.2617994 + 0.31415927, 0.0, 0.19634955),
    'leg2': (-0.2617994 + 0.31415927, 0.0, -0.19634955),
    'fore_leg1': (0.0, 0.0, -0.1308997),
    'fore_leg2': (0.0, 0.0, 0.1308997),
    'inner_fore_leg1': (0.31415927, 0.0, 0.0),
    'inner_fore_leg2': (0.31415927, 0.0, 0.0),
}
for _i in range(3):
    _n = str(_i + 1)
    SKELETON_REST[f'middle{_n}'] = (0.17453294, 0.0, 0.0)
    # Spine.setAngles(middleSpine) narrows the middle segment's ribs by a
    # fiftieth; only the second of the three is called with it set
    _narrow = 0.98 if _i == 1 else 1.0
    for _j, _y in enumerate((0.69813174, 1.0471976, 0.8975979)):
        SKELETON_REST[f'side1{_j + 1}{_n}'] = (0.0, -_y * _narrow, 0.0)
        SKELETON_REST[f'side2{_j + 1}{_n}'] = (0.0, _y * _narrow, 0.0)

B.TAG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'data', 'minibosses.json')
B.OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'static', 'minecraft', 'minibosses')
# em.build()/build_dragon() write to entity_model's own OUT, which B.OUT
# above does not touch - a vanilla miniboss (Elder Guardian, Ravager) would
# otherwise land in the boss gallery instead of its own. Nothing here is a
# dragon or reads em.MOBS by tier, so redirecting it wholesale is safe.
B.em.OUT = B.OUT

# The constant part of each mutantmore rig's idle animation, in degrees, read
# out of its <Mob>SineWaveAnimations.mutant<Mob>IdleAnimation. Every one of
# these mobs is built standing to attention and does its actual leaning,
# hunching and knee-bending here, a fixed offset per bone with a slow sway
# added on top. The sway is left out; the offset is the mob's stance.
MUTANT_HUSK_IDLE = {
    'pelvis': (14.8959, -2.9799, 1.9025),
    'body': (30.0, 0.0, 0.0),
    'head': (-44.9526, 0.23, -3.5275),
    'leftArm': (-20.0, 2.5, -20.0),
    'leftArmLower': (-60.0, 0.0, 0.0),
    'rightArm': (-17.2212, 3.3439, 13.3875),
    'rightArmLower': (-60.0, 0.0, 0.0),
    'leftLeg': (-37.5, 0.0, 0.0),
    'leftLegLower': (37.5, 0.0, 0.0),
    'rightLeg': (-37.5, 0.0, 0.0),
    'rightLegLower': (37.5, 0.0, 0.0),
}

MUTANT_HOGLIN_IDLE = {
    'body': (-27.5, 0.0, 0.0),
    'chest': (32.5, 0.0, 0.0),
    'neck': (15.0, 0.0, 0.0),
    'head': (-15.0, 0.0, 0.0),
    'leftEar': (20.1021, 63.2047, 18.3342),
    'rightEar': (20.1021, -63.2047, -18.3342),
    'tail': (157.5, 0.0, 0.0),
    'leftFrontLeg': (0.0, 0.0, -25.0),
    'leftFrontLegLower': (0.0, 0.0, 25.0),
    'rightFrontLeg': (0.0, 0.0, 25.0),
    'rightFrontLegLower': (0.0, 0.0, -25.0),
}

MUTANT_FROZEN_ZOMBIE_IDLE = {
    'pelvis': (23.0654, -9.589, -1.5102),
    'body': (32.6344, 6.0935, 1.1885),
    'head': (-48.9648, 0.8778, -1.7604),
    'leftArm': (-36.975, -5.0461, -11.4427),
    'leftArmLower': (-22.4842, -0.7518, 0.4339),
    'rightArm': (-15.7772, 10.1991, 22.8505),
    'rightArmLower': (-57.5, 0.0, 0.0),
    'leftLeg': (-37.5, 0.0, 0.0),
    'leftLegLower': (37.5, 0.0, 0.0),
    'rightLeg': (-37.5, 0.0, 0.0),
    'rightLegLower': (37.5, 0.0, 0.0),
}

# This one keeps its idle in a keyframe rather than a sine wave, but to the
# same end and in the same units: every channel is a constant with a slow
# cosine laid over it. The constants are the pose - and for this mob they are
# the whole of it, since its ribcage is eighteen straight bars until the idle
# curls them round its chest.
MUTANT_WITHER_SKELETON_IDLE = {
    'pelvis1': (7.4833, 6.4605, 8.4107),
    'pelvis2': (4.9811, 0.4352, -4.9811),
    'spine1': (10.0, 0.0, 0.0),
    'spine2': (17.4334, -0.8834, -5.5187),
    'spine3': (24.5447, -6.4729, 8.0381),
    'rib': (7.5586, 33.3074, 18.6743),
    'rib2': (0.0, 55.0, 0.0),
    'rib3': (0.0, 50.0, 0.0),
    'rib4': (0.0, 32.5, 0.0),
    'rib5': (0.0, 55.0, 0.0),
    'rib6': (0.0, 50.0, 0.0),
    'rib7': (-38.7131, 34.7354, -40.8298),
    'rib8': (0.0, 55.0, 0.0),
    'rib9': (0.0, 50.0, 0.0),
    'rib10': (-4.0398, -37.3237, 6.2862),
    'rib11': (0.0, -55.0, 0.0),
    'rib12': (0.0, -50.0, 0.0),
    'rib13': (21.6577, -39.4781, -32.6171),
    'rib14': (0.0, -55.0, 0.0),
    'rib15': (0.0, -50.0, 0.0),
    'rib16': (-25.8858, -24.8308, 26.5514),
    'rib17': (0.0, -55.0, 0.0),
    'rib18': (0.0, -50.0, 0.0),
    'rightShoulderPad': (-25.0, 0.0, 0.0),
    'leftShoulderPad': (-27.5, 0.0, 0.0),
    'neck': (-24.6401, -6.6338, -2.4405),
    'head': (-30.0415, 5.212, 5.3547),
    'jaw': (1.843, -0.7651, -8.3505),
    'rightArm': (-10.0775, 8.6887, 36.1248),
    'rightArmLower': (-48.4266, 19.0568, -20.2085),
    'leftArm': (-25.3084, -24.1499, -29.1469),
    'leftArmLower': (-33.0061, -10.5249, 6.772),
    'rightLeg': (0.0, 22.5, 10.0),
    'rightLegLower': (10.0, 0.0, 0.0),
    'leftLeg': (-27.6747, -18.0134, -10.2699),
    'leftLegLower': (27.2633, 1.4519, 3.5436),
}

MUTANT_JUNGLE_ZOMBIE_IDLE = {
    'pelvis': (7.3959, -2.9799, 1.9025),
    'body': (42.5, 0.0, 0.0),
    'head': (-47.4526, 0.23, -3.5275),
    'leftArm': (1.9844, -24.4749, -21.9665),
    'leftArmLower': (-47.5, 0.0, 0.0),
    'rightArm': (-14.9523, 30.2231, 4.48),
    'rightArmLower': (-60.0, 0.0, 0.0),
    'vines': (-47.5, 0.0, 0.0),
    'leftVine': (-27.5, 0.0, 0.0),
    'leftVine2': (50.0, 0.0, 0.0),
    'leftVine3': (47.4729, 1.8619, -1.6686),
    'leftVine4': (26.8588, 29.2189, 7.1228),
    'leftLeg': (-37.0772, -6.0681, -7.9634),
    'leftLegLower': (37.3946, -3.0414, 3.9705),
    'rightLeg': (-37.0772, 6.0681, 7.9634),
    'rightLegLower': (37.3946, 3.0414, -3.9705),
}

# Hand-pinned minibosses, filled in as the general heuristics get one wrong -
# the same reasoning as bosses.py's OVERRIDES, kept separate so a miniboss fix
# never collides with a boss id.
MINIBOSS_OVERRIDES = {
    # Cerberus and Tank ship their own bedrock-format geometry - the same
    # shape geckolib reads - but as assets/majruszsdifficulty/custom/*.json
    # rather than a *.geo.json, which is the only thing geo_route's own
    # auto-discovery looks for. Pinning the exact path here routes them
    # through read_model instead, which B.read_model is taught to read a
    # bedrock file from regardless of what it's named.
    'majruszsdifficulty:cerberus': {
        'model': 'assets/majruszsdifficulty/custom/cerberus_model.json',
        'texture': 'textures/entity/cerberus.png'},
    'majruszsdifficulty:tank': {
        'model': 'assets/majruszsdifficulty/custom/tank_model.json',
        'texture': 'textures/entity/tank.png'},
    # Giant's own GiantModel class builds nothing itself - it only scales up
    # what it extends, vanilla's HumanoidModel - so the automatic search
    # finds a class with no boxes in it. Pinning the model routes it through
    # read_model, which already falls back to the vanilla base class when a
    # mod's own chain runs out.
    'majruszsdifficulty:giant': {
        'model': 'com/majruszsdifficulty/entity/GiantModel.class',
        'texture': 'textures/entity/giant.png'},

    # Every illageandspillage mob wears the same tiny party hat and candle -
    # "birthday" and the "thingy" hanging off it - year round, the way its
    # boss-roster cousins do. It reads as a fruit stuck to the head rather
    # than the mob it is actually drawing.
    'illageandspillage:absorber': {'drop': ('birthday',)},

    # From the Shadows keeps two other mobs' skins in the same folder as
    # theirs (frog.png, at 128x128, happens to be the size the model's own
    # geo file declares) and the size-matching pass reaches for that before
    # anything gets to vote on the name. Both bosses are actually drawn from
    # 256x256 sheets the geo file undersells - pinning the texture outright
    # is what pick_texture's own naming signals already wanted to do.
    # Both rigs are built lying down and stood up by their root bone, so the
    # usual reading leaves them as a heap of loose boxes - 'alt' is the one
    # that puts the beast back together.
    'fromtheshadows:bulldrogioth': {
        'texture': 'textures/entity/bulldrogioth.png',
        'mirror': True, 'spin': 'alt'},
    # nehemoth_stone.png is the renderer's default skin; retexture.png and
    # soul_retexture.png are states it switches to only once provoked.
    'fromtheshadows:nehemoth': {
        'texture': 'textures/entity/nehemoth_stone.png',
        'mirror': True, 'spin': 'alt'},

    # Same trap: shellback.png is Aquamirae's own 128x128 mount texture, the
    # exact size ModelMazeMother's builder declares, so it wins the size
    # check before maze_mother.png - the sheet the renderer actually binds -
    # gets a say.
    # She is a ray: forty-four across, eighty-eight long and twelve thick.
    # Framed as built the long axis wins, the card turns her side-on and all
    # that is left is a hairline. Tipped over instead, the whole span reads.
    'aquamirae:maze_mother': {
        'texture': 'textures/entity/maze_mother.png',
        'pose': [35, 20, 0]},

    # The javelin is thrown, and the rig parks it seventy pixels out to the
    # side: taken into the frame it is most of the picture and the knight
    # holding it is a speck.
    # and it is a suit of armour with a ghost inside it, the same trick
    # Maledictus plays on the boss roster: the renderer hangs a second layer
    # off the same bones in the ghost's own skin, so the helmet sheet alone
    # leaves everything below the visor reading off the wrong corner of it.
    'legendary_monsters:resurrected_knight': {
        'drop': ('javelin',),
        'ghost': 'textures/entity/resurrected_knight/ghost_body.png'},


    # The bytecode reader finds no LayerDefinition.create call to read a
    # sheet size from - this model leaves it to a default the vanilla biped
    # uses - so every box is unwrapped against a guessed 64x64 while the
    # actual sheet is 128x64. java_route's own guess carries no flag saying
    # it is one, so nothing downstream knows to correct it; pinning the
    # model routes the build through read_model instead, which does mark a
    # guessed size and hands it the pinned texture's real one in its place.
    'mutantmonsters:mutant_snow_golem': {
        'model': 'fuzs/mutantmonsters/client/model/MutantSnowGolemModel.class',
        'texture': 'textures/entity/mutant_snow_golem/mutant_snow_golem.png'},

    # These geckolib rigs mirror several cubes onto the sheet's other half -
    # a mirrored leg or claw reading the unmirrored UV comes out with its
    # texture backwards. Not the model's default, since a mod occasionally
    # leaves the flag set by accident; here it is genuinely meant.
    'netherman:bell_guardian': {'mirror': True},
    'skarrier_mobs:carnager': {'mirror': True},

    # Both of these hand their repeated parts to a static helper method that
    # takes the part names as arguments - a loop in spirit, called by hand
    # four times over for the enderman's arms and three for the skeleton's
    # spine - which is exactly what the reader cannot see into: a class's own
    # bytecode, not the ones it calls out to. Left alone, each call is
    # misread as a single bone of its own, one leftover cube apiece, and
    # everything the helper actually built is simply gone.
    'mutantmonsters:mutant_enderman': {
        # the four bones the reader mistook the arm-building calls for
        'drop': ('right_', 'left_', 'lower_right_', 'lower_left_'),
        'parts': ENDERMAN_ARMS,
        'rest': ENDERMAN_REST,
        # its eyes are an emissive pass the renderer lays over the same
        # bones; without it a mob this black is a silhouette and nothing else
        'coat': 'textures/entity/mutant_enderman/eyes.png',
    },

    # The hat is switched off in the model's own constructor and never comes
    # back. The crossed arms and the pair of loose ones are the same two
    # arms drawn two ways - an illager at rest folds them, and the renderer
    # shows whichever the pose calls for - so drawing both is the mob
    # wearing a second set through its chest.
    'illagerinvasion:invoker': {
        'drop': ('hat', 'right_arm', 'left_arm'),
    },

    # The ghost arm and the spear in it are not a stray second copy of the
    # knight: BeheadedKnightGhostArmLayer draws them from ghost_arm.png,
    # which is empty everywhere but the arm. Read off the knight's own sheet
    # they take their colour from whatever happens to sit at those
    # co-ordinates, which is what made them look like a mob wearing another.
    'legendary_monsters:beheaded_knight': {
        'skin': {'texture': 'textures/entity/beheaded_knight/ghost_arm.png',
                 'bones': ('ghostArmRoot', 'cube_r16', 'cube_r17', 'cube_r18')},
    },
    # MutantCreeperModel.setAngles(): a creeper reared up on four splayed
    # legs. Built flat the legs run straight back and it stands as a post.
    'mutantmonsters:mutant_creeper': {
        'rest': {
            'pelvis': (-0.7853982, 0.0, 0.0),
            'body':   (0.9424778, 0.0, 0.0),
            'neck':   (1.0471976, 0.0, 0.0),
            'head':   (0.5235988, 0.0, 0.0),
            'front_right_leg': (0.31415927, -0.7853982, 0.0),
            'front_left_leg':  (0.31415927, 0.7853982, 0.0),
            'front_right_fore_leg': (-0.20943952, 0.3926991, 0.0),
            'front_left_fore_leg':  (-0.20943952, -0.3926991, 0.0),
            'back_right_leg': (0.9, 0.62831855, 0.0),
            'back_left_leg':  (0.9, -0.62831855, 0.0),
            'back_right_fore_leg': (0.48332196, 0.0, 0.0),
            'back_left_fore_leg':  (0.48332196, 0.0, 0.0),
        },
    },

    # A hundred and thirty-seven pixels of wingspan and thirty of body: seen
    # square on it is a wire with a phantom threaded through the middle.
    # Tipped forward the wings become the picture, which is the mob.
    'mutantmore:mutant_phantom': {'pose': [45, 0, 0]},

    # Two hundred and forty-eight pixels across, and two hundred of that is
    # four antennae: flat sheets a hundred and twenty long, lying straight
    # out to either side with no turn on them at all. Framed whole the
    # crayfish itself is a speck between them, so the card takes the body and
    # lets the antennae run off the sides.
    'notsoshrimple:crayfish': {'focus': 'cephalothorax', 'zoom': 2.2},

    # A giant clam with skulls in its maw, sat flat on the seabed: its shell
    # is a pair of sixty-four-wide sheets of no thickness and its tentacles
    # lie out flat around them. Square on, all of that is edge-on and the
    # card shows a line. Tipped forward the shell and what is inside it read.
    'notsoshrimple:maneater': {'pose': [20, 0, 0]},

    # Three hundred and twenty-two pixels nose to tail, most of it tail. The
    # whole of it in one card is a thread, so the card takes the head and the
    # dorsal fin and lets the tail run off the side, the way the boss roster
    # already frames its own long swimmers.
    'alexscaves:hullbreaker': {'focus': 'body', 'zoom': 2.0},

    # snowBlock is the forty-cube of ice the zombie starts the fight sealed
    # inside, and the card was drawing nothing else; projectile is a flat
    # sheet of icicles it throws. Neither is the mob.
    'mutantmore:mutant_frozen_zombie': {
        'drop': ('snowBlock', 'projectile'),
        'lean': MUTANT_FROZEN_ZOMBIE_IDLE,
    },

    # The husk's cacti are grown on it only once it has been in the sun, and
    # the twenty-cube of sand in its fist is conjured for one attack and kept
    # scaled to nothing the rest of the time. The model hides all four itself.
    'mutantmore:mutant_husk': {
        'drop': ('cacti', 'cactus4', 'cactus5', 'sandBlock'),
        'lean': MUTANT_HUSK_IDLE,
    },

    'mutantmore:mutant_hoglin': {'lean': MUTANT_HOGLIN_IDLE},

    # The shulker's four legs are folded by its idle animation rather than
    # by the mesh: each hip is turned three ways and each knee bent back a
    # right angle and then fifty degrees more. Built as it stands, the legs
    # run straight out of the shell like spokes. The constant part of each
    # turn is taken; the slow sway laid over it is not.
    'mutantmore:mutant_shulker': {
        'lean': {
            'box': (-2.5, 0.0, 0.0),
            'legright1': (-24.7851, 38.8447, -36.3602),
            'legright1joint1': (-90.0, 0.0, 0.0),
            'legright1joint2': (-50.0, 0.0, 0.0),
            'legright2': (24.7851, -38.8447, -36.3602),
            'legright2joint1': (-90.0, 0.0, 0.0),
            'legright2joint2': (-50.0, 0.0, 0.0),
            'legleft1': (-24.78507, -38.84468, 36.3602),
            'legleft1joint1': (0.0, 0.0, 90.0),
            'legleft1joint2': (-50.0, 0.0, 0.0),
            'legleft2': (24.7851, 38.8447, 36.3602),
            'legleft2joint1': (-90.0, 0.0, 0.0),
            'legleft2joint2': (-50.0, 0.0, 0.0),
        },
    },
    'mutantmore:mutant_jungle_zombie': {'lean': MUTANT_JUNGLE_ZOMBIE_IDLE},
    'mutantmore:mutant_wither_skeleton': {
        'lean': MUTANT_WITHER_SKELETON_IDLE,
    },

    # MutantSnowGolemModel.setAngles(): hunched, arms swung forward, knees
    # bent. And the pumpkin on its head is a second pass - JackOLanternLayer
    # draws the head bones over again out of jack_o_lantern.png - so without
    # it the mob is a bare snow head with a face carved on nothing.
    'mutantmonsters:mutant_snow_golem': {
        'model': 'fuzs/mutantmonsters/client/model/MutantSnowGolemModel.class',
        'texture': 'textures/entity/mutant_snow_golem/mutant_snow_golem.png',
        # The pumpkin is not a part of the golem's own mesh: a layer builds a
        # second copy of the whole model, switches every bone off but the
        # head and its inner_head, and draws that one box from the lantern
        # sheet. inner_head is a shell half a pixel proud of the snow head
        # inside it, so the pumpkin sits over the head rather than through it,
        # and head_core keeps the golem's own sheet - it is buried anyway.
        # That second mesh is laid out against a 64x32 sheet even though the
        # file shipped is a 128x64 copy of it, so it needs measuring its own
        # way or the face reads off a quarter of the pumpkin.
        'skin': {'texture': 'textures/entity/mutant_snow_golem/jack_o_lantern.png',
                 'bones': ('inner_head',), 'size': (64, 32)},
        'rest': {
            'abdomen': (0.1308997, 0.0, 0.0),
            'chest':   (0.1308997, 0.0, 0.0),
            'head':    (-0.2617994, 0.0, 0.0),
            'arm1':    (-0.31415927, 0.0, 0.0),
            'arm2':    (-0.31415927, 0.0, 0.0),
            'inner_arm1': (0.0, 0.5235988, 0.5235988),
            'inner_arm2': (0.0, -0.5235988, -0.5235988),
            'fore_arm1': (0.0, -0.5235988, -0.2617994),
            'fore_arm2': (0.0, 0.5235988, 0.2617994),
            'inner_fore_arm1': (-0.5235988, 0.0, 0.0),
            'inner_fore_arm2': (-0.5235988, 0.0, 0.0),
            'leg1': (-0.62831855, 0.0, 0.0),
            'leg2': (-0.62831855, 0.0, 0.0),
            'inner_leg1': (0.0, 0.0, 0.5235988),
            'inner_leg2': (0.0, 0.0, -0.5235988),
            'fore_leg1': (0.0, 0.0, -0.5235988),
            'fore_leg2': (0.0, 0.0, 0.5235988),
            'inner_fore_leg1': (0.69813174, 0.0, 0.0),
            'inner_fore_leg2': (0.69813174, 0.0, 0.0),
        },
    },

    # MutantZombieModel.setAngles(): hunched forward, arms out, knees bent.
    'mutantmonsters:mutant_zombie': {
        'rest': {
            'waist':  (0.19634955, 0.0, 0.0),
            'chest':  (0.5235988, 0.0, 0.0),
            'head':   (-0.71994835, 0.0, 0.0),
            'arm1':   (-0.32724923, 0.0, 0.3926991),
            'arm2':   (-0.32724923, 0.0, -0.3926991),
            'fore_arm1': (-1.0471976, 0.0, 0.0),
            'fore_arm2': (-1.0471976, 0.0, 0.0),
            'leg1':   (-0.7853982, 0.0, 0.0),
            'leg2':   (-0.7853982, 0.0, 0.0),
            'fore_leg1': (0.7853982, 0.0, 0.0),
            'fore_leg2': (0.7853982, 0.0, 0.0),
        },
    },

    'mutantmonsters:mutant_skeleton': {
        'parts': SKELETON_SPINE,
        # the neck and both shoulders hang off the last spine segment, not
        # the root the reader leaves them on with no segment to find
        'reparent': {'neck': 'middle3', 'shoulder1': 'middle3', 'shoulder2': 'middle3'},
        'rest': SKELETON_REST,
        # and it carries a crossbow, which is a model of its own with a sheet
        # of its own: the renderer walks down the right arm and draws it at
        # the hand. MutantCrossbowModel.setAngles(PI) splays its limbs and
        # rotateRope() strings it.
        'graft': {
            'model': 'fuzs/mutantmonsters/client/model/MutantCrossbowModel.class',
            'texture': 'textures/entity/mutant_crossbow.png',
            'parent': 'inner_fore_arm1', 'prefix': 'crossbow',
            'at': (0, 14, 0),
            'rest': {
                'middle1': (0.3927, 0.0, 0.0),
                'middle2': (-0.3927, 0.0, 0.0),
                'side1': (-0.6283, 0.0, 0.0),
                'side2': (0.6283, 0.0, 0.0),
                'side3': (-0.7854, 0.0, 0.0),
                'side4': (0.7854, 0.0, 0.0),
                # rotateRope() straightens each string back against the three
                # turns of the limb it is tied to
                'rope1': (1.021, 0.0, 0.0),
                'rope2': (-1.021, 0.0, 0.0),
            },
        },
    },
}
B.OVERRIDES = MINIBOSS_OVERRIDES

if __name__ == '__main__':
    B.main()
