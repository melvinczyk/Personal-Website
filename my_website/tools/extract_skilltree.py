"""Pull the Passive Skill Tree's own tree out of the mod, and out of the pack.

Run from my_website/:
    python tools/extract_skilltree.py [--jar <jar>] [--pack <pst.zip>]

Two sources, layered, because the pack does not use the tree the mod ships:

  * the MOD JAR carries 588 skills, six classes, and most of the icons.
  * the SERVER'S OWN DATAPACK carries 687 - the six plus a seventh class,
    Runekiller, that the pack added with the mod's in-game editor. It lives at
    "Groid Pack OG/datapacks/pst.zip" on the game host and is what the server
    actually loads, so where the two disagree it wins.

The seventh class's icons and names are not in either: the icons ride in the
instance's own resource pack and the names in its KubeJS lang file, both of
which this reads from the CurseForge instance if it is there.

The mod ships the whole tree as data: one JSON per skill carrying where it
sits, how big it draws, which icon it wears and what it connects to. So the
portal draws the real tree at the real coordinates rather than a diagram of
one - the shape a player sees in game is the shape on the page.

Written out as one tree.json plus the icons, because 588 files of four
numbers each is a request storm and the whole tree is smaller than one boss
model.
"""
import io, json, math, os, re, sys, zipfile
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), 'static', 'minecraft', 'skilltree')
INSTANCES = [os.path.expanduser(p) for p in (
    '~/curseforge/minecraft/Instances/Groid Pack OG',
    '~/Documents/curseforge/minecraft/Instances/Groid Pack OG')]
MODS = [os.path.join(i, 'mods') for i in INSTANCES]

# Where the pack keeps what the mod jar does not: the seventh class's icons,
# and every skill name the editor made up.
PACK_ICONS = 'global_packs/required_resources/Passive Skill Tree Icons/assets/skilltree/textures/icons'
PACK_LANG = 'kubejs/assets/skilltree/lang/en_us.json'

# What the pack charges for a skill point, and how many it allows. Both are in
# the instance's own config rather than in the mod, and both have been changed
# since this was written once already, so they are read rather than repeated.
PACK_CONFIG = 'config/skilltree-common.toml'

SKILLS = 'data/skilltree/skills/'
LANG = 'assets/skilltree/lang/en_us.json'

# buttonSize doubles as the grade: the mod draws a class node at 24, a
# keystone at 32, a gateway at 30, a notable at 20 and everything else at 16.
# Taken off the background texture instead, which names it outright.
GRADES = ('class', 'lesser', 'notable', 'keystone', 'gateway')


# ── what a skill actually does ──────────────────────────────────────────────
# The mod builds its tooltips in Java from these same fields; this reproduces
# the reading rather than the code. Every bonus becomes one line of text and,
# where it is a thing worth adding up across a whole build, a key to add it
# under - so the planner can total a route without knowing anything about the
# mod's own vocabulary.
PRETTY = {
    'max_health': 'Max Health', 'attack_damage': 'Attack Damage',
    'attack_speed': 'Attack Speed', 'armor': 'Armour',
    'armor_toughness': 'Armour Toughness', 'movement_speed': 'Movement Speed',
    'knockback_resistance': 'Knockback Resistance', 'luck': 'Luck',
    'crit_chance': 'Crit Chance', 'crit_damage': 'Crit Damage',
    'life_steal': 'Life Steal', 'overheal': 'Overheal',
    'armor_pierce': 'Armour Pierce', 'prot_pierce': 'Protection Pierce',
    'armor_shred': 'Armour Shred', 'current_hp_damage': 'Current Health Damage',
    'exp_per_minute': 'Experience per Minute', 'blocking': 'Blocking',
    'evasion': 'Evasion', 'stealth': 'Stealth', 'regeneration': 'Regeneration',
}


def _name(value):
    """'minecraft:generic.max_health' -> 'Max Health'."""
    tail = str(value or '').split(':')[-1].split('.')[-1]
    return PRETTY.get(tail, tail.replace('_', ' ').title())


def _pct(value):
    """0.15 -> '15%', and never '15.000000000000002%'."""
    n = round(value * 100, 2)
    return f'{n:g}%'


def _num(value):
    """Two decimals is right for +1.5 Protection Pierce and wrong for the
    small scaling bonuses: life steal per point of missing health is 0.0015,
    and rounded to two places it reads as +0, as though the skill did
    nothing. Keep going until something survives the rounding.
    """
    if value and abs(value) < 0.01:
        return f'{round(value, 6):g}'
    return f'{round(value, 2):g}'


# The pack's own item tags. These matter: the Runekiller is gated entirely on
# gear the player did not craft, and the tags list the exact items. Read as
# "a weapon" the class reads like every other one, which is the opposite of
# what it is.
TAGS = {
    'skilltree:uncraftable_weapons': 'uncraftable weapon',
    'skilltree:uncraftable_armor': 'uncraftable armour',
    'skilltree:uncraftable_helmets': 'uncraftable helmet',
    'skilltree:uncraftable_chestplates': 'uncraftable chestplate',
    'skilltree:uncraftable_leggings': 'uncraftable leggings',
    'skilltree:uncraftable_boots': 'uncraftable boots',
    'forge:curios/jewelry': 'jewellery',
    'curios:ring': 'ring',
    'curios:necklace': 'necklace',
    'curios:quiver': 'quiver',
}

# Things that take no article and no plural, so "a food" and "armours" do not
# turn up in a tooltip.
MASS = ('food', 'armour', 'jewellery', 'leggings', 'potions')


def _a(what):
    """'weapon' -> 'a weapon', 'uncraftable armour' -> 'uncraftable armour'."""
    if not what or what.endswith('s') or what.split()[-1] in MASS:
        return what
    return ('an ' if what[0] in 'aeiou' else 'a ') + what


def _plural(what):
    if not what or what.endswith('s') or what.split()[-1] in MASS:
        return what
    return what + 's'


def _gear(cond):
    """'weapon' / 'pickaxe' / 'uncraftable helmet' out of an item condition.

    Bare, with no article: the callers word it differently - holding one,
    wearing one, crafting several - so each adds its own.
    """
    kind = str((cond or {}).get('type', '')).split(':')[-1]
    if kind == 'equipment_type':
        what = str(cond.get('equipment_type', '')).replace('_', ' ')
        return '' if what in ('', 'any') else what.replace('armor', 'armour')
    if kind == 'potion':
        return 'potions'
    if kind == 'food':
        return 'food'
    if kind == 'tag':
        # the field is tag_id; reading 'tag' silently returned nothing, so
        # every tagged condition rendered as its bare fallback
        tag = str(cond.get('tag_id') or cond.get('tag') or '')
        return TAGS.get(tag, _name(tag).lower())
    if kind == 'enchanted':
        return 'enchanted item'
    return kind.replace('_', ' ') if kind not in ('', 'none') else ''


def _when(bonus, *keys):
    """The 'with a pickaxe' half of a bonus. Every condition the pack uses."""
    said = []
    for key in keys:
        cond = bonus.get(key) or {}
        kind = str(cond.get('type', '')).split(':')[-1]
        if kind in ('', 'none'):
            continue
        if kind == 'equipment_type' or kind in ('potion', 'food', 'tag'):
            what = _gear(cond)
            if what:
                said.append(f'with {_a(what)}' if key == 'item_condition' else what)
        elif kind == 'has_item_in_hand':
            what = _gear(cond.get('item_condition'))
            said.append(f'while holding {_a(what)}' if what else 'while holding a weapon')
        elif kind == 'has_item_equipped':
            what = _gear(cond.get('item_condition'))
            said.append(f'while wearing {_a(what)}' if what else 'while equipped')
        elif kind == 'has_gems':
            said.append('while socketed')
        elif kind == 'health_percentage':
            said.append('at low health')
        elif kind == 'food_level':
            said.append('while well fed')
        elif kind == 'effect_amount':
            said.append('while affected')
        elif kind == 'has_effect':
            said.append('against affected enemies')
        elif kind == 'burning':
            said.append('against burning enemies')
        elif kind == 'projectile':
            said.append('with projectiles')
        elif kind == 'melee':
            said.append('in melee')
        else:
            said.append(kind.replace('_', ' '))
    return ', '.join(dict.fromkeys(said))


def _undouble(per, when):
    """Drop a condition that only repeats what the scaling clause just said."""
    kept = []
    for clause in when.split(', '):
        head, _, what = clause.partition(' ')
        if head == 'while':
            what = clause.split(' ', 2)[2] if clause.count(' ') > 1 else ''
            bare = re.sub(r'^an? ', '', what)
            if bare and bare in per:
                continue
        kept.append(clause)
    return ', '.join(kept)


def _per(bonus):
    """The 'per point of armour' half, which is the whole of some skills.

    Colossus is +0.1 attack damage and reads as nothing at all without it:
    what it actually gives is a tenth of a point of damage for every point of
    armour worn, and the number on its own says none of that.
    """
    for key in ('player_multiplier', 'enemy_multiplier'):
        mult = bonus.get(key) or {}
        kind = str(mult.get('type', '')).split(':')[-1]
        if kind in ('', 'none'):
            continue
        if kind == 'attribute_value':
            divisor = float(mult.get('divisor') or 1)
            who = _name(mult.get('attribute'))
            unit = f'{_num(divisor)} {who}' if divisor != 1 else who
            return f'per {unit}'
        if kind == 'gems_amount':
            what = _gear(mult.get('item_condition'))
            return f'per gem in your {what}' if what else 'per gem socketed'
        if kind == 'enchants_amount':
            what = _gear(mult.get('item_condition'))
            return f'per enchantment on your {what}' if what else 'per enchantment'
        if kind == 'enchants_levels':
            what = _gear(mult.get('item_condition'))
            return f'per enchantment level on your {what}' if what else 'per enchantment level'
        if kind == 'missing_health_percentage':
            divisor = float(mult.get('divisor') or 1)
            return f'per {_num(divisor)}% of health missing'
        if kind == 'food_level':
            return 'per point of hunger'
        if kind == 'effect_amount':
            return 'per active effect'
        if kind == 'distance_to_target':
            return 'per block of distance'
        return f'per {kind.replace("_", " ")}'
    return ''


def bonus_line(bonus):
    """One bonus as (text, tally key, value, is-percent). Key None = not summed."""
    kind = str(bonus.get('type', '')).split(':')[-1]
    # 'per point of armour' comes first: for some skills it is the whole of
    # what they do, where the condition is only when they do it
    per = _per(bonus)
    when = _when(bonus, 'player_condition', 'item_condition',
                 'damage_condition', 'target_condition')
    if per and when:
        when = _undouble(per, when)
    tail = (f' {per}' if per else '') + (f' {when}' if when else '')
    # a bonus that scales off something else is not a fixed number, so it is
    # not a thing a build can add up into one line
    scales = bool(per)

    if kind == 'attribute':
        who = _name(bonus.get('attribute'))
        amount = float(bonus.get('amount') or 0)
        # operation 0 is a flat add; 1 and 2 are multipliers of the base
        if bonus.get('operation'):
            return f'+{_pct(amount)} {who}{tail}', None if scales else f'{who}%', amount, True
        return f'+{_num(amount)} {who}{tail}', None if scales else who, amount, False

    if kind == 'damage':
        amount = float(bonus.get('amount') or 0)
        if bonus.get('operation'):
            return f'+{_pct(amount)} Damage{tail}', None if scales else 'Damage%', amount, True
        return f'+{_num(amount)} Damage{tail}', None if scales else 'Damage', amount, False

    simple = {
        'crit_chance':   ('chance',     'Crit Chance'),
        'crit_damage':   ('amount',     'Crit Damage'),
        'incoming_healing': ('multiplier', 'Incoming Healing'),
        'jump_height':   ('multiplier', 'Jump Height'),
        'block_break_speed': ('multiplier', 'Block Break Speed'),
        'gem_power':     ('multiplier', 'Gem Power'),
        'repair_efficiency': ('multiplier', 'Repair Efficiency'),
        'enchantment_requirement': ('multiplier', 'Enchantment Requirement'),
        'healing':       ('amount',     'Life on Hit'),
        'free_enchantment': ('chance',  'Free Enchantment Chance'),
        'arrow_retrieval': ('chance',   'Arrow Retrieval Chance'),
        'enchantment_amplification': ('chance', 'Enchantment Amplification'),
    }
    if kind in simple:
        field, label = simple[kind]
        amount = float(bonus.get(field) or 0)
        sign = '+' if amount >= 0 else ''
        return f'{sign}{_pct(amount)} {label}{tail}', None if scales else f'{label}%', amount, True

    if kind == 'gained_experience':
        amount = float(bonus.get('multiplier') or 0)
        source = str(bonus.get('experience_source', 'all')).replace('_', ' ')
        return (f'+{_pct(amount)} experience from {source}',
                f'Experience ({source})%', amount, True)

    if kind == 'loot_duplication':
        amount = float(bonus.get('chance') or 0)
        what = str(bonus.get('loot_type', 'loot')).replace('_', ' ')
        return (f'{_pct(amount)} chance to double {what} loot',
                f'Double {what} loot%', amount, True)

    if kind == 'player_sockets':
        n = int(bonus.get('sockets') or 0)
        return f'+{n} socket{"" if n == 1 else "s"}{tail}', 'Sockets', n, False

    if kind == 'ignite':
        return (f'{_pct(float(bonus.get("chance") or 0))} chance to ignite for '
                f'{_num(float(bonus.get("duration") or 0))}s', None, 0, False)

    if kind == 'recipe_unlock':
        return f'unlocks {_name(bonus.get("recipe_id"))}', None, 0, False

    if kind == 'crafted_item_bonus':
        return _crafted(bonus)

    return kind.replace('_', ' '), None, 0, False


# Which field carries the number, because it is not the same one twice, and
# whether that number is a fraction or a count. Reading 'multiplier or amount'
# off all of them found neither on most and printed every one as +0%.
CRAFTED = {
    'potion_duration':      ('multiplier', 'Potion Duration', True),
    'food_saturation':      ('multiplier', 'Food Saturation', True),
    'food_healing':         ('amount',     'Food Healing',    True),
    'durability':           ('chance',     'Durability',      True),
    'quiver_capacity':      ('chance',     'Quiver Capacity', False),
    'sockets':              ('amount',     'Sockets',         False),
}


def _verb(subject, stem):
    """'crafted potions give', but 'crafted armour gives'."""
    return stem if subject.endswith('s') else stem + 's'


def _crafted(bonus):
    """A bonus the player puts onto the things they make, not onto themselves."""
    inner = bonus.get('item_bonus') or {}
    kind = str(inner.get('type', '')).split(':')[-1]
    made = 'crafted ' + (_plural(_gear(bonus.get('item_condition'))) or 'items')

    # the item carries a whole skill bonus of its own, so read that one
    if kind == 'skill_bonus':
        text, key, value, pct = bonus_line(inner.get('skill_bonus') or {})
        # the tally strips a trailing % to get the label, so the % stays last
        if key:
            key = key[:-1] + ' (crafted)%' if key.endswith('%') else key + ' (crafted)'
        return f'{made} {_verb(made, "give")} {text}', key, value, pct

    if kind == 'potion_amplification':
        chance = float(inner.get('chance') or 0)
        return (f'{_pct(chance)} chance to amplify {made}',
                'Potion Amplification (crafted)%', chance, True)

    if kind == 'food_effect':
        effect = _name(inner.get('effect'))
        level = int(inner.get('amplifier') or 0) + 1
        secs = round(float(inner.get('duration') or 0) / 20)
        return (f'{made} {_verb(made, "grant")} {effect} {level} for {secs}s',
                None, 0, False)

    if kind in CRAFTED:
        field, label, pct = CRAFTED[kind]
        amount = float(inner.get(field) or 0)
        # operation 0 is a flat add even where the field is called a chance
        if pct and not inner.get('operation') and kind == 'quiver_capacity':
            pct = False
        shown = _pct(amount) if pct else _num(amount)
        if kind == 'sockets':
            label = 'socket' if amount == 1 else 'sockets'
        return (f'+{shown} {label} on {made}', f'{label} (crafted)' + ('%' if pct else ''),
                amount, pct)

    return f'{_name(inner.get("type")) or "a bonus"} on {made}', None, 0, False


def skill_costs():
    """The experience each skill point costs, straight out of the config.

    Returns (max points, [total for 1 point, total for 2, ...]). CUMULATIVE,
    not per point: the list climbs all the way and its last entry is the whole
    tree, so adding the entries together adds a running total to itself.

    The curve is deliberate and reads best in levels, which is plainly the
    unit it was written in - every entry converts to a whole number. One level
    per point up to sixty, then a takeoff, then an S easing into exactly 2000.
    """
    for folder in INSTANCES:
        path = os.path.join(folder, PACK_CONFIG)
        if not os.path.exists(path):
            continue
        text = open(path).read()
        cap = re.search(r'"Maximum skill points"\s*=\s*(\d+)', text)
        costs = re.search(r'"Levelup costs"\s*=\s*\[(.*?)\]', text, re.S)
        if not cap:
            continue
        return (int(cap.group(1)),
                [int(n) for n in costs.group(1).replace('\n', '').split(',')
                 if n.strip()] if costs else [])
    return 0, []


GUIDE = os.path.join(os.path.dirname(HERE), 'templates', 'minecraft_guide.html')


def _level(xp):
    """Minecraft's own experience curve, inverted: experience -> level."""
    if xp <= 352:
        return math.sqrt(xp + 9) - 3
    if xp <= 1507:
        return 8.1 + math.sqrt(0.4 * (xp - 195.975))
    return 18.0555556 + math.sqrt((2 / 9) * (xp - 752.9861111))


def guide_chart(cap, costs):
    """Rewrite the guide's own copy of the cost curve from the same numbers.

    That chart is a hand-written SVG in the guide template, and hand-written
    means it goes stale: it still said 120 points and 2.8 million for the last
    one long after the pack had moved to 130 and four million. Same source,
    same maths, written back into the page.
    """
    if not costs or not os.path.exists(GUIDE):
        return False
    W, L, R, TOP, BOT = 892, 56, 56, 24, 260
    plot = W - L - R
    # in levels, and read off the curve rather than summed - see skill_costs
    costs = [round(_level(xp)) for xp in costs]
    lo, hi = math.log10(costs[0]), math.log10(max(costs))
    span = hi - lo or 1

    def px(i):
        return L + (i / (len(costs) - 1)) * plot

    def py(v):
        return BOT - ((math.log10(v) - lo) / span) * (BOT - TOP)

    points = ' '.join(f'{px(i):.1f},{py(c):.1f}' for i, c in enumerate(costs))

    rungs = []
    for power in range(math.ceil(lo), math.floor(hi) + 1):
        y = py(10 ** power)
        if not TOP <= y <= BOT:
            continue
        label = (f'{10 ** (power - 6)}M' if power >= 6 else
                 f'{10 ** (power - 3)}K' if power >= 3 else f'{10 ** power}')
        rungs.append(
            f'<line class="gxc-gridline" x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}"/>\n'
            f'            <text class="gxc-gridlabel" x="{L - 50}" y="{y + 3:.1f}">lv {label}</text>')

    marks = []
    for n in dict.fromkeys([0, cap // 2 - 1, int(cap * 0.77) - 1, cap - 1]):
        if not 0 <= n < len(costs):
            continue
        x, y = px(n), py(costs[n])
        last = n == cap - 1
        marks.append(
            f'<g>\n              <circle class="gxc-dot" cx="{x:.1f}" cy="{y:.1f}" r="4"/>\n'
            f'              <text class="gxc-marklabel" x="{x - 36 if last else x:.0f}" '
            f'y="{y - 14 if last else BOT + 12:.0f}" text-anchor="middle">#{n + 1}</text>\n'
            f'              <text class="gxc-marksub" x="{x - 36 if last else x:.0f}" '
            f'y="{y if last else BOT + 26:.0f}" text-anchor="middle">'
            f'level {costs[n]:,}</text>\n            </g>')

    half, most = costs[cap // 2 - 1], costs[cap - 1]
    svg = f"""<svg class="gxc-svg" viewBox="0 0 892 300" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="gxc-fade" x1="0" y1="0" x2="0" y2="1">
                <stop class="gxc-stop-top" offset="0%"/>
                <stop class="gxc-stop-bot" offset="100%"/>
              </linearGradient>
            </defs>
            {chr(10).join('            ' + r for r in rungs).strip()}
            <polygon class="gxc-area" points="{points} {W - R},{BOT} {L},{BOT}"/>
            <polyline class="gxc-line" points="{points}"/>
            {chr(10).join('            ' + m for m in marks).strip()}
            <text class="gxc-axislabel" x="{L + plot / 2:.0f}" y="298" text-anchor="middle">skill point # (1 to {cap})</text>
          </svg>"""

    note = (f'The player level each skill point needs, log scale. One level a '
            f'point up to 60, then it takes off, then it eases into the cap. '
            f'In plain terms: half the tree, {cap // 2} points, is <b>level '
            f'{half:,}</b>. The other half costs the remaining '
            f'<b>{most - half:,} levels</b> up to <b>{most:,}</b>.')

    page = open(GUIDE).read()
    page, hits = re.subn(r'<svg class="gxc-svg".*?</svg>', lambda _m: svg, page,
                         count=1, flags=re.S)
    page, notes = re.subn(r'(<div class="gxc-note">).*?(</div>)',
                          lambda _m: f'{_m.group(1)}{note}{_m.group(2)}', page,
                          count=1, flags=re.S)
    if hits and notes:
        open(GUIDE, 'w').write(page)
        return True
    return False


def find_jar(arg):
    if arg and arg.endswith('.jar'):
        return arg
    for folder in ([arg] if arg else []) + MODS:
        if folder and os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if name.lower().startswith('passiveskilltree') and name.endswith('.jar'):
                    return os.path.join(folder, name)
    return None


def main(arg=None, pack=None):
    jar = find_jar(arg)
    if not jar or not os.path.exists(jar):
        print('no PassiveSkillTree jar found')
        return
    os.makedirs(os.path.join(OUT, 'icons'), exist_ok=True)
    print('reading', os.path.basename(jar))

    # every skill file, the datapack's copy winning where both have one
    raw_skills = {}
    sources = [jar] + ([pack] if pack and os.path.exists(pack) else [])
    for source in sources:
        with zipfile.ZipFile(source) as z:
            for entry in z.namelist():
                # a zip made on a Mac carries a shadow copy of every file
                if entry.startswith('__MACOSX') or not (
                        entry.startswith(SKILLS) and entry.endswith('.json')):
                    continue
                raw_skills[os.path.basename(entry)] = json.loads(z.read(entry))
        print(f'  {os.path.basename(source)}: {len(raw_skills)} skills so far')

    lang = {}
    with zipfile.ZipFile(jar) as z:
        lang.update(json.loads(z.read(LANG)))
    for folder in INSTANCES:
        extra = os.path.join(folder, PACK_LANG)
        if os.path.exists(extra):
            with open(extra) as fh:
                lang.update(json.load(fh))
            break

    with zipfile.ZipFile(jar) as z:
        nodes, edges, wanted = {}, [], set()
        for raw in raw_skills.values():
            key = raw['id'].split(':')[-1]
            grade = os.path.basename(raw.get('backgroundTexture', ''))[:-4] or 'lesser'
            icon = os.path.basename(raw.get('iconTexture', '')) or ''
            wanted.add(raw.get('iconTexture', ''))
            nodes[key] = {
                'n': lang.get(f'skill.skilltree.{key}.name', key.replace('_', ' ')),
                # the mod's own coordinates, rounded to a pixel - the tree is
                # a thousand across and nothing here needs the sixth decimal
                'x': round(raw['positionX'], 1),
                'y': round(raw['positionY'], 1),
                's': raw.get('buttonSize', 16),
                'g': grade if grade in GRADES else 'lesser',
                'i': icon,
                # which class's arm of the tree it is on. Every id is prefixed
                # with it, and there are exactly six.
                'c': key.split('_')[0],
                'start': bool(raw.get('isStartingPoint')),
                # what it does, already worded - see bonus_line
                'b': [bonus_line(x) for x in (raw.get('bonuses') or [])
                      if isinstance(x, dict)],
            }
            for other in (raw.get('directConnections') or []):
                edges.append([key, other.split(':')[-1], 0])
            for other in (raw.get('longConnections') or []):
                edges.append([key, other.split(':')[-1], 1])

        # An edge is undirected and both ends list it, so half of these are
        # the same line drawn twice. Keyed on the sorted pair to drop the copy.
        seen, out_edges = set(), []
        for a, b, long in edges:
            if b not in nodes:
                continue
            pair = tuple(sorted((a, b)))
            if pair in seen:
                continue
            seen.add(pair)
            out_edges.append([pair[0], pair[1], long])

        extra_icons = next((os.path.join(f, PACK_ICONS) for f in INSTANCES
                            if os.path.isdir(os.path.join(f, PACK_ICONS))), None)
        drawn = missing = 0
        for path in sorted(wanted):
            if not path:
                continue
            entry = 'assets/skilltree/' + path.split(':')[-1]
            name = os.path.basename(entry)
            art = None
            try:
                art = Image.open(io.BytesIO(z.read(entry))).convert('RGBA')
            except KeyError:
                # the seventh class draws with icons the jar has never heard
                # of - they ship in the pack's own resource pack instead
                loose = extra_icons and os.path.join(extra_icons, name)
                if loose and os.path.exists(loose):
                    art = Image.open(loose).convert('RGBA')
            if art is None:
                missing += 1
                continue
            art.save(os.path.join(OUT, 'icons', name))
            drawn += 1

    cap, costs = skill_costs()
    tree = {'nodes': nodes, 'edges': out_edges,
            'classes': sorted({n['c'] for n in nodes.values()}),
            # what the pack allows and what it charges - see skill_costs
            'max': cap, 'costs': costs}
    with open(os.path.join(OUT, 'tree.json'), 'w') as fh:
        json.dump(tree, fh, separators=(',', ':'))
    xs = [n['x'] for n in nodes.values()]
    ys = [n['y'] for n in nodes.values()]
    print(f'{len(nodes)} skills, {len(out_edges)} connections, {drawn} icons'
          + (f' ({missing} with no art anywhere)' if missing else ''))
    print(f'extent {min(xs):.0f}..{max(xs):.0f} by {min(ys):.0f}..{max(ys):.0f}')
    print('classes:', ', '.join(tree['classes']))
    if cap:
        print(f'{cap} points, {costs[-1]:,} experience to fill the tree '
              f'(level {round(_level(costs[-1]))})')
        print('guide chart', 'rewritten' if guide_chart(cap, costs) else 'unchanged')


def _flag(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None


if __name__ == '__main__':
    loose = [a for a in sys.argv[1:] if not a.startswith('-')]
    main(_flag('--jar') or (loose[0] if loose else None), _flag('--pack'))
