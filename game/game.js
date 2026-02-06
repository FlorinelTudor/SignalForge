const canvas = document.getElementById("game-canvas");
const ctx = canvas.getContext("2d");

const overlay = document.getElementById("overlay");
const overlayTitle = document.getElementById("overlay-title");
const overlaySubtitle = document.getElementById("overlay-subtitle");
const overlayHint = document.getElementById("overlay-hint");
const startBtn = document.getElementById("start-btn");
const statusChip = document.getElementById("status-chip");

const ASSET_ROOT = "assets/larzes/NoLight/Medium";
function loadSprite(file) {
  const img = new Image();
  img.src = `${ASSET_ROOT}/${file}`;
  return img;
}

const SPRITES = {
  player: loadSprite("Ship_2_A_Medium_NoLight.png"),
  chaser: loadSprite("Enemy_1_A_Medium_NoLight.png"),
  skirmisher: loadSprite("Enemy_2_A_Medium_NoLight.png"),
  charger: loadSprite("Enemy_3_A_Medium_NoLight.png"),
  sapper: loadSprite("Enemy_4_A_Medium_NoLight.png"),
  splitter: loadSprite("Enemy_1_A_Medium_NoLight.png"),
  splitlet: loadSprite("Enemy_1_A_Medium_NoLight.png"),
  bullet: loadSprite("Missile_A_Medium_NoLight.png"),
  pod: loadSprite("Pickup_1_A_Medium_NoLight.png"),
  core: loadSprite("Pickup_2_A_Medium_NoLight.png"),
  mod: loadSprite("Pickup_3_B_Medium_NoLight.png"),
  boss: loadSprite("Boss_1_B_Medium_NoLight.png"),
  gate: loadSprite("Pickup_3_A_Medium_NoLight.png"),
};

const world = { width: 900, height: 600 };
const keysDown = new Set();

const state = {
  mode: "menu",
  time: 0,
  score: 0,
  collected: 0,
  goal: 8,
  gems: [],
  enemies: [],
  bullets: [],
  particles: [],
  pods: [],
  mods: [],
  slowFields: [],
  riskZones: [],
  stars: [],
  enemySpawnTimer: 0,
  gemTarget: 4,
  shootCooldown: 0,
  shieldCooldown: 0,
  dashCooldown: 0,
  dashTime: 0,
  dashDir: { x: 0, y: -1 },
  chainCount: 0,
  chainTimer: 0,
  chainWindow: 4,
  chainWindowBase: 4,
  heat: 0,
  heatMax: 100,
  overheated: false,
  speedBoost: 0,
  podTimer: 4,
  modTimer: 7,
  ammoMode: "spread",
  ammoTimer: 0,
  riskTimer: 12,
  riskTick: 0,
  wave: 1,
  wavePause: 0,
  shopOptions: [],
  upgrades: {
    speed: 0,
    shield: 0,
    chain: 0,
  },
  objective: null,
  objectiveCooldown: 0,
  drone: {
    x: world.width / 2,
    y: world.height / 2,
    angle: 0,
    cooldown: 0,
    fireRate: 0.7,
    level: 1,
  },
  flash: { time: 0, color: "rgba(255, 110, 110, 0.35)" },
  audioReady: false,
  gateActive: false,
  gate: null,
  shake: { time: 0, strength: 0 },
  lastTimestamp: 0,
  renderScale: 1,
  pixelRatio: 1,
  mouse: {
    x: world.width / 2,
    y: world.height / 2,
    active: false,
    inside: false,
  },
  player: {
    x: world.width / 2,
    y: world.height / 2,
    vx: 0,
    vy: 0,
    r: 14,
    speed: 260,
    accel: 1100,
    drag: 6,
    maxHealth: 3,
    health: 3,
    invuln: 0,
    facing: { x: 0, y: -1 },
  },
};

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function distance(a, b) {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return Math.hypot(dx, dy);
}

function initAudio() {
  if (state.audioReady) return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    state.audioCtx = new AudioCtx();
    state.audioReady = true;
  } catch (err) {
    state.audioReady = false;
  }
}

function playTone(freq, duration, type = "sine", volume = 0.08) {
  if (!state.audioReady || !state.audioCtx) return;
  const ctx = state.audioCtx;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  gain.gain.value = volume;
  osc.connect(gain).connect(ctx.destination);
  osc.start();
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);
  osc.stop(ctx.currentTime + duration);
}

function addFlash(color, time) {
  state.flash.color = color;
  state.flash.time = Math.max(state.flash.time, time);
}

function getShieldCooldownBase() {
  return Math.max(3.0, 5.5 - state.upgrades.shield * 0.6);
}

function getChainWindow() {
  return state.chainWindowBase + state.upgrades.chain * 0.8;
}

function getPlayerSpeedBase() {
  return 260 + state.upgrades.speed * 18;
}

function randomPoint(r, avoid) {
  for (let i = 0; i < 40; i++) {
    const x = r + Math.random() * (world.width - r * 2);
    const y = r + Math.random() * (world.height - r * 2);
    if (avoid && distance({ x, y }, avoid) < avoid.r + r + 60) continue;
    return { x, y };
  }
  return { x: world.width / 2, y: world.height / 2 };
}

function spawnStarfield() {
  state.stars = Array.from({ length: 120 }, () => {
    return {
      x: Math.random() * world.width,
      y: Math.random() * world.height,
      r: Math.random() * 1.6 + 0.4,
      tw: Math.random() * Math.PI * 2,
    };
  });
}

function drawSprite(img, x, y, size, rotation = 0, alpha = 1) {
  if (!img || !img.naturalWidth) return false;
  const scale = size / Math.max(img.naturalWidth, img.naturalHeight);
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rotation);
  ctx.globalAlpha = alpha;
  ctx.drawImage(
    img,
    (-img.naturalWidth * scale) / 2,
    (-img.naturalHeight * scale) / 2,
    img.naturalWidth * scale,
    img.naturalHeight * scale
  );
  ctx.restore();
  return true;
}

function spawnGem() {
  const spot = randomPoint(10, state.player);
  state.gems.push({ x: spot.x, y: spot.y, r: 10, spin: Math.random() * Math.PI * 2 });
}

function spawnFuelPod() {
  const spot = randomPoint(12, state.player);
  state.pods.push({ x: spot.x, y: spot.y, r: 12, life: 10 });
}

function spawnModPickup() {
  const spot = randomPoint(12, state.player);
  const types = ["five", "pierce", "homing", "ricochet"];
  const type = types[Math.floor(Math.random() * types.length)];
  state.mods.push({ x: spot.x, y: spot.y, r: 12, life: 12, type });
}

function spawnSlowField(x, y) {
  state.slowFields.push({ x, y, r: 80, life: 4 });
}

function spawnRiskZone() {
  const spot = randomPoint(120, state.player);
  state.riskZones.push({ x: spot.x, y: spot.y, r: 120, life: 18 });
}

function spawnGate() {
  const spot = randomPoint(48, state.player);
  state.gate = { x: spot.x, y: spot.y, r: 48, pulse: Math.random() * Math.PI * 2 };
  state.gateActive = true;
}

function createEnemy(type) {
  const spot = randomPoint(18, state.player);
  const heading = Math.random() * Math.PI * 2;
  const enemy = {
    x: spot.x,
    y: spot.y,
    r: 16,
    vx: Math.cos(heading) * 40,
    vy: Math.sin(heading) * 40,
    speed: 95 + Math.random() * 20,
    hp: 2,
    maxHp: 2,
    type,
    mode: "normal",
    orbitDir: Math.random() < 0.5 ? -1 : 1,
    orbitRadius: 150 + Math.random() * 40,
    chargeCooldown: 1.6 + Math.random() * 1.2,
    windup: 0,
    dashTime: 0,
    dashSpeed: 360,
    dropCooldown: 2.4 + Math.random() * 1.6,
    splitOnDeath: false,
    stun: 0,
    shootCooldown: 1.2 + Math.random() * 0.6,
  };

  if (type === "skirmisher") {
    enemy.r = 14;
    enemy.speed = 85 + Math.random() * 18;
    enemy.hp = 1;
    enemy.maxHp = 1;
  } else if (type === "charger") {
    enemy.r = 18;
    enemy.speed = 80 + Math.random() * 14;
    enemy.hp = 3;
    enemy.maxHp = 3;
    enemy.dashSpeed = 380;
  } else if (type === "sapper") {
    enemy.r = 15;
    enemy.speed = 70 + Math.random() * 12;
    enemy.hp = 2;
    enemy.maxHp = 2;
    enemy.orbitRadius = 200 + Math.random() * 30;
    enemy.dropCooldown = 2.5 + Math.random() * 1.8;
  } else if (type === "splitter") {
    enemy.r = 17;
    enemy.speed = 92 + Math.random() * 16;
    enemy.hp = 2;
    enemy.maxHp = 2;
    enemy.splitOnDeath = true;
  } else if (type === "splitlet") {
    enemy.r = 10;
    enemy.speed = 120 + Math.random() * 20;
    enemy.hp = 1;
    enemy.maxHp = 1;
  } else if (type === "boss") {
    enemy.r = 40;
    enemy.speed = 60;
    enemy.hp = 16;
    enemy.maxHp = 16;
    enemy.dashSpeed = 220;
    enemy.dropCooldown = 3.5;
    enemy.mode = "boss";
  } else {
    enemy.maxHp = enemy.hp;
  }

  return enemy;
}

function spawnEnemy() {
  const roll = Math.random();
  const type =
    roll < 0.4
      ? "chaser"
      : roll < 0.62
        ? "skirmisher"
        : roll < 0.8
          ? "charger"
          : roll < 0.92
            ? "sapper"
            : "splitter";
  state.enemies.push(createEnemy(type));
}

function spawnWave() {
  const isBossWave = state.wave % 4 === 0;
  if (isBossWave) {
    state.enemies.push(createEnemy("boss"));
    state.enemies.push(createEnemy("skirmisher"));
    state.enemies.push(createEnemy("chaser"));
  } else {
    const count = Math.min(7, 2 + state.wave);
    for (let i = 0; i < count; i++) spawnEnemy();
  }
}

function resetGame() {
  state.time = 0;
  state.score = 0;
  state.collected = 0;
  state.gems = [];
  state.enemies = [];
  state.bullets = [];
  state.particles = [];
  state.pods = [];
  state.mods = [];
  state.slowFields = [];
  state.riskZones = [];
  state.enemySpawnTimer = 0.5;
  state.shootCooldown = 0;
  state.shieldCooldown = 0;
  state.dashCooldown = 0;
  state.dashTime = 0;
  state.dashDir = { x: 0, y: -1 };
  state.chainCount = 0;
  state.chainTimer = 0;
  state.chainWindowBase = 4;
  state.chainWindow = getChainWindow();
  state.heat = 0;
  state.overheated = false;
  state.speedBoost = 0;
  state.podTimer = 4;
  state.modTimer = 7;
  state.ammoMode = "spread";
  state.ammoTimer = 0;
  state.riskTimer = 12;
  state.riskTick = 0;
  state.wave = 1;
  state.wavePause = 0;
  state.objective = null;
  state.objectiveCooldown = 2;
  state.upgrades = { speed: 0, shield: 0, chain: 0 };
  state.drone.angle = 0;
  state.drone.cooldown = 0;
  state.drone.level = 1;
  state.gateActive = false;
  state.gate = null;
  state.shake = { time: 0, strength: 0 };
  state.player.x = world.width / 2;
  state.player.y = world.height / 2;
  state.player.vx = 0;
  state.player.vy = 0;
  state.player.health = state.player.maxHealth;
  state.player.invuln = 0;
  state.player.facing = { x: 0, y: -1 };
  state.player.speed = getPlayerSpeedBase();
  while (state.gems.length < state.gemTarget) spawnGem();
  spawnWave();
  spawnStarfield();
}

function buildShopOptions() {
  return [
    {
      key: "A",
      id: "speed",
      label: "Thrusters",
      desc: "Move speed +18",
      cost: 300 + state.upgrades.speed * 180,
      max: 3,
    },
    {
      key: "B",
      id: "shield",
      label: "Shield Grid",
      desc: "Shield cooldown -0.6s",
      cost: 320 + state.upgrades.shield * 200,
      max: 4,
    },
    {
      key: "Space",
      id: "chain",
      label: "Chain Buffer",
      desc: "Chain window +0.8s",
      cost: 260 + state.upgrades.chain * 170,
      max: 4,
    },
  ];
}

function openShop() {
  state.shopOptions = buildShopOptions();
  setMode("shop");
}

function closeShop() {
  setMode("playing");
}

function purchaseUpgrade(id) {
  const option = state.shopOptions.find((item) => item.id === id);
  if (!option) return;
  if (state.upgrades[id] >= option.max) return;
  if (state.score < option.cost) return;
  state.score -= option.cost;
  state.upgrades[id] += 1;

  if (id === "speed") {
    state.player.speed = getPlayerSpeedBase();
  } else if (id === "chain") {
    state.chainWindowBase = 4 + state.upgrades.chain * 0.8;
  }
  state.chainWindow = getChainWindow();
  playTone(520, 0.08, "triangle", 0.07);
  addFlash("rgba(119, 224, 255, 0.25)", 0.2);
  state.shopOptions = buildShopOptions();
}

function setOverlay(mode) {
  overlay.classList.toggle("visible", mode !== "playing");
  if (mode === "menu") {
    overlayTitle.textContent = "Star Courier";
    overlaySubtitle.textContent =
      "Slip through the drone field, scoop the cores, and signal the jump gate.";
    overlayHint.textContent = "Press Enter to launch";
    startBtn.textContent = "Start Run";
    statusChip.textContent = "Offline";
  } else if (mode === "paused") {
    overlayTitle.textContent = "Paused";
    overlaySubtitle.textContent = "Your courier is holding position.";
    overlayHint.textContent = "Press P to resume";
    startBtn.textContent = "Resume";
    statusChip.textContent = "Holding";
  } else if (mode === "shop") {
    overlayTitle.textContent = "Salvage Shop";
    overlaySubtitle.innerHTML = state.shopOptions
      .map((opt) => {
        const maxed = state.upgrades[opt.id] >= opt.max;
        const costLabel = maxed ? "MAX" : `${opt.cost} pts`;
        return `<strong>${opt.key}</strong> ${opt.label} — ${opt.desc} (${costLabel})`;
      })
      .join("<br>");
    overlayHint.textContent = "Press Enter to exit";
    startBtn.textContent = "Resume Run";
    statusChip.textContent = "Docked";
  } else if (mode === "gameover") {
    overlayTitle.textContent = "Ship disabled";
    overlaySubtitle.textContent = "The drones locked on. Reset the run.";
    overlayHint.textContent = "Press R to restart";
    startBtn.textContent = "Restart Run";
    statusChip.textContent = "Critical";
  } else if (mode === "win") {
    overlayTitle.textContent = "Jump gate charged";
    overlaySubtitle.textContent = "All cores secured. You made the jump.";
    overlayHint.textContent = "Press R to play again";
    startBtn.textContent = "Run It Back";
    statusChip.textContent = "Cleared";
  } else if (mode === "playing") {
    statusChip.textContent = "Live";
  }
}

function setMode(mode) {
  state.mode = mode;
  setOverlay(mode);
}

function startGame() {
  resetGame();
  setMode("playing");
}

function pauseGame() {
  if (state.mode !== "playing") return;
  setMode("paused");
}

function resumeGame() {
  if (state.mode !== "paused") return;
  setMode("playing");
}

function endGame(win) {
  setMode(win ? "win" : "gameover");
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen?.();
  } else {
    document.exitFullscreen?.();
  }
}

function handlePrimaryAction() {
  if (state.mode === "menu" || state.mode === "gameover" || state.mode === "win") {
    startGame();
  } else if (state.mode === "paused") {
    resumeGame();
  } else if (state.mode === "shop") {
    closeShop();
  }
}

startBtn.addEventListener("click", handlePrimaryAction);
document.addEventListener("pointerdown", initAudio, { once: true });
document.addEventListener("keydown", initAudio, { once: true });

function triggerDash() {
  if (state.mode !== "playing") return;
  if (state.dashCooldown > 0 || state.dashTime > 0) return;
  const move = getMovementVector();
  const dir = move.len ? { x: move.x, y: move.y } : { ...state.player.facing };
  if (!dir.x && !dir.y) dir.y = -1;
  state.dashDir = dir;
  state.dashTime = 0.12;
  state.dashCooldown = 1.6;
  state.player.invuln = Math.max(state.player.invuln, 0.25);
  addShake(4, 0.15);
  playTone(680, 0.08, "sawtooth", 0.05);
  spawnParticles({
    x: state.player.x,
    y: state.player.y,
    color: "rgba(119, 224, 255, 0.9)",
    count: 14,
    speed: 200,
    life: 0.35,
  });
}

function triggerShield() {
  if (state.mode !== "playing") return;
  if (state.shieldCooldown > 0) return;
  state.shieldCooldown = getShieldCooldownBase();
  addShake(8, 0.2);
  playTone(420, 0.12, "triangle", 0.06);
  spawnParticles({
    x: state.player.x,
    y: state.player.y,
    color: "rgba(119, 224, 255, 0.9)",
    count: 26,
    speed: 220,
    life: 0.5,
  });

  for (const enemy of state.enemies) {
    const dx = enemy.x - state.player.x;
    const dy = enemy.y - state.player.y;
    const dist = Math.hypot(dx, dy);
    if (dist < 120) {
      const nx = dx / Math.max(1, dist);
      const ny = dy / Math.max(1, dist);
      enemy.vx += nx * 260;
      enemy.vy += ny * 260;
      enemy.stun = Math.max(enemy.stun, 0.5);
      if (enemy.hp > 1) enemy.hp -= 1;
    }
  }
}

window.addEventListener("keydown", (event) => {
  if (event.repeat) return;
  keysDown.add(event.code);

  if (state.mode === "shop") {
    if (event.code === "KeyA") purchaseUpgrade("speed");
    if (event.code === "KeyB") purchaseUpgrade("shield");
    if (event.code === "Space") purchaseUpgrade("chain");
    if (event.code === "Enter") closeShop();
    return;
  }

  if (event.code === "KeyF") {
    toggleFullscreen();
  }

  if (event.code === "Enter") {
    if (state.mode === "menu") startGame();
    else if (state.mode === "playing") openShop();
  }

  if (event.code === "KeyP") {
    if (state.mode === "playing") pauseGame();
    else if (state.mode === "paused") resumeGame();
  }

  if (event.code === "Escape" && !document.fullscreenElement) {
    if (state.mode === "playing") pauseGame();
  }

  if (event.code === "KeyR" && (state.mode === "gameover" || state.mode === "win")) {
    startGame();
  }

  if (event.code === "ShiftLeft" || event.code === "ShiftRight" || event.code === "KeyB") {
    triggerDash();
  }

  if (event.code === "KeyE") {
    triggerShield();
  }
});

window.addEventListener("keyup", (event) => {
  keysDown.delete(event.code);
});

function updateMouseTarget(event) {
  const rect = canvas.getBoundingClientRect();
  const x = ((event.clientX - rect.left) / rect.width) * world.width;
  const y = ((event.clientY - rect.top) / rect.height) * world.height;
  state.mouse.x = clamp(x, 0, world.width);
  state.mouse.y = clamp(y, 0, world.height);
}

canvas.addEventListener("mousemove", (event) => {
  state.mouse.inside = true;
  state.mouse.active = true;
  updateMouseTarget(event);
});

canvas.addEventListener("mouseleave", () => {
  state.mouse.inside = false;
  state.mouse.active = false;
});

canvas.addEventListener("contextmenu", (event) => {
  event.preventDefault();
});

canvas.addEventListener("mousedown", (event) => {
  if (event.button === 2) {
    triggerShield();
  }
});

function getMovementVector() {
  let dx = 0;
  let dy = 0;
  if (keysDown.has("ArrowLeft") || keysDown.has("KeyA")) dx -= 1;
  if (keysDown.has("ArrowRight") || keysDown.has("KeyD")) dx += 1;
  if (keysDown.has("ArrowUp") || keysDown.has("KeyW")) dy -= 1;
  if (keysDown.has("ArrowDown") || keysDown.has("KeyS")) dy += 1;
  if (!dx && !dy) return { x: 0, y: 0, len: 0 };
  const len = Math.hypot(dx, dy);
  return { x: dx / len, y: dy / len, len };
}

function updatePlayer(dt, slowFactor, speedBoostFactor) {
  const move = getMovementVector();
  const player = state.player;
  const maxSpeed = player.speed * speedBoostFactor * slowFactor;
  const accel = player.accel * speedBoostFactor * slowFactor;
  let speed = Math.hypot(player.vx, player.vy);

  if (state.dashTime > 0) {
    state.dashTime = Math.max(0, state.dashTime - dt);
    player.vx = state.dashDir.x * 520;
    player.vy = state.dashDir.y * 520;
  } else if (move.len) {
    player.vx += move.x * accel * dt;
    player.vy += move.y * accel * dt;
    speed = Math.hypot(player.vx, player.vy);
    if (speed > maxSpeed) {
      player.vx = (player.vx / speed) * maxSpeed;
      player.vy = (player.vy / speed) * maxSpeed;
    }
  } else {
    const drag = Math.max(0, 1 - player.drag * dt);
    player.vx *= drag;
    player.vy *= drag;
    speed = Math.hypot(player.vx, player.vy);
  }

  if (state.mouse.inside) {
    const mx = state.mouse.x - player.x;
    const my = state.mouse.y - player.y;
    const dist = Math.hypot(mx, my);
    if (dist > 8) {
      player.facing = { x: mx / dist, y: my / dist };
    }
  } else if (speed > 20) {
    player.facing = { x: player.vx / speed, y: player.vy / speed };
  }

  player.x += player.vx * dt;
  player.y += player.vy * dt;

  player.x = clamp(player.x, player.r, world.width - player.r);
  player.y = clamp(player.y, player.r, world.height - player.r);

  if (player.invuln > 0) player.invuln = Math.max(0, player.invuln - dt);
}

function spawnParticles({ x, y, color, count, speed, life }) {
  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const spread = speed * (0.4 + Math.random() * 0.6);
    state.particles.push({
      x,
      y,
      vx: Math.cos(angle) * spread,
      vy: Math.sin(angle) * spread,
      life,
      ttl: life,
      color,
    });
  }
}

function addShake(strength, time) {
  state.shake.strength = Math.max(state.shake.strength, strength);
  state.shake.time = Math.max(state.shake.time, time);
}

function spawnBullet({ origin, angle, speed, owner, damage, pierce, homing, bounces }) {
  state.bullets.push({
    x: origin.x,
    y: origin.y,
    vx: Math.cos(angle) * speed,
    vy: Math.sin(angle) * speed,
    r: 4,
    life: 1.1,
    owner,
    damage,
    pierce,
    homing,
    bounces,
  });
}

function fireBullet({
  origin,
  angle,
  speed,
  owner = "player",
  damage = 1,
  spreadCount = 1,
  spreadAngle = 0,
  pierce = 0,
  homing = false,
  bounces = 0,
}) {
  const offsets = [];
  if (spreadCount === 1) {
    offsets.push(0);
  } else {
    const start = -spreadAngle * (spreadCount - 1) * 0.5;
    for (let i = 0; i < spreadCount; i++) {
      offsets.push(start + spreadAngle * i);
    }
  }
  for (const offset of offsets) {
    spawnBullet({
      origin: {
        x: origin.x + Math.cos(angle + offset) * 20,
        y: origin.y + Math.sin(angle + offset) * 20,
      },
      angle: angle + offset,
      speed,
      owner,
      damage,
      pierce,
      homing,
      bounces,
    });
  }
}

function firePlayerShot() {
  const dir = state.player.facing;
  const speed = 420;
  const baseAngle = Math.atan2(dir.y, dir.x);
  let spreadCount = 3;
  let spreadAngle = 0.14;
  let pierce = 0;
  let homing = false;
  let bounces = 0;

  if (state.ammoMode === "five") {
    spreadCount = 5;
    spreadAngle = 0.12;
  } else if (state.ammoMode === "pierce") {
    pierce = 2;
  } else if (state.ammoMode === "homing") {
    homing = true;
  } else if (state.ammoMode === "ricochet") {
    bounces = 1;
  }

  fireBullet({
    origin: { x: state.player.x, y: state.player.y },
    angle: baseAngle,
    speed,
    owner: "player",
    damage: 1,
    spreadCount,
    spreadAngle,
    pierce,
    homing,
    bounces,
  });
  playTone(740, 0.05, "square", 0.05);
  spawnParticles({
    x: state.player.x + dir.x * (state.player.r + 2),
    y: state.player.y + dir.y * (state.player.r + 2),
    color: "rgba(249, 248, 113, 0.9)",
    count: 6,
    speed: 90,
    life: 0.35,
  });
}

function updateBullets(dt) {
  state.bullets = state.bullets.filter((b) => {
    if (b.homing) {
      let nearest = null;
      let nearestDist = 9999;
      for (const enemy of state.enemies) {
        const dx = enemy.x - b.x;
        const dy = enemy.y - b.y;
        const dist = Math.hypot(dx, dy);
        if (dist < nearestDist) {
          nearestDist = dist;
          nearest = enemy;
        }
      }
      if (nearest && nearestDist < 240) {
        const angle = Math.atan2(nearest.y - b.y, nearest.x - b.x);
        const speed = Math.hypot(b.vx, b.vy);
        b.vx += Math.cos(angle) * speed * 0.04;
        b.vy += Math.sin(angle) * speed * 0.04;
        const newSpeed = Math.hypot(b.vx, b.vy);
        if (newSpeed > 0) {
          b.vx = (b.vx / newSpeed) * speed;
          b.vy = (b.vy / newSpeed) * speed;
        }
      }
    }

    b.x += b.vx * dt;
    b.y += b.vy * dt;
    b.life -= dt;

    if (b.bounces && b.bounces > 0) {
      let bounced = false;
      if (b.x < 0 || b.x > world.width) {
        b.vx *= -1;
        bounced = true;
      }
      if (b.y < 0 || b.y > world.height) {
        b.vy *= -1;
        bounced = true;
      }
      if (bounced) b.bounces -= 1;
    }

    const onScreen =
      b.x > -40 && b.x < world.width + 40 && b.y > -40 && b.y < world.height + 40;
    return b.life > 0 && onScreen;
  });
}

function spawnSplitlets(origin) {
  for (let i = 0; i < 2; i++) {
    const child = createEnemy("splitlet");
    child.x = origin.x + (Math.random() * 18 - 9);
    child.y = origin.y + (Math.random() * 18 - 9);
    child.vx = (Math.random() * 2 - 1) * 140;
    child.vy = (Math.random() * 2 - 1) * 140;
    state.enemies.push(child);
  }
}

function updateEnemies(dt) {
  for (const enemy of state.enemies) {
    if (enemy.stun > 0) {
      enemy.stun = Math.max(0, enemy.stun - dt);
      enemy.vx *= 0.9;
      enemy.vy *= 0.9;
      if (enemy.stun === 0 && enemy.type === "charger") {
        enemy.mode = "normal";
      }
      enemy.x += enemy.vx * dt;
      enemy.y += enemy.vy * dt;
      enemy.x = clamp(enemy.x, enemy.r, world.width - enemy.r);
      enemy.y = clamp(enemy.y, enemy.r, world.height - enemy.r);
      continue;
    }

    const dx = state.player.x - enemy.x;
    const dy = state.player.y - enemy.y;
    const dist = Math.max(1, Math.hypot(dx, dy));
    const steerX = dx / dist;
    const steerY = dy / dist;
    const perpX = -steerY;
    const perpY = steerX;

    if (enemy.type === "boss") {
      enemy.vx += steerX * enemy.speed * dt * 0.3;
      enemy.vy += steerY * enemy.speed * dt * 0.3;
      enemy.dropCooldown -= dt;
      if (enemy.dropCooldown <= 0) {
        enemy.dropCooldown = 4.5;
        state.enemies.push(createEnemy("chaser"));
        if (Math.random() < 0.5) state.enemies.push(createEnemy("sapper"));
        spawnParticles({
          x: enemy.x,
          y: enemy.y,
          color: "rgba(255, 184, 108, 0.9)",
          count: 16,
          speed: 140,
          life: 0.6,
        });
      }
      enemy.shootCooldown -= dt;
      if (enemy.shootCooldown <= 0) {
        enemy.shootCooldown = 1.8;
        const angle = Math.atan2(state.player.y - enemy.y, state.player.x - enemy.x);
        fireBullet({
          origin: { x: enemy.x, y: enemy.y },
          angle,
          speed: 260,
          owner: "enemy",
          damage: 1,
          spreadCount: 3,
          spreadAngle: 0.18,
        });
      }
    } else if (enemy.type === "charger") {
      if (enemy.mode === "windup") {
        enemy.windup -= dt;
        enemy.vx *= 0.86;
        enemy.vy *= 0.86;
        if (enemy.windup <= 0) {
          enemy.mode = "dash";
          enemy.dashTime = 0.35;
          enemy.vx = steerX * enemy.dashSpeed;
          enemy.vy = steerY * enemy.dashSpeed;
        }
      } else if (enemy.mode === "dash") {
        enemy.dashTime -= dt;
        if (enemy.dashTime <= 0) {
          enemy.mode = "normal";
          enemy.chargeCooldown = 2.1 + Math.random() * 1.2;
        }
      } else {
        enemy.chargeCooldown -= dt;
        if (enemy.chargeCooldown <= 0 && dist < 260) {
          enemy.mode = "windup";
          enemy.windup = 0.45;
          enemy.vx *= 0.5;
          enemy.vy *= 0.5;
        } else {
          enemy.vx += steerX * enemy.speed * dt * 0.45;
          enemy.vy += steerY * enemy.speed * dt * 0.45;
        }
      }
    } else if (enemy.type === "skirmisher") {
      const radialError = clamp((dist - enemy.orbitRadius) / enemy.orbitRadius, -1.2, 1.2);
      enemy.vx += steerX * radialError * enemy.speed * dt * 1.4;
      enemy.vy += steerY * radialError * enemy.speed * dt * 1.4;
      enemy.vx += perpX * enemy.speed * dt * 0.7 * enemy.orbitDir;
      enemy.vy += perpY * enemy.speed * dt * 0.7 * enemy.orbitDir;
    } else if (enemy.type === "sapper") {
      const radialError = clamp((dist - enemy.orbitRadius) / enemy.orbitRadius, -1.2, 1.2);
      enemy.vx += steerX * radialError * enemy.speed * dt * 1.2;
      enemy.vy += steerY * radialError * enemy.speed * dt * 1.2;
      enemy.vx += perpX * enemy.speed * dt * 0.5 * enemy.orbitDir;
      enemy.vy += perpY * enemy.speed * dt * 0.5 * enemy.orbitDir;
      enemy.dropCooldown -= dt;
      if (enemy.dropCooldown <= 0 && dist < 260) {
        spawnSlowField(enemy.x, enemy.y);
        enemy.dropCooldown = 4.5 + Math.random() * 2.2;
        spawnParticles({
          x: enemy.x,
          y: enemy.y,
          color: "rgba(124, 255, 107, 0.9)",
          count: 10,
          speed: 120,
          life: 0.4,
        });
      }
    } else {
      enemy.vx += steerX * enemy.speed * dt * 0.6;
      enemy.vy += steerY * enemy.speed * dt * 0.6;
    }

    const speed = Math.hypot(enemy.vx, enemy.vy);
    const maxSpeed = enemy.speed;
    if (enemy.mode !== "dash" && speed > maxSpeed) {
      enemy.vx = (enemy.vx / speed) * maxSpeed;
      enemy.vy = (enemy.vy / speed) * maxSpeed;
    }

    enemy.x += enemy.vx * dt;
    enemy.y += enemy.vy * dt;

    if (enemy.x < enemy.r || enemy.x > world.width - enemy.r) enemy.vx *= -1;
    if (enemy.y < enemy.r || enemy.y > world.height - enemy.r) enemy.vy *= -1;

    enemy.x = clamp(enemy.x, enemy.r, world.width - enemy.r);
    enemy.y = clamp(enemy.y, enemy.r, world.height - enemy.r);
  }

}

function updateParticles(dt) {
  state.particles = state.particles.filter((p) => {
    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.life -= dt;
    return p.life > 0;
  });
}

function updateSlowFields(dt) {
  state.slowFields = state.slowFields.filter((field) => {
    field.life -= dt;
    return field.life > 0;
  });
}

function updatePods(dt) {
  state.pods = state.pods.filter((pod) => {
    pod.life -= dt;
    return pod.life > 0;
  });
  if (state.pods.length < 2) {
    state.podTimer -= dt;
    if (state.podTimer <= 0) {
      spawnFuelPod();
      state.podTimer = 6 + Math.random() * 6;
    }
  }
}

function updateMods(dt) {
  state.mods = state.mods.filter((mod) => {
    mod.life -= dt;
    return mod.life > 0;
  });
  if (state.ammoTimer > 0) {
    state.ammoTimer = Math.max(0, state.ammoTimer - dt);
    if (state.ammoTimer === 0) state.ammoMode = "spread";
  } else if (state.mods.length === 0) {
    state.modTimer -= dt;
    if (state.modTimer <= 0) {
      spawnModPickup();
      state.modTimer = 10 + Math.random() * 8;
    }
  }
}

function updateRiskZones(dt) {
  state.riskZones = state.riskZones.filter((zone) => {
    zone.life -= dt;
    return zone.life > 0;
  });
  if (state.riskZones.length === 0) {
    state.riskTimer -= dt;
    if (state.riskTimer <= 0) {
      spawnRiskZone();
      state.riskTimer = 16 + Math.random() * 8;
    }
  }
}

function updateDrone(dt) {
  const drone = state.drone;
  drone.angle += dt * 1.4;
  const radius = 32 + drone.level * 4;
  drone.x = state.player.x + Math.cos(drone.angle) * radius;
  drone.y = state.player.y + Math.sin(drone.angle) * radius;
  if (drone.cooldown > 0) {
    drone.cooldown = Math.max(0, drone.cooldown - dt);
    return;
  }
  let nearest = null;
  let nearestDist = 9999;
  for (const enemy of state.enemies) {
    const dx = enemy.x - drone.x;
    const dy = enemy.y - drone.y;
    const dist = Math.hypot(dx, dy);
    if (dist < nearestDist) {
      nearestDist = dist;
      nearest = enemy;
    }
  }
  if (nearest && nearestDist < 280) {
    const angle = Math.atan2(nearest.y - drone.y, nearest.x - drone.x);
    fireBullet({
      origin: { x: drone.x, y: drone.y },
      angle,
      speed: 360,
      owner: "drone",
      damage: 0.7,
    });
    drone.cooldown = drone.fireRate;
  }
}

function updateObjectives(dt) {
  if (state.objectiveCooldown > 0) {
    state.objectiveCooldown = Math.max(0, state.objectiveCooldown - dt);
    return;
  }
  if (!state.objective) {
    const roll = Math.random();
    if (roll < 0.34) {
      state.objective = {
        type: "survive",
        timer: 18,
        target: 18,
        progress: 0,
        reward: 180,
      };
    } else if (roll < 0.67) {
      state.objective = {
        type: "collect",
        timer: 12,
        target: 2,
        progress: 0,
        reward: 160,
      };
    } else {
      state.objective = {
        type: "slay",
        timer: 12,
        target: 3,
        progress: 0,
        reward: 200,
      };
    }
  }
  if (!state.objective) return;
  state.objective.timer = Math.max(0, state.objective.timer - dt);
  if (state.objective.type === "survive") {
    state.objective.progress = state.objective.target - state.objective.timer;
    if (state.objective.timer === 0) {
      state.score += state.objective.reward;
      playTone(520, 0.12, "square", 0.08);
      addFlash("rgba(255, 200, 120, 0.3)", 0.3);
      state.objective = null;
      state.objectiveCooldown = 6;
    }
  } else if (state.objective.timer === 0) {
    state.objective = null;
    state.objectiveCooldown = 6;
  }
}

function registerObjectiveEvent(eventType) {
  if (!state.objective) return;
  if (state.objective.type === "collect" && eventType === "collect") {
    state.objective.progress += 1;
    if (state.objective.progress >= state.objective.target) {
      state.score += state.objective.reward;
      playTone(560, 0.12, "square", 0.08);
      addFlash("rgba(255, 200, 120, 0.3)", 0.3);
      state.objective = null;
      state.objectiveCooldown = 6;
    }
  } else if (state.objective.type === "slay" && eventType === "slay") {
    state.objective.progress += 1;
    if (state.objective.progress >= state.objective.target) {
      state.score += state.objective.reward;
      playTone(560, 0.12, "square", 0.08);
      addFlash("rgba(255, 200, 120, 0.3)", 0.3);
      state.objective = null;
      state.objectiveCooldown = 6;
    }
  } else if (state.objective.type === "survive" && eventType === "damage") {
    state.objective = null;
    state.objectiveCooldown = 6;
  }
}

function getRiskMultiplier() {
  for (const zone of state.riskZones) {
    const dx = state.player.x - zone.x;
    const dy = state.player.y - zone.y;
    if (Math.hypot(dx, dy) < zone.r) {
      return 1.5;
    }
  }
  return 1;
}

function getAmmoLabel() {
  if (state.ammoMode === "five") return "Five";
  if (state.ammoMode === "pierce") return "Pierce";
  if (state.ammoMode === "homing") return "Homing";
  if (state.ammoMode === "ricochet") return "Ricochet";
  return "Tri";
}

function getSlowFactor() {
  let factor = 1;
  for (const field of state.slowFields) {
    const dx = state.player.x - field.x;
    const dy = state.player.y - field.y;
    if (Math.hypot(dx, dy) < field.r) {
      factor = Math.min(factor, 0.55);
    }
  }
  return factor;
}

function handleCollisions() {
  const player = state.player;
  const riskMultiplier = getRiskMultiplier();
  state.chainWindow = getChainWindow() + (riskMultiplier > 1 ? 1.2 : 0);

  for (let i = state.gems.length - 1; i >= 0; i--) {
    const gem = state.gems[i];
    if (distance(player, gem) < player.r + gem.r) {
      state.gems.splice(i, 1);
      state.collected += 1;
      if (state.chainTimer > 0) state.chainCount += 1;
      else state.chainCount = 1;
      state.chainTimer = state.chainWindow;
      state.score += Math.round(100 * state.chainCount * riskMultiplier);
      registerObjectiveEvent("collect");
      spawnParticles({
        x: gem.x,
        y: gem.y,
        color: "rgba(255, 184, 108, 0.9)",
        count: 14,
        speed: 140,
        life: 0.6,
      });
      playTone(520, 0.07, "triangle", 0.06);
    }
  }

  if (state.collected >= state.goal && !state.gateActive) {
    state.gems = [];
    spawnGate();
  }

  if (!state.gateActive && state.gems.length < state.gemTarget) {
    spawnGem();
  }

  for (let i = state.enemies.length - 1; i >= 0; i--) {
    const enemy = state.enemies[i];
    if (distance(player, enemy) < player.r + enemy.r) {
      if (player.invuln <= 0) {
        player.health -= 1;
        player.invuln = 1.1;
        player.vx -= (enemy.x - player.x) * 2.5;
        player.vy -= (enemy.y - player.y) * 2.5;
        addShake(10, 0.3);
        addFlash("rgba(255, 90, 90, 0.35)", 0.35);
        playTone(180, 0.12, "sawtooth", 0.08);
        registerObjectiveEvent("damage");
        spawnParticles({
          x: player.x,
          y: player.y,
          color: "rgba(255, 107, 107, 0.9)",
          count: 18,
          speed: 160,
          life: 0.5,
        });
        if (player.health <= 0) {
          endGame(false);
          return;
        }
      }
    }
  }

  for (let i = state.bullets.length - 1; i >= 0; i--) {
    const bullet = state.bullets[i];
    if (bullet.owner === "enemy") {
      if (distance(bullet, player) < bullet.r + player.r) {
        state.bullets.splice(i, 1);
        if (player.invuln <= 0) {
          player.health -= bullet.damage || 1;
          player.invuln = 0.8;
          addShake(8, 0.25);
          addFlash("rgba(255, 90, 90, 0.35)", 0.35);
          playTone(180, 0.12, "sawtooth", 0.08);
          registerObjectiveEvent("damage");
          if (player.health <= 0) {
            endGame(false);
            return;
          }
        }
      }
      continue;
    }

    for (let j = state.enemies.length - 1; j >= 0; j--) {
      const enemy = state.enemies[j];
      if (distance(bullet, enemy) < bullet.r + enemy.r) {
        if (bullet.pierce && bullet.pierce > 0) {
          bullet.pierce -= 1;
        } else {
          state.bullets.splice(i, 1);
        }
        enemy.hp -= bullet.damage || 1;
        spawnParticles({
          x: bullet.x,
          y: bullet.y,
          color: "rgba(119, 224, 255, 0.9)",
          count: 8,
          speed: 120,
          life: 0.4,
        });
        if (enemy.hp <= 0) {
          state.enemies.splice(j, 1);
          state.score += Math.round(200 * riskMultiplier);
          registerObjectiveEvent("slay");
          addShake(6, 0.2);
          spawnParticles({
            x: enemy.x,
            y: enemy.y,
            color: "rgba(255, 107, 107, 0.9)",
            count: 16,
            speed: 150,
            life: 0.6,
          });
          if (enemy.splitOnDeath) {
            spawnSplitlets(enemy);
          }
        }
        break;
      }
    }
  }

  for (let i = state.pods.length - 1; i >= 0; i--) {
    const pod = state.pods[i];
    if (distance(player, pod) < player.r + pod.r) {
      state.pods.splice(i, 1);
      if (player.health < player.maxHealth) {
        player.health += 1;
      } else {
        state.speedBoost = 3;
      }
      spawnParticles({
        x: pod.x,
        y: pod.y,
        color: "rgba(119, 224, 255, 0.9)",
        count: 12,
        speed: 140,
        life: 0.5,
      });
      playTone(600, 0.1, "triangle", 0.06);
    }
  }

  for (let i = state.mods.length - 1; i >= 0; i--) {
    const mod = state.mods[i];
    if (distance(player, mod) < player.r + mod.r) {
      state.mods.splice(i, 1);
      state.ammoMode = mod.type;
      state.ammoTimer = 12;
      spawnParticles({
        x: mod.x,
        y: mod.y,
        color: "rgba(249, 248, 113, 0.9)",
        count: 12,
        speed: 150,
        life: 0.5,
      });
      playTone(720, 0.12, "square", 0.06);
    }
  }

  if (state.gateActive && state.gate) {
    if (distance(player, state.gate) < player.r + state.gate.r) {
      endGame(true);
      return;
    }
  }
}

function update(dt) {
  if (state.mode !== "playing") return;

  state.time += dt;

  if (state.dashCooldown > 0) state.dashCooldown = Math.max(0, state.dashCooldown - dt);
  if (state.shieldCooldown > 0) state.shieldCooldown = Math.max(0, state.shieldCooldown - dt);
  if (state.chainTimer > 0) {
    state.chainTimer = Math.max(0, state.chainTimer - dt);
    if (state.chainTimer === 0) state.chainCount = 0;
  }
  if (state.speedBoost > 0) state.speedBoost = Math.max(0, state.speedBoost - dt);

  const slowFactor = getSlowFactor();
  const boostFactor = state.speedBoost > 0 ? 1.35 : 1;
  const riskMultiplier = getRiskMultiplier();
  state.chainWindow = getChainWindow() + (riskMultiplier > 1 ? 1.2 : 0);
  if (riskMultiplier > 1) {
    state.riskTick += dt;
    if (state.riskTick >= 2.6) {
      state.riskTick = 0;
      if (state.player.invuln <= 0) {
        state.player.health -= 1;
        state.player.invuln = 0.6;
        addFlash("rgba(255, 120, 80, 0.3)", 0.3);
        playTone(220, 0.1, "sawtooth", 0.06);
        registerObjectiveEvent("damage");
        if (state.player.health <= 0) {
          endGame(false);
          return;
        }
      }
    }
  } else {
    state.riskTick = 0;
  }
  updatePlayer(dt, slowFactor, boostFactor);

  if (state.shootCooldown > 0) state.shootCooldown -= dt;
  if (keysDown.has("Space") && !state.overheated) {
    state.heat += dt * 65;
  } else {
    state.heat -= dt * 50;
  }
  if (!keysDown.has("Space")) {
    state.heat -= dt * 30;
  }
  state.heat = clamp(state.heat, 0, state.heatMax);
  if (!state.overheated && state.heat >= state.heatMax) {
    state.overheated = true;
  }
  if (state.overheated && state.heat <= state.heatMax * 0.35) {
    state.overheated = false;
  }

  if (keysDown.has("Space") && state.shootCooldown <= 0 && !state.overheated) {
    firePlayerShot();
    state.shootCooldown = 0.22;
  }

  for (const gem of state.gems) {
    const dx = state.player.x - gem.x;
    const dy = state.player.y - gem.y;
    const dist = Math.hypot(dx, dy);
    if (dist > 1 && dist < 90) {
      const pull = (1 - dist / 90) * 140;
      gem.x += (dx / dist) * pull * dt;
      gem.y += (dy / dist) * pull * dt;
    }
  }

  updateBullets(dt);
  updateEnemies(dt);
  updateDrone(dt);
  updateParticles(dt);
  updateSlowFields(dt);
  updatePods(dt);
  updateMods(dt);
  updateRiskZones(dt);
  updateObjectives(dt);
  handleCollisions();

  if (!state.gateActive) {
    if (state.enemies.length === 0) {
      state.wavePause -= dt;
      if (state.wavePause <= 0) {
        state.wave += 1;
        state.wavePause = 2;
        spawnWave();
      }
    } else {
      state.wavePause = 2;
    }
  }

  if (state.shake.time > 0) {
    state.shake.time = Math.max(0, state.shake.time - dt);
    if (state.shake.time === 0) state.shake.strength = 0;
  }

  if (state.flash.time > 0) {
    state.flash.time = Math.max(0, state.flash.time - dt);
  }

  if (state.gateActive && state.gate) {
    state.gate.pulse += dt * 2.2;
  }
}

function drawBackground() {
  const grad = ctx.createLinearGradient(0, 0, 0, world.height);
  grad.addColorStop(0, "#05070f");
  grad.addColorStop(0.5, "#141a2c");
  grad.addColorStop(1, "#11101f");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, world.width, world.height);

  for (const star of state.stars) {
    star.tw += 0.02;
    const glow = 0.4 + Math.sin(star.tw) * 0.4;
    ctx.fillStyle = `rgba(119, 224, 255, ${0.3 + glow})`;
    ctx.beginPath();
    ctx.arc(star.x, star.y, star.r + glow * 0.6, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawPlayer() {
  const player = state.player;
  const pulse = player.invuln > 0 ? 0.4 + Math.sin(state.time * 18) * 0.4 : 1;
  const angle = Math.atan2(player.facing.y, player.facing.x) + Math.PI / 2;
  const size = player.r * 3.1;
  if (!drawSprite(SPRITES.player, player.x, player.y, size, angle, pulse)) {
    ctx.save();
    ctx.globalAlpha = pulse;
    ctx.fillStyle = "#77e0ff";
    ctx.beginPath();
    ctx.arc(player.x, player.y, player.r, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = "rgba(255, 255, 255, 0.9)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(player.x, player.y);
    ctx.lineTo(player.x + player.facing.x * 18, player.y + player.facing.y * 18);
    ctx.stroke();
    ctx.restore();
  }
}

function drawGems() {
  for (const gem of state.gems) {
    gem.spin += 0.05;
    const size = gem.r * 2.4;
    if (!drawSprite(SPRITES.core, gem.x, gem.y, size, gem.spin)) {
      ctx.save();
      ctx.translate(gem.x, gem.y);
      ctx.rotate(gem.spin);
      ctx.fillStyle = "#ffb86c";
      ctx.beginPath();
      ctx.moveTo(0, -gem.r);
      ctx.lineTo(gem.r, 0);
      ctx.lineTo(0, gem.r);
      ctx.lineTo(-gem.r, 0);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }
  }
}

function drawSlowFields() {
  for (const field of state.slowFields) {
    const alpha = Math.max(0, field.life / 4) * 0.35;
    ctx.strokeStyle = `rgba(124, 255, 107, ${alpha.toFixed(2)})`;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(field.x, field.y, field.r, 0, Math.PI * 2);
    ctx.stroke();
  }
}

function drawPods() {
  for (const pod of state.pods) {
    const size = pod.r * 2.6;
    if (!drawSprite(SPRITES.pod, pod.x, pod.y, size, state.time * 0.8)) {
      ctx.save();
      ctx.translate(pod.x, pod.y);
      ctx.fillStyle = "#77e0ff";
      ctx.beginPath();
      ctx.moveTo(0, -pod.r);
      ctx.quadraticCurveTo(pod.r, -pod.r * 0.2, 0, pod.r);
      ctx.quadraticCurveTo(-pod.r, -pod.r * 0.2, 0, -pod.r);
      ctx.fill();
      ctx.restore();
    }
  }
}

function drawMods() {
  for (const mod of state.mods) {
    const size = mod.r * 2.6;
    drawSprite(SPRITES.mod, mod.x, mod.y, size, state.time * 0.6);
  }
}

function drawRiskZones() {
  for (const zone of state.riskZones) {
    const alpha = Math.max(0, zone.life / 18) * 0.35;
    ctx.strokeStyle = `rgba(255, 184, 108, ${alpha.toFixed(2)})`;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(zone.x, zone.y, zone.r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(zone.x, zone.y, zone.r * 0.6, 0, Math.PI * 2);
    ctx.stroke();
  }
}

function drawDrone() {
  const drone = state.drone;
  ctx.fillStyle = "rgba(119, 224, 255, 0.9)";
  ctx.beginPath();
  ctx.arc(drone.x, drone.y, 6, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.5)";
  ctx.beginPath();
  ctx.moveTo(drone.x, drone.y);
  ctx.lineTo(state.player.x, state.player.y);
  ctx.stroke();
}

function drawEnemies() {
  for (const enemy of state.enemies) {
    const target =
      enemy.type === "boss"
        ? SPRITES.boss
        : enemy.type === "skirmisher"
          ? SPRITES.skirmisher
          : enemy.type === "charger"
            ? SPRITES.charger
            : enemy.type === "sapper"
              ? SPRITES.sapper
              : enemy.type === "splitter"
                ? SPRITES.splitter
                : enemy.type === "splitlet"
                  ? SPRITES.splitlet
                  : SPRITES.chaser;
    const enemyAngle =
      Math.hypot(enemy.vx, enemy.vy) > 10
        ? Math.atan2(enemy.vy, enemy.vx) + Math.PI / 2
        : Math.atan2(state.player.y - enemy.y, state.player.x - enemy.x) + Math.PI / 2;
    const size =
      enemy.type === "boss"
        ? enemy.r * 3.2
        : enemy.type === "splitlet"
          ? enemy.r * 2.6
          : enemy.r * 3.1;
    const drawn = drawSprite(target, enemy.x, enemy.y, size, enemyAngle);
    if (!drawn) {
      ctx.fillStyle = enemy.type === "charger" ? "#4fffe1" : "#ff6b6b";
      ctx.beginPath();
      ctx.arc(enemy.x, enemy.y, enemy.r, 0, Math.PI * 2);
      ctx.fill();
    }

    if (enemy.type === "charger") {
      const pulse = enemy.mode === "windup" ? 0.5 + Math.sin(state.time * 12) * 0.5 : 0;
      if (pulse > 0) {
        ctx.strokeStyle = `rgba(79, 255, 225, ${0.35 + pulse * 0.3})`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(enemy.x, enemy.y, enemy.r + 8 + pulse * 4, 0, Math.PI * 2);
        ctx.stroke();
      }
    } else {
      ctx.strokeStyle = "rgba(255,255,255,0.6)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(enemy.x - enemy.r * 0.5, enemy.y - enemy.r * 0.5);
      ctx.lineTo(enemy.x + enemy.r * 0.5, enemy.y + enemy.r * 0.5);
      ctx.stroke();
    }

    const barWidth = enemy.type === "boss" ? 70 : 26;
    const barX = enemy.x - barWidth / 2;
    const barY = enemy.y + enemy.r + 6;
    ctx.fillStyle = "rgba(12, 15, 26, 0.7)";
    ctx.fillRect(barX, barY, barWidth, 4);
    ctx.fillStyle = "#77e0ff";
    ctx.fillRect(barX, barY, barWidth * (enemy.hp / enemy.maxHp), 4);
  }
}

function drawBullets() {
  for (const bullet of state.bullets) {
    const angle = Math.atan2(bullet.vy, bullet.vx) + Math.PI / 2;
    const size = 18;
    if (bullet.owner === "enemy") {
      ctx.fillStyle = "rgba(255, 107, 107, 0.8)";
      ctx.beginPath();
      ctx.arc(bullet.x, bullet.y, bullet.r + 2, 0, Math.PI * 2);
      ctx.fill();
    }
    if (!drawSprite(SPRITES.bullet, bullet.x, bullet.y, size, angle)) {
      ctx.fillStyle = "rgba(249, 248, 113, 0.9)";
      ctx.beginPath();
      ctx.arc(bullet.x, bullet.y, bullet.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

function drawParticles() {
  for (const p of state.particles) {
    const alpha = Math.max(0, p.life / p.ttl);
    ctx.fillStyle = p.color.replace("0.9", alpha.toFixed(2));
    ctx.beginPath();
    ctx.arc(p.x, p.y, 2.2, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawGate() {
  if (!state.gateActive || !state.gate) return;
  const gate = state.gate;
  const pulse = 0.5 + Math.sin(gate.pulse) * 0.4;
  const size = gate.r * 2.6;
  if (!drawSprite(SPRITES.gate, gate.x, gate.y, size, gate.pulse * 0.05)) {
    ctx.strokeStyle = `rgba(119, 224, 255, ${0.4 + pulse * 0.4})`;
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(gate.x, gate.y, gate.r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = `rgba(255, 184, 108, ${0.2 + pulse * 0.3})`;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(gate.x, gate.y, gate.r + 10 + pulse * 6, 0, Math.PI * 2);
    ctx.stroke();
  }
}

function drawHud() {
  ctx.save();
  ctx.fillStyle = "rgba(12, 15, 26, 0.7)";
  ctx.fillRect(16, 16, 210, 98);
  ctx.strokeStyle = "rgba(255,255,255,0.2)";
  ctx.strokeRect(16, 16, 210, 98);

  ctx.fillStyle = "#f4f6ff";
  ctx.font = "14px 'DM Mono', monospace";
  ctx.fillText(`Score ${state.score}`, 28, 38);
  const objective = state.gateActive ? "Gate online" : `${state.collected}/${state.goal}`;
  ctx.fillText(`Cores ${objective}`, 28, 58);
  ctx.fillText(`Hull ${state.player.health}`, 28, 78);
  ctx.fillText(`Wave ${state.wave}`, 28, 98);
  ctx.restore();

  ctx.save();
  ctx.fillStyle = "rgba(12, 15, 26, 0.7)";
  ctx.fillRect(world.width - 220, 16, 204, 110);
  ctx.strokeStyle = "rgba(255,255,255,0.2)";
  ctx.strokeRect(world.width - 220, 16, 204, 110);

  const heatWidth = 170;
  const heatX = world.width - 210;
  const heatY = 30;
  const heatRatio = state.heat / state.heatMax;
  ctx.fillStyle = "rgba(255,255,255,0.1)";
  ctx.fillRect(heatX, heatY, heatWidth, 8);
  ctx.fillStyle = state.overheated ? "#ff6b6b" : "#f9f871";
  ctx.fillRect(heatX, heatY, heatWidth * heatRatio, 8);
  ctx.fillStyle = "#f4f6ff";
  ctx.font = "12px 'DM Mono', monospace";
  ctx.fillText("Heat", heatX, heatY - 4);

  const chainRatio = state.chainTimer / state.chainWindow;
  ctx.fillStyle = "rgba(255,255,255,0.1)";
  ctx.fillRect(heatX, heatY + 20, heatWidth, 6);
  ctx.fillStyle = "#ffb86c";
  ctx.fillRect(heatX, heatY + 20, heatWidth * chainRatio, 6);
  ctx.fillStyle = "#f4f6ff";
  ctx.fillText(`Chain x${state.chainCount || 0}`, heatX, heatY + 18);

  ctx.fillStyle = "#77e0ff";
  ctx.fillText(`Dash ${state.dashCooldown.toFixed(1)}s`, heatX, heatY + 40);
  ctx.fillText(`Shield ${state.shieldCooldown.toFixed(1)}s`, heatX, heatY + 54);
  ctx.fillStyle = "#f4f6ff";
  ctx.fillText(`Ammo ${getAmmoLabel()}`, heatX, heatY + 70);

  if (state.objective) {
    const obj = state.objective;
    let label = "";
    if (obj.type === "survive") {
      label = `Objective: Survive ${obj.timer.toFixed(0)}s`;
    } else if (obj.type === "collect") {
      label = `Objective: Cores ${obj.progress}/${obj.target}`;
    } else if (obj.type === "slay") {
      label = `Objective: KOs ${obj.progress}/${obj.target}`;
    }
    ctx.fillStyle = "#ffb86c";
    ctx.fillText(label, heatX, heatY + 86);
  }
  ctx.restore();
}

function render() {
  let shakeX = 0;
  let shakeY = 0;
  if (state.shake.time > 0) {
    const strength = state.shake.strength;
    shakeX = (Math.random() * 2 - 1) * strength;
    shakeY = (Math.random() * 2 - 1) * strength;
  }
  ctx.setTransform(
    state.renderScale * state.pixelRatio,
    0,
    0,
    state.renderScale * state.pixelRatio,
    shakeX,
    shakeY
  );
  ctx.clearRect(0, 0, world.width, world.height);
  drawBackground();
  drawRiskZones();
  drawSlowFields();
  drawGems();
  drawMods();
  drawPods();
  drawParticles();
  drawBullets();
  drawGate();
  drawEnemies();
  drawDrone();
  drawPlayer();
  if (state.mode === "playing") drawHud();
  if (state.flash.time > 0) {
    ctx.save();
    ctx.globalAlpha = Math.min(1, state.flash.time * 2);
    ctx.fillStyle = state.flash.color;
    ctx.fillRect(0, 0, world.width, world.height);
    ctx.restore();
  }
}

function resizeCanvas() {
  const padding = 32;
  const isFullscreen = document.fullscreenElement || document.body.classList.contains("fullscreen");
  const maxWidth = isFullscreen ? window.innerWidth : Math.min(window.innerWidth - padding, 960);
  const maxHeight = isFullscreen ? window.innerHeight : Math.min(window.innerHeight - 220, 640);
  const scale = Math.min(maxWidth / world.width, maxHeight / world.height, 1);
  const displayWidth = Math.max(320, Math.floor(world.width * scale));
  const displayHeight = Math.max(220, Math.floor(world.height * scale));

  canvas.style.width = `${displayWidth}px`;
  canvas.style.height = `${displayHeight}px`;

  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.floor(displayWidth * ratio);
  canvas.height = Math.floor(displayHeight * ratio);
  state.renderScale = displayWidth / world.width;
  state.pixelRatio = ratio;
  render();
}

window.addEventListener("resize", resizeCanvas);

document.addEventListener("fullscreenchange", () => {
  document.body.classList.toggle("fullscreen", Boolean(document.fullscreenElement));
  setTimeout(resizeCanvas, 50);
});

let useExternalAdvance = false;

function tick(timestamp) {
  if (!state.lastTimestamp) state.lastTimestamp = timestamp;
  const dt = Math.min(0.05, (timestamp - state.lastTimestamp) / 1000);
  state.lastTimestamp = timestamp;
  if (!useExternalAdvance) {
    update(dt);
  }
  render();
  requestAnimationFrame(tick);
}

window.advanceTime = (ms) => {
  useExternalAdvance = true;
  const steps = Math.max(1, Math.round(ms / (1000 / 60)));
  for (let i = 0; i < steps; i++) {
    update(1 / 60);
  }
  render();
};

window.render_game_to_text = () => {
  const payload = {
    coordinate_system: "origin top-left, x right, y down, units pixels",
    mode: state.mode,
    time: Number(state.time.toFixed(2)),
    score: state.score,
    goal: state.goal,
    collected: state.collected,
    wave: state.wave,
    gateActive: state.gateActive,
    gate: state.gate
      ? { x: Number(state.gate.x.toFixed(1)), y: Number(state.gate.y.toFixed(1)), r: state.gate.r }
      : null,
    chain: {
      count: state.chainCount,
      timer: Number(state.chainTimer.toFixed(2)),
      window: state.chainWindow,
    },
    heat: {
      value: Number(state.heat.toFixed(1)),
      max: state.heatMax,
      overheated: state.overheated,
    },
    ammo: {
      mode: state.ammoMode,
      timer: Number(state.ammoTimer.toFixed(2)),
    },
    upgrades: { ...state.upgrades },
    cooldowns: {
      shoot: Number(state.shootCooldown.toFixed(2)),
      dash: Number(state.dashCooldown.toFixed(2)),
      shield: Number(state.shieldCooldown.toFixed(2)),
    },
    player: {
      x: Number(state.player.x.toFixed(1)),
      y: Number(state.player.y.toFixed(1)),
      vx: Number(state.player.vx.toFixed(1)),
      vy: Number(state.player.vy.toFixed(1)),
      r: state.player.r,
      speed: state.player.speed,
      health: state.player.health,
      invulnerable: state.player.invuln > 0,
      speedBoost: Number(state.speedBoost.toFixed(2)),
      dashTime: Number(state.dashTime.toFixed(2)),
      facing: {
        x: Number(state.player.facing.x.toFixed(2)),
        y: Number(state.player.facing.y.toFixed(2)),
      },
    },
    mouse: {
      x: Number(state.mouse.x.toFixed(1)),
      y: Number(state.mouse.y.toFixed(1)),
      active: state.mouse.active,
      inside: state.mouse.inside,
    },
    drone: {
      x: Number(state.drone.x.toFixed(1)),
      y: Number(state.drone.y.toFixed(1)),
      cooldown: Number(state.drone.cooldown.toFixed(2)),
      level: state.drone.level,
    },
    bullets: state.bullets.map((b) => ({
      x: Number(b.x.toFixed(1)),
      y: Number(b.y.toFixed(1)),
      vx: Number(b.vx.toFixed(1)),
      vy: Number(b.vy.toFixed(1)),
      r: b.r,
      life: Number(b.life.toFixed(2)),
      owner: b.owner,
      homing: Boolean(b.homing),
      pierce: b.pierce || 0,
      bounces: b.bounces || 0,
    })),
    enemies: state.enemies.map((e) => ({
      x: Number(e.x.toFixed(1)),
      y: Number(e.y.toFixed(1)),
      vx: Number(e.vx.toFixed(1)),
      vy: Number(e.vy.toFixed(1)),
      r: e.r,
      hp: e.hp,
      maxHp: e.maxHp,
      type: e.type,
      mode: e.mode,
      chargeCooldown: Number(e.chargeCooldown.toFixed(2)),
      windup: Number(e.windup.toFixed(2)),
      dashTime: Number(e.dashTime.toFixed(2)),
      orbitRadius: Number(e.orbitRadius.toFixed(1)),
    })),
    gems: state.gems.map((g) => ({
      x: Number(g.x.toFixed(1)),
      y: Number(g.y.toFixed(1)),
      r: g.r,
    })),
    mods: state.mods.map((m) => ({
      x: Number(m.x.toFixed(1)),
      y: Number(m.y.toFixed(1)),
      r: m.r,
      type: m.type,
      life: Number(m.life.toFixed(2)),
    })),
    pods: state.pods.map((p) => ({
      x: Number(p.x.toFixed(1)),
      y: Number(p.y.toFixed(1)),
      r: p.r,
      life: Number(p.life.toFixed(2)),
    })),
    slowFields: state.slowFields.map((f) => ({
      x: Number(f.x.toFixed(1)),
      y: Number(f.y.toFixed(1)),
      r: f.r,
      life: Number(f.life.toFixed(2)),
    })),
    riskZones: state.riskZones.map((z) => ({
      x: Number(z.x.toFixed(1)),
      y: Number(z.y.toFixed(1)),
      r: z.r,
      life: Number(z.life.toFixed(2)),
    })),
    objective: state.objective
      ? {
          type: state.objective.type,
          timer: Number(state.objective.timer.toFixed(2)),
          target: state.objective.target,
          progress: state.objective.progress,
          reward: state.objective.reward,
        }
      : null,
  };
  return JSON.stringify(payload);
};

resetGame();
setMode("menu");
resizeCanvas();
requestAnimationFrame(tick);
