const crypto = require("crypto");

const MAX_PLAYERS = 9;
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
};

const STARTING_FAMILIES = [
  { name: "Carter", profile: "Cleveland factory family", food: 55, health: 62, savings: 28, debt: 42, hope: 58, education: 64, stability: 54, bankTrust: 55, stock: 0 },
  { name: "Rosen", profile: "Small shop owners", food: 60, health: 58, savings: 44, debt: 48, hope: 62, education: 68, stability: 48, bankTrust: 62, stock: 0 },
  { name: "Williams", profile: "Tenant farm family", food: 48, health: 55, savings: 18, debt: 55, hope: 52, education: 50, stability: 42, bankTrust: 45, stock: 0 },
  { name: "Novak", profile: "Immigrant household", food: 52, health: 59, savings: 22, debt: 38, hope: 56, education: 58, stability: 45, bankTrust: 50, stock: 0 },
];

const state = globalThis.__greatDepressionRooms || { rooms: new Map() };
globalThis.__greatDepressionRooms = state;

function clamp(value) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function json(res, status, payload) {
  res.statusCode = status;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.setHeader("cache-control", "no-store");
  res.end(JSON.stringify(payload));
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
    players: room.players,
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
  });
  ["food", "health", "savings", "hope", "education", "stability", "bankTrust"].forEach((key) => {
    family[key] = clamp(family[key] + crypto.randomInt(17) - 8);
  });
  family.debt = Math.max(0, Math.round(family.debt + crypto.randomInt(21) - 10));
  return family;
}

function applyChoices(family, choices, phaseId) {
  const next = { ...family, choices: { ...(family.choices || {}) } };
  choices.forEach((choice) => {
    Object.entries(IMPACTS[choice] || {}).forEach(([key, value]) => {
      const current = next[key] || 0;
      next[key] = key === "debt" || key === "stock" ? Math.max(0, current + value) : clamp(current + value);
    });
  });
  if (phaseId === "crash" && next.stock > 0) {
    next.savings = clamp(next.savings - Math.ceil(next.stock * 0.55));
    next.hope = clamp(next.hope - 8);
    next.stock = Math.max(0, Math.floor(next.stock * 0.25));
  }
  next.debt = Math.max(0, Math.round(next.debt || 0));
  next.minFood = Math.min(next.minFood ?? next.food, next.food);
  next.minHealth = Math.min(next.minHealth ?? next.health, next.health);
  next.minHope = Math.min(next.minHope ?? next.hope, next.hope);
  next.minEducation = Math.min(next.minEducation ?? next.education, next.education);
  next.minStability = Math.min(next.minStability ?? next.stability, next.stability);
  return next;
}

function getBody(req) {
  if (!req.body) return {};
  if (typeof req.body === "string") {
    try {
      return JSON.parse(req.body || "{}");
    } catch {
      return {};
    }
  }
  return req.body;
}

module.exports = function handler(req, res) {
  const parts = Array.isArray(req.query.path) ? req.query.path : [req.query.path].filter(Boolean);
  if (parts[0] !== "rooms") return json(res, 404, { detail: "Not found" });

  if (req.method === "POST" && parts.length === 1) {
    let code = roomCode();
    for (let i = 0; i < 12 && state.rooms.has(code); i += 1) code = roomCode();
    if (state.rooms.has(code)) return json(res, 500, { detail: "Could not create a unique room code" });
    const now = new Date().toISOString();
    const room = {
      room_code: code,
      host_token: crypto.randomBytes(32).toString("base64url"),
      phase_index: 0,
      players: [],
      created_at: now,
      updated_at: now,
    };
    state.rooms.set(code, room);
    return json(res, 200, { room: publicRoom(room), hostToken: room.host_token });
  }

  const code = String(parts[1] || "").trim().toUpperCase();
  const room = state.rooms.get(code);
  if (!room) return json(res, 404, { detail: "Room not found" });

  if (req.method === "GET" && parts.length === 2) return json(res, 200, { room: publicRoom(room) });

  const body = getBody(req);
  if (req.method === "POST" && parts[2] === "join") {
    const clientId = body.client_id || crypto.randomUUID();
    const existing = room.players.find((player) => player.clientId === clientId);
    if (existing) return json(res, 200, { room: publicRoom(room), playerId: existing.id });
    if (room.players.length >= MAX_PLAYERS) return json(res, 409, { detail: `Room is full (${MAX_PLAYERS} players max).` });
    const player = pickFamily(String(body.player_name || "Player").trim() || "Player", room.players.length, clientId);
    room.players.push(player);
    room.updated_at = new Date().toISOString();
    return json(res, 200, { room: publicRoom(room), playerId: player.id });
  }

  if (req.method === "POST" && parts[2] === "choices") {
    const phaseId = PHASE_IDS[Math.min(room.phase_index, PHASE_IDS.length - 1)];
    const playerIndex = room.players.findIndex((player) => player.id === body.player_id);
    if (playerIndex < 0) return json(res, 404, { detail: "Player not found in this room" });
    if ((room.players[playerIndex].choices?.[phaseId] || []).length === 2) return json(res, 200, { room: publicRoom(room) });
    const updatedPlayer = applyChoices(room.players[playerIndex], (body.choices || []).slice(0, 2), phaseId);
    updatedPlayer.choices = { ...(room.players[playerIndex].choices || {}), [phaseId]: (body.choices || []).slice(0, 2) };
    room.players[playerIndex] = updatedPlayer;
    if (room.players.length && room.players.every((player) => (player.choices?.[phaseId] || []).length === 2)) {
      room.phase_index = Math.min(room.phase_index + 1, PHASE_IDS.length - 1);
    }
    room.updated_at = new Date().toISOString();
    return json(res, 200, { room: publicRoom(room) });
  }

  if (req.method === "POST" && parts[2] === "advance") {
    if (!body.host_token || body.host_token !== room.host_token) return json(res, 403, { detail: "Only the host can advance this room." });
    room.phase_index = Math.min(room.phase_index + 1, PHASE_IDS.length - 1);
    room.updated_at = new Date().toISOString();
    return json(res, 200, { room: publicRoom(room) });
  }

  return json(res, 404, { detail: "Not found" });
};
