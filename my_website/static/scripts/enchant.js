/* The Arcane Table: Apotheosis' enchanting module, run rather than described.
 *
 * The sibling of forge.js. Same shape - a lazily-fetched data file, a station
 * you build something at, and a catalog you read - and the same rule about
 * where numbers come from: everything here is the pack's own data or the mod's
 * own code, and where a constant is quoted the comment says which method it
 * was read out of.
 *
 * What Apotheosis does to enchanting, in one paragraph: vanilla's bookshelf
 * count is replaced by five stats that blocks around the table contribute.
 * Eterna is the ceiling - every point of it is two levels of enchanting power.
 * Quanta is variance, a bell curve either side of the level you spent.
 * Rectification lifts the bottom of that curve without touching the top.
 * Arcana re-weights the rarity table and, past two thresholds, guarantees
 * extra enchantments. Clues decide how much of the result you see before you
 * commit. This panel computes all five from a set of blocks and shows what
 * they buy you.
 *
 * One thing this is not: a roll simulator. The game picks enchantments from a
 * seed stored on the player, and the min/max cost of every modded enchantment
 * lives in that mod's own Java rather than in any file - so which enchantments
 * a given power can produce is not knowable from data for 175 of the 214 here.
 * What *is* knowable, and what this shows, is the whole of the stat side: the
 * levels each slot offers, the power band quanta and rectification put around
 * them, the exact rarity weights arcana produces, and every infusion recipe's
 * stat window.
 */
(function () {
  'use strict';

  const panel = document.getElementById('sec-ench');
  const stage = document.getElementById('ench-stage');
  if (!panel || !stage) return;                 // not this page

  const ROOT = panel.dataset.root;
  const STAMP = panel.dataset.stamp || '0';
  const asset = path => ROOT + path + '?v=' + STAMP;
  let D = null;

  const BY = { block: {}, ench: {} };

  // ── the mod's own maths ────────────────────────────────────────────────────

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const round1 = v => Math.round(v * 10) / 10;

  /* What a table and the blocks around it add up to.

     Three things here are not obvious and all three come from
     ApothEnchantmentMenu$TableStats$Builder rather than from any data file:

     A bare table is not all zeroes. The Builder's constructor puts fifteen
     quanta and one clue on every table before a shelf is placed, which is why
     vanilla enchanting is a gamble and why you always get one hint.

     The item's enchantability feeds *arcana*, at half rate. The mod's book
     says only "is increased by 50% of an item's enchantability" with the
     stat's name hidden inside a formatting macro; the constructor names it.
     So a gold sword is eleven arcana of rarity weighting, not eleven eterna
     of levels.

     And eterna is bucketed rather than summed. Each block carries its own
     ceiling; blocks are grouped by that ceiling, the groups are walked from
     lowest cap to highest, and each capped group clamps the running total to
     its own cap. A group that is already over its ceiling throws the excess
     away before a higher-ceilinged block is ever counted - twenty dormant
     deepshelves and one draconic endshelf make 25, not 30. */
  function totals(counts, enchantability) {
    const C = D.constants;
    const buckets = new Map();            // this block's cap -> eterna in it
    let quanta = C.base_quanta, arcana = 0, rect = 0, clues = C.base_clues;
    let used = 0, placedEterna = 0, treasure = false;
    for (const block of D.blocks) {
      const n = counts[block.id] || 0;
      if (!n) continue;
      used += n;
      placedEterna += block.eterna * n;
      buckets.set(block.maxEterna,
                  (buckets.get(block.maxEterna) || 0) + block.eterna * n);
      quanta += block.quanta * n;
      arcana += block.arcana * n;
      rect += block.rectification * n;
      clues += block.clues * n;
      if (block.allows_treasure) treasure = true;
    }
    const bonus = (enchantability || 0) * C.enchantability_to_arcana;
    arcana += bonus;

    let eterna = 0, ceiling = 0;
    for (const [cap, sum] of [...buckets.entries()].sort((a, b) => a[0] - b[0])) {
      eterna = cap > 0 ? Math.min(cap, eterna + sum) : eterna + sum;
      ceiling = Math.max(ceiling, cap);
    }
    const uncapped = eterna;
    eterna = clamp(eterna, 0, C.max_eterna);
    return {
      blocks: used,
      placedEterna,                       // what the shelves are worth on paper
      ceiling: Math.min(C.max_eterna, ceiling || C.max_eterna),
      eterna,
      capped: placedEterna > uncapped + 0.001 || uncapped > C.max_eterna,
      quanta, arcana, rect, clues,
      bonus, treasure,
    };
  }

  /* The level each of the three slots offers.
     RealEnchantmentHelper.getEnchantmentCost: the third slot is the whole of
     your eterna in levels, and the first two roll inside a band of it. */
  function slotLevels(eterna) {
    const maxLevel = Math.round(eterna * D.constants.levels_per_eterna);
    return D.constants.slot_bands.map(band => ({
      min: band.exact ? maxLevel : Math.max(1, Math.round(maxLevel * band.min)),
      max: band.exact ? maxLevel : Math.max(1, Math.round(maxLevel * band.max)),
      exact: !!band.exact,
    }));
  }

  /* What quanta and rectification do to a level once you have spent it.

     getQuantaFactor draws a gaussian, divides it by three and clamps it to
     [-1, 1], so the factor is a bell centred on your base power rather than a
     flat range. Rectification raises the floor: anything under (R - 1) is
     rerolled uniformly between (R - 1) and 1, which is why the mod's book says
     the minimum is 1 - (1 - R) * Quanta and why negative rectification hurts.

     The page shows the band rather than a roll, which is what the game's own
     info screen shows too. */
  function powerBand(level, quanta, rect) {
    const r = rect / 100;
    const lo = 1 - (quanta / 100) * (1 - r);
    const hi = 1 + quanta / 100;
    const ceiling = D.constants.power_ceiling;
    return {
      lo: clamp(Math.round(level * lo), 1, ceiling),
      hi: clamp(Math.round(level * hi), 1, ceiling),
      loFactor: lo, hiFactor: hi,
    };
  }

  /* ApothEnchantmentMenu$Arcana.getForThreshold: the highest tier whose
     threshold your arcana reaches. The weights are the whole reason to want
     the stat - at zero a Very Rare enchantment is one pick in eighteen, at
     the top of the ladder it is ten in eighteen. */
  function arcanaTier(arcana) {
    let tier = D.arcana[0];
    for (const step of D.arcana) if (arcana >= step.threshold) tier = step;
    return tier;
  }

  /* How many enchantments this arcana guarantees before a single extra roll
     is made. Read off selectEnchantment's two threshold branches, and used
     only to say so on the page - the roll itself applies the thresholds
     directly, in the mod's own order. */
  function arcanaGuarantee(arcana) {
    const C = D.constants;
    if (arcana >= C.arcana_guarantee_three) return 3;
    if (arcana >= C.arcana_guarantee_two) return 2;
    return 1;
  }

  // ── small dom helpers, the forge's own ─────────────────────────────────────

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function iconImg(id, cls) {
    const anim = D.anims && D.anims[id];
    if (!anim || !D.icons[id]) {
      const img = document.createElement('img');
      img.className = 'en-icon ' + (cls || '');
      if (D.icons[id]) img.src = asset('icons/' + D.icons[id]);
      img.alt = '';
      return img;
    }
    const box = document.createElement('i');
    box.className = 'en-icon anim ' + (cls || '');
    box.style.backgroundImage = `url(${asset('icons/' + D.icons[id])})`;
    box.style.setProperty('--frames', anim.frames);
    box.style.setProperty('--steps', Math.max(2, anim.frames));
    box.style.setProperty('--dur', anim.seconds + 's');
    return box;
  }
  function name(id) { return (D.names && D.names[id]) || id; }

  const REDUCED = window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)');
  function motion(node, frames, options) {
    if (!node || !node.animate || (REDUCED && REDUCED.matches)) return null;
    let anim;
    try { anim = node.animate(frames, options); } catch (e) { return null; }
    const life = (options.delay || 0) + (options.duration || 0) + 250;
    setTimeout(() => {
      try { if (anim.playState !== 'finished') anim.finish(); } catch (e) { /* gone */ }
    }, life);
    return anim;
  }

  // ── the table ──────────────────────────────────────────────────────────────

  const state = {
    placed: {},                      // "x,y,z" -> block id
    brush: 'minecraft:bookshelf',    // what a click puts down
    erase: false,                    // touch has no shift key, so this is a mode
    item: 'minecraft:diamond_sword',
    kind: 'sword',           // the slot custom gear stands in
    ench: 10,
    slot: 2,
    seed: (Math.random() * 1e9) | 0,
    result: null,                    // the last roll
    layer: 'both',                   // 'both', 0 or 1 - what you are editing
    detail: null,                    // the palette tile being looked at
    /* The drawer starts open on a desk and shut on a phone.

       On a desk it costs the build a third of a frame it has plenty of, and
       having the tools already there is worth more than the width. On a phone
       it would cover half of everything before you had seen the build once,
       so it waits to be asked - the handle under the stage carries the
       current block, so nothing is hidden, only folded. */
    tools: !(window.matchMedia
             && window.matchMedia('(max-width: 860px)').matches),
  };

  /* Gear worth enchanting. `kind` is the slot UniversalEnchants sorts targets
     into, and `ench` is Item.getEnchantmentValue, which Apotheosis turns into
     arcana at half rate. */
  const ITEMS = [
    { id: 'minecraft:diamond_sword', name: 'Diamond Sword', ench: 10, kind: 'sword' },
    { id: 'minecraft:netherite_sword', name: 'Netherite Sword', ench: 15, kind: 'sword' },
    { id: 'minecraft:golden_sword', name: 'Golden Sword', ench: 22, kind: 'sword' },
    { id: 'minecraft:diamond_axe', name: 'Diamond Axe', ench: 10, kind: 'axe' },
    { id: 'minecraft:diamond_pickaxe', name: 'Diamond Pickaxe', ench: 10, kind: 'pickaxe' },
    { id: 'minecraft:diamond_shovel', name: 'Diamond Shovel', ench: 10, kind: 'shovel' },
    { id: 'minecraft:diamond_helmet', name: 'Diamond Helmet', ench: 10, kind: 'helmet' },
    { id: 'minecraft:diamond_chestplate', name: 'Diamond Chestplate', ench: 10, kind: 'chestplate' },
    { id: 'minecraft:diamond_leggings', name: 'Diamond Leggings', ench: 10, kind: 'leggings' },
    { id: 'minecraft:diamond_boots', name: 'Diamond Boots', ench: 10, kind: 'boots' },
    { id: 'minecraft:bow', name: 'Bow', ench: 1, kind: 'bow' },
    { id: 'minecraft:crossbow', name: 'Crossbow', ench: 1, kind: 'crossbow' },
    { id: 'minecraft:trident', name: 'Trident', ench: 1, kind: 'trident' },
    { id: 'minecraft:fishing_rod', name: 'Fishing Rod', ench: 1, kind: 'fishing_rod' },
    { id: 'minecraft:shield', name: 'Shield', ench: 1, kind: 'shield' },
    { id: 'minecraft:elytra', name: 'Elytra', ench: 1, kind: 'elytra' },
    { id: '__custom__', name: 'Custom gear', ench: 15, kind: 'sword' },
  ];

  /* What the table reads, and the gap you stand in.

     Apotheosis does not change which positions count. ApothEnchantmentMenu's
     gatherStats walks vanilla's own EnchantmentTableBlock.BOOKSHELF_OFFSETS
     and asks canReadStatsFrom about each - so the ring is exactly vanilla's:
     sixteen positions a layer at a chebyshev distance of two, two layers,
     thirty-two sockets in all, and nothing beyond them is read at any range.

     Two of the thirty-two are the doorway, and they stay empty: a ring with
     no way in is not a build, and it is also what makes fifteen the famous
     number - sixteen positions a layer, less the door, is fifteen shelves.
     Thirty of the thirty-two, then, and that is the ceiling this panel
     builds to. */
  const SOCKETS = 32;                  // BOOKSHELF_OFFSETS, both layers
  const DOORWAY = o => o.x === 0 && o.z === 2;

  function usable(o) { return !DOORWAY(o); }

  function ringSlots(layers) {
    return D.offsets.filter(o => layers.includes(o.y) && usable(o));
  }

  const PRESETS = {
    'Vanilla 15': { fill: 'minecraft:bookshelf', layers: [0] },
    'Starter': { fill: 'apotheosis:hellshelf', layers: [0],
                 extra: { 'apotheosis:seashelf': 6 } },
    'Mid': { fill: 'apotheosis:infused_hellshelf', layers: [0, 1],
             extra: { 'apotheosis:infused_seashelf': 8, 'apotheosis:sightshelf': 2,
                      'apotheosis:rectifier': 2 } },
    'Max': { fill: 'apotheosis:draconic_endshelf', layers: [0, 1],
             extra: { 'apotheosis:pearl_endshelf': 8,
                      'apotheosis:echoing_sculkshelf': 6,
                      'apotheosis:rectifier_t3': 4,
                      'apotheosis:sightshelf_t2': 2 } },
  };

  const key = o => o.x + ',' + o.y + ',' + o.z;

  function layout(preset) {
    const spec = PRESETS[preset];
    const slots = ringSlots(spec.layers);
    const out = {};
    let i = 0;
    for (const [id, n] of Object.entries(spec.extra || {})) {
      for (let k = 0; k < n && i < slots.length; k++, i++) out[key(slots[i])] = id;
    }
    for (; i < slots.length; i++) out[key(slots[i])] = spec.fill;
    return out;
  }

  function currentItem() {
    const found = ITEMS.find(i => i.id === state.item) || ITEMS[0];
    // custom gear takes whichever slot the control below the picker is set to
    return found.id === '__custom__'
      ? Object.assign({}, found, { kind: state.kind }) : found;
  }
  function itemEnch() {
    const item = currentItem();
    return item.id === '__custom__' ? state.ench : item.ench;
  }

  function buildTotals() {
    const counts = {};
    for (const id of Object.values(state.placed)) counts[id] = (counts[id] || 0) + 1;
    return totals(counts, itemEnch());
  }

  // ── the roll ───────────────────────────────────────────────────────────────

  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  /* Box-Muller, because getQuantaFactor draws a gaussian and a uniform in its
     place would make the power band flat instead of belled. */
  function gauss(rand) {
    let u = 0, v = 0;
    while (!u) u = rand();
    while (!v) v = rand();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  /* The power one level of one enchantment asks for.

     EnchantmentInfo.defaultMin, which is what every enchantment on this pack
     uses because every Min Power Function in the config is blank. Up to the
     enchantment's natural maximum it is vanilla's own curve; past it, each
     extra level costs another `step` multiplied by (levels past max) to the
     1.6 - so the levels Apotheosis adds get expensive fast. Protection IV
     wants 34 power and Protection VIII wants 177. */
  function minPower(ench, level) {
    const [a, b] = ench.min;
    const base = a + b * level;
    if (level > ench.vmax && level > 1) {
      const step = b || 15;              // a flat curve has no step to copy
      return base + step * Math.trunc(Math.pow(level - ench.vmax, 1.6));
    }
    return base;
  }

  /* EnchantmentInfo.defaultMax: a flat absoluteMaxEterna * 4 for every
     enchantment, every level. Trivial, and checked anyway - the mod tests
     both ends of the window and this page is a transcription of the mod, not
     a tidier version of it. It bites the moment a pack registers a shelf with
     a higher ceiling than fifty: the ceiling is the largest maxEterna in the
     enchanting_stats data, so it and this both move. */
  function maxPower(ench, level) {
    return D.constants.power_ceiling;
  }

  /* Which enchantments this power can reach, at what level.

     Note what is *not* here: an upper bound. Apotheosis' defaultMax is a flat
     absoluteMaxEterna * 4 - two hundred, for every enchantment - so unlike
     vanilla nothing drops back out of the pool once you can afford it. That
     single change is most of why high-eterna tables roll so many
     enchantments at once.

     Modded enchantments are in the pool too. Their real curve lives in their
     own mod's code and cannot be read from any file here, so they fall back
     to Enchantment's own base-class default of 1 + 10 * level. That is a
     genuine default rather than an invention - a modded enchantment that
     overrides nothing uses exactly it - but it is still an assumption per
     enchantment, so they are flagged and the page marks them. */
  function poolAt(power, item, treasure) {
    const out = [];
    for (const ench of D.enchants) {
      // A treasure enchantment is off the table unless a Treasure Shelf is in
      // range - that block is the only thing in the mod that answers yes to
      // IEnchantingBlock.allowsTreasure, and it is the whole reason Mending
      // can be enchanted here at all rather than only traded or fished for.
      if (ench.treasure && !treasure) continue;
      if (!ench.discoverable) continue;
      // what it goes on, from the server's own UniversalEnchants config -
      // real for the modded ones too, which is why they can be in the draw at
      // all. An enchantment with no entry there has no knowable target and
      // stays out rather than being offered on everything.
      if (!ench.fits.includes(item.kind)) continue;
      /* getAvailableEnchantmentResults walks levels down from the
         enchantment's configured maximum and takes the first that this power
         can pay for, stopping at the enchantment's own minimum level - which
         is 1 for everything in this pack. Both ends of the window are
         tested, the way the mod tests them. */
      const floor = ench.minLevel || 1;
      for (let lvl = ench.max; lvl >= floor; lvl--) {
        if (power >= minPower(ench, lvl) && power <= maxPower(ench, lvl)) {
          out.push({ ench, level: lvl });
          break;
        }
      }
    }
    return out;
  }

  function weightOf(entry, tier) {
    const i = D.rarities.indexOf(entry.ench.rarity);
    return tier.weights[i < 0 ? 0 : i];
  }

  /* Two enchantments that will not share an item. UniversalEnchants lists
     these per enchantment and the list is not always written on both sides,
     so it is checked in both directions. */
  function clashes(a, b) {
    if (a === b) return true;
    const ea = BY.ench[a], eb = BY.ench[b];
    if (ea && ea.clashes.includes(b)) return true;
    if (eb && eb.clashes.includes(a)) return true;
    return false;
  }

  /* RealEnchantmentHelper.selectEnchantment, followed statement for statement.

     The order here is the mod's order, and it is not the obvious one. The two
     arcana guarantees fire *before* the extra-roll loop, not after it, and
     they are additional to whatever that loop then draws - so a table at 75
     arcana takes three enchantments off the pool and then still rolls for
     more, rather than rolling and being topped up to three. This page used to
     do it the other way round, which quietly capped a max-arcana table at the
     number the dice happened to give it.

     The pruning is the mod's too: removeIncompatible runs against the last
     thing added, after the first pick and after the second, and then at the
     top of every iteration of the loop. Not after the third - the mod does
     not, and the loop's own first pass covers it. */
  function rollOffer(T, slotIndex, seed) {
    const rand = rng(seed);
    const C = D.constants;
    const levels = slotLevels(T.eterna);
    const lv = levels[slotIndex];
    // getEnchantmentCost: slot 2 is maxLevel outright, the others roll
    // uniformly inside their band - Mth.randomBetween, then max(1, round).
    const base = lv.exact ? lv.min
      : Math.max(1, Math.round((lv.min + rand() * (lv.max - lv.min))));

    // getQuantaFactor, returned as a fraction and used as (1 + it)
    const r = T.rect / 100;
    let f = clamp(gauss(rand) / C.quanta_gaussian_divisor, -1, 1);
    if (f < r - 1) f = (r - 1) + rand() * (1 - (r - 1));
    const power = clamp(Math.round(base * (1 + T.quanta * f / 100)), 1, C.power_ceiling);

    const item = currentItem();
    const tier = arcanaTier(T.arcana);
    let pool = poolAt(power, item, T.treasure);
    const chosen = [];
    if (pool.length) {
      // WeightedRandom.getRandomItem over the arcana weights
      const pick = () => {
        const total = pool.reduce((a, e) => a + weightOf(e, tier), 0);
        let roll = rand() * total;
        for (const entry of pool) {
          roll -= weightOf(entry, tier);
          if (roll <= 0) return entry;
        }
        return pool[pool.length - 1];
      };
      const prune = got => {
        pool = pool.filter(e => !clashes(e.ench.id, got.ench.id));
      };
      const take = () => { const got = pick(); chosen.push(got); return got; };

      prune(take());
      // "At 25% you will always receive at least two enchantments. At 75%,
      // three." - and the mod means at least, not exactly.
      if (T.arcana >= C.arcana_guarantee_two && pool.length) prune(take());
      if (T.arcana >= C.arcana_guarantee_three && pool.length) take();

      /* The vanilla extra-roll loop with Apotheosis' cap on it. Note which
         power is halved: the loop counts down from the *modified* power, but
         the moment that runs past 45 it is replaced outright by 1.15 of the
         base - so a wildly lucky quanta roll does not also buy you a longer
         tail of extra enchantments. */
      let n = power;
      if (n > C.extra_roll_cap) n = Math.trunc(base * C.extra_roll_scale);
      while (Math.floor(rand() * C.extra_roll_die) <= n) {
        if (chosen.length) prune(chosen[chosen.length - 1]);
        if (!pool.length) break;
        take();
        n = Math.trunc(n / 2);
      }
    }
    return { base, power, level: lv, chosen, tier };
  }

  /* The odds, for the offer that is selected: every enchantment the middle of
     this offer's power band can reach, and how often it would be the first
     one drawn. Exact given the pool - it is the arcana weight over the pool's
     total - and recomputed whenever anything changes. */
  function oddsFor(T, slotIndex) {
    const levels = slotLevels(T.eterna);
    const lv = levels[slotIndex];
    const base = lv.exact ? lv.min : Math.round((lv.min + lv.max) / 2);
    const band = powerBand(base, T.quanta, T.rect);
    const mid = Math.round((band.lo + band.hi) / 2);
    const tier = arcanaTier(T.arcana);
    const pool = poolAt(mid, currentItem(), T.treasure);
    const total = pool.reduce((a, e) => a + weightOf(e, tier), 0) || 1;
    return {
      band, mid, tier,
      rows: pool.map(e => ({
        ench: e.ench, level: e.level,
        pct: 100 * weightOf(e, tier) / total,
      })).sort((a, b) => b.pct - a.pct || a.ench.name.localeCompare(b.ench.name)),
    };
  }

  // ── the isometric build ────────────────────────────────────────────────────

  const CUBE = 46;

  function faceTexture(id, face) {
    const set = D.faces[id];
    if (set && set[face]) return asset('icons/' + set[face]);
    if (D.icons[id]) return asset('icons/' + D.icons[id]);
    return null;
  }

  /* Whether this particular face of this block moves.

     Not the same question as whether the *block* moves. The Blazing
     Hellshelf's side is a twenty-one frame filmstrip and its top is a still
     tile, so a per-block flag - which is all `anims` is - cannot answer it.
     The extractor records the two separately for exactly this reason. */
  function faceAnim(id, face) {
    const set = D.face_anims && D.face_anims[id];
    return (set && set[face]) || null;
  }

  /* One face, dressed.

     A still face is the texture stretched over the whole square. A filmstrip
     is the same png several hundred pixels tall, so it is scaled to
     frames x 100% in Y and stepped down one frame at a time - the same
     treatment the item icons already get, which is why the sprite in the
     palette looked right while the block in the build did not.

     `height` is the squash a short block wears. It multiplies into the Y
     scale rather than replacing it, so a short animated block would still
     come out square - none exist today, and the arithmetic should not be the
     reason for that. */
  function dressFace(node, id, face, height) {
    const url = faceTexture(id, face);
    node.style.animation = '';
    node.style.backgroundPosition = '';
    if (!url) {
      node.style.backgroundImage = '';
      node.style.backgroundSize = '';
      return;
    }
    node.style.backgroundImage = `url(${url})`;
    const anim = face === 'top' ? faceAnim(id, 'top') : faceAnim(id, 'side');
    const h = height || 1;
    if (anim && anim.frames > 1) {
      node.style.backgroundSize = '100% ' + (anim.frames * 100 / h) + '%';
      node.style.setProperty('--frames', anim.frames);
      node.style.setProperty('--steps', Math.max(2, anim.frames));
      node.style.setProperty('--dur', anim.seconds + 's');
      node.classList.add('anim');
      return;
    }
    node.classList.remove('anim');
    /* A block shorter than a cube is drawn by squashing the whole cube in Z,
       which squashes its side textures with it - the enchanting table's sides
       came out compressed against a top drawn at full size. The walls are
       given the bottom h of their texture blown up to fill instead, so once
       the squash lands the pixels are back to square and match the lid. This
       is what the game does too: a twelve-tall block maps its sides to twelve
       rows of texture rather than scaling sixteen into twelve. */
    if (h !== 1 && face !== 'top') {
      node.style.backgroundSize = '100% ' + (100 / h) + '%';
      node.style.backgroundPositionY = '100%';
    } else {
      node.style.backgroundSize = '';
    }
  }

  /* Re-dress a cube that is already on screen, so a socket changing what is
     in it does not mean rebuilding the world around it. */
  function paintCube(box, id) {
    if (box._id === id) return;
    box._id = id;
    const h = box._height || 1;
    for (const node of box.children) {
      dressFace(node, id, node.classList.contains('top') ? 'top' : 'side', h);
    }
  }

  function cube(id, o, opts) {
    opts = opts || {};
    const box = el('div', 'en-cube' + (opts.ghost ? ' ghost' : ''));
    box.style.width = CUBE + 'px';
    box.style.height = CUBE + 'px';
    box.style.marginLeft = (-CUBE / 2) + 'px';
    box.style.marginTop = (-CUBE / 2) + 'px';
    const h = opts.height || 1;
    const drop = -(1 - h) * (CUBE / 2);
    box.style.transform =
      `translate3d(${o.x * CUBE}px, ${o.z * CUBE}px, ${o.y * CUBE}px)`
      + (h === 1 ? '' : ` translateZ(${drop}px) scaleZ(${h})`);
    box.style.setProperty('--half', (CUBE / 2) + 'px');
    box._height = h;
    box._id = id;
    for (const [face, tex] of [['top', 'top'], ['w-n', 'side'], ['w-s', 'side'],
                               ['w-e', 'side'], ['w-w', 'side']]) {
      const side = el('div', 'f ' + face);
      dressFace(side, id, tex, h);
      box.appendChild(side);
    }
    return box;
  }

  /* How far from the camera a socket is.

     The world is turned -45 degrees, so the axis running away from the viewer
     is x + z: the smaller it is, the further back the block sits. Height
     breaks the tie, lower first.

     This is what the click handler sorts on, and the reason it has to: two
     sockets on a corner overlap on screen, the near one is on top, and filling
     it walls off the far one for good. Clicking fills the furthest thing under
     the cursor, so a corner fills back to front and nothing gets stranded. */
  function depthOf(o) { return (o.x + o.z) * 4 + o.y; }

  /* Where a socket lands on screen, in the camera's own terms.

     The world carries one transform - rotateX(60deg) rotateZ(-45deg) - and
     the whole build is laid out inside it, so nothing here has to guess how
     big the result is: run a point through the same two rotations by hand and
     you have its screen position exactly.

       rotateZ(-45): sx = (X + Y)/root2,  sy = (Y - X)/root2
       rotateX(60):  screen y = sy * cos60 - Z * sin60

     This is what the fit below is built on, and it is why the camera can be
     sized to the build rather than to a number somebody measured once. */
  const COS60 = 0.5, SIN60 = Math.sin(Math.PI / 3), ROOT2 = Math.SQRT2;

  function project(X, Y, Z) {
    const sx = (X + Y) / ROOT2;
    const sy = (Y - X) / ROOT2;
    return { x: sx, y: sy * COS60 - Z * SIN60 };
  }

  /* The box the whole build occupies on screen, at scale 1.

     Every cube's eight corners are projected rather than its centre - a cube
     seen at this angle is a hexagon a good deal wider than the point it hangs
     from, and fitting to the centres alone clipped the near corners off every
     time. */
  function buildBounds(cells) {
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    const h = CUBE / 2;
    for (const c of cells) {
      const X = c.x * CUBE, Y = c.z * CUBE, Z = c.y * CUBE;
      for (const dx of [-h, h]) for (const dy of [-h, h]) for (const dz of [-h, h]) {
        const q = project(X + dx, Y + dy, Z + dz);
        if (q.x < x0) x0 = q.x;
        if (q.x > x1) x1 = q.x;
        if (q.y < y0) y0 = q.y;
        if (q.y > y1) y1 = q.y;
      }
    }
    if (!isFinite(x0)) return { w: 1, h: 1, cx: 0, cy: 0 };
    return { w: x1 - x0, h: y1 - y0, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2 };
  }

  /* Which layer you are working on.

     Two layers of shelves at this angle hide each other: the upper ring sits
     over the lower one and the back half of the lower ring is behind it for
     good. Focusing a layer does not remove the other - the build is still the
     build, and both still count - it fades it and stops it taking clicks, so
     you can reach what you are working on without losing the shape of what
     you are not. */
  function layerOn(y) { return state.layer === 'both' || state.layer === y; }

  function isoStage() {
    const view = el('div', 'en-iso');
    const world = el('div', 'en-iso-world');

    const floor = [];
    for (let x = -2; x <= 2; x++) {
      for (let z = -2; z <= 2; z++) floor.push({ x, y: -1, z });
    }
    for (const o of floor) {
      const tile = cube('minecraft:obsidian', o);
      tile.classList.add('en-cube-floor');
      world.appendChild(tile);
    }
    const table = cube('minecraft:enchanting_table', { x: 0, y: 0, z: 0 },
                       { height: 0.75 });
    table.classList.add('en-cube-table');
    world.appendChild(table);

    /* The book the real block keeps open above itself. It is an entity model
       in game and there is no flat sprite of it, so the item stands in - but
       without something up there the block reads as a red slab and not as an
       enchanting table, which is most of why this thing kept looking wrong. */
    const book = el('div', 'en-iso-book');
    book.style.backgroundImage = `url(${asset('icons/' + D.icons['minecraft:book'])})`;
    book.style.transform =
      `translate3d(0px, 0px, ${CUBE * 0.95}px) rotateX(-60deg) rotateZ(45deg)`;
    world.appendChild(book);

    const sockets = new Map();
    for (const o of D.offsets) {
      const open = usable(o);
      const id = state.placed[key(o)];
      const box = cube(id || 'minecraft:bookshelf', o, { ghost: !id });
      box.classList.add('en-slot-cube');
      if (!open) box.classList.add('en-blocked');
      if (!layerOn(o.y)) box.classList.add('en-dim');
      box.dataset.slot = key(o);
      box.dataset.depth = depthOf(o);
      box.dataset.layer = o.y;
      box._offset = o;
      sockets.set(key(o), box);
      box.title = (open ? (id ? name(id) : 'empty') : 'doorway')
        + ' · ' + o.x + ',' + o.y + ',' + o.z;
      world.appendChild(box);
    }

    /* Fit the camera to the build instead of trusting a scale somebody
       measured once.

       The old number was a flat 1.24, arrived at against a 286px box and this
       exact ring, and it was wrong the moment either changed - which on a
       phone is immediately, and which is what "too zoomed in" was. The bounds
       are computed from the cells actually drawn, the box is measured when it
       lands, and the scale is whichever axis runs out first. Same build at
       every width; just the size it can be. */
    const cells = floor.concat(D.offsets.map(o => ({ x: o.x, y: o.y, z: o.z })));
    const bounds = buildBounds(cells);
    /* Fit the camera to the part of the frame nothing is standing on.

       The drawer overlays the build - down the right on a desk, up from the
       bottom on a phone - so the space the build actually has is the frame
       less whatever the drawer is covering. Measuring the drawer rather than
       assuming its size means the same code handles both arrangements, and
       handles them while the drawer is mid-slide.

       The world hangs off the frame's centre, so centring on the *available*
       region is a matter of shifting by half the difference between the two
       insets - which is what dx and dy are. */
    const fit = () => {
      const box = view.getBoundingClientRect();
      if (!box.width || !box.height) return false;
      const pad = 10;
      let insetR = 0, insetB = 0;
      if (state.tools && sideBox && sideBox.isConnected) {
        /* How much room the drawer takes, from its layout size rather than
           from where it currently is on screen.

           getBoundingClientRect was the obvious thing and it was wrong in a
           way that only showed on the way *in*: the drawer opens by sliding
           from translateX(100%), so at the moment the fit runs it is still
           parked off the right edge and its measured left is the frame's
           right - an inset of nothing. Closing looked fine because nothing is
           the right answer for a shut drawer, and opening left the build
           sitting exactly where it was, which is the "it's static" bug.

           offsetWidth and offsetHeight are the untransformed box, so they
           give the room the drawer is *going* to take the frame it starts
           moving. The build then glides into place alongside it, because the
           world carries a transform transition of its own.

           Which edge it is anchored to is decided by shape, not by size: a
           rail is as tall as the frame, a sheet is as wide as it. Asking
           which inset came out larger got this backwards - a full-height
           rail answers "all of it" to how far up from the bottom it reaches,
           and the build ended up rendered at a fifth of its size. */
        const w = sideBox.offsetWidth, h = sideBox.offsetHeight;
        if (w && h) {
          const fullWidth = w >= box.width * 0.9;
          const fullHeight = h >= box.height * 0.9;
          if (fullWidth && !fullHeight) insetB = h;
          else insetR = w;
        }
        /* Give way, but not the whole frame.

           The phone sheet is over half the stage tall, and taken literally
           that leaves the build ninety pixels to live in - it rendered at
           three tenths of its size, which is not a build anybody can work on.
           A drawer past this much is treated as overlaying the build rather
           than displacing it: the build shrinks as far as the cap and then
           stops, and the sheet simply covers what it covers. Which is the
           right reading of a sheet on a phone anyway - you open it, you pick
           something, you shut it. */
        const CEDE = 0.45;
        insetR = Math.min(insetR, box.width * CEDE);
        insetB = Math.min(insetB, box.height * CEDE);
      }
      const availW = Math.max(60, box.width - insetR - pad * 2);
      const availH = Math.max(60, box.height - insetB - pad * 2);
      const k = Math.min(availW / bounds.w, availH / bounds.h);
      const dx = -insetR / 2, dy = -insetB / 2;
      world.style.transform =
        `translate(${-bounds.cx * k + dx}px, ${-bounds.cy * k + dy}px)`
        + ` rotateX(60deg) rotateZ(-45deg) scale3d(${k}, ${k}, ${k})`;
      return true;
    };
    // redraw calls this after the drawer's class has changed, so the camera
    // re-centres on the same frame the drawer starts moving on
    view._refit = fit;
    // and once more when it has finished, so a drawer whose height settled
    // differently from its layout guess is still accounted for
    if (sideBox) sideBox.addEventListener('transitionend', fit);

    /* The stage is built before the panel it lives in is in the document -
       tableView assembles the whole thing and hands it back, and only then
       does renderTab mount it - so the first measurement is of an element
       with no box at all. Rather than reorder the mount around one
       measurement, this asks again until it gets an answer.

       Not on requestAnimationFrame, or not only. A hidden tab runs no frames
       at all, so a panel opened in one - a middle-click, a restored session,
       a phone with the browser in the background - would sit there with the
       fit never having run and the build drawn at its raw unscaled size,
       which is the one failure that looks worst. A timer runs in a hidden tab
       where a frame does not, so both are used, and the visibility change is
       taken as a cue too. */
    let tries = 0;
    const settle = () => {
      if (fit() || ++tries > 60) return;
      requestAnimationFrame(settle);
      setTimeout(settle, 32);
    };
    settle();
    document.addEventListener('visibilitychange', fit);

    // and again whenever the frame changes size - a phone turning, the window
    // being dragged, the tools column folding underneath the build
    if (window.ResizeObserver) {
      // kept on the view: an observer nothing holds a reference to is a
      // collectable observer, and a build that stops resizing after a garbage
      // collection is not a bug anybody would find twice
      view._fit = new ResizeObserver(fit);
      view._fit.observe(view);
    } else {
      window.addEventListener('resize', fit);
    }

    /* Which socket the pointer is over.

       One handler for the whole stage rather than one per cube, so it can look
       at everything under the pointer and choose, instead of taking whatever
       the browser happened to put on top. Two sockets on a corner overlap on
       screen; filling the near one walls off the far one for good, so placing
       fills the furthest thing under the cursor and a corner fills back to
       front with nothing stranded behind it. Erasing goes the other way, to
       the nearest filled one - which is the one you can actually see. */
    function socketAt(clientX, clientY, erasing) {
      const stack = document.elementsFromPoint(clientX || 0, clientY || 0);
      const cubes = [];
      for (const node of stack) {
        const cubeEl = node.closest && node.closest('.en-slot-cube');
        if (cubeEl && !cubes.includes(cubeEl)
            && !cubeEl.classList.contains('en-blocked')
            && layerOn(Number(cubeEl.dataset.layer))) {
          cubes.push(cubeEl);
        }
      }
      if (!cubes.length) return null;
      const wanted = cubes.filter(c => erasing ? !c.classList.contains('ghost')
                                               : c.classList.contains('ghost'));
      if (!wanted.length) return null;
      wanted.sort((a, b) => erasing
        ? b.dataset.depth - a.dataset.depth
        : a.dataset.depth - b.dataset.depth);
      return wanted[0].dataset.slot;
    }

    /* Painting, rather than clicking thirty times.

       One tap per socket is the thing that made this panel feel like work,
       and it is worse on a phone than anywhere. Holding and dragging runs the
       same placement along everything it passes over, and the rebuild is
       deferred to the next frame - so a fast drag across a dozen sockets is
       one redraw rather than twelve. The fill buttons above are the other
       half of it: nobody should have to lay a wall of hellshelves by hand at
       all. */
    let painting = false, dirty = false;

    const flush = () => {
      if (!dirty) return;
      dirty = false;
      redraw();
    };
    const paint = (clientX, clientY, erasing) => {
      const slot = socketAt(clientX, clientY, erasing);
      if (!slot) return;
      if (erasing) delete state.placed[slot];
      else if (state.placed[slot] === state.brush) return;
      else state.placed[slot] = state.brush;
      if (!dirty) { dirty = true; requestAnimationFrame(flush); }
    };
    const erasingFrom = e => state.erase || e.shiftKey || e.button === 2;

    view.addEventListener('pointerdown', e => {
      if (e.pointerType === 'mouse' && e.button !== 0 && e.button !== 2) return;
      e.preventDefault();
      painting = true;
      // the stage keeps the pointer for the whole stroke, so dragging off the
      // edge and back does not drop it half way through
      try { view.setPointerCapture(e.pointerId); } catch (err) { /* fine */ }
      paint(e.clientX, e.clientY, erasingFrom(e));
    });
    view.addEventListener('pointermove', e => {
      if (!painting) return;
      e.preventDefault();
      paint(e.clientX, e.clientY, erasingFrom(e));
    });
    const stop = () => { painting = false; flush(); };
    view.addEventListener('pointerup', stop);
    view.addEventListener('pointercancel', stop);
    view.addEventListener('contextmenu', e => e.preventDefault());

    view.appendChild(world);
    view._sockets = sockets;
    return view;
  }

  // ── the game's own enchanting window ───────────────────────────────────────

  /* The game window, at two and a half times its texture size.

     2x was 352 pixels of window against 570 of percentages and had the
     proportions backwards; 3x was 528 and had them backwards the other way.
     This is the size in between, and it is a half rather than a whole for a
     reason worth writing down: every offset here is a multiple of SCALE, so
     at 2.5 the odd ones land on half pixels. That is fine - the browser snaps
     a blit to device pixels, and on any 2x display half a CSS pixel is a
     whole device pixel anyway - but it is why the sheet is blitted rather
     than scaled with a transform, which would resample the art instead of
     re-rasterising it. */
  const GUI_W = 176, SCALE = 2.5;
  const px = n => (n * SCALE) + 'px';

  function sheet(sx, sy, w, h) {
    const node = el('div', 'en-blit');
    node.style.width = px(w);
    node.style.height = px(h);
    node.style.backgroundImage = `url(${asset('gui/' + D.gui.enchanting)})`;
    node.style.backgroundSize = px(256) + ' ' + px(256);
    node.style.backgroundPosition = `-${sx * SCALE}px -${sy * SCALE}px`;
    return node;
  }
  function place(node, x, y) {
    node.style.left = px(x);
    node.style.top = px(y);
    return node;
  }
  function guiLabel(text, x, y, cls) {
    const node = el('span', 'en-label ' + (cls || ''), text);
    place(node, x, y);
    return node;
  }

  /* The game's own enchanting window, as far down as the offers.

     The vanilla sheet's top seventy-two rows are the enchant area: the title,
     the book, the item and lapis slots, and the three offer rows. Everything
     below that in the texture is the player's own inventory, which has
     nothing to say here, so it is not blitted.

     Apotheosis draws Eterna/Quanta/Arcana bars under this window in game, and
     this panel used to draw them too. It no longer does: the gauges across
     the top of the build are the same three numbers and two more besides,
     read off the same totals, and having them twice on one screen in two
     different visual languages made the panel look like it was reporting two
     things when it was reporting one. The window keeps what only it can show
     - the offers, their levels and their cost. */
  /* The Standard Galactic Alphabet, blitted a glyph at a time.

     This is the writing the enchanting table puts on its offers, and it is
     deliberately unreadable: the game picks random words from a fixed list
     and draws them in this alphabet, so the row tells you nothing except that
     something is on offer. Same here - the text is gibberish seeded off the
     build and the row, so it is stable while you are looking at it and
     different for each of the three.

     The sheet is font/ascii_sga.png, a 128x128 grid of sixteen by sixteen
     8x8 cells in ASCII order, so a character's cell is (code % 16, code / 16).
     Advances come from the extractor, which measured each glyph rather than
     assuming a fixed cell - a monospaced run of these reads as a code table
     instead of as writing. */
  const SGA_CELL = 8;

  function sgaGlyph(code) {
    const col = code % 16, row = Math.floor(code / 16);
    const node = el('span', 'en-rune');
    node.style.width = px(SGA_CELL);
    node.style.height = px(SGA_CELL);
    node.style.backgroundImage = `url(${asset('gui/' + D.gui.sga)})`;
    node.style.backgroundSize = px(128) + ' ' + px(128);
    node.style.backgroundPosition =
      `-${col * SGA_CELL * SCALE}px -${row * SGA_CELL * SCALE}px`;
    return node;
  }

  /* A line of runes that fits the width given, in the game's own manner: a
     few short words rather than one long string. */
  function runeLine(seed, maxWidth) {
    const rand = rng(seed);
    const line = el('span', 'en-runes');
    let used = 0, wordLeft = 2 + Math.floor(rand() * 5);
    while (used < maxWidth) {
      const code = wordLeft > 0
        ? 97 + Math.floor(rand() * 26)                 // a-z
        : 32;                                          // a space between words
      const width = (D.sga_widths && D.sga_widths[code]) || 6;
      if (used + width > maxWidth) break;
      const glyph = sgaGlyph(code);
      glyph.style.marginRight = px(width - SGA_CELL);
      line.appendChild(glyph);
      used += width;
      wordLeft = wordLeft > 0 ? wordLeft - 1 : 2 + Math.floor(rand() * 5);
    }
    return line;
  }

  function guiPanel(T) {
    const gui = el('div', 'en-gui');
    gui.style.width = px(GUI_W);

    const window_ = el('div', 'en-gui-win');
    window_.style.width = px(GUI_W);
    window_.style.height = px(72);
    window_.appendChild(place(sheet(0, 0, GUI_W, 72), 0, 0));

    /* The two things the table actually takes, in the two slots it takes them
       in - EnchantmentMenu puts the item at (15, 47) and the lapis at (35, 47),
       so that is where they go. Seeing the sword you picked sitting in the
       table is the whole difference between a diagram and a thing you are
       using. */
    /* The book the table keeps open above its slots. The game draws a 3D
       model there and the sheet has no picture of one, so the item's own
       texture stands in - it reads as what it is, which is the point. */
    const book = el('div', 'en-gbook');
    place(book, 22, 12);
    book.appendChild(iconImg('minecraft:book'));
    window_.appendChild(book);

    const slotItem = el('div', 'en-gslot');
    place(slotItem, 15, 47);
    slotItem.appendChild(iconImg(itemIcon()));
    window_.appendChild(slotItem);

    const slotLapis = el('div', 'en-gslot');
    place(slotLapis, 35, 47);
    slotLapis.appendChild(iconImg('minecraft:lapis_lazuli'));
    const count = el('b', null, String(state.slot + 1));
    slotLapis.appendChild(count);
    window_.appendChild(slotLapis);

    const levels = slotLevels(T.eterna);
    levels.forEach((lv, row) => {
      const on = row === state.slot;
      const live = lv.max > 0 && T.eterna > 0;
      const strip = place(sheet(0, !live ? 185 : on ? 204 : 166, 108, 19),
                          60, 14 + 19 * row);
      strip.className += ' en-row' + (on ? ' on' : '') + (live ? '' : ' dead');
      if (live) {
        const orb = place(sheet(16 * row, 224, 16, 16), 61, 15 + 19 * row);
        orb.className += ' en-orb';
        window_.appendChild(orb);
      }
      if (live) {
        // the runes sit between the level orb and the cost, where the game
        // writes them, and are seeded so they hold still while you read
        const runes = runeLine((state.seed ^ (row * 0x9E3779B1)) >>> 0, 62);
        place(runes, 80, 17 + 19 * row);
        runes.className += ' en-runes';
        window_.appendChild(runes);
      }
      window_.appendChild(guiLabel(String(row + 1), 68, 18 + 19 * row, 'en-lapis'));
      window_.appendChild(guiLabel(live ? String(lv.exact ? lv.min : lv.max) : '',
                                   164, 25 + 19 * row, 'en-need'));
      strip.addEventListener('click', () => {
        if (!live) return;
        state.slot = row;
        redraw();
      });
      window_.appendChild(strip);
    });
    gui.appendChild(window_);

    return gui;
  }

  // ── the panel ──────────────────────────────────────────────────────────────

  let isoBox = null, statBox = null, castBox = null, sideBox = null;

  function tableView() {
    const wrap = el('div', 'en-table');

    const work = el('div', 'en-work');

    const main = el('div', 'en-main');
    statBox = el('div', 'en-statbar');
    isoBox = el('div', 'en-stage-box');
    main.append(statBox, isoBox);

    /* The tools sit *on* the build now rather than beside it.

       Beside it, they took a fixed three hundred pixels off the right of the
       panel for the whole time the panel was open - which is what "the render
       is more to the left" was. The build was centred in its own frame the
       whole time; the frame was the thing sitting left, because a column of
       controls was holding the other half of the panel open whether you were
       using it or not.

       As a drawer over the build, the stage gets the full width of the panel
       and the camera centres in whatever the drawer is not covering - see
       fit(), which insets by the drawer's own measured size. Closed, the
       build has the whole panel and is centred in it. */
    sideBox = el('aside', 'en-side');
    main.appendChild(toolsToggle());
    work.appendChild(main);
    wrap.appendChild(work);

    castBox = el('div', 'en-cast');
    wrap.appendChild(castBox);

    if (!Object.keys(state.placed).length) state.placed = layout('Vanilla 15');
    redraw();
    return wrap;
  }

  /* Redraw, without rebuilding the world.

     The stage is fifty-odd cubes of five textured faces each, and it used to
     be thrown away and built again on every change - including every frame of
     a drag, which is what made painting feel like wading. It is built once
     now and the sockets are updated in place: the same divs get different
     background images. Everything else on the panel is cheap enough to
     rebuild, so it still is. */
  let stageView = null;

  function redraw() {
    if (!isoBox) return;
    const T = buildTotals();
    drawStatbar(T);
    if (!stageView || !stageView.isConnected) {
      isoBox.innerHTML = '';
      stageView = isoStage();
      // the drawer lives inside the stage box too, and emptying the box to
      // rebuild the world takes it with it - so it goes back afterwards, and
      // after the stage rather than before it, because it sits on top
      isoBox.append(stageView, sideBox);
    } else {
      syncStage();
    }
    drawSide(T);
    drawCast(T);
    // the handle carries the current brush, so it changes when the brush does
    const old = isoBox.parentNode.querySelector('.en-tools-btn');
    if (old) old.replaceWith(toolsToggle());
    refit();
  }

  /* Re-centre the camera on whatever the drawer has left it. Called after
     every redraw, because opening or shutting the drawer changes the space
     the build has without changing the build. */
  function refit() {
    if (stageView && stageView._refit) stageView._refit();
  }

  /* The sockets, brought up to date. One pass over the map the stage kept:
     what is in the slot now, whether the slot is reachable at all, and
     whether its layer is the one being worked on. */
  function syncStage() {
    const sockets = stageView && stageView._sockets;
    if (!sockets) return;
    for (const [slot, box] of sockets) {
      const o = box._offset;
      const id = state.placed[slot];
      const open = usable(o);
      paintCube(box, id || 'minecraft:bookshelf');
      box.classList.toggle('ghost', !id);
      box.classList.toggle('en-blocked', !open);
      box.classList.toggle('en-dim', !layerOn(o.y));
      box.title = (open ? (id ? name(id) : 'empty') : 'doorway')
        + ' · ' + o.x + ',' + o.y + ',' + o.z;
    }
  }

  /* The five readings, across the top of the build they come from.

     These are the panel's headline and the reason to move a shelf at all, so
     they are gauges rather than five coloured boxes: a value that reads
     against its own ceiling, a track that fills, and one line saying what the
     number buys you. Each keeps one colour everywhere it appears - in the
     gauge, on a palette chip, on an infusion requirement - so a reading is
     the same colour wherever you meet it.

     Clues is the odd one and is meant to be. The other four are quantities
     with a ceiling you are pushing against; clues is how much of the result
     you are allowed to see before you commit, which is not a quantity of the
     same kind. It gets the spectrum, which is also the colour the game itself
     puts on an enchantment you cannot read yet. */
  function drawStatbar(T) {
    statBox.innerHTML = '';
    const maxE = D.constants.max_eterna;
    const pills = [
      ['e', 'Eterna', T.eterna, maxE,
       Math.round(T.eterna * D.constants.levels_per_eterna) + ' levels',
       'of ' + round1(maxE)],
      ['q', 'Quanta', T.quanta, 100, '\u00b1' + round1(T.quanta) + '% swing', 'of 100'],
      ['a', 'Arcana', T.arcana, 100,
       arcanaTier(T.arcana).name.toLowerCase() + ' \u00b7 '
         + arcanaGuarantee(T.arcana) + ' guaranteed', 'of 100'],
      ['r', 'Rect', T.rect, 100, T.quanta
        ? Math.round(100 * (1 - (T.quanta / 100) * (1 - T.rect / 100))) + '% floor'
        : 'nothing to lift', 'of 100'],
      ['c', 'Clues', T.clues, 8, T.clues + ' of 3 shown', 'of 8'],
    ];
    for (const [cls, label, value, max, note, ceiling] of pills) {
      const pill = el('div', 'en-pill ' + cls);
      const top = el('div', 'en-pill-top');
      top.appendChild(el('i', null, label));
      pill.appendChild(top);

      const read = el('div', 'en-pill-read');
      const b = el('b', null, round1(value));
      read.append(b, el('em', null, ceiling));
      pill.appendChild(read);

      const track = el('div', 'en-gauge');
      const fill = el('span', value < 0 ? 'neg' : null);
      track.appendChild(fill);
      pill.append(track, el('span', 'en-pill-note', note));
      statBox.appendChild(pill);

      // the fill grows into place rather than appearing at its width, which
      // is what makes a shelf going down read as a stat going up
      requestAnimationFrame(() => {
        fill.style.width = clamp(Math.abs(value) / max * 100, 0, 100) + '%';
      });
      motion(b, [{ transform: 'translateY(-4px)', opacity: .4 },
                 { transform: 'none', opacity: 1 }],
        { duration: 260, easing: 'cubic-bezier(.2,.8,.3,1)' });
    }
  }

  // ── building ───────────────────────────────────────────────────────────────

  /* Fill every reachable socket of the layers given with the current brush.

     The point of the whole panel is what a wall of one shelf is worth, and
     laying that wall a socket at a time is thirty taps of nothing. Fill is
     the answer to that, and it is why the presets no longer have to be the
     only fast route to a real build. */
  function fillLayers(layers) {
    for (const o of ringSlots(layers)) state.placed[key(o)] = state.brush;
  }
  function clearLayers(layers) {
    for (const o of D.offsets) {
      if (layers.includes(o.y)) delete state.placed[key(o)];
    }
  }
  function activeLayers() {
    return state.layer === 'both' ? [0, 1] : [state.layer];
  }

  /* The handle on the drawer.

     It carries the brush rather than only a word, because the one thing you
     need to know while the drawer is shut is what a click is about to put
     down - and a picture of the block answers that without opening anything.
     It lives outside .en-stage-box's overflow so it cannot be clipped, and it
     is a real button with aria-expanded so it works from a keyboard. */
  function toolsToggle() {
    const btn = el('button', 'en-tools-btn' + (state.tools ? ' on' : ''));
    btn.type = 'button';
    btn.setAttribute('aria-expanded', state.tools ? 'true' : 'false');
    btn.setAttribute('aria-controls', 'en-tools');
    const brush = BY.block[state.brush];
    if (brush) btn.appendChild(iconImg(brush.id, 'sm'));
    btn.appendChild(el('b', null, state.erase ? 'Removing'
      : (brush ? name(brush.id) : 'Build tools')));
    btn.appendChild(el('i', null, state.tools ? 'Hide tools' : 'Build tools'));
    btn.addEventListener('click', () => { state.tools = !state.tools; redraw(); });
    return btn;
  }

  function toolButton(label, cls, onClick, title) {
    const btn = el('button', cls, label);
    btn.type = 'button';
    if (title) btn.title = title;
    btn.addEventListener('click', onClick);
    return btn;
  }

  /* The tools, the palette, and one line saying what the palette is pointing
     at. Three things, in the order you use them. */
  function drawSide(T) {
    sideBox.innerHTML = '';
    sideBox.id = 'en-tools';
    sideBox.classList.toggle('on', state.tools);
    // shut, it is out of the tab order as well as off the screen - a drawer
    // you cannot see should not be a drawer you can tab into
    sideBox.inert = !state.tools;
    sideBox.setAttribute('aria-hidden', state.tools ? 'false' : 'true');

    // a way out from inside, for a phone where the handle is behind the sheet
    const shut = toolButton('\u00d7', 'en-tools-shut',
      () => { state.tools = false; redraw(); }, 'Hide the build tools');
    shut.setAttribute('aria-label', 'Hide the build tools');
    sideBox.appendChild(shut);

    // ── presets ──
    const presets = el('div', 'en-presets');
    presets.appendChild(el('span', 'en-side-lbl', 'Preset'));
    for (const label of Object.keys(PRESETS)) {
      presets.appendChild(toolButton(label, 'en-preset',
        () => { state.placed = layout(label); redraw(); }));
    }
    sideBox.appendChild(presets);

    /* ── which layer, and whether there is a way in ──

       Both of these were fixed before. The upper ring hides the lower one at
       this camera angle, so working on the lower one meant working blind; and
       the doorway was struck out of the offsets outright, which put two of
       the game's thirty-two sockets permanently out of reach along with the
       eterna they carry. */
    const rowLayer = el('div', 'en-toolrow');
    rowLayer.appendChild(el('span', 'en-side-lbl', 'Layer'));
    const layers = el('div', 'en-segs');
    for (const [value, label] of [['both', 'Both'], [0, 'Lower'], [1, 'Upper']]) {
      layers.appendChild(toolButton(label,
        'en-seg' + (state.layer === value ? ' on' : ''),
        () => { state.layer = value; redraw(); }));
    }
    rowLayer.appendChild(layers);
    sideBox.appendChild(rowLayer);

    // ── place, remove, fill, clear ──
    const rowDo = el('div', 'en-toolrow');
    rowDo.appendChild(el('span', 'en-side-lbl', 'Brush'));
    /* Place or remove, as a switch. There is no shift key on a phone and a
       long press is a guess nobody can see, so the mode is a control - but
       shift and right-click still work for anyone who has them. */
    const modes = el('div', 'en-segs');
    for (const [erase, label] of [[false, 'Place'], [true, 'Remove']]) {
      modes.appendChild(toolButton(label,
        'en-seg' + (state.erase === erase ? ' on' : ''),
        () => { state.erase = erase; redraw(); }));
    }
    rowDo.appendChild(modes);
    rowDo.appendChild(toolButton('Fill', 'en-act',
      () => { fillLayers(activeLayers()); redraw(); },
      'Fill every open socket of the layers in view with the selected block'));
    rowDo.appendChild(toolButton('Clear', 'en-act clear',
      () => { clearLayers(activeLayers()); redraw(); },
      'Empty the layers in view'));
    sideBox.appendChild(rowDo);

    /* How full the ring is, against the only number that matters: thirty.
       The table reads thirty-two sockets and two of them are the door, so
       thirty is a full build and there is no arrangement anywhere that beats
       it. Worth saying outright - "15 of 30" is the difference between a
       vanilla ring and a finished one, and nothing else on the panel says
       which of those you are looking at. */
    const filled = Object.keys(state.placed).filter(k => state.placed[k]).length;
    const count = el('div', 'en-fill');
    count.appendChild(el('span', null, filled + ' of ' + (SOCKETS - 2) + ' placed'));
    const bar = el('div', 'en-meter');
    const lit = el('span');
    lit.style.width = (100 * filled / (SOCKETS - 2)) + '%';
    bar.appendChild(lit);
    count.appendChild(bar);
    sideBox.appendChild(count);

    // ── the blocks themselves ──
    sideBox.appendChild(palette());
  }

  /* The palette: every enchanting block at once, as the blocks.

     This was thirty-one rows of name-plus-chips in a box 188 pixels tall, so
     you were reading a list through a letterbox and scrolling it to find a
     shelf you already knew the look of. They are sprites in a grid now - the
     game's own inventory, more or less - which fits all of them in less room
     than the letterbox took, needs no scrolling at any width, and gives a
     finger something the size of a finger to hit.

     The numbers did not go anywhere; they moved to one line under the grid,
     which shows whatever you are pointing at and falls back to what is
     selected. One block's stats at a time is what anybody reads anyway, and
     it is the difference between a wall of chips and a fact. */
  function palette() {
    const wrap = el('div', 'en-palette');

    const grid = el('div', 'en-pal-grid');
    const blocks = D.blocks.filter(b => !b.is_tag);
    const detail = el('div', 'en-pal-detail');

    const show = block => {
      detail.innerHTML = '';
      if (!block) return;
      detail.appendChild(iconImg(block.id, 'sm'));
      detail.appendChild(el('b', null, name(block.id)));
      const chips = el('span', 'en-brush-stats');
      for (const [k, label, cls] of [
        ['eterna', 'E', 'e'], ['quanta', 'Q', 'q'], ['arcana', 'A', 'a'],
        ['rectification', 'R', 'r'], ['clues', 'C', 'c'],
      ]) {
        const v = block[k];
        if (!v) continue;
        chips.appendChild(el('i', 'st ' + cls + (v < 0 ? ' neg' : ''),
          label + (v > 0 ? '+' : '') + round1(v)));
      }
      if (block.maxEterna) {
        chips.appendChild(el('i', 'st cap', '≤' + round1(block.maxEterna)));
      }
      // the Treasure Shelf gives no stats at all - what it does is let the
      // pool keep its treasure enchantments, which is the only route to
      // Mending at a table
      if (block.allows_treasure) {
        chips.appendChild(el('i', 'st treasure', 'treasure'));
      }
      if (!chips.childNodes.length) {
        chips.appendChild(el('i', 'st', 'no stats'));
      }
      detail.appendChild(chips);
    };

    for (const block of blocks) {
      const on = state.brush === block.id && !state.erase;
      const tile = el('button', 'en-pal' + (on ? ' on' : ''));
      tile.type = 'button';
      const n = Object.values(state.placed).filter(id => id === block.id).length;
      tile.appendChild(iconImg(block.id));
      if (n) tile.appendChild(el('u', null, String(n)));
      // the name is on the tile for a pointer and read out by the line below
      // for everyone else, so nothing here depends on being able to hover
      tile.title = name(block.id);
      tile.setAttribute('aria-label', name(block.id));
      tile.addEventListener('pointerenter', () => show(block));
      tile.addEventListener('focus', () => show(block));
      tile.addEventListener('click', () => {
        state.brush = block.id;
        state.erase = false;
        state.detail = block.id;
        redraw();
      });
      grid.appendChild(tile);
    }
    grid.addEventListener('pointerleave', () => show(BY.block[state.brush]));

    wrap.append(grid, detail);
    show(BY.block[state.detail] || BY.block[state.brush] || blocks[0]);
    return wrap;
  }

  /* The picker, the window, what came out of it, and the odds - all in one
     row so nothing has to be hunted for.

     The item used to be a select buried in the side panel, which is the one
     control on this page you change most and the one that was hardest to
     find. It is a row of the actual items now, and the one you pick is drawn
     into the table's own item slot, which is where it would be in game. */
  function drawCast(T) {
    castBox.innerHTML = '';

    const picker = el('div', 'en-picker');
    for (const entry of ITEMS) {
      const on = state.item === entry.id;
      const btn = el('button', 'en-pick' + (on ? ' on' : ''));
      btn.type = 'button';
      btn.title = entry.name + ' \u00b7 enchantability '
        + (entry.id === '__custom__' ? state.ench : entry.ench);
      if (entry.id === '__custom__') btn.appendChild(el('span', 'en-pick-any', '?'));
      else btn.appendChild(iconImg(entry.id));
      btn.addEventListener('click', () => { state.item = entry.id; redraw(); });
      picker.appendChild(btn);
    }
    castBox.appendChild(picker);

    // the custom piece's own numbers, only while it is the one selected
    const custom = el('div', 'en-custom'
      + (currentItem().id === '__custom__' ? ' on' : ''));
    const kindPick = document.createElement('select');
    for (const kind of D.kinds) {
      kindPick.appendChild(option(kind, kind.replace('_', ' ')));
    }
    kindPick.value = state.kind;
    kindPick.addEventListener('change', () => { state.kind = kindPick.value; redraw(); });
    custom.appendChild(labelledField('Slot', kindPick));
    const enchIn = document.createElement('input');
    enchIn.type = 'number';
    enchIn.min = '0';
    enchIn.max = '200';
    enchIn.value = state.ench;
    enchIn.addEventListener('input', () => {
      const v = parseInt(enchIn.value, 10);
      state.ench = Number.isFinite(v) ? clamp(v, 0, 200) : 0;
      redraw();
    });
    custom.appendChild(labelledField('Enchantability', enchIn));
    castBox.appendChild(custom);

    const row = el('div', 'en-cast-row');

    const left = el('div', 'en-cast-gui');
    /* The window is a fixed 440 of game texture and a phone is 375 of screen,
       so on a narrow panel it has to come down to fit.

       It used to come down by a flat 0.84 under a 420px media query, which
       was a guess at one width and wrong at every other - at 2.5x it left a
       440px window scaled to 370 inside a 264px column, and the panel's own
       overflow:hidden quietly cut the right-hand third of the enchanting
       window off. Scaling to the box it is actually in cannot be wrong at any
       width, and it is the same measure-then-fit the build's camera uses.

       The scale is a transform rather than a smaller SCALE because SCALE is
       what the blits are computed from: changing it re-rasterises every
       offset in the sheet, where a transform takes the window as drawn and
       shrinks the whole thing evenly. */
    const guiFit = el('div', 'en-gui-fit');
    guiFit.appendChild(guiPanel(T));
    left.appendChild(guiFit);
    fitGui(guiFit);
    const roll = el('button', 'en-roll');
    roll.type = 'button';
    roll.innerHTML = '<span>Enchant</span>';
    roll.disabled = !(T.eterna > 0);
    roll.addEventListener('click', () => {
      state.seed = (Math.random() * 1e9) | 0;
      state.result = rollOffer(T, state.slot, state.seed);
      redraw();
      motion(castBox.querySelector('.en-result'),
        [{ opacity: 0, transform: 'translateY(8px) scale(.98)' },
         { opacity: 1, transform: 'none' }],
        { duration: 340, easing: 'cubic-bezier(.2,.8,.3,1)' });
    });
    left.appendChild(roll);
    row.appendChild(left);

    const right = el('div', 'en-cast-out');

    const result = el('div', 'en-result');
    if (state.result && state.result.chosen.length) {
      const head = el('div', 'en-result-head');
      head.appendChild(iconImg(itemIcon(), 'sm'));
      head.appendChild(el('b', null, currentItem().name));
      head.appendChild(el('em', null, state.result.power + ' power'));
      result.appendChild(head);
      state.result.chosen.forEach((got, i) => {
        const line = el('div', 'en-got r-' + got.ench.rarity.toLowerCase());
        line.appendChild(el('b', null, got.ench.name));
        line.appendChild(el('i', null, roman(got.level)));
        result.appendChild(line);
        motion(line, [{ opacity: 0, transform: 'translateX(-10px)' },
                      { opacity: 1, transform: 'none' }],
          { duration: 300, delay: 90 + i * 80, easing: 'cubic-bezier(.2,.8,.3,1)' });
      });
    } else {
      result.appendChild(el('p', 'en-none',
        state.result ? 'nothing at this power' : '\u2014'));
    }
    right.appendChild(result);

    const odds = oddsFor(T, state.slot);
    const bars = el('div', 'en-oddbars');
    const top = odds.rows.slice(0, 60);
    const most = top.length ? top[0].pct : 1;
    top.forEach((entry, i) => {
      const line = el('div', 'en-oddbar r-' + entry.ench.rarity.toLowerCase()
                      + (entry.ench.assumed ? ' guess' : ''));
      const label = el('i', null, entry.ench.name + ' ' + roman(entry.level));
      if (entry.ench.assumed) label.title = entry.ench.mod + ' \u2014 curve assumed';
      line.appendChild(label);
      const track = el('div', 'en-meter');
      const fill = el('span');
      track.appendChild(fill);
      line.appendChild(track);
      line.appendChild(el('b', null, pct(entry.pct)));
      bars.appendChild(line);
      requestAnimationFrame(() => { fill.style.width = (100 * entry.pct / most) + '%'; });
      motion(line, [{ opacity: 0 }, { opacity: 1 }],
        { duration: 220, delay: Math.min(i, 20) * 26, easing: 'ease-out' });
    });
    if (!top.length) bars.appendChild(el('p', 'en-none', '\u2014'));
    right.appendChild(bars);

    row.appendChild(right);
    castBox.appendChild(row);
  }

  /* Scale the game window to whatever width its column has, and give the
     wrapper the height the scaled thing actually occupies - a transform does
     not change layout, so without this the row keeps a 440-wide window's
     worth of height under a window drawn at half that.

     Deferred a frame on first call because the panel is assembled before it
     is mounted, so there is no column to measure yet; and re-run on resize,
     because the column changes with the panel. */
  function fitGui(box) {
    const gui = box.firstChild;
    if (!gui) return;
    const run = () => {
      const avail = box.parentNode && box.parentNode.clientWidth;
      if (!avail) return false;
      const k = Math.min(1, avail / (GUI_W * SCALE));
      gui.style.transformOrigin = 'top left';
      gui.style.transform = k < 1 ? `scale(${k})` : '';
      box.style.height = Math.ceil(gui.offsetHeight * k) + 'px';
      return true;
    };
    if (!run()) {
      let tries = 0;
      const settle = () => {
        if (run() || ++tries > 40) return;
        requestAnimationFrame(settle);
        setTimeout(settle, 32);
      };
      settle();
    }
    if (window.ResizeObserver && box.parentNode) {
      box._fit = new ResizeObserver(run);
      box._fit.observe(box.parentNode);
    }
  }

  /* Custom gear has no item of its own, so it borrows the icon of whatever
     slot it says it is - a picture of the thing beats an empty frame. */
  function itemIcon() {
    const item = currentItem();
    if (item.id !== '__custom__') return item.id;
    const stand = ITEMS.find(i => i.id !== '__custom__' && i.kind === state.kind);
    return stand ? stand.id : 'minecraft:book';
  }

  /* Whole per cents. "21.7%" is three characters of precision nobody is
     acting on and it was the widest column on the row. */
  function pct(value) {
    if (value >= 1) return Math.round(value) + '%';
    return value >= 0.05 ? '<1%' : '0%';
  }

  const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
                 'XI', 'XII', 'XIII', 'XIV', 'XV'];
  function roman(n) { return ROMAN[n] || String(n); }

  function labelledField(text, control) {
    const wrap = el('label', 'en-field');
    wrap.appendChild(el('span', null, text));
    wrap.appendChild(control);
    return wrap;
  }

  // ── the catalog ────────────────────────────────────────────────────────────

  let catView = 'enchants';
  const catState = { search: '', rarity: '', mod: '', open: null };

  function catalog() {
    const wrap = el('div', 'en-catalog');
    const nav = el('nav', 'en-subnav');
    for (const [key, label] of [['enchants', 'Enchantments']]) {
      const btn = el('button', 'en-sub' + (key === catView ? ' active' : ''), label);
      btn.addEventListener('click', () => { catView = key; renderTab('catalog'); });
      nav.appendChild(btn);
    }
    wrap.appendChild(nav);
    wrap.appendChild(enchantView());
    return wrap;
  }

  /* Every enchantment the pack loads, and the one number worth having for
     each: how far Apotheosis lets it go. Protection to 8, Feather Falling to
     11, Sharpness to 8 - all of them raised well past vanilla, and none of it
     visible anywhere in game except by enchanting one and looking. */
  function enchantView() {
    const view = el('div');
    const bar = el('div', 'en-toolbar');

    const search = document.createElement('input');
    search.type = 'search';
    search.placeholder = 'Search enchantments';
    search.value = catState.search;
    search.addEventListener('input', () => {
      catState.search = search.value.toLowerCase();
      paint();
    });
    bar.appendChild(labelled('Find', search));

    const rarity = document.createElement('select');
    rarity.appendChild(option('', 'any rarity'));
    for (const r of D.rarities) {
      rarity.appendChild(option(r, r.replace('_', ' ').toLowerCase()));
    }
    rarity.value = catState.rarity;
    rarity.addEventListener('change', () => { catState.rarity = rarity.value; paint(); });
    bar.appendChild(labelled('Rarity', rarity));

    const mods = [...new Set(D.enchants.map(e => e.mod))].sort();
    const modPick = document.createElement('select');
    modPick.appendChild(option('', 'every mod (' + mods.length + ')'));
    for (const m of mods) modPick.appendChild(option(m, m));
    modPick.value = catState.mod;
    modPick.addEventListener('change', () => { catState.mod = modPick.value; paint(); });
    bar.appendChild(labelled('From', modPick));

    const count = el('span', 'en-count');
    bar.appendChild(count);
    view.appendChild(bar);

    const list = el('div', 'en-ench-list');
    view.appendChild(list);

    function paint() {
      list.innerHTML = '';
      const rows = D.enchants.filter(e => {
        if (catState.rarity && e.rarity !== catState.rarity) return false;
        if (catState.mod && e.mod !== catState.mod) return false;
        if (catState.search) {
          const hay = (e.name + ' ' + e.id).toLowerCase();
          if (!hay.includes(catState.search)) return false;
        }
        return true;
      });
      rows.sort((a, b) => b.max - a.max || a.name.localeCompare(b.name));
      count.textContent = rows.length + ' of ' + D.enchants.length;
      if (!rows.length) {
        list.appendChild(el('p', 'en-empty', 'Nothing matches.'));
        return;
      }
      rows.forEach((e, i) => {
        const card = el('article', 'en-ench r-' + e.rarity.toLowerCase());
        const top = el('div', 'en-ench-top');
        top.appendChild(el('b', 'en-ench-name', e.name));
        const lv = el('span', 'en-ench-lv');
        lv.appendChild(el('b', null, String(e.max)));
        lv.appendChild(el('i', null, 'max'));
        top.appendChild(lv);
        card.appendChild(top);

        const meta = el('div', 'en-ench-meta');
        meta.appendChild(el('span', 'chip rarity', e.rarity.replace('_', ' ').toLowerCase()));
        if (e.loot < e.max) {
          meta.appendChild(el('span', 'chip', 'loot caps at ' + e.loot));
        }
        if (e.treasure) meta.appendChild(el('span', 'chip warn', 'treasure only'));
        if (!e.discoverable) meta.appendChild(el('span', 'chip warn', 'not from the table'));
        if (!e.tradeable) meta.appendChild(el('span', 'chip', 'no villager trade'));
        meta.appendChild(el('span', 'chip mod', e.mod));
        card.appendChild(meta);
        list.appendChild(card);

        motion(card, [{ opacity: 0, transform: 'translateY(6px)' },
                      { opacity: 1, transform: 'none' }],
          { duration: 280, delay: Math.min(i, 24) * 14, easing: 'ease-out' });
      });
    }
    paint();
    return view;
  }

  function option(value, text) {
    const node = document.createElement('option');
    node.value = value;
    node.textContent = text;
    return node;
  }
  function labelled(text, control) {
    const wrap = el('label', 'en-tool');
    wrap.appendChild(el('span', null, text));
    wrap.appendChild(control);
    return wrap;
  }

  // ── tabs ───────────────────────────────────────────────────────────────────

  function renderTab(tab) {
    stage.innerHTML = '';
    const bar = el('nav', 'en-tabs');
    for (const [key, label] of [['table', 'Table'], ['catalog', 'Catalog']]) {
      const btn = el('button', 'en-tab' + (key === tab ? ' active' : ''), label);
      btn.addEventListener('click', () => renderTab(key));
      bar.appendChild(btn);
    }
    stage.appendChild(bar);
    stage.appendChild(tab === 'catalog' ? catalog() : tableView());
  }

  // ── boot ───────────────────────────────────────────────────────────────────

  let mounted = false;
  const wrap = document.getElementById('en-wrap');

  window.enchOpen = function () {
    wrap.classList.add('on');
    if (!mounted) { mounted = true; load(); }
    requestAnimationFrame(() =>
      wrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' }));
  };

  window.enchShut = function () {
    if (window.workshopShut) window.workshopShut(wrap);
    else { wrap.classList.remove('on'); wrap.scrollIntoView({ block: 'nearest' }); }
  };

  function load() {
    fetch(asset('enchanting.json'))
      .then(r => r.json())
      .then(data => {
        D = data;
        for (const block of D.blocks) BY.block[block.id] = block;
        for (const ench of D.enchants) BY.ench[ench.id] = ench;
        state.placed = layout('Vanilla 15');
        renderTab('table');
      })
      .catch(error => {
        mounted = false;                   // opening again retries
        stage.innerHTML = '';
        stage.appendChild(el('p', 'en-loading',
          'Could not read the pack data: ' + error));
      });
  }
})();
