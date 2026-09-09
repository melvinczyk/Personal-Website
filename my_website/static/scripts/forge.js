/* The Apothic Forge: Apotheosis' reforging table, gem socketing and gem
   cutting, run rather than described.
 *
 * Everything here is a port of the mod's own code against the mod's own data.
 * The data comes from tools/extract_apotheosis.py, which merges Apotheosis and
 * ancientreforging with our two datapacks in the order the game merges them,
 * so the costs and curves on this page are the ones on the server, not the
 * mod's defaults. Where a number or a rule below looks arbitrary, it is quoted
 * from a specific class and the comment says which.
 *
 * One thing this is not: bit-identical to a particular reforge in a particular
 * world. The game seeds its roll from a number stored in the player's own NBT
 * and runs it through Xoroshiro; that seed is not knowable here and copying
 * the generator without it would buy nothing. What is identical is everything
 * that decides what *can* come out - the rule list, the pool each rule draws
 * from, the filter that pool passes through, the value curve each affix rolls
 * on, and the cost of asking. Roll the same seed twice on this page and you
 * get the same item; roll it a hundred times and the distribution is the
 * game's distribution.
 */
(function () {
  'use strict';

  const panel = document.getElementById('sec-forge');
  const stage = document.getElementById('fg-stage');
  if (!panel || !stage) return;                // not this page

  const ROOT = panel.dataset.root;
  /* Every asset here goes out stamped with the data file's own mtime. The
     markup's own ?t= buster cannot reach anything fetched by script or built
     into a style attribute, and a re-extract read out of a stale cache is
     indistinguishable from an extractor that did not run. */
  const STAMP = panel.dataset.stamp || '0';
  const asset = path => ROOT + path + '?v=' + STAMP;
  let D = null;                 // the extracted model, once loaded

  // fast lookups built once the data lands
  const BY = { rarity: {}, affix: {}, gem: {}, item: {}, cat: {} };
  let RARITIES = [];            // ordinal order, which is also power order

  // ── the game's own small maths ─────────────────────────────────────────────

  /* Placebo's StepFunction: a value is not a range, it is a ladder. `level` is
     the affix's stored roll in [0,1) and this picks the rung. The half-step
     offset is the mod's, and it is what makes a roll of 0 land on the bottom
     rung rather than half a rung below it. */
  function stepValue(fn, level) {
    if (typeof fn === 'number') return fn;
    if (!fn) return 0;
    const steps = fn.steps, step = fn.step, min = fn.min;
    return min + Math.trunc(steps * (level + 0.5 / steps)) * step;
  }
  function stepMax(fn) {
    if (typeof fn === 'number') return fn;
    return fn ? fn.min + fn.steps * fn.step : 0;
  }
  function stepMin(fn) {
    return typeof fn === 'number' ? fn : (fn ? fn.min : 0);
  }

  /* Deterministic PRNG, so a seed on this page is a seed. mulberry32 rather
     than Xoroshiro for the reason in the header: the game's stream cannot be
     reproduced without the player's stored seed, and a good uniform generator
     is what the algorithm actually needs. */
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function shuffle(list, rand) {          // Fisher-Yates, as Collections.shuffle
    for (let i = list.length - 1; i > 0; i--) {
      const j = Math.floor(rand() * (i + 1));
      const tmp = list[i]; list[i] = list[j]; list[j] = tmp;
    }
    return list;
  }

  /* ItemStack.ATTRIBUTE_MODIFIER_FORMAT is DecimalFormat("#.##"): at most two
     decimals, and no trailing zeroes at all. */
  function fmt2(value) {
    const rounded = Math.round(value * 100) / 100;
    return String(rounded);
  }
  /* Affix.fmt: whole numbers lose their decimal point entirely. */
  function fmt(value) {
    return value === Math.trunc(value) ? String(Math.trunc(value)) : fmt2(value);
  }

  // ── lang ───────────────────────────────────────────────────────────────────

  function lang(key, fallback) {
    const value = D.lang[key];
    return value === undefined ? (fallback === undefined ? key : fallback) : value;
  }
  /* Minecraft's translate: %s in order, %1$s by index, and %% for a literal
     per cent sign. The last one is not decoration - most of these strings end
     in "%s%%", so a pass that only knows about %s prints "38%%". Both forms
     are matched in the one sweep, because handling them in two passes would
     let a substituted value's own % be read as an escape. */
  function tr(key, ...args) {
    let index = 0;
    return lang(key).replace(/%%|%(?:(\d+)\$)?s/g, (match, pos) => {
      if (match === '%%') return '%';
      return pos ? (args[pos - 1] ?? '') : (args[index++] ?? '');
    });
  }

  // ── categories and the predicates the affix classes hardcode ───────────────

  const isArmor    = c => ['helmet', 'chestplate', 'leggings', 'boots'].includes(c);
  const isBreaker  = c => c === 'pickaxe' || c === 'shovel';
  const isRanged   = c => c === 'bow' || c === 'crossbow' || c === 'trident';
  const isLight    = c => c === 'sword' || c === 'trident';

  function gatePasses(gate, cat) {
    switch (gate) {
      case 'shield':       return cat === 'shield';
      case 'heavy_weapon': return cat === 'heavy_weapon';
      case 'light_weapon': return isLight(cat);
      case 'breaker':      return isBreaker(cat);
      case 'ranged':       return isRanged(cat);
      case 'ranged_light_or_breaker':
        return isRanged(cat) || isLight(cat) || isBreaker(cat);
      default:             return true;
    }
  }

  /* Affix.canApplyTo, generalised over every subclass.
     Two gates, and they are not the same gate. The "types" list in the json is
     a set membership test; the hardcoded one is a method on LootCategory. An
     affix that has neither is not unrestricted - it just has no restriction
     beyond supporting the rarity. */
  function canApply(affix, cat, rarityId) {
    if (affix.type === 'SOCKET' || affix.type === 'DURABILITY') return false;
    if (cat === 'none') return false;
    if (affix.gate) {
      if (!gatePasses(affix.gate, cat)) return false;
    } else if (affix.categories.length && !affix.categories.includes(cat)) {
      return false;
    }
    // the three min_rarity affixes carry no value table at all: they are
    // on or off, and "supports this rarity" means "at least this rarity"
    if (affix.min_rarity) {
      return BY.rarity[rarityId].ordinal >= BY.rarity[affix.min_rarity].ordinal;
    }
    return !!(affix.values && affix.values[rarityId] !== undefined);
  }

  // ── LootController.createLootItem ──────────────────────────────────────────

  /* LootRarity.LootRule.execute.
     The subtlety worth stating: `backup` is not what happens when the chance
     roll fails. A failed roll produces nothing at all. The backup fires only
     when the roll succeeded and the pool for that type came back empty, which
     on this pack is exactly how an Ancient bow gets its fifth line - there are
     only four stat affixes a bow can take, so the fifth stat rule finds
     nothing and falls through to an ability. */
  function execRule(rule, cat, rarity, chosen, sockets, rand) {
    if (rule.type === 'DURABILITY') return;
    if (rand() <= rule.chance) {
      if (rule.type === 'SOCKET') { sockets.n += 1; return; }
      const pool = D.affixes.filter(a =>
        a.type === rule.type && canApply(a, cat, rarity.id) && !chosen.includes(a.id));
      if (!pool.length) {
        if (rule.backup) execRule(rule.backup, cat, rarity, chosen, sockets, rand);
        return;
      }
      shuffle(pool, rand);
      chosen.push(pool[0].id);
    }
  }

  /* The whole of LootController.createLootItem, including the shuffle that
     decides which affix supplies the prefix and which the suffix. */
  function rollItem(base, rarityId, seed) {
    const rarity = BY.rarity[rarityId];
    const rand = rng(seed);
    const chosen = [];
    const sockets = { n: 0 };
    let durability = 0;

    for (const rule of rarity.rules) {
      if (rule.type === 'DURABILITY') { durability = rule.chance; continue; }
      execRule(rule, base.category, rarity, chosen, sockets, rand);
    }

    // every selected affix draws its own roll, in selection order
    const affixes = chosen.map(id => ({ id, level: rand() }));

    if (durability > 0) {
      // the durable affix's own level is the rarity's flat chance plus a
      // wobble of -7% to +7%, in whole percents: AffixHelper.step(-0.07,14,0.01)
      affixes.push({
        id: 'apotheosis:durable',
        level: durability + stepValue({ min: -0.07, steps: 14, step: 0.01 }, rand()),
      });
    }

    const named = affixes.filter(a => a.id !== 'apotheosis:durable');
    shuffle(named, rand);
    const prefix = named.length ? affixName(named[0].id, true) : '';
    const suffix = named.length > 1 ? affixName(named[1].id, false) : '';

    return {
      base, rarity: rarityId, seed,
      affixes, sockets: sockets.n,
      gems: new Array(sockets.n).fill(null),
      prefix, suffix,
    };
  }

  /* An affix's words come from the lang file, and two of them have none: this
     pack adds Bulwarked and Emberlined as new files, and a datapack cannot add
     lang entries the way it adds data. In game those render as the raw
     translation key. Here the id's own stem is title-cased instead, which is
     the name they were plainly meant to have, and the suffix is simply
     absent rather than invented. */
  function affixName(id, prefix) {
    const known = lang('affix.' + id + (prefix ? '' : '.suffix'), '');
    if (known || !prefix) return known;
    return id.split('/').pop().split('_')
      .map(word => capitalise(word)).join('-');
  }

  /* The mixin that produces the display name splices the item's own name into
     the middle of the affix pattern, which is why the pattern has a blank in
     it. Reproduced rather than approximated so a one-affix Common item reads
     "Blessed Iron Helmet" and not "Blessed Iron Helmet of ". */
  function itemName(item) {
    // custom gear carries its own name; everything else is named by the lang
    const base = item.base.name || D.names[item.base.id] || item.base.id;
    if (!item.prefix && !item.suffix) return base;
    if (!item.suffix) return tr('misc.apotheosis.affix_name.two', item.prefix, base);
    return tr('misc.apotheosis.affix_name.three', item.prefix, base, item.suffix);
  }

  // ── attribute lines ────────────────────────────────────────────────────────

  /* IFormattableAttribute.toValueComponent. Whether a modifier reads as "+3"
     or "+15%" is not a property of the number: it is how the attribute was
     registered and what operation the modifier uses. */
  function attrValue(attrId, operation, value) {
    const attr = D.attributes[attrId] || {};
    const addition = !operation || operation === 'ADDITION';
    if (attr.boolean) return value > 0 ? 'Enabled' : 'Disabled';
    if (attr.percent) {
      const scale = addition && attr.addition_scale ? attr.addition_scale : 100;
      return fmt2(value * (addition ? scale : 100)) + '%';
    }
    return addition ? fmt2(value) : fmt2(value * 100) + '%';
  }

  function attrLine(attrId, operation, value) {
    const name = (D.attributes[attrId] || {}).name || attrId;
    const positive = value > 0;
    const text = (positive ? '+' : '-') +
      attrValue(attrId, operation, Math.abs(value)) + ' ' + name;
    return { text, cls: positive ? 'c-blue' : 'c-red' };
  }

  // ── what one affix says on a tooltip ───────────────────────────────────────

  /* Affix.addInformation, dispatched per subclass. Attribute affixes are the
     odd one out: they contribute nothing here, because their effect shows up
     in the item's attribute block instead. */
  function affixLines(affix, rarityId, level, cat) {
    const id = affix.id;
    const values = affix.values && affix.values[rarityId];

    switch (affix.kind) {
      case 'apotheosis:attribute':
        return [];

      case 'apotheosis:damage_reduction': {
        const type = lang('misc.apotheosis.' + affix.damage_type.toLowerCase(),
                          affix.damage_type);
        return [{ text: tr('affix.apotheosis:damage_reduction.desc', type,
                           fmt(100 * stepValue(values, level))) }];
      }

      case 'apotheosis:mob_effect': {
        const duration = Math.trunc(stepValue(values.duration, level));
        const amplifier = Math.trunc(stepValue(values.amplifier, level));
        let effect = D.effects[affix.mob_effect] || affix.mob_effect;
        if (amplifier > 0) {
          effect = tr('potion.withAmplifier', effect,
                      lang('potion.potency.' + amplifier, String(amplifier + 1)));
        }
        if (duration > 20) {
          effect = tr('potion.withDuration', effect, ticks(duration));
        }
        let text = tr('affix.apotheosis.target.' + affix.target.toLowerCase(), effect);
        if (values.cooldown && values.cooldown > 0) {
          text += ' ' + tr('affix.apotheosis.cooldown', ticks(values.cooldown));
        }
        if (affix.stack_on_reapply) text += ' ' + lang('affix.apotheosis.stacking');
        return [{ text, cls: 'c-yellow' }];
      }

      // the specials, each quoting its own class's addInformation
      case 'apotheosis:cleaving': {
        // targets reads a *different* slice of the same roll than chance does,
        // so one affix carries two independent-looking numbers off one level
        const chance = stepValue(values.chance, level);
        const targets = Math.trunc(stepValue(values.targets, (level % 0.5) * 2));
        return [{ text: tr('affix.' + id + '.desc', fmt2(100 * chance), targets),
                  cls: 'c-yellow' }];
      }
      case 'apotheosis:executing':
      case 'apotheosis:festive':
      case 'apotheosis:psychic':
      case 'apotheosis:spectral':
        return [{ text: tr('affix.' + id + '.desc', fmt(100 * stepValue(values, level))) }];
      case 'apotheosis:thunderstruck':
        return [{ text: tr('affix.' + id + '.desc',
                           Math.trunc(stepValue(values, level))) }];
      case 'apotheosis:enlightened':
        return [{ text: tr('affix.' + id + '.desc',
                           Math.trunc(stepValue(values, level))) }];
      case 'apotheosis:omnetic':
        return [{ text: tr('affix.' + id + '.desc',
                           lang('misc.apotheosis.' + values.name, values.name)) }];
      case 'apotheosis:radial': {
        // the value is a list of shapes rather than a curve: the roll indexes it
        const shapes = values || [];
        const shape = shapes[Math.min(shapes.length - 1,
                                      Math.floor(level * shapes.length))] || {};
        return [{ text: tr('affix.' + id + '.desc', shape.x, shape.y) }];
      }
      case 'apotheosis:telepathic': {
        const kind = (isRanged(cat) || cat === 'sword' || cat === 'heavy_weapon')
          ? 'weapon' : 'tool';
        return [{ text: lang('affix.' + id + '.desc.' + kind) }];
      }
      case 'apotheosis:durable':
        // DurableAffix multiplies the level by 100 before handing it to the
        // base class, so the percent sign in the lang string lines up
        return [{ text: tr('affix.' + id + '.desc', fmt(level * 100)) }];
      case 'apotheosis:socket':
        return [{ text: tr('affix.' + id + '.desc', level) }];
      default:
        return [{ text: tr('affix.' + id + '.desc', fmt(level)) }];
    }
  }

  function cooldownTag(ticksCount) {
    return ticksCount > 0 ? tr('affix.apotheosis.cooldown', ticks(ticksCount)) : '';
  }

  /* StringUtil.formatTickDuration: m:ss. */
  function ticks(count) {
    const seconds = Math.floor(count / 20);
    return Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0');
  }

  // ── gems ───────────────────────────────────────────────────────────────────

  function gemRarities(gem) {
    // Gem's constructor derives the bounds from the first bonus's value table
    // when the json does not state them, and clamps every socketed rarity into
    // that window
    const supported = RARITIES.filter(r => bonusSupports(gem.bonuses[0], r.id));
    const min = gem.min_rarity || (supported[0] || RARITIES[0]).id;
    const max = gem.max_rarity ||
      (supported[supported.length - 1] || RARITIES[RARITIES.length - 1]).id;
    return { min, max };
  }
  function clampGemRarity(gem, rarityId) {
    const { min, max } = gemRarities(gem);
    const ord = BY.rarity[rarityId].ordinal;
    if (ord < BY.rarity[min].ordinal) return min;
    if (ord > BY.rarity[max].ordinal) return max;
    return rarityId;
  }
  function bonusSupports(bonus, rarityId) {
    if (!bonus) return false;
    if (bonus.type === 'apotheosis:multi_attribute') {
      return bonus.modifiers[0].values[rarityId] !== undefined;
    }
    return bonus.values && bonus.values[rarityId] !== undefined;
  }
  function gemBonus(gem, cat, rarityId) {
    for (const bonus of gem.bonuses) {
      if (bonus.gem_class && bonus.gem_class.types.includes(cat)
          && bonusSupports(bonus, rarityId)) return bonus;
    }
    return null;
  }
  function gemName(gem, rarityId) {
    // the rarity is a prefix on the gem's own name rather than a separate
    // line: "Flawless Ballast Gem", "Perfect Gem of the Warlord"
    const base = lang('item.apotheosis.gem.' + gem.id, gem.variant);
    return tr('item.apotheosis.gem.apotheosis:' + rarityId, base);
  }

  /* GemBonus.getSocketBonusTooltip, per subclass. */
  function bonusLine(bonus, rarityId) {
    switch (bonus.type) {
      case 'apotheosis:attribute': {
        const value = stepValue(bonus.values[rarityId], 0);
        return attrLine(bonus.attribute, bonus.operation, value);
      }
      case 'apotheosis:multi_attribute': {
        /* MultiAttrBonus builds an argument array twice as long as its
           modifier list: the full "+8% Attack Damage" components first, then
           a bare value for each. The bare half is passed the loop *index*
           rather than the modifier's value - `toValueComponent(attr, op,
           (double) i, flag)` - which is an upstream slip, not one of mine.
           It only shows when a bonus has fewer modifiers than its desc string
           has slots, as this pack's Royalty helmet bonus does: one modifier
           under the two-slot "%s and %s", which renders in game as
           "+8% Attack Damage and 0%". Reproduced rather than tidied, because
           the point of this page is to show what the game shows. */
        const args = bonus.modifiers.map(m =>
          attrLine(m.attribute, m.operation, m.values[rarityId]).text);
        bonus.modifiers.forEach((m, i) =>
          args.push(attrValue(m.attribute, m.operation, i)));
        return { text: tr(bonus.desc, ...args), cls: 'c-yellow' };
      }
      case 'apotheosis:damage_reduction': {
        const type = lang('misc.apotheosis.' + bonus.damage_type.toLowerCase(),
                          bonus.damage_type);
        return { text: tr('affix.apotheosis:damage_reduction.desc', type,
                          fmt(100 * stepValue(bonus.values[rarityId], 0))),
                 cls: 'c-yellow' };
      }
      case 'apotheosis:durability':
        return { text: tr('bonus.apotheosis:durability.desc',
                          fmt(100 * stepValue(bonus.values[rarityId], 0))),
                 cls: 'c-yellow' };
      case 'apotheosis:enchantment': {
        const level = bonus.values[rarityId];
        let key = 'bonus.apotheosis:enchantment.desc';
        if (bonus.global) key += '.global';
        else if (bonus.must_exist) key += '.mustExist';
        const name = D.enchantments[bonus.enchantment] || bonus.enchantment;
        return { text: tr(key, level,
                          lang('misc.apotheosis.level' + (level > 1 ? '.many' : '')),
                          name),
                 cls: 'c-green' };
      }
      case 'apotheosis:mob_effect': {
        const values = bonus.values[rarityId];
        const duration = Math.trunc(stepValue(values.duration, 0));
        const amplifier = Math.trunc(stepValue(values.amplifier, 0));
        let effect = D.effects[bonus.mob_effect] || bonus.mob_effect;
        if (amplifier > 0) {
          effect = tr('potion.withAmplifier', effect,
                      lang('potion.potency.' + amplifier, String(amplifier + 1)));
        }
        if (duration > 20) effect = tr('potion.withDuration', effect, ticks(duration));
        let text = tr('affix.apotheosis.target.' + bonus.target.toLowerCase(), effect);
        if (values.cooldown > 0) {
          text += ' ' + tr('affix.apotheosis.cooldown', ticks(values.cooldown));
        }
        return { text, cls: 'c-yellow' };
      }
      /* The seven bespoke bonuses. There is no generic shape to fall back on
         here: each one's value is a different record and each one's lang
         string takes its arguments in a different order, so guessing from the
         json - multiplying everything by a hundred, say - turns the Ore
         Magnet's "8 durability" into "800%". Each is spelled out against its
         own class's getSocketBonusTooltip. */
      case 'apotheosis:all_stats':
      case 'apotheosis:mageslayer':
        return { text: tr('bonus.' + bonus.type + '.desc',
                          fmt(100 * stepMin(bonus.values[rarityId]))),
                 cls: 'c-yellow' };
      case 'apotheosis:twilight_ore_magnet':
        // a flat durability cost, not a fraction: no hundred anywhere near it
        return { text: tr('bonus.' + bonus.type + '.desc',
                          Math.trunc(stepValue(bonus.values[rarityId], 0))),
                 cls: 'c-yellow' };
      case 'apotheosis:leech_block': {
        const data = bonus.values[rarityId];
        return { text: tr('bonus.' + bonus.type + '.desc',
                          fmt(100 * data.heal_factor), cooldownTag(data.cooldown)),
                 cls: 'c-yellow' };
      }
      case 'apotheosis:twilight_treasure_goblin':
      case 'apotheosis:twilight_fortification': {
        const data = bonus.values[rarityId];
        return { text: tr('bonus.' + bonus.type + '.desc',
                          fmt(100 * data.chance), cooldownTag(data.cooldown)),
                 cls: 'c-yellow' };
      }
      case 'apotheosis:bloody_arrow': {
        const data = bonus.values[rarityId];
        return { text: tr('bonus.' + bonus.type + '.desc',
                          fmt(100 * data.health_cost), fmt(100 * data.damage_mult),
                          cooldownTag(data.cooldown)),
                 cls: 'c-yellow' };
      }
      case 'apotheosis:drop_transform':
        // its lang key is named by the gem rather than by the bonus type
        return { text: tr(bonus.desc,
                          fmt(100 * stepMin(bonus.values[rarityId]))),
                 cls: 'c-yellow' };
      default:
        return { text: bonus.type, cls: 'c-dim' };
    }
  }

  // ── tooltips ───────────────────────────────────────────────────────────────

  const tip = document.getElementById('fg-tip');

  function showTip(lines, event) {
    if (!lines || !lines.length) return hideTip();
    tip.innerHTML = '';
    for (const line of lines) {
      const row = document.createElement('div');
      row.className = 'fg-tip-line ' + (line.cls || '');
      // every string here is drawn from the game's own lang files rather than
      // from anything a visitor typed, but it still goes in as text
      row.textContent = line.text;
      if (line.blank) row.innerHTML = '&nbsp;';
      tip.appendChild(row);
    }
    tip.hidden = false;
    moveTip(event);
  }
  function moveTip(event) {
    if (tip.hidden || !event) return;
    const pad = 16;
    const box = tip.getBoundingClientRect();
    let x = event.clientX + pad, y = event.clientY + pad;
    if (x + box.width > window.innerWidth - 8) x = event.clientX - box.width - pad;
    if (y + box.height > window.innerHeight - 8) y = window.innerHeight - box.height - 8;
    tip.style.left = Math.max(4, x) + 'px';
    tip.style.top = Math.max(4, y) + 'px';
  }
  function hideTip() { tip.hidden = true; }
  document.addEventListener('mousemove', moveTip);

  const RARITY_CLASS = id => 'r-' + id;

  /* The full hover text for a rolled item: name, affix lines, sockets and
     their gems, then the attribute block. Ordered as the game orders it. */
  function itemTooltip(item) {
    const lines = [{ text: itemName(item), cls: RARITY_CLASS(item.rarity) }];
    const cat = item.base.category;

    const modifiers = [];
    for (const inst of item.affixes) {
      const affix = BY.affix[inst.id];
      if (!affix) continue;
      if (affix.kind === 'apotheosis:attribute') {
        modifiers.push(attrLine(affix.attribute, affix.operation,
                                stepValue(affix.values[item.rarity], inst.level)));
      } else {
        lines.push(...affixLines(affix, item.rarity, inst.level, cat));
      }
    }

    if (item.sockets > 0) {
      lines.push({ blank: true, text: '' });
      for (const gemStack of item.gems) {
        if (!gemStack) {
          lines.push({ text: lang('socket.apotheosis.empty'), cls: 'c-dim' });
          continue;
        }
        const gem = BY.gem[gemStack.gem];
        const rarityId = clampGemRarity(gem, gemStack.rarity);
        lines.push({ text: gemName(gem, rarityId), cls: RARITY_CLASS(rarityId) });
        const bonus = gemBonus(gem, cat, rarityId);
        lines.push(bonus
          ? Object.assign({}, bonusLine(bonus, rarityId), { indent: true })
          : { text: 'Invalid Gem Category', cls: 'c-red' });
      }
    }

    if (modifiers.length) {
      lines.push({ blank: true, text: '' });
      lines.push({ text: slotLabel(cat), cls: 'c-dim' });
      lines.push(...modifiers);
    }
    return lines;
  }

  function slotLabel(cat) {
    if (isArmor(cat)) return 'When on ' + BY.cat[cat].name;
    return lang('item.modifiers.mainhand', 'When in Main Hand');
  }

  function gemTooltip(gemStack) {
    const gem = BY.gem[gemStack.gem];
    const rarityId = clampGemRarity(gem, gemStack.rarity);
    const lines = [{ text: gemName(gem, rarityId), cls: RARITY_CLASS(rarityId) }];
    if (gem.unique) lines.push({ text: lang('text.apotheosis.unique'), cls: 'c-unique' });
    lines.push({ blank: true, text: '' });
    lines.push({ text: lang('text.apotheosis.socketable_into'), cls: 'c-socket' });

    const cats = [];
    for (const bonus of gem.bonuses) {
      for (const cat of bonus.gem_class.types) if (!cats.includes(cat)) cats.push(cat);
    }
    cats.sort();
    for (const cat of cats) {
      lines.push({ text: tr('text.apotheosis.dot_prefix', BY.cat[cat].plural),
                   cls: 'c-socket' });
    }
    lines.push({ blank: true, text: '' });

    if (gem.bonuses.length === 1) {
      lines.push({ text: lang('item.modifiers.socket'), cls: 'c-gold' });
      lines.push(bonusLine(gem.bonuses[0], rarityId));
    } else {
      lines.push({ text: lang('item.modifiers.socket_in'), cls: 'c-gold' });
      for (const bonus of gem.bonuses) {
        if (!bonusSupports(bonus, rarityId)) continue;
        const label = lang('gem_class.' + bonus.gem_class.key, bonus.gem_class.key);
        lines.push({ text: tr('text.apotheosis.dot_prefix',
                              label + ': ' + bonusLine(bonus, rarityId).text),
                     cls: 'c-gold' });
      }
    }
    return lines;
  }

  // ── the item's own stat block ──────────────────────────────────────────────

  /* What the piece is actually worth once everything on it is applied.
     `base` is the item with nothing rolled on it; affixes and gems fold in on
     top, so the block reads "9 → 15.25" rather than making you add up a
     tooltip. Attack damage carries the +1 the player's own fist supplies,
     which is why the game's tooltip and a damage number never quite agree
     unless you say which one you mean - this is the item's contribution, the
     way the tooltip states it. */
  const STAT_ORDER = [
    ['attack_damage',        'minecraft:generic.attack_damage'],
    ['attack_speed',         'minecraft:generic.attack_speed'],
    ['armor',                'minecraft:generic.armor'],
    ['armor_toughness',      'minecraft:generic.armor_toughness'],
    ['knockback_resistance', 'minecraft:generic.knockback_resistance'],
  ];

  function statBlock(item) {
    const base = item.base.stats || {};
    const cat = item.base.category;

    /* Attribute modifiers arrive as three operations and the game applies them
       in that order: every ADDITION, then MULTIPLY_BASE against the original
       base, then MULTIPLY_TOTAL against the running total. Summing them into
       one number would put a +15% crit chance and a +3 attack damage in the
       same pile. */
    const add = {}, mulBase = {}, mulTotal = {};
    const bump = (attr, op, value) => {
      const into = op === 'MULTIPLY_TOTAL' ? mulTotal
                 : op === 'MULTIPLY_BASE' ? mulBase : add;
      into[attr] = (into[attr] || 0) + value;
    };

    for (const inst of item.affixes) {
      const affix = BY.affix[inst.id];
      if (!affix || affix.kind !== 'apotheosis:attribute') continue;
      bump(affix.attribute, affix.operation,
           stepValue(affix.values[item.rarity], inst.level));
    }
    for (const gemStack of item.gems) {
      if (!gemStack) continue;
      const gem = BY.gem[gemStack.gem];
      const rarityId = clampGemRarity(gem, gemStack.rarity);
      const bonus = gemBonus(gem, cat, rarityId);
      if (!bonus) continue;
      if (bonus.type === 'apotheosis:attribute') {
        bump(bonus.attribute, bonus.operation, stepValue(bonus.values[rarityId], 0));
      } else if (bonus.type === 'apotheosis:multi_attribute') {
        for (const mod of bonus.modifiers) {
          bump(mod.attribute, mod.operation, mod.values[rarityId]);
        }
      }
    }

    const touched = new Set([...Object.keys(add), ...Object.keys(mulBase),
                             ...Object.keys(mulTotal)]);
    const rows = [];

    // the named stats first, in the order a vanilla tooltip lists them, so a
    // sword's damage is always the top line
    for (const [key, attr] of STAT_ORDER) {
      const baseValue = base[key];
      if (baseValue === undefined && !touched.has(attr)) continue;
      // an unknown base is not a base of zero. Twilight Forest's tiers are not
      // read out of its jar, so a fiery sword shown as "0 -> 4.75" would read
      // as a sword that hits for 4.75 rather than one hitting 4.75 harder than
      // it did. Where there is no base, only the gain is printed.
      const known = baseValue !== undefined;
      rows.push(statRow(attr, known ? baseValue : 0, add, mulBase, mulTotal, known));
      touched.delete(attr);
    }
    // then everything an affix or gem added that the item had none of
    for (const attr of [...touched].sort()) {
      rows.push(statRow(attr, 0, add, mulBase, mulTotal, false));
    }

    if (base.durability) {
      // the Durable affix does not raise the number, it makes each point last
      // longer, and several of them stack the way the mod stacks them:
      // chance = chance + (1 - chance) * next
      let saved = 0;
      for (const inst of item.affixes) {
        if (inst.id === 'apotheosis:durable') saved += (1 - saved) * inst.level;
      }
      for (const gemStack of item.gems) {
        if (!gemStack) continue;
        const gem = BY.gem[gemStack.gem];
        const rarityId = clampGemRarity(gem, gemStack.rarity);
        const bonus = gemBonus(gem, cat, rarityId);
        if (bonus && bonus.type === 'apotheosis:durability') {
          saved += (1 - saved) * stepMin(bonus.values[rarityId]);
        }
      }
      // the Durable affix never raises the number, so showing "2031 -> 2031"
      // would be noise: the point is the share of damage that never lands
      rows.push(plainRow('Durability', fmt2(base.durability)));
      if (saved > 0) {
        rows.push({ name: 'Durability damage ignored', base: null,
                    total: fmt2(saved * 100) + '%', up: true });
      }
    }
    return rows;
  }

  function statRow(attr, baseValue, add, mulBase, mulTotal, showBase) {
    const info = D.attributes[attr] || { name: attr };
    const flat = add[attr] || 0;
    const scale = (1 + (mulBase[attr] || 0)) * (1 + (mulTotal[attr] || 0));
    const total = (baseValue + flat) * scale;
    // a BooleanAttribute has no number worth printing: the game says Enabled
    const show = value => info.boolean
      ? (value > 0 ? 'Enabled' : 'Disabled')
      : (info.percent ? fmt2(value * (info.addition_scale || 100)) + '%'
                      : fmt2(value));

    /* A percentage of a base this page does not have is not zero, it is
       unknown. Gravity and the reach attributes have real non-zero bases the
       game supplies and nothing in the mod files states, so a -40% modifier
       against a base of 0 would compute a confident, wrong "0". Where the
       only modifiers are multiplicative and there is no base to multiply, the
       honest thing to print is the multiplier. */
    if (!showBase && flat && scale === 1) {
      return { name: info.name, base: null,
               total: (flat > 0 ? '+' : '') + show(flat), up: flat > 0 };
    }
    if (!showBase && scale !== 1) {
      return { name: info.name, base: null,
               total: (scale > 1 ? '+' : '') + fmt2((scale - 1) * 100) + '%',
               up: scale > 1 };
    }
    const changed = Math.abs(total - baseValue) > 1e-9;
    return {
      name: info.name,
      base: showBase ? show(baseValue) : null,
      total: changed ? show(total) : (showBase ? null : show(total)),
      up: total > baseValue,
    };
  }

  function plainRow(name, value) {
    return { name, base: null, total: value, up: false };
  }

  // ── the panel ──────────────────────────────────────────────────────────────

  const SCALE = 2;                       // the game's own pixels, doubled
  // The container, in two pieces. GUI_BODY is everything down to the last
  // offer strip; GUI_CAP is the container's own bottom border, taken from the
  // foot of the same sheet and put back under it so the panel is a closed box
  // rather than a screenshot with a torn edge.
  const GUI_BODY = 72;
  // seven rows: four of panel, two of the bevel's shadow, one of the black
  // outline. An eighth would reach into the hotbar the sheet draws below it
  const GUI_CAP  = 7;
  const px = n => (n * SCALE) + 'px';

  /* A rectangle blitted out of the game's own 256x256 reforge sheet, at the
     source coordinates ReforgingScreen uses. */
  function sheet(sx, sy, w, h) {
    const el = document.createElement('div');
    el.className = 'fg-blit';
    el.style.width = px(w);
    el.style.height = px(h);
    el.style.backgroundImage = `url(${asset('gui/' + D.gui.reforge)})`;
    el.style.backgroundSize = px(256) + ' ' + px(256);
    el.style.backgroundPosition = `-${sx * SCALE}px -${sy * SCALE}px`;
    return el;
  }
  function place(el, x, y) {
    el.style.left = px(x);
    el.style.top = px(y);
    return el;
  }
  /* An item's icon, and where the game animates it, the animation.

     Fifteen of these textures move in-game: gem dust, the Mythic and Ancient
     materials, and the six gems whose whole character is that they are lit.
     The extractor bakes each one's mcmeta - the playback order, the repeats
     and the interpolated cross-fades - down to a constant-rate filmstrip, so
     running it here is one steps() keyframe over background-position and no
     per-texture logic at all. A still icon stays an <img>; only a moving one
     pays for a background layer. */
  function iconImg(id, cls) {
    const anim = D.anims && D.anims[id];
    if (!anim || !D.icons[id]) {
      const img = document.createElement('img');
      img.className = 'fg-icon ' + (cls || '');
      if (D.icons[id]) img.src = asset('icons/' + D.icons[id]);
      img.alt = '';
      return img;
    }
    const el = document.createElement('i');
    el.className = 'fg-icon anim ' + (cls || '');
    el.style.backgroundImage = `url(${asset('icons/' + D.icons[id])})`;
    el.style.setProperty('--frames', anim.frames);
    /* steps(n, jump-none) yields exactly n output values, 0 to 1 inclusive -
       so the step count is the frame count, not one less than it. Passing
       frames-1 (the count you would want for the default `end` behaviour)
       lands on frames-1 rungs and silently drops the last tile of every
       strip. jump-none is what puts both ends of the film on screen. */
    el.style.setProperty('--steps', Math.max(2, anim.frames));
    el.style.setProperty('--dur', anim.seconds + 's');
    return el;
  }

  function option(value, text) {
    const el = document.createElement('option');
    el.value = value;
    el.textContent = text;
    return el;
  }
  function field(labelText, control) {
    const wrap = document.createElement('label');
    wrap.className = 'fg-field';
    const name = document.createElement('span');
    name.textContent = labelText;
    wrap.appendChild(name);
    wrap.appendChild(control);
    return wrap;
  }


  /* Pick a piece, pick a tier, socket what the roll left room for, read what
     comes out.

     The container is the game's own texture, and it is 176 game pixels wide
     whatever the panel around it is. That is why the three offers inside it
     carry a shape rather than a name: "Thunderstruck Netherite Sword of
     Weakness" does not fit in a hundred and fifty pixels at any size, and a
     name cut off after two words is worse than no name. What you are actually
     choosing between is how the roll came out - four stats or three, two
     sockets or none - and that fits, and reads at a glance. The full name and
     everything under it is one hover away, and sits in the panel beside it
     for whichever offer is taken. */
  function stationForge() {
    const wrap = document.createElement('div');
    wrap.className = 'fg-forge';

    const state = {
      // Gear of your own is the case this page is nearly always opened for:
      // the pack's real endgame armour comes from a dozen mods Apotheosis has
      // never heard of and will still happily reforge. Vanilla is the
      // reference shelf beside it, not the front door.
      itemId: CUSTOM_ID,
      rarity: 'mythic',
      seed: (Math.random() * 1e9) | 0,
      pick: 0,                            // which of the three offers is taken
      gems: [],                           // {id, rarity} per socket, or null
    };

    // ── controls ────────────────────────────────────────────────────────────
    const controls = document.createElement('div');
    controls.className = 'fg-controls';

    /* Two ways in, as a switch rather than as one select with an odd entry at
       the top. The old list mixed a piece you describe yourself in among
       seventy you pick, and buried it under every Twilight Forest tier as
       well - knightmetal, steeleaf, ironwood and fiery, none of which anyone
       reforges on this server. What is left is vanilla, which is worth having
       because its numbers are the ones everybody knows by heart, and yours. */
    const modes = document.createElement('div');
    modes.className = 'fg-modes';
    const modeBtns = {};
    for (const [key, label, note] of [
      ['custom',  'Your gear',    'describe any piece'],
      ['vanilla', 'Vanilla gear', 'the reference shelf'],
    ]) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'fg-mode';
      btn.innerHTML = '<b></b><i></i>';
      btn.firstChild.textContent = label;
      btn.lastChild.textContent = note;
      btn.addEventListener('click', () => {
        state.itemId = key === 'custom' ? CUSTOM_ID : itemPick.value;
        state.gems = [];
        reroll();
      });
      modeBtns[key] = btn;
      modes.appendChild(btn);
    }
    controls.appendChild(modes);

    const picks = document.createElement('div');
    picks.className = 'fg-picks';

    const itemPick = document.createElement('select');
    for (const cat of D.categories) {
      const group = document.createElement('optgroup');
      group.label = cat.plural;
      for (const item of vanillaItems()) {
        if (item.category !== cat.id) continue;
        group.appendChild(option(item.id, D.names[item.id] || item.id));
      }
      if (group.children.length) itemPick.appendChild(group);
    }
    itemPick.value = 'minecraft:netherite_sword';
    if (!itemPick.value) itemPick.value = vanillaItems()[0].id;
    itemPick.addEventListener('change', () => {
      state.itemId = itemPick.value;
      state.gems = [];
      reroll();
    });
    const gearField = field('Vanilla piece', itemPick);
    gearField.className += ' fg-vanilla-field';
    picks.appendChild(gearField);

    const rarityPick = document.createElement('select');
    for (const rarity of RARITIES) {
      rarityPick.appendChild(option(rarity.id, capitalise(rarity.id)));
    }
    rarityPick.value = state.rarity;
    rarityPick.className = RARITY_CLASS(state.rarity);
    rarityPick.addEventListener('change', () => {
      state.rarity = rarityPick.value;
      rarityPick.className = RARITY_CLASS(state.rarity);
      state.gems = [];
      reroll();
    });

    const rollBtn = document.createElement('button');
    rollBtn.className = 'fg-roll';
    rollBtn.innerHTML = '<span>Reroll</span>';
    rollBtn.addEventListener('click', () => {
      state.seed = (Math.random() * 1e9) | 0;
      state.gems = [];
      rollBtn.classList.remove('spun');
      // restart the strike rather than let a second press land on a running
      // animation and do nothing visible
      void rollBtn.offsetWidth;
      rollBtn.classList.add('spun');
      reroll();
    });

    picks.appendChild(field('Tier', rarityPick));
    picks.appendChild(rollBtn);
    controls.appendChild(picks);

    const editor = customEditor(() => { state.gems = []; reroll(); });
    controls.appendChild(editor.el);
    wrap.appendChild(controls);

    /* Three columns: the table, the sockets beside it, and what came out.

       The sockets used to sit *under* the table in the same narrow column,
       which is the one place on this panel that could not afford them - the
       table is a fixed 352 pixels and cannot give any of it back, so three
       socket cards stacked under it ran the whole panel a few hundred pixels
       taller for a strip of empty space beside them. Put beside the table
       they cost no height at all and fill width that was already going
       spare. */
    const body = document.createElement('div');
    body.className = 'fg-body';

    const make = document.createElement('div');
    make.className = 'fg-make';

    /* The container, closed. It is drawn out of the sheet in two pieces: the
       body down to the last offer row, and the container's own bottom edge
       under it. Cutting it off at the offer rows and leaving it there was a
       screenshot with a torn edge - the game's own border is right there in
       the sheet, seven rows of it, and putting it back costs one more blit. */
    const gui = document.createElement('div');
    gui.className = 'fg-gui';
    gui.style.width = px(176);
    gui.style.height = px(GUI_BODY + GUI_CAP);
    gui.appendChild(place(sheet(0, 0, 176, GUI_BODY), 0, 0));
    gui.appendChild(place(sheet(0, 159, 176, GUI_CAP), 0, GUI_BODY));
    gui.appendChild(guiLabel(lang('container.apotheosis.reforge', 'Reforge'), 8, 5));

    const slotLayer = document.createElement('div');
    gui.appendChild(slotLayer);
    const rowLayer = document.createElement('div');
    gui.appendChild(rowLayer);
    make.appendChild(gui);

    body.appendChild(make);

    const socketCol = document.createElement('div');
    socketCol.className = 'fg-socket-col';
    body.appendChild(socketCol);

    const result = document.createElement('div');
    result.className = 'fg-result';
    body.appendChild(result);
    wrap.appendChild(body);

    // ── drawing ─────────────────────────────────────────────────────────────
    let rolls = [];

    function baseItem() {
      if (state.itemId === CUSTOM_ID) return customItem;
      // an id that names nothing would throw all the way up through reroll()
      // and leave the panel frozen on its last draw for the rest of the
      // session, so it falls back to the piece you can always describe
      return BY.item[state.itemId] || customItem;
    }

    function reroll() {
      const custom = state.itemId === CUSTOM_ID;
      const base = baseItem();
      editor.sync(custom);
      modeBtns.custom.classList.toggle('on', custom);
      modeBtns.vanilla.classList.toggle('on', !custom);
      gearField.classList.toggle('off', custom);
      // the three offers, each its own roll off the one seed, exactly as
      // ReforgingScreen.recomputeChoices builds them
      rolls = [0, 1, 2].map(row =>
        rollItem(base, state.rarity, (state.seed ^ (row * 0x45D9F3B)) | 0));
      if (state.pick >= rolls.length) state.pick = 0;
      state.gems.length = rolls[state.pick].sockets;
      draw();
    }

    /* A socket holds {id, rarity}, and that rarity is the gem's own. The item
       and the gem in it are two separate finds in the game - a Common sword
       will happily carry a Perfect gem - so tying them together hid the most
       interesting thing a socket can do. */
    function chosen() {
      const item = cloneItem(rolls[state.pick]);
      item.gems = item.gems.map((_, i) => state.gems[i]
        ? { kind: 'gem', gem: state.gems[i].id,
            rarity: state.gems[i].rarity, count: 1 }
        : null);
      return item;
    }

    function draw() {
      drawSlots();
      drawOffers();
      drawSockets();
      drawResult();
    }

    /* The table's own three slots, holding what this reforge actually costs.

       They used to hold the tier's base cost while a separate "Cost ×2" box
       under the table did the multiplying, which meant the two disagreed on
       screen for every row but the first, and the box was a third place to
       look for a number the container already had a slot for. The slots are
       the cost now: choose Mythic and the third row and the material slot
       says 36, the dust slot says 48, and the row itself says 900 levels. */
    function drawSlots() {
      slotLayer.innerHTML = '';
      const recipe = D.recipes.reforging[state.rarity];
      const base = baseItem();
      const mult = state.pick + 1;
      const filling = [
        [25, 24, D.icons[base.id] ? base.id : null, 0, itemLabel(base)],
        [15, 45, BY.rarity[state.rarity].material,
         recipe ? recipe.material_cost * mult : 0],
        [35, 45, 'apotheosis:gem_dust', recipe ? recipe.dust_cost * mult : 0],
      ];
      for (const [x, y, id, count, title] of filling) {
        const cell = document.createElement('div');
        cell.className = 'fg-slot';
        place(cell, x, y);
        cell.style.width = px(16);
        cell.style.height = px(16);
        if (id) {
          cell.appendChild(iconImg(id));
        } else {
          // custom gear has no icon of its own: the slot says what it is
          const mark = document.createElement('span');
          mark.className = 'fg-slot-mark';
          mark.textContent = '?';
          cell.appendChild(mark);
        }
        // a cost of one still gets its badge, unlike an inventory stack: the
        // number is the point of the slot here, not incidental to it
        if (count) {
          const badge = document.createElement('b');
          badge.textContent = count;
          // the count re-keys on every redraw so the tick is seen, not just
          // arrived at
          badge.className = 'tick';
          cell.appendChild(badge);
        }
        const name = title || D.names[id] || id;
        cell.addEventListener('mouseenter', e => showTip(
          [{ text: count ? count + ' × ' + name : name }], e));
        cell.addEventListener('mouseleave', hideTip);
        slotLayer.appendChild(cell);
      }
    }

    /* The three offers, in the strips the screen blits them to. Each carries
       the shape of its roll rather than its name: stats, abilities and
       sockets as pips, which is what you are choosing between and what fits. */
    function drawOffers() {
      rowLayer.innerHTML = '';
      for (let row = 0; row < 3; row++) {
        const active = row === state.pick;
        // src y 166 is the resting strip, 204 the highlighted one
        const strip = place(sheet(0, active ? 204 : 166, 108, 19), 60, 14 + 19 * row);
        strip.className += ' fg-row' + (active ? ' on' : '');
        /* The tier gem, blitted from the sheet's own 16x16 cell. The cell starts
           at y=224, not 223: sampling a row high took in a blank row above the
           gem and dropped the bottom row of its cell, which pushed it a pixel
           down inside its box. The gems themselves are 9x9, 9x11 and 11x13 in
           the mod's texture - they grow mostly downward as the tier climbs,
           which is Apotheosis' art rather than anything this page does to it. */
        const badge = place(sheet(16 * row, 224, 16, 16), 61, 15 + 19 * row);
        badge.className += ' fg-badge';

        const shape = document.createElement('div');
        shape.className = 'fg-shape';
        place(shape, 79, 15 + 19 * row);
        const preview = rolls[row];
        const counts = rollShape(preview);
        for (const [kind, n] of counts) {
          for (let i = 0; i < n; i++) {
            const pip = document.createElement('i');
            pip.className = 'sh ' + kind;
            shape.appendChild(pip);
          }
        }
        /* The level cost for this row, in the tier's own colour with the hard
           outline the screen draws it with. This is the slot the game puts a
           number in too, and it is worth more than the "x2" that was there:
           the multiplier is obvious from the row, the three hundred levels
           are not. */
        const recipe = D.recipes.reforging[state.rarity];
        const levels = recipe ? recipe.level_cost * (row + 1) : 0;
        const mult = guiLabel(levels + ' lvl', 60 + 100, 18 + 19 * row, 'fg-mult');
        mult.style.color = rarityColour(state.rarity);

        strip.addEventListener('mouseenter', e => showTip(itemTooltip(preview), e));
        strip.addEventListener('mouseleave', hideTip);
        strip.addEventListener('click', () => {
          state.pick = row;
          state.gems = new Array(rolls[row].sockets).fill(null);
          draw();
        });
        rowLayer.append(strip, badge, shape, mult);
      }
    }

    function drawSockets() {
      socketCol.innerHTML = '';
      const item = rolls[state.pick];

      const head = document.createElement('h4');
      head.textContent = item.sockets ? 'Sockets (' + item.sockets + ')' : 'Sockets';
      socketCol.appendChild(head);

      if (!item.sockets) {
        const none = document.createElement('p');
        none.className = 'fg-nosocket';
        none.textContent = BY.rarity[state.rarity].rules.some(r => r.type === 'SOCKET')
          ? 'None this roll.' : 'Never at this tier.';
        socketCol.appendChild(none);
        return;
      }

      // only gems that fit this item: the smithing table refuses the rest, so
      // offering them would be a lie
      const usable = D.gems
        .map(gem => {
          const rarityId = clampGemRarity(gem, state.rarity);
          const bonus = gemBonus(gem, item.base.category, rarityId);
          return bonus && { gem, rarityId, line: bonusLine(bonus, rarityId).text };
        })
        .filter(Boolean);

      for (let i = 0; i < item.sockets; i++) {
        const held = state.gems[i];
        const heldGem = held && BY.gem[held.id];

        const card = document.createElement('div');
        card.className = 'fg-socket' + (heldGem ? ' full' : '');

        const face = document.createElement('div');
        face.className = 'fg-socket-face';
        const well = document.createElement('div');
        well.className = 'fg-socket-well';
        if (heldGem) {
          well.appendChild(iconImg(heldGem.id));
          well.style.setProperty('--tier', rarityColour(held.rarity));
          well.addEventListener('mouseenter', e => showTip(
            gemTooltip({ kind: 'gem', gem: heldGem.id,
                         rarity: held.rarity, count: 1 }), e));
          well.addEventListener('mouseleave', hideTip);
        }
        face.appendChild(well);

        const bodyEl = document.createElement('div');
        bodyEl.className = 'fg-socket-body';

        const pick = document.createElement('select');
        pick.appendChild(option('', 'empty socket'));
        for (const entry of usable) {
          // the effect rides along in the option, so choosing is not picking
          // blind and then reading back what you got
          pick.appendChild(option(entry.gem.id,
            gemShort(entry.gem) + ' · ' + entry.line));
        }
        pick.value = held ? held.id : '';
        pick.addEventListener('change', () => {
          const gem = BY.gem[pick.value];
          if (!gem) { state.gems[i] = null; draw(); return; }
          // a Unique gem cannot go in twice, the rule Gem.canApplyTo has
          if (gem.unique && state.gems.some((g, j) => j !== i && g && g.id === gem.id)) {
            pick.value = held ? held.id : '';
            flash(pick, gemShort(gem) + ' is Unique.');
            return;
          }
          state.gems[i] = { id: gem.id, rarity: clampGemRarity(gem, state.rarity) };
          draw();
        });
        bodyEl.appendChild(pick);

        if (heldGem) {
          const name = document.createElement('b');
          name.className = RARITY_CLASS(held.rarity);
          name.textContent = gemName(heldGem, held.rarity);
          bodyEl.appendChild(name);

          /* The gem's own tier. A gem is found and cut apart from the gear it
             goes in, so any tier it supports can sit in any item, and the gap
             between a Cracked and a Perfect one is most of what a socket is
             worth. */
          const band = document.createElement('div');
          band.className = 'fg-socket-band';
          const { min, max } = gemRarities(heldGem);
          for (const rarity of RARITIES) {
            if (rarity.ordinal < BY.rarity[min].ordinal
                || rarity.ordinal > BY.rarity[max].ordinal) continue;
            const pip = document.createElement('button');
            pip.type = 'button';
            pip.className = 'fg-pip' + (rarity.id === held.rarity ? ' on' : '');
            pip.style.setProperty('--tier', rarityColour(rarity.id));
            pip.title = capitalise(rarity.id);
            pip.addEventListener('click', () => {
              state.gems[i] = { id: heldGem.id, rarity: rarity.id };
              draw();
            });
            band.appendChild(pip);
          }
          bodyEl.appendChild(band);

          const what = document.createElement('span');
          what.className = 'fg-socket-what';
          what.textContent = bonusLine(
            gemBonus(heldGem, item.base.category, held.rarity), held.rarity).text;
          bodyEl.appendChild(what);
        }

        face.appendChild(bodyEl);
        card.appendChild(face);
        socketCol.appendChild(card);
      }
    }

    function drawResult() {
      const item = chosen();
      result.innerHTML = '';

      const tipBox = document.createElement('div');
      tipBox.className = 'fg-tipbox';
      for (const line of itemTooltip(item)) {
        const el = document.createElement('div');
        el.className = 'fg-tip-line ' + (line.cls || '');
        if (line.blank) el.innerHTML = '&nbsp;';
        else el.textContent = line.text;
        tipBox.appendChild(el);
      }
      result.appendChild(tipBox);

      const rows = statBlock(item);
      if (rows.length) {
        const stats = document.createElement('div');
        stats.className = 'fg-stats';
        const head = document.createElement('h4');
        head.textContent = 'Stats';
        stats.appendChild(head);
        for (const row of rows) {
          const line = document.createElement('div');
          line.className = 'fg-stat';
          const name = document.createElement('i');
          name.textContent = row.name;
          line.appendChild(name);
          if (row.base !== null && row.total) {
            const from = document.createElement('s');
            from.textContent = row.base;
            const to = document.createElement('b');
            to.className = row.up ? 'up' : 'down';
            to.textContent = row.total;
            line.append(from, to);
          } else {
            const only = document.createElement('b');
            // green only where the roll put the number there; a stat the item
            // simply has is not an improvement on anything
            only.className = row.up ? 'up' : '';
            only.textContent = row.total || row.base;
            line.appendChild(only);
          }
          stats.appendChild(line);
        }
        if (!item.base.stats || !Object.keys(item.base.stats).length) {
          const note = document.createElement('p');
          note.className = 'fg-statnote';
          note.textContent = 'Base numbers unknown for modded gear.';
          stats.appendChild(note);
        }
        result.appendChild(stats);
      }
    }

    reroll();
    return wrap;
  }

  /* How a roll came out, as three counts. This is the whole of what separates
     one offer from another - the tier is the same for all three - so it is
     what the strips carry. */
  function rollShape(item) {
    let stats = 0, abilities = 0;
    for (const inst of item.affixes) {
      const affix = BY.affix[inst.id];
      if (!affix) continue;
      if (affix.type === 'STAT') stats++;
      else if (affix.type === 'ABILITY') abilities++;
    }
    return [['stat', stats], ['ability', abilities], ['socket', item.sockets]];
  }

  // ── gear of your own ───────────────────────────────────────────────────────
  //
  // The mod's own affix loot pool is real gear across every dimension, but it
  // is not the gear anyone here reforges: it is vanilla plus four Twilight
  // Forest tiers - knightmetal, steeleaf, ironwood, fiery - and the endgame
  // on this server is none of those. It is amethyst and Cataclysm and a dozen
  // mods Apotheosis has never heard of and will still happily reforge, because
  // anything with a LootCategory qualifies.
  //
  // So the list is cut to vanilla, whose numbers everybody knows by heart and
  // which is therefore worth having as a reference, and the piece you describe
  // yourself is promoted from an odd entry at the bottom of a select to one of
  // the two ways in. That one is the ninety-per-cent case.

  const VANILLA_NS = 'minecraft:';
  function vanillaItems() {
    return D.items.filter(item => item.id.startsWith(VANILLA_NS));
  }

  const CUSTOM_ID = '__custom__';
  const customItem = {
    id: CUSTOM_ID, name: 'Custom gear', category: 'chestplate',
    stats: { armor: 8, armor_toughness: 2, durability: 528 },
  };

  /* Filling in four numbers by hand to describe a chestplate is the tax on
     using this page at all, so the numbers are one press away: the vanilla
     pieces of the same slot, offered as a starting point to edit down or up
     from. Modded endgame armour is nearly always somewhere near netherite,
     and "netherite plus two armour" is a far quicker thing to type than the
     whole set. */
  const PRESET_TIERS = ['netherite', 'diamond', 'iron'];
  function presetsFor(cat) {
    const out = [];
    for (const tier of PRESET_TIERS) {
      const item = D.items.find(i => i.category === cat
        && i.id.startsWith(VANILLA_NS) && i.id.includes(tier));
      if (item && item.stats && Object.keys(item.stats).length) {
        out.push({ id: item.id, label: capitalise(tier), stats: item.stats });
      }
    }
    return out;
  }

  // which numbers are worth asking for, per category: nobody wants to be asked
  // for a chestplate's attack speed
  const CUSTOM_FIELDS = {
    armour: [['armor', 'Armor'], ['armor_toughness', 'Toughness'],
             ['durability', 'Durability']],
    weapon: [['attack_damage', 'Attack damage'], ['attack_speed', 'Attack speed'],
             ['durability', 'Durability']],
    plain:  [['durability', 'Durability']],
  };
  function customShape(cat) {
    if (isArmor(cat)) return CUSTOM_FIELDS.armour;
    if (cat === 'shield' || cat === 'bow' || cat === 'crossbow') {
      return CUSTOM_FIELDS.plain;
    }
    return CUSTOM_FIELDS.weapon;
  }

  function itemLabel(base) {
    return base.id === CUSTOM_ID ? base.name : (D.names[base.id] || base.id);
  }

  /* The editor, folded away until the custom piece is the one selected. */
  function customEditor(onChange) {
    const el = document.createElement('div');
    el.className = 'fg-custom';

    const name = document.createElement('input');
    name.type = 'text';
    name.value = customItem.name;
    name.addEventListener('input', () => {
      customItem.name = name.value || 'Custom gear';
      onChange();
    });

    const catPick = document.createElement('select');
    for (const cat of D.categories) catPick.appendChild(option(cat.id, cat.name));
    catPick.value = customItem.category;
    catPick.addEventListener('change', () => {
      customItem.category = catPick.value;
      // the numbers asked for change with the slot, and a chestplate's armour
      // is not a sword's damage: start the new shape clean rather than
      // carrying values that no longer mean anything
      customItem.stats = {};
      paintStats();
      onChange();
    });

    const top = document.createElement('div');
    top.className = 'fg-custom-top';
    top.appendChild(field('Name', name));
    top.appendChild(field('Slot', catPick));
    el.appendChild(top);

    const nums = document.createElement('div');
    nums.className = 'fg-custom-nums';
    el.appendChild(nums);

    // one press to start from a piece whose numbers are already known, rather
    // than four boxes to fill from memory
    const quick = document.createElement('div');
    quick.className = 'fg-presets';
    el.appendChild(quick);

    function paintStats() {
      nums.innerHTML = '';
      for (const [key, label] of customShape(customItem.category)) {
        const input = document.createElement('input');
        input.type = 'number';
        input.min = '0';
        input.step = key === 'attack_speed' ? '0.1' : '1';
        input.value = customItem.stats[key] ?? '';
        input.placeholder = '0';
        input.addEventListener('input', () => {
          const value = parseFloat(input.value);
          if (Number.isFinite(value)) customItem.stats[key] = value;
          else delete customItem.stats[key];
          onChange();
        });
        nums.appendChild(field(label, input));
      }
      paintPresets();
    }

    function paintPresets() {
      quick.innerHTML = '';
      const list = presetsFor(customItem.category);
      if (!list.length) return;
      const lead = document.createElement('span');
      lead.className = 'fg-presets-lead';
      lead.textContent = 'Start from';
      quick.appendChild(lead);
      for (const preset of list) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'fg-preset';
        btn.appendChild(iconImg(preset.id, 'sm'));
        const text = document.createElement('span');
        text.textContent = preset.label;
        btn.appendChild(text);
        btn.title = 'Copy the numbers off a ' + (D.names[preset.id] || preset.id);
        btn.addEventListener('click', () => {
          customItem.stats = Object.assign({}, preset.stats);
          paintStats();
          onChange();
        });
        quick.appendChild(btn);
      }
    }
    paintStats();

    return {
      el,
      sync(on) { el.classList.toggle('on', on); },
    };
  }

  function guiLabel(text, x, y, cls) {
    const el = document.createElement('span');
    el.className = 'fg-label ' + (cls || '');
    el.textContent = text;
    place(el, x, y);
    return el;
  }
  function capitalise(text) {
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  /* Movement, added to something already on screen and readable without it.

     Everything animated from script on this page goes through here so the two
     ways it can be unwanted are handled in one place: the reduced-motion
     setting, and a browser with no Web Animations API at all. In both cases
     the element keeps its resting appearance and nothing is hidden - which is
     the whole reason these are not CSS keyframes with a `backwards` fill. */
  const REDUCED = window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)');
  function motion(el, frames, options) {
    if (!el || !el.animate || (REDUCED && REDUCED.matches)) return null;
    let anim;
    try {
      anim = el.animate(frames, options);
    } catch (error) {
      return null;                       // an old browser, and no harm done
    }
    /* A fade-in holds its element at opacity 0 for as long as the animation
       sits at its first keyframe, and an animation only leaves that keyframe
       when the document timeline advances. Every real browser advances it;
       a surface that has paused rendering does not, and there the fade would
       never finish and the card would never appear.

       So the end state is guaranteed off setTimeout, which runs on the wall
       clock and owes the animation timeline nothing. If the animation ran
       normally it has long since finished and this is a no-op. */
    const life = (options.delay || 0) + (options.duration || 0) + 250;
    if (Number.isFinite(life)) {
      setTimeout(() => {
        try { if (anim.playState !== 'finished') anim.finish(); } catch (e) { /* gone */ }
      }, life);
    }
    return anim;
  }
  function cloneItem(item) {
    return Object.assign({}, item, {
      affixes: item.affixes.map(a => Object.assign({}, a)),
      gems: item.gems.slice(),
    });
  }
  function flash(el, message) {
    const note = document.createElement('span');
    note.className = 'fg-flash';
    note.textContent = message;
    el.parentNode.appendChild(note);
    setTimeout(() => note.remove(), 2600);
  }

  // ── the catalog ────────────────────────────────────────────────────────────
  //
  // The half of this panel people actually read. Three views rather than one
  // long scroll, because "which gem should go in my sword" and "what can a
  // mythic axe roll" are different questions and neither is served by making
  // you scroll past the other.

  let catView = 'gems';
  const catState = {
    gemSearch: '', gemCat: '', gemOpen: null,
    afxSearch: '', afxCat: '', afxTier: 'mythic', afxType: '', afxOpen: null,
  };

  function catalog() {
    const wrap = document.createElement('div');
    wrap.className = 'fg-catalog';

    const nav = document.createElement('nav');
    nav.className = 'fg-subnav';
    for (const [key, name] of [['gems', 'Gems'], ['affixes', 'Affixes'],
                               ['tiers', 'Tiers & Costs']]) {
      const btn = document.createElement('button');
      btn.className = 'fg-sub' + (key === catView ? ' active' : '');
      btn.textContent = name;
      btn.addEventListener('click', () => { catView = key; renderTab('catalog'); });
      nav.appendChild(btn);
    }
    wrap.appendChild(nav);

    wrap.appendChild(catView === 'affixes' ? affixView()
                   : catView === 'tiers'   ? tierView()
                   : gemView());
    return wrap;
  }

  // ── gems, as cards ─────────────────────────────────────────────────────────

  /* "Gem of the Ravenous Blood Lord" does not fit on a tile and the words that
     matter are the last ones, so the card carries the distinguishing part and
     the full name waits inside. */
  function gemShort(gem) {
    const full = lang('item.apotheosis.gem.' + gem.id, gem.variant);
    return full.replace(/^Gem of the /, '').replace(/ Gem$/, '');
  }
  function gemFull(gem) {
    return lang('item.apotheosis.gem.' + gem.id, gem.variant);
  }
  function gemCats(gem) {
    const out = [];
    for (const bonus of gem.bonuses) {
      for (const cat of bonus.gem_class.types) if (!out.includes(cat)) out.push(cat);
    }
    return out;
  }

  function gemView() {
    const view = document.createElement('div');

    const bar = document.createElement('div');
    bar.className = 'fg-toolbar';

    const search = document.createElement('input');
    search.type = 'search';
    search.placeholder = 'Search gems';
    search.value = catState.gemSearch;
    search.addEventListener('input', () => {
      catState.gemSearch = search.value.toLowerCase();
      paint();
    });
    bar.appendChild(labelled('Find', search));

    const catPick = document.createElement('select');
    catPick.appendChild(option('', 'fits anything'));
    for (const cat of D.categories) catPick.appendChild(option(cat.id, cat.plural));
    catPick.value = catState.gemCat;
    catPick.addEventListener('change', () => {
      catState.gemCat = catPick.value;
      paint();
    });
    bar.appendChild(labelled('Fits in', catPick));

    const count = document.createElement('span');
    count.className = 'fg-count';
    bar.appendChild(count);
    view.appendChild(bar);

    const grid = document.createElement('div');
    grid.className = 'fg-gems';
    view.appendChild(grid);

    function paint() {
      grid.innerHTML = '';
      const shown = D.gems.filter(gem => {
        if (catState.gemCat && !gemCats(gem).includes(catState.gemCat)) return false;
        if (!catState.gemSearch) return true;
        // the search reaches the effects too, so "life steal" finds the gem
        // that gives it without you knowing it is called Blood Lord
        const hay = (gemFull(gem) + ' ' + gem.bonuses.map(b =>
          RARITIES.filter(r => bonusSupports(b, r.id))
            .map(r => bonusLine(b, r.id).text).join(' ')).join(' ')).toLowerCase();
        return hay.includes(catState.gemSearch);
      });
      count.textContent = shown.length + ' of ' + D.gems.length;
      for (const gem of shown) grid.appendChild(gemCard(gem));
      if (!shown.length) {
        const none = document.createElement('p');
        none.className = 'fg-empty';
        none.textContent = 'Nothing matches that.';
        grid.appendChild(none);
      }
    }
    paint();
    return view;
  }

  function gemCard(gem) {
    const { min, max } = gemRarities(gem);
    const open = catState.gemOpen === gem.id;

    const card = document.createElement('div');
    card.className = 'gcard' + (open ? ' open' : '');
    // a card is lit by the best it can be, the way a boss card is lit by rank
    card.style.setProperty('--tier', rarityColour(max));
    card.addEventListener('click', event => {
      if (event.target.closest('.gc-body')) return;   // reading, not toggling
      catState.gemOpen = open ? null : gem.id;
      renderTab('catalog');
    });

    const stage = document.createElement('div');
    stage.className = 'gc-stage';
    stage.appendChild(iconImg(gem.id));
    card.appendChild(stage);

    const foot = document.createElement('div');
    foot.className = 'gc-foot';
    const name = document.createElement('div');
    name.className = 'gc-name';
    name.textContent = open ? gemFull(gem) : gemShort(gem);
    foot.appendChild(name);

    const band = document.createElement('div');
    band.className = 'gc-band';
    // the tiers this gem can be, as a strip: five pips read faster than
    // "rare-ancient" and they carry the colours the tooltip will use
    for (const rarity of RARITIES) {
      const pip = document.createElement('i');
      const inside = rarity.ordinal >= BY.rarity[min].ordinal
                  && rarity.ordinal <= BY.rarity[max].ordinal;
      pip.className = 'gc-pip' + (inside ? ' on' : '');
      if (inside) pip.style.background = rarityColour(rarity.id);
      pip.title = capitalise(rarity.id);
      band.appendChild(pip);
    }
    foot.appendChild(band);

    if (gem.unique) {
      const tag = document.createElement('span');
      tag.className = 'gc-unique';
      tag.textContent = lang('text.apotheosis.unique');
      foot.appendChild(tag);
    }
    card.appendChild(foot);

    if (open) card.appendChild(gemBody(gem, min, max));
    return card;
  }

  function rarityColour(id) {
    const colour = BY.rarity[id].color;
    return colour === 'rainbow' ? '#fff6d8' : colour;
  }

  /* What an open gem card says: where it drops, and a block per category with
     one line per tier. This is the answer to the only question anyone brings
     to a gem, which is "what will it do in the thing I am holding". */
  function gemBody(gem, min, max) {
    const body = document.createElement('div');
    body.className = 'gc-body';

    const facts = document.createElement('div');
    facts.className = 'gc-facts';
    const add = (key, value) => {
      const row = document.createElement('div');
      const k = document.createElement('i');
      k.textContent = key;
      const v = document.createElement('span');
      v.textContent = value;
      row.append(k, v);
      facts.appendChild(row);
    };
    add('Tiers', capitalise(min) + ' to ' + capitalise(max));
    if (gem.dimensions.length) {
      add('Drops in', gem.dimensions
        .map(d => capitalise(d.split(':').pop().replace(/_/g, ' '))).join(', '));
    }
    add('Drop weight', String(gem.weight));
    if (gem.unique) add('Unique', 'one per item');
    body.appendChild(facts);

    for (const bonus of gem.bonuses) {
      const block = document.createElement('div');
      block.className = 'gc-block';

      const head = document.createElement('h5');
      const className = lang('gem_class.' + bonus.gem_class.key, bonus.gem_class.key);
      head.textContent = className;
      // "Light Weapons" is worth spelling out as swords and tridents; "Helmets"
      // spelled out is "Helmets", and printing it twice reads as a mistake
      const spelled = bonus.gem_class.types
        .map(c => BY.cat[c] ? BY.cat[c].plural : c).join(', ');
      if (spelled.toLowerCase() !== className.toLowerCase()) {
        const fits = document.createElement('span');
        fits.textContent = spelled;
        head.appendChild(fits);
      }
      block.appendChild(head);

      for (const rarity of RARITIES) {
        // a bonus may carry values for tiers the gem itself can never be:
        // GemInstance clamps a socketed rarity into the gem's own window
        // first, so a row outside it describes an item that cannot exist
        if (!bonusSupports(bonus, rarity.id)) continue;
        if (rarity.ordinal < BY.rarity[min].ordinal
            || rarity.ordinal > BY.rarity[max].ordinal) continue;
        const row = document.createElement('div');
        row.className = 'gc-line';
        const tier = document.createElement('i');
        tier.className = RARITY_CLASS(rarity.id);
        tier.textContent = capitalise(rarity.id);
        const value = document.createElement('span');
        value.textContent = bonusLine(bonus, rarity.id).text;
        row.append(tier, value);
        block.appendChild(row);
      }
      body.appendChild(block);
    }
    return body;
  }

  // ── affixes, as a filtered list ────────────────────────────────────────────

  /* The old shape of this was a nine-column table: six tiers across, every
     cell a value in six-point type, most of them a dash. It answered every
     question at once and none of them legibly. This asks which tier you care
     about and gives that tier the room the other five were taking. */
  function affixView() {
    const view = document.createElement('div');

    const bar = document.createElement('div');
    bar.className = 'fg-toolbar';

    const search = document.createElement('input');
    search.type = 'search';
    search.placeholder = 'Search affixes';
    search.value = catState.afxSearch;
    search.addEventListener('input', () => {
      catState.afxSearch = search.value.toLowerCase();
      paint();
    });
    bar.appendChild(labelled('Find', search));

    const catPick = document.createElement('select');
    catPick.appendChild(option('', 'any gear'));
    for (const cat of D.categories) catPick.appendChild(option(cat.id, cat.plural));
    catPick.value = catState.afxCat;
    catPick.addEventListener('change', () => { catState.afxCat = catPick.value; paint(); });
    bar.appendChild(labelled('On', catPick));

    const tierPick = document.createElement('select');
    for (const rarity of RARITIES) {
      tierPick.appendChild(option(rarity.id, capitalise(rarity.id)));
    }
    tierPick.value = catState.afxTier;
    tierPick.addEventListener('change', () => {
      catState.afxTier = tierPick.value;
      tierPick.className = RARITY_CLASS(catState.afxTier);
      paint();
    });
    tierPick.className = RARITY_CLASS(catState.afxTier);
    bar.appendChild(labelled('At tier', tierPick));

    const typePick = document.createElement('select');
    typePick.appendChild(option('', 'stats & abilities'));
    typePick.appendChild(option('STAT', 'stats only'));
    typePick.appendChild(option('ABILITY', 'abilities only'));
    typePick.value = catState.afxType;
    typePick.addEventListener('change', () => { catState.afxType = typePick.value; paint(); });
    bar.appendChild(labelled('Kind', typePick));

    const count = document.createElement('span');
    count.className = 'fg-count';
    bar.appendChild(count);
    view.appendChild(bar);

    const list = document.createElement('div');
    list.className = 'fg-afx-list';
    view.appendChild(list);

    function paint(quiet) {
      list.innerHTML = '';
      const tier = catState.afxTier;
      const rows = [];

      for (const affix of D.affixes) {
        if (affix.type === 'SOCKET' || affix.type === 'DURABILITY') continue;
        if (catState.afxType && affix.type !== catState.afxType) continue;
        const fits = D.categories.map(c => c.id).filter(c => affix.gate
          ? gatePasses(affix.gate, c)
          : (!affix.categories.length || affix.categories.includes(c)));
        if (catState.afxCat && !fits.includes(catState.afxCat)) continue;

        // the sample category decides the wording of the few affixes whose
        // text depends on what they are on, so prefer the one being filtered
        const sample = catState.afxCat || fits[0];
        if (!canApply(affix, sample, tier)) continue;

        const prefix = affixName(affix.id, true);
        const suffix = affixName(affix.id, false);
        const value = affixValue(affix, tier, sample);
        if (catState.afxSearch) {
          const hay = (prefix + ' ' + suffix + ' ' + value).toLowerCase();
          if (!hay.includes(catState.afxSearch)) continue;
        }
        rows.push({ affix, prefix, suffix, value, fits,
                    from: firstTier(affix, sample) });
      }

      count.textContent = rows.length + ' at ' + capitalise(tier);
      if (!rows.length) {
        const none = document.createElement('p');
        none.className = 'fg-empty';
        none.textContent = 'Nothing rolls there.';
        list.appendChild(none);
        return;
      }

      rows.sort((a, b) => a.prefix.localeCompare(b.prefix));
      /* The entrance belongs to a list that changed, not to a card that
         opened. Expanding one affix repaints the whole list - which is cheap
         and keeps the open state in one place - but replaying eighty staggered
         fades every time somebody clicks a card made the page look like it was
         reloading itself. `quiet` is set only by the card toggle. */
      rows.forEach((row, index) =>
        list.appendChild(affixCard(row, index, paint, !quiet)));
    }
    paint();
    return view;
  }

  /* One affix, shut.

     What was here before put four things on every card at the same weight -
     the prefix, the suffix, a sentence of value, and one chip per category it
     fits, which for a general affix is twelve chips reading "Bow Crossbow
     Pickaxe Shovel Heavy Weapon Helmet..." underneath every single entry. A
     hundred of those is a wall, and the one number you came to read is the
     smallest thing on it.

     So: the value is the headline, the name is the label above it, and the
     twelve chips collapse into at most five family names. Everything else -
     the exact category list, and what this affix rolls at each of the six
     tiers - is a press away rather than always on. */
  const AFFIX_FAMILIES = [
    ['Armour', ['helmet', 'chestplate', 'leggings', 'boots']],
    ['Melee',  ['sword', 'heavy_weapon', 'trident']],
    ['Tools',  ['pickaxe', 'shovel']],
    ['Ranged', ['bow', 'crossbow']],
    ['Shield', ['shield']],
  ];

  /* Twelve categories as at most five words. A family whose every member fits
     is named; a family only partly covered names its members instead, which is
     one or two words rather than a lie of omission. */
  function affixFits(fits) {
    if (fits.length === D.categories.length) return [{ text: 'any gear', all: true }];
    const set = new Set(fits);
    const out = [];
    for (const [name, members] of AFFIX_FAMILIES) {
      const hit = members.filter(c => set.has(c));
      if (!hit.length) continue;
      if (hit.length === members.length) out.push({ text: name });
      else for (const cat of hit) out.push({ text: BY.cat[cat].name });
    }
    return out;
  }

  function affixCard(row, index, repaint, intro) {
    const open = catState.afxOpen === row.affix.id;
    const el = document.createElement('article');
    el.className = 'fg-afx' + (open ? ' open' : '');
    // Coloured by the tier it first becomes reachable at, which is the one
    // thing about an affix worth knowing at a glance: stat-or-ability was
    // the old colouring and it told you nothing you could act on, while
    // "this needs Rare gear" is the whole of why you would reforge again.
    if (row.from) el.style.setProperty('--kind', rarityColour(row.from));
    // Staggered down the grid rather than eighty cards arriving at once, so a
    // filter change reads as the list rebuilding itself. Capped at two dozen:
    // past that the delay is longer than anyone waits to read the top of it.
    // Skipped entirely when the repaint came from opening a card - see paint().
    if (intro) {
      motion(el, [{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }],
        { duration: 300, delay: Math.min(index, 24) * 16, easing: 'ease-out' });
    }

    const head = document.createElement('button');
    head.type = 'button';
    head.className = 'fg-afx-head';
    head.setAttribute('aria-expanded', String(open));

    const name = document.createElement('span');
    name.className = 'fg-afx-name';
    const prefix = document.createElement('b');
    prefix.textContent = row.prefix;
    const suffix = document.createElement('i');
    suffix.textContent = row.suffix;
    name.append(prefix, suffix);

    const value = document.createElement('span');
    value.className = 'fg-afx-value';
    value.textContent = row.value;

    const meta = document.createElement('span');
    meta.className = 'fg-afx-meta';
    for (const chip of affixFits(row.fits)) {
      const el2 = document.createElement('span');
      el2.className = 'chip' + (chip.all ? ' all' : '');
      el2.textContent = chip.text;
      meta.appendChild(el2);
    }
    if (row.from && row.from !== RARITIES[0].id) {
      const from = document.createElement('span');
      from.className = 'chip from ' + RARITY_CLASS(row.from);
      from.textContent = capitalise(row.from) + '+';
      meta.appendChild(from);
    }
    const caret = document.createElement('span');
    caret.className = 'fg-afx-caret';
    caret.textContent = '▾';
    meta.appendChild(caret);

    head.append(name, value, meta);
    head.addEventListener('click', () => {
      catState.afxOpen = open ? null : row.affix.id;
      repaint(true);                     // quiet: this is not a new list
    });
    el.appendChild(head);

    if (open) {
      const detail = affixDetail(row);
      el.appendChild(detail);
      // measured after it is in the document, so the sweep goes to the height
      // the ladder actually needs rather than to a guessed maximum
      requestAnimationFrame(() => {
        const height = detail.scrollHeight;
        motion(detail,
          [{ height: '0px', opacity: 0 }, { height: height + 'px', opacity: 1 }],
          { duration: 240, easing: 'ease-out' });
      });
    }
    return el;
  }

  /* What it rolls at every tier, which is the question the shut card cannot
     answer and the one that decides whether reforging again is worth it. */
  function affixDetail(row) {
    const box = document.createElement('div');
    box.className = 'fg-afx-detail';

    const ladder = document.createElement('div');
    ladder.className = 'fg-afx-ladder';
    for (const rarity of RARITIES) {
      const line = document.createElement('div');
      line.className = 'fg-afx-rung'
        + (rarity.id === catState.afxTier ? ' here' : '');
      line.style.setProperty('--tier', rarityColour(rarity.id));
      const tier = document.createElement('i');
      tier.className = RARITY_CLASS(rarity.id);
      tier.textContent = capitalise(rarity.id);
      const what = document.createElement('span');
      const sample = catState.afxCat || row.fits[0];
      what.textContent = canApply(row.affix, sample, rarity.id)
        ? affixValue(row.affix, rarity.id, sample) : '—';
      if (!canApply(row.affix, sample, rarity.id)) what.className = 'off';
      line.append(tier, what);
      ladder.appendChild(line);
    }
    box.appendChild(ladder);

    // the full category list, which the shut card folded into families
    if (row.fits.length !== D.categories.length) {
      const all = document.createElement('div');
      all.className = 'fg-afx-all';
      for (const cat of row.fits) {
        const chip = document.createElement('span');
        chip.className = 'chip';
        chip.textContent = BY.cat[cat].name;
        all.appendChild(chip);
      }
      box.appendChild(all);
    }
    return box;
  }

  /* The bottom and top of what one affix rolls at one tier, worded the way its
     own tooltip would word it. Both ends are real rungs of the ladder, not a
     min and a max the value never actually lands on. */
  function affixValue(affix, rarityId, cat) {
    if (affix.min_rarity) return 'always on';
    const values = affix.values[rarityId];

    if (affix.kind === 'apotheosis:attribute') {
      const low = attrValue(affix.attribute, affix.operation, stepMin(values));
      const high = attrValue(affix.attribute, affix.operation, stepMax(values));
      const name = (D.attributes[affix.attribute] || {}).name || affix.attribute;
      return (low === high ? '+' + low : '+' + low + ' to +' + high) + ' ' + name;
    }
    if (affix.kind === 'apotheosis:damage_reduction') {
      const type = lang('misc.apotheosis.' + affix.damage_type.toLowerCase(),
                        affix.damage_type);
      return type + ' damage taken down ' + fmt(100 * stepMin(values))
        + '–' + fmt(100 * stepMax(values)) + '%';
    }
    if (affix.kind === 'apotheosis:mob_effect') {
      const amp = Math.trunc(stepMax(values.amplifier));
      const effect = D.effects[affix.mob_effect] || affix.mob_effect;
      const target = tr('affix.apotheosis.target.' + affix.target.toLowerCase(),
                        effect + (amp > 0 ? ' ' + roman(amp + 1) : ''));
      return target + ', ' + ticks(Math.trunc(stepMin(values.duration))) + '–'
        + ticks(Math.trunc(stepMax(values.duration)));
    }
    // everything else is a special with a sentence of its own
    const low = affixLines(affix, rarityId, 0, cat)[0];
    const high = affixLines(affix, rarityId, 0.999, cat)[0];
    if (!low) return '—';
    const shorten = line => line.text.replace(/\s+\[.*$/, '');
    return low.text === high.text ? shorten(low) : shorten(low) + ' → ' + shorten(high);
  }

  /* The lowest tier this affix can turn up on at all, on the gear in question. */
  function firstTier(affix, cat) {
    for (const rarity of RARITIES) {
      if (canApply(affix, cat, rarity.id)) return rarity.id;
    }
    return null;
  }

  const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'];
  function roman(n) { return ROMAN[n] || String(n); }

  // ── tiers, costs and the rules behind them ─────────────────────────────────

  /* Two tables of numbers and no paragraphs. What a tier rolls and what it
     costs are both readings you take at a glance and come back to; a page of
     prose around them is read once and skipped forever after. */
  function tierView() {
    const view = document.createElement('div');
    const rar = section('Reforging');
    rar.appendChild(tierCards());
    view.appendChild(rar);
    const cut = section('Gem cutting');
    cut.appendChild(cuttingList());
    view.appendChild(cut);
    return view;
  }

  /* The rarity table was eight columns wide, which on a phone is a horizontal
     scrollbar and on a desk is a lot of squinting. One card a tier says the
     same things with room to name them. */
  function tierCards() {
    const grid = document.createElement('div');
    grid.className = 'fg-tiers';
    const totalWeight = RARITIES.reduce((a, r) => a + r.weight, 0);

    for (const rarity of RARITIES) {
      const card = document.createElement('div');
      card.className = 'fg-tier';
      card.style.setProperty('--tier', rarityColour(rarity.id));

      const head = document.createElement('h5');
      head.className = RARITY_CLASS(rarity.id);
      head.textContent = capitalise(rarity.id);
      const chance = document.createElement('em');
      chance.textContent = (100 * rarity.weight / totalWeight).toFixed(1) + '%';
      head.appendChild(chance);
      card.appendChild(head);

      const rolls = document.createElement('div');
      rolls.className = 'fg-tier-rolls';
      const count = t => rarity.rules.filter(x => x.type === t).length;
      const sure = t => rarity.rules.filter(x => x.type === t && x.chance >= 1).length;
      const range = t => {
        const all = count(t);
        if (!all) return null;
        return sure(t) === all ? String(all) : sure(t) + '–' + all;
      };
      for (const [type, name] of [['STAT', 'stats'], ['ABILITY', 'abilities'],
                                  ['SOCKET', 'sockets']]) {
        const got = range(type);
        if (!got) continue;
        const pill = document.createElement('span');
        pill.innerHTML = '<b></b><i></i>';
        pill.firstChild.textContent = got;
        pill.lastChild.textContent = name;
        rolls.appendChild(pill);
      }
      const dur = rarity.rules.find(x => x.type === 'DURABILITY');
      if (dur) {
        const pill = document.createElement('span');
        pill.innerHTML = '<b></b><i></i>';
        pill.firstChild.textContent = Math.round(dur.chance * 100) + '%';
        pill.lastChild.textContent = 'durable';
        rolls.appendChild(pill);
      }
      card.appendChild(rolls);

      const cost = D.recipes.reforging[rarity.id];
      const foot = document.createElement('div');
      foot.className = 'fg-tier-cost';
      if (cost) {
        foot.appendChild(costLine(rarity.material, cost.material_cost));
        foot.appendChild(costLine('apotheosis:gem_dust', cost.dust_cost));
        const lv = document.createElement('span');
        lv.className = 'lv';
        lv.textContent = cost.level_cost + ' lv';
        foot.appendChild(lv);
      }
      card.appendChild(foot);
      grid.appendChild(card);
    }
    return grid;
  }

  function costLine(itemId, count) {
    const el = document.createElement('span');
    if (D.icons[itemId]) el.appendChild(iconImg(itemId, 'sm'));
    const text = document.createElement('i');
    text.textContent = count;
    el.appendChild(text);
    el.title = count + ' × ' + (D.names[itemId] || itemId);
    return el;
  }

  function cuttingList() {
    const list = document.createElement('div');
    list.className = 'fg-cut-list';
    for (let i = 0; i < RARITIES.length - 1; i++) {
      const from = RARITIES[i], to = RARITIES[i + 1];
      const topJump = to.ordinal === RARITIES[RARITIES.length - 1].ordinal;
      const row = document.createElement('div');
      row.className = 'fg-cut';

      const step = document.createElement('div');
      step.className = 'fg-cut-step';
      step.innerHTML = `<i class="${RARITY_CLASS(from.id)}">${capitalise(from.id)}</i>`
        + `<em>→</em><i class="${RARITY_CLASS(to.id)}">${capitalise(to.id)}</i>`;
      row.appendChild(step);

      const cost = document.createElement('div');
      cost.className = 'fg-cut-cost';
      cost.appendChild(costLine('apotheosis:gem_dust',
        D.cutting.dust_base + from.ordinal * D.cutting.dust_per_ordinal));
      const pair = document.createElement('span');
      pair.textContent = '2 gems';
      cost.appendChild(pair);
      row.appendChild(cost);

      const mats = document.createElement('div');
      mats.className = 'fg-cut-mats';
      const opts = [];
      if (i > 0 && !topJump) opts.push([RARITIES[i - 1].material, D.cutting.mat_prev]);
      if (!topJump) opts.push([from.material, D.cutting.mat_same]);
      opts.push([to.material, D.cutting.mat_next]);
      opts.forEach(([id, n], index) => {
        if (index) {
          const or = document.createElement('em');
          or.textContent = 'or';
          mats.appendChild(or);
        }
        mats.appendChild(costLine(id, n));
      });
      row.appendChild(mats);
      list.appendChild(row);
    }
    return list;
  }

  function section(title, blurb) {
    const el = document.createElement('section');
    el.className = 'fg-cat-sec';
    const head = document.createElement('h2');
    head.textContent = title;
    el.appendChild(head);
    if (blurb) {
      const p = document.createElement('p');
      p.className = 'fg-blurb';
      p.textContent = blurb;
      el.appendChild(p);
    }
    return el;
  }
  function labelled(name, control) {
    const wrap = document.createElement('label');
    wrap.className = 'fg-tool';
    const text = document.createElement('span');
    text.textContent = name;
    wrap.append(text, control);
    return wrap;
  }


  // ── tabs ───────────────────────────────────────────────────────────────────

  let tabBar = null;

  function renderTab(tab) {
    hideTip();
    stage.innerHTML = '';

    tabBar = document.createElement('nav');
    tabBar.className = 'fg-tabs';
    for (const [key, name] of [['forge', 'Forge'], ['catalog', 'Catalog']]) {
      const btn = document.createElement('button');
      btn.className = 'fg-tab' + (key === tab ? ' active' : '');
      btn.textContent = name;
      btn.addEventListener('click', () => renderTab(key));
      tabBar.appendChild(btn);
    }
    stage.appendChild(tabBar);
    stage.appendChild(tab === 'catalog' ? catalog() : stationForge());
  }

  // ── boot ───────────────────────────────────────────────────────────────────
  //
  // Nothing is fetched until the section is opened. The data file is a hundred
  // kilobytes of affix curves and gem tables, and most people who load this
  // page never open this panel; the portal already polls three endpoints of
  // its own on a clock, and this one has no clock at all - a mod's rules do
  // not change while you are reading them.

  let mounted = false;
  const wrap = document.getElementById('fg-wrap');

  /* Opened and shut the way the skill tree's planner is: the tab is put down
     and the panel takes its place. The first open is also the first fetch. */
  window.forgeOpen = function () {
    wrap.classList.add('on');
    if (!mounted) { mounted = true; load(); }
    requestAnimationFrame(() =>
      wrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' }));
  };

  window.forgeShut = function () {
    wrap.classList.remove('on');
    hideTip();
    wrap.scrollIntoView({ block: 'nearest' });
  };

  function load() {
    fetch(asset('data.json'))
    .then(response => response.json())
    .then(data => {
      D = data;
      RARITIES = D.rarities.slice().sort((a, b) => a.ordinal - b.ordinal);
      for (const rarity of RARITIES) BY.rarity[rarity.id] = rarity;
      for (const affix of D.affixes) BY.affix[affix.id] = affix;
      for (const gem of D.gems) BY.gem[gem.id] = gem;
      for (const item of D.items) BY.item[item.id] = item;
      for (const cat of D.categories) BY.cat[cat.id] = cat;

      // the rarity colours are the mod's own, so the page never invents one
      const style = document.createElement('style');
      style.textContent = RARITIES.map(r =>
        `.${RARITY_CLASS(r.id)}{color:${r.color === 'rainbow' ? '#fff6d8' : r.color}}`
      ).join('\n');
      document.head.appendChild(style);

      renderTab('forge');
    })
    .catch(error => {
      // a failed fetch leaves the panel mountable again, so opening it a
      // second time retries rather than staying empty for good
      mounted = false;
      stage.innerHTML = '';
      const message = document.createElement('p');
      message.className = 'fg-loading';
      message.textContent = 'Could not read the pack data: ' + error;
      stage.appendChild(message);
    });
  }
})();
