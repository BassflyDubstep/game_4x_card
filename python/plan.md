# Opponent AI implementation plan

## Problem
- The current Python prototype supports exactly one actively controlled empire per match.
- `Game.run()` contains a console-driven loop with nested action functions, so turn execution, input handling, and game rules are tightly coupled.
- `Map` already exposes most rule operations needed by an AI (`move_regiment`, `attack_regiment`, `attack_city`, `defend_regiment`, `split_regiment`, `combine_regiments`, visibility and influence queries), which makes a lightweight opponent layer feasible.
- Because this logic should port cleanly to C++, the first AI should avoid Python-specific patterns and avoid heavyweight search techniques.

## Recommended approach
- Implement a **rule-based / utility-scored AI**, not minimax or machine learning.
- Separate **turn decision-making** from **console input** so both human and computer players use the same game-rule API.
- Represent AI choices as explicit action objects or action dictionaries with stable fields (`action_type`, `actor_id`, `target_id`, `target_pos`, `metadata`) so the same design maps directly to C++ structs/classes later.
- Keep the first milestone intentionally narrow: local human + local AI players only, full information limited by existing fog-of-war rules, and simple tactical behavior.

## Current-state findings from `python/main.py`
- `Player` only stores `id`, `name`, and `color`; it has no controller type or AI profile.
- `Game` stores one `selected_player_id`, meaning the program currently assumes one human empire and zero active opponent turns.
- Turn advancement happens in `advance_turn()`, but it only resets movement/battle state, processes regiment production, and redraws the map. No other players take actions.
- Most player commands are implemented as nested functions inside `Game.run()`, which is convenient for the console UI but a poor seam for AI reuse or C++ porting.
- The best reusable boundary already exists in `Map`: game-state mutation methods are mostly input-free and validation-heavy, which is exactly what an AI layer should call.

## Architecture plan

### 1. Add controller metadata to players
- Extend `Player` with a controller field such as `controller_type: "human" | "computer"` and optionally an `ai_profile`.
- Keep it data-only so it ports directly to a C++ enum plus a small config struct.
- Update map loading or new-game setup so one empire is marked human and the rest can be assigned computer control.

### 2. Pull action execution out of nested console helpers
- Refactor the logic in `Game.run()` so the game exposes reusable methods like:
  - `queue_regiment_order(player_id, city_id, regiment_name)`
  - `move_regiment_for_player(player_id, regiment_id, x, y)`
  - `attack_with_regiment(player_id, regiment_id, target_kind, target_id)`
  - `defend_regiment_for_player(player_id, regiment_id)`
- Keep console prompts as a thin translation layer that gathers input and calls these methods.
- This is the most important portability step, because it creates C++-friendly game commands independent of `input()` and `print()`.

### 3. Introduce a turn scheduler for all empires
- Replace the single-human assumption with an ordered turn flow over all players.
- Recommended shape:
  1. Start global turn
  2. Reset movement / battle state
  3. Process build queue
  4. For each player in order:
     - if human: enter menu loop until end-turn
     - if computer: generate and execute AI actions
  5. Advance to next global turn
- This keeps the model explicit and easy to port into a future C++ `Game::update()` loop.

### 4. Create a simple opponent planner
- Add a small AI module/class that inspects the current map from one player’s perspective and returns ranked actions.
- Recommended first-pass priorities:
  1. **Immediate attacks** if a visible enemy regiment or city is in range and the estimated trade is favorable.
  2. **City defense** if an enemy is near an owned city/capital.
  3. **Movement toward objectives** such as nearby enemy cities, contested influence zones, vulnerable enemy regiments, and capitals worth pressuring.
  4. **Regiment production** in owned cities when the empire has few active regiments or nearby threats.
  5. **Defend stance** when no strong attack or move exists.
- Avoid split/combine logic in the first AI milestone unless needed later; those actions are valuable but add branching complexity early.

### 5. Use deterministic heuristics instead of search
- Score candidate actions with small, transparent formulas using data you already have:
  - distance to target
  - attack range availability
  - own total units vs enemy total units
  - regiment attack/defense scores
  - target type bonus (capitals and strategically important cities score higher than generic targets)
  - threat to nearby owned cities
  - tile influence / contested control
  - progress toward high-value strategic fronts instead of random nearest-target wandering
- Prefer deterministic tie-breaking so debugging and C++ parity are easier.
- If you want variety later, add a very small randomness term behind a configurable difficulty flag.

### 6. Keep AI computation portable
- Use plain lists, loops, numbers, and simple helper functions.
- Avoid Python features that do not translate cleanly to C++ design, such as deep closures, dynamic monkey-patching, reflection, or highly nested dict schemas.
- Favor explicit DTO-style data structures now so the later C++ version becomes mostly a type translation rather than a redesign.

## Suggested implementation phases

### Phase 1: Refactor for shared commands
- Move nested player action logic out of `Game.run()` into named `Game` methods.
- Preserve current behavior for the human-controlled empire.

### Phase 2: Multi-controller turn flow
- Add controller metadata to `Player`.
- Update match setup so one player is human and remaining players can be computer-controlled.
- Convert `advance_turn()` into a true full-player turn scheduler.

### Phase 3: Baseline AI
- Add a `ComputerOpponent` / `SimpleAiController` component.
- Implement attack, move, defend, and regiment-production choices.
- Keep decisions visibility-aware by using existing discovery/visibility methods.

### Phase 4: Evaluation tuning
- Tune action scoring against real maps.
- Add safeguards against obviously bad moves, such as attacking stronger targets, wasting movement, overextending away from influence objectives, or leaving capitals exposed when a defend action is available.

### Phase 5: Portability prep for C++
- Freeze the Python-side command and controller interfaces.
- Document the future C++ equivalents: enums, structs, and class responsibilities.

## Recommended first milestone
- Ship a **Simple AI** that can:
  - own turns
  - create regiments
  - move toward the nearest meaningful enemy objective, weighted toward contested territory and capitals
  - attack when the outcome is likely favorable
  - defend when under threat and no favorable action exists
- Do **not** start with pathfinding, diplomacy, multiplayer networking, minimax, or learning systems.

## Confirmed scope choice
- The first opponent milestone should already include **broader map-control goals**, especially contested influence areas and capital pressure, rather than being purely tactical.

## Notes
- This codebase is already close to supporting AI at the rule layer; the main blocker is that the command flow is embedded inside the console UI.
- The safest long-term move is to treat the current Python prototype as the place to define clean controller and command abstractions that can later be copied into C++ with minimal conceptual change.
