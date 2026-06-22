import "@/App.css";
import { useEffect, useMemo, useRef, useState } from "react";

const asset = (name) => `${process.env.PUBLIC_URL || ""}/depression-game/${name}`;
const MAX_PLAYERS = 9;
const GAME_STATE_VERSION = "blob-multiplayer-v2";
const COOPERATIVE_CHOICES = new Set(["join_mutual_aid", "organize_neighbors", "support_union", "sponsor_neighbor", "contribute_community_pot"]);
const RISK_CHOICES = new Set(["invest_stocks", "borrow_to_invest", "move_to_city", "withdraw_bank_cash", "search_any_work", "move_for_work_camp", "seek_defense_work", "support_union", "take_desperate_work", "undercut_wages", "inform_on_black_market"]);
const WORK_OR_RELIEF_CHOICES = new Set(["keep_factory_job", "search_any_work", "apply_public_works", "stay_public_works", "seek_defense_work", "take_desperate_work", "older_child_fulltime", "accept_relief", "seek_charity_clinic", "hoard_relief"]);
const MOBILITY_CHOICES = new Set(["move_to_city", "move_with_relatives", "move_for_work_camp", "seek_defense_work"]);

const phases = [
  {
    id: "postwar",
    years: "1919-1920",
    title: "Coming Home to a Changed Economy",
    image: "postwar-market-conditions.png",
    newsImage: "news-postwar.png",
    news: "War orders end as prices swing",
    summary: "Factories lose wartime orders while families face high prices, uncertain hours, and a peacetime economy still finding its footing.",
    conditions: [["Jobs", "Unstable", "warn"], ["Prices", "Volatile", "warn"], ["Bank trust", "Steady", "good"], ["Credit", "Cautious", "neutral"]],
    choices: [
      ["keep_factory_job", "Keep factory job", "Accept shorter hours and protect stability."],
      ["use_savings_food", "Use savings for food", "Protect health, but reduce your cushion."],
      ["move_to_city", "Move closer to work", "Higher wage chance, higher rent."],
      ["take_store_credit", "Buy on store credit", "Preserve cash now, add debt later."],
      ["pull_child_school", "Older child works", "Raise income, harm education and morale."],
      ["join_mutual_aid", "Join mutual aid", "Build support, spend time and small dues."],
      ["contribute_community_pot", "Share supplies", "Help the community pot at a short-term cost."],
    ],
  },
  {
    id: "recession_1921",
    years: "1920-1921",
    title: "Short Recession and Hard Choices",
    image: "recession-1921-market.png",
    newsImage: "news-postwar.png",
    news: "Factory hours fall as buyers pull back",
    summary: "A sharp downturn cuts hours and demand. Families must decide whether to protect cash, health, schooling, or mobility.",
    conditions: [["Jobs", "Falling", "bad"], ["Prices", "Still high", "warn"], ["Credit", "Careful", "neutral"], ["Relief", "Mostly local", "warn"]],
    choices: [
      ["use_savings_food", "Use savings for food", "Protect health, but reduce your cushion."],
      ["take_store_credit", "Buy on store credit", "Preserve cash now, add debt later."],
      ["move_to_city", "Move closer to work", "Higher wage chance, higher rent."],
      ["pull_child_school", "Older child works", "Raise income, harm education and morale."],
      ["join_mutual_aid", "Join mutual aid", "Build support, spend time and small dues."],
      ["hoard_relief", "Take extra relief", "Gain food now, but damage trust if exposed."],
      ["keep_factory_job", "Stay with current employer", "Accept shorter hours and protect stability."],
    ],
  },
  {
    id: "early_boom",
    years: "1922-1924",
    title: "New Confidence",
    image: "roaring-twenties-market.png",
    newsImage: "news-boom.png",
    news: "Factories hum and credit expands",
    summary: "Work becomes steadier and modern goods feel newly reachable. Credit starts to look like a normal part of family progress.",
    conditions: [["Confidence", "High", "good"], ["Credit", "Easy", "good"], ["Wages", "Improving", "good"], ["Risk", "Easy to ignore", "warn"]],
    choices: [
      ["buy_radio_credit", "Buy a radio on credit", "Raise hope and status, add debt."],
      ["pay_down_debt", "Pay down debt", "Less exciting, more resilient."],
      ["night_school", "Night school", "Improve future job options, lose income now."],
      ["keep_cash", "Keep cash cushion", "A cautious choice in an optimistic time."],
      ["move_better_rental", "Move to better rental", "Improve health and morale, raise rent."],
      ["build_emergency_fund", "Build emergency fund", "Delay comfort, strengthen resilience."],
    ],
  },
  {
    id: "speculation",
    years: "1925-1928",
    title: "Easy Money and Big Promises",
    image: "speculation-market.png",
    newsImage: "news-boom.png",
    news: "Credit boom lifts Main Street",
    summary: "Stocks, installment plans, and confident headlines make the future feel expandable. Families choose how far to lean in.",
    conditions: [["Stocks", "Rising", "good"], ["Credit", "Very easy", "good"], ["Confidence", "Bright", "good"], ["Risk", "Hidden", "warn"]],
    choices: [
      ["invest_stocks", "Invest savings in stocks", "Join the boom and chase returns."],
      ["borrow_to_invest", "Borrow to invest", "Bigger upside, dangerous leverage."],
      ["buy_radio_credit", "Upgrade household goods", "Raise hope and status, add debt."],
      ["pay_down_debt", "Pay down debt", "Less exciting, more resilient."],
      ["keep_cash", "Keep cash cushion", "A cautious choice in an optimistic time."],
      ["night_school", "Invest in skills", "Improve future job options, lose income now."],
      ["undercut_wages", "Undercut wages", "Win scarce work by accepting less pay and lower trust."],
    ],
  },
  {
    id: "crash",
    years: "1929",
    title: "A Sudden Break",
    image: "crash-market-pressure.png",
    newsImage: "news-crash.png",
    news: "Market falls as bank fears spread",
    summary: "Stocks plunge and confidence turns quickly. Families with savings, debt, or stock exposure must decide what to protect first.",
    conditions: [["Stocks", "Falling", "bad"], ["Bank confidence", "Falling", "bad"], ["Credit", "Tight", "bad"], ["Jobs", "At risk", "warn"]],
    choices: [
      ["sell_stocks_now", "Sell remaining stocks", "Lock in losses, preserve some cash."],
      ["withdraw_bank_cash", "Withdraw bank cash", "Protect from bank failure, feed panic."],
      ["cut_food_rent", "Cut food and rent costs", "Reduce spending, hurt health and stability."],
      ["search_any_work", "Search for any work", "Chance of income, high stress."],
      ["move_with_relatives", "Move in with relatives", "Lower rent, lower independence and hope."],
      ["keep_children_school", "Keep children in school", "Protect future, sacrifice short-term income."],
    ],
  },
  {
    id: "deepening",
    years: "1930-1932",
    title: "Jobs Vanish and Banks Strain",
    image: "deepening-market.png",
    newsImage: "news-crash.png",
    news: "Job losses spread across towns",
    summary: "The shock becomes a long emergency. Local relief, family networks, and painful cuts become part of survival.",
    conditions: [["Unemployment", "Severe", "bad"], ["Bank confidence", "Low", "bad"], ["Food security", "Fragile", "bad"], ["Relief", "Local/private", "warn"]],
    choices: [
      ["cut_food_rent", "Cut food and rent costs", "Reduce spending, hurt health and stability."],
      ["search_any_work", "Search for any work", "Chance of income, high stress."],
      ["move_with_relatives", "Move in with relatives", "Lower rent, lower independence and hope."],
      ["keep_children_school", "Keep children in school", "Protect future, sacrifice short-term income."],
      ["sell_possessions", "Sell possessions", "Raise cash, lower hope and comfort."],
      ["join_mutual_aid", "Lean on mutual aid", "Build support, spend time and small dues."],
      ["hoard_relief", "Take extra relief", "Gain food now, but damage trust if exposed."],
    ],
  },
  {
    id: "bank_holiday",
    years: "1933",
    title: "Banks Reopen and Relief Begins",
    image: "new-deal-market-conditions.png",
    newsImage: "news-newdeal.png",
    news: "Banks reopen as work programs begin",
    summary: "Bank reforms and relief agencies change the options available to families, but trust has to be rebuilt.",
    conditions: [["Unemployment", "Severe", "bad"], ["Bank confidence", "Stabilizing", "good"], ["Credit", "Cautious", "neutral"], ["Relief", "Expanding", "good"]],
    choices: [
      ["apply_public_works", "Apply for public works", "Chance of wages, physically demanding."],
      ["trust_reopened_bank", "Return cash to reopened bank", "Rebuild safety, depends on trust."],
      ["accept_relief", "Accept relief support", "Protect food and health, lower pride."],
      ["move_for_work_camp", "Send eldest to work camp", "Income and skills, family separation."],
      ["organize_neighbors", "Organize neighbors", "Mutual aid and voice, takes time."],
      ["delay_medical_care", "Delay medical care", "Preserve cash, risk health later."],
      ["contribute_community_pot", "Share relief supplies", "Strengthen the community pot and your reputation."],
    ],
  },
  {
    id: "work_relief",
    years: "1934-1936",
    title: "Work Relief and Uneven Hope",
    image: "work-relief-market.png",
    newsImage: "news-newdeal.png",
    news: "Work projects spread to more towns",
    summary: "Public works, local politics, and family pride all shape who gets help and how secure that help feels.",
    conditions: [["Jobs", "Partly restored", "warn"], ["Relief", "Expanding", "good"], ["Wages", "Uneven", "warn"], ["Hope", "Recovering", "good"]],
    choices: [
      ["stay_public_works", "Stay with public works", "Stable if available, limited advancement."],
      ["repair_health", "Spend on health", "Improve long-term survival, reduce cash."],
      ["organize_neighbors", "Organize neighbors", "Mutual aid and voice, takes time."],
      ["move_for_work_camp", "Send eldest to work camp", "Income and skills, family separation."],
      ["rebuild_savings", "Rebuild savings", "Slow progress, stronger resilience."],
      ["trust_reopened_bank", "Trust the reopened bank", "Rebuild safety, depends on trust."],
      ["hoard_relief", "Take extra relief", "Gain food now, but damage trust if exposed."],
    ],
  },
  {
    id: "second",
    years: "1937-1938",
    title: "A Recovery Stumbles",
    image: "recovery-stumbles-market.png",
    newsImage: "public-news-1937-newspaper.png",
    news: "Recovery slows as jobless rise again",
    summary: "Policy changes, business caution, and weak demand contribute to another downturn.",
    conditions: [["Unemployment", "Rising again", "bad"], ["Bank confidence", "Improved", "good"], ["Credit", "Cautious", "neutral"], ["Relief", "Contested", "warn"]],
    choices: [
      ["stay_public_works", "Stay with public works", "Stable if available, limited advancement."],
      ["seek_defense_work", "Seek defense work", "Risky move toward growing industry."],
      ["rebuild_savings", "Rebuild savings", "Slow progress, stronger resilience."],
      ["repair_health", "Spend on health", "Improve long-term survival, reduce cash."],
      ["support_union", "Support union drive", "Potential wage gains, job conflict risk."],
      ["older_child_fulltime", "Older child works full-time", "Income now, education cost deepens."],
      ["undercut_wages", "Undercut wages", "Win scarce work by accepting less pay and lower trust."],
    ],
  },
  {
    id: "defense_shift",
    years: "1939-1940",
    title: "Factories Turn Toward New Orders",
    image: "defense-shift-market.png",
    newsImage: "news-recovery.png",
    news: "Factories prepare for new orders",
    summary: "Industrial demand begins to shift. Families must decide whether to move toward new work or keep rebuilding carefully.",
    conditions: [["Factory demand", "Rising", "good"], ["Unemployment", "Improving", "good"], ["Savings", "Thin", "warn"], ["Stability", "Possible", "good"]],
    choices: [
      ["seek_defense_work", "Seek defense work", "Risky move toward growing industry."],
      ["rebuild_savings", "Rebuild savings", "Slow progress, stronger resilience."],
      ["repair_health", "Spend on health", "Improve long-term survival, reduce cash."],
      ["support_union", "Support union drive", "Potential wage gains, job conflict risk."],
      ["keep_children_school", "Keep children in school", "Protect future, sacrifice short-term income."],
      ["move_better_rental", "Move to safer housing", "Improve health and morale, raise rent."],
      ["inform_on_black_market", "Inform on informal trade", "Gain a short edge, but take an exploit penalty."],
    ],
  },
  {
    id: "recovery",
    years: "1941-1942",
    title: "Recovery and Mobilization",
    image: "recovery-mobilization-market.png",
    newsImage: "news-recovery.png",
    news: "Factories hire as orders surge",
    summary: "The long crisis gives way to mobilization, though not every family recovers equally.",
    conditions: [["Unemployment", "Falling", "good"], ["Bank confidence", "Recovering", "good"], ["Savings", "Rebuilding", "good"], ["Public support", "Shifting", "neutral"]],
    choices: [],
  },
];

const extremeChoiceRules = [
  {
    id: "seek_charity_clinic",
    title: "Seek charity clinic",
    detail: "Health crisis: recover health, but lose savings and hope.",
    when: (family) => family.health < 25,
  },
  {
    id: "send_family_to_country",
    title: "Send family to relatives",
    detail: "Health crisis: protect food and health, but reduce stability.",
    when: (family) => family.health < 25,
  },
  {
    id: "pawn_heirloom",
    title: "Pawn family heirloom",
    detail: "Savings crisis: raise cash fast, but hurt hope.",
    when: (family) => family.savings < 20,
  },
  {
    id: "take_desperate_work",
    title: "Take dangerous work",
    detail: "Food crisis: bring income and food, risk health.",
    when: (family) => family.food < 20,
  },
  {
    id: "sponsor_neighbor",
    title: "Sponsor a neighbor",
    detail: "High stability: build support, spend savings.",
    when: (family) => family.stability > 80,
  },
  {
    id: "fund_training",
    title: "Fund training",
    detail: "High savings: improve education and future resilience.",
    when: (family) => family.savings > 80,
  },
];

function getExtremeChoices(family) {
  if (!family) return [];
  return extremeChoiceRules
    .filter((rule) => rule.when(family))
    .slice(0, 2)
    .map(({ id, title, detail }) => [id, title, detail]);
}

function familyImageFor(family) {
  if (!family) return "family-profile.png";
  const minHealth = Math.min(family.health ?? 100, family.minHealth ?? 100);
  const dangerValues = [
    family.food,
    family.health,
    family.hope,
    family.education,
    family.stability,
    family.savings,
    family.minFood,
    family.minHealth,
    family.minHope,
    family.minEducation,
    family.minStability,
    family.minSavings,
  ].filter((value) => typeof value === "number");
  if (minHealth < 25) return "family-health-crisis.png";
  return dangerValues.some((value) => value < 25) ? "family-danger-state.png" : "family-profile.png";
}

function clamp(value) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function scoreFamily(family) {
  const core = (family.food + family.health + family.savings + family.hope + family.education + family.stability) / 6;
  const debtPenalty = family.debt * 0.28;
  const reputationBonus = ((family.reputation ?? 50) - 50) * 0.22;
  const exploitPenalty = (family.exploitMarkers || 0) * 5;
  const dangerMeters = ["minFood", "minHealth", "minHope", "minEducation", "minStability", "minSavings"];
  const dangerPenalty = dangerMeters.reduce((sum, key) => {
    const value = family[key] ?? 100;
    if (value < 10) return sum + 18;
    if (value < 25) return sum + 10;
    if (value < 35) return sum + 4;
    return sum;
  }, 0);
  const resilienceBonus = dangerPenalty === 0 ? 6 : 0;
  return clamp(core - debtPenalty - dangerPenalty - exploitPenalty + reputationBonus + resilienceBonus + objectiveResult(family).bonus);
}

function flattenChoices(family) {
  return Object.values(family.choices || {}).flat();
}

function countChoices(family, choiceSet) {
  return flattenChoices(family).filter((choice) => choiceSet.has(choice)).length;
}

function objectiveResult(family) {
  const choices = flattenChoices(family);
  const usedMigrationPath = choices.some((choice) => MOBILITY_CHOICES.has(choice));
  const workReliefCount = countChoices(family, WORK_OR_RELIEF_CHOICES);
  const communityCount = countChoices(family, COOPERATIVE_CHOICES);
  const trust = family.reputation ?? 50;
  const completed =
    (family.objectiveId === "industrial_stability" && family.stability >= 60 && trust >= 45) ||
    (family.objectiveId === "shopkeeper_debt" && family.debt <= 45 && family.hope >= 45) ||
    (family.objectiveId === "tenant_food" && (family.food >= 50 || usedMigrationPath)) ||
    (family.objectiveId === "immigrant_trust" && (trust >= 65 || family.education >= 60)) ||
    (family.objectiveId === "railroad_mobility" && workReliefCount >= 2 && family.health >= 45) ||
    (family.objectiveId === "garment_solidarity" && communityCount >= 2 && family.hope >= 55) ||
    (family.objectiveId === "service_respect" && family.stability >= 50 && trust >= 60) ||
    (family.objectiveId === "miner_health" && family.health >= 45 && family.debt <= 55) ||
    (family.objectiveId === "seasonal_work" && family.food >= 45 && workReliefCount >= 2);
  return { completed, bonus: completed ? 10 : 0 };
}

function lowestRecordedMeter(family) {
  return Math.min(
    family.minFood ?? family.food ?? 100,
    family.minHealth ?? family.health ?? 100,
    family.minHope ?? family.hope ?? 100,
    family.minEducation ?? family.education ?? 100,
    family.minStability ?? family.stability ?? 100,
    family.minSavings ?? family.savings ?? 100
  );
}

function startingHardship(family) {
  if (typeof family.initialHardship === "number") return family.initialHardship;
  const baseline = ["food", "health", "savings", "hope", "education", "stability"].reduce((sum, key) => sum + (family[key] || 0), 0) / 6;
  return 100 - baseline + (family.debt || 0) * 0.25;
}

function awardWinner(players, scoreMap, selector, usedIds = new Set()) {
  const eligible = players.filter((player) => !usedIds.has(player.id));
  const pool = eligible.length ? eligible : players;
  return [...pool].sort((a, b) => selector(b, scoreMap.get(b.id)) - selector(a, scoreMap.get(a.id)) || (scoreMap.get(b.id) || 0) - (scoreMap.get(a.id) || 0))[0];
}

function computeAwards(players) {
  if (!players.length) return [];
  const scored = players.map((player) => ({ ...player, score: scoreFamily(player) })).sort((a, b) => b.score - a.score);
  const scoreMap = new Map(scored.map((player) => [player.id, player.score]));
  const mostResilient = scored[0];
  const usedIds = new Set(mostResilient ? [mostResilient.id] : []);
  const communityAnchor = awardWinner(players, scoreMap, (player) => {
    const choices = flattenChoices(player);
    return (player.reputation ?? 50) + choices.filter((choice) => COOPERATIVE_CHOICES.has(choice)).length * 8 - (player.exploitMarkers || 0) * 12;
  }, usedIds);
  if (communityAnchor) usedIds.add(communityAnchor.id);
  const hardestRoad = awardWinner(players, scoreMap, (player) => startingHardship(player) + Math.max(0, scoreMap.get(player.id) || 0) * 0.35, usedIds);
  if (hardestRoad) usedIds.add(hardestRoad.id);
  const boldestGamble = awardWinner(players, scoreMap, (player) => {
    const choices = flattenChoices(player);
    return choices.filter((choice) => RISK_CHOICES.has(choice)).length * 12 + (player.stock || 0) * 0.25 + (player.exploitMarkers || 0) * 6;
  }, usedIds);
  if (boldestGamble) usedIds.add(boldestGamble.id);
  const steadyHand = awardWinner(players, scoreMap, (player) => lowestRecordedMeter(player) - (player.exploitMarkers || 0) * 10 - (player.rushedChoiceCount || 0) * 3, usedIds);
  return [
    { id: "resilient", title: "Most Resilient Family", player: mostResilient, detail: "Highest final resilience score across meters, debt, trust, and danger penalties.", primary: true },
    { id: "anchor", title: "Community Anchor", player: communityAnchor, detail: "Best record of cooperation, trust, and low exploitation." },
    { id: "hardest", title: "Hardest Road", player: hardestRoad, detail: "Strongest finish from the toughest family position." },
    { id: "gamble", title: "Boldest Gamble", player: boldestGamble, detail: "Took the biggest strategic risks while staying in the race." },
    { id: "steady", title: "Steady Hand", player: steadyHand, detail: "Kept the family out of danger with the fewest severe lows." },
  ].filter((award) => award.player);
}

function historicalDebrief(players, shared) {
  if (!players.length) return [];
  const choices = players.flatMap(flattenChoices);
  const exploitCount = players.reduce((sum, player) => sum + (player.exploitMarkers || 0), 0);
  const objectiveCount = players.filter((player) => objectiveResult(player).completed).length;
  const dangerCount = players.filter((player) => lowestRecordedMeter(player) < 25).length;
  const cooperationCount = choices.filter((choice) => COOPERATIVE_CHOICES.has(choice)).length;
  const workReliefCount = choices.filter((choice) => WORK_OR_RELIEF_CHOICES.has(choice)).length;
  const takeaways = [
    `${objectiveCount}/${players.length} families completed their background objective, showing how the same economy created different survival priorities.`,
    `${workReliefCount} work or relief choices were made. Scarce opportunities helped, but they could not remove pressure for everyone.`,
    cooperationCount >= exploitCount
      ? "Cooperation was a meaningful strategy: shared support improved trust and helped families absorb shocks."
      : "Soft betrayal paid in the short term, but exploit markers and lower trust made selfish survival more costly at the end.",
    dangerCount
      ? `${dangerCount} families hit a danger zone on at least one meter, showing how quickly food, health, savings, hope, schooling, or stability could become fragile.`
      : "No family crossed a severe danger threshold, which means the room collectively managed risk unusually well.",
    (shared?.trust ?? 55) >= 60
      ? "The room ended with a relatively strong trust climate, making relief and work access easier to justify."
      : "The room ended with a strained trust climate, showing how scarcity can weaken community confidence.",
  ];
  return takeaways;
}

function loadSavedGame() {
  if (typeof window === "undefined") return {};
  try {
    const params = new URLSearchParams(window.location.search);
    const joinCode = (params.get("room") || "").trim().toUpperCase();
    const saved = JSON.parse(window.localStorage.getItem("gd-game-state") || "{}");
    if (params.has("newHost")) {
      window.localStorage.removeItem("gd-game-state");
      return {};
    }
    if (saved.version !== GAME_STATE_VERSION) return {};
    if (saved.view === "host" && !saved.hostToken) return {};
    if (joinCode) {
      if (saved.roomCode === joinCode && (saved.activePlayerId || saved.hostToken)) return saved;
      return { view: "join", roomCode: joinCode };
    }
    return saved;
  } catch {
    return {};
  }
}

const apiBase = () => {
  if (process.env.REACT_APP_GAME_API_URL) return process.env.REACT_APP_GAME_API_URL.replace(/\/$/, "");
  if (typeof window !== "undefined" && ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname)) {
    return window.location.port === "3000" ? "http://localhost:8000/api" : "/api";
  }
  return "/api";
};

async function gameApi(path, options = {}) {
  const response = await fetch(`${apiBase()}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.error || "The game room server did not respond.");
  return data;
}

function App() {
  const savedGame = useMemo(() => loadSavedGame(), []);
  const [view, setView] = useState(savedGame.view || "start");
  const [roomCode, setRoomCode] = useState(savedGame.roomCode || "");
  const [hostToken, setHostToken] = useState(savedGame.hostToken || "");
  const [players, setPlayers] = useState(savedGame.players || []);
  const [shared, setShared] = useState(savedGame.shared || null);
  const [phaseIndex, setPhaseIndex] = useState(savedGame.phaseIndex || 0);
  const [playerName, setPlayerName] = useState(savedGame.playerName || "");
  const [activePlayerId, setActivePlayerId] = useState(savedGame.activePlayerId || "");
  const [selected, setSelected] = useState(savedGame.selected || []);
  const [apiError, setApiError] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [lastSyncedAt, setLastSyncedAt] = useState(savedGame.lastSyncedAt || 0);
  const [phaseRevealVisible, setPhaseRevealVisible] = useState(false);
  const joinClientIdRef = useRef(savedGame.joinClientId || `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`);

  const phase = phases[phaseIndex] || phases[0];
  const isFinalPhase = phaseIndex >= phases.length - 1;
  const activePlayer = players.find((p) => p.id === activePlayerId) || players[0];
  const submittedChoices = activePlayer?.choices?.[phase.id] || [];
  const submittedCount = players.filter((p) => p.choices?.[phase.id]?.length === 2).length;
  const activeChoices = useMemo(() => {
    if (!phase.choices.length) return phase.choices;
    const existingChoiceIds = new Set(phase.choices.map(([id]) => id));
    const extremeChoices = getExtremeChoices(activePlayer).filter(([id]) => !existingChoiceIds.has(id));
    return [...phase.choices, ...extremeChoices];
  }, [activePlayer, phase]);
  const scoredPlayers = useMemo(
    () => players.map((p) => ({ ...p, score: scoreFamily(p) })).sort((a, b) => b.score - a.score),
    [players]
  );
  const rushedChoiceWarning = activePlayer?.lastChoiceRushed;

  useEffect(() => {
    window.localStorage.setItem(
      "gd-game-state",
      JSON.stringify({ version: GAME_STATE_VERSION, view, roomCode, hostToken, players, shared, phaseIndex, playerName, activePlayerId, selected, lastSyncedAt, joinClientId: joinClientIdRef.current })
    );
  }, [view, roomCode, hostToken, players, shared, phaseIndex, playerName, activePlayerId, selected, lastSyncedAt]);

  useEffect(() => {
    if (view !== "host" && view !== "player") return undefined;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    setPhaseRevealVisible(true);
    const timer = window.setTimeout(() => setPhaseRevealVisible(false), reduceMotion ? 350 : 4400);
    return () => window.clearTimeout(timer);
  }, [phaseIndex, view]);

  function syncRoom(room) {
    if (!room) return;
    setRoomCode(room.roomCode);
    setPlayers(room.players || []);
    setShared(room.shared || null);
    setPhaseIndex(room.phaseIndex || 0);
    setLastSyncedAt(Date.now());
  }

  function resetExpiredRoom() {
    setView("start");
    setRoomCode("");
    setHostToken("");
    setPlayers([]);
    setShared(null);
    setPhaseIndex(0);
    setActivePlayerId("");
    setSelected([]);
    setLastSyncedAt(0);
    setApiError("That room expired. Create a fresh room to continue.");
  }

  async function runGameRequest(request) {
    setIsBusy(true);
    setApiError("");
    try {
      return await request();
    } catch (error) {
      if (/room not found/i.test(error.message)) {
        resetExpiredRoom();
        return null;
      }
      setApiError(error.message);
      return null;
    } finally {
      setIsBusy(false);
    }
  }

  useEffect(() => {
    if (!roomCode || view === "start" || view === "join") return undefined;
    let cancelled = false;
    const pullRoom = async () => {
      try {
        const data = await gameApi(`/game/rooms/${roomCode}`);
        if (!cancelled) {
          syncRoom(data.room);
          setApiError("");
        }
      } catch (error) {
        if (!cancelled) {
          if (/room not found/i.test(error.message)) resetExpiredRoom();
          else setApiError(error.message);
        }
      }
    };
    pullRoom();
    const timer = window.setInterval(pullRoom, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [roomCode, view]);

  async function createHostRoom() {
    const data = await runGameRequest(() => gameApi("/game/rooms", { method: "POST", body: JSON.stringify({}) }));
    if (!data) return;
    syncRoom(data.room);
    setHostToken(data.hostToken || "");
    setActivePlayerId("");
    setSelected([]);
    setView("host");
  }

  async function joinRoom() {
    const code = roomCode.trim().toUpperCase();
    if (!code) {
      setApiError("Ask the host for the room code first.");
      return;
    }
    const data = await runGameRequest(() =>
      gameApi(`/game/rooms/${code}/join`, {
        method: "POST",
        body: JSON.stringify({ room_code: code, player_name: playerName.trim() || "Player", client_id: joinClientIdRef.current }),
      })
    );
    if (!data) return;
    syncRoom(data.room);
    setHostToken("");
    setActivePlayerId(data.playerId);
    setSelected([]);
    setView("player");
  }

  async function addDemoPlayer() {
    if (!roomCode || players.length >= MAX_PLAYERS) return;
    const data = await runGameRequest(() =>
      gameApi(`/game/rooms/${roomCode}/join`, {
        method: "POST",
        body: JSON.stringify({ room_code: roomCode, player_name: `Player ${players.length + 1}`, client_id: `demo-${Date.now()}-${players.length}` }),
      })
    );
    if (!data) return;
    syncRoom(data.room);
    setActivePlayerId(data.playerId);
  }

  function toggleChoice(choice) {
    setSelected((current) => {
      if (current.includes(choice)) return current.filter((item) => item !== choice);
      return current.length >= 2 ? [current[1], choice] : [...current, choice];
    });
  }

  async function submitChoices() {
    if (!activePlayer || selected.length !== 2) return;
    const data = await runGameRequest(() =>
      gameApi(`/game/rooms/${roomCode}/choices`, {
        method: "POST",
        body: JSON.stringify({ player_id: activePlayer.id, choices: selected }),
      })
    );
    if (!data) return;
    syncRoom(data.room);
    setSelected([]);
  }

  async function advancePhase() {
    if (view !== "host") return;
    if (!hostToken) {
      setApiError("This browser is missing the host key. Create a new host room to control phases.");
      return;
    }
    const data = await runGameRequest(() =>
      gameApi(`/game/rooms/${roomCode}/advance`, { method: "POST", body: JSON.stringify({ host_token: hostToken }) })
    );
    if (!data) return;
    syncRoom(data.room);
    setSelected([]);
  }

  return (
    <main className="gd-app">
      <section className="gd-topbar">
        <div>
          <p className="gd-kicker">Main Street, 1919</p>
          <h1>American Promise Survival Game</h1>
        </div>
        <div className="gd-room">Room {roomCode || "not started"}</div>
      </section>
      {apiError && <div className="gd-alert">{apiError}</div>}

      {view === "start" && (
        <section className="gd-start">
          <div className="gd-hero">
            <img src={asset("login-hero.png")} alt="" />
            <div>
              <p className="gd-kicker">1919-1942 multiplayer learning game</p>
              <h2>Chase the American Promise.</h2>
              <p>
                Join with a room code, receive a random family, and choose two actions each round as public news changes the
                economy around you. Your food, health, savings, debt, hope, and education shape your final score.
              </p>
              <div className="gd-actions">
                <button onClick={createHostRoom} disabled={isBusy}>{isBusy ? "Creating..." : "Create host room"}</button>
                <button className="secondary" onClick={() => setView("join")}>Join as player</button>
              </div>
            </div>
          </div>
        </section>
      )}

      {view === "join" && (
        <section className="gd-panel gd-join">
          <h2>Join a room</h2>
          <input value={roomCode} onChange={(e) => setRoomCode(e.target.value.toUpperCase())} placeholder="Room code" />
          <input value={playerName} onChange={(e) => setPlayerName(e.target.value)} placeholder="Your name" />
          <button onClick={joinRoom} disabled={isBusy}>{isBusy ? "Joining..." : "Get family profile"}</button>
        </section>
      )}

      {(view === "host" || view === "player") && (
        <>
        {phaseRevealVisible && (
          <div className="phase-reveal" key={phase.id} aria-hidden="true">
            <img src={asset(phase.image)} alt="" />
            <div className="phase-reveal-copy">
              <p className="gd-kicker">Market Conditions - {phase.years}</p>
              <h2>{phase.title}</h2>
            </div>
          </div>
        )}
        <section className={`gd-grid ${phaseRevealVisible ? "phase-ui-hidden" : "phase-ui-visible"}`}>
          <div className="gd-main">
            <div className="gd-market">
              <p className="gd-kicker">Market Conditions - {phase.years}</p>
              <img src={asset(phase.image)} alt={phase.title} />
              <p>{phase.summary}</p>
            </div>

            <div className="gd-news">
              <p className="gd-kicker">Public News</p>
              {phase.newsImage && <img src={asset(phase.newsImage)} alt={phase.news} />}
              <h2>{phase.news}</h2>
            </div>

            {activeChoices.length > 0 && submittedChoices.length > 0 ? (
              <div className="gd-panel gd-submitted">
                <p className="gd-kicker">Choices Submitted</p>
                <h2>Ready for the next phase</h2>
                <p>
                  Your choices were applied to the family meters. The phase will move forward automatically once every
                  player in the room has submitted, or the host can advance it manually.
                </p>
                {rushedChoiceWarning && <p className="gd-sync">Quick choices gave reduced positive gains this round.</p>}
                <p className="gd-sync">Submitted {submittedCount}/{players.length}</p>
                {view === "host" && <button onClick={advancePhase} disabled={isBusy || isFinalPhase}>Advance now</button>}
              </div>
            ) : activeChoices.length > 0 ? (
              <div className="gd-choices">
                <img src={asset("new-deal-choice-background.png")} alt="" />
                <div className="gd-choice-content">
                  <p className="gd-kicker">Choose 2 Actions</p>
                  <div className="gd-choice-grid">
                    {activeChoices.map(([id, title, detail], index) => (
                      <button key={id} className={selected.includes(id) ? "selected" : ""} onClick={() => toggleChoice(id)}>
                        <span>{String.fromCharCode(65 + index)}</span>
                        <strong>{title}</strong>
                        <em>{detail}</em>
                      </button>
                    ))}
                  </div>
                  <button className="gd-submit" onClick={submitChoices} disabled={selected.length !== 2 || isBusy}>
                    {isBusy ? "Submitting..." : "Submit choices"}
                  </button>
                </div>
              </div>
            ) : (
              <Leaderboard players={scoredPlayers} shared={shared} />
            )}
          </div>

          <aside className="gd-sidebar">
            <FamilyCard family={activePlayer} />
            {activePlayer && <Meters family={activePlayer} />}
            <CommunityPanel shared={shared} />
            <Conditions conditions={phase.conditions} />
            {view === "host" && (
              <div className="gd-panel">
                <p className="gd-kicker">Host Controls</p>
                <p className="gd-sync">Players {players.length}/{MAX_PLAYERS} - submitted {submittedCount}/{players.length}</p>
              <p className="gd-sync">Phase {Math.min(phaseIndex + 1, phases.length)}/{phases.length} - target 20-25 min</p>
                <p className="gd-sync">Sync {lastSyncedAt ? new Date(lastSyncedAt).toLocaleTimeString() : "waiting"}</p>
                <button onClick={addDemoPlayer} disabled={isBusy || players.length >= MAX_PLAYERS}>Add demo player</button>
                <button onClick={advancePhase} disabled={isBusy || isFinalPhase}>Advance phase</button>
                <button onClick={() => setView("host")}>Show leaderboard</button>
              </div>
            )}
          </aside>
        </section>
        </>
      )}
    </main>
  );
}

function FamilyCard({ family }) {
  if (!family) {
    return <div className="gd-panel"><p className="gd-kicker">Family Profile</p><p>No players yet. Add a player to assign a family.</p></div>;
  }
  return (
    <div className="gd-panel">
      <div className="family-image">
        <img src={asset(familyImageFor(family))} alt={`${family.name} family`} />
      </div>
      <p className="gd-kicker">Family Profile</p>
      <h2>The {family.name} Family</h2>
      <p>{family.playerName} - {family.profile}</p>
      {family.objectiveTitle && (
        <div className="family-objective">
          <strong>{family.role}</strong>
          <p>{family.objectiveTitle}: {family.objectiveDetail}</p>
        </div>
      )}
    </div>
  );
}

function Meters({ family }) {
  const meters = ["food", "health", "savings", "hope", "education", "stability"];
  const reputation = family.reputation ?? 50;
  return (
    <div className="gd-panel">
      <p className="gd-kicker">Family Meters</p>
      {meters.map((key) => (
        <div className="meter" key={key}>
          <span>{key}</span>
          <div><i style={{ width: `${family[key]}%` }} /></div>
          <b>{family[key]}</b>
        </div>
      ))}
      <div className="meter debt"><span>debt</span><div><i style={{ width: `${family.debt}%` }} /></div><b>{family.debt}</b></div>
      <div className="meter reputation">
        <span>trust</span>
        <div><i style={{ width: `${Math.max(0, Math.min(100, ((reputation + 30) / 130) * 100))}%` }} /></div>
        <b>{reputation}</b>
      </div>
      {!!family.exploitMarkers && <p className="gd-sync">Exploit markers: {family.exploitMarkers}</p>}
    </div>
  );
}

function CommunityPanel({ shared }) {
  const current = shared || {
    trust: 55,
    communityPot: 3,
    workSlots: 1,
    reliefSlots: 1,
    communityNeed: 2,
    lastRound: "No shared decision has resolved yet.",
  };
  const trustStatus = current.trust >= 68 ? "good" : current.trust <= 35 ? "bad" : "warn";
  const potStatus = current.communityPot >= current.communityNeed ? "good" : current.communityPot <= 1 ? "bad" : "warn";
  return (
    <div className="gd-panel community-panel">
      <p className="gd-kicker">Town Hall</p>
      <h2>Discuss aloud, choose secretly</h2>
      <p className="gd-sync">Take a short meeting discussion before choices. The app only records final choices.</p>
      <div className="community-stats">
        <div>
          <span>Work slots</span>
          <strong>{current.workSlots}</strong>
        </div>
        <div>
          <span>Relief slots</span>
          <strong>{current.reliefSlots}</strong>
        </div>
        <div className={potStatus}>
          <span>Community pot</span>
          <strong>{current.communityPot}/{current.communityNeed}</strong>
        </div>
        <div className={trustStatus}>
          <span>Trust climate</span>
          <strong>{current.trust}</strong>
        </div>
      </div>
      <p className="community-last">{current.lastRound}</p>
    </div>
  );
}

function Conditions({ conditions }) {
  return (
    <div className="gd-panel">
      <p className="gd-kicker">Shared Conditions</p>
      <div className="condition-list">
        {conditions.map(([label, value, status]) => (
          <div className="condition" key={label}>
            <span className={status}>{status === "good" ? "↗" : status === "bad" ? "!" : "•"}</span>
            <div><strong>{label}</strong><p>{value}</p></div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Leaderboard({ players, shared }) {
  const awards = computeAwards(players);
  const debrief = historicalDebrief(players, shared);
  return (
    <div className="gd-panel leaderboard">
      <p className="gd-kicker">Final Leaderboard</p>
      <h2>Scores include danger penalties</h2>
      {awards[0] && (
        <div className="winner-badge">
          <img src={asset("award-most-resilient-family.png")} alt="Most Resilient Family badge" />
          <div>
            <p className="gd-kicker">Winner</p>
            <h3>{awards[0].player.playerName || "Player"} ({awards[0].player.name} Family)</h3>
            <p>{awards[0].detail}</p>
          </div>
        </div>
      )}
      {players.map((player, index) => (
        <LeaderboardRow player={player} index={index} key={player.id} />
      ))}
      <p className="gd-note">Scores include danger penalties, debt, trust reputation, exploit markers, and a +10 family objective bonus.</p>
      <div className="award-grid">
        {awards.map((award) => (
          <div className={award.primary ? "award-card primary" : "award-card"} key={award.id}>
            <span>{award.primary ? "★" : "•"}</span>
            <div>
              <strong>{award.title}</strong>
              <p>{award.player.playerName || "Player"} ({award.player.name} Family)</p>
              <small>{award.detail}</small>
            </div>
          </div>
        ))}
      </div>
      <div className="debrief-panel">
        <p className="gd-kicker">Historical Debrief</p>
        <h3>What this room experienced</h3>
        {debrief.map((takeaway) => (
          <p key={takeaway}>{takeaway}</p>
        ))}
      </div>
    </div>
  );
}

function LeaderboardRow({ player, index }) {
  const objective = objectiveResult(player);
  return (
    <div className="leader-row" key={player.id}>
      <b>{index + 1}</b>
      <span>
        {player.playerName || "Player"} ({player.name} Family)
        <small>Trust {player.reputation ?? 50} · Exploit markers {player.exploitMarkers || 0}</small>
        {player.objectiveTitle && (
          <small>{objective.completed ? "+10" : "0"} objective: {player.objectiveTitle}</small>
        )}
      </span>
      <strong>{player.score}</strong>
    </div>
  );
}

export default App;
