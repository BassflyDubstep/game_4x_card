# Copilot Prompt: Regiment Combat & City Siege Mechanics

Paste everything below into Copilot Chat (or as a comment above where you want it scaffolded) in `main.py`.

---

## Context

This is a card-driven grand strategy prototype (`main.py`). `Regiment` and `City` already exist with `regiment_attack_score`, `city_attack_score`, `defense_score`, `total_units()`, etc. — do not modify how those existing fields/scores are computed. I need two new mechanics added: regiment-vs-regiment battle resolution, and regiment-vs-city siege resolution. Implement these as new methods on the `Map` class, since `Map` already owns the logic that touches regiments, cities, and tiles together (see `move_regiment`, `get_regiment_at`). Match the existing code style: snake_case, `ValueError` for invalid state (see `move_regiment` for tone/phrasing), minimal comments only where the logic isn't self-evident, no docstrings elsewhere in the file so keep new ones short or omit. **Do not add any `print()` calls inside these methods** — the codebase's convention is that only methods explicitly named `print_*` do console output; these should be pure logic that return structured data for the UI layer to consume later.

---

## 1. Regiment vs. Regiment Combat

### New constants — add to `Regiment` as class attributes, next to `REGIMENT_ATTACK_WEIGHTS`:

```python
BASE_BATTLE_RATE = 0.25       # max fraction of a force that can be lost in a single combat round
FORCE_SIZE_EXPONENT = 0.5     # 0.5 = sqrt-dampened size scaling, 1.0 = linear/full stacking advantage
```

### New method: `Map.resolve_regiment_battle(self, regiment_a_id: int, regiment_b_id: int) -> dict`

Resolves **one round** of combat between two regiments (the caller is responsible for invoking this once per turn while both regiments remain adjacent/in conflict — do not build a multi-round loop inside this method).

**Validation** (raise `ValueError`, matching the phrasing style of `move_regiment`):
- Either regiment doesn't exist on the map
- Either regiment has `total_units() == 0`
- Both regiments share the same `owner_id`

**Formula:**
```
power_a = regiment_a.regiment_attack_score * (regiment_a.total_units() ** Regiment.FORCE_SIZE_EXPONENT)
power_b = regiment_b.regiment_attack_score * (regiment_b.total_units() ** Regiment.FORCE_SIZE_EXPONENT)

loss_fraction_a = Regiment.BASE_BATTLE_RATE * (power_b / (power_a + power_b))
loss_fraction_b = Regiment.BASE_BATTLE_RATE * (power_a / (power_a + power_b))
```
(`regiment_attack_score` already includes the hero bonus — do not apply hero multipliers again here.)

**Casualty distribution:** For each regiment, apply its loss fraction to `total_units()` to get a total casualty count, then distribute those casualties across `infantry`, `ranged`, `cavalry` (not `siege` — siege units don't participate in regiment-vs-regiment combat per `REGIMENT_ATTACK_WEIGHTS`, which excludes siege) proportionally to current composition. Use the largest-remainder method: floor each type's proportional share, sum the floored casualties, then assign the leftover one-by-one to the types with the largest fractional remainder until the total casualty count is reached. No unit type may go below 0.

**Defeat handling:** After casualties, if a regiment's `total_units() == 0`, mark it defeated: remove it from `self.regiments` and clear its tile's `regiment_id`. Both regiments can be defeated in the same round (mutual annihilation) — handle this case explicitly.

**Return value:** a dict with at least: casualties applied to each side (by unit type), each regiment's remaining `total_units()`, and boolean `defeated` flags for each side.

---

## 2. City Siege

### New constants — add to `City` as class attributes, next to `_city_symbols`:

```python
RESISTANCE_MULTIPLIER = 5.0       # max_siege_resistance = defense_score * RESISTANCE_MULTIPLIER
DEFENSE_SCALE = 1.0               # scales defense_score's weight in the siege power ratio
BASE_SIEGE_RATE = 0.20            # max fraction of resistance that can be lost in a single siege round
SIEGE_REGEN_RATE = 0.15           # fraction of max_resistance recovered per turn when unbesieged
SACK_POPULATION_PENALTY = 0.30    # fraction of population lost when a city is sacked
```

### `City` changes

- Add `self.siege_resistance` and `self.max_siege_resistance` in `__init__`, computed via a new `_default_max_siege_resistance()` method that mirrors the existing `_default_defense_score()` pattern: `defense_score * RESISTANCE_MULTIPLIER`. Initialize `siege_resistance` to the max.
- Update `mark_as_capital()` to also recompute `max_siege_resistance` and reset `siege_resistance` to the new max, the same way it already recomputes `defense_score`.

### New method: `Map.resolve_siege(self, regiment_id: int, city_id: int) -> dict`

Resolves **one turn** of siege state for a city. Call this once per turn per city that has any enemy regiment on its tile (or none — see regen case).

**Validation:** regiment and city must both exist. Regiment does not need to be a besieger for this call — if `regiment_id` is `None` or the regiment isn't physically on the city's tile, treat this as "unbesieged" and go to the regen branch below (don't raise an error for that case).

**Determining a valid besieger:** A regiment is besieging a city only if it currently occupies the exact same tile as the city (`Map.get_city_location(city_id)` returns the same coordinates as `Map.get_regiment_location(regiment_id)`), and the regiment's `owner_id` differs from `city.owner_id`.

**If besieged:**
```
siege_pressure = regiment.city_attack_score * regiment.total_units()
loss_fraction = City.BASE_SIEGE_RATE * (siege_pressure / (siege_pressure + city.defense_score * City.DEFENSE_SCALE))
resistance_loss = city.siege_resistance * loss_fraction
city.siege_resistance = max(0.0, city.siege_resistance - resistance_loss)
```
If `city.siege_resistance <= 0` after this: the city is **sacked**.
- `city.owner_id` becomes the besieging regiment's `owner_id`
- `city.population = round(city.population * (1 - City.SACK_POPULATION_PENALTY))`
- `city.siege_resistance = city.max_siege_resistance` (reset for the new owner)
- update the city's `symbol` the same way `mark_as_capital()` does, to reflect the new `owner_id`

**If not besieged:**
```
city.siege_resistance = min(city.max_siege_resistance, city.siege_resistance + City.SIEGE_REGEN_RATE * city.max_siege_resistance)
```

**Return value:** a dict with at least: `resistance_before`, `resistance_after`, `max_resistance`, and boolean `sacked` (plus `previous_owner_id` / `new_owner_id` if sacked).

---

## Constraints / things to avoid

- Don't touch `recalculate_attack_scores`, `_compute_weighted_score`, or any existing weight dicts.
- Don't wire these into the `player_loop()` menu or turn loop yet — just implement the two methods so they can be called/tested independently. I'll handle UI integration separately.
- Don't introduce randomness (no `random.random()` calls) — these formulas are meant to be deterministic; variance should come from card play, not dice.
