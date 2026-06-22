const crypto = require("crypto");
const express = require("express");
const path = require("path");

const MAX_PLAYERS = 9;
const MIN_THINKING_TIME_MS = 7000;
const PORT = Number(process.env.PORT || 4173);
const PHASE_IDS = [
  "postwar",
  "recession_1921",
  "early_boom",
  "speculation",
  "crash",
  "deepening",
  "bank_holiday",
  "work_relief",
  "second",
  "defense_shift",
  "recovery",
];

const IMPACTS = {
  keep_factory_job: { food: 6, savings: 9, hope: -5, stability: 16 },
  use_savings_food: { food: 18, health: 9, savings: -17 },
  move_to_city: { savings: -10, hope: 7, stability: -9 },
  take_store_credit: { food: 8, debt: 17, hope: 5 },
  pull_child_school: { savings: 13, education: -24, hope: -14 },
  join_mutual_aid: { hope: 12, stability: 11, savings: -5 },
  build_emergency_fund: { savings: 16, hope: -4, stability: 11 },
  invest_stocks: { savings: 22, stock: 26, hope: 10, stability: -4 },
  borrow_to_invest: { savings: 28, stock: 38, debt: 24, hope: 12, stability: -12 },
  buy_radio_credit: { hope: 15, debt: 16, savings: -5 },
  pay_down_debt: { debt: -24, savings: -9, stability: 10 },
  night_school: { education: 17, savings: -9, hope: 4 },
  keep_cash: { savings: 13, stability: 8, hope: -3 },
  move_better_rental: { health: 13, hope: 10, debt: 9 },
  sell_stocks_now: { savings: -14, stock: -28, stability: 10 },
  withdraw_bank_cash: { savings: 9, bankTrust: -22, stability: 7 },
  cut_food_rent: { food: -20, health: -14, savings: 16, stability: -12 },
  search_any_work: { savings: 12, health: -8, hope: 5 },
  move_with_relatives: { debt: -10, stability: 9, hope: -16 },
  keep_children_school: { education: 18, savings: -13, hope: 6 },
  sell_possessions: { savings: 18, hope: -15, stability: -7 },
  apply_public_works: { food: 15, savings: 13, health: -5, hope: 16 },
  trust_reopened_bank: { bankTrust: 22, stability: 12 },
  accept_relief: { food: 19, health: 10, hope: -7 },
  move_for_work_camp: { savings: 14, education: 7, hope: -10 },
  organize_neighbors: { hope: 14, stability: 13, savings: -5 },
  delay_medical_care: { savings: 13, health: -22 },
  stay_public_works: { savings: 11, stability: 12 },
  seek_defense_work: { savings: 20, hope: 16, stability: -5 },
  rebuild_savings: { savings: 20, hope: 5, stability: 5 },
  repair_health: { health: 21, savings: -12 },
  support_union: { hope: 11, stability: -10, savings: 11 },
  older_child_fulltime: { savings: 16, education: -21, hope: -11 },
  seek_charity_clinic: { health: 24, savings: -12, hope: -8 },
  send_family_to_country: { health: 16, food: 12, stability: -16, hope: -5 },
  pawn_heirloom: { savings: 24, hope: -18, stability: -6 },
  take_desperate_work: { food: 16, savings: 14, health: -15, stability: -6 },
  sponsor_neighbor: { hope: 12, stability: 8, savings: -14 },
  fund_training: { education: 20, savings: -18, hope: 6 },
};

const STARTING_FAMILIES = [
  { name: "Carter", profile: "Cleveland factory family", food: 55, health: 62, savings: 28, debt: 42, hope: 58, education: 64, stability: 54, bankTrust: 55, stock: 0 },
  { name: "Rosen", profile: "Small shop owners", food: 60, health: 58, savings: 44, debt: 48, hope: 62, education: 68, stability: 48, bankTrust: 62, stock: 0 },
  { name: "Williams", profile: "Tenant farm family", food: 48, health: 55, savings: 18, debt: 55, hope: 52, education: 50, stability: 42, bankTrust: 45, stock: 0 },
  { name: "Novak", profile: "Immigrant household", food: 52, health: 59, savings: 22, debt: 38, hope: 56, education: 58, stability: 45, bankTrust: 50, stock: 0 },
  { name: "O'Connor", profile: "Railroad worker household", food: 57, health: 60, savings: 24, debt: 36, hope: 57, education: 61, stability: 52, bankTrust: 54, stock: 0 },
  { name: "Bianchi", profile: "Garment district family", food: 54, health: 57, savings: 30, debt: 44, hope: 60, education: 63, stability: 47, bankTrust: 52, stock: 0 },
  { name: "Johnson", profile: "Black urban service family", food: 50, health: 56, savings: 16, debt: 46, hope: 55, education: 59, stability: 40, bankTrust: 42, stock: 0 },
  { name: "Kowalski", profile: "Coal town mining family", food: 53, health: 51, savings: 20, debt: 50, hope: 50, education: 52, stability: 43, bankTrust: 47, stock: 0 },
  { name: "Martinez", profile: "Seasonal farm labor family", food: 46, health: 54, savings: 14, debt: 40, hope: 54, education: 48, stability: 38, bankTrust: 43, stock: 0 },
];

const rooms = new Map();

function clamp(value) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function positiveImpactMultiplier(family, rushed) {
  if (!rushed) return 1;
  return Math.max(0.55, 0.85 - (family.rushedChoiceCount || 0) * 0.1);
}

function scaledImpact(key, value, multiplier) {
  if (multiplier >= 1) return value;
  if (key === "debt" && value < 0) return Math.round(value * multiplier);
  if (key !== "debt" && value > 0) return Math.round(value * multiplier);
  return value;
}

function roomCode() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let code = "";
  for (let i = 0; i < 4; i += 1) code += alphabet[crypto.randomInt(alphabet.length)];
  return code;
}

function publicRoom(room) {
  return {
    roomCode: room.room_code,
    phaseIndex: room.phase_index,
    players: room.players || [],
    updatedAt: room.updated_at,
  };
}

function pickFamily(playerName, index, clientId) {
  const family = { ...STARTING_FAMILIES[index % STARTING_FAMILIES.length] };
  Object.assign(family, {
    id: crypto.randomUUID(),
    playerName,
    clientId: clientId || crypto.randomUUID(),
    choices: {},
    score: 0,
    slot: index,
  });
  ["food", "health", "savings", "hope", "education", "stability", "bankTrust"].forEach((key) => {
    family[key] = clamp(family[key] + crypto.randomInt(17) - 8);
  });
  family.debt = Math.max(0, Math.round(family.debt + crypto.randomInt(21) - 10));
  return family;
}

function applyChoices(family, choices, phaseId, options = {}) {
  const next = { ...family, choices: { ...(family.choices || {}) } };
  const multiplier = positiveImpactMultiplier(family, options.rushed);
  choices.forEach((choice) => {
    Object.entries(IMPACTS[choice] || {}).forEach(([key, value]) => {
      const impact = scaledImpact(key, value, multiplier);
      const current = next[key] || 0;
      next[key] = key === "debt" || key === "stock" ? Math.max(0, current + impact) : clamp(current + impact);
    });
  });
  if (phaseId === "crash" && next.stock > 0) {
    next.savings = clamp(next.savings - Math.ceil(next.stock * 0.55));
    next.hope = clamp(next.hope - 8);
    next.stock = Math.max(0, Math.floor(next.stock * 0.25));
  }
  next.minFood = Math.min(next.minFood ?? next.food, next.food);
  next.minHealth = Math.min(next.minHealth ?? next.health, next.health);
  next.minHope = Math.min(next.minHope ?? next.hope, next.hope);
  next.minEducation = Math.min(next.minEducation ?? next.education, next.education);
  next.minStability = Math.min(next.minStability ?? next.stability, next.stability);
  next.rushedChoiceCount = (next.rushedChoiceCount || 0) + (options.rushed ? 1 : 0);
  next.lastChoiceRushed = Boolean(options.rushed);
  next.lastChoiceMultiplier = multiplier;
  return next;
}

function getRoom(req, res) {
  const room = rooms.get(String(req.params.roomCode || "").trim().toUpperCase());
  if (!room) {
    res.status(404).json({ detail: "Room not found" });
    return null;
  }
  return room;
}

const app = express();
app.use(express.json());

app.post("/api/game/rooms", (_req, res) => {
  for (let i = 0; i < 12; i += 1) {
    const code = roomCode();
    if (rooms.has(code)) continue;
    const now = new Date().toISOString();
    const room = {
      room_code: code,
      host_token: crypto.randomBytes(32).toString("base64url"),
      phase_index: 0,
      players: [],
      created_at: now,
      phase_started_at: now,
      updated_at: now,
    };
    rooms.set(code, room);
    res.json({ room: publicRoom(room), hostToken: room.host_token });
    return;
  }
  res.status(500).json({ detail: "Could not create a unique room code" });
});

app.get("/api/game/rooms/:roomCode", (req, res) => {
  const room = getRoom(req, res);
  if (room) res.json({ room: publicRoom(room) });
});

app.post("/api/game/rooms/:roomCode/join", (req, res) => {
  const room = getRoom(req, res);
  if (!room) return;
  const clientId = req.body.client_id || crypto.randomUUID();
  const existing = room.players.find((player) => player.clientId === clientId);
  if (existing) {
    res.json({ room: publicRoom(room), playerId: existing.id });
    return;
  }
  if (room.players.length >= MAX_PLAYERS) {
    res.status(409).json({ detail: `Room is full (${MAX_PLAYERS} players max).` });
    return;
  }
  const player = pickFamily(String(req.body.player_name || "Player").trim() || "Player", room.players.length, clientId);
  room.players.push(player);
  room.updated_at = new Date().toISOString();
  res.json({ room: publicRoom(room), playerId: player.id });
});

app.post("/api/game/rooms/:roomCode/choices", (req, res) => {
  const room = getRoom(req, res);
  if (!room) return;
  const phaseId = PHASE_IDS[Math.min(room.phase_index, PHASE_IDS.length - 1)];
  const index = room.players.findIndex((player) => player.id === req.body.player_id);
  if (index < 0) {
    res.status(404).json({ detail: "Player not found in this room" });
    return;
  }
  if ((room.players[index].choices?.[phaseId] || []).length !== 2) {
    const choices = (req.body.choices || []).slice(0, 2);
    const phaseStartedAt = Date.parse(room.phase_started_at || room.updated_at || room.created_at || new Date().toISOString());
    const rushed = Date.now() - phaseStartedAt < MIN_THINKING_TIME_MS;
    const updated = applyChoices(room.players[index], choices, phaseId, { rushed });
    updated.choices = { ...(room.players[index].choices || {}), [phaseId]: choices };
    room.players[index] = updated;
    if (room.players.length && room.players.every((player) => (player.choices?.[phaseId] || []).length === 2)) {
      room.phase_index = Math.min(room.phase_index + 1, PHASE_IDS.length - 1);
      room.phase_started_at = new Date().toISOString();
    }
    room.updated_at = new Date().toISOString();
  }
  res.json({ room: publicRoom(room) });
});

app.post("/api/game/rooms/:roomCode/advance", (req, res) => {
  const room = getRoom(req, res);
  if (!room) return;
  if (!req.body.host_token || req.body.host_token !== room.host_token) {
    res.status(403).json({ detail: "Only the host can advance this room." });
    return;
  }
  room.phase_index = Math.min(room.phase_index + 1, PHASE_IDS.length - 1);
  room.phase_started_at = new Date().toISOString();
  room.updated_at = new Date().toISOString();
  res.json({ room: publicRoom(room) });
});

const buildDir = path.join(__dirname, "..", "build");
app.use(express.static(buildDir));
app.get("*", (_req, res) => res.sendFile(path.join(buildDir, "index.html")));

app.listen(PORT, "127.0.0.1", () => {
  console.log(`Playtest server listening on http://localhost:${PORT}`);
});
