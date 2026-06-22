const crypto = require("crypto");
const { BlobError, get, list, put } = require("@vercel/blob");

const MAX_PLAYERS = 9;
const MIN_THINKING_TIME_MS = 7000;
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
  contribute_community_pot: { food: -8, savings: -5, hope: 6, stability: 7, reputation: 10 },
  hoard_relief: { food: 18, savings: 8, hope: -5, reputation: -14 },
  undercut_wages: { savings: 19, stability: -12, hope: -8, reputation: -12 },
  inform_on_black_market: { savings: 16, stability: 8, hope: -10, reputation: -16 },
};

const ACTION_DYNAMICS = {
  keep_factory_job: ["work"],
  search_any_work: ["work"],
  apply_public_works: ["work", "relief"],
  stay_public_works: ["work"],
  seek_defense_work: ["work"],
  take_desperate_work: ["work"],
  older_child_fulltime: ["work"],
  accept_relief: ["relief"],
  seek_charity_clinic: ["relief"],
  join_mutual_aid: ["cooperate"],
  organize_neighbors: ["cooperate"],
  support_union: ["cooperate"],
  sponsor_neighbor: ["cooperate"],
  contribute_community_pot: ["cooperate"],
  hoard_relief: ["relief", "betray"],
  undercut_wages: ["work", "betray"],
  inform_on_black_market: ["betray"],
};

const PHASE_PRESSURE = {
  postwar: { work: 0.7, relief: 0.2, need: 0.55 },
  recession_1921: { work: 0.45, relief: 0.25, need: 0.7 },
  early_boom: { work: 0.85, relief: 0.2, need: 0.45 },
  speculation: { work: 0.85, relief: 0.2, need: 0.45 },
  crash: { work: 0.35, relief: 0.25, need: 0.85 },
  deepening: { work: 0.3, relief: 0.35, need: 1 },
  bank_holiday: { work: 0.45, relief: 0.55, need: 0.85 },
  work_relief: { work: 0.65, relief: 0.6, need: 0.65 },
  second: { work: 0.5, relief: 0.45, need: 0.75 },
  defense_shift: { work: 0.75, relief: 0.35, need: 0.5 },
  recovery: { work: 0.9, relief: 0.3, need: 0.35 },
};

const STARTING_FAMILIES = [
  { name: "Carter", profile: "Cleveland factory household", role: "Industrial wage earners", objectiveId: "industrial_stability", objectiveTitle: "Hold the household together", objectiveDetail: "Finish with Stability 60+ while keeping trust at 45+.", food: 55, health: 62, savings: 28, debt: 42, hope: 58, education: 64, stability: 54, bankTrust: 55, stock: 0 },
  { name: "Rosen", profile: "Small shop owners", role: "Main Street merchants", objectiveId: "shopkeeper_debt", objectiveTitle: "Keep the shop solvent", objectiveDetail: "Finish with Debt 45 or lower and Hope 45+.", food: 60, health: 58, savings: 44, debt: 48, hope: 62, education: 68, stability: 48, bankTrust: 62, stock: 0 },
  { name: "Williams", profile: "Tenant farm family", role: "Rural tenant farmers", objectiveId: "tenant_food", objectiveTitle: "Keep food on the table", objectiveDetail: "Finish with Food 50+ or successfully use a migration/work-camp path.", food: 48, health: 55, savings: 18, debt: 55, hope: 52, education: 50, stability: 42, bankTrust: 45, stock: 0 },
  { name: "Novak", profile: "Recent immigrant industrial household", role: "New arrival workers", objectiveId: "immigrant_trust", objectiveTitle: "Build standing", objectiveDetail: "Finish with Trust 65+ or Education 60+.", food: 52, health: 59, savings: 22, debt: 38, hope: 56, education: 58, stability: 45, bankTrust: 50, stock: 0 },
  { name: "O'Connor", profile: "Railroad worker household", role: "Rail and transport workers", objectiveId: "railroad_mobility", objectiveTitle: "Keep moving, stay healthy", objectiveDetail: "Use at least 2 work or mobility actions and finish with Health 45+.", food: 57, health: 60, savings: 24, debt: 36, hope: 57, education: 61, stability: 52, bankTrust: 54, stock: 0 },
  { name: "Bianchi", profile: "Garment district family", role: "Urban garment workers", objectiveId: "garment_solidarity", objectiveTitle: "Stand with the neighborhood", objectiveDetail: "Use at least 2 community/labor actions and finish with Hope 55+.", food: 54, health: 57, savings: 30, debt: 44, hope: 60, education: 63, stability: 47, bankTrust: 52, stock: 0 },
  { name: "Johnson", profile: "Black urban service family", role: "Urban service workers", objectiveId: "service_respect", objectiveTitle: "Earn respect under pressure", objectiveDetail: "Finish with Stability 50+ and Trust 60+.", food: 50, health: 56, savings: 16, debt: 46, hope: 55, education: 59, stability: 40, bankTrust: 42, stock: 0 },
  { name: "Kowalski", profile: "Coal town mining family", role: "Mining household", objectiveId: "miner_health", objectiveTitle: "Survive dangerous work", objectiveDetail: "Finish with Health 45+ and Debt 55 or lower.", food: 53, health: 51, savings: 20, debt: 50, hope: 50, education: 52, stability: 43, bankTrust: 47, stock: 0 },
  { name: "Martinez", profile: "Seasonal farm labor family", role: "Migrant farm workers", objectiveId: "seasonal_work", objectiveTitle: "Find enough work", objectiveDetail: "Finish with Food 45+ and use at least 2 work or relief actions.", food: 46, health: 54, savings: 14, debt: 40, hope: 54, education: 48, stability: 38, bankTrust: 43, stock: 0 },
];

const blobToken = process.env.BLOB_READ_WRITE_TOKEN;
const BLOB_OPTIONS = blobToken ? { access: "private", token: blobToken } : { access: "private" };
const memoryStore = globalThis.__gdGameMemoryStore || new Map();
globalThis.__gdGameMemoryStore = memoryStore;
globalThis.__gdGameBlobUnavailable = globalThis.__gdGameBlobUnavailable || false;
const DEFAULT_JSONBLOB_STORE_ID = "019ee11f-8caa-7a8e-8546-8e68b1c29c74";
const JSONBLOB_STORE_IDS = [...new Set([process.env.JSONBLOB_STORE_ID, DEFAULT_JSONBLOB_STORE_ID].filter(Boolean))];

function clamp(value) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function clampReputation(value) {
  return Math.max(-30, Math.min(100, Math.round(value)));
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
  const phaseId = PHASE_IDS[Math.min(room.phase_index, PHASE_IDS.length - 1)];
  return {
    roomCode: room.room_code,
    phaseIndex: room.phase_index,
    players: room.players || [],
    shared: sharedSnapshot(room, phaseId),
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
    reputation: 50,
    exploitMarkers: 0,
  });
  ["food", "health", "savings", "hope", "education", "stability", "bankTrust"].forEach((key) => {
    family[key] = clamp(family[key] + crypto.randomInt(17) - 8);
  });
  family.debt = Math.max(0, Math.round(family.debt + crypto.randomInt(21) - 10));
  family.initialHardship = Math.round(100 - (family.food + family.health + family.savings + family.hope + family.education + family.stability) / 6 + family.debt * 0.25);
  return family;
}

function applyChoices(family, choices, phaseId, options = {}) {
  const next = { ...family, choices: { ...(family.choices || {}) } };
  const multiplier = positiveImpactMultiplier(family, options.rushed);
  choices.forEach((choice) => {
    Object.entries(IMPACTS[choice] || {}).forEach(([key, value]) => {
      const impact = scaledImpact(key, value, multiplier);
      const current = next[key] || 0;
      if (key === "debt" || key === "stock") next[key] = Math.max(0, current + impact);
      else if (key === "reputation") next[key] = clampReputation((next[key] ?? 50) + impact);
      else next[key] = clamp(current + impact);
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
  next.minSavings = Math.min(next.minSavings ?? next.savings, next.savings);
  next.rushedChoiceCount = (next.rushedChoiceCount || 0) + (options.rushed ? 1 : 0);
  next.lastChoiceRushed = Boolean(options.rushed);
  next.lastChoiceMultiplier = multiplier;
  return next;
}

function phaseCapacity(phaseId, playerCount) {
  const pressure = PHASE_PRESSURE[phaseId] || PHASE_PRESSURE.postwar;
  return {
    workSlots: Math.max(1, Math.round(playerCount * pressure.work)),
    reliefSlots: Math.max(1, Math.round(playerCount * pressure.relief)),
    communityNeed: Math.max(2, Math.ceil(playerCount * pressure.need)),
  };
}

function choiceHasTag(choices, tag) {
  return choices.some((choice) => (ACTION_DYNAMICS[choice] || []).includes(tag));
}

function applySharedImpact(family, impact) {
  const next = { ...family };
  Object.entries(impact).forEach(([key, value]) => {
    const current = key === "reputation" ? next[key] ?? 50 : next[key] || 0;
    if (key === "debt" || key === "stock" || key === "exploitMarkers") next[key] = Math.max(0, current + value);
    else if (key === "reputation") next[key] = clampReputation(current + value);
    else next[key] = clamp(current + value);
  });
  next.minFood = Math.min(next.minFood ?? next.food, next.food);
  next.minHealth = Math.min(next.minHealth ?? next.health, next.health);
  next.minHope = Math.min(next.minHope ?? next.hope, next.hope);
  next.minEducation = Math.min(next.minEducation ?? next.education, next.education);
  next.minStability = Math.min(next.minStability ?? next.stability, next.stability);
  next.minSavings = Math.min(next.minSavings ?? next.savings, next.savings);
  return next;
}

function resolveScarcity(contenders, slots) {
  return [...contenders]
    .sort((a, b) => (b.player.reputation ?? 50) - (a.player.reputation ?? 50) || a.player.slot - b.player.slot)
    .slice(0, slots)
    .reduce((winners, item) => winners.add(item.player.id), new Set());
}

function sharedSnapshot(room, phaseId) {
  const playerCount = Math.max(1, (room.players || []).length);
  return {
    trust: room.shared?.trust ?? 55,
    communityPot: room.shared?.communityPot ?? 3,
    lastRound: room.shared?.lastRound || "No shared decision has resolved yet.",
    ...phaseCapacity(phaseId, playerCount),
  };
}

function resolveSharedRound(room, phaseId) {
  room.resolved_phases = room.resolved_phases || {};
  if (room.resolved_phases[phaseId]) return;

  const capacity = phaseCapacity(phaseId, room.players.length);
  const round = room.players.map((player) => ({
    player,
    choices: player.choices?.[phaseId] || [],
  }));
  const work = round.filter((entry) => choiceHasTag(entry.choices, "work"));
  const relief = round.filter((entry) => choiceHasTag(entry.choices, "relief"));
  const cooperate = round.filter((entry) => choiceHasTag(entry.choices, "cooperate"));
  const betray = round.filter((entry) => choiceHasTag(entry.choices, "betray"));
  const workWinners = resolveScarcity(work, capacity.workSlots);
  const reliefWinners = resolveScarcity(relief, capacity.reliefSlots);
  const communityPot = Math.max(0, (room.shared?.communityPot ?? 3) + cooperate.length * 2 - betray.length);
  const potMetNeed = communityPot >= capacity.communityNeed;

  room.players = room.players.map((player) => {
    const choices = player.choices?.[phaseId] || [];
    let next = player;
    if (choiceHasTag(choices, "work") && !workWinners.has(player.id)) next = applySharedImpact(next, { savings: -8, hope: -5 });
    if (choiceHasTag(choices, "relief") && !reliefWinners.has(player.id)) next = applySharedImpact(next, { food: -7, hope: -4 });
    if (choiceHasTag(choices, "cooperate")) next = applySharedImpact(next, { reputation: 5 });
    if (choiceHasTag(choices, "betray")) next = applySharedImpact(next, { reputation: -8, exploitMarkers: 1 });
    next = applySharedImpact(next, potMetNeed ? { food: 4, hope: 5, stability: 3 } : { hope: -5, stability: -4 });
    return next;
  });

  const trustDelta = cooperate.length * 4 - betray.length * 9 + (potMetNeed ? 4 : -5) - Math.max(0, work.length - capacity.workSlots) * 2;
  room.shared = {
    trust: clamp((room.shared?.trust ?? 55) + trustDelta),
    communityPot: Math.max(0, communityPot - capacity.communityNeed),
    lastRound: `${cooperate.length} helped the community, ${betray.length} took a selfish edge. ${
      potMetNeed ? "The community pot held." : "The pot fell short."
    }`,
    last: {
      phaseId,
      cooperate: cooperate.length,
      betray: betray.length,
      workDemand: work.length,
      reliefDemand: relief.length,
      workSlots: capacity.workSlots,
      reliefSlots: capacity.reliefSlots,
      potMetNeed,
    },
  };
  room.resolved_phases[phaseId] = true;
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

function roomPath(code) {
  return `game-rooms/${code}/room.json`;
}

function playerPath(code, slot) {
  return `game-rooms/${code}/players/slot-${slot}.json`;
}

function choicePath(code, slot, phaseId) {
  return `game-rooms/${code}/choices/slot-${slot}-${phaseId}.json`;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function shouldUseMemoryStore(error) {
  const message = String(error?.message || error || "");
  return /blob: this store has been suspended|no token|unauthorized|forbidden/i.test(message);
}

function readMemoryJson(path) {
  const value = memoryStore.get(path);
  return value ? JSON.parse(value) : null;
}

function writeMemoryJson(path, payload, allowOverwrite = true) {
  if (!allowOverwrite && memoryStore.has(path)) throw new Error("already exists");
  memoryStore.set(path, JSON.stringify(payload));
}

async function readJsonBlobStore() {
  let lastStatus = "";
  for (const id of JSONBLOB_STORE_IDS) {
    const response = await fetch(`https://jsonblob.com/api/jsonBlob/${id}`, { cache: "no-store" });
    if (response.ok) return { id, store: await response.json() };
    lastStatus = `${id}:${response.status}`;
  }
  throw new Error(`JSONBlob read failed (${lastStatus || "not configured"})`);
}

async function writeJsonBlobStore(id, store) {
  const response = await fetch(`https://jsonblob.com/api/jsonBlob/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(store),
  });
  if (!response.ok) throw new Error(`JSONBlob write failed (${response.status})`);
}

async function readFallbackJson(path) {
  if (!JSONBLOB_STORE_IDS.length) return readMemoryJson(path);
  const { store } = await readJsonBlobStore();
  const value = store[path];
  return value ? JSON.parse(value) : null;
}

async function writeFallbackJson(path, payload, allowOverwrite = true) {
  if (!JSONBLOB_STORE_IDS.length) {
    writeMemoryJson(path, payload, allowOverwrite);
    return;
  }
  const { id, store } = await readJsonBlobStore();
  if (!allowOverwrite && store[path]) throw new Error("already exists");
  store[path] = JSON.stringify(payload);
  await writeJsonBlobStore(id, store);
}

async function listFallbackPaths(prefix, limit) {
  if (!JSONBLOB_STORE_IDS.length) return [...memoryStore.keys()].filter((path) => path.startsWith(prefix)).slice(0, limit);
  const { store } = await readJsonBlobStore();
  return Object.keys(store).filter((path) => path.startsWith(prefix)).slice(0, limit);
}

async function listStoredPaths(prefix, limit) {
  if (!globalThis.__gdGameBlobUnavailable) {
    try {
      const result = await list({ ...BLOB_OPTIONS, prefix, limit });
      return result.blobs.map((blob) => blob.pathname);
    } catch (error) {
      if (!shouldUseMemoryStore(error)) throw error;
      globalThis.__gdGameBlobUnavailable = true;
    }
  }
  return listFallbackPaths(prefix, limit);
}

async function readJson(path) {
  if (globalThis.__gdGameBlobUnavailable) return readFallbackJson(path);
  try {
    const blob = await get(path, BLOB_OPTIONS);
    if (!blob || blob.statusCode !== 200 || !blob.stream) return null;
    const reader = blob.stream.getReader();
    const chunks = [];
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(Buffer.from(value));
    }
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch (error) {
    if (shouldUseMemoryStore(error)) {
      globalThis.__gdGameBlobUnavailable = true;
      return readFallbackJson(path);
    }
    if (error instanceof BlobError || /not found/i.test(String(error.message || ""))) return null;
    throw error;
  }
}

async function writeJson(path, payload, allowOverwrite = true) {
  if (globalThis.__gdGameBlobUnavailable) {
    await writeFallbackJson(path, payload, allowOverwrite);
    return;
  }
  try {
    await put(path, JSON.stringify(payload), {
      ...BLOB_OPTIONS,
      addRandomSuffix: false,
      allowOverwrite,
      contentType: "application/json; charset=utf-8",
    });
  } catch (error) {
    if (!shouldUseMemoryStore(error)) throw error;
    globalThis.__gdGameBlobUnavailable = true;
    await writeFallbackJson(path, payload, allowOverwrite);
  }
}

async function listPlayers(code) {
  const prefix = `game-rooms/${code}/players/`;
  const paths = await listStoredPaths(prefix, MAX_PLAYERS + 5);
  const players = await Promise.all(
    paths
      .filter((path) => /slot-\d+\.json$/.test(path))
      .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
      .slice(0, MAX_PLAYERS)
      .map((path) => readJson(path))
  );
  const visiblePlayers = players.filter(Boolean);
  const choices = await listChoiceMarkers(code);
  choices.forEach(({ slot, phaseId, choices: selectedChoices, rushed }) => {
    const playerIndex = visiblePlayers.findIndex((player) => player.slot === slot);
    if (playerIndex < 0) return;
    const player = visiblePlayers[playerIndex];
    if ((player.choices?.[phaseId] || []).length === 2) return;
    const updated = applyChoices(player, selectedChoices, phaseId, { rushed });
    updated.choices = { ...(player.choices || {}), [phaseId]: selectedChoices };
    visiblePlayers[playerIndex] = updated;
  });
  return visiblePlayers;
}

async function listChoiceMarkers(code) {
  const prefix = `game-rooms/${code}/choices/`;
  const paths = await listStoredPaths(prefix, MAX_PLAYERS * PHASE_IDS.length + 10);
  const markers = await Promise.all(
    paths
      .filter((path) => /slot-\d+-[^/]+\.json$/.test(path))
      .map(async (path) => {
        const match = path.match(/slot-(\d+)-([^.]+)\.json$/);
        const payload = await readJson(path);
        if (!match || !payload) return null;
        return { slot: Number(match[1]), phaseId: match[2], choices: payload.choices || [], rushed: Boolean(payload.rushed) };
      })
  );
  return markers.filter(Boolean);
}

async function readRoom(code) {
  const room = await readJson(roomPath(code));
  if (!room) return null;
  room.players = await listPlayers(code);
  return room;
}

async function saveRoom(room) {
  const roomPayload = { ...room };
  delete roomPayload.players;
  await writeJson(roomPath(room.room_code), roomPayload);
}

async function createRoom() {
  for (let i = 0; i < 12; i += 1) {
    const code = roomCode();
    const now = new Date().toISOString();
    const room = {
      room_code: code,
      host_token: crypto.randomBytes(32).toString("base64url"),
      phase_index: 0,
      created_at: now,
      phase_started_at: now,
      shared: { trust: 55, communityPot: 3, lastRound: "No shared decision has resolved yet." },
      resolved_phases: {},
      updated_at: now,
    };
    try {
      await writeJson(roomPath(code), room, false);
      room.players = [];
      return room;
    } catch (error) {
      if (!/already exists|overwrite/i.test(String(error.message || ""))) throw error;
    }
  }
  return null;
}

async function addPlayer(code, playerName, clientId) {
  const players = await listPlayers(code);
  const existing = players.find((player) => player.clientId === clientId);
  if (existing) return existing;
  if (players.length >= MAX_PLAYERS) return null;

  for (let slot = 0; slot < MAX_PLAYERS; slot += 1) {
    if (players.some((player) => player.slot === slot)) continue;
    const player = { ...pickFamily(playerName, slot, clientId), slot };
    try {
      await writeJson(playerPath(code, slot), player, false);
      return player;
    } catch (error) {
      if (!/already exists|overwrite/i.test(String(error.message || ""))) throw error;
    }
  }
  return null;
}

async function savePlayer(code, player) {
  await writeJson(playerPath(code, player.slot), player);
}

async function handleGameRequest(req, res) {
  const rawParts = Array.isArray(req.query.path) ? req.query.path : [req.query.path].filter(Boolean);
  const urlParts = (req.url || "")
    .split("?")[0]
    .split("/")
    .filter(Boolean)
    .filter((part) => part !== "api");
  const routeParts = rawParts.length ? rawParts : urlParts;
  const parts = routeParts[0] === "game" ? routeParts.slice(1) : routeParts;
  if (parts[0] !== "rooms") return json(res, 404, { detail: "Not found" });

  if (req.method === "POST" && parts.length === 1) {
    const room = await createRoom();
    if (!room) return json(res, 500, { detail: "Could not create a unique room code" });
    return json(res, 200, { room: publicRoom(room), hostToken: room.host_token });
  }

  const code = String(parts[1] || "").trim().toUpperCase();
  const room = await readRoom(code);
  if (!room) return json(res, 404, { detail: "Room not found" });

  if (req.method === "GET" && parts.length === 2) return json(res, 200, { room: publicRoom(room) });

  const body = getBody(req);
  if (req.method === "POST" && parts[2] === "join") {
    const clientId = body.client_id || crypto.randomUUID();
    const player = await addPlayer(code, String(body.player_name || "Player").trim() || "Player", clientId);
    if (!player) return json(res, 409, { detail: `Room is full (${MAX_PLAYERS} players max).` });
    room.updated_at = new Date().toISOString();
    await saveRoom(room);
    room.players = await listPlayers(code);
    return json(res, 200, { room: publicRoom(room), playerId: player.id });
  }

  if (req.method === "POST" && parts[2] === "choices") {
    const phaseId = PHASE_IDS[Math.min(room.phase_index, PHASE_IDS.length - 1)];
    const playerIndex = room.players.findIndex((player) => player.id === body.player_id);
    if (playerIndex < 0) return json(res, 404, { detail: "Player not found in this room" });
    if ((room.players[playerIndex].choices?.[phaseId] || []).length === 2) return json(res, 200, { room: publicRoom(room) });
    const phaseStartedAt = Date.parse(room.phase_started_at || room.updated_at || room.created_at || new Date().toISOString());
    const rushed = Date.now() - phaseStartedAt < MIN_THINKING_TIME_MS;
    try {
      await writeJson(choicePath(code, room.players[playerIndex].slot, phaseId), { choices: (body.choices || []).slice(0, 2), rushed }, false);
    } catch (error) {
      if (!/already exists|overwrite/i.test(String(error.message || ""))) throw error;
      room.players = await listPlayers(code);
      return json(res, 200, { room: publicRoom(room) });
    }
    const updatedPlayer = applyChoices(room.players[playerIndex], (body.choices || []).slice(0, 2), phaseId, { rushed });
    updatedPlayer.choices = { ...(room.players[playerIndex].choices || {}), [phaseId]: (body.choices || []).slice(0, 2) };
    await savePlayer(code, updatedPlayer);
    for (let attempt = 0; attempt < 4; attempt += 1) {
      room.players = await listPlayers(code);
      if (room.players.find((player) => player.id === body.player_id)?.choices?.[phaseId]?.length === 2) break;
      await delay(120);
    }
    if (room.players.length && room.players.every((player) => (player.choices?.[phaseId] || []).length === 2)) {
      resolveSharedRound(room, phaseId);
      await Promise.all(room.players.map((player) => savePlayer(code, player)));
      room.phase_index = Math.min(room.phase_index + 1, PHASE_IDS.length - 1);
      room.phase_started_at = new Date().toISOString();
    }
    room.updated_at = new Date().toISOString();
    await saveRoom(room);
    return json(res, 200, { room: publicRoom(room) });
  }

  if (req.method === "POST" && parts[2] === "advance") {
    if (!body.host_token || body.host_token !== room.host_token) return json(res, 403, { detail: "Only the host can advance this room." });
    room.phase_index = Math.min(room.phase_index + 1, PHASE_IDS.length - 1);
    room.phase_started_at = new Date().toISOString();
    room.updated_at = new Date().toISOString();
    await saveRoom(room);
    return json(res, 200, { room: publicRoom(room) });
  }

  return json(res, 404, { detail: "Not found" });
}

module.exports = async function handler(req, res) {
  try {
    return await handleGameRequest(req, res);
  } catch (error) {
    console.error(error);
    return json(res, 500, { detail: error.message || "The game room server did not respond." });
  }
};
