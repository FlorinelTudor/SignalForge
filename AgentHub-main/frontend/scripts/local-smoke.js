const DEFAULT_BASE_URL = "http://127.0.0.1:4173/api/game";
const MAX_PLAYERS = 9;

const phaseChoices = [
  ["keep_factory_job", "contribute_community_pot"],
  ["use_savings_food", "hoard_relief"],
  ["buy_radio_credit", "pay_down_debt"],
  ["invest_stocks", "undercut_wages"],
  ["sell_stocks_now", "withdraw_bank_cash"],
  ["cut_food_rent", "hoard_relief"],
  ["apply_public_works", "contribute_community_pot"],
  ["stay_public_works", "hoard_relief"],
  ["stay_public_works", "undercut_wages"],
  ["seek_defense_work", "inform_on_black_market"],
];

function getBaseUrl() {
  const baseUrl = process.env.GAME_API_URL || DEFAULT_BASE_URL;
  const parsed = new URL(baseUrl);
  const isLocal =
    parsed.hostname === "localhost" ||
    parsed.hostname === "127.0.0.1" ||
    parsed.hostname === "::1";

  if (!isLocal && process.env.ALLOW_PUBLIC_SMOKE !== "1") {
    throw new Error(
      `Refusing to run quota-heavy smoke test against ${baseUrl}. ` +
        "Use localhost, or set ALLOW_PUBLIC_SMOKE=1 intentionally."
    );
  }

  return baseUrl.replace(/\/$/, "");
}

async function request(baseUrl, path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { "content-type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw new Error(`${options.method || "GET"} ${path} returned ${response.status}: ${text.slice(0, 240)}`);
  }

  return payload;
}

async function main() {
  const baseUrl = getBaseUrl();
  const created = await request(baseUrl, "/rooms", { method: "POST", body: JSON.stringify({}) });
  const roomCode = created.room.roomCode;
  const stamp = Date.now();

  await Promise.all(
    Array.from({ length: MAX_PLAYERS }, (_, index) =>
      request(baseUrl, `/rooms/${roomCode}/join`, {
        method: "POST",
        body: JSON.stringify({
          player_name: `Local Player ${index + 1}`,
          client_id: `local-smoke-${stamp}-${index}`,
        }),
      })
    )
  );

  let state = await request(baseUrl, `/rooms/${roomCode}`);
  const families = state.room.players.map((player) => player.name);
  if (state.room.players.length !== MAX_PLAYERS) {
    throw new Error(`Expected ${MAX_PLAYERS} players, got ${state.room.players.length}`);
  }
  if (new Set(families).size !== MAX_PLAYERS) {
    throw new Error(`Expected unique family names, got: ${families.join(", ")}`);
  }
  if (state.room.players.some((player) => !player.role || !player.objectiveId || !player.objectiveTitle)) {
    throw new Error("Expected every player to receive a period role and family objective");
  }

  for (let round = 0; round < phaseChoices.length; round += 1) {
    const choices = phaseChoices[round];
    await Promise.all(
      state.room.players.map((player) =>
        request(baseUrl, `/rooms/${roomCode}/choices`, {
          method: "POST",
          body: JSON.stringify({ player_id: player.id, choices }),
        })
      )
    );
    state = await request(baseUrl, `/rooms/${roomCode}`);
    const expectedPhase = round + 1;
    if (state.room.phaseIndex !== expectedPhase) {
      throw new Error(`Expected phase ${expectedPhase}, got ${state.room.phaseIndex}`);
    }
    if (!state.room.shared || typeof state.room.shared.trust !== "number") {
      throw new Error("Expected shared community state after choices resolved");
    }
  }

  console.log(`Local smoke passed: room ${roomCode}, ${MAX_PLAYERS} players, final phase ${state.room.phaseIndex}.`);
  console.log(`Families: ${families.join(", ")}`);
}

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
