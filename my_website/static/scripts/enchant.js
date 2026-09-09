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

  /* The gap you stand in.

     A ring with no way in is not a build anybody makes, and it is also what
     makes fifteen the famous number: the ring is sixteen positions a layer,
     leave the doorway out and a single layer is exactly fifteen. */
  const DOORWAY = o => o.x === 0 && o.z === 2;

  function ringSlots(layers) {
    return D.offsets.filter(o => layers.includes(o.y) && !DOORWAY(o));
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
      for (let lvl = ench.max; lvl >= 1; lvl--) {
        if (power >= minPower(ench, lvl)) { out.push({ ench, level: lvl }); break; }
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

  /* RealEnchantmentHelper.selectEnchantment, as far as it can be followed:
     modify the power by the quanta factor, draw one by weight, then keep
     drawing while rand.nextInt(50) <= n, halving n each time - with
     Apotheosis' cap that resets n to 1.15x the *base* power once the modified
     power runs past 45. */
  function rollOffer(T, slotIndex, seed) {
    const rand = rng(seed);
    const C = D.constants;
    const levels = slotLevels(T.eterna);
    const lv = levels[slotIndex];
    const base = lv.exact ? lv.min
      : Math.max(1, Math.round(lv.min + rand() * (lv.max - lv.min)));

    const r = T.rect / 100;
    let f = clamp(gauss(rand) / C.quanta_gaussian_divisor, -1, 1);
    if (f < r - 1) f = (r - 1) + rand() * (1 - (r - 1));
    const power = clamp(Math.round(base * (1 + T.quanta * f / 100)), 1, C.power_ceiling);

    const item = currentItem();
    const tier = arcanaTier(T.arcana);
    let pool = poolAt(power, item, T.treasure);
    const chosen = [];
    if (pool.length) {
      const pick = () => {
        const total = pool.reduce((a, e) => a + weightOf(e, tier), 0);
        let roll = rand() * total;
        for (const entry of pool) {
          roll -= weightOf(entry, tier);
          if (roll <= 0) return entry;
        }
        return pool[pool.length - 1];
      };
      const take = () => {
        const got = pick();
        chosen.push(got);
        pool = pool.filter(e => !clashes(e.ench.id, got.ench.id));
      };
      take();
      let n = power;
      if (n > C.extra_roll_cap) n = Math.trunc(base * C.extra_roll_scale);
      while (Math.floor(rand() * C.extra_roll_die) <= n && pool.length) {
        take();
        n = Math.floor(n / 2);
      }
      // arcana's two thresholds guarantee a second and a third
      const want = arcanaGuarantee(T.arcana);
      while (chosen.length < want && pool.length) take();
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
    for (const [face, tex] of [['top', 'top'], ['w-n', 'side'], ['w-s', 'side'],
                               ['w-e', 'side'], ['w-w', 'side']]) {
      const side = el('div', 'f ' + face);
      const url = faceTexture(id, tex);
      if (url) side.style.backgroundImage = `url(${url})`;
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

  function isoStage() {
    const view = el('div', 'en-iso');
    const world = el('div', 'en-iso-world');

    for (let x = -2; x <= 2; x++) {
      for (let z = -2; z <= 2; z++) {
        const tile = cube('minecraft:obsidian', { x, y: -1, z });
        tile.classList.add('en-cube-floor');
        world.appendChild(tile);
      }
    }
    const table = cube('minecraft:enchanting_table', { x: 0, y: 0, z: 0 },
                       { height: 0.75 });
    table.classList.add('en-cube-table');
    world.appendChild(table);

    for (const o of D.offsets) {
      if (DOORWAY(o)) continue;
      const id = state.placed[key(o)];
      const box = cube(id || 'minecraft:bookshelf', o, { ghost: !id });
      box.classList.add('en-slot-cube');
      box.dataset.slot = key(o);
      box.dataset.depth = depthOf(o);
      box.title = (id ? name(id) : 'empty') + ' · ' + o.x + ',' + o.y + ',' + o.z;
      world.appendChild(box);
    }

    /* One handler for the whole stage rather than one per cube, so it can look
       at everything under the pointer and choose, instead of taking whatever
       the browser happened to put on top. */
    const hit = e => {
      e.preventDefault();
      const stack = document.elementsFromPoint(
        e.clientX !== undefined ? e.clientX : 0,
        e.clientY !== undefined ? e.clientY : 0);
      const cubes = [];
      for (const node of stack) {
        const cubeEl = node.closest && node.closest('.en-slot-cube');
        if (cubeEl && !cubes.includes(cubeEl)) cubes.push(cubeEl);
      }
      if (!cubes.length) return;
      const erasing = state.erase || e.shiftKey || e.button === 2
        || e.type === 'contextmenu';
      // placing goes to the furthest empty socket, erasing to the nearest
      // filled one - which is the one you can actually see and meant to click
      const wanted = cubes.filter(c => erasing ? !c.classList.contains('ghost')
                                               : c.classList.contains('ghost'));
      if (!wanted.length) return;
      wanted.sort((a, b) => erasing
        ? b.dataset.depth - a.dataset.depth
        : a.dataset.depth - b.dataset.depth);
      const slot = wanted[0].dataset.slot;
      if (erasing) delete state.placed[slot];
      else state.placed[slot] = state.brush;
      redraw();
    };
    view.addEventListener('click', hit);
    view.addEventListener('contextmenu', hit);

    view.appendChild(world);
    return view;
  }

  // ── the game's own enchanting window ───────────────────────────────────────

  const GUI_W = 176, SCALE = 2;
  let D_MAX_ETERNA = 50;
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

  /* The game's own enchanting window, as far down as the offers - and then
     the three bars Apotheosis adds under them.

     The vanilla sheet's top seventy-two rows are the enchant area: the title,
     the book, the item and lapis slots, and the three offer rows. Everything
     below that in the texture is the player's own inventory, which has nothing
     to say here, so it is not blitted. The Eterna/Quanta/Arcana bars are not
     in the sheet at all - Apotheosis draws them itself - so they are drawn
     here too, in the same three colours the mod uses. */
  const GUI_STAT_ROWS = [
    ['e', 'Eterna', '#3ec13e', T => T.eterna, D_MAX_ETERNA],
    ['q', 'Quanta', '#c14040', T => T.quanta, 100],
    ['a', 'Arcana', '#a445c4', T => T.arcana, 100],
  ];

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

    // the three bars, in the mod's own colours
    const bars = el('div', 'en-gui-stats');
    for (const [cls, label, colour, get, max] of GUI_STAT_ROWS) {
      const row = el('div', 'en-gbar ' + cls);
      row.style.setProperty('--lit', colour);
      row.appendChild(el('i', null, label));
      const track = el('div', 'en-gtrack');
      const fill = el('span');
      fill.style.width = clamp(get(T) / max * 100, 0, 100) + '%';
      track.appendChild(fill);
      row.appendChild(track);
      bars.appendChild(row);
    }
    gui.appendChild(bars);
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

    sideBox = el('aside', 'en-side');
    work.append(main, sideBox);
    wrap.appendChild(work);

    castBox = el('div', 'en-cast');
    wrap.appendChild(castBox);

    if (!Object.keys(state.placed).length) state.placed = layout('Vanilla 15');
    redraw();
    return wrap;
  }

  function redraw() {
    if (!isoBox) return;
    const T = buildTotals();
    drawStatbar(T);
    isoBox.innerHTML = '';
    isoBox.appendChild(isoStage());
    drawSide(T);
    drawCast(T);
  }

  /* The five readings, across the top of the build where they belong: this is
     what the blocks under them are for, and the whole point of moving a shelf
     is watching one of these move. */
  function drawStatbar(T) {
    statBox.innerHTML = '';
    const pills = [
      ['e', 'Eterna', T.eterna, D.constants.max_eterna,
       Math.round(T.eterna * D.constants.levels_per_eterna) + ' lvl'],
      ['q', 'Quanta', T.quanta, 100, '±' + round1(T.quanta) + '%'],
      ['a', 'Arcana', T.arcana, 100, arcanaTier(T.arcana).name.toLowerCase()],
      ['r', 'Rect', T.rect, 100, T.quanta
        ? Math.round(100 * (1 - (T.quanta / 100) * (1 - T.rect / 100))) + '% floor' : '—'],
      ['c', 'Clues', T.clues, 8, T.clues + ' shown'],
    ];
    for (const [cls, label, value, max, note] of pills) {
      const pill = el('div', 'en-pill ' + cls);
      const top = el('div', 'en-pill-top');
      top.appendChild(el('i', null, label));
      const b = el('b', null, round1(value));
      top.appendChild(b);
      pill.appendChild(top);
      const track = el('div', 'en-meter');
      const fill = el('span', value < 0 ? 'neg' : null);
      fill.style.width = clamp(Math.abs(value) / max * 100, 0, 100) + '%';
      track.appendChild(fill);
      pill.append(track, el('span', 'en-pill-note', note));
      statBox.appendChild(pill);
      motion(b, [{ transform: 'translateY(-4px)', opacity: .4 },
                 { transform: 'none', opacity: 1 }],
        { duration: 260, easing: 'cubic-bezier(.2,.8,.3,1)' });
    }
  }

  /* The side window: what a click puts down, without leaving the build. */
  function drawSide(T) {
    sideBox.innerHTML = '';

    const presets = el('div', 'en-presets');
    for (const label of Object.keys(PRESETS)) {
      const btn = el('button', 'en-preset', label);
      btn.type = 'button';
      btn.addEventListener('click', () => { state.placed = layout(label); redraw(); });
      presets.appendChild(btn);
    }
    const clear = el('button', 'en-preset clear', 'Clear');
    clear.type = 'button';
    clear.addEventListener('click', () => { state.placed = {}; redraw(); });
    presets.appendChild(clear);
    sideBox.appendChild(presets);

    /* Place or remove, as a switch. There is no shift key on a phone, and a
       long-press is a guess nobody can see - so the mode is a control. */
    const modes = el('div', 'en-modes');
    for (const [erase, label] of [[false, 'Place'], [true, 'Remove']]) {
      const btn = el('button', 'en-mode' + (state.erase === erase ? ' on' : ''), label);
      btn.type = 'button';
      btn.addEventListener('click', () => { state.erase = erase; redraw(); });
      modes.appendChild(btn);
    }
    sideBox.appendChild(modes);

    const list = el('div', 'en-brushes');
    for (const block of D.blocks) {
      if (block.is_tag) continue;
      const on = state.brush === block.id && !state.erase;
      const row = el('button', 'en-brush' + (on ? ' on' : ''));
      row.type = 'button';
      const n = Object.values(state.placed).filter(id => id === block.id).length;
      row.appendChild(iconImg(block.id, 'sm'));
      const words = el('span', 'en-brush-words');
      words.appendChild(el('b', null, name(block.id)));
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
      words.appendChild(chips);
      row.appendChild(words);
      if (n) row.appendChild(el('u', null, String(n)));
      row.addEventListener('click', () => {
        state.brush = block.id; state.erase = false; redraw();
      });
      list.appendChild(row);
    }
    sideBox.appendChild(list);
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
    left.appendChild(guiPanel(T));
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
    wrap.classList.remove('on');
    wrap.scrollIntoView({ block: 'nearest' });
  };

  function load() {
    fetch(asset('enchanting.json'))
      .then(r => r.json())
      .then(data => {
        D = data;
        D_MAX_ETERNA = D.constants.max_eterna;
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
