Original prompt: Build and iterate a playable web game in this workspace, validating changes with a Playwright loop.

- Created new game shell under /Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/game with index.html, style.css, and game.js.
- Implemented Star Courier: move, shoot, collect cores, avoid drones, pause/resume, restart, fullscreen toggle, HUD, and render_game_to_text + advanceTime hooks.
- Not yet run Playwright loop or inspected screenshots.

- Attempted Playwright run; failed because Node cannot find the playwright package and npm install failed due to network ENOTFOUND to registry.npmjs.org.
- Started local server with python http.server on port 5173 (nohup).

- Installed Playwright (npm) and downloaded Chromium binaries; needed symlinks for arm64 cache paths.
- Playwright client now runs against file:// URL (localhost server failed with connection refused).
- Iteration: improved movement feel (accel/drag), faster fire rate, added gem magnetism, particle effects, and screen shake.
- Verified screenshots + render_game_to_text outputs after changes (output/web-game/shot-*.png, state-*.json).

- Added enemy behaviors: chasers, skirmishers (orbit), chargers (windup + dash), with telegraphed visuals and per-type HP.
- Updated render_game_to_text to include enemy behavior state fields.
- Ran Playwright loop after changes; screenshots in output/web-game/shot-*.png and states in output/web-game/state-*.json.

- Added new mechanics: core chain multiplier, weapon overheat, dash, shield burst, fuel pods, slow fields from sappers, splitter enemies, and gate objective after collecting all cores.
- Updated HUD for heat/chain/cooldowns, added gate rendering and extra gameplay state to render_game_to_text.
- Ran Playwright loop with new action burst; screenshots in output/web-game/shot-*.png and states in output/web-game/state-*.json.

- Implemented spread-shot firing (3-projectile fan) and reduced bullet life slightly.
- Re-ran Playwright loop; screenshots updated in output/web-game/shot-*.png.

- Fullscreen now truly expands to canvas-only view when pressing F (body fullscreen class + resize logic). Removed duplicate CSS blocks.
- Verified via Playwright run; screenshots in output/web-game/shot-*.png.

- Integrated Larzes Medium assets for player, enemies, bullets, pickups, and gate. Switched to sprite rendering with fallback shapes.
- Playwright run required serving via http://127.0.0.1:5173 to avoid tainted canvas; screenshots updated in output/web-game/shot-*.png.

- Replaced gate sprite from boss to Pickup_3_A to better fit gate objective.
- Re-ran Playwright via http://127.0.0.1:5173 and updated screenshots in output/web-game/shot-*.png.

- Added mouse steering: hold left mouse to move toward cursor; keyboard still works. Added mouse state to render_game_to_text and updated control text.
- Updated Playwright actions to include left-mouse movement and revalidated via http://127.0.0.1:5173; screenshots updated.

- Mouse now controls ship facing (aim); movement is WASD-only. Updated controls text and input handling accordingly.
- Revalidated via Playwright on http://127.0.0.1:5173; screenshots updated.

- Added ammo mods, risk zones, companion drone, wave system with boss mini-boss, salvage shop upgrades, objectives, audio/flash FX, and enemy bullets.
- Updated HUD, controls, and render_game_to_text to include new systems. Ran Playwright via http://127.0.0.1:5173; screenshots updated.
