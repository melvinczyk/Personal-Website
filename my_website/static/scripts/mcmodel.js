// Renders a Minecraft player, and whatever they are wearing, with three.js.
//
// This began as CSS 3D boxes, which cannot be made to work: CSS sorts a scene
// by comparing whole faces, so a skin face regularly wins against an armor face
// that is genuinely in front of it and punches through at the silhouette. A
// depth buffer settles it per pixel and the question stops existing, which also
// lets a modded set bring its thousand boxes without the page minding.
//
// Measurements are in skin pixels throughout, in the portal's own axes: +x
// right, +y down, +z toward the viewer. The model root is flipped in y so a
// perfectly ordinary camera sees it the right way up.

import * as THREE from '/static/vendor/three.module.min.js';

// [x, y] origin of each face in the 64x64 skin sheet. The base layer sits where
// Mojang has always put it; the second layer (hat, jacket, sleeves) is the same
// box offset elsewhere on the sheet.
const UV = {
  head:  { top: [8, 0],   bottom: [16, 0],  right: [0, 8],   front: [8, 8],   left: [16, 8], back: [24, 8] },
  head2: { top: [40, 0],  bottom: [48, 0],  right: [32, 8],  front: [40, 8],  left: [48, 8], back: [56, 8] },
  body:  { top: [20, 16], bottom: [28, 16], right: [16, 20], front: [20, 20], left: [28, 20], back: [32, 20] },
  body2: { top: [20, 32], bottom: [28, 32], right: [16, 36], front: [20, 36], left: [28, 36], back: [32, 36] },
  armR:  { top: [44, 16], bottom: [48, 16], right: [40, 20], front: [44, 20], left: [48, 20], back: [52, 20] },
  armR2: { top: [44, 32], bottom: [48, 32], right: [40, 36], front: [44, 36], left: [48, 36], back: [52, 36] },
  armL:  { top: [36, 48], bottom: [40, 48], right: [32, 52], front: [36, 52], left: [40, 52], back: [44, 52] },
  armL2: { top: [52, 48], bottom: [56, 48], right: [48, 52], front: [52, 52], left: [56, 52], back: [60, 52] },
  legR:  { top: [4, 16],  bottom: [8, 16],  right: [0, 20],  front: [4, 20],  left: [8, 20],  back: [12, 20] },
  legR2: { top: [4, 32],  bottom: [8, 32],  right: [0, 36],  front: [4, 36],  left: [8, 36],  back: [12, 36] },
  legL:  { top: [20, 48], bottom: [24, 48], right: [16, 52], front: [20, 52], left: [24, 52], back: [28, 52] },
  legL2: { top: [4, 48],  bottom: [8, 48],  right: [0, 52],  front: [4, 52],  left: [8, 52],  back: [12, 52] },
};

// A flat armor sheet is a second skin: one holds the helmet, chestplate and
// boots, the other the leggings. Each carries a single arm and a single leg,
// drawn on both sides.
const ARMOR_UV = {
  head: { top: [8, 0],   bottom: [16, 0],  right: [0, 8],   front: [8, 8],   left: [16, 8], back: [24, 8] },
  body: { top: [20, 16], bottom: [28, 16], right: [16, 20], front: [20, 20], left: [28, 20], back: [32, 20] },
  arm:  { top: [44, 16], bottom: [48, 16], right: [40, 20], front: [44, 20], left: [48, 20], back: [52, 20] },
  leg:  { top: [4, 16],  bottom: [8, 16],  right: [0, 20],  front: [4, 20],  left: [8, 20],  back: [12, 20] },
};

// How far each piece stands off the body, matching the game: the leggings hug,
// everything else sits proud.
const FIT = { head: 1, chest: 1, legs: 0.5, feet: 1 };

// Minecraft shades a face by the way it points. Without this a model of a
// hundred grey boxes has no shape at all.
const SHADE = { top: 1, front: 0.86, back: 0.86, left: 0.68, right: 0.68, bottom: 0.55 };

// Per face: the corner its texture starts at and the way its two axes run, in
// multiples of half the box.
const FACE_FRAME = {
  front:  { corner: [-1, -1,  1], right: [ 1, 0, 0], down: [0, 1, 0] },
  back:   { corner: [ 1, -1, -1], right: [-1, 0, 0], down: [0, 1, 0] },
  right:  { corner: [-1, -1, -1], right: [ 0, 0, 1], down: [0, 1, 0] },
  left:   { corner: [ 1, -1,  1], right: [ 0, 0,-1], down: [0, 1, 0] },
  top:    { corner: [-1, -1, -1], right: [ 1, 0, 0], down: [0, 0, 1] },
  bottom: { corner: [-1,  1,  1], right: [ 1, 0, 0], down: [0, 0,-1] },
};

const FACES = ['front', 'back', 'left', 'right', 'top', 'bottom'];

function faceSize(name, w, h, d) {
  if (name === 'top' || name === 'bottom') return [w, d];
  if (name === 'left' || name === 'right') return [d, h];
  return [w, h];
}

// Where each limb hangs, and where a converted model expects to attach.
function joints(armW) {
  return {
    head: [0, -12, 0],
    body: [0, -2, 0],
    armR: [-(4 + armW / 2), -2, 0],
    armL: [(4 + armW / 2), -2, 0],
    legR: [-2, 10, 0],
    legL: [2, 10, 0],
  };
}

// ---------------------------------------------------------------------------
// Geometry: every box of a limb goes into one buffer, so a set of two hundred
// cubes still costs a single draw.
// ---------------------------------------------------------------------------

class Batch {
  constructor(tw, th) {
    this.tw = tw;
    this.th = th;
    this.position = [];
    this.uv = [];
    this.color = [];
  }

  /** rect is [u, v, width, height, flip] in sheet pixels; turn is optional. */
  face(name, centre, size, rect, turn) {
    const frame = FACE_FRAME[name];
    const half = size.map(v => v / 2);
    const [fw, fh] = faceSize(name, size[0], size[1], size[2]);

    const origin = [0, 1, 2].map(i => centre[i] + frame.corner[i] * half[i]);
    const across = frame.right.map(v => v * fw);
    const down   = frame.down.map(v => v * fh);
    const at = (a, b) => {
      const point = [0, 1, 2].map(i => origin[i] + across[i] * a + down[i] * b);
      return turn ? turn(point) : point;
    };

    const [ux, uy, uw, uh, flip = ''] = rect;
    let u0 = ux / this.tw, u1 = (ux + uw) / this.tw;
    let v0 = 1 - uy / this.th, v1 = 1 - (uy + uh) / this.th;
    if (flip.includes('x')) [u0, u1] = [u1, u0];
    if (flip.includes('y')) [v0, v1] = [v1, v0];

    const corners = [at(0, 0), at(1, 0), at(1, 1), at(0, 1)];
    const uvs = [[u0, v0], [u1, v0], [u1, v1], [u0, v1]];
    const tint = SHADE[name];

    for (const [a, b, c] of [[0, 1, 2], [0, 2, 3]]) {
      for (const index of [a, b, c]) {
        this.position.push(...corners[index]);
        this.uv.push(...uvs[index]);
        this.color.push(tint, tint, tint);
      }
    }
  }

  /** A box whose uv table names one origin per face, sized from the box. */
  box(centre, size, uv, opts = {}) {
    const grow = opts.grow || 0;
    const drawn = size.map(v => v + 2 * grow);
    for (const name of FACES) {
      const key = opts.mirror && (name === 'left' || name === 'right')
        ? (name === 'left' ? 'right' : 'left') : name;
      if (!uv[key]) continue;
      const [uw, uh] = faceSize(name, size[0], size[1], size[2]);
      this.face(name, centre, drawn, [uv[key][0], uv[key][1], uw, uh]);
    }
  }

  get empty() { return this.position.length === 0; }

  mesh(map, opts = {}) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(this.position, 3));
    geometry.setAttribute('uv', new THREE.Float32BufferAttribute(this.uv, 2));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(this.color, 3));
    // alphaTest leaves every pixel either drawn or not drawn, so armor writes
    // depth like anything else and nothing anywhere has to be sorted
    // a blacked-out model still needs its texture: the alpha is what gives a
    // silhouette its shape, and multiplying by black leaves only that
    // and a see-through shell is the one thing that cannot be drawn that way:
    // it blends instead, writes no depth, and goes on last so whatever it is
    // sheltering is already there to show through it
    const material = new THREE.MeshBasicMaterial({
      map,
      color: opts.locked ? 0x000000 : 0xffffff,
      vertexColors: !opts.locked,
      side: THREE.DoubleSide,
      ...(opts.veil
        ? { transparent: true, depthWrite: false }
        : { alphaTest: 0.5 }),
    });
    const mesh = new THREE.Mesh(geometry, material);
    if (opts.veil) mesh.renderOrder = 1;
    return mesh;
  }
}

/** The turn a converted cube carries, about its own pivot.
 *  Composed z, then y, then x, unless the model asks for the reverse. */
function turner(cube) {
  const [rx, ry, rz] = cube.r.map(d => d * Math.PI / 180);
  const X = new THREE.Matrix4().makeRotationX(rx);
  const Y = new THREE.Matrix4().makeRotationY(ry);
  const Z = new THREE.Matrix4().makeRotationZ(rz);
  const matrix = cube.o === 'xyz'
    ? X.clone().multiply(Y).multiply(Z)
    : Z.clone().multiply(Y).multiply(X);
  const pivot = new THREE.Vector3(...cube.p);
  const point = new THREE.Vector3();
  return ([x, y, z]) => {
    point.set(x, y, z).sub(pivot).applyMatrix4(matrix).add(pivot);
    return [point.x, point.y, point.z];
  };
}

const _textures = new Map();

function texture(url) {
  if (!_textures.has(url)) {
    const map = new THREE.TextureLoader().load(url, paintAll);
    map.magFilter = THREE.NearestFilter;
    map.minFilter = THREE.NearestFilter;
    map.colorSpace = THREE.SRGBColorSpace;
    _textures.set(url, map);
  }
  return _textures.get(url);
}

const _models = new Map();

function loadModel(url) {
  if (!_models.has(url)) _models.set(url, fetch(url).then(r => r.json()));
  return _models.get(url);
}

// ---------------------------------------------------------------------------
// One renderer, copied out to a small canvas per card. Cards come and go as the
// rail moves, and webgl contexts are far too costly to churn.
// ---------------------------------------------------------------------------

const WIDTH = 99, HEIGHT = 171, UNIT = 4.5, DISTANCE = 138;
// how far a worn skin sits inside the one over it, in skin pixels
const INSET = 0.2;

let renderer = null;
const views = new Set();

function ensureRenderer() {
  if (!renderer) {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearAlpha(0);
  }
  return renderer;
}

function paint(view) {
  const gl = ensureRenderer();
  gl.setSize(view.w, view.h, false);
  gl.render(view.scene, view.camera);
  view.ctx.clearRect(0, 0, view.canvas.width, view.canvas.height);
  view.ctx.drawImage(gl.domElement, 0, 0,
                     Math.round(view.w * gl.getPixelRatio()),
                     Math.round(view.h * gl.getPixelRatio()),
                     0, 0, view.canvas.width, view.canvas.height);
}

/** A canvas of the right size for a view, already in the element. */
function canvasFor(el, w, h) {
  const canvas = document.createElement('canvas');
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(w * ratio);
  canvas.height = Math.round(h * ratio);
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  el.innerHTML = '';
  el.appendChild(canvas);
  return canvas;
}

/** A camera framing `h / UNIT` pixels of model from DISTANCE away. */
function eye(w, h, unit) {
  const camera = new THREE.PerspectiveCamera(
    2 * Math.atan((h / unit / 2) / DISTANCE) * 180 / Math.PI, w / h, 1, 900);
  camera.position.set(0, 0, DISTANCE);
  return camera;
}

function paintAll() {
  for (const view of views) paint(view);
}

let frame = null;

function animate(now) {
  const turning = [...views].filter(v => v.turning);
  if (!turning.length) { frame = null; return; }
  frame = requestAnimationFrame(animate);

  const t = now / 1000;
  for (const view of turning) {
    view.root.rotation.y = (t / 18) * Math.PI * 2 - 0.35;
    if (!view.limbs || !view.limbs.armR) { paint(view); continue; }
    const swing = Math.sin(t * Math.PI * 2 / 3.4) * 0.17;
    view.limbs.armR.rotation.x = swing;
    view.limbs.legL.rotation.x = swing;
    view.limbs.armL.rotation.x = -swing;
    view.limbs.legR.rotation.x = -swing;
    paint(view);
  }
}

function startTurning() {
  if (frame === null) frame = requestAnimationFrame(animate);
}

/**
 * Render a player into `el`.
 * opts: { skin, slim, worn } - worn holds, per body part, either a flat armor
 * sheet or a model converted from the mod's own.
 */
function buildPlayerModel(el, opts) {
  if (!opts.skin) return;
  disposeModel(el);

  const armW = opts.slim ? 3 : 4;
  const flat = {}, built = {};
  for (const [part, piece] of Object.entries(opts.worn || {})) {
    (piece.model ? built : flat)[part] = piece;
  }

  const w = opts.width || WIDTH;
  const h = opts.height || HEIGHT;
  const canvas = canvasFor(el, w, h);
  const world = new THREE.Scene();
  const camera = eye(w, h, UNIT * (h / HEIGHT));

  const root = new THREE.Group();
  root.scale.y = -1;             // the portal measures y downward, the camera up
  world.add(root);

  const limbs = {};
  for (const [part, at] of Object.entries(joints(armW))) {
    const group = new THREE.Group();
    group.position.set(at[0], at[1], at[2]);
    root.add(group);
    limbs[part] = group;
  }
  // arms and legs turn about the shoulder and hip, six pixels above the middle
  for (const part of ['armR', 'armL', 'legR', 'legL']) {
    limbs[part].position.y -= 6;
    const hang = new THREE.Group();
    hang.position.y = 6;
    limbs[part].add(hang);
    limbs[part].hang = hang;
  }

  const skinMap = texture(opts.skin);
  const wearing = {
    head: limbs.head, body: limbs.body,
    armR: limbs.armR.hang, armL: limbs.armL.hang,
    legR: limbs.legR.hang, legL: limbs.legL.hang,
  };

  // size, base layer, second layer, and how far the second layer stands off
  const BODY = {
    head: [[8, 8, 8],     UV.head, UV.head2, 0.35],
    body: [[8, 12, 4],    UV.body, UV.body2, 0.25],
    armR: [[armW, 12, 4], UV.armR, UV.armR2, 0.25],
    armL: [[armW, 12, 4], UV.armL, UV.armL2, 0.25],
    legR: [[4, 12, 4],    UV.legR, UV.legR2, 0.25],
    legL: [[4, 12, 4],    UV.legL, UV.legL2, 0.25],
  };
  for (const [part, group] of Object.entries(wearing)) {
    const [size, base, over, grow] = BODY[part];
    const batch = new Batch(64, 64);
    batch.box([0, 0, 0], size, base);
    batch.box([0, 0, 0], size, over, { grow });
    group.add(batch.mesh(skinMap));
  }

  // flat armor is the body's own boxes again, padded out and wearing the sheet
  const COVERS = {
    head: [['head', ARMOR_UV.head, [8, 8, 8]]],
    chest: [['body', ARMOR_UV.body, [8, 12, 4]], ['armR', ARMOR_UV.arm, [4, 12, 4]],
            ['armL', ARMOR_UV.arm, [4, 12, 4]]],
    legs: [['body', ARMOR_UV.body, [8, 12, 4]], ['legR', ARMOR_UV.leg, [4, 12, 4]],
           ['legL', ARMOR_UV.leg, [4, 12, 4]]],
    feet: [['legR', ARMOR_UV.leg, [4, 12, 4]], ['legL', ARMOR_UV.leg, [4, 12, 4]]],
  };
  for (const [slot, piece] of Object.entries(flat)) {
    const map = texture(piece.url);
    for (const [part, uv, size] of COVERS[slot]) {
      const batch = new Batch(64, piece.th * 64 / piece.tw);
      batch.box([0, 0, 0], size, uv, { grow: FIT[slot], mirror: part.endsWith('L') });
      wearing[part].add(batch.mesh(map));
    }
  }

  const view = { el, canvas, ctx: canvas.getContext('2d'), scene: world, camera,
                 root, limbs, wearing, built, armW, w, h,
                 turning: false, dressed: false, worn: [] };
  el._view = view;
  views.add(view);
  root.rotation.y = -0.35;
  paint(view);
}

// A modded set can be a thousand boxes, so only the card in the middle of the
// rail is ever wearing one.
function dressModel(el) {
  const view = el && el._view;
  if (!view) return;
  view.turning = true;
  startTurning();
  if (view.dressed) return;
  view.dressed = true;

  for (const piece of Object.values(view.built)) {
    loadModel(piece.model).then(model => {
      if (!view.dressed) return;               // the rail moved on meanwhile
      const map = texture(piece.model.replace(/[^/]+$/, model.texture));
      const shift = 6 - (4 + view.armW / 2);

      for (const [part, cubes] of Object.entries(model.slots[piece.slot] || {})) {
        const group = view.wearing[part];
        if (!group) continue;
        const dx = part === 'armR' ? -shift : part === 'armL' ? shift : 0;

        // every cube of the limb, turned ones included, bakes into one buffer
        const batch = new Batch(model.tw, model.th);
        for (const cube of cubes) {
          const centre = [cube.c[0] + dx, cube.c[1], cube.c[2]];
          const turn = cube.r ? turner({ ...cube, p: [cube.p[0] + dx, cube.p[1], cube.p[2]] }) : null;
          for (const [name, rect] of Object.entries(cube.f)) {
            batch.face(name, centre, cube.s, rect, turn);
          }
        }
        if (batch.empty) continue;
        const mesh = batch.mesh(map);
        group.add(mesh);
        view.worn.push(mesh);
      }
      paint(view);
    }).catch(() => {});
  }
}

function undressModel(el) {
  const view = el && el._view;
  if (!view) return;
  view.turning = false;
  if (!view.dressed) return;
  view.dressed = false;
  for (const mesh of view.worn) {
    mesh.parent.remove(mesh);
    mesh.geometry.dispose();
    mesh.material.dispose();
  }
  view.worn = [];
  paint(view);
}

function disposeModel(el) {
  const view = el && el._view;
  if (!view) return;
  views.delete(view);
  view.scene.traverse(node => {
    if (node.geometry) node.geometry.dispose();
    if (node.material) node.material.dispose();
  });
  el._view = null;
}


/**
 * Render a mob into `el` from a model read out of the game's own client.
 *
 * opts: { model, locked, width, height }. A locked mob is drawn in black:
 * the shape is there, kept honest by the texture's own transparency, but
 * nothing of what it looks like is given away until somebody has felled it.
 */
function buildMobModel(el, opts) {
  loadModel(opts.model).then(model => {
    disposeModel(el);

    const w = opts.width || 150, h = opts.height || 190;
    const canvas = canvasFor(el, w, h);
    const world = new THREE.Scene();
    const camera = eye(w, h, UNIT * (h / HEIGHT));

    const root = new THREE.Group();
    root.scale.y = -1;              // the portal measures y downward
    world.add(root);
    const fit = new THREE.Group();  // carries the framing
    root.add(fit);
    const shell = new THREE.Group();
    fit.add(shell);

    const map = texture(opts.model.replace(/[^/]+$/, model.texture));
    // Some mobs are worn: a suit of armour with a ghost inside it, drawn by the
    // game as the same bones a second time in a second skin. Holding the ghost
    // a fraction inside the armour keeps the two off each other's faces and
    // lets it show through wherever the outer skin is see-through.
    const under = model.ghost
      ? texture(opts.model.replace(/[^/]+$/, model.ghost)) : null;
    // and armour is the same trick the other way about: the game hangs it off
    // the mob's own bones a shade wider, so it sits over the skin
    const over = model.coat
      ? texture(opts.model.replace(/[^/]+$/, model.coat)) : null;
    // A bone may wear a skin of its own: a serpent's body segments come from
    // a second model with a second sheet, and the two are drawn as one mob.
    const skins = (model.skins || []).map(skin => ({
      map: texture(opts.model.replace(/[^/]+$/, skin.texture)),
      tw: skin.tw, th: skin.th, veil: !!skin.veil,
    }));
    const bones = {};

    for (const bone of model.bones) {
      const group = new THREE.Group();
      group.position.set(...bone.pivot);
      // Minecraft turns a part about z, then y, then x. Three's default is the
      // other way round, which quietly scrambles any bone rotated on two axes.
      if (bone.rot && bone.rot.some(Boolean)) group.rotation.set(...bone.rot, 'ZYX');
      (bones[bone.parent] || shell).add(group);
      bones[bone.name] = group;

      const skin = skins[bone.skin || 0];
      const batch = new Batch(skin ? skin.tw : model.tw, skin ? skin.th : model.th);
      const inner = under ? new Batch(model.tw, model.th) : null;
      const outer = over ? new Batch(model.tw, model.th) : null;
      for (const cube of bone.cubes) {
        // a cube of its own may be turned about a point inside the bone
        const turn = cube.r ? turner(cube) : null;
        const worn = inner ? cube.s.map(v => Math.max(v - INSET, 0.01)) : null;
        const armed = outer ? cube.s.map(v => v + INSET) : null;
        for (const [name, rect] of Object.entries(cube.f)) {
          batch.face(name, cube.c, cube.s, rect, turn);
          if (inner) inner.face(name, cube.c, worn, rect, turn);
          if (outer) outer.face(name, cube.c, armed, rect, turn);
        }
      }
      if (inner && !inner.empty) group.add(inner.mesh(under, { locked: opts.locked }));
      if (!batch.empty) {
        group.add(batch.mesh(skin ? skin.map : map,
                             { locked: opts.locked, veil: skin && skin.veil }));
      }
      if (outer && !outer.empty) group.add(outer.mesh(over, { locked: opts.locked }));
    }

    // Mobs are all sizes and all shapes: a wither is wider than it is tall, a
    // warden three times a player, and the Luxtructosaurus four hundred pixels
    // of neck and tail. Something that long reads as a heap of slabs seen
    // head-on, so turn it side-on first and frame what is then in front. A mob
    // that the side-on turn does not suit carries a turn of its own instead,
    // and that one is taken as its chosen pose.
    if (model.pose) shell.rotation.set(...model.pose.map(d => d * Math.PI / 180), 'ZYX');
    let box = new THREE.Box3().setFromObject(shell);
    let size = box.getSize(new THREE.Vector3());
    if (!model.pose && size.z > size.x * 1.4) {
      shell.rotation.y = Math.PI / 2;
      box = new THREE.Box3().setFromObject(shell);
      size = box.getSize(new THREE.Vector3());
    }
    const visible = HEIGHT / UNIT;
    const scale = Math.min(
      visible * 0.92 / (size.y || 1),
      visible * (w / h) * 0.92 / (size.x || 1),
      // and never so close that the near half of it is behind the camera
      DISTANCE * 0.55 / ((size.z / 2) || 1)) * (model.zoom || 1);

    // Something far longer than a card can hold reads as a rope at any size the
    // whole of it will fit in. Those name a bone to put in the middle instead,
    // and lean on the zoom to bring it in close: a portrait, not a map. Only
    // along an axis that overruns, though: a serpent wants its head centred
    // across the card, and still wants to sit level down it.
    const middle = box.getCenter(new THREE.Vector3());
    if (model.focus && bones[model.focus]) {
      const at = new THREE.Vector3();
      bones[model.focus].updateWorldMatrix(true, false);
      bones[model.focus].getWorldPosition(at);
      // the box is measured in the frame's own axes, before the root turns the
      // model the right way up, so the bone has to be read back into them
      fit.worldToLocal(at);
      // depth has no such limit: the part being framed belongs at the camera's
      // own distance whatever the rest of the mob is doing behind it
      const room = [visible * (w / h), visible, 0];
      ['x', 'y', 'z'].forEach((axis, i) => {
        if (size[axis] * scale > room[i]) middle[axis] = at[axis];
      });
    }
    fit.scale.setScalar(scale);
    fit.position.set(-middle.x * scale, -middle.y * scale, -middle.z * scale);

    const view = { el, canvas, ctx: canvas.getContext('2d'), scene: world,
                   camera, root, w, h, turning: false, worn: [] };
    el._view = view;
    views.add(view);
    root.rotation.y = -0.35;
    paint(view);
  }).catch(() => {});
}

/** Start or stop a mob turning on the spot. */
function turnModel(el, on) {
  const view = el && el._view;
  if (!view) return;
  view.turning = on !== false;
  if (view.turning) startTurning(); else paint(view);
}

window.buildPlayerModel = buildPlayerModel;
window.buildMobModel = buildMobModel;
window.turnModel = turnModel;
window.dressModel = dressModel;
window.undressModel = undressModel;
window.disposeModel = disposeModel;
window.dispatchEvent(new Event('mcmodel-ready'));
