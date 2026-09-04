# main.py
import os
import sys
import math
import random
from pathlib import Path
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

class Player:

    MAX_HAND_SIZE = 5
    INITIAL_MATERIALS = {
        'coin': 180,
        'food': 90,
        'wood': 70,
        'stone': 30,
    }

    def __init__(self, id: int, name: str, color: str, controller_type: str = 'human'):
        self.id = id
        self.name = name
        self.color = color
        self.controller_type = controller_type
        self.deck = None
        self.hand = []
        self.active_card_effects = []
        self.card_play_lock_sources = 0
        self.materials = self._build_initial_materials()

    def initialize_cards(self, deck):
        self.deck = deck
        self.hand = []
        self.active_card_effects = []
        self.card_play_lock_sources = 0

    def _build_initial_materials(self):
        return {
            material: int(amount)
            for material, amount in self.INITIAL_MATERIALS.items()
        }

    def reset_materials(self):
        self.materials = self._build_initial_materials()

    def get_material(self, material_type: str):
        normalized_material = str(material_type).strip().lower()
        return int(self.materials.get(normalized_material, 0))

    def add_materials(self, delta: dict[str, int]):
        for material_type, amount in delta.items():
            normalized_material = str(material_type).strip().lower()
            self.materials[normalized_material] = max(
                0,
                self.get_material(normalized_material) + int(amount),
            )

    def can_afford(self, costs: dict[str, int]):
        return all(
            self.get_material(material_type) >= max(0, int(amount))
            for material_type, amount in costs.items()
        )

    def spend_materials(self, costs: dict[str, int]):
        normalized_costs = {
            str(material_type).strip().lower(): max(0, int(amount))
            for material_type, amount in costs.items()
            if int(amount) > 0
        }
        if not self.can_afford(normalized_costs):
            shortfalls = [
                f'{material_type}={amount - self.get_material(material_type)}'
                for material_type, amount in normalized_costs.items()
                if self.get_material(material_type) < amount
            ]
            raise ValueError(f'Cannot afford costs: {", ".join(shortfalls)}')
        for material_type, amount in normalized_costs.items():
            self.materials[material_type] = self.get_material(material_type) - amount

    def materials_summary(self):
        return ', '.join(
            f'{material_type.title()}={self.get_material(material_type)}'
            for material_type in ('coin', 'food', 'wood', 'stone')
        )

    def can_draw_card(self):
        return len(self.hand) < self.MAX_HAND_SIZE

    def can_play_cards(self):
        return self.card_play_lock_sources <= 0

    def hand_limit(self):
        return self.MAX_HAND_SIZE

class City:

    _city_symbols = {'City': 'C', 'Capital': '*C'}
    DEFAULT_LINE_OF_SIGHT_RADIUS = 3
    CAPITAL_LINE_OF_SIGHT_BONUS = 1
    DEFAULT_ATTACK_RADIUS = 1
    CAPITAL_ATTACK_RADIUS_BONUS = 1
    DEFAULT_INFLUENCE_ANCHORS = {0: 1.0, 1: 0.8, 2: 0.4, 3: 0.1}
    CAPITAL_INFLUENCE_ANCHORS = {0: 1.0, 1: 0.9, 2: 0.5, 3: 0.2, 4: 0.1}
    CITY_OCCUPATION_STABILIZATION_TURNS = 5
    CAPITAL_OCCUPATION_STABILIZATION_TURNS = 10
    OCCUPATION_INFLUENCE_FLOOR = 0.20
    CAPITAL_OCCUPATION_INFLUENCE_FLOOR = 0.10
    DEFAULT_ATTACK_SCALE = 0.75
    CAPITAL_ATTACK_SCALE = 0.85
    MIN_POST_CAPTURE_RECOVERY_TURNS = 3
    RESISTANCE_MULTIPLIER = 6.0
    DEFENSE_SCALE = 1.0
    BASE_SIEGE_RATE = 0.20
    SIEGE_REGEN_RATE = 0.15
    SACK_POPULATION_PENALTY = 0.30
    POST_CAPTURE_RESISTANCE_RATIO = 0.25
    MIN_LEVEL = 1
    MAX_LEVEL = 10
    LEVEL_XP_BASE = 140
    LEVEL_XP_GROWTH = 1.85
    LEVEL_DEFENSE_SCALING = 0.08
    LEVEL_INFLUENCE_SCALING = 0.04
    SOVEREIGNTY_XP_PER_TURN = 8

    def __init__(self, id: int, name: str, owner_id: int,
                 population: int = 1000, is_capital: bool = False,
                 defense_score: float = None, attack_score: float = None,
                 line_of_sight_radius: int = None, level: int = 1,
                 experience: int = 0):
        self.id = id
        self.name = name
        self.owner_id = owner_id
        self.population = population
        self.is_capital = is_capital
        self.level = self._validate_level(level)
        self.experience = max(
            self.experience_required_for_level(self.level),
            int(experience),
        )
        self.defense_score = defense_score if defense_score is not None else self._default_defense_score()
        self.attack_score = attack_score if attack_score is not None else self._default_attack_score()
        self.line_of_sight_radius = self._validate_line_of_sight_radius(
            self.DEFAULT_LINE_OF_SIGHT_RADIUS if line_of_sight_radius is None else line_of_sight_radius
        )
        self.influence_radius_bonus = 0
        self.influence_score_bonus = 0.0
        self.influence_score_multiplier = 1.0
        self.defense_score_bonus = 0.0
        self.attack_score_bonus = 0.0
        self.influence_profile_anchors = self._default_influence_anchors()
        self.max_siege_resistance = self._default_max_siege_resistance()
        self.siege_resistance = self.max_siege_resistance
        self.occupation_recovery_turns_remaining = 0
        self.occupation_recovery_total_turns = 0
        self.siege_repair_delay_turns_remaining = 0
        self.regiment_production_lock_turns_remaining = 0
        self.previous_owner_id = None
        self.queue_slot_bonus = 0
        self.production_speed_bonus = 0.0
        self.regiment_power_bonus = 0.0
        self.hero_access_bonus = 0
        self.resource_pull_bonus = 0.0
        self.navy_access_bonus = 0
        self.coin_income_bonus = 0.0
        self.food_income_bonus = 0.0
        self.wood_income_bonus = 0.0
        self.stone_income_bonus = 0.0
        self.food_growth_bonus = 0.0
        self.siege_resistance_bonus = 0.0
        self.pending_capture_level_penalty = False
        self._update_symbol()
        self.refresh_derived_stats(preserve_siege_ratio=False)

    def mark_as_capital(self):
        self.is_capital = True
        self.influence_profile_anchors = self._default_influence_anchors()
        self.refresh_derived_stats(preserve_siege_ratio=False)
        self._update_symbol()

    def _default_defense_score(self):
        # Population and capital status provide a simple defensive baseline.
        base_defense = 28 + (self.population / 160) + (14 if self.is_capital else 0)
        return round(base_defense * (1 + ((self.level - 1) * self.LEVEL_DEFENSE_SCALING)), 2)

    def _default_attack_score(self):
        scale = self.CAPITAL_ATTACK_SCALE if self.is_capital else self.DEFAULT_ATTACK_SCALE
        return round(self._default_defense_score() * scale, 2)

    def _default_max_siege_resistance(self):
        return round(
            (self.defense_score * self.RESISTANCE_MULTIPLIER) + getattr(self, 'siege_resistance_bonus', 0.0),
            2,
        )

    def _validate_line_of_sight_radius(self, radius: int):
        if not isinstance(radius, int) or radius < 0:
            raise ValueError('City line of sight radius must be a non-negative integer')
        return radius

    def _validate_level(self, level: int):
        if not isinstance(level, int):
            raise ValueError('City level must be an integer')
        if level < self.MIN_LEVEL or level > self.MAX_LEVEL:
            raise ValueError(f'City level must be between {self.MIN_LEVEL} and {self.MAX_LEVEL}')
        return level

    @classmethod
    def experience_required_for_level(cls, level: int):
        validated_level = max(cls.MIN_LEVEL, min(cls.MAX_LEVEL, int(level)))
        if validated_level <= cls.MIN_LEVEL:
            return 0
        required = 0
        for level_index in range(2, validated_level + 1):
            required += int(round(cls.LEVEL_XP_BASE * (cls.LEVEL_XP_GROWTH ** (level_index - 2))))
        return required

    def _determine_level_from_experience(self):
        resolved_level = self.MIN_LEVEL
        for candidate_level in range(self.MIN_LEVEL, self.MAX_LEVEL + 1):
            if self.experience >= self.experience_required_for_level(candidate_level):
                resolved_level = candidate_level
            else:
                break
        return resolved_level

    def refresh_derived_stats(self, preserve_siege_ratio: bool = True):
        existing_ratio = 1.0
        if preserve_siege_ratio and getattr(self, 'max_siege_resistance', 0) > 0:
            existing_ratio = self.siege_resistance / self.max_siege_resistance
        self.defense_score = self._default_defense_score()
        self.attack_score = self._default_attack_score()
        self.max_siege_resistance = self._default_max_siege_resistance()
        if preserve_siege_ratio:
            self.siege_resistance = round(
                max(0.0, min(self.max_siege_resistance, self.max_siege_resistance * existing_ratio)),
                2,
            )
        else:
            self.siege_resistance = self.max_siege_resistance

    def add_experience(self, amount: int):
        experience_gain = max(0, int(amount))
        if experience_gain <= 0:
            return {'experience_gained': 0, 'level_before': self.level, 'level_after': self.level}
        level_before = self.level
        self.experience += experience_gain
        self.level = self._determine_level_from_experience()
        if self.level != level_before:
            self.refresh_derived_stats()
        return {
            'experience_gained': experience_gain,
            'level_before': level_before,
            'level_after': self.level,
        }

    def set_level(self, level: int, reset_experience_to_floor: bool = True):
        resolved_level = self._validate_level(level)
        level_before = self.level
        self.level = resolved_level
        if reset_experience_to_floor or self.experience < self.experience_required_for_level(resolved_level):
            self.experience = self.experience_required_for_level(resolved_level)
        if self.level != level_before:
            self.refresh_derived_stats()

    def level_bonus_radius(self):
        return (self.level - 1) // 3

    def level_bonus_queue_slots(self):
        return 1 if self.level >= 4 else 0

    def level_bonus_attack_radius(self):
        return 1 if self.level >= 7 else 0

    def queue_capacity(self):
        return max(1, 1 + self.level_bonus_queue_slots() + self.queue_slot_bonus + (1 if self.level >= 8 else 0))

    def production_turn_multiplier(self):
        return max(0.45, 1.0 - self.production_speed_bonus - (0.03 * max(0, self.level - 1)))

    def can_train_heroes(self):
        return self.level >= 5 or self.hero_access_bonus > 0

    def has_navy_access(self):
        return self.navy_access_bonus > 0

    def apply_population_growth(self, amount: int):
        growth = max(0, int(amount))
        if growth <= 0:
            return {'population_before': self.population, 'population_after': self.population, 'growth': 0}
        population_before = self.population
        self.population += growth
        self.refresh_derived_stats()
        self.add_experience(max(1, growth // 6))
        return {
            'population_before': population_before,
            'population_after': self.population,
            'growth': growth,
        }

    def _default_influence_anchors(self):
        return dict(
            self.CAPITAL_INFLUENCE_ANCHORS if self.is_capital else self.DEFAULT_INFLUENCE_ANCHORS
        )

    def effective_line_of_sight_radius(self):
        full_radius = max(
            0,
            self.line_of_sight_radius +
            self.influence_radius_bonus +
            self.level_bonus_radius() +
            (self.CAPITAL_LINE_OF_SIGHT_BONUS if self.is_capital else 0),
        )
        occupation_multiplier = self.occupation_influence_multiplier()
        if occupation_multiplier >= 1.0:
            return full_radius
        if full_radius == 0:
            return 0
        return max(1, math.ceil(full_radius * occupation_multiplier))

    def effective_attack_radius(self):
        return max(
            1,
            self.DEFAULT_ATTACK_RADIUS +
            self.level_bonus_attack_radius() +
            (self.CAPITAL_ATTACK_RADIUS_BONUS if self.is_capital else 0),
        )

    def occupation_stabilization_turns(self):
        return (
            self.CAPITAL_OCCUPATION_STABILIZATION_TURNS
            if self.is_capital else self.CITY_OCCUPATION_STABILIZATION_TURNS
        )

    def occupation_influence_floor(self):
        return (
            self.CAPITAL_OCCUPATION_INFLUENCE_FLOOR
            if self.is_capital else self.OCCUPATION_INFLUENCE_FLOOR
        )

    def occupation_influence_multiplier(self):
        if self.occupation_recovery_turns_remaining <= 0 or self.occupation_recovery_total_turns <= 0:
            return 1.0
        progress = (
            (self.occupation_recovery_total_turns - self.occupation_recovery_turns_remaining) /
            self.occupation_recovery_total_turns
        )
        return round(
            self.occupation_influence_floor() +
            ((1.0 - self.occupation_influence_floor()) * max(0.0, min(1.0, progress))),
            4,
        )

    def get_influence_profile(self):
        return self._build_influence_profile(
            self.effective_line_of_sight_radius(),
            self.influence_profile_anchors,
        )

    def get_influence_at_distance(self, distance: int):
        if not isinstance(distance, int) or distance < 0:
            raise ValueError('Influence distance must be a non-negative integer')

        influence_profile = self.get_influence_profile()
        base_score = influence_profile.get(distance, 0.0)
        modified_score = (
            (base_score + self.influence_score_bonus) *
            self.influence_score_multiplier *
            (1.0 + (self.LEVEL_INFLUENCE_SCALING * max(0, self.level - 1))) *
            self.occupation_influence_multiplier()
        )
        return max(0.0, min(1.0, round(modified_score, 4)))

    def effective_defense_score(self):
        return round(max(0.0, self.defense_score + self.defense_score_bonus), 2)

    def effective_attack_score(self):
        return round(max(0.0, self.attack_score + self.attack_score_bonus), 2)

    def compute_post_capture_recovery_turns(self, total_influence_score: float, max_influence_score: float):
        if max_influence_score <= 0:
            return self.MIN_POST_CAPTURE_RECOVERY_TURNS
        normalized_influence = max(0.0, min(1.0, total_influence_score / max_influence_score))
        base_turns = self.occupation_stabilization_turns()
        return max(
            self.MIN_POST_CAPTURE_RECOVERY_TURNS,
            int(math.ceil(base_turns - ((base_turns - self.MIN_POST_CAPTURE_RECOVERY_TURNS) * normalized_influence))),
        )

    def begin_occupation(self, new_owner_id: int):
        self.previous_owner_id = self.owner_id
        self.owner_id = new_owner_id
        self.population = max(1, round(self.population * (1 - self.SACK_POPULATION_PENALTY)))
        self.occupation_recovery_total_turns = self.occupation_stabilization_turns()
        self.occupation_recovery_turns_remaining = self.occupation_recovery_total_turns
        self.refresh_derived_stats(preserve_siege_ratio=False)
        self.siege_resistance = round(self.max_siege_resistance * self.POST_CAPTURE_RESISTANCE_RATIO, 2)
        self.siege_repair_delay_turns_remaining = self.occupation_stabilization_turns()
        self.regiment_production_lock_turns_remaining = self.occupation_stabilization_turns()
        self.pending_capture_level_penalty = True
        self._update_symbol()

    def update_post_capture_cooldowns(self, total_influence_score: float, max_influence_score: float):
        recovery_turns = self.compute_post_capture_recovery_turns(total_influence_score, max_influence_score)
        self.siege_repair_delay_turns_remaining = recovery_turns
        self.regiment_production_lock_turns_remaining = recovery_turns
        return recovery_turns

    def can_queue_regiment(self):
        return self.regiment_production_lock_turns_remaining <= 0

    def grant_sovereignty_experience(self, under_enemy_pressure: bool = False):
        if self.occupation_recovery_turns_remaining > 0:
            return {'experience_gained': 0, 'level_before': self.level, 'level_after': self.level}
        if under_enemy_pressure:
            return {'experience_gained': 0, 'level_before': self.level, 'level_after': self.level}
        return self.add_experience(self.SOVEREIGNTY_XP_PER_TURN + max(0, self.level - 1))

    def progress_turn_state(self, under_enemy_pressure: bool = False):
        level_penalty_applied = False
        level_before_penalty = self.level
        if not under_enemy_pressure:
            if self.occupation_recovery_turns_remaining > 0:
                self.occupation_recovery_turns_remaining -= 1
            if self.siege_repair_delay_turns_remaining > 0:
                self.siege_repair_delay_turns_remaining -= 1
            elif self.siege_resistance < self.max_siege_resistance:
                self.siege_resistance = round(
                    min(
                        self.max_siege_resistance,
                        self.siege_resistance + (self.SIEGE_REGEN_RATE * self.max_siege_resistance),
                    ),
                    2,
                )
            if self.regiment_production_lock_turns_remaining > 0:
                self.regiment_production_lock_turns_remaining -= 1
            if self.pending_capture_level_penalty and self.occupation_recovery_turns_remaining <= 0:
                self.set_level(max(self.MIN_LEVEL, self.level - 2))
                self.pending_capture_level_penalty = False
                level_penalty_applied = True
        return {
            'city_id': self.id,
            'under_enemy_pressure': under_enemy_pressure,
            'siege_resistance': self.siege_resistance,
            'occupation_recovery_turns_remaining': self.occupation_recovery_turns_remaining,
            'siege_repair_delay_turns_remaining': self.siege_repair_delay_turns_remaining,
            'regiment_production_lock_turns_remaining': self.regiment_production_lock_turns_remaining,
            'level': self.level,
            'experience': self.experience,
            'capture_level_penalty_applied': level_penalty_applied,
            'level_before_penalty': level_before_penalty,
        }

    @staticmethod
    def _build_influence_profile(max_radius: int, anchors: dict[int, float]):
        if max_radius < 0:
            return {}

        normalized_anchors = {
            distance: max(0.0, min(1.0, float(score)))
            for distance, score in anchors.items()
            if isinstance(distance, int) and distance >= 0
        }
        if 0 not in normalized_anchors:
            normalized_anchors[0] = 1.0

        anchor_distances = sorted(normalized_anchors)
        last_anchor_distance = anchor_distances[-1]
        last_anchor_value = normalized_anchors[last_anchor_distance]
        profile = {}

        for distance in range(max_radius + 1):
            if distance in normalized_anchors:
                profile[distance] = round(normalized_anchors[distance], 4)
                continue

            lower_distance = max(d for d in anchor_distances if d < distance)
            upper_candidates = [d for d in anchor_distances if d > distance]
            if upper_candidates:
                upper_distance = min(upper_candidates)
                lower_position = math.log(lower_distance + 1)
                upper_position = math.log(upper_distance + 1)
                current_position = math.log(distance + 1)
                if math.isclose(lower_position, upper_position):
                    interpolated = normalized_anchors[lower_distance]
                else:
                    interpolation_ratio = (
                        (current_position - lower_position) /
                        (upper_position - lower_position)
                    )
                    interpolated = normalized_anchors[lower_distance] + (
                        (normalized_anchors[upper_distance] - normalized_anchors[lower_distance]) *
                        interpolation_ratio
                    )
            else:
                tail_distance = distance - last_anchor_distance
                interpolated = last_anchor_value / (1 + math.log(tail_distance + 1, 2))

            profile[distance] = round(max(0.0, min(1.0, interpolated)), 4)
        return profile

    def _update_symbol(self):
        self.symbol = f'{"*C" if self.is_capital else "C"}{self.id}({self.owner_id})'

class Tile:

    _allowable_types = {
        'grass':    {'passable_foot': True,  'passable_water': False, 'symbol': '.'},
        'water':    {'passable_foot': False, 'passable_water': True,  'symbol': '~'},
        'mountain': {'passable_foot': False, 'passable_water': False, 'symbol': '^'},
        'forest':   {'passable_foot': True,  'passable_water': False, 'symbol': '%'},
        'hill':     {'passable_foot': True,  'passable_water': False, 'symbol': 'n'},
    }

    def __init__(self, type: str = 'grass', x: int = None, y: int = None,
                 regiment_id: int = None, city_id: int = None,
                 resource_id: int = None, improvement_id: int = None):
        if type not in Tile._allowable_types.keys():
            raise ValueError(f'Invalid tile type: {type}')
        self.type = type
        self.x = x
        self.y = y
        self.regiment_id = regiment_id
        self.city_id = city_id
        self.resource_id = resource_id
        self.improvement_id = improvement_id
        self.passable_foot = self._allowable_types[type]['passable_foot']
        self.passable_water = self._allowable_types[type]['passable_water']
        self.symbol = self._allowable_types[type]['symbol']
        self.influence_scores: dict[int, float] = {}
        self.influence_owner_id: int | None = None
        self.is_influence_contested = False

class ResourceDefinition:

    def __init__(self, resource_type: str, name: str, symbol: str,
                 terrain_types: set[str], material_bonus: dict[str, int] = None,
                 city_bonuses: dict[str, float] = None):
        self.resource_type = str(resource_type).strip().lower()
        self.name = str(name).strip()
        self.symbol = str(symbol).strip()
        self.terrain_types = set(terrain_types)
        self.material_bonus = dict(material_bonus) if material_bonus is not None else {}
        self.city_bonuses = dict(city_bonuses) if city_bonuses is not None else {}

class Resource:

    DEFINITIONS: dict[str, ResourceDefinition] = {}
    SPAWN_TABLE = {
        'grass': (
            (0.10, 'wheat'),
            (0.17, 'horses'),
            (0.20, 'gems'),
        ),
        'hill': (
            (0.08, 'wheat'),
            (0.16, 'horses'),
            (0.25, 'iron'),
            (0.32, 'stone_vein'),
        ),
        'forest': (
            (0.18, 'timber'),
            (0.22, 'gems'),
        ),
        'mountain': (
            (0.16, 'iron'),
            (0.25, 'stone_vein'),
            (0.30, 'gems'),
        ),
        'water': (
            (0.16, 'fish'),
            (0.22, 'pearls'),
        ),
    }

    @classmethod
    def initialize_definitions(cls):
        if cls.DEFINITIONS:
            return
        definitions = [
            ResourceDefinition('wheat', 'Wheat', 'Wh', {'grass', 'hill'}, {'food': 3}, {'resource_pull_bonus': 0.08}),
            ResourceDefinition('horses', 'Horses', 'Ho', {'grass', 'hill'}, {'food': 1}, {'regiment_power_bonus': 0.06}),
            ResourceDefinition('timber', 'Timber', 'Ti', {'forest'}, {'wood': 3}, {'resource_pull_bonus': 0.06}),
            ResourceDefinition('iron', 'Iron', 'Ir', {'hill', 'mountain'}, {'stone': 1}, {'regiment_power_bonus': 0.08}),
            ResourceDefinition('stone_vein', 'Stone Vein', 'St', {'hill', 'mountain'}, {'stone': 2}, {'defense_bonus': 4}),
            ResourceDefinition('fish', 'Fish', 'Fi', {'water'}, {'food': 2}, {'food_growth_bonus': 0.05}),
            ResourceDefinition('pearls', 'Pearls', 'Pe', {'water'}, {'coin': 3}, {'card_purchase_tier_bonus': 1}),
            ResourceDefinition('gems', 'Gems', 'Ge', {'grass', 'hill', 'mountain', 'forest'}, {'coin': 4}, {'card_purchase_tier_bonus': 1}),
        ]
        cls.DEFINITIONS = {
            definition.resource_type: definition
            for definition in definitions
        }

    @classmethod
    def choose_for_tile(cls, tile_type: str, rng):
        cls.initialize_definitions()
        entries = cls.SPAWN_TABLE.get(tile_type, ())
        if not entries:
            return None
        roll = rng.random()
        for threshold, resource_type in entries:
            if roll <= threshold:
                return resource_type
        return None

    def __init__(self, resource_type: str, id: int = None):
        Resource.initialize_definitions()
        normalized_resource_type = str(resource_type).strip().lower()
        if normalized_resource_type not in self.DEFINITIONS:
            raise ValueError(f'Unsupported resource type: {resource_type}')
        self.id = id
        self.resource_type = normalized_resource_type
        self.definition = self.DEFINITIONS[normalized_resource_type]
        self.name = self.definition.name
        self.symbol = self.definition.symbol

class ImprovementDefinition:

    def __init__(self, improvement_kind: str, name: str, symbol: str,
                 intra_city: bool, build_turns: int, costs: dict[str, int],
                 min_city_level: int = 1, required_tile_types: set[str] = None,
                 requires_adjacent_water: bool = False, bonuses: dict[str, float] = None,
                 city_xp_reward: int = 0, max_per_city: int | None = None):
        self.improvement_kind = str(improvement_kind).strip().lower()
        self.name = str(name).strip()
        self.symbol = str(symbol).strip()
        self.intra_city = bool(intra_city)
        self.build_turns = max(1, int(build_turns))
        self.costs = {
            str(material_type).strip().lower(): max(0, int(amount))
            for material_type, amount in costs.items()
        }
        self.min_city_level = max(1, int(min_city_level))
        self.required_tile_types = set(required_tile_types) if required_tile_types is not None else set()
        self.requires_adjacent_water = bool(requires_adjacent_water)
        self.bonuses = dict(bonuses) if bonuses is not None else {}
        self.city_xp_reward = max(0, int(city_xp_reward))
        self.max_per_city = None if max_per_city is None else max(1, int(max_per_city))

class Improvement:

    DEFINITIONS: dict[str, ImprovementDefinition] = {}

    @classmethod
    def initialize_definitions(cls):
        if cls.DEFINITIONS:
            return
        definitions = [
            ImprovementDefinition(
                'granary', 'Granary', 'Gr', True, 2, {'coin': 35, 'wood': 10},
                min_city_level=1,
                bonuses={'food_growth_bonus': 0.18, 'resource_pull_bonus': 0.08, 'food_income_bonus': 0.10},
                city_xp_reward=55, max_per_city=1,
            ),
            ImprovementDefinition(
                'market', 'Market', 'Mk', True, 3, {'coin': 50, 'wood': 15},
                min_city_level=2,
                bonuses={'coin_income_bonus': 0.20, 'influence_multiplier_bonus': 0.05},
                city_xp_reward=70, max_per_city=1,
            ),
            ImprovementDefinition(
                'barracks', 'Barracks', 'Ba', True, 3, {'coin': 60, 'wood': 20, 'stone': 10},
                min_city_level=2,
                bonuses={'production_speed_bonus': 0.15, 'regiment_power_bonus': 0.12, 'hero_access_bonus': 1},
                city_xp_reward=85, max_per_city=1,
            ),
            ImprovementDefinition(
                'walls', 'Walls', 'Wa', True, 4, {'coin': 70, 'stone': 24},
                min_city_level=4,
                bonuses={'defense_bonus': 18, 'siege_resistance_bonus': 80},
                city_xp_reward=95, max_per_city=1,
            ),
            ImprovementDefinition(
                'castle', 'Castle', 'Ca', True, 5, {'coin': 110, 'wood': 25, 'stone': 40},
                min_city_level=6,
                bonuses={
                    'defense_bonus': 28,
                    'attack_bonus': 15,
                    'queue_slot_bonus': 1,
                    'production_speed_bonus': 0.10,
                    'hero_access_bonus': 1,
                    'coin_income_bonus': 0.10,
                },
                city_xp_reward=135, max_per_city=1,
            ),
            ImprovementDefinition(
                'watchtower', 'Watchtower', 'Wt', False, 2, {'coin': 30, 'wood': 16},
                min_city_level=2, required_tile_types={'grass', 'hill', 'forest'},
                bonuses={'influence_radius_bonus': 1, 'influence_multiplier_bonus': 0.03},
                city_xp_reward=45, max_per_city=1,
            ),
            ImprovementDefinition(
                'farm', 'Farm', 'Fa', False, 2, {'coin': 25, 'wood': 10},
                min_city_level=1, required_tile_types={'grass', 'hill'},
                bonuses={'food_income_flat': 4, 'resource_pull_bonus': 0.10},
                city_xp_reward=45, max_per_city=None,
            ),
            ImprovementDefinition(
                'lumber_mill', 'Lumber Mill', 'Lu', False, 2, {'coin': 25, 'wood': 8},
                min_city_level=1, required_tile_types={'forest'},
                bonuses={'wood_income_flat': 4},
                city_xp_reward=45, max_per_city=None,
            ),
            ImprovementDefinition(
                'quarry', 'Quarry', 'Qu', False, 3, {'coin': 40, 'wood': 10},
                min_city_level=3, required_tile_types={'hill', 'mountain'},
                bonuses={'stone_income_flat': 4},
                city_xp_reward=65, max_per_city=None,
            ),
            ImprovementDefinition(
                'port', 'Port', 'Po', False, 3, {'coin': 55, 'wood': 28},
                min_city_level=2, required_tile_types={'grass', 'hill', 'forest'},
                requires_adjacent_water=True,
                bonuses={'navy_access_bonus': 1, 'production_speed_bonus': 0.05, 'hero_access_bonus': 1},
                city_xp_reward=75, max_per_city=1,
            ),
        ]
        cls.DEFINITIONS = {
            definition.improvement_kind: definition
            for definition in definitions
        }

    def __init__(self, improvement_kind: str, city_id: int, owner_id: int,
                 id: int = None, tile_pos: tuple[int, int] = None):
        Improvement.initialize_definitions()
        normalized_kind = str(improvement_kind).strip().lower()
        if normalized_kind not in self.DEFINITIONS:
            raise ValueError(f'Unsupported improvement kind: {improvement_kind}')
        self.id = id
        self.improvement_kind = normalized_kind
        self.definition = self.DEFINITIONS[normalized_kind]
        self.city_id = city_id
        self.owner_id = owner_id
        self.tile_pos = tuple(tile_pos) if tile_pos is not None else None
        self.name = self.definition.name
        self.symbol = self.definition.symbol
        self.is_destroyed = False

    def is_intra_city(self):
        return self.definition.intra_city

    def is_extra_city(self):
        return not self.definition.intra_city

    def is_port(self):
        return self.improvement_kind == 'port'

    def apply_to_city(self, city: City, reverse: bool = False):
        direction = -1 if reverse else 1
        for bonus_name, value in self.definition.bonuses.items():
            scaled_value = value * direction
            if bonus_name == 'influence_multiplier_bonus':
                city.influence_score_multiplier = max(
                    0.0,
                    round(city.influence_score_multiplier + scaled_value, 4),
                )
                continue
            if bonus_name == 'defense_bonus':
                city.defense_score_bonus += scaled_value
                continue
            if bonus_name == 'attack_bonus':
                city.attack_score_bonus += scaled_value
                continue
            if bonus_name == 'siege_resistance_bonus':
                city.siege_resistance_bonus += scaled_value
                city.refresh_derived_stats()
                continue
            if hasattr(city, bonus_name):
                current_value = getattr(city, bonus_name)
                updated_value = current_value + scaled_value
                if isinstance(current_value, int):
                    updated_value = int(round(updated_value))
                elif isinstance(current_value, float):
                    updated_value = round(updated_value, 4)
                setattr(city, bonus_name, updated_value)

class Card:

    _next_instance_id = 1

    def __init__(self, definition):
        self.instance_id = Card._next_instance_id
        Card._next_instance_id += 1
        self.definition = definition

    def label(self):
        return f'[{self.instance_id}] {self.definition.name}'

class CardEffectDefinition:

    def __init__(self, effect_type: str, magnitude = None,
                 duration_turns: int = 0, metadata: dict | None = None):
        self.effect_type = str(effect_type).strip()
        self.magnitude = magnitude
        self.duration_turns = max(0, int(duration_turns))
        self.metadata = dict(metadata) if metadata is not None else {}

class CardDefinition:

    def __init__(self, card_id: str, name: str, rarity: str, card_type: str,
                 target_scope: str, effects: list[CardEffectDefinition],
                 description: str, deck_weight: int = 1, grant_weight: int = None):
        self.card_id = str(card_id).strip()
        self.name = str(name).strip()
        self.rarity = str(rarity).strip().lower()
        self.card_type = str(card_type).strip().lower()
        self.target_scope = str(target_scope).strip().lower()
        self.effects = list(effects)
        self.description = str(description).strip()
        self.deck_weight = max(0, int(deck_weight))
        self.grant_weight = max(0, int(grant_weight if grant_weight is not None else max(1, deck_weight)))

class Deck:

    def __init__(self, cards: list[Card] = None, reshuffle_enabled: bool = False, rng = None):
        self.draw_pile = list(cards) if cards is not None else []
        self.discard_pile = []
        self.exhausted_pile = []
        self.reshuffle_enabled = bool(reshuffle_enabled)
        self.rng = rng if rng is not None else random

    def cards_remaining(self):
        return len(self.draw_pile)

    def draw(self):
        if not self.draw_pile and self.reshuffle_enabled and self.discard_pile:
            self.rng.shuffle(self.discard_pile)
            self.draw_pile = self.discard_pile
            self.discard_pile = []
        if not self.draw_pile:
            return None
        return self.draw_pile.pop()

    def discard(self, card: Card):
        self.discard_pile.append(card)

    def exhaust(self, card: Card):
        self.exhausted_pile.append(card)

    def add_to_top(self, card: Card):
        self.draw_pile.append(card)

    def add_to_discard(self, card: Card):
        self.discard_pile.append(card)

    def peek_top(self, count: int):
        if count <= 0:
            return []
        return list(reversed(self.draw_pile[-count:]))

    def remove_card(self, card: Card):
        for pile in (self.draw_pile, self.discard_pile, self.exhausted_pile):
            if card in pile:
                pile.remove(card)
                return True
        return False

class ActiveCardEffect:

    _next_effect_id = 1

    def __init__(self, source_player_id: int, host_player_id: int,
                 card: Card, target_kind: str, target_id: int | None,
                 effect: CardEffectDefinition):
        self.effect_id = ActiveCardEffect._next_effect_id
        ActiveCardEffect._next_effect_id += 1
        self.source_player_id = source_player_id
        self.host_player_id = host_player_id
        self.card_instance_id = card.instance_id
        self.card_name = card.definition.name
        self.target_kind = target_kind
        self.target_id = target_id
        self.effect_type = effect.effect_type
        self.magnitude = effect.magnitude
        self.turns_remaining = effect.duration_turns
        self.metadata = dict(effect.metadata)

class CardLibrary:

    RARITY_ORDER = {'common': 0, 'uncommon': 1, 'rare': 2, 'legendary': 3}
    RARITY_COLORS = {
        'common': Fore.GREEN,
        'uncommon': Fore.BLUE,
        'rare': Fore.MAGENTA,
        'legendary': Fore.YELLOW,
    }

    def __init__(self):
        self.definitions = {}
        for definition in self._build_definitions():
            self.definitions[definition.card_id] = definition

    def _build_definitions(self):
        definitions = []

        def add(card_id: str, name: str, rarity: str, card_type: str,
                target_scope: str, description: str, deck_weight: int,
                effects: list[CardEffectDefinition], grant_weight: int = None):
            definitions.append(CardDefinition(
                card_id=card_id,
                name=name,
                rarity=rarity,
                card_type=card_type,
                target_scope=target_scope,
                effects=effects,
                description=description,
                deck_weight=deck_weight,
                grant_weight=grant_weight,
            ))

        add(
            'battle_drill', 'Battle Drill', 'common', 'duration', 'own_regiment',
            'Boost one friendly regiment\'s attack and defense for 2 turns.',
            12,
            [
                CardEffectDefinition('regiment_attack_bonus', magnitude=18, duration_turns=2),
                CardEffectDefinition('regiment_defense_bonus', magnitude=14, duration_turns=2),
            ],
        )
        add(
            'crippling_mud', 'Crippling Mud', 'common', 'duration', 'enemy_regiment',
            'Reduce one enemy regiment\'s attack and defense for 2 turns.',
            11,
            [
                CardEffectDefinition('regiment_attack_bonus', magnitude=-18, duration_turns=2),
                CardEffectDefinition('regiment_defense_bonus', magnitude=-14, duration_turns=2),
            ],
        )
        add(
            'watchtowers', 'Watchtowers', 'common', 'duration', 'own_city',
            'Increase one friendly city\'s defense for 2 turns.',
            11,
            [CardEffectDefinition('city_defense_bonus', magnitude=20, duration_turns=2)],
        )
        add(
            'sapper_ring', 'Sapper Ring', 'common', 'duration', 'enemy_city',
            'Reduce one enemy city\'s defense for 2 turns.',
            10,
            [CardEffectDefinition('city_defense_bonus', magnitude=-20, duration_turns=2)],
        )
        add(
            'inspiring_banner', 'Inspiring Banner', 'common', 'duration', 'own_regiment',
            'Increase one friendly regiment\'s influence for 2 turns.',
            10,
            [CardEffectDefinition('regiment_influence_multiplier_bonus', magnitude=0.25, duration_turns=2)],
        )
        add(
            'fear_campaign', 'Fear Campaign', 'common', 'duration', 'enemy_regiment',
            'Reduce one enemy regiment\'s influence for 2 turns.',
            10,
            [CardEffectDefinition('regiment_influence_multiplier_bonus', magnitude=-0.25, duration_turns=2)],
        )
        add(
            'harvest_festival', 'Harvest Festival', 'common', 'duration', 'own_city',
            'Increase one friendly city\'s influence for 2 turns.',
            10,
            [CardEffectDefinition('city_influence_multiplier_bonus', magnitude=0.20, duration_turns=2)],
        )
        add(
            'civic_unrest', 'Civic Unrest', 'common', 'duration', 'enemy_city',
            'Reduce one enemy city\'s influence for 2 turns.',
            9,
            [CardEffectDefinition('city_influence_multiplier_bonus', magnitude=-0.20, duration_turns=2)],
        )
        add(
            'forced_march', 'Forced March', 'uncommon', 'duration', 'own_regiment',
            'A regiment keeps its movement after attack, defend, or split for 2 turns.',
            7,
            [CardEffectDefinition('regiment_move_after_action', magnitude=1, duration_turns=2)],
        )
        add(
            'pinning_fire', 'Pinning Fire', 'uncommon', 'duration', 'enemy_regiment',
            'Prevent one enemy regiment from moving for 2 turns.',
            7,
            [CardEffectDefinition('regiment_movement_lock', magnitude=1, duration_turns=2)],
        )
        add(
            'flurry_orders', 'Flurry Orders', 'uncommon', 'duration', 'own_regiment',
            'Allow one regiment to attack an additional time each turn for 2 turns.',
            6,
            [CardEffectDefinition('regiment_extra_attack_bonus', magnitude=1, duration_turns=2)],
        )
        add(
            'rapid_withdrawal', 'Rapid Withdrawal', 'rare', 'immediate', 'own_regiment',
            'Allow one regiment to keep movement after its next attack, defend, or split.',
            3,
            [CardEffectDefinition('grant_move_after_action_charge', magnitude=1)],
        )
        add(
            'mountain_pass', 'Mountain Pass', 'uncommon', 'immediate', 'own_regiment',
            'Grant one regiment a one-time ability to traverse impassable land terrain.',
            5,
            [CardEffectDefinition('grant_terrain_boundary_pass', magnitude=1)],
        )
        add(
            'heroic_volunteer', 'Heroic Volunteer', 'rare', 'immediate', 'own_regiment',
            'Permanently add a hero to one friendly regiment.',
            3,
            [CardEffectDefinition('add_regiment_hero', magnitude=1)],
        )
        add(
            'assassination', 'Assassination', 'rare', 'immediate', 'enemy_regiment',
            'Kill one hero in an enemy regiment.',
            3,
            [CardEffectDefinition('remove_regiment_hero', magnitude=1)],
        )
        add(
            'expansion_charter', 'Expansion Charter', 'rare', 'immediate', 'own_city',
            'Permanently increase one city\'s influence radius and influence strength.',
            2,
            [CardEffectDefinition(
                'modify_city_radius_and_influence',
                magnitude=1,
                metadata={'influence_multiplier_bonus': 0.20},
            )],
        )
        add(
            'border_crackdown', 'Border Crackdown', 'rare', 'immediate', 'enemy_city',
            'Permanently reduce one enemy city\'s influence radius and influence strength.',
            2,
            [CardEffectDefinition(
                'modify_city_radius_and_influence',
                magnitude=-1,
                metadata={'influence_multiplier_bonus': -0.20},
            )],
        )
        add(
            'levy_enlistment', 'Levy Enlistment', 'rare', 'immediate', 'own_regiment',
            'Permanently add units of a chosen type to one friendly regiment.',
            3,
            [CardEffectDefinition('modify_regiment_units', magnitude=6, metadata={'unit_choice_required': True})],
        )
        add(
            'supply_attrition', 'Supply Attrition', 'rare', 'immediate', 'enemy_regiment',
            'Permanently remove units of a chosen type from one enemy regiment.',
            3,
            [CardEffectDefinition('modify_regiment_units', magnitude=-4, metadata={'unit_choice_required': True})],
        )
        add(
            'sudden_insight', 'Sudden Insight', 'uncommon', 'immediate', 'self',
            'Draw 2 extra cards.',
            6,
            [CardEffectDefinition('draw_cards', magnitude=2)],
        )
        add(
            'strategic_search', 'Strategic Search', 'uncommon', 'immediate', 'self',
            'Choose 1 card from the top 8 cards of your deck.',
            5,
            [CardEffectDefinition('choose_from_top_cards', magnitude=8)],
        )
        add(
            'treasure_hoard', 'Treasure Hoard', 'rare', 'immediate', 'self',
            'Gain a random card of a chosen rarity above Common.',
            3,
            [CardEffectDefinition('gain_random_card_by_rarity', magnitude=1, metadata={'allowable_rarities': ['uncommon', 'rare', 'legendary']})],
        )
        add(
            'silence_the_court', 'Silence the Court', 'rare', 'duration', 'enemy_player',
            'Prevent one opponent from playing cards for 2 turns.',
            3,
            [CardEffectDefinition('player_card_play_lock', magnitude=1, duration_turns=2)],
        )
        add(
            'war_council', 'War Council', 'uncommon', 'immediate', 'self',
            'Discard your hand and redraw up to 5 cards.',
            4,
            [CardEffectDefinition('discard_hand_and_redraw', magnitude=5)],
        )
        add(
            'imperial_edict', 'Imperial Edict', 'legendary', 'immediate', 'own_regiment',
            'Permanently add a large number of chosen units to a friendly regiment.',
            0,
            [CardEffectDefinition('modify_regiment_units', magnitude=10, metadata={'unit_choice_required': True})],
            grant_weight=2,
        )
        add(
            'grand_design', 'Grand Design', 'legendary', 'immediate', 'own_city',
            'Permanently grant a large city influence expansion.',
            0,
            [CardEffectDefinition(
                'modify_city_radius_and_influence',
                magnitude=2,
                metadata={'influence_multiplier_bonus': 0.35},
            )],
            grant_weight=2,
        )
        return definitions

    def get_definition(self, card_id: str):
        return self.definitions.get(card_id)

    def build_random_deck(self, deck_size: int = 50, rng = None, reshuffle_enabled: bool = False):
        rng = rng if rng is not None else random
        eligible_definitions = [definition for definition in self.definitions.values() if definition.deck_weight > 0]
        if not eligible_definitions:
            raise ValueError('No card definitions are available to build a deck')
        chosen_definitions = rng.choices(
            population=eligible_definitions,
            weights=[definition.deck_weight for definition in eligible_definitions],
            k=max(0, int(deck_size)),
        )
        cards = [Card(definition) for definition in chosen_definitions]
        rng.shuffle(cards)
        return Deck(cards=cards, reshuffle_enabled=reshuffle_enabled, rng=rng)

    def build_random_card_of_rarity(self, rarity: str, rng = None):
        rarity_name = str(rarity).strip().lower()
        rng = rng if rng is not None else random
        eligible_definitions = [
            definition for definition in self.definitions.values()
            if definition.rarity == rarity_name and definition.grant_weight > 0
        ]
        if not eligible_definitions:
            raise ValueError(f'No cards are available for rarity "{rarity_name}"')
        chosen_definition = rng.choices(
            population=eligible_definitions,
            weights=[definition.grant_weight for definition in eligible_definitions],
            k=1,
        )[0]
        return Card(chosen_definition)

class Regiment:

    REGIMENT_ATTACK_WEIGHTS = {
        'infantry': 1.0,
        'ranged': 0.85,
        'cavalry': 1.15,
        'navy': 1.45,
    }
    REGIMENT_DEFENSE_WEIGHTS = {
        'infantry': 1.15,
        'ranged': 0.95,
        'cavalry': 1.0,
        'navy': 1.4,
    }
    BASE_BATTLE_RATE = 0.25
    FORCE_SIZE_EXPONENT = 0.5
    RANGED_ATTACK_RADIUS = 2
    DEFAULT_LINE_OF_SIGHT_RADIUS = 1
    TILE_INFLUENCE_SCORE = 1.0
    CITY_INFLUENCE_SUPPORT_BONUS = 0.25
    CITY_INFLUENCE_DISRUPTION_PENALTY = 0.25
    HERO_INFLUENCE_BONUS = 0.25
    HERO_INFLUENCE_RADIUS = 1
    DEFENDING_ATTACK_MULTIPLIER = 0.75
    DEFENDING_DEFENSE_MULTIPLIER = 1.25
    DEFENSE_SCORE_SCALE = 100.0
    MIN_LEVEL = 1
    MAX_LEVEL = 10
    LEVEL_XP_BASE = 55
    LEVEL_XP_GROWTH = 1.90
    LEVEL_SCORE_SCALING = 0.07
    LEVEL_INFLUENCE_SCALING = 0.05

    CITY_ATTACK_WEIGHTS = {
        'infantry': 0.8,
        'ranged': 0.7,
        'cavalry': 0.6,
        'siege': 1.6,
        'navy': 1.5,
    }
    NAVY_MOVEMENT_MULTIPLIER = 0.75

    def __init__(self, id: int = None, name: str = 'Unnamed Regiment', owner_id: int = None,
                 infantry: int = 0, ranged: int = 0, cavalry: int = 0,
                 siege: int = 0, navy: int = 0, heroes: list[str] = None,
                 line_of_sight_radius: int = None, level: int = 1,
                 experience: int = 0):
        self.id = id
        self.name = name
        self.owner_id = owner_id
        self.level = self._validate_level(level)
        self.experience = max(
            self.experience_required_for_level(self.level),
            int(experience),
        )
        self.infantry = self._validate_unit_count(infantry, 'infantry')
        self.ranged = self._validate_unit_count(ranged, 'ranged')
        self.cavalry = self._validate_unit_count(cavalry, 'cavalry')
        self.siege = self._validate_unit_count(siege, 'siege')
        self.navy = self._validate_unit_count(navy, 'navy')
        self.heroes = list(heroes) if heroes is not None else []
        self.line_of_sight_radius = self._validate_line_of_sight_radius(
            self.DEFAULT_LINE_OF_SIGHT_RADIUS if line_of_sight_radius is None else line_of_sight_radius
        )
        self.influence_radius_bonus = 0
        self.tile_influence_score = self.TILE_INFLUENCE_SCORE
        self.city_influence_support_bonus = self.CITY_INFLUENCE_SUPPORT_BONUS
        self.city_influence_disruption_penalty = self.CITY_INFLUENCE_DISRUPTION_PENALTY
        self.hero_influence_bonus = self.HERO_INFLUENCE_BONUS
        self.hero_influence_radius = self.HERO_INFLUENCE_RADIUS
        self.influence_score_multiplier = 1.0
        self.attack_score_bonus = 0.0
        self.defense_score_bonus = 0.0
        self.city_attack_score_bonus = 0.0
        self.extra_attack_allowance = 0
        self.attacks_made_this_turn = 0
        self.move_after_action_sources = 0
        self.move_after_action_charges = 0
        self.movement_blocked_sources = 0
        self.terrain_boundary_pass_enabled = False

        self.regiment_attack_score = 0.0
        self.defense_score = 0.0
        self.city_attack_score = 0.0
        self.movement_spent_this_turn = 0
        self.reorganized_this_turn = False
        self.is_defending = False
        self._validate_force_composition()
        self.recalculate_attack_scores()

    def _validate_unit_count(self, value: int, unit_type: str):
        if not isinstance(value, int) or value < 0:
            raise ValueError(f'{unit_type} count must be a non-negative integer')
        return value

    def _validate_line_of_sight_radius(self, radius: int):
        if not isinstance(radius, int) or radius < 0:
            raise ValueError('Regiment line of sight radius must be a non-negative integer')
        return radius

    def _validate_level(self, level: int):
        if not isinstance(level, int):
            raise ValueError('Regiment level must be an integer')
        if level < self.MIN_LEVEL or level > self.MAX_LEVEL:
            raise ValueError(f'Regiment level must be between {self.MIN_LEVEL} and {self.MAX_LEVEL}')
        return level

    @classmethod
    def experience_required_for_level(cls, level: int):
        validated_level = max(cls.MIN_LEVEL, min(cls.MAX_LEVEL, int(level)))
        if validated_level <= cls.MIN_LEVEL:
            return 0
        required = 0
        for level_index in range(2, validated_level + 1):
            required += int(round(cls.LEVEL_XP_BASE * (cls.LEVEL_XP_GROWTH ** (level_index - 2))))
        return required

    def _determine_level_from_experience(self):
        resolved_level = self.MIN_LEVEL
        for candidate_level in range(self.MIN_LEVEL, self.MAX_LEVEL + 1):
            if self.experience >= self.experience_required_for_level(candidate_level):
                resolved_level = candidate_level
            else:
                break
        return resolved_level

    def add_experience(self, amount: int):
        experience_gain = max(0, int(amount))
        if experience_gain <= 0:
            return {'experience_gained': 0, 'level_before': self.level, 'level_after': self.level}
        level_before = self.level
        self.experience += experience_gain
        self.level = self._determine_level_from_experience()
        if self.level != level_before:
            self.recalculate_attack_scores()
        return {
            'experience_gained': experience_gain,
            'level_before': level_before,
            'level_after': self.level,
        }

    def set_level(self, level: int, reset_experience_to_floor: bool = True):
        resolved_level = self._validate_level(level)
        level_before = self.level
        self.level = resolved_level
        if reset_experience_to_floor or self.experience < self.experience_required_for_level(resolved_level):
            self.experience = self.experience_required_for_level(resolved_level)
        if self.level != level_before:
            self.recalculate_attack_scores()

    def effective_influence_multiplier(self):
        return max(
            0.0,
            round(
                self.influence_score_multiplier *
                (1.0 + (self.LEVEL_INFLUENCE_SCALING * max(0, self.level - 1))),
                4,
            ),
        )

    def total_units(self):
        return self.infantry + self.ranged + self.cavalry + self.siege + self.navy

    def is_navy(self):
        return self.navy > 0 and (self.infantry + self.ranged + self.cavalry + self.siege) == 0

    def force_kind(self):
        return 'navy' if self.is_navy() else 'regiment'

    def hero_count(self):
        return len(self.heroes)

    def _validate_force_composition(self):
        if self.navy > 0 and (self.infantry + self.ranged + self.cavalry + self.siege) > 0:
            raise ValueError('Navy forces may only contain navy units and heroes')

    def effective_line_of_sight_radius(self):
        return max(0, self.line_of_sight_radius + self.influence_radius_bonus + ((self.level - 1) // 4))

    def has_hero_influence(self):
        return self.hero_count() > 0 and self.hero_influence_bonus > 0

    def update_composition(self, infantry: int = None, ranged: int = None,
                           cavalry: int = None, siege: int = None, navy: int = None):
        if infantry is not None:
            self.infantry = self._validate_unit_count(infantry, 'infantry')
        if ranged is not None:
            self.ranged = self._validate_unit_count(ranged, 'ranged')
        if cavalry is not None:
            self.cavalry = self._validate_unit_count(cavalry, 'cavalry')
        if siege is not None:
            self.siege = self._validate_unit_count(siege, 'siege')
        if navy is not None:
            self.navy = self._validate_unit_count(navy, 'navy')
        self._validate_force_composition()
        self.recalculate_attack_scores()

    def add_hero(self, hero_name: str):
        normalized_name = str(hero_name).strip()
        if not normalized_name:
            raise ValueError('Hero name must be a non-empty string')
        self.heroes.append(normalized_name)
        self.recalculate_attack_scores()

    def remove_hero(self):
        if not self.heroes:
            raise ValueError(f'Regiment {self.id} has no heroes to remove')
        removed_hero = self.heroes.pop()
        self.recalculate_attack_scores()
        return removed_hero

    def symbol(self):
        return f'N{self.id}({self.owner_id})' if self.is_navy() else f'R{self.id}({self.owner_id})'

    def movement_range(self):
        # Larger and stronger regiments move less distance per turn.
        movement = 8 - (self.total_units() / 25) - (self.regiment_attack_score / 120)
        if self.is_navy():
            movement *= self.NAVY_MOVEMENT_MULTIPLIER
        return max(1, int(round(movement)))

    def movement_remaining(self):
        if self.movement_blocked_sources > 0:
            return 0
        return max(0, self.movement_range() - self.movement_spent_this_turn)

    def can_move_distance(self, distance: int):
        return distance <= self.movement_remaining()

    def record_movement(self, distance: int):
        self.movement_spent_this_turn += max(0, distance)

    def consume_movement(self):
        self.movement_spent_this_turn = self.movement_range()

    def reset_turn_movement(self):
        self.movement_spent_this_turn = 0
        self.reorganized_this_turn = False
        self.is_defending = False
        self.attacks_made_this_turn = 0

    def mark_reorganized_this_turn(self):
        self.reorganized_this_turn = True
        if self.can_move_after_action():
            self._consume_move_after_action_charge_if_needed()
            return
        self.consume_movement()

    def max_attacks_per_turn(self):
        return max(1, 1 + self.extra_attack_allowance)

    def can_attack_this_turn(self):
        if self.attacks_made_this_turn >= self.max_attacks_per_turn():
            return False
        if self.attacks_made_this_turn == 0:
            return self.movement_remaining() >= 1
        return True

    def can_move_after_action(self):
        return self.move_after_action_sources > 0 or self.move_after_action_charges > 0

    def _consume_move_after_action_charge_if_needed(self):
        if self.move_after_action_charges > 0:
            self.move_after_action_charges -= 1

    def record_attack_action(self):
        self.attacks_made_this_turn += 1
        if self.can_move_after_action():
            self._consume_move_after_action_charge_if_needed()
            return
        self.consume_movement()

    def effective_regiment_attack_score(self):
        attack_score = max(0.0, self.regiment_attack_score + self.attack_score_bonus)
        if self.is_defending:
            return round(attack_score * self.DEFENDING_ATTACK_MULTIPLIER, 2)
        return round(attack_score, 2)

    def effective_defense_score(self):
        defense_score = max(0.0, self.defense_score + self.defense_score_bonus)
        if self.is_defending:
            return round(defense_score * self.DEFENDING_DEFENSE_MULTIPLIER, 2)
        return round(defense_score, 2)

    def effective_defense_factor(self):
        return 1.0 + (self.effective_defense_score() / self.DEFENSE_SCORE_SCALE)

    def enter_defensive_stance(self):
        self.is_defending = True
        if self.can_move_after_action():
            self._consume_move_after_action_charge_if_needed()
            return
        self.consume_movement()

    def effective_city_attack_score(self):
        return round(max(0.0, self.city_attack_score + self.attack_score_bonus + self.city_attack_score_bonus), 2)

    def has_ranged_attack_capability(self):
        return self.ranged > 0 or getattr(self, 'navy', 0) > 0

    def attack_range(self):
        base_attack_range = self.RANGED_ATTACK_RADIUS if self.has_ranged_attack_capability() else 1
        if self.level >= 7 and (self.has_ranged_attack_capability() or self.siege > 0):
            return base_attack_range + 1
        return base_attack_range

    def can_attack_distance(self, distance: int):
        return 0 <= distance <= self.attack_range()

    def recalculate_attack_scores(self):
        self.regiment_attack_score = self._compute_weighted_score(
            self.REGIMENT_ATTACK_WEIGHTS,
            include_siege=False,
        )
        self.defense_score = self._compute_weighted_score(
            self.REGIMENT_DEFENSE_WEIGHTS,
            include_siege=False,
        )
        self.city_attack_score = self._compute_weighted_score(
            self.CITY_ATTACK_WEIGHTS,
            include_siege=True,
        )

    def _compute_weighted_score(self, weights: dict[str, float], include_siege: bool):
        unit_counts = {
            'infantry': self.infantry,
            'ranged': self.ranged,
            'cavalry': self.cavalry,
            'navy': self.navy,
        }
        if include_siege:
            unit_counts['siege'] = self.siege

        total_weighted_units = 0.0
        total_units = 0
        for unit_type, count in unit_counts.items():
            total_weighted_units += count * weights[unit_type]
            total_units += count

        if total_units == 0:
            return 0.0

        hero_bonus = 1 + (0.05 * self.hero_count())
        level_bonus = 1 + (self.LEVEL_SCORE_SCALING * max(0, self.level - 1))
        return round((total_weighted_units / total_units) * hero_bonus * level_bonus * 100, 2)

class Map:

    MAX_INFLUENCE_SCORE = 1.0
    PLAYER_TOTAL_INFLUENCE_TILE_WEIGHT = 100.0
    INFLUENCE_EPSILON = 0.0001
    MIN_VISIBLE_INFLUENCE_SCORE = 0.01
    MIN_VISIBLE_INFLUENCE_COLOR_BLEND = 0.4

    def __init__(self, width: int = 10, height: int = 10,
                 default_tile: str = 'grass'):
        self.width = width
        self.height = height
        self.default_tile = default_tile
        self.tiles = {}
        self.players: dict[int, Player] = {}
        self.cities: dict[int, City] = {}
        self.regiments: dict[int, Regiment] = {}
        self.resources: dict[int, Resource] = {}
        self.improvements: dict[int, Improvement] = {}
        self.player_discovered_tiles: dict[int, set[tuple[int, int]]] = {}
        self.next_regiment_id = 1
        self.next_resource_id = 1
        self.next_improvement_id = 1
        self.resolved_regiment_battles_this_turn: set[tuple[int, int]] = set()
        self.resolved_sieges_this_turn: set[int] = set()
        self.resolved_city_attacks_this_turn: set[int] = set()

    def add_player(self, player: Player):
        self.players[player.id] = player
        self._ensure_player_discovery_entry(player.id)
        self.recalculate_tile_influence()

    def add_city(self, city: City):
        if city.owner_id not in self.players:
            raise ValueError(f'City {city.id} references missing player {city.owner_id}')
        self.cities[city.id] = city
        self.recalculate_tile_influence()
        if self.get_city_location(city.id) is not None:
            self.update_player_discovery(city.owner_id)

    def get_player(self, player_id: int):
        return self.players.get(player_id)

    def get_player_total_influence_score(self, player_id: int):
        if player_id not in self.players:
            raise ValueError(f'Player {player_id} does not exist')

        total_score = 0.0
        for tile in self.tiles.values():
            total_score += (
                tile.influence_scores.get(player_id, 0.0) *
                self.PLAYER_TOTAL_INFLUENCE_TILE_WEIGHT
            )
        return round(total_score, 2)

    def get_max_possible_influence_score(self):
        return max(
            self.PLAYER_TOTAL_INFLUENCE_TILE_WEIGHT,
            self.width * self.height * self.PLAYER_TOTAL_INFLUENCE_TILE_WEIGHT,
        )

    def get_player_influence_rankings(self):
        rankings = []
        for player in self.players.values():
            rankings.append((player, self.get_player_total_influence_score(player.id)))
        return sorted(rankings, key=lambda entry: (-entry[1], entry[0].id))

    def get_player_capitals(self, player_id: int):
        return [
            city for city in self.cities.values()
            if city.owner_id == player_id and city.is_capital
        ]

    def get_players_with_capitals(self):
        return {
            player_id for player_id in self.players
            if self.get_player_capitals(player_id)
        }

    def get_city(self, city_id: int):
        return self.cities.get(city_id)

    def get_city_owner(self, city_id: int):
        city = self.get_city(city_id)
        if city is None:
            return None
        return self.get_player(city.owner_id)

    def get_city_location(self, city_id: int):
        for (x, y), tile in self.tiles.items():
            if tile.city_id == city_id:
                return (x, y)
        return None

    def get_regiment(self, regiment_id: int):
        return self.regiments.get(regiment_id)

    def get_resource(self, resource_id: int):
        return self.resources.get(resource_id)

    def get_resource_at(self, x: int, y: int):
        tile = self.tiles.get((x, y))
        if tile is None or tile.resource_id is None:
            return None
        return self.get_resource(tile.resource_id)

    def add_resource(self, resource: Resource, x: int, y: int):
        if (x, y) not in self.tiles:
            raise ValueError(f'Resource tile ({x}, {y}) is out of bounds')
        tile = self.tiles[(x, y)]
        if tile.resource_id is not None:
            raise ValueError(f'Tile ({x}, {y}) already has a resource')
        if resource.definition.terrain_types and tile.type not in resource.definition.terrain_types:
            raise ValueError(f'Resource {resource.name} cannot be placed on {tile.type}')
        if resource.id is None:
            resource.id = self.next_resource_id
            self.next_resource_id += 1
        self.resources[resource.id] = resource
        tile.resource_id = resource.id
        return resource

    def get_improvement(self, improvement_id: int):
        return self.improvements.get(improvement_id)

    def get_improvement_at(self, x: int, y: int):
        tile = self.tiles.get((x, y))
        if tile is None or tile.improvement_id is None:
            return None
        return self.get_improvement(tile.improvement_id)

    def get_city_improvements(self, city_id: int, include_destroyed: bool = False):
        return [
            improvement for improvement in self.improvements.values()
            if improvement.city_id == city_id and (include_destroyed or not improvement.is_destroyed)
        ]

    def get_city_ports(self, city_id: int):
        return [
            improvement for improvement in self.get_city_improvements(city_id)
            if improvement.is_port()
        ]

    def add_improvement(self, improvement: Improvement):
        if improvement.city_id not in self.cities:
            raise ValueError(f'Improvement references missing city {improvement.city_id}')
        city = self.cities[improvement.city_id]
        if improvement.owner_id != city.owner_id:
            improvement.owner_id = city.owner_id
        if improvement.id is None:
            improvement.id = self.next_improvement_id
            self.next_improvement_id += 1
        if improvement.is_extra_city():
            if improvement.tile_pos is None:
                raise ValueError('Extra-city improvements require a tile position')
            if improvement.tile_pos not in self.tiles:
                raise ValueError(f'Improvement tile {improvement.tile_pos} is out of bounds')
            tile = self.tiles[improvement.tile_pos]
            if tile.improvement_id is not None:
                raise ValueError(f'Tile {improvement.tile_pos} already has an improvement')
            tile.improvement_id = improvement.id
        self.improvements[improvement.id] = improvement
        improvement.apply_to_city(city, reverse=False)
        self.recalculate_tile_influence()
        self.update_player_discovery(city.owner_id)
        return improvement

    def remove_improvement(self, improvement_id: int):
        improvement = self.improvements.get(improvement_id)
        if improvement is None:
            return None
        city = self.cities.get(improvement.city_id)
        if city is not None:
            improvement.apply_to_city(city, reverse=True)
        if improvement.tile_pos is not None and improvement.tile_pos in self.tiles:
            self.tiles[improvement.tile_pos].improvement_id = None
        improvement.is_destroyed = True
        self.improvements.pop(improvement_id, None)
        self.recalculate_tile_influence()
        if city is not None and city.owner_id in self.players:
            self.update_player_discovery(city.owner_id)
        return improvement

    def transfer_city_improvements_to_owner(self, city_id: int, new_owner_id: int):
        for improvement in self.get_city_improvements(city_id):
            improvement.owner_id = new_owner_id

    def city_has_resource_in_sight(self, city_id: int, resource_type: str):
        return any(
            resource.resource_type == str(resource_type).strip().lower()
            for resource in self.get_city_visible_resources(city_id)
        )

    def get_city_visible_resources(self, city_id: int):
        city = self.get_city(city_id)
        city_location = self.get_city_location(city_id)
        if city is None or city_location is None:
            return []
        resources = []
        for resource in self.resources.values():
            resource_location = self.get_resource_location(resource.id)
            if resource_location is None:
                continue
            if self.get_tile_distance(city_location, resource_location) <= city.effective_line_of_sight_radius():
                resources.append(resource)
        return resources

    def get_resource_location(self, resource_id: int):
        for (x, y), tile in self.tiles.items():
            if tile.resource_id == resource_id:
                return (x, y)
        return None

    def populate_resources(self):
        Resource.initialize_definitions()
        seeded_rng = random.Random((self.width * 4099) + (self.height * 8191) + (len(self.cities) * 131))
        for position, tile in sorted(self.tiles.items()):
            if tile.resource_id is not None:
                continue
            resource_type = Resource.choose_for_tile(tile.type, seeded_rng)
            if resource_type is None:
                continue
            self.add_resource(Resource(resource_type), position[0], position[1])

    def get_regiment_location(self, regiment_id: int):
        for (x, y), tile in self.tiles.items():
            if tile.regiment_id == regiment_id:
                return (x, y)
        return None

    def get_regiment_at(self, x: int, y: int):
        tile = self.tiles.get((x, y))
        if tile is None or tile.regiment_id is None:
            return None
        return self.get_regiment(tile.regiment_id)

    def get_enemy_regiments_in_range_of_city(self, city_id: int):
        city = self.get_city(city_id)
        city_location = self.get_city_location(city_id)
        if city is None or city_location is None:
            return []
        enemy_regiments = []
        for regiment in self.regiments.values():
            if regiment.owner_id == city.owner_id:
                continue
            regiment_location = self.get_regiment_location(regiment.id)
            if regiment_location is None:
                continue
            attack_distance = self.get_tile_distance(city_location, regiment_location)
            if attack_distance <= max(regiment.attack_range(), city.effective_attack_radius()):
                enemy_regiments.append(regiment)
        return enemy_regiments

    def get_enemy_regiments_in_sight_of_city(self, city_id: int):
        city = self.get_city(city_id)
        city_location = self.get_city_location(city_id)
        if city is None or city_location is None:
            return []
        enemy_regiments = []
        for regiment in self.regiments.values():
            if regiment.owner_id == city.owner_id:
                continue
            regiment_location = self.get_regiment_location(regiment.id)
            if regiment_location is None:
                continue
            if self.get_tile_distance(city_location, regiment_location) <= city.effective_line_of_sight_radius():
                enemy_regiments.append(regiment)
        return enemy_regiments

    def advance_city_states_for_new_turn(self):
        city_updates = []
        owners_to_refresh = set()
        for city in self.cities.values():
            was_multiplier = city.occupation_influence_multiplier()
            was_radius = city.effective_line_of_sight_radius()
            under_enemy_pressure = bool(self.get_enemy_regiments_in_range_of_city(city.id))
            update = city.progress_turn_state(under_enemy_pressure=under_enemy_pressure)
            city_updates.append(update)
            if (
                city.owner_id in self.players and (
                    not math.isclose(was_multiplier, city.occupation_influence_multiplier()) or
                    was_radius != city.effective_line_of_sight_radius()
                )
            ):
                owners_to_refresh.add(city.owner_id)

        if city_updates:
            self.recalculate_tile_influence()
        for player_id in owners_to_refresh:
            self.update_player_discovery(player_id)
        return city_updates

    def get_tile_distance(self, origin: tuple[int, int], target: tuple[int, int]):
        if origin is None or target is None:
            raise ValueError('Both origin and target locations are required')
        return max(abs(target[0] - origin[0]), abs(target[1] - origin[1]))

    def _ensure_player_discovery_entry(self, player_id: int):
        if player_id not in self.player_discovered_tiles:
            self.player_discovered_tiles[player_id] = set()
        return self.player_discovered_tiles[player_id]

    def get_tiles_in_radius(self, origin: tuple[int, int], radius: int):
        if origin is None:
            return set()
        if not isinstance(radius, int) or radius < 0:
            raise ValueError('Line of sight radius must be a non-negative integer')

        tiles_in_radius = set()
        origin_x, origin_y = origin
        min_x = max(0, origin_x - radius)
        max_x = min(self.width - 1, origin_x + radius)
        min_y = max(0, origin_y - radius)
        max_y = min(self.height - 1, origin_y + radius)
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                tiles_in_radius.add((x, y))
        return tiles_in_radius

    def is_tile_securely_owned_by_player(self, x: int, y: int, player_id: int):
        tile = self.tiles.get((x, y))
        if tile is None:
            return False
        return tile.influence_owner_id == player_id and not tile.is_influence_contested

    def is_tile_in_city_line_of_sight(self, city_id: int, x: int, y: int):
        city_location = self.get_city_location(city_id)
        city = self.get_city(city_id)
        if city is None or city_location is None:
            return False
        return self.get_tile_distance(city_location, (x, y)) <= city.effective_line_of_sight_radius()

    def is_adjacent_to_water(self, x: int, y: int):
        for delta_x in (-1, 0, 1):
            for delta_y in (-1, 0, 1):
                if delta_x == 0 and delta_y == 0:
                    continue
                neighbor = self.tiles.get((x + delta_x, y + delta_y))
                if neighbor is not None and neighbor.passable_water:
                    return True
        return False

    def _clamp_influence_score(self, score: float):
        return round(max(0.0, min(self.MAX_INFLUENCE_SCORE, float(score))), 4)

    def _set_tile_influence(self, tile: Tile, influence_scores: dict[int, float]):
        normalized_scores = {
            player_id: self._clamp_influence_score(influence_scores.get(player_id, 0.0))
            for player_id in self.players
        }
        tile.influence_scores = normalized_scores

        if not normalized_scores:
            tile.influence_owner_id = None
            tile.is_influence_contested = False
            return

        highest_score = max(normalized_scores.values(), default=0.0)
        if highest_score <= self.INFLUENCE_EPSILON:
            tile.influence_owner_id = None
            tile.is_influence_contested = False
            return

        winning_players = [
            player_id for player_id, score in normalized_scores.items()
            if abs(score - highest_score) <= self.INFLUENCE_EPSILON
        ]
        tile.influence_owner_id = winning_players[0] if len(winning_players) == 1 else None
        tile.is_influence_contested = len(winning_players) > 1

    def recalculate_tile_influence(self):
        if not self.tiles:
            return

        city_influence_by_tile = {
            position: {player_id: 0.0 for player_id in self.players}
            for position in self.tiles
        }
        regiment_support_by_tile = {
            position: {player_id: 0.0 for player_id in self.players}
            for position in self.tiles
        }
        regiment_disruption_by_tile = {
            position: {player_id: 0.0 for player_id in self.players}
            for position in self.tiles
        }
        hero_influence_by_tile = {
            position: {player_id: 0.0 for player_id in self.players}
            for position in self.tiles
        }
        regiment_tile_control_by_tile = {
            position: {player_id: 0.0 for player_id in self.players}
            for position in self.tiles
        }

        for city in self.cities.values():
            city_location = self.get_city_location(city.id)
            if city_location is None or city.owner_id not in self.players:
                continue

            for position in self.get_tiles_in_radius(city_location, city.effective_line_of_sight_radius()):
                distance = self.get_tile_distance(city_location, position)
                influence_score = city.get_influence_at_distance(distance)
                if influence_score <= self.INFLUENCE_EPSILON:
                    continue
                city_influence_by_tile[position][city.owner_id] = self._clamp_influence_score(
                    city_influence_by_tile[position][city.owner_id] + influence_score
                )

        for regiment in self.regiments.values():
            regiment_location = self.get_regiment_location(regiment.id)
            if regiment_location is None or regiment.owner_id not in self.players:
                continue

            for position in self.get_tiles_in_radius(regiment_location, regiment.effective_line_of_sight_radius()):
                if city_influence_by_tile[position].get(regiment.owner_id, 0.0) > self.INFLUENCE_EPSILON:
                    regiment_support_by_tile[position][regiment.owner_id] = self._clamp_influence_score(
                        regiment_support_by_tile[position][regiment.owner_id] +
                        (regiment.city_influence_support_bonus * regiment.effective_influence_multiplier())
                    )

                for player_id in self.players:
                    if player_id == regiment.owner_id:
                        continue
                    if city_influence_by_tile[position].get(player_id, 0.0) <= self.INFLUENCE_EPSILON:
                        continue
                    regiment_disruption_by_tile[position][player_id] = self._clamp_influence_score(
                        regiment_disruption_by_tile[position][player_id] +
                        (regiment.city_influence_disruption_penalty * regiment.effective_influence_multiplier())
                    )

            if regiment.has_hero_influence():
                for position in self.get_tiles_in_radius(regiment_location, regiment.hero_influence_radius):
                    hero_influence_by_tile[position][regiment.owner_id] = self._clamp_influence_score(
                        hero_influence_by_tile[position][regiment.owner_id] +
                        (regiment.hero_influence_bonus * regiment.effective_influence_multiplier())
                    )

            regiment_tile_control_by_tile[regiment_location][regiment.owner_id] = self._clamp_influence_score(
                regiment_tile_control_by_tile[regiment_location][regiment.owner_id] +
                (regiment.tile_influence_score * regiment.effective_influence_multiplier())
            )

        for position, tile in self.tiles.items():
            total_influence = {}
            for player_id in self.players:
                influence_score = (
                    city_influence_by_tile[position][player_id] +
                    regiment_support_by_tile[position][player_id] +
                    hero_influence_by_tile[position][player_id] -
                    regiment_disruption_by_tile[position][player_id]
                )
                influence_score = self._clamp_influence_score(influence_score)
                influence_score = max(
                    influence_score,
                    regiment_tile_control_by_tile[position][player_id],
                )
                total_influence[player_id] = self._clamp_influence_score(influence_score)
            self._set_tile_influence(tile, total_influence)

    def get_player_visible_tiles(self, player_id: int):
        if player_id not in self.players:
            return set()

        visible_tiles = set()
        for city in self.cities.values():
            if city.owner_id != player_id:
                continue
            visible_tiles.update(self.get_tiles_in_radius(
                self.get_city_location(city.id),
                city.effective_line_of_sight_radius(),
            ))

        for regiment in self.regiments.values():
            if regiment.owner_id != player_id:
                continue
            visible_tiles.update(self.get_tiles_in_radius(
                self.get_regiment_location(regiment.id),
                regiment.effective_line_of_sight_radius(),
            ))
        return visible_tiles

    def get_player_discovered_tiles(self, player_id: int):
        return self._ensure_player_discovery_entry(player_id)

    def update_player_discovery(self, player_id: int):
        discovered_tiles = self._ensure_player_discovery_entry(player_id)
        discovered_tiles.update(self.get_player_visible_tiles(player_id))
        return discovered_tiles

    def refresh_all_player_discovery(self):
        self.recalculate_tile_influence()
        for player_id in self.players:
            self.update_player_discovery(player_id)

    def is_tile_visible_to_player(self, x: int, y: int, player_id: int):
        return (x, y) in self.get_player_visible_tiles(player_id)

    def is_city_visible_to_player(self, city_id: int, player_id: int):
        location = self.get_city_location(city_id)
        return location is not None and self.is_tile_visible_to_player(location[0], location[1], player_id)

    def is_regiment_visible_to_player(self, regiment_id: int, player_id: int):
        location = self.get_regiment_location(regiment_id)
        return location is not None and self.is_tile_visible_to_player(location[0], location[1], player_id)

    def can_place_regiment_on_tile(self, regiment: Regiment, tile: Tile):
        if regiment.is_navy():
            improvement = self.get_improvement(tile.improvement_id) if tile.improvement_id is not None else None
            return tile.passable_water or (improvement is not None and improvement.is_port())
        return tile.passable_foot or (regiment.terrain_boundary_pass_enabled and not tile.passable_water)

    def add_regiment(self, regiment: Regiment, x: int, y: int):
        if regiment.owner_id not in self.players:
            raise ValueError(f'Regiment owner {regiment.owner_id} does not exist')
        if (x, y) not in self.tiles:
            raise ValueError(f'Tile ({x}, {y}) is out of bounds')
        tile = self.tiles[(x, y)]
        if tile.regiment_id is not None:
            raise ValueError(f'Tile ({x}, {y}) already has a regiment')
        if not self.can_place_regiment_on_tile(regiment, tile):
            if regiment.is_navy():
                raise ValueError(f'Tile ({x}, {y}) is not passable for navy forces')
            raise ValueError(f'Tile ({x}, {y}) is not passable for land regiments')

        if regiment.id is None:
            regiment.id = self.next_regiment_id
            self.next_regiment_id += 1
        elif regiment.id in self.regiments:
            raise ValueError(f'Regiment id {regiment.id} already exists')
        else:
            self.next_regiment_id = max(self.next_regiment_id, regiment.id + 1)

        self.regiments[regiment.id] = regiment
        tile.regiment_id = regiment.id
        self.recalculate_tile_influence()
        self.update_player_discovery(regiment.owner_id)

    def move_regiment(self, regiment_id: int, target_x: int, target_y: int):
        regiment = self.get_regiment(regiment_id)
        if regiment is None:
            raise ValueError(f'Regiment {regiment_id} does not exist')

        start = self.get_regiment_location(regiment_id)
        if start is None:
            raise ValueError(f'Regiment {regiment_id} is not on the map')
        if (target_x, target_y) not in self.tiles:
            raise ValueError(f'Target tile ({target_x}, {target_y}) is out of bounds')

        target_tile = self.tiles[(target_x, target_y)]
        if target_tile.regiment_id is not None:
            raise ValueError(f'Target tile ({target_x}, {target_y}) already has a regiment')
        if not self.can_place_regiment_on_tile(regiment, target_tile):
            if regiment.is_navy():
                raise ValueError(f'Target tile ({target_x}, {target_y}) is not passable for navy forces')
            raise ValueError(f'Target tile ({target_x}, {target_y}) is not passable for land regiments')

        delta_x = abs(target_x - start[0])
        delta_y = abs(target_y - start[1])
        distance = max(delta_x, delta_y)
        if not regiment.can_move_distance(distance):
            raise ValueError(
                f'Regiment {regiment_id} has {regiment.movement_remaining()} movement remaining this turn '
                f'and cannot move {distance} tiles'
            )

        self.tiles[start].regiment_id = None
        target_tile.regiment_id = regiment_id
        if regiment.is_defending:
            regiment.is_defending = False
        regiment.record_movement(distance)
        improvement = self.get_improvement(target_tile.improvement_id) if target_tile.improvement_id is not None else None
        if improvement is not None and improvement.owner_id != regiment.owner_id:
            self.remove_improvement(improvement.id)
        if (
            regiment.terrain_boundary_pass_enabled and
            not regiment.is_navy() and
            not self.tiles[start].passable_foot and
            target_tile.passable_foot
        ):
            regiment.terrain_boundary_pass_enabled = False
        self.recalculate_tile_influence()
        self.update_player_discovery(regiment.owner_id)

    def split_regiment(self, regiment_id: int, target_x: int, target_y: int,
                       split_counts: dict[str, int], new_name: str = None):
        regiment = self.get_regiment(regiment_id)
        if regiment is None:
            raise ValueError(f'Regiment {regiment_id} does not exist')
        if regiment.total_units() == 0:
            raise ValueError(f'Regiment {regiment_id} has no units remaining')
        if regiment.reorganized_this_turn:
            raise ValueError(f'Regiment {regiment_id} has already split or combined this turn')
        if regiment.movement_remaining() < 1:
            raise ValueError(f'Regiment {regiment_id} has no movement remaining to perform a split')

        start = self.get_regiment_location(regiment_id)
        if start is None:
            raise ValueError(f'Regiment {regiment_id} is not on the map')
        if (target_x, target_y) not in self.tiles:
            raise ValueError(f'Target tile ({target_x}, {target_y}) is out of bounds')
        if self.get_tile_distance(start, (target_x, target_y)) != 1:
            raise ValueError('Split regiment must form on an adjacent tile')

        target_tile = self.tiles[(target_x, target_y)]
        if target_tile.regiment_id is not None:
            raise ValueError(f'Target tile ({target_x}, {target_y}) already has a regiment')
        if not self.can_place_regiment_on_tile(regiment, target_tile):
            if regiment.is_navy():
                raise ValueError(f'Target tile ({target_x}, {target_y}) is not passable for navy forces')
            raise ValueError(f'Target tile ({target_x}, {target_y}) is not passable for land regiments')

        unit_types = ('infantry', 'ranged', 'cavalry', 'siege', 'navy')
        transfer_counts = {}
        for unit_type in unit_types:
            transfer_count = split_counts.get(unit_type, 0)
            if not isinstance(transfer_count, int) or transfer_count < 0:
                raise ValueError(f'Split count for {unit_type} must be a non-negative integer')
            if transfer_count > getattr(regiment, unit_type):
                raise ValueError(f'Regiment {regiment_id} does not have enough {unit_type} to split that amount')
            transfer_counts[unit_type] = transfer_count

        transferred_total = sum(transfer_counts.values())
        if transferred_total == 0:
            raise ValueError('Split must transfer at least one unit into the new regiment')

        remaining_counts = {
            unit_type: getattr(regiment, unit_type) - transfer_counts[unit_type]
            for unit_type in unit_types
        }
        if sum(remaining_counts.values()) == 0:
            raise ValueError('Split must leave at least one unit in the original regiment')

        regiment_name = str(new_name).strip() if new_name is not None else ''
        if not regiment_name:
            regiment_name = f'{regiment.name} Detachment'

        split_regiment = Regiment(
            name=regiment_name,
            owner_id=regiment.owner_id,
            infantry=transfer_counts['infantry'],
            ranged=transfer_counts['ranged'],
            cavalry=transfer_counts['cavalry'],
            siege=transfer_counts['siege'],
            navy=transfer_counts['navy'],
            level=regiment.level,
            experience=regiment.experience,
        )
        self.add_regiment(split_regiment, target_x, target_y)
        regiment.update_composition(
            infantry=remaining_counts['infantry'],
            ranged=remaining_counts['ranged'],
            cavalry=remaining_counts['cavalry'],
            siege=remaining_counts['siege'],
            navy=remaining_counts['navy'],
        )
        original_size = regiment.total_units()
        split_size = split_regiment.total_units()
        if split_size > original_size:
            split_regiment.set_level(regiment.level)
            regiment.set_level(max(Regiment.MIN_LEVEL, regiment.level // 2))
        else:
            regiment.set_level(regiment.level)
            split_regiment.set_level(max(Regiment.MIN_LEVEL, regiment.level // 2))
        regiment.mark_reorganized_this_turn()
        split_regiment.mark_reorganized_this_turn()
        self.recalculate_tile_influence()
        return split_regiment

    def combine_regiments(self, source_regiment_id: int, target_regiment_id: int):
        if source_regiment_id == target_regiment_id:
            raise ValueError('A regiment cannot combine into itself')

        source_regiment = self.get_regiment(source_regiment_id)
        if source_regiment is None:
            raise ValueError(f'Regiment {source_regiment_id} does not exist')
        target_regiment = self.get_regiment(target_regiment_id)
        if target_regiment is None:
            raise ValueError(f'Regiment {target_regiment_id} does not exist')
        if source_regiment.owner_id != target_regiment.owner_id:
            raise ValueError('Only regiments from the same empire may combine')
        if source_regiment.is_navy() != target_regiment.is_navy():
            raise ValueError('Land regiments and navies cannot combine')
        if source_regiment.total_units() == 0:
            raise ValueError(f'Regiment {source_regiment_id} has no units remaining')
        if target_regiment.total_units() == 0:
            raise ValueError(f'Regiment {target_regiment_id} has no units remaining')
        if source_regiment.reorganized_this_turn:
            raise ValueError(f'Regiment {source_regiment_id} has already split or combined this turn')
        if target_regiment.reorganized_this_turn:
            raise ValueError(f'Regiment {target_regiment_id} has already split or combined this turn')
        if source_regiment.movement_remaining() < 1:
            raise ValueError(f'Regiment {source_regiment_id} has no movement remaining to perform a combine')
        if target_regiment.movement_remaining() < 1:
            raise ValueError(f'Regiment {target_regiment_id} has no movement remaining to perform a combine')

        source_location = self.get_regiment_location(source_regiment_id)
        target_location = self.get_regiment_location(target_regiment_id)
        if source_location is None:
            raise ValueError(f'Regiment {source_regiment_id} is not on the map')
        if target_location is None:
            raise ValueError(f'Regiment {target_regiment_id} is not on the map')
        if self.get_tile_distance(source_location, target_location) != 1:
            raise ValueError('Regiments must be on adjacent tiles to combine')

        source_size = source_regiment.total_units()
        target_size = target_regiment.total_units()
        highest_level = max(source_regiment.level, target_regiment.level)
        preserve_highest_level = (
            (source_regiment.level > target_regiment.level and source_size > target_size) or
            (target_regiment.level > source_regiment.level and target_size > source_size)
        )
        target_regiment.update_composition(
            infantry=target_regiment.infantry + source_regiment.infantry,
            ranged=target_regiment.ranged + source_regiment.ranged,
            cavalry=target_regiment.cavalry + source_regiment.cavalry,
            siege=target_regiment.siege + source_regiment.siege,
            navy=target_regiment.navy + source_regiment.navy,
        )
        target_regiment.heroes.extend(source_regiment.heroes)
        if preserve_highest_level:
            target_regiment.set_level(highest_level)
        else:
            weighted_level = math.floor(
                ((source_regiment.level * source_size) + (target_regiment.level * target_size)) /
                max(1, source_size + target_size)
            )
            target_regiment.set_level(max(Regiment.MIN_LEVEL, weighted_level))
        target_regiment.recalculate_attack_scores()
        self._remove_regiment_from_map(source_regiment_id)
        target_regiment.mark_reorganized_this_turn()
        self.recalculate_tile_influence()
        return target_regiment

    def _award_regiment_combat_experience(self, regiment: Regiment, casualties_inflicted: int,
                                          casualties_taken: int = 0, defeated_enemy: bool = False,
                                          attacked_city: bool = False):
        experience_gain = max(0, int(casualties_inflicted * (6 if attacked_city else 4)))
        experience_gain += max(0, int(casualties_taken))
        if defeated_enemy:
            experience_gain += 18 if attacked_city else 12
        regiment.add_experience(experience_gain)
        return experience_gain

    def resolve_regiment_battle(self, regiment_a_id: int, regiment_b_id: int) -> dict:
        regiment_a = self.get_regiment(regiment_a_id)
        if regiment_a is None:
            raise ValueError(f'Regiment {regiment_a_id} does not exist')
        regiment_b = self.get_regiment(regiment_b_id)
        if regiment_b is None:
            raise ValueError(f'Regiment {regiment_b_id} does not exist')
        if self.get_regiment_location(regiment_a_id) is None:
            raise ValueError(f'Regiment {regiment_a_id} is not on the map')
        if self.get_regiment_location(regiment_b_id) is None:
            raise ValueError(f'Regiment {regiment_b_id} is not on the map')
        if regiment_a.total_units() == 0:
            raise ValueError(f'Regiment {regiment_a_id} has no units remaining')
        if regiment_b.total_units() == 0:
            raise ValueError(f'Regiment {regiment_b_id} has no units remaining')
        if regiment_a.owner_id == regiment_b.owner_id:
            raise ValueError(f'Regiments {regiment_a_id} and {regiment_b_id} belong to the same owner')

        battle_key = tuple(sorted((regiment_a_id, regiment_b_id)))
        if battle_key in self.resolved_regiment_battles_this_turn:
            raise ValueError(
                f'Battle between Regiment {regiment_a_id} and Regiment {regiment_b_id} has already been resolved this turn'
            )

        power_a = regiment_a.effective_regiment_attack_score() * (regiment_a.total_units() ** Regiment.FORCE_SIZE_EXPONENT)
        power_b = regiment_b.effective_regiment_attack_score() * (regiment_b.total_units() ** Regiment.FORCE_SIZE_EXPONENT)
        pressure_a = power_b / regiment_a.effective_defense_factor()
        pressure_b = power_a / regiment_b.effective_defense_factor()
        total_pressure = pressure_a + pressure_b
        if total_pressure == 0:
            loss_fraction_a = 0.0
            loss_fraction_b = 0.0
        else:
            loss_fraction_a = Regiment.BASE_BATTLE_RATE * (pressure_a / total_pressure)
            loss_fraction_b = Regiment.BASE_BATTLE_RATE * (pressure_b / total_pressure)

        casualties_a = self._apply_regiment_battle_losses(
            regiment_a,
            min(
                regiment_a.total_units(),
                int(math.floor((regiment_a.total_units() * loss_fraction_a) + 0.5)),
            ),
        )
        casualties_b = self._apply_regiment_battle_losses(
            regiment_b,
            min(
                regiment_b.total_units(),
                int(math.floor((regiment_b.total_units() * loss_fraction_b) + 0.5)),
            ),
        )

        remaining_units_a = regiment_a.total_units()
        remaining_units_b = regiment_b.total_units()
        defeated_a = remaining_units_a == 0
        defeated_b = remaining_units_b == 0

        if defeated_a:
            self._remove_regiment_from_map(regiment_a_id)
        if defeated_b:
            self._remove_regiment_from_map(regiment_b_id)

        self._award_regiment_combat_experience(
            regiment_a,
            casualties_inflicted=sum(casualties_b.values()),
            casualties_taken=sum(casualties_a.values()),
            defeated_enemy=defeated_b,
        )
        self._award_regiment_combat_experience(
            regiment_b,
            casualties_inflicted=sum(casualties_a.values()),
            casualties_taken=sum(casualties_b.values()),
            defeated_enemy=defeated_a,
        )

        self.resolved_regiment_battles_this_turn.add(battle_key)
        return {
            'regiment_a_id': regiment_a_id,
            'regiment_b_id': regiment_b_id,
            'casualties_a': casualties_a,
            'casualties_b': casualties_b,
            'remaining_units_a': remaining_units_a,
            'remaining_units_b': remaining_units_b,
            'defeated_a': defeated_a,
            'defeated_b': defeated_b,
        }

    def attack_regiment(self, attacker_id: int, defender_id: int) -> dict:
        if attacker_id == defender_id:
            raise ValueError('A regiment cannot attack itself')

        attacker = self.get_regiment(attacker_id)
        if attacker is None:
            raise ValueError(f'Regiment {attacker_id} does not exist')
        defender = self.get_regiment(defender_id)
        if defender is None:
            raise ValueError(f'Regiment {defender_id} does not exist')
        if attacker.total_units() == 0:
            raise ValueError(f'Regiment {attacker_id} has no units remaining')
        if not attacker.can_attack_this_turn():
            raise ValueError(
                f'Regiment {attacker_id} cannot attack again this turn '
                f'(movement remaining={attacker.movement_remaining()}, '
                f'attacks remaining={max(0, attacker.max_attacks_per_turn() - attacker.attacks_made_this_turn)})'
            )
        if attacker.is_defending:
            raise ValueError(f'Regiment {attacker_id} is defending and cannot attack this turn')

        attacker_location = self.get_regiment_location(attacker_id)
        defender_location = self.get_regiment_location(defender_id)
        if attacker_location is None:
            raise ValueError(f'Regiment {attacker_id} is not on the map')
        if defender_location is None:
            raise ValueError(f'Regiment {defender_id} is not on the map')

        attack_distance = self.get_tile_distance(attacker_location, defender_location)
        if not attacker.can_attack_distance(attack_distance):
            raise ValueError(
                f'Regiment {attacker_id} may attack up to {attacker.attack_range()} tile(s), '
                f'but Regiment {defender_id} is {attack_distance} tile(s) away'
            )

        defender_was_defending = defender.is_defending
        defender_effective_attack_score = defender.effective_regiment_attack_score()
        defender_defense_score = defender.effective_defense_score()
        result = self.resolve_regiment_battle(attacker_id, defender_id)
        attacker.record_attack_action()
        result['attack_distance'] = attack_distance
        result['attacker_spent_all_movement'] = attacker.movement_remaining() == 0
        result['defender_was_defending'] = defender_was_defending
        result['defender_effective_attack_score'] = defender_effective_attack_score
        result['defender_defense_score'] = defender_defense_score
        return result

    def resolve_siege(self, regiment_id: int = None, city_id: int = None) -> dict:
        if city_id is None:
            raise ValueError('City id is required')

        city = self.get_city(city_id)
        if city is None:
            raise ValueError(f'City {city_id} does not exist')
        city_location = self.get_city_location(city_id)
        if city_location is None:
            raise ValueError(f'City {city_id} is not on the map')
        if city_id in self.resolved_sieges_this_turn:
            raise ValueError(f'Siege resolution for City {city_id} has already been resolved this turn')

        regiment = None
        if regiment_id is not None:
            regiment = self.get_regiment(regiment_id)
            if regiment is None:
                raise ValueError(f'Regiment {regiment_id} does not exist')
            if regiment.total_units() == 0:
                raise ValueError(f'Regiment {regiment_id} has no units remaining')

        resistance_before = city.siege_resistance
        sacked = False
        previous_owner_id = city.owner_id
        regiment_location = self.get_regiment_location(regiment_id) if regiment_id is not None else None
        attack_distance = self.get_tile_distance(regiment_location, city_location) if regiment_location is not None else None
        if (
            regiment is not None and
            regiment_location is not None and
            regiment.owner_id != city.owner_id and
            not regiment.can_attack_distance(attack_distance)
        ):
            raise ValueError(
                f'Regiment {regiment_id} may attack up to {regiment.attack_range()} tile(s), '
                f'but City {city_id} is {attack_distance} tile(s) away'
            )
        is_besieging = (
            regiment is not None and
            regiment_location is not None and
            regiment.can_attack_distance(attack_distance) and
            regiment.owner_id != city.owner_id
        )

        if not is_besieging:
            raise ValueError(f'Regiment {regiment_id} is not in a valid position to besiege City {city_id}')

        siege_pressure = regiment.effective_city_attack_score() * (regiment.total_units() ** Regiment.FORCE_SIZE_EXPONENT)
        city_resilience = city.effective_defense_score() * City.DEFENSE_SCALE
        total_pressure = siege_pressure + city_resilience
        loss_fraction = 0.0 if total_pressure == 0 else City.BASE_SIEGE_RATE * (siege_pressure / total_pressure)
        raw_resistance_loss = city.siege_resistance * loss_fraction
        resistance_loss = 0.0 if city.siege_resistance <= 0 else max(0.01, round(raw_resistance_loss, 2))
        city.siege_resistance = round(max(0.0, city.siege_resistance - resistance_loss), 2)
        attacker_casualties = {'infantry': 0, 'ranged': 0, 'cavalry': 0, 'siege': 0, 'navy': 0}
        attacker_destroyed = False

        if city.siege_resistance <= 0:
            previous_owner_id = city.owner_id
            city.begin_occupation(regiment.owner_id)
            city.add_experience(20)
            self.transfer_city_improvements_to_owner(city.id, city.owner_id)
            self.recalculate_tile_influence()
            city.update_post_capture_cooldowns(
                total_influence_score=self.get_player_total_influence_score(city.owner_id),
                max_influence_score=self.get_max_possible_influence_score(),
            )
            self.update_player_discovery(city.owner_id)
            if previous_owner_id in self.players:
                self.update_player_discovery(previous_owner_id)
            sacked = True
            self._award_regiment_combat_experience(
                regiment,
                casualties_inflicted=max(1, int(resistance_loss * 2)),
                defeated_enemy=True,
                attacked_city=True,
            )
        else:
            self._award_regiment_combat_experience(
                regiment,
                casualties_inflicted=max(1, int(resistance_loss)),
                attacked_city=True,
            )

        self.resolved_sieges_this_turn.add(city_id)
        result = {
            'city_id': city_id,
            'regiment_id': regiment_id,
            'resistance_before': resistance_before,
            'resistance_after': city.siege_resistance,
            'max_resistance': city.max_siege_resistance,
            'attacker_casualties': attacker_casualties,
            'attacker_remaining_units': regiment.total_units() if not attacker_destroyed else 0,
            'attacker_destroyed': attacker_destroyed,
            'city_attack_score': city.effective_attack_score(),
            'sacked': sacked,
        }
        if sacked:
            result['previous_owner_id'] = previous_owner_id
            result['new_owner_id'] = city.owner_id
            result['occupation_recovery_turns_remaining'] = city.occupation_recovery_turns_remaining
            result['siege_repair_delay_turns_remaining'] = city.siege_repair_delay_turns_remaining
            result['regiment_production_lock_turns_remaining'] = city.regiment_production_lock_turns_remaining
        return result

    def resolve_city_attack(self, city_id: int, regiment_id: int) -> dict:
        city = self.get_city(city_id)
        if city is None:
            raise ValueError(f'City {city_id} does not exist')
        if city_id in self.resolved_city_attacks_this_turn:
            raise ValueError(f'City {city_id} has already attacked this turn')

        regiment = self.get_regiment(regiment_id)
        if regiment is None:
            raise ValueError(f'Regiment {regiment_id} does not exist')
        if regiment.total_units() == 0:
            raise ValueError(f'Regiment {regiment_id} has no units remaining')
        if regiment.owner_id == city.owner_id:
            raise ValueError(f'City {city_id} and Regiment {regiment_id} belong to the same owner')

        city_location = self.get_city_location(city_id)
        regiment_location = self.get_regiment_location(regiment_id)
        if city_location is None:
            raise ValueError(f'City {city_id} is not on the map')
        if regiment_location is None:
            raise ValueError(f'Regiment {regiment_id} is not on the map')

        attack_distance = self.get_tile_distance(city_location, regiment_location)
        if attack_distance > city.effective_line_of_sight_radius():
            raise ValueError(
                f'City {city_id} may attack up to its line of sight radius of '
                f'{city.effective_line_of_sight_radius()} tile(s), but Regiment {regiment_id} is '
                f'{attack_distance} tile(s) away'
            )

        city_pressure = city.effective_attack_score() * (
            1.0 + (city.siege_resistance / max(city.max_siege_resistance, 1.0))
        )
        regiment_pressure = regiment.effective_regiment_attack_score() * (
            regiment.total_units() ** Regiment.FORCE_SIZE_EXPONENT
        )
        casualty_fraction = 0.0 if city_pressure <= 0 else min(
            Regiment.BASE_BATTLE_RATE,
            0.10 + (0.14 * (city_pressure / max(1.0, city_pressure + (regiment_pressure / max(1.0, regiment.effective_defense_factor())))))
        )
        casualty_count = min(
            regiment.total_units(),
            int(math.floor((regiment.total_units() * casualty_fraction) + 0.5)),
        )
        casualties = self._apply_regiment_battle_losses(regiment, casualty_count)
        destroyed = regiment.total_units() == 0
        if destroyed:
            self._remove_regiment_from_map(regiment_id)

        city.add_experience(max(4, casualty_count * 2))

        self.resolved_city_attacks_this_turn.add(city_id)
        return {
            'city_id': city_id,
            'regiment_id': regiment_id,
            'attack_distance': attack_distance,
            'city_attack_score': city.effective_attack_score(),
            'casualties': casualties,
            'remaining_units': regiment.total_units() if not destroyed else 0,
            'destroyed': destroyed,
        }

    def attack_city(self, regiment_id: int, city_id: int) -> dict:
        regiment = self.get_regiment(regiment_id)
        if regiment is None:
            raise ValueError(f'Regiment {regiment_id} does not exist')
        if regiment.total_units() == 0:
            raise ValueError(f'Regiment {regiment_id} has no units remaining')
        if not regiment.can_attack_this_turn():
            raise ValueError(
                f'Regiment {regiment_id} cannot attack again this turn '
                f'(movement remaining={regiment.movement_remaining()}, '
                f'attacks remaining={max(0, regiment.max_attacks_per_turn() - regiment.attacks_made_this_turn)})'
            )
        if regiment.is_defending:
            raise ValueError(f'Regiment {regiment_id} is defending and cannot attack this turn')

        city = self.get_city(city_id)
        if city is None:
            raise ValueError(f'City {city_id} does not exist')
        if regiment.owner_id == city.owner_id:
            raise ValueError(f'Regiment {regiment_id} and City {city_id} belong to the same owner')

        regiment_location = self.get_regiment_location(regiment_id)
        city_location = self.get_city_location(city_id)
        attack_result = self.resolve_siege(regiment_id=regiment_id, city_id=city_id)
        if regiment.total_units() > 0:
            regiment.record_attack_action()
        attack_result['attack_distance'] = self.get_tile_distance(regiment_location, city_location)
        attack_result['attacker_spent_all_movement'] = True if attack_result['attacker_destroyed'] else regiment.movement_remaining() == 0
        return attack_result

    def defend_regiment(self, regiment_id: int):
        regiment = self.get_regiment(regiment_id)
        if regiment is None:
            raise ValueError(f'Regiment {regiment_id} does not exist')
        if regiment.total_units() == 0:
            raise ValueError(f'Regiment {regiment_id} has no units remaining')
        if self.get_regiment_location(regiment_id) is None:
            raise ValueError(f'Regiment {regiment_id} is not on the map')
        if regiment.movement_remaining() < 1:
            raise ValueError(f'Regiment {regiment_id} has no movement remaining to defend')
        if regiment.is_defending:
            raise ValueError(f'Regiment {regiment_id} is already defending this turn')

        regiment.enter_defensive_stance()
        return {
            'regiment_id': regiment_id,
            'defense_score': regiment.defense_score,
            'effective_defense_score': regiment.effective_defense_score(),
            'effective_attack_score': regiment.effective_regiment_attack_score(),
            'movement_remaining': regiment.movement_remaining(),
        }

    def reset_regiment_movement_for_new_turn(self):
        for regiment in self.regiments.values():
            regiment.reset_turn_movement()

    def reset_battle_resolution_for_new_turn(self):
        self.resolved_regiment_battles_this_turn.clear()
        self.resolved_sieges_this_turn.clear()
        self.resolved_city_attacks_this_turn.clear()

    def _apply_regiment_battle_losses(self, regiment: Regiment, casualty_count: int):
        casualties = {'infantry': 0, 'ranged': 0, 'cavalry': 0, 'siege': 0, 'navy': 0}
        total_combat_units = regiment.infantry + regiment.ranged + regiment.cavalry + regiment.siege + regiment.navy
        casualty_count = max(0, min(total_combat_units, casualty_count))
        if casualty_count == 0 or total_combat_units == 0:
            return casualties

        shares = []
        for unit_type in ('infantry', 'ranged', 'cavalry', 'siege', 'navy'):
            unit_count = getattr(regiment, unit_type)
            share = casualty_count * (unit_count / total_combat_units)
            assigned = math.floor(share)
            casualties[unit_type] = assigned
            shares.append((unit_type, share - assigned))

        casualties_remaining = casualty_count - sum(casualties.values())
        shares.sort(key=lambda item: item[1], reverse=True)
        for unit_type, _ in shares[:casualties_remaining]:
            casualties[unit_type] += 1

        regiment.update_composition(
            infantry=max(0, regiment.infantry - casualties['infantry']),
            ranged=max(0, regiment.ranged - casualties['ranged']),
            cavalry=max(0, regiment.cavalry - casualties['cavalry']),
            siege=max(0, regiment.siege - casualties['siege']),
            navy=max(0, regiment.navy - casualties['navy']),
        )
        return casualties

    def _remove_regiment_from_map(self, regiment_id: int):
        location = self.get_regiment_location(regiment_id)
        if location is not None:
            self.tiles[location].regiment_id = None
        self.regiments.pop(regiment_id, None)
        self.recalculate_tile_influence()

    def print_regiment_metadata(self, regiment: Regiment):
        if regiment is None:
            print('No regiment found.')
            return

        owner = self.get_player(regiment.owner_id)
        owner_name = owner.name if owner is not None else f'Unknown({regiment.owner_id})'
        owner_color = self._get_player_color_code(owner.color) if owner is not None else ''
        if owner_color:
            owner_name = f'{owner_color}{owner_name}{Style.RESET_ALL}'
        location = self.get_regiment_location(regiment.id)
        location_text = f'({location[0]}, {location[1]})' if location is not None else 'UNPLACED'

        print('REGIMENT:')
        print(
            f'  id={regiment.id} | type={"Navy" if regiment.is_navy() else "Regiment"} | '
            f'name={regiment.name} | owner={owner_name} | location={location_text}'
        )
        print(
            f'  level={regiment.level} | xp={regiment.experience} | '
            f'composition: infantry={regiment.infantry}, ranged={regiment.ranged}, cavalry={regiment.cavalry}, '
            f'siege={regiment.siege}, navy={regiment.navy}, heroes={regiment.hero_count()}'
        )
        print(
            f'  scores: vs_regiment={regiment.regiment_attack_score}, vs_regiment_effective={regiment.effective_regiment_attack_score()}, '
            f'defense={regiment.defense_score}, defense_effective={regiment.effective_defense_score()}, vs_city={regiment.effective_city_attack_score()} '
            f'| move_range={regiment.movement_range()} | move_remaining={regiment.movement_remaining()} '
            f'| attack_range={regiment.attack_range()} | attacks_remaining={max(0, regiment.max_attacks_per_turn() - regiment.attacks_made_this_turn)} '
            f'| line_of_sight={regiment.effective_line_of_sight_radius()} | stance={"DEFEND" if regiment.is_defending else "READY"}'
        )
        if regiment.heroes:
            print(f'  heroes: {", ".join(regiment.heroes)}')
        if regiment.move_after_action_sources > 0 or regiment.move_after_action_charges > 0:
            print(
                f'  card effects: move-after-action turns={regiment.move_after_action_sources}, '
                f'one-shot charges={regiment.move_after_action_charges}'
            )
        if regiment.extra_attack_allowance > 0:
            print(f'  card effects: bonus attacks per turn={regiment.extra_attack_allowance}')
        if regiment.movement_blocked_sources > 0:
            print(f'  card effects: movement blocked by {regiment.movement_blocked_sources} effect(s)')
        if regiment.terrain_boundary_pass_enabled:
            print('  card effects: impassable terrain traversal is active')
        print('')

    def _normalize_player_color_name(self, player_color: str):
        return str(player_color).strip().lower().replace('_', '').replace('-', '')

    def _get_player_color_code(self, player_color: str):
        color_map = {
            'black': Fore.BLACK,
            'red': Fore.RED,
            'green': Fore.GREEN,
            'yellow': Fore.YELLOW,
            'blue': Fore.BLUE,
            'magenta': Fore.MAGENTA,
            'cyan': Fore.CYAN,
            'white': Fore.WHITE,
            'lightblack': Fore.LIGHTBLACK_EX,
            'lightred': Fore.LIGHTRED_EX,
            'lightgreen': Fore.LIGHTGREEN_EX,
            'lightyellow': Fore.LIGHTYELLOW_EX,
            'lightblue': Fore.LIGHTBLUE_EX,
            'lightmagenta': Fore.LIGHTMAGENTA_EX,
            'lightcyan': Fore.LIGHTCYAN_EX,
            'lightwhite': Fore.LIGHTWHITE_EX,
        }
        normalized = self._normalize_player_color_name(player_color)
        return color_map.get(normalized, '')

    def _get_player_color_rgb(self, player_color: str):
        color_map = {
            'black': (0, 0, 0),
            'red': (205, 49, 49),
            'green': (13, 188, 121),
            'yellow': (229, 229, 16),
            'blue': (36, 114, 200),
            'magenta': (188, 63, 188),
            'cyan': (17, 168, 205),
            'white': (229, 229, 229),
            'lightblack': (102, 102, 102),
            'lightred': (241, 76, 76),
            'lightgreen': (35, 209, 139),
            'lightyellow': (245, 245, 67),
            'lightblue': (59, 142, 234),
            'lightmagenta': (214, 112, 214),
            'lightcyan': (41, 184, 219),
            'lightwhite': (255, 255, 255),
        }
        normalized = self._normalize_player_color_name(player_color)
        return color_map.get(normalized)

    def _get_influence_gradient_color_code(self, player_color: str, influence_score: float):
        player_rgb = self._get_player_color_rgb(player_color)
        if player_rgb is None:
            return ''

        normalized_score = self._clamp_influence_score(influence_score)
        if normalized_score <= self.INFLUENCE_EPSILON:
            return ''

        blend_ratio = self.MIN_VISIBLE_INFLUENCE_COLOR_BLEND
        if normalized_score > self.MIN_VISIBLE_INFLUENCE_SCORE:
            scaled_score = (
                (normalized_score - self.MIN_VISIBLE_INFLUENCE_SCORE) /
                (self.MAX_INFLUENCE_SCORE - self.MIN_VISIBLE_INFLUENCE_SCORE)
            )
            blend_ratio += (1.0 - self.MIN_VISIBLE_INFLUENCE_COLOR_BLEND) * scaled_score
        blended_rgb = tuple(
            round(255 + ((channel - 255) * blend_ratio))
            for channel in player_rgb
        )
        return f'\033[38;2;{blended_rgb[0]};{blended_rgb[1]};{blended_rgb[2]}m'

    def _get_tile_symbol_for_view(self, tile: Tile, visible_tiles: set[tuple[int, int]] = None,
                                  discovered_tiles: set[tuple[int, int]] = None):
        if visible_tiles is not None and discovered_tiles is not None:
            position = (tile.x, tile.y)
            if position not in discovered_tiles:
                return ' ', None, None
            if position not in visible_tiles:
                return tile.symbol, None, None

        city = self.get_city(tile.city_id) if tile.city_id is not None else None
        regiment = self.get_regiment(tile.regiment_id) if tile.regiment_id is not None else None
        improvement = self.get_improvement(tile.improvement_id) if tile.improvement_id is not None else None
        resource = self.get_resource(tile.resource_id) if tile.resource_id is not None else None
        if regiment is not None:
            return regiment.symbol(), city, regiment
        if city is not None:
            return city.symbol, city, regiment
        if improvement is not None:
            return improvement.symbol, city, regiment
        if resource is not None:
            return resource.symbol, city, regiment
        return tile.symbol, city, regiment

    def print(self, viewer_player_id: int = None):
        visible_tiles = None
        discovered_tiles = None
        if viewer_player_id is not None:
            visible_tiles = self.get_player_visible_tiles(viewer_player_id)
            discovered_tiles = self.update_player_discovery(viewer_player_id)

        # Get the max character length for each column of the map for proper alignment
        col_widths = []
        for x in range(self.width):
            col_width = len(str(x))
            for y in range(self.height):
                tile = self.tiles[(x, y)]
                symbol, _, _ = self._get_tile_symbol_for_view(tile, visible_tiles, discovered_tiles)
                col_width = max(col_width, len(symbol))
            col_widths.append(col_width)

        # Print the map
        print(f'\nMAP:')
        row_label_width = max(1, len(str(self.height - 1)))
        header_padding = ' ' * (row_label_width + 1)
        print(f"{header_padding}{' '.join(str(x).center(col_widths[x]) for x in range(self.width))}")
        for y in range(self.height):
            row_display = [str(y).rjust(row_label_width)]
            for x in range(self.width):
                tile = self.tiles[(x, y)]
                symbol, city, regiment = self._get_tile_symbol_for_view(tile, visible_tiles, discovered_tiles)
                display_symbol = symbol.center(col_widths[x])
                if viewer_player_id is not None and (x, y) not in visible_tiles:
                    row_display.append(display_symbol)
                    continue
                tile_owner = self.get_player(tile.influence_owner_id) if tile.influence_owner_id is not None else None
                influence_score = tile.influence_scores.get(tile_owner.id, 0.0) if tile_owner is not None else 0.0
                color_code = (
                    self._get_influence_gradient_color_code(tile_owner.color, influence_score)
                    if tile_owner is not None else ''
                )
                if color_code:
                    display_symbol = f'{color_code}{display_symbol}{Style.RESET_ALL}'
                row_display.append(display_symbol)
            print(' '.join(row_display))

        # Print the legend
        legend_entries = [f"{t}={Tile._allowable_types[t]['symbol']}" \
                          for t in Tile._allowable_types.keys()]
        for s in City._city_symbols:
            legend_entries.append(f'{s}={City._city_symbols[s]}')
        legend_entries.append('Regiment=R<id>(owner_id)')
        legend_entries.append('Navy=N<id>(owner_id)')
        legend_entries.append('Improvement symbols=Gr/Mk/Ba/Wa/Ca/Wt/Fa/Lu/Qu/Po')
        legend_entries.append('Resource symbols=Wh/Ho/Ti/Ir/St/Fi/Pe/Ge')
        legend_entries.append('Undiscovered=<space>')
        legend_entries.append('Influence tint: 0.0=white, 0.01+=40% player color, 1.0=full player color')
        print('-----\nLEGEND:')
        for l in legend_entries:
            print(l, end='; ') if l != legend_entries[-1] else print(l)
        print('\n')

    def print_player_metadata(self, sort_by: str = 'influence', show_rank: bool = True):
        if not self.players:
            print('No player metadata is loaded.')
            return

        if sort_by == 'influence':
            player_entries = self.get_player_influence_rankings()
        elif sort_by in {'player_id', 'id'}:
            player_entries = [
                (player, self.get_player_total_influence_score(player.id))
                for player in sorted(self.players.values(), key=lambda player: player.id)
            ]
        else:
            raise ValueError(f'Unsupported player metadata sort order: {sort_by}')

        print('PLAYERS:')
        for rank, (player, total_influence_score) in enumerate(player_entries, start=1):
            color_code = self._get_player_color_code(player.color)
            prefix = f'{rank}. ' if show_rank else ''
            player_text = (
                f'{prefix}P{player.id}: {player.name} ({player.color}) | '
                f'controller={player.controller_type} | total influence={total_influence_score:.2f} | '
                f'materials={player.materials_summary()}'
            )
            if color_code:
                player_text = f'{color_code}{player_text}{Style.RESET_ALL}'
            print(f'  {player_text}')
        print('')

    def print_city_metadata(self, viewer_player_id: int = None):
        if not self.cities:
            print('No city metadata is loaded.')
            return

        visible_tiles = None
        if viewer_player_id is not None:
            visible_tiles = self.get_player_visible_tiles(viewer_player_id)
            self.update_player_discovery(viewer_player_id)

        visible_city_count = 0
        print('CITIES:')
        for city in self.cities.values():
            location = self.get_city_location(city.id)
            if viewer_player_id is not None:
                if location is None or location not in visible_tiles:
                    continue
            visible_city_count += 1
            city_type = 'Capital' if city.is_capital else 'City'
            owner = self.get_player(city.owner_id)
            owner_name = owner.name if owner is not None else f'Unknown({city.owner_id})'
            owner_color = self._get_player_color_code(owner.color) if owner is not None else ''
            if owner_color:
                owner_name = f'{owner_color}{owner_name}{Style.RESET_ALL}'
            location_text = f'({location[0]}, {location[1]})' if location is not None else 'UNPLACED'
            print(
                f'  {city_type} {city.id}: {city.name} | owner={owner_name} | '
                f'level={city.level} xp={city.experience} | population={city.population} | attack={city.effective_attack_score()} | '
                f'defense={city.effective_defense_score()} | siege={city.siege_resistance}/{city.max_siege_resistance} | '
                f'line_of_sight={city.effective_line_of_sight_radius()} | queue={city.queue_capacity()} | location={location_text}'
            )
            city_improvements = self.get_city_improvements(city.id)
            if city_improvements:
                print(f'    improvements: {", ".join(improvement.name for improvement in city_improvements)}')
            city_resources = self.get_city_visible_resources(city.id)
            if city_resources:
                print(f'    resources in sight: {", ".join(resource.name for resource in city_resources)}')
            if city.occupation_recovery_turns_remaining > 0:
                print(
                    f'    occupation recovery: {city.occupation_recovery_turns_remaining} turn(s) remaining | '
                    f'influence multiplier={city.occupation_influence_multiplier():.2f}'
                )
            if city.siege_repair_delay_turns_remaining > 0:
                print(
                    f'    siege repairs: delayed for {city.siege_repair_delay_turns_remaining} turn(s) | '
                    f'regiment production lock={city.regiment_production_lock_turns_remaining}'
                )
        if visible_city_count == 0:
            print('  No cities or capitals are currently within line of sight.')
        print('')

class MapLoader:

    def __init__(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as map_file:
            self.map_data = map_file.read()

    def parse(self):
        width = None
        height = None
        default_type = 'grass'
        explicit_tiles: dict[tuple[int, int], str] = {}
        players_data: dict[int, dict] = {}
        cities_data: dict[int, dict] = {}
        tile_city_attachments: dict[tuple[int, int], int] = {}
        tile_city_kinds: dict[tuple[int, int], str] = {}

        for line_number, raw_line in enumerate(self.map_data.splitlines(), start=1):
            line = raw_line.split('#', 1)[0].strip()
            if not line:
                continue
            parts = line.split()
            keyword = parts[0].lower()

            if keyword == 'size' and len(parts) == 3:
                width, height = int(parts[1]), int(parts[2])
            elif keyword == 'default' and len(parts) == 2:
                default_type = parts[1]
            elif keyword == 'player' and len(parts) >= 4:
                player_id = int(parts[1])
                player_color = parts[-1]
                player_name = ' '.join(parts[2:-1])
                players_data[player_id] = {
                    'id': player_id,
                    'name': player_name,
                    'color': player_color,
                }
            elif keyword in {'city', 'capital'} and len(parts) >= 5:
                city_id = int(parts[1])
                owner_id = int(parts[2])
                city_population = int(parts[-1])
                city_name = ' '.join(parts[3:-1])
                cities_data[city_id] = {
                    'id': city_id,
                    'name': city_name,
                    'owner_id': owner_id,
                    'population': city_population,
                    'is_capital': keyword == 'capital',
                }
            elif len(parts) == 4 and parts[2].lower() in {'city', 'capital'}:
                x, y = int(parts[0]), int(parts[1])
                city_id = int(parts[3])
                tile_city_attachments[(x, y)] = city_id
                tile_city_kinds[(x, y)] = parts[2].lower()
            elif len(parts) == 3:
                x, y, tile_type = int(parts[0]), int(parts[1]), parts[2]
                explicit_tiles[(x, y)] = tile_type
            else:
                raise ValueError(f'Unsupported map directive at line {line_number}: "{raw_line}"')

        if width is None or height is None:
            raise ValueError('Map file missing required "size" directive')

        game_map = Map(width=width, height=height, default_tile=default_type)

        for player_data in players_data.values():
            game_map.add_player(Player(
                id=player_data['id'],
                name=player_data['name'],
                color=player_data['color'],
            ))

        for city_data in cities_data.values():
            game_map.add_city(City(
                id=city_data['id'],
                name=city_data['name'],
                owner_id=city_data['owner_id'],
                population=city_data['population'],
                is_capital=city_data['is_capital'],
            ))

        for city_id in tile_city_attachments.values():
            if city_id not in game_map.cities:
                raise ValueError(f'Tile references undefined city_id={city_id}')

        for position, kind in tile_city_kinds.items():
            if kind == 'capital':
                game_map.cities[tile_city_attachments[position]].mark_as_capital()

        for y in range(height):
            for x in range(width):
                tile_type = explicit_tiles.get((x, y), default_type)
                game_map.tiles[(x, y)] = Tile(
                    type=tile_type,
                    x=x,
                    y=y,
                    city_id=tile_city_attachments.get((x, y)),
                )

        game_map.populate_resources()
        game_map.refresh_all_player_discovery()
        return game_map

class Menu:

    def __init__(self):
        self.options = []

    def add_option(self, title: str, listener = None, shortcut: str = None):
        if not isinstance(title, str) or not title.strip():
            raise ValueError('Menu option title must be a non-empty string')
        if listener is not None and not callable(listener):
            raise ValueError('Menu option listener must be callable')

        if shortcut is None:
            shortcut = title.strip()[0]
        if not isinstance(shortcut, str) or len(shortcut.strip()) != 1:
            raise ValueError('Menu option shortcut must be a single letter')

        self.options.append({
            'title': title.strip(),
            'shortcut': shortcut.strip().lower(),
            'listener': listener,
        })
        return len(self.options) - 1

    def set_listener(self, selection, listener):
        if not callable(listener):
            raise ValueError('Menu option listener must be callable')
        index = self._resolve_option_index(selection)
        self.options[index]['listener'] = listener

    def select_option(self, selection):
        index = self._resolve_option_index(selection)
        option = self.options[index]
        if option['listener'] is not None:
            return option['listener']()
        return option

    def _resolve_option_index(self, selection):
        if not self.options:
            raise ValueError('No menu options are available')

        if isinstance(selection, int):
            if 0 <= selection < len(self.options):
                return selection
            if 1 <= selection <= len(self.options):
                return selection - 1
            raise ValueError(f'Invalid menu selection: {selection}')

        normalized = str(selection).strip().lower()
        if not normalized:
            raise ValueError('Menu selection cannot be empty')

        if normalized.isdigit():
            selected = int(normalized)
            if 1 <= selected <= len(self.options):
                return selected - 1

        for index, option in enumerate(self.options):
            if normalized == option['title'].lower():
                return index
            if normalized == option['shortcut']:
                return index

        raise ValueError(f'Invalid menu selection: {selection}')

class ConsoleMenu(Menu):

    def __init__(self):
        super().__init__()

    def print_options(self):
        for index, option in enumerate(self.options, start=1):
            print(f'{index}. ({option["shortcut"]}) {option["title"]}')

    def prompt_and_select(self, prompt: str = 'Select an option: '):
        while True:
            self.print_options()
            selection = input(prompt)
            try:
                return self.select_option(selection)
            except ValueError as error:
                print(error)

class SimpleAiController:

    MIN_REGIMENT_ATTACK_SCORE = 0.0
    MIN_CITY_ATTACK_SCORE = -10.0
    THREAT_RADIUS = 2

    def __init__(self, rng = None):
        self.rng = rng if rng is not None else random.Random()

    def plan_turn(self, game, player_id: int):
        if game.map is None or game.map.get_player(player_id) is None:
            return []

        player = game.map.get_player(player_id)
        action_limit = game.get_player_action_limit(player_id)
        card_limit = min(action_limit, game.get_player_card_limit(player_id))
        actions = []
        reserved_materials = dict(player.materials)
        reserved_regiment_targets = set()
        reserved_city_targets = set()
        actions.extend(self._plan_card_actions(game, player_id, action_limit, card_limit))
        if len(actions) < action_limit:
            improvement_actions, reserved_materials = self._plan_improvement_orders(
                game,
                player_id,
                action_limit - len(actions),
                reserved_materials,
            )
            actions.extend(improvement_actions)
        if len(actions) < action_limit:
            force_actions, reserved_materials = self._plan_regiment_orders(
                game,
                player_id,
                action_limit - len(actions),
                reserved_materials,
            )
            actions.extend(force_actions)

        regiments = sorted(
            game.get_player_regiments(player_id),
            key=lambda regiment: (-regiment.total_units(), regiment.id),
        )
        for regiment in regiments:
            if len(actions) >= action_limit:
                break
            if game.map.get_regiment(regiment.id) is None:
                continue
            action = self._plan_regiment_action(
                game,
                player_id,
                regiment,
                reserved_regiment_targets,
                reserved_city_targets,
            )
            if action is None:
                continue
            actions.append(action)
            if action['action_type'] == 'attack_regiment':
                reserved_regiment_targets.add(action['target_id'])
            elif action['action_type'] == 'attack_city':
                reserved_city_targets.add(action['target_id'])
        return actions[:action_limit]

    def _can_reserve_costs(self, budget: dict[str, int], costs: dict[str, int]):
        return all(int(budget.get(material_type, 0)) >= int(amount) for material_type, amount in costs.items())

    def _reserve_costs(self, budget: dict[str, int], costs: dict[str, int]):
        updated_budget = dict(budget)
        for material_type, amount in costs.items():
            updated_budget[material_type] = int(updated_budget.get(material_type, 0)) - int(amount)
        return updated_budget

    def _plan_improvement_orders(self, game, player_id: int, available_slots: int, reserved_materials: dict[str, int]):
        if available_slots <= 0:
            return [], reserved_materials
        owned_cities = sorted(
            game.get_player_cities(player_id),
            key=lambda city: (not city.is_capital, -city.level, -city.population, city.id),
        )
        actions = []
        budget = dict(reserved_materials)
        for city in owned_cities:
            if len(actions) >= available_slots:
                break
            if game.get_city_queue_space_remaining(player_id, city.id) <= 0:
                continue
            candidate_improvements = []
            if city.level >= 2 and not game.map.get_city_ports(city.id):
                candidate_improvements.append('port')
            if not any(improvement.improvement_kind == 'market' for improvement in game.map.get_city_improvements(city.id)):
                candidate_improvements.append('market')
            if not any(improvement.improvement_kind == 'barracks' for improvement in game.map.get_city_improvements(city.id)):
                candidate_improvements.append('barracks')
            candidate_improvements.extend(['farm', 'lumber_mill', 'quarry'])
            for improvement_kind in candidate_improvements:
                try:
                    definition = game.get_improvement_definition(improvement_kind)
                except ValueError:
                    continue
                if city.level < definition.min_city_level:
                    continue
                if not self._can_reserve_costs(budget, definition.costs):
                    continue
                valid_sites = game.find_valid_improvement_sites_for_city(city.id, definition.improvement_kind)
                if not valid_sites:
                    continue
                target_pos = None if definition.intra_city else valid_sites[0]
                actions.append({
                    'action_type': 'queue_improvement',
                    'player_id': player_id,
                    'actor_id': city.id,
                    'target_id': city.id,
                    'metadata': {
                        'improvement_kind': definition.improvement_kind,
                        'improvement_name': definition.name,
                        'target_pos': target_pos,
                    },
                })
                budget = self._reserve_costs(budget, definition.costs)
                break
        return actions, budget

    def _plan_regiment_orders(self, game, player_id: int, available_slots: int, reserved_materials: dict[str, int]):
        if available_slots <= 0:
            return [], reserved_materials
        owned_cities = sorted(
            game.get_player_cities(player_id),
            key=lambda city: (not city.is_capital, -city.population, city.id),
        )
        if not owned_cities:
            return [], reserved_materials

        owned_regiments = game.get_player_regiments(player_id)
        active_regiments = len([regiment for regiment in owned_regiments if not regiment.is_navy()])
        active_navies = len([regiment for regiment in owned_regiments if regiment.is_navy()])
        queued_regiments = sum(
            1 for order in game.regiment_build_queue
            if order['owner_id'] == player_id and order.get('order_kind', 'force') == 'force'
            and order.get('force_kind', 'regiment') == 'regiment'
        )
        queued_navies = sum(
            1 for order in game.regiment_build_queue
            if order['owner_id'] == player_id and order.get('order_kind', 'force') == 'force'
            and order.get('force_kind', 'regiment') == 'navy'
        )
        desired_regiments = max(2, len(owned_cities) * 2)
        influence_score = game.map.get_player_total_influence_score(player_id)
        desired_navies = 0
        if any(game.map.get_city_ports(city.id) for city in owned_cities):
            desired_navies = 1
            if influence_score >= 30000:
                desired_navies += 1
            if influence_score >= 70000:
                desired_navies += 1
            desired_navies = min(desired_navies, max(1, len(owned_cities)))
        if active_regiments + queued_regiments >= desired_regiments:
            threatened_cities = {
                city.id for city in owned_cities
                if game.map.get_enemy_regiments_in_range_of_city(city.id)
            }
        else:
            threatened_cities = set()

        actions = []
        budget = dict(reserved_materials)
        queued_this_turn = active_regiments + queued_regiments
        queued_navies_total = active_navies + queued_navies
        for city in owned_cities:
            if len(actions) >= available_slots:
                break
            if not city.can_queue_regiment():
                continue
            if game.get_city_queue_space_remaining(player_id, city.id) <= len([
                action for action in actions if action['target_id'] == city.id
            ]):
                continue
            if queued_navies_total < desired_navies:
                spawn_pos = self._find_best_navy_spawn_tile(game, player_id, city)
                navy_cost = game.get_force_order_cost(city, 'navy')
                if spawn_pos is not None and self._can_reserve_costs(budget, navy_cost):
                    navy_name = f'{city.name} Fleet T{game.turn}'
                    actions.append({
                        'action_type': 'queue_navy',
                        'player_id': player_id,
                        'actor_id': city.id,
                        'target_id': city.id,
                        'target_pos': spawn_pos,
                        'metadata': {
                            'regiment_name': navy_name,
                            'spawn_pos': spawn_pos,
                            'priority': 110 if city.is_capital else 90,
                        },
                    })
                    budget = self._reserve_costs(budget, navy_cost)
                    queued_navies_total += 1
                    continue
            should_queue = queued_this_turn < desired_regiments or city.id in threatened_cities
            if not should_queue:
                continue
            regiment_cost = game.get_force_order_cost(city, 'regiment')
            if not self._can_reserve_costs(budget, regiment_cost):
                continue
            regiment_name = f'{city.name} Guard T{game.turn}'
            actions.append({
                'action_type': 'queue_regiment',
                'player_id': player_id,
                'actor_id': city.id,
                'target_id': city.id,
                'target_pos': game.map.get_city_location(city.id),
                'metadata': {
                    'regiment_name': regiment_name,
                    'priority': 100 if city.is_capital else 80,
                },
            })
            budget = self._reserve_costs(budget, regiment_cost)
            queued_this_turn += 1
        return actions, budget

    def _plan_card_actions(self, game, player_id: int, action_limit: int, card_limit: int):
        player = game.map.get_player(player_id)
        if player is None or player.deck is None or not player.can_play_cards() or not player.hand:
            return []

        actions = []
        card_budget = min(card_limit, max(1, math.ceil(action_limit / 2)))
        for card in sorted(
            player.hand,
            key=lambda candidate: (
                -CardLibrary.RARITY_ORDER.get(candidate.definition.rarity, 0),
                0 if candidate.definition.card_type == 'duration' else 1,
                candidate.instance_id,
            ),
        ):
            if len(actions) >= min(action_limit, card_budget):
                break
            action = self._build_card_action(game, player, card)
            if action is not None:
                actions.append(action)
        return actions

    def _find_best_navy_spawn_tile(self, game, player_id: int, city: City):
        port_positions = [
            tuple(port.tile_pos)
            for port in game.map.get_city_ports(city.id)
            if port.tile_pos is not None
        ]
        if not port_positions:
            return None
        city_location = game.map.get_city_location(city.id)
        enemy_city_locations = [
            game.map.get_city_location(enemy_city.id)
            for enemy_city in game.get_visible_enemy_cities(player_id)
            if game.map.get_city_location(enemy_city.id) is not None
        ]
        return min(
            port_positions,
            key=lambda position: (
                0 if game.map.tiles[position].influence_owner_id == player_id else 1,
                min(
                    (game.map.get_tile_distance(position, enemy_position) for enemy_position in enemy_city_locations),
                    default=game.map.get_tile_distance(position, city_location) if city_location is not None else 99,
                ),
                game.map.get_tile_distance(position, city_location) if city_location is not None else 99,
                position,
            ),
        )

    def _build_card_action(self, game, player: Player, card: Card):
        payload = {}
        target_scope = card.definition.target_scope
        effect_types = {effect.effect_type for effect in card.definition.effects}

        if target_scope == 'own_regiment':
            target = self._choose_card_friendly_regiment(game, player.id, effect_types)
            if target is None:
                return None
            payload['target_kind'] = 'regiment'
            payload['target_id'] = target.id
        elif target_scope == 'enemy_regiment':
            target = self._choose_card_enemy_regiment(game, player.id)
            if target is None:
                return None
            payload['target_kind'] = 'regiment'
            payload['target_id'] = target.id
        elif target_scope == 'own_city':
            target = self._choose_card_friendly_city(game, player.id)
            if target is None:
                return None
            payload['target_kind'] = 'city'
            payload['target_id'] = target.id
        elif target_scope == 'enemy_city':
            target = self._choose_card_enemy_city(game, player.id)
            if target is None:
                return None
            payload['target_kind'] = 'city'
            payload['target_id'] = target.id
        elif target_scope == 'enemy_player':
            target = self._choose_card_enemy_player(game, player.id)
            if target is None:
                return None
            payload['target_kind'] = 'player'
            payload['target_id'] = target.id
        elif target_scope not in {'self', 'none'}:
            return None

        if 'modify_regiment_units' in effect_types:
            regiment = game.map.get_regiment(payload.get('target_id')) if payload.get('target_kind') == 'regiment' else None
            if regiment is None:
                return None
            effect = next(effect for effect in card.definition.effects if effect.effect_type == 'modify_regiment_units')
            payload['unit_type'] = self._choose_card_unit_type(regiment, int(effect.magnitude))
            if payload['unit_type'] is None:
                return None

        if 'gain_random_card_by_rarity' in effect_types:
            influence_score = game.map.get_player_total_influence_score(player.id)
            payload['rarity'] = 'legendary' if influence_score >= 90000 else 'rare' if influence_score >= 40000 else 'uncommon'

        if 'choose_from_top_cards' in effect_types:
            payload['choice_index'] = 0

        return {
            'action_type': 'play_card',
            'player_id': player.id,
            'metadata': {
                'card_instance_id': card.instance_id,
                'card_name': card.definition.name,
                'target_payload': payload,
            },
        }

    def _choose_card_friendly_regiment(self, game, player_id: int, effect_types: set[str]):
        regiments = game.get_player_regiments(player_id)
        if 'grant_terrain_boundary_pass' in effect_types:
            regiments = [regiment for regiment in regiments if not regiment.is_navy()]
        if not regiments:
            return None
        return max(
            regiments,
            key=lambda regiment: (
                regiment.effective_city_attack_score() + regiment.effective_regiment_attack_score(),
                regiment.total_units(),
                -regiment.id,
            ),
        )

    def _choose_card_enemy_regiment(self, game, player_id: int):
        enemy_regiments = game.get_visible_enemy_regiments(player_id)
        if not enemy_regiments:
            return None
        return max(
            enemy_regiments,
            key=lambda regiment: (
                regiment.effective_regiment_attack_score(),
                regiment.total_units(),
                -regiment.id,
            ),
        )

    def _choose_card_friendly_city(self, game, player_id: int):
        cities = game.get_player_cities(player_id)
        if not cities:
            return None
        return max(cities, key=lambda city: (city.is_capital, city.population, -city.id))

    def _choose_card_enemy_city(self, game, player_id: int):
        cities = game.get_visible_enemy_cities(player_id)
        if not cities:
            return None
        return max(cities, key=lambda city: (city.is_capital, city.population, -city.id))

    def _choose_card_enemy_player(self, game, player_id: int):
        opponents = [
            player for player in game.map.players.values()
            if player.id != player_id
        ]
        if not opponents:
            return None
        return max(
            opponents,
            key=lambda opponent: (
                game.map.get_player_total_influence_score(opponent.id),
                -opponent.id,
            ),
        )

    def _choose_card_unit_type(self, regiment: Regiment, magnitude: int):
        if magnitude > 0:
            return 'navy' if regiment.is_navy() else 'infantry'
        candidate_types = ['navy'] if regiment.is_navy() else ['infantry', 'ranged', 'cavalry', 'siege']
        available = [unit_type for unit_type in candidate_types if getattr(regiment, unit_type) > 0]
        return max(available, key=lambda unit_type: getattr(regiment, unit_type), default=None)

    def _plan_regiment_action(self, game, player_id: int, regiment: Regiment,
                              reserved_regiment_targets: set[int], reserved_city_targets: set[int]):
        if regiment.total_units() <= 0:
            return None

        best_attack = self._find_best_attack_action(
            game,
            player_id,
            regiment,
            reserved_regiment_targets,
            reserved_city_targets,
        )
        if best_attack is not None:
            return best_attack

        best_move = self._find_best_move_action(game, player_id, regiment)
        if best_move is not None:
            return best_move

        if self._should_defend(game, player_id, regiment):
            location = game.map.get_regiment_location(regiment.id)
            return {
                'action_type': 'defend_regiment',
                'player_id': player_id,
                'actor_id': regiment.id,
                'target_id': regiment.id,
                'target_pos': location,
                'metadata': {'priority': 20},
            }
        return None

    def _find_best_attack_action(self, game, player_id: int, regiment: Regiment,
                                 reserved_regiment_targets: set[int], reserved_city_targets: set[int]):
        if not regiment.can_attack_this_turn() or regiment.is_defending:
            return None

        origin = game.map.get_regiment_location(regiment.id)
        if origin is None:
            return None

        best_action = None
        best_score = None

        for enemy_regiment in game.get_visible_enemy_regiments(player_id):
            if enemy_regiment.id in reserved_regiment_targets:
                continue
            target_location = game.map.get_regiment_location(enemy_regiment.id)
            if target_location is None:
                continue
            attack_distance = game.map.get_tile_distance(origin, target_location)
            if not regiment.can_attack_distance(attack_distance):
                continue
            score = self._score_regiment_attack(game, regiment, enemy_regiment)
            if score < self.MIN_REGIMENT_ATTACK_SCORE:
                continue
            action = {
                'action_type': 'attack_regiment',
                'player_id': player_id,
                'actor_id': regiment.id,
                'target_id': enemy_regiment.id,
                'target_pos': target_location,
                'metadata': {'score': round(score, 2), 'target_kind': 'regiment'},
            }
            if best_score is None or score > best_score:
                best_score = score
                best_action = action

        for enemy_city in game.get_visible_enemy_cities(player_id):
            if enemy_city.id in reserved_city_targets:
                continue
            target_location = game.map.get_city_location(enemy_city.id)
            if target_location is None:
                continue
            attack_distance = game.map.get_tile_distance(origin, target_location)
            if not regiment.can_attack_distance(attack_distance):
                continue
            score = self._score_city_attack(game, regiment, enemy_city)
            if score < self.MIN_CITY_ATTACK_SCORE:
                continue
            action = {
                'action_type': 'attack_city',
                'player_id': player_id,
                'actor_id': regiment.id,
                'target_id': enemy_city.id,
                'target_pos': target_location,
                'metadata': {'score': round(score, 2), 'target_kind': 'city'},
            }
            if best_score is None or score > best_score:
                best_score = score
                best_action = action
        return best_action

    def _score_regiment_attack(self, game, attacker: Regiment, defender: Regiment):
        attacker_pressure = (
            attacker.effective_regiment_attack_score() *
            (attacker.total_units() ** Regiment.FORCE_SIZE_EXPONENT)
        )
        defender_pressure = (
            defender.effective_regiment_attack_score() *
            (defender.total_units() ** Regiment.FORCE_SIZE_EXPONENT)
        )
        score = (
            (attacker_pressure / max(1.0, defender.effective_defense_factor())) -
            (defender_pressure / max(1.0, attacker.effective_defense_factor()))
        )
        score += (attacker.total_units() - defender.total_units()) * 2.5
        defender_location = game.map.get_regiment_location(defender.id)
        if defender_location is not None:
            defender_tile = game.map.tiles.get(defender_location)
            if defender_tile is not None and defender_tile.is_influence_contested:
                score += 10
        threatened_cities = [
            city for city in game.get_player_cities(attacker.owner_id)
            if game.map.get_city_location(city.id) is not None and
            defender_location is not None and
            game.map.get_tile_distance(game.map.get_city_location(city.id), defender_location) <= self.THREAT_RADIUS
        ]
        score += len(threatened_cities) * 18
        return score

    def _score_city_attack(self, game, attacker: Regiment, city: City):
        city_pressure = (
            attacker.effective_city_attack_score() *
            (attacker.total_units() ** Regiment.FORCE_SIZE_EXPONENT)
        )
        resistance_ratio = city.siege_resistance / max(city.max_siege_resistance, 1.0)
        score = city_pressure - (city.effective_defense_score() * 1.15)
        score += 30 if city.is_capital else 18
        score += (1.0 - resistance_ratio) * 22
        city_location = game.map.get_city_location(city.id)
        if city_location is not None:
            tile = game.map.tiles.get(city_location)
            if tile is not None and tile.is_influence_contested:
                score += 8
        return score

    def _find_best_move_action(self, game, player_id: int, regiment: Regiment):
        if regiment.movement_remaining() <= 0:
            return None
        origin = game.map.get_regiment_location(regiment.id)
        if origin is None:
            return None

        objectives = self._collect_objectives(game, player_id)
        if not objectives:
            return None

        current_score = self._score_position(game, player_id, origin, objectives)
        best_position = None
        best_score = current_score
        min_x = max(0, origin[0] - regiment.movement_remaining())
        max_x = min(game.map.width - 1, origin[0] + regiment.movement_remaining())
        min_y = max(0, origin[1] - regiment.movement_remaining())
        max_y = min(game.map.height - 1, origin[1] + regiment.movement_remaining())

        visible_tiles = game.map.get_player_visible_tiles(player_id)
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                if (x, y) == origin:
                    continue
                if (x, y) not in visible_tiles:
                    continue
                if game.map.get_tile_distance(origin, (x, y)) > regiment.movement_remaining():
                    continue
                tile = game.map.tiles[(x, y)]
                if tile.regiment_id is not None:
                    continue
                if not game.map.can_place_regiment_on_tile(regiment, tile):
                    continue
                score = self._score_position(game, player_id, (x, y), objectives)
                if score > best_score + 4:
                    best_score = score
                    best_position = (x, y)

        if best_position is None:
            return None
        return {
            'action_type': 'move_regiment',
            'player_id': player_id,
            'actor_id': regiment.id,
            'target_id': None,
            'target_pos': best_position,
            'metadata': {'score': round(best_score, 2)},
        }

    def _collect_objectives(self, game, player_id: int):
        objectives = []
        visible_tiles = game.map.get_player_visible_tiles(player_id)
        enemy_cities = sorted(
            game.get_visible_enemy_cities(player_id),
            key=lambda city: (not city.is_capital, city.id),
        )
        for city in enemy_cities:
            city_location = game.map.get_city_location(city.id)
            if city_location is None:
                continue
            tile = game.map.tiles.get(city_location)
            priority = 140 if city.is_capital else 100
            if tile is not None and tile.is_influence_contested:
                priority += 15
            objectives.append({'kind': 'city', 'position': city_location, 'priority': priority, 'target_id': city.id})

        for regiment in game.get_visible_enemy_regiments(player_id):
            position = game.map.get_regiment_location(regiment.id)
            if position is None:
                continue
            priority = 72 + max(0, 18 - regiment.total_units())
            objectives.append({'kind': 'regiment', 'position': position, 'priority': priority, 'target_id': regiment.id})

        for position in sorted(visible_tiles):
            tile = game.map.tiles[position]
            if tile.is_influence_contested:
                objectives.append({'kind': 'contested_tile', 'position': position, 'priority': 62, 'target_id': None})
            elif tile.influence_owner_id not in {None, player_id}:
                objectives.append({'kind': 'enemy_influence', 'position': position, 'priority': 48, 'target_id': tile.influence_owner_id})
        return objectives

    def _score_position(self, game, player_id: int, position: tuple[int, int], objectives: list[dict]):
        tile = game.map.tiles[position]
        best_objective_score = max(
            objective['priority'] - (game.map.get_tile_distance(position, objective['position']) * 12)
            for objective in objectives
        )
        if tile.is_influence_contested:
            best_objective_score += 12
        elif tile.influence_owner_id not in {None, player_id}:
            best_objective_score += 8

        if tile.city_id is not None:
            city = game.map.get_city(tile.city_id)
            if city is not None and city.owner_id != player_id:
                best_objective_score += 20 if city.is_capital else 14
        return best_objective_score

    def _should_defend(self, game, player_id: int, regiment: Regiment):
        if regiment.is_defending or regiment.movement_remaining() < 1:
            return False

        location = game.map.get_regiment_location(regiment.id)
        if location is None:
            return False

        for enemy_regiment in game.get_visible_enemy_regiments(player_id):
            enemy_location = game.map.get_regiment_location(enemy_regiment.id)
            if enemy_location is None:
                continue
            if game.map.get_tile_distance(location, enemy_location) <= enemy_regiment.attack_range():
                return True

        for city in game.get_player_cities(player_id):
            city_location = game.map.get_city_location(city.id)
            if city_location is None:
                continue
            if game.map.get_tile_distance(location, city_location) > 1:
                continue
            if game.map.get_enemy_regiments_in_range_of_city(city.id):
                return True
        return False

class Game:

    def __init__(self, map = None):
        print('Game initialized.')
        self.map = map
        self.is_running = True
        self.player_in_loop = False
        self.selected_player_id = None
        self.turn = 0
        self.regiment_build_queue = []
        self.card_library = CardLibrary()
        self.random = random.Random()
        self.ai_controller = SimpleAiController(self.random)
        self.allow_deck_reshuffle = False
        self.card_unlock_turn = 3
        self.active_victory_conditions = ['capture-all-capitals']
        self.influence_victory_threshold = None
        self.turn_order = []
        self.current_turn_player_index = 0
        self.round_planned_actions: dict[int, list[dict]] = {}
        self.last_round_summary = None

    def initialize_player_economy(self):
        if self.map is None:
            raise ValueError('A map must be loaded before initializing player economy')
        for player in self.map.players.values():
            player.reset_materials()

    def get_selected_player(self):
        if self.map is None or self.selected_player_id is None:
            return None
        return self.map.get_player(self.selected_player_id)

    def get_current_turn_player(self):
        if self.map is None or not self.turn_order:
            return None
        if self.current_turn_player_index < 0 or self.current_turn_player_index >= len(self.turn_order):
            return None
        return self.map.get_player(self.turn_order[self.current_turn_player_index])

    def assign_match_controllers(self, human_player_id: int):
        if self.map is None:
            raise ValueError('A map must be loaded before assigning controllers.')
        if self.map.get_player(human_player_id) is None:
            raise ValueError(f'Player {human_player_id} does not exist.')
        for player in self.map.players.values():
            player.controller_type = 'human' if player.id == human_player_id else 'computer'
        self.selected_player_id = human_player_id

    def initialize_turn_order(self):
        if self.map is None:
            raise ValueError('A map must be loaded before initializing turn order.')
        ordered_player_ids = sorted(self.map.players)
        if self.selected_player_id in ordered_player_ids:
            selected_index = ordered_player_ids.index(self.selected_player_id)
            ordered_player_ids = ordered_player_ids[selected_index:] + ordered_player_ids[:selected_index]
        self.turn_order = ordered_player_ids
        self.current_turn_player_index = 0
        self._reset_round_planned_actions()

    def _reset_round_planned_actions(self):
        if self.map is None:
            self.round_planned_actions = {}
            return
        self.round_planned_actions = {
            player_id: [] for player_id in sorted(self.map.players)
        }

    def _ensure_round_plan_entry(self, player_id: int):
        if player_id not in self.round_planned_actions:
            self.round_planned_actions[player_id] = []
        return self.round_planned_actions[player_id]

    def get_player_planned_actions(self, player_id: int):
        return list(self._ensure_round_plan_entry(player_id))

    def get_player_planned_action_count(self, player_id: int):
        return len(self._ensure_round_plan_entry(player_id))

    def get_player_planned_card_count(self, player_id: int):
        return sum(
            1 for action in self._ensure_round_plan_entry(player_id)
            if action['action_type'] == 'play_card'
        )

    def get_player_planned_card_instance_ids(self, player_id: int):
        return {
            action.get('metadata', {}).get('card_instance_id')
            for action in self._ensure_round_plan_entry(player_id)
            if action['action_type'] == 'play_card'
        }

    def get_player_action_limit(self, player_id: int):
        if self.map is None:
            return 3
        influence_score = self.map.get_player_total_influence_score(player_id)
        return 3 + max(0, int(influence_score // 10000))

    def get_player_card_limit(self, player_id: int):
        if self.map is None:
            return 2
        influence_score = self.map.get_player_total_influence_score(player_id)
        if influence_score < 10000:
            return 2
        return min(5, 2 + int((influence_score - 10000) // 30000))

    def _get_card_from_player_hand_by_instance_id(self, player: Player, card_instance_id: int):
        for card in player.hand:
            if card.instance_id == card_instance_id:
                return card
        return None

    def _get_player_card_hand_index_by_instance_id(self, player: Player, card_instance_id: int):
        for index, card in enumerate(player.hand):
            if card.instance_id == card_instance_id:
                return index
        return None

    def _resolve_action_target_owner_id(self, action: dict):
        if self.map is None:
            return None
        action_type = action['action_type']
        if action_type in {'queue_regiment', 'queue_navy', 'queue_improvement', 'buy_card', 'recruit_hero', 'refit_force'}:
            return action.get('player_id')
        if action_type == 'attack_regiment':
            target_regiment = self.map.get_regiment(action['target_id'])
            return None if target_regiment is None else target_regiment.owner_id
        if action_type == 'attack_city':
            target_city = self.map.get_city(action['target_id'])
            return None if target_city is None else target_city.owner_id
        if action_type == 'play_card':
            payload = action.get('metadata', {}).get('target_payload', {})
            target_kind = payload.get('target_kind')
            target_id = payload.get('target_id')
            if target_kind == 'player':
                return target_id
            if target_kind == 'regiment':
                target_regiment = self.map.get_regiment(target_id)
                return None if target_regiment is None else target_regiment.owner_id
            if target_kind == 'city':
                target_city = self.map.get_city(target_id)
                return None if target_city is None else target_city.owner_id
        return None

    def describe_planned_action(self, action: dict):
        action_type = action['action_type']
        metadata = action.get('metadata', {})
        if action_type in {'queue_regiment', 'queue_navy'}:
            city = self.map.get_city(action['target_id']) if self.map is not None else None
            city_name = city.name if city is not None else f'City {action["target_id"]}'
            regiment_name = metadata.get('regiment_name', f'{city_name} Guard')
            if action_type == 'queue_navy':
                return f'Queue navy "{regiment_name}" from {city_name} at port {metadata.get("spawn_pos")}'
            return f'Queue regiment "{regiment_name}" at {city_name}'
        if action_type == 'queue_improvement':
            city = self.map.get_city(action['target_id']) if self.map is not None else None
            city_name = city.name if city is not None else f'City {action["target_id"]}'
            improvement_name = metadata.get('improvement_name', metadata.get('improvement_kind', 'Improvement'))
            target_pos = metadata.get('target_pos')
            if target_pos is None:
                return f'Queue {improvement_name} in {city_name}'
            return f'Queue {improvement_name} for {city_name} at {target_pos}'
        if action_type == 'move_regiment':
            return f'Move Regiment {action["actor_id"]} to {action["target_pos"]}'
        if action_type == 'attack_regiment':
            return f'Regiment {action["actor_id"]} attack Regiment {action["target_id"]}'
        if action_type == 'attack_city':
            return f'Regiment {action["actor_id"]} attack City {action["target_id"]}'
        if action_type == 'defend_regiment':
            return f'Regiment {action["actor_id"]} defend'
        if action_type == 'buy_card':
            return f'Buy {metadata.get("rarity", "common")} card'
        if action_type == 'recruit_hero':
            return f'Recruit hero for Regiment {action["target_id"]}'
        if action_type == 'refit_force':
            return f'Refit Regiment {action["target_id"]} with {metadata.get("upgrade_kind", "upgrade")}'
        if action_type == 'play_card':
            card_name = metadata.get('card_name', f'Card {metadata.get("card_instance_id")}')
            payload = metadata.get('target_payload', {})
            target_kind = payload.get('target_kind')
            target_id = payload.get('target_id')
            if target_kind is not None and target_id is not None:
                return f'Play "{card_name}" on {target_kind} {target_id}'
            return f'Play "{card_name}"'
        raise ValueError(f'Unsupported planned action type: {action_type}')

    def print_player_planned_actions(self, player_id: int):
        player = self.map.get_player(player_id) if self.map is not None else None
        if player is None:
            raise ValueError(f'Player {player_id} does not exist')
        planned_actions = self.get_player_planned_actions(player_id)
        action_limit = self.get_player_action_limit(player_id)
        card_limit = min(action_limit, self.get_player_card_limit(player_id))
        print(
            f'PLANNED ACTIONS: {len(planned_actions)}/{action_limit} | '
            f'cards={self.get_player_planned_card_count(player_id)}/{card_limit}'
        )
        if not planned_actions:
            print('  No actions planned yet.')
            print('')
            return
        for index, action in enumerate(planned_actions, start=1):
            print(f'  {index}. {self.describe_planned_action(action)}')
        print('')

    def _validate_planned_action(self, player_id: int, action: dict):
        if self.map is None:
            raise ValueError('A map must be loaded before planning actions.')
        action_type = action['action_type']
        metadata = action.setdefault('metadata', {})

        if action_type in {'queue_regiment', 'queue_navy'}:
            city = self.map.get_city(action['target_id'])
            if city is None:
                raise ValueError(f'City {action["target_id"]} does not exist.')
            if city.owner_id != player_id:
                raise ValueError(f'City {city.id} belongs to another empire.')
            if not city.can_queue_regiment():
                raise ValueError(
                    f'{city.name} cannot produce regiments for {city.regiment_production_lock_turns_remaining} more turn(s) '
                    f'while the occupation is being stabilized.'
                )
            if self.get_city_queue_space_remaining(player_id, city.id) <= 0:
                raise ValueError(f'{city.name} has no open production queue slots.')
            if action_type == 'queue_navy':
                spawn_pos = metadata.get('spawn_pos')
                if spawn_pos is None or len(spawn_pos) != 2:
                    raise ValueError('Navy plans require a port tile spawn position.')
                self._validate_navy_spawn_tile(player_id, city.id, int(spawn_pos[0]), int(spawn_pos[1]))
            return action

        if action_type == 'queue_improvement':
            city_id = action['target_id']
            if self.get_city_queue_space_remaining(player_id, city_id) <= 0:
                city = self.map.get_city(city_id)
                city_name = city.name if city is not None else f'City {city_id}'
                raise ValueError(f'{city_name} has no open production queue slots.')
            city, definition, normalized_target = self._validate_improvement_order(
                player_id,
                city_id,
                metadata.get('improvement_kind'),
                metadata.get('target_pos'),
            )
            metadata['improvement_kind'] = definition.improvement_kind
            metadata['improvement_name'] = definition.name
            metadata['target_pos'] = normalized_target
            return action

        if action_type == 'move_regiment':
            regiment = self.map.get_regiment(action['actor_id'])
            if regiment is None:
                raise ValueError(f'Regiment {action["actor_id"]} does not exist.')
            if regiment.owner_id != player_id:
                raise ValueError(f'Regiment {regiment.id} belongs to another empire.')
            if self.map.get_regiment_location(regiment.id) is None:
                raise ValueError(f'Regiment {regiment.id} is not on the map.')
            target_x, target_y = action['target_pos']
            if (target_x, target_y) not in self.map.tiles:
                raise ValueError(f'Target tile ({target_x}, {target_y}) is out of bounds.')
            target_tile = self.map.tiles[(target_x, target_y)]
            if target_tile.regiment_id is not None:
                raise ValueError(f'Target tile ({target_x}, {target_y}) already has a regiment.')
            if not self.map.can_place_regiment_on_tile(regiment, target_tile):
                if regiment.is_navy():
                    raise ValueError(f'Target tile ({target_x}, {target_y}) is not passable for navy forces.')
                raise ValueError(f'Target tile ({target_x}, {target_y}) is not passable for land regiments.')
            distance = self.map.get_tile_distance(self.map.get_regiment_location(regiment.id), (target_x, target_y))
            if not regiment.can_move_distance(distance):
                raise ValueError(
                    f'Regiment {regiment.id} has {regiment.movement_remaining()} movement remaining this turn '
                    f'and cannot move {distance} tiles.'
                )
            return action

        if action_type == 'attack_regiment':
            attacker = self.map.get_regiment(action['actor_id'])
            defender = self.map.get_regiment(action['target_id'])
            if attacker is None:
                raise ValueError(f'Regiment {action["actor_id"]} does not exist.')
            if attacker.owner_id != player_id:
                raise ValueError(f'Regiment {attacker.id} belongs to another empire.')
            if defender is None:
                raise ValueError(f'Regiment {action["target_id"]} does not exist.')
            if defender.owner_id == player_id:
                raise ValueError('Friendly fire is not allowed.')
            if not self.map.is_regiment_visible_to_player(defender.id, player_id):
                raise ValueError(f'Regiment {defender.id} is not currently visible to your empire.')
            if not attacker.can_attack_this_turn():
                raise ValueError(
                    f'Regiment {attacker.id} cannot attack again this turn '
                    f'(movement remaining={attacker.movement_remaining()}, '
                    f'attacks remaining={max(0, attacker.max_attacks_per_turn() - attacker.attacks_made_this_turn)}).'
                )
            if attacker.is_defending:
                raise ValueError(f'Regiment {attacker.id} is defending and cannot attack this turn.')
            attack_distance = self.map.get_tile_distance(
                self.map.get_regiment_location(attacker.id),
                self.map.get_regiment_location(defender.id),
            )
            if not attacker.can_attack_distance(attack_distance):
                raise ValueError(
                    f'Regiment {attacker.id} may attack up to {attacker.attack_range()} tile(s), '
                    f'but Regiment {defender.id} is {attack_distance} tile(s) away.'
                )
            metadata['target_owner_id'] = defender.owner_id
            return action

        if action_type == 'attack_city':
            attacker = self.map.get_regiment(action['actor_id'])
            city = self.map.get_city(action['target_id'])
            if attacker is None:
                raise ValueError(f'Regiment {action["actor_id"]} does not exist.')
            if attacker.owner_id != player_id:
                raise ValueError(f'Regiment {attacker.id} belongs to another empire.')
            if city is None:
                raise ValueError(f'City {action["target_id"]} does not exist.')
            if city.owner_id == player_id:
                raise ValueError('Friendly fire is not allowed.')
            if not self.map.is_city_visible_to_player(city.id, player_id):
                raise ValueError(f'City {city.id} is not currently visible to your empire.')
            if not attacker.can_attack_this_turn():
                raise ValueError(
                    f'Regiment {attacker.id} cannot attack again this turn '
                    f'(movement remaining={attacker.movement_remaining()}, '
                    f'attacks remaining={max(0, attacker.max_attacks_per_turn() - attacker.attacks_made_this_turn)}).'
                )
            if attacker.is_defending:
                raise ValueError(f'Regiment {attacker.id} is defending and cannot attack this turn.')
            attack_distance = self.map.get_tile_distance(
                self.map.get_regiment_location(attacker.id),
                self.map.get_city_location(city.id),
            )
            if not attacker.can_attack_distance(attack_distance):
                raise ValueError(
                    f'Regiment {attacker.id} may attack up to {attacker.attack_range()} tile(s), '
                    f'but City {city.id} is {attack_distance} tile(s) away.'
                )
            metadata['target_owner_id'] = city.owner_id
            return action

        if action_type == 'defend_regiment':
            regiment = self.map.get_regiment(action['actor_id'])
            if regiment is None:
                raise ValueError(f'Regiment {action["actor_id"]} does not exist.')
            if regiment.owner_id != player_id:
                raise ValueError(f'Regiment {regiment.id} belongs to another empire.')
            if regiment.total_units() == 0:
                raise ValueError(f'Regiment {regiment.id} has no units remaining.')
            if self.map.get_regiment_location(regiment.id) is None:
                raise ValueError(f'Regiment {regiment.id} is not on the map.')
            if regiment.movement_remaining() < 1:
                raise ValueError(f'Regiment {regiment.id} has no movement remaining to defend.')
            if regiment.is_defending:
                raise ValueError(f'Regiment {regiment.id} is already defending this turn.')
            return action

        if action_type == 'buy_card':
            player = self.map.get_player(player_id)
            if player is None:
                raise ValueError(f'Player {player_id} does not exist.')
            if player.deck is None:
                raise ValueError(f'Player {player_id} does not have a deck.')
            if not player.can_draw_card():
                raise ValueError(f'{player.name} cannot buy a card because the hand is full.')
            rarity = str(metadata.get('rarity', 'common')).strip().lower()
            if rarity not in self.get_available_card_purchase_rarities(player_id):
                raise ValueError(f'{rarity.title()} cards are not yet available to your empire.')
            metadata['rarity'] = rarity
            return action

        if action_type == 'recruit_hero':
            regiment = self.map.get_regiment(action['target_id'])
            if regiment is None:
                raise ValueError(f'Regiment {action["target_id"]} does not exist.')
            if regiment.owner_id != player_id:
                raise ValueError(f'Regiment {regiment.id} belongs to another empire.')
            host_city = self._resolve_regiment_supporting_city(regiment)
            if host_city is None:
                raise ValueError('Heroes may only be recruited into forces stationed in a friendly city or port.')
            if not host_city.can_train_heroes():
                raise ValueError(f'{host_city.name} does not yet have the training capacity to recruit heroes.')
            return action

        if action_type == 'refit_force':
            regiment = self.map.get_regiment(action['target_id'])
            if regiment is None:
                raise ValueError(f'Regiment {action["target_id"]} does not exist.')
            if regiment.owner_id != player_id:
                raise ValueError(f'Regiment {regiment.id} belongs to another empire.')
            if self._resolve_regiment_supporting_city(regiment) is None:
                raise ValueError('Forces may only be refit inside a friendly city or port.')
            upgrade_kind = str(metadata.get('upgrade_kind', '')).strip().lower()
            if upgrade_kind not in {'ranged', 'siege'}:
                raise ValueError('Refit plans require "ranged" or "siege".')
            metadata['upgrade_kind'] = upgrade_kind
            return action

        if action_type == 'play_card':
            if self.turn <= self.card_unlock_turn:
                raise ValueError(f'Cards cannot be played until after turn {self.card_unlock_turn}.')
            player = self.map.get_player(player_id)
            if player is None:
                raise ValueError(f'Player {player_id} does not exist.')
            if player.deck is None:
                raise ValueError(f'Player {player_id} does not have a deck.')
            if not player.can_play_cards():
                raise ValueError(f'{player.name} is currently prevented from playing cards.')
            card_instance_id = metadata.get('card_instance_id')
            card = self._get_card_from_player_hand_by_instance_id(player, card_instance_id)
            if card is None:
                raise ValueError(f'Card {card_instance_id} is no longer in hand.')
            if card_instance_id in self.get_player_planned_card_instance_ids(player_id):
                raise ValueError(f'"{card.definition.name}" is already planned to be played this turn.')
            resolved_target = self._resolve_card_target(player, card.definition, metadata.get('target_payload', {}))
            metadata['card_name'] = card.definition.name
            if resolved_target['target_kind'] == 'player':
                metadata['target_owner_id'] = resolved_target['target_id']
            elif resolved_target['target_kind'] == 'regiment' and resolved_target.get('entity') is not None:
                metadata['target_owner_id'] = resolved_target['entity'].owner_id
            elif resolved_target['target_kind'] == 'city' and resolved_target.get('entity') is not None:
                metadata['target_owner_id'] = resolved_target['entity'].owner_id
            return action

        raise ValueError(f'Unsupported action type: {action_type}')

    def queue_action_for_player(self, player_id: int, action: dict):
        if self.map is None:
            raise ValueError('A map must be loaded before planning actions.')
        player = self.map.get_player(player_id)
        if player is None:
            raise ValueError(f'Player {player_id} does not exist.')
        current_player = self.get_current_turn_player()
        if current_player is None or current_player.id != player_id:
            raise ValueError(f'It is not {player.name}\'s planning phase.')

        normalized_action = dict(action)
        normalized_action['player_id'] = player_id
        normalized_action['metadata'] = dict(action.get('metadata', {}))

        action_limit = self.get_player_action_limit(player_id)
        planned_count = self.get_player_planned_action_count(player_id)
        if planned_count >= action_limit:
            raise ValueError(f'{player.name} has already planned the maximum {action_limit} action(s) this turn.')

        if normalized_action['action_type'] == 'play_card':
            card_limit = min(action_limit, self.get_player_card_limit(player_id))
            if self.get_player_planned_card_count(player_id) >= card_limit:
                raise ValueError(f'{player.name} has already planned the maximum {card_limit} card play(s) this turn.')

        normalized_action['metadata']['target_owner_id'] = self._resolve_action_target_owner_id(normalized_action)
        normalized_action = self._validate_planned_action(player_id, normalized_action)
        self._ensure_round_plan_entry(player_id).append(normalized_action)
        return {
            'queued': True,
            'action': normalized_action,
            'action_count': self.get_player_planned_action_count(player_id),
            'action_limit': action_limit,
            'card_count': self.get_player_planned_card_count(player_id),
            'card_limit': min(action_limit, self.get_player_card_limit(player_id)),
        }

    def get_player_regiments(self, player_id: int):
        if self.map is None:
            return []
        return [
            regiment for regiment in self.map.regiments.values()
            if regiment.owner_id == player_id
        ]

    def get_player_cities(self, player_id: int):
        if self.map is None:
            return []
        return [
            city for city in self.map.cities.values()
            if city.owner_id == player_id
        ]

    def get_production_orders_for_city(self, city_id: int):
        return [
            order for order in self.regiment_build_queue
            if order['city_id'] == city_id
        ]

    def get_city_planned_production_count(self, player_id: int, city_id: int):
        return sum(
            1 for action in self._ensure_round_plan_entry(player_id)
            if action['action_type'] in {'queue_regiment', 'queue_navy', 'queue_improvement'}
            and action['target_id'] == city_id
        )

    def get_city_total_reserved_queue_slots(self, player_id: int, city_id: int):
        return len(self.get_production_orders_for_city(city_id)) + self.get_city_planned_production_count(player_id, city_id)

    def get_city_queue_space_remaining(self, player_id: int, city_id: int):
        city = self.map.get_city(city_id) if self.map is not None else None
        if city is None:
            return 0
        return max(0, city.queue_capacity() - self.get_city_total_reserved_queue_slots(player_id, city_id))

    def get_visible_enemy_regiments(self, player_id: int):
        if self.map is None:
            return []
        return [
            regiment for regiment in self.map.regiments.values()
            if regiment.owner_id != player_id and self.map.is_regiment_visible_to_player(regiment.id, player_id)
        ]

    def get_visible_enemy_cities(self, player_id: int):
        if self.map is None:
            return []
        return [
            city for city in self.map.cities.values()
            if city.owner_id != player_id and self.map.is_city_visible_to_player(city.id, player_id)
        ]

    def has_regiment_order_for_city(self, city_id: int):
        return any(
            order['city_id'] == city_id and order.get('order_kind', 'force') == 'force'
            for order in self.regiment_build_queue
        )

    def has_regiment_order_for_city_this_turn(self, city_id: int):
        return any(
            order['city_id'] == city_id and order.get('queued_on_turn') == self.turn
            for order in self.regiment_build_queue
        )

    def get_player_owned_sea_tiles(self, player_id: int):
        if self.map is None:
            return []
        return [
            position for position, tile in sorted(self.map.tiles.items())
            if tile.passable_water and tile.influence_owner_id == player_id and not tile.is_influence_contested
        ]

    def get_player_owned_tile_count(self, player_id: int, tile_types: set[str] = None):
        if self.map is None:
            return 0
        return sum(
            1 for tile in self.map.tiles.values()
            if tile.influence_owner_id == player_id and not tile.is_influence_contested
            and (tile_types is None or tile.type in tile_types)
        )

    def get_player_accessible_resources(self, player_id: int):
        if self.map is None:
            return []
        visible_resource_ids = set()
        for city in self.get_player_cities(player_id):
            for resource in self.map.get_city_visible_resources(city.id):
                visible_resource_ids.add(resource.id)
        return [
            self.map.get_resource(resource_id)
            for resource_id in sorted(visible_resource_ids)
            if self.map.get_resource(resource_id) is not None
        ]

    def get_player_improvements(self, player_id: int):
        if self.map is None:
            return []
        return [
            improvement for improvement in self.map.improvements.values()
            if improvement.owner_id == player_id
        ]

    def get_city_resource_bonus_summary(self, city: City):
        bonuses = {
            'resource_pull_bonus': city.resource_pull_bonus,
            'regiment_power_bonus': city.regiment_power_bonus,
            'defense_bonus': 0.0,
            'food_growth_bonus': city.food_growth_bonus,
            'card_purchase_tier_bonus': 0,
        }
        for resource in self.map.get_city_visible_resources(city.id):
            for bonus_name, value in resource.definition.city_bonuses.items():
                bonuses[bonus_name] = bonuses.get(bonus_name, 0) + value
        return bonuses

    def calculate_material_income(self, player_id: int):
        if self.map is None:
            return {'coin': 0, 'food': 0, 'wood': 0, 'stone': 0}
        influence_score = self.map.get_player_total_influence_score(player_id)
        influence_factor = max(1.0, influence_score / 10000)
        forest_tiles = self.get_player_owned_tile_count(player_id, {'forest'})
        food_tiles = self.get_player_owned_tile_count(player_id, {'grass', 'hill'})
        coin_income = max(12, int(influence_score / 1400))
        food_income = int(food_tiles * 0.55 * influence_factor)
        wood_income = int(forest_tiles * 0.65 * influence_factor)
        stone_income = 0

        accessible_resources = self.get_player_accessible_resources(player_id)
        for resource in accessible_resources:
            for material_type, amount in resource.definition.material_bonus.items():
                if material_type == 'coin':
                    coin_income += amount
                elif material_type == 'food':
                    food_income += amount
                elif material_type == 'wood':
                    wood_income += amount
                elif material_type == 'stone':
                    stone_income += amount

        for city in self.get_player_cities(player_id):
            bonus_summary = self.get_city_resource_bonus_summary(city)
            coin_income += int(round(coin_income * city.coin_income_bonus * 0.20))
            food_income += int(round(max(0, bonus_summary.get('resource_pull_bonus', 0.0)) * 3))
            food_income += int(round(food_tiles * city.food_income_bonus * 0.10))
            wood_income += int(round(forest_tiles * city.wood_income_bonus * 0.10))
            stone_income += int(round(max(0, city.stone_income_bonus) * 2))

        for improvement in self.get_player_improvements(player_id):
            bonuses = improvement.definition.bonuses
            coin_income += int(bonuses.get('coin_income_flat', 0))
            food_income += int(bonuses.get('food_income_flat', 0))
            wood_income += int(bonuses.get('wood_income_flat', 0))
            stone_income += int(bonuses.get('stone_income_flat', 0))

        quarry_count = len([
            improvement for improvement in self.get_player_improvements(player_id)
            if improvement.improvement_kind == 'quarry'
        ])
        stone_income += int(quarry_count * max(1.0, influence_factor * 1.1))

        return {
            'coin': max(0, int(coin_income)),
            'food': max(0, int(food_income)),
            'wood': max(0, int(wood_income)),
            'stone': max(0, int(stone_income)),
        }

    def process_material_income_for_new_round(self, viewer_player_id: int = None):
        if self.map is None:
            return []
        messages = []
        for player in sorted(self.map.players.values(), key=lambda entry: entry.id):
            income = self.calculate_material_income(player.id)
            player.add_materials(income)
            if viewer_player_id in {None, player.id}:
                messages.append(
                    f'{player.name} gathered Coin={income["coin"]}, Food={income["food"]}, '
                    f'Wood={income["wood"]}, Stone={income["stone"]}.'
                )
        return messages

    def process_city_growth_and_sovereignty(self, viewer_player_id: int = None):
        if self.map is None:
            return []
        messages = []
        for player in sorted(self.map.players.values(), key=lambda entry: entry.id):
            for city in sorted(self.get_player_cities(player.id), key=lambda entry: (-entry.level, -entry.population, entry.id)):
                city_location = self.map.get_city_location(city.id)
                under_enemy_pressure = bool(self.map.get_enemy_regiments_in_range_of_city(city.id))
                city.grant_sovereignty_experience(under_enemy_pressure=under_enemy_pressure)
                if city_location is None:
                    continue
                growth_food_cost = max(18, 12 + (city.level * 5) + (city.population // 350))
                player_food = player.get_material('food')
                if player_food < growth_food_cost:
                    continue
                bonus_summary = self.get_city_resource_bonus_summary(city)
                growth_bonus = 1.0 + city.food_growth_bonus + bonus_summary.get('food_growth_bonus', 0.0)
                growth_amount = max(
                    10,
                    int(round((12 + (city.level * 3) + (bonus_summary.get('resource_pull_bonus', 0.0) * 12)) * growth_bonus)),
                )
                player.spend_materials({'food': growth_food_cost})
                growth_result = city.apply_population_growth(growth_amount)
                if viewer_player_id in {None, player.id}:
                    messages.append(
                        f'{city.name} grew by {growth_result["growth"]} population for {growth_food_cost} Food '
                        f'(population={growth_result["population_after"]}, level={city.level}).'
                    )
        return messages

    def get_force_order_cost(self, city: City, force_kind: str):
        normalized_force_kind = str(force_kind).strip().lower()
        if normalized_force_kind == 'navy':
            return {'coin': 55 + (city.level * 10)}
        return {'coin': 35 + (city.level * 8)}

    def get_card_purchase_cost(self, rarity: str):
        return {
            'common': {'coin': 35},
            'uncommon': {'coin': 60},
            'rare': {'coin': 95},
            'legendary': {'coin': 150},
        }[str(rarity).strip().lower()]

    def get_card_purchase_tier(self, player_id: int):
        tier = 0
        accessible_resources = self.get_player_accessible_resources(player_id)
        for resource in accessible_resources:
            tier += int(resource.definition.city_bonuses.get('card_purchase_tier_bonus', 0))
        if any(city.level >= 4 for city in self.get_player_cities(player_id)):
            tier += 1
        if any(improvement.improvement_kind in {'market', 'castle'} for improvement in self.get_player_improvements(player_id)):
            tier += 1
        return tier

    def get_available_card_purchase_rarities(self, player_id: int):
        tier = self.get_card_purchase_tier(player_id)
        allowable = ['common']
        if tier >= 1:
            allowable.append('uncommon')
        if tier >= 2:
            allowable.append('rare')
        if tier >= 4:
            allowable.append('legendary')
        return allowable

    def _deduplicate_messages(self, messages: list[str]):
        unique_messages = []
        seen_messages = set()
        for message in messages:
            if message in seen_messages:
                continue
            seen_messages.add(message)
            unique_messages.append(message)
        return unique_messages

    def _determine_regiment_build_turns(self, city: City):
        base_turns = max(1, min(6, math.ceil(3000 / max(city.population, 1))))
        return max(1, int(math.ceil(base_turns * city.production_turn_multiplier())))

    def _determine_navy_build_turns(self, city: City):
        return max(2, min(8, self._determine_regiment_build_turns(city) + 1))

    def _create_random_regiment_for_city(self, city: City, owner_id: int, regiment_name: str):
        resource_bonus = self.get_city_resource_bonus_summary(city)
        size_multiplier = 1.0 + city.regiment_power_bonus + resource_bonus.get('regiment_power_bonus', 0.0)
        total_units = int(round(
            max(8, city.population // 45 + self.random.randint(0, max(3, city.population // 200))) *
            size_multiplier
        ))
        infantry = self.random.randint(total_units // 4, total_units // 2)
        remaining = total_units - infantry
        ranged = self.random.randint(0, remaining)
        remaining -= ranged
        cavalry = self.random.randint(0, remaining)
        siege = remaining - cavalry
        hero_chance = 0.0 if not city.can_train_heroes() else min(0.75, 0.08 + (0.07 * city.level) + (0.10 * city.hero_access_bonus))
        heroes = [f'Hero_{self.random.randint(1, 999)}'] if self.random.random() < hero_chance else []
        initial_level = min(Regiment.MAX_LEVEL, max(1, 1 + ((city.level - 1) // 3)))
        return Regiment(
            name=regiment_name,
            owner_id=owner_id,
            infantry=infantry,
            ranged=ranged,
            cavalry=cavalry,
            siege=siege,
            heroes=heroes,
            level=initial_level,
        )

    def _create_random_navy_for_city(self, city: City, owner_id: int, regiment_name: str):
        resource_bonus = self.get_city_resource_bonus_summary(city)
        size_multiplier = 1.0 + (city.regiment_power_bonus * 0.8) + (resource_bonus.get('regiment_power_bonus', 0.0) * 0.5)
        total_units = int(round(
            max(4, city.population // 120 + self.random.randint(0, max(2, city.population // 450))) *
            size_multiplier
        ))
        hero_chance = 0.0 if not city.can_train_heroes() else min(0.60, 0.05 + (0.05 * city.level) + (0.08 * city.hero_access_bonus))
        heroes = [f'Admiral_{self.random.randint(1, 999)}'] if self.random.random() < hero_chance else []
        initial_level = min(Regiment.MAX_LEVEL, max(1, 1 + ((city.level - 1) // 3)))
        return Regiment(
            name=regiment_name,
            owner_id=owner_id,
            navy=total_units,
            heroes=heroes,
            level=initial_level,
        )

    def get_improvement_definition(self, improvement_kind: str):
        Improvement.initialize_definitions()
        normalized_kind = str(improvement_kind).strip().lower()
        definition = Improvement.DEFINITIONS.get(normalized_kind)
        if definition is None:
            raise ValueError(f'Unsupported improvement kind: {improvement_kind}')
        return definition

    def _get_city_improvement_count(self, city_id: int, improvement_kind: str):
        normalized_kind = str(improvement_kind).strip().lower()
        return len([
            improvement for improvement in self.map.get_city_improvements(city_id)
            if improvement.improvement_kind == normalized_kind
        ])

    def find_valid_improvement_sites_for_city(self, city_id: int, improvement_kind: str):
        if self.map is None:
            return []
        city = self.map.get_city(city_id)
        city_location = self.map.get_city_location(city_id)
        definition = self.get_improvement_definition(improvement_kind)
        if city is None or city_location is None:
            return []
        if definition.intra_city:
            if definition.max_per_city is not None and self._get_city_improvement_count(city.id, definition.improvement_kind) >= definition.max_per_city:
                return []
            return [city_location]
        valid_positions = []
        for position in sorted(self.map.get_tiles_in_radius(city_location, city.effective_line_of_sight_radius())):
            tile = self.map.tiles.get(position)
            if tile is None:
                continue
            if not self.map.is_tile_securely_owned_by_player(position[0], position[1], city.owner_id):
                continue
            if tile.improvement_id is not None:
                continue
            if definition.required_tile_types and tile.type not in definition.required_tile_types:
                continue
            if definition.requires_adjacent_water and not self.map.is_adjacent_to_water(position[0], position[1]):
                continue
            if definition.max_per_city is not None and self._get_city_improvement_count(city.id, definition.improvement_kind) >= definition.max_per_city:
                continue
            valid_positions.append(position)
        return valid_positions

    def _validate_improvement_order(self, player_id: int, city_id: int,
                                    improvement_kind: str, target_pos: tuple[int, int] = None):
        if self.map is None:
            raise ValueError('A map must be loaded before queueing improvements.')
        city = self.map.get_city(city_id)
        if city is None:
            raise ValueError(f'City {city_id} does not exist.')
        if city.owner_id != player_id:
            raise ValueError(f'City {city_id} belongs to another empire.')
        definition = self.get_improvement_definition(improvement_kind)
        if city.level < definition.min_city_level:
            raise ValueError(f'{city.name} must be at least level {definition.min_city_level} to build {definition.name}.')
        valid_positions = self.find_valid_improvement_sites_for_city(city.id, definition.improvement_kind)
        if definition.intra_city:
            if not valid_positions:
                raise ValueError(f'{city.name} already has the maximum number of {definition.name} improvements.')
            return city, definition, None
        if target_pos is None:
            raise ValueError(f'{definition.name} requires a target tile.')
        normalized_target = (int(target_pos[0]), int(target_pos[1]))
        if normalized_target not in valid_positions:
            raise ValueError(f'Tile {normalized_target} is not a valid site for {definition.name}.')
        return city, definition, normalized_target

    def _validate_navy_spawn_tile(self, player_id: int, city_id: int, spawn_x: int, spawn_y: int):
        if self.map is None:
            raise ValueError('A map must be loaded before queueing navies.')
        city = self.map.get_city(city_id)
        if city is None:
            raise ValueError(f'City {city_id} does not exist.')
        if (spawn_x, spawn_y) not in self.map.tiles:
            raise ValueError(f'Port tile ({spawn_x}, {spawn_y}) is out of bounds.')
        spawn_tile = self.map.tiles[(spawn_x, spawn_y)]
        improvement = self.map.get_improvement(spawn_tile.improvement_id) if spawn_tile.improvement_id is not None else None
        if improvement is None or not improvement.is_port():
            raise ValueError(f'Tile ({spawn_x}, {spawn_y}) is not a port.')
        if improvement.city_id != city_id:
            raise ValueError(f'Port tile ({spawn_x}, {spawn_y}) does not belong to {city.name}.')
        if spawn_tile.regiment_id is not None:
            raise ValueError(f'Port tile ({spawn_x}, {spawn_y}) already has a force on it.')
        if spawn_tile.influence_owner_id != player_id or spawn_tile.is_influence_contested:
            raise ValueError(f'Port tile ({spawn_x}, {spawn_y}) is not securely owned by your empire.')
        return spawn_tile

    def _queue_force_order(self, player_id: int, city_id: int, regiment_name: str = None,
                           force_kind: str = 'regiment', spawn_pos: tuple[int, int] = None):
        if self.map is None:
            raise ValueError('A map must be loaded before queueing regiments.')
        city = self.map.get_city(city_id)
        if city is None:
            raise ValueError(f'City {city_id} does not exist.')
        if city.owner_id != player_id:
            raise ValueError(f'City {city_id} belongs to another empire.')
        if not city.can_queue_regiment():
            raise ValueError(
                f'{city.name} cannot produce regiments for {city.regiment_production_lock_turns_remaining} more turn(s) '
                f'while the occupation is being stabilized.'
            )
        if len(self.get_production_orders_for_city(city.id)) >= city.queue_capacity():
            raise ValueError(f'{city.name} has no open production queue slots.')

        normalized_force_kind = str(force_kind).strip().lower()
        if normalized_force_kind not in {'regiment', 'navy'}:
            raise ValueError(f'Unsupported force kind: {force_kind}')

        selected_name = str(regiment_name).strip() if regiment_name is not None else ''
        if not selected_name:
            selected_name = f'{city.name} {"Fleet" if normalized_force_kind == "navy" else "Guard"}'

        spawn_position = None
        if normalized_force_kind == 'navy':
            if spawn_pos is None:
                raise ValueError('A port tile spawn position is required when queueing a navy.')
            spawn_position = (int(spawn_pos[0]), int(spawn_pos[1]))
            self._validate_navy_spawn_tile(player_id, city.id, spawn_position[0], spawn_position[1])

        player = self.map.get_player(player_id)
        if player is None:
            raise ValueError(f'Player {player_id} does not exist.')
        costs = self.get_force_order_cost(city, normalized_force_kind)
        player.spend_materials(costs)

        turns_to_build = (
            self._determine_navy_build_turns(city)
            if normalized_force_kind == 'navy' else
            self._determine_regiment_build_turns(city)
        )
        self.regiment_build_queue.append({
            'order_kind': 'force',
            'city_id': city.id,
            'owner_id': city.owner_id,
            'regiment_name': selected_name,
            'force_kind': normalized_force_kind,
            'spawn_pos': spawn_position,
            'turns_remaining': turns_to_build,
            'queued_on_turn': self.turn,
            'costs': dict(costs),
        })
        return {
            'queued': True,
            'city_id': city.id,
            'owner_id': city.owner_id,
            'regiment_name': selected_name,
            'force_kind': normalized_force_kind,
            'spawn_pos': spawn_position,
            'turns_to_build': turns_to_build,
            'costs': dict(costs),
        }

    def queue_regiment_order(self, player_id: int, city_id: int, regiment_name: str = None):
        return self._queue_force_order(player_id, city_id, regiment_name=regiment_name, force_kind='regiment')

    def queue_navy_order(self, player_id: int, city_id: int, spawn_x: int, spawn_y: int, regiment_name: str = None):
        return self._queue_force_order(
            player_id,
            city_id,
            regiment_name=regiment_name,
            force_kind='navy',
            spawn_pos=(spawn_x, spawn_y),
        )

    def queue_improvement_order(self, player_id: int, city_id: int, improvement_kind: str,
                                target_pos: tuple[int, int] = None):
        city, definition, normalized_target = self._validate_improvement_order(
            player_id,
            city_id,
            improvement_kind,
            target_pos=target_pos,
        )
        if len(self.get_production_orders_for_city(city.id)) >= city.queue_capacity():
            raise ValueError(f'{city.name} has no open production queue slots.')
        player = self.map.get_player(player_id)
        if player is None:
            raise ValueError(f'Player {player_id} does not exist.')
        player.spend_materials(definition.costs)
        turns_to_build = max(1, int(math.ceil(definition.build_turns * city.production_turn_multiplier())))
        self.regiment_build_queue.append({
            'order_kind': 'improvement',
            'city_id': city.id,
            'owner_id': city.owner_id,
            'improvement_kind': definition.improvement_kind,
            'improvement_name': definition.name,
            'target_pos': normalized_target,
            'turns_remaining': turns_to_build,
            'queued_on_turn': self.turn,
            'costs': dict(definition.costs),
        })
        return {
            'queued': True,
            'city_id': city.id,
            'owner_id': city.owner_id,
            'improvement_kind': definition.improvement_kind,
            'improvement_name': definition.name,
            'target_pos': normalized_target,
            'turns_to_build': turns_to_build,
            'costs': dict(definition.costs),
        }

    def cancel_regiment_order(self, player_id: int, city_id: int):
        if self.map is None:
            raise ValueError('A map must be loaded before canceling regiment orders.')
        city = self.map.get_city(city_id)
        if city is None:
            raise ValueError(f'City {city_id} does not exist.')
        if city.owner_id != player_id:
            raise ValueError(f'City {city_id} belongs to another empire.')

        for order in reversed(self.regiment_build_queue):
            if order['city_id'] != city_id:
                continue
            self.regiment_build_queue.remove(order)
            player = self.map.get_player(player_id)
            if player is not None:
                player.add_materials(order.get('costs', {}))
            return {
                'canceled': True,
                'city_id': city_id,
                'regiment_name': order.get('regiment_name'),
                'improvement_name': order.get('improvement_name'),
                'force_kind': order.get('force_kind', 'regiment'),
                'order_kind': order.get('order_kind', 'force'),
                'turns_remaining': order['turns_remaining'],
                'refunded_costs': dict(order.get('costs', {})),
            }
        raise ValueError(f'{city.name} has no production currently in progress.')

    def purchase_card_for_player(self, player_id: int, rarity: str):
        if self.map is None:
            raise ValueError('A map must be loaded before purchasing cards.')
        player = self.map.get_player(player_id)
        if player is None:
            raise ValueError(f'Player {player_id} does not exist.')
        if player.deck is None:
            raise ValueError(f'Player {player_id} does not have a deck.')
        normalized_rarity = str(rarity).strip().lower()
        if normalized_rarity not in self.get_available_card_purchase_rarities(player_id):
            raise ValueError(f'{normalized_rarity.title()} cards are not yet available to your empire.')
        if not player.can_draw_card():
            raise ValueError(f'{player.name} cannot buy a card because the hand is full.')
        costs = self.get_card_purchase_cost(normalized_rarity)
        player.spend_materials(costs)
        purchased_card = self.card_library.build_random_card_of_rarity(normalized_rarity, rng=self.random)
        player.hand.append(purchased_card)
        return {'purchased': True, 'card': purchased_card, 'rarity': normalized_rarity, 'costs': costs}

    def _resolve_regiment_supporting_city(self, regiment: Regiment):
        location = self.map.get_regiment_location(regiment.id) if self.map is not None else None
        if location is None:
            return None
        tile = self.map.tiles.get(location)
        if tile is None:
            return None
        if tile.city_id is not None:
            city = self.map.get_city(tile.city_id)
            if city is not None and city.owner_id == regiment.owner_id:
                return city
        if tile.improvement_id is not None:
            improvement = self.map.get_improvement(tile.improvement_id)
            if improvement is not None and improvement.owner_id == regiment.owner_id:
                return self.map.get_city(improvement.city_id)
        return None

    def recruit_hero_for_player(self, player_id: int, regiment_id: int, hero_name: str = None):
        if self.map is None:
            raise ValueError('A map must be loaded before recruiting heroes.')
        regiment = self.map.get_regiment(regiment_id)
        if regiment is None:
            raise ValueError(f'Regiment {regiment_id} does not exist.')
        if regiment.owner_id != player_id:
            raise ValueError(f'Regiment {regiment_id} belongs to another empire.')
        host_city = self._resolve_regiment_supporting_city(regiment)
        if host_city is None:
            raise ValueError('Heroes may only be recruited into forces stationed in a friendly city or port.')
        if not host_city.can_train_heroes():
            raise ValueError(f'{host_city.name} does not yet have the training capacity to recruit heroes.')
        player = self.map.get_player(player_id)
        hero_cost = {'coin': 70 + (15 * regiment.hero_count())}
        player.spend_materials(hero_cost)
        resolved_name = str(hero_name).strip() if hero_name is not None else ''
        regiment.add_hero(resolved_name or f'Hero_{self.random.randint(1000, 9999)}')
        regiment.add_experience(18 + (host_city.level * 2))
        return {
            'recruited': True,
            'regiment_id': regiment.id,
            'hero_name': regiment.heroes[-1],
            'city_id': host_city.id,
            'costs': hero_cost,
        }

    def refit_force_for_player(self, player_id: int, regiment_id: int, upgrade_kind: str):
        if self.map is None:
            raise ValueError('A map must be loaded before refitting forces.')
        regiment = self.map.get_regiment(regiment_id)
        if regiment is None:
            raise ValueError(f'Regiment {regiment_id} does not exist.')
        if regiment.owner_id != player_id:
            raise ValueError(f'Regiment {regiment_id} belongs to another empire.')
        host_city = self._resolve_regiment_supporting_city(regiment)
        if host_city is None:
            raise ValueError('Forces may only be refit inside a friendly city or port.')
        normalized_upgrade = str(upgrade_kind).strip().lower()
        if normalized_upgrade not in {'ranged', 'siege'}:
            raise ValueError('Upgrade type must be "ranged" or "siege".')
        player = self.map.get_player(player_id)
        if regiment.is_navy():
            costs = {'wood': 16 if normalized_upgrade == 'ranged' else 20}
            player.spend_materials(costs)
            if normalized_upgrade == 'ranged':
                regiment.attack_score_bonus += 10
                regiment.defense_score_bonus += 5
            else:
                regiment.attack_score_bonus += 6
                regiment.city_attack_score_bonus += 18
            regiment.add_experience(10)
            return {
                'refit': True,
                'regiment_id': regiment.id,
                'upgrade_kind': normalized_upgrade,
                'costs': costs,
            }
        costs = {'wood': 12 if normalized_upgrade == 'ranged' else 14}
        player.spend_materials(costs)
        if normalized_upgrade == 'ranged':
            regiment.update_composition(ranged=regiment.ranged + 3)
        else:
            regiment.update_composition(siege=regiment.siege + 2)
        regiment.add_experience(8)
        return {
            'refit': True,
            'regiment_id': regiment.id,
            'upgrade_kind': normalized_upgrade,
            'costs': costs,
        }

    def move_regiment_for_player(self, player_id: int, regiment_id: int, target_x: int, target_y: int):
        if self.map is None:
            raise ValueError('A map must be loaded before moving regiments.')
        regiment = self.map.get_regiment(regiment_id)
        if regiment is None:
            raise ValueError(f'Regiment {regiment_id} does not exist.')
        if regiment.owner_id != player_id:
            raise ValueError(f'Regiment {regiment_id} belongs to another empire.')
        self.map.move_regiment(regiment_id, target_x, target_y)
        return {
            'moved': True,
            'regiment_id': regiment_id,
            'target_pos': (target_x, target_y),
            'movement_remaining': regiment.movement_remaining(),
        }

    def move_regiment_for_player_by_delta(self, player_id: int, regiment_id: int, delta_x: int, delta_y: int):
        if self.map is None:
            raise ValueError('A map must be loaded before moving regiments.')
        regiment = self.map.get_regiment(regiment_id)
        if regiment is None:
            raise ValueError(f'Regiment {regiment_id} does not exist.')
        if regiment.owner_id != player_id:
            raise ValueError(f'Regiment {regiment_id} belongs to another empire.')
        start = self.map.get_regiment_location(regiment_id)
        if start is None:
            raise ValueError(f'Regiment {regiment_id} is not on the map.')
        target_x = start[0] + delta_x
        target_y = start[1] + delta_y
        result = self.move_regiment_for_player(player_id, regiment_id, target_x, target_y)
        result['delta'] = (delta_x, delta_y)
        return result

    def attack_with_regiment(self, player_id: int, regiment_id: int, target_kind: str, target_id: int):
        if self.map is None:
            raise ValueError('A map must be loaded before attacking.')
        regiment = self.map.get_regiment(regiment_id)
        if regiment is None:
            raise ValueError(f'Regiment {regiment_id} does not exist.')
        if regiment.owner_id != player_id:
            raise ValueError(f'Regiment {regiment_id} belongs to another empire.')

        normalized_target_kind = str(target_kind).strip().lower()
        if normalized_target_kind == 'regiment':
            defender = self.map.get_regiment(target_id)
            if defender is None:
                raise ValueError(f'Regiment {target_id} does not exist.')
            if defender.owner_id == player_id:
                raise ValueError('Friendly fire is not allowed.')
            if not self.map.is_regiment_visible_to_player(defender.id, player_id):
                raise ValueError(f'Regiment {defender.id} is not currently visible to your empire.')
            return {
                'action_type': 'attack_regiment',
                'result': self.map.attack_regiment(regiment_id, defender.id),
                'target': defender,
            }

        if normalized_target_kind == 'city':
            target_city = self.map.get_city(target_id)
            if target_city is None:
                raise ValueError(f'City {target_id} does not exist.')
            if target_city.owner_id == player_id:
                raise ValueError('Friendly fire is not allowed.')
            if not self.map.is_city_visible_to_player(target_city.id, player_id):
                raise ValueError(f'City {target_city.id} is not currently visible to your empire.')
            attack_result = self.map.attack_city(regiment_id, target_city.id)
            victory_result = self.evaluate_victory_conditions()
            self.handle_victory_result(victory_result)
            return {
                'action_type': 'attack_city',
                'result': attack_result,
                'target': target_city,
                'victory_result': victory_result,
            }

        raise ValueError(f'Unsupported target kind: {target_kind}')

    def defend_regiment_for_player(self, player_id: int, regiment_id: int):
        if self.map is None:
            raise ValueError('A map must be loaded before defending regiments.')
        regiment = self.map.get_regiment(regiment_id)
        if regiment is None:
            raise ValueError(f'Regiment {regiment_id} does not exist.')
        if regiment.owner_id != player_id:
            raise ValueError(f'Regiment {regiment_id} belongs to another empire.')
        return self.map.defend_regiment(regiment_id)

    def process_regiment_build_queue(self, viewer_player_id: int = None):
        if self.map is None or not self.regiment_build_queue:
            return []

        completed_orders = []
        messages = []
        for order in self.regiment_build_queue:
            order['turns_remaining'] -= 1
            if order['turns_remaining'] > 0:
                continue

            city = self.map.get_city(order['city_id'])
            city_location = self.map.get_city_location(order['city_id'])
            order_kind = order.get('order_kind', 'force')
            force_kind = order.get('force_kind', 'regiment')
            spawn_position = tuple(order['spawn_pos']) if order.get('spawn_pos') is not None else city_location
            is_visible_to_viewer = (
                viewer_player_id is None or order['owner_id'] == viewer_player_id
            )
            if city is None or city_location is None:
                if is_visible_to_viewer:
                    messages.append(f"Build order canceled: City {order['city_id']} no longer has a valid location.")
                completed_orders.append(order)
                continue
            if city.owner_id != order['owner_id']:
                if is_visible_to_viewer:
                    messages.append(
                        f"Build order canceled: City {order['city_id']} is no longer controlled by Player {order['owner_id']}."
                    )
                completed_orders.append(order)
                continue
            if not city.can_queue_regiment():
                order['turns_remaining'] = max(order['turns_remaining'], 1)
                continue
            if order_kind == 'improvement':
                try:
                    _, definition, normalized_target = self._validate_improvement_order(
                        order['owner_id'],
                        city.id,
                        order['improvement_kind'],
                        order.get('target_pos'),
                    )
                    improvement = Improvement(
                        improvement_kind=definition.improvement_kind,
                        city_id=city.id,
                        owner_id=order['owner_id'],
                        tile_pos=normalized_target,
                    )
                    self.map.add_improvement(improvement)
                    city.add_experience(definition.city_xp_reward)
                    if is_visible_to_viewer:
                        if normalized_target is None:
                            messages.append(f'{city.name} completed {definition.name}.')
                        else:
                            messages.append(f'{city.name} completed {definition.name} at {normalized_target}.')
                    completed_orders.append(order)
                except ValueError as error:
                    if is_visible_to_viewer:
                        messages.append(f'Build order delayed for city {city.id}: {error}')
                    order['turns_remaining'] = 1
                continue
            if force_kind == 'navy':
                if spawn_position not in self.map.tiles:
                    if is_visible_to_viewer:
                        messages.append(
                            f'Build order canceled for navy at city {city.id}: port tile {spawn_position} is out of bounds.'
                        )
                    completed_orders.append(order)
                    continue
                spawn_tile = self.map.tiles[spawn_position]
                improvement = self.map.get_improvement(spawn_tile.improvement_id) if spawn_tile.improvement_id is not None else None
                if improvement is None or not improvement.is_port():
                    if is_visible_to_viewer:
                        messages.append(
                            f'Build order canceled for navy at city {city.id}: tile {spawn_position} is no longer a valid port.'
                        )
                    completed_orders.append(order)
                    continue
                if spawn_tile.influence_owner_id != order['owner_id'] or spawn_tile.is_influence_contested:
                    if is_visible_to_viewer:
                        messages.append(
                            f'Build order canceled for navy at city {city.id}: port tile {spawn_position} is no longer securely owned.'
                        )
                    completed_orders.append(order)
                    continue
                if spawn_tile.regiment_id is not None:
                    if is_visible_to_viewer:
                        messages.append(
                            f'Build order delayed for city {city.id}: port tile {spawn_position} is currently occupied.'
                        )
                    order['turns_remaining'] = 1
                    continue

            try:
                regiment = (
                    self._create_random_navy_for_city(
                        city=city,
                        owner_id=order['owner_id'],
                        regiment_name=order['regiment_name'],
                    ) if force_kind == 'navy' else
                    self._create_random_regiment_for_city(
                        city=city,
                        owner_id=order['owner_id'],
                        regiment_name=order['regiment_name'],
                    )
                )
                self.map.add_regiment(regiment, spawn_position[0], spawn_position[1])
                if is_visible_to_viewer:
                    if force_kind == 'navy':
                        messages.append(
                            f'Navy formed: {regiment.symbol()} launched from {city.name} at port {spawn_position}.'
                        )
                    else:
                        messages.append(f'Regiment formed: {regiment.symbol()} at city {city.name}.')
                completed_orders.append(order)
            except ValueError as error:
                if is_visible_to_viewer:
                    messages.append(f'Build order delayed for city {city.id}: {error}')
                order['turns_remaining'] = 1

        self.regiment_build_queue = [order for order in self.regiment_build_queue if order not in completed_orders]
        return self._deduplicate_messages(messages)

    def print_regiment_build_queue_status(self, viewer_player_id: int = None, show_empty_message: bool = True):
        visible_orders = self.regiment_build_queue
        if viewer_player_id is not None:
            visible_orders = [
                order for order in self.regiment_build_queue
                if order['owner_id'] == viewer_player_id
            ]

        if not visible_orders:
            if show_empty_message:
                print('No forces or improvements are currently queued for production for your empire.')
            return

        print('PRODUCTION QUEUE:')
        for order in visible_orders:
            city = self.map.get_city(order['city_id']) if self.map is not None else None
            city_name = city.name if city is not None else f'City {order["city_id"]}'
            turns_remaining = max(0, order['turns_remaining'])
            order_kind = order.get('order_kind', 'force')
            if order_kind == 'improvement':
                target_pos = tuple(order['target_pos']) if order.get('target_pos') is not None else None
                location_text = f' at tile {target_pos}' if target_pos is not None else ''
                print(
                    f"  {turns_remaining} turn(s) until {order['improvement_name']} finishes at {city_name}{location_text}."
                )
                continue
            force_kind = order.get('force_kind', 'regiment')
            if force_kind == 'navy':
                print(
                    f"  {turns_remaining} turn(s) until Navy '{order['regiment_name']}' appears at port "
                    f'{tuple(order["spawn_pos"])} from {city_name}.'
                )
                continue
            print(
                f"  {turns_remaining} turn(s) until Regiment '{order['regiment_name']}' "
                f'appears at {city_name}.'
            )
        print('')

    def process_city_auto_attacks(self, viewer_player_id: int = None):
        if self.map is None:
            return []

        messages = []
        for city in sorted(self.map.cities.values(), key=lambda city: city.id):
            enemy_regiments = self.map.get_enemy_regiments_in_sight_of_city(city.id)
            if not enemy_regiments:
                continue
            target_regiment = max(
                enemy_regiments,
                key=lambda regiment: (
                    regiment.effective_regiment_attack_score(),
                    regiment.total_units(),
                    -self.map.get_tile_distance(self.map.get_city_location(city.id), self.map.get_regiment_location(regiment.id)),
                    -regiment.id,
                ),
            )
            try:
                result = self.map.resolve_city_attack(city.id, target_regiment.id)
            except ValueError:
                continue

            if viewer_player_id not in {None, city.owner_id, target_regiment.owner_id}:
                continue
            target_owner = self.map.get_player(target_regiment.owner_id)
            target_owner_name = target_owner.name if target_owner is not None else f'Player {target_regiment.owner_id}'
            casualty_total = sum(result['casualties'].values())
            messages.append(
                f'{city.symbol} auto-attacked {target_regiment.symbol()} from {result["attack_distance"]} tile(s): '
                f'{casualty_total} losses to {target_owner_name}, {result["remaining_units"]} unit(s) remain.'
            )
            if result['destroyed']:
                messages.append(f'{target_regiment.name} was destroyed by {city.name}.')
        return self._deduplicate_messages(messages)

    def print_owned_regiments_metadata(self, player_id: int):
        if self.map is None:
            raise ValueError('A map must be loaded before printing regiments.')
        player = self.map.get_player(player_id)
        if player is None:
            raise ValueError(f'Player {player_id} does not exist.')
        regiments = sorted(self.get_player_regiments(player_id), key=lambda regiment: regiment.id)
        if not regiments:
            print(f'{player.name} has no regiments on the map.')
            print('')
            return
        for regiment in regiments:
            self.map.print_regiment_metadata(regiment)

    def begin_round(self, resolution_messages: list[str] = None):
        if self.map is None:
            raise ValueError('A map must be loaded before starting a round.')
        self.turn += 1
        self._reset_round_planned_actions()
        expiration_messages = self.process_active_card_effects_for_new_turn(
            viewer_player_id=self.selected_player_id
        )
        self.map.reset_regiment_movement_for_new_turn()
        self.map.reset_battle_resolution_for_new_turn()
        build_messages = self.process_regiment_build_queue(viewer_player_id=self.selected_player_id)
        city_attack_messages = self.process_city_auto_attacks(viewer_player_id=self.selected_player_id)
        city_updates = self.map.advance_city_states_for_new_turn()
        material_messages = self.process_material_income_for_new_round(viewer_player_id=self.selected_player_id)
        growth_messages = self.process_city_growth_and_sovereignty(viewer_player_id=self.selected_player_id)
        draw_messages = self.process_influence_card_draws(viewer_player_id=self.selected_player_id)
        victory_result = self.evaluate_victory_conditions()
        self.last_round_summary = {
            'resolution_messages': list(resolution_messages or []),
            'expiration_messages': self._deduplicate_messages(expiration_messages),
            'build_messages': build_messages,
            'city_attack_messages': city_attack_messages,
            'city_updates': city_updates,
            'material_messages': self._deduplicate_messages(material_messages),
            'growth_messages': self._deduplicate_messages(growth_messages),
            'draw_messages': self._deduplicate_messages(draw_messages),
            'victory_result': victory_result,
        }
        self.handle_victory_result(victory_result)
        return self.last_round_summary

    def print_selected_player_round_summary(self):
        if self.map is None or self.selected_player_id is None:
            return
        self.map.print(viewer_player_id=self.selected_player_id)
        self.map.print_player_metadata()
        self.print_regiment_build_queue_status(
            viewer_player_id=self.selected_player_id,
            show_empty_message=False,
        )
        summary = self.last_round_summary or {}
        for update in summary.get('city_updates', []):
            city = self.map.get_city(update['city_id'])
            if city is None:
                continue
            if city.owner_id != self.selected_player_id:
                continue
            if city.occupation_recovery_turns_remaining > 0:
                print(
                    f'{city.symbol} stabilization: {city.occupation_recovery_turns_remaining} turn(s) remaining | '
                    f'influence multiplier={city.occupation_influence_multiplier():.2f}'
                )
            if city.siege_repair_delay_turns_remaining > 0:
                print(
                    f'{city.symbol} repairs delayed: {city.siege_repair_delay_turns_remaining} turn(s) remaining | '
                    f'regiment production lock={city.regiment_production_lock_turns_remaining}'
                )
            if update.get('capture_level_penalty_applied'):
                print(f'{city.name} lost 2 city levels after the occupation stabilized (now level {city.level}).')
        for key in (
            'resolution_messages',
            'build_messages',
            'city_attack_messages',
            'material_messages',
            'growth_messages',
            'expiration_messages',
            'draw_messages',
        ):
            for message in summary.get(key, []):
                print(message)

    def advance_to_next_player_turn(self):
        if not self.turn_order:
            return
        self.current_turn_player_index = (self.current_turn_player_index + 1) % len(self.turn_order)
        if self.current_turn_player_index == 0:
            resolution_messages = self.resolve_planned_round(viewer_player_id=self.selected_player_id)
            if not self.player_in_loop:
                self.last_round_summary = {
                    'resolution_messages': resolution_messages,
                    'expiration_messages': [],
                    'build_messages': [],
                    'city_attack_messages': [],
                    'city_updates': [],
                    'material_messages': [],
                    'growth_messages': [],
                    'draw_messages': [],
                    'victory_result': self.evaluate_victory_conditions(),
                }
                return
            self.begin_round(resolution_messages=resolution_messages)

    def execute_action_for_player(self, player_id: int, action: dict):
        action_type = action['action_type']
        if action_type == 'queue_regiment':
            return self.queue_regiment_order(
                player_id,
                action['target_id'],
                action.get('metadata', {}).get('regiment_name'),
            )
        if action_type == 'queue_navy':
            spawn_pos = action.get('metadata', {}).get('spawn_pos')
            return self.queue_navy_order(
                player_id,
                action['target_id'],
                spawn_pos[0],
                spawn_pos[1],
                action.get('metadata', {}).get('regiment_name'),
            )
        if action_type == 'queue_improvement':
            metadata = action.get('metadata', {})
            return self.queue_improvement_order(
                player_id,
                action['target_id'],
                metadata.get('improvement_kind'),
                metadata.get('target_pos'),
            )
        if action_type == 'move_regiment':
            target_x, target_y = action['target_pos']
            return self.move_regiment_for_player(player_id, action['actor_id'], target_x, target_y)
        if action_type == 'attack_regiment':
            return self.attack_with_regiment(player_id, action['actor_id'], 'regiment', action['target_id'])
        if action_type == 'attack_city':
            return self.attack_with_regiment(player_id, action['actor_id'], 'city', action['target_id'])
        if action_type == 'defend_regiment':
            return self.defend_regiment_for_player(player_id, action['actor_id'])
        if action_type == 'buy_card':
            return self.purchase_card_for_player(player_id, action.get('metadata', {}).get('rarity', 'common'))
        if action_type == 'recruit_hero':
            return self.recruit_hero_for_player(
                player_id,
                action['target_id'],
                action.get('metadata', {}).get('hero_name'),
            )
        if action_type == 'refit_force':
            return self.refit_force_for_player(
                player_id,
                action['target_id'],
                action.get('metadata', {}).get('upgrade_kind'),
            )
        if action_type == 'play_card':
            player = self.map.get_player(player_id)
            if player is None:
                raise ValueError(f'Player {player_id} does not exist')
            card_instance_id = action.get('metadata', {}).get('card_instance_id')
            hand_index = self._get_player_card_hand_index_by_instance_id(player, card_instance_id)
            if hand_index is None:
                raise ValueError(f'Card {card_instance_id} is no longer in hand')
            return self.play_card_for_player(
                player_id,
                hand_index,
                action.get('metadata', {}).get('target_payload', {}),
            )
        raise ValueError(f'Unsupported action type: {action_type}')

    def _action_is_visible_to_viewer(self, action: dict, viewer_player_id: int = None):
        if viewer_player_id is None:
            return True
        if action['player_id'] == viewer_player_id:
            return True
        return action.get('metadata', {}).get('target_owner_id') == viewer_player_id

    def _build_action_resolution_messages(self, player_id: int, action: dict, result):
        player = self.map.get_player(player_id) if self.map is not None else None
        player_name = player.name if player is not None else f'Player {player_id}'
        action_type = action['action_type']
        if action_type in {'queue_regiment', 'queue_navy'}:
            city = self.map.get_city(result['city_id']) if self.map is not None else None
            city_name = city.name if city is not None else f'City {result["city_id"]}'
            if action_type == 'queue_navy':
                return [
                    f'{player_name} queued navy "{result["regiment_name"]}" from {city_name} '
                    f'at port {result["spawn_pos"]} ({result["turns_to_build"]} turn(s) to build).'
                ]
            return [
                f'{player_name} queued regiment "{result["regiment_name"]}" at {city_name} '
                f'({result["turns_to_build"]} turn(s) to build).'
            ]
        if action_type == 'queue_improvement':
            city = self.map.get_city(result['city_id']) if self.map is not None else None
            city_name = city.name if city is not None else f'City {result["city_id"]}'
            location_text = f' at {result["target_pos"]}' if result.get('target_pos') is not None else ''
            return [
                f'{player_name} queued {result["improvement_name"]} for {city_name}{location_text} '
                f'({result["turns_to_build"]} turn(s) to build).'
            ]
        if action_type == 'move_regiment':
            return [f'{player_name} moved Regiment {result["regiment_id"]} to {result["target_pos"]}.']
        if action_type == 'defend_regiment':
            return [f'{player_name} set Regiment {result["regiment_id"]} to defend.']
        if action_type == 'buy_card':
            return [f'{player_name} bought a {result["rarity"].title()} card: {result["card"].definition.name}.']
        if action_type == 'recruit_hero':
            return [f'{player_name} recruited {result["hero_name"]} into Regiment {result["regiment_id"]}.']
        if action_type == 'refit_force':
            return [f'{player_name} refit Regiment {result["regiment_id"]} with a {result["upgrade_kind"]} upgrade.']
        if action_type == 'play_card':
            messages = [f'{player_name} played {result["card"].definition.name}.']
            messages.extend(result['messages'])
            return messages
        if action_type == 'attack_regiment':
            combat_result = result['result']
            target_regiment = result['target']
            attacker_losses = sum(combat_result['casualties_a'].values())
            defender_losses = sum(combat_result['casualties_b'].values())
            messages = [
                f'{player_name} attacked {target_regiment.symbol()} from {combat_result["attack_distance"]} tile(s): '
                f'attacker losses={attacker_losses}, defender losses={defender_losses}.'
            ]
            if combat_result['defeated_a']:
                messages.append(f'Regiment {combat_result["regiment_a_id"]} was destroyed.')
            if combat_result['defeated_b']:
                messages.append(f'Regiment {combat_result["regiment_b_id"]} was destroyed.')
            return messages
        if action_type == 'attack_city':
            siege_result = result['result']
            target_city = result['target']
            messages = [
                f'{player_name} attacked {target_city.name}: siege resistance '
                f'{siege_result["resistance_before"]} -> {siege_result["resistance_after"]}.'
            ]
            if siege_result['sacked']:
                new_owner = self.map.get_player(siege_result['new_owner_id']) if self.map is not None else None
                new_owner_name = new_owner.name if new_owner is not None else f'Player {siege_result["new_owner_id"]}'
                messages.append(
                    f'{target_city.name} was captured by {new_owner_name}; full influence returns in '
                    f'{siege_result["occupation_recovery_turns_remaining"]} turn(s).'
                )
            return messages
        return [f'{player_name} resolved {self.describe_planned_action(action)}.']

    def resolve_planned_round(self, viewer_player_id: int = None):
        if self.map is None:
            return []
        influence_rankings = [
            (player.id, self.map.get_player_total_influence_score(player.id))
            for player in self.map.players.values()
        ]
        influence_rankings.sort(key=lambda entry: (-entry[1], entry[0]))

        messages = []
        for player_id, _ in influence_rankings:
            for action in list(self._ensure_round_plan_entry(player_id)):
                if not self.player_in_loop:
                    break
                try:
                    result = self.execute_action_for_player(player_id, action)
                except ValueError as error:
                    if self._action_is_visible_to_viewer(action, viewer_player_id):
                        messages.append(
                            f'{self.describe_planned_action(action)} failed during resolution: {error}'
                        )
                    continue
                if self._action_is_visible_to_viewer(action, viewer_player_id):
                    messages.extend(self._build_action_resolution_messages(player_id, action, result))
            if not self.player_in_loop:
                break
        self._reset_round_planned_actions()
        return messages

    def execute_computer_turn(self, player_id: int):
        player = self.map.get_player(player_id) if self.map is not None else None
        if player is None:
            raise ValueError(f'Player {player_id} does not exist.')
        for action in self.ai_controller.plan_turn(self, player_id):
            if not self.player_in_loop:
                break
            try:
                self.queue_action_for_player(player_id, action)
            except ValueError:
                continue
            if self.get_player_planned_action_count(player_id) >= self.get_player_action_limit(player_id):
                break
        if not self.player_in_loop:
            return
        self.advance_to_next_player_turn()

    def resolve_until_human_turn(self):
        while self.player_in_loop:
            current_player = self.get_current_turn_player()
            if current_player is None:
                return
            if current_player.controller_type != 'computer':
                return
            self.execute_computer_turn(current_player.id)

    def end_human_turn(self):
        if not self.player_in_loop:
            return
        self.advance_to_next_player_turn()
        self.resolve_until_human_turn()
        if self.player_in_loop:
            self.print_selected_player_round_summary()

    def select_player_empire(self):
        if self.map is None:
            raise ValueError('A map must be loaded before selecting an empire.')
        if not self.map.players:
            print('This map has no empires to select.')
            self.selected_player_id = None
            return False

        print('Choose an empire for this match:')
        self.map.print_player_metadata(sort_by='player_id', show_rank=False)

        while True:
            selection = input('Enter the empire/player id to control, or leave empty to cancel: ').strip()
            if not selection:
                print('Empire selection canceled.')
                self.selected_player_id = None
                return False
            if not selection.isdigit():
                print('Empire id must be a positive integer.')
                continue

            player_id = int(selection)
            selected_player = self.map.get_player(player_id)
            if selected_player is None:
                print(f'Empire {player_id} does not exist on this map.')
                continue

            self.assign_match_controllers(player_id)
            print(f'You are now playing as {selected_player.name}.')
            return True

    def initialize_player_card_system(self):
        if self.map is None:
            raise ValueError('A map must be loaded before initializing player decks')
        Card._next_instance_id = 1
        ActiveCardEffect._next_effect_id = 1
        for player in self.map.players.values():
            player.initialize_cards(self.card_library.build_random_deck(
                deck_size=50,
                rng=self.random,
                reshuffle_enabled=self.allow_deck_reshuffle,
            ))
        for player in self.map.players.values():
            self.draw_cards_for_player(player.id, 5)

    def get_card_draw_probability(self, player_id: int):
        if self.map is None:
            return 0.0
        total_influence = self.map.get_player_total_influence_score(player_id)
        max_map_influence = max(
            100.0,
            self.map.width * self.map.height * self.map.PLAYER_TOTAL_INFLUENCE_TILE_WEIGHT,
        )
        normalized_score = max(0.0, min(1.0, total_influence / max_map_influence))
        return round(min(0.85, 0.15 + (normalized_score * 0.70)), 4)

    def _refresh_card_affected_map_state(self, refresh_visibility: bool = False):
        if self.map is None:
            return
        if refresh_visibility:
            self.map.refresh_all_player_discovery()
        else:
            self.map.recalculate_tile_influence()

    def draw_card_for_player(self, player_id: int):
        if self.map is None:
            raise ValueError('A map must be loaded before drawing cards')
        player = self.map.get_player(player_id)
        if player is None:
            raise ValueError(f'Player {player_id} does not exist')
        if player.deck is None:
            raise ValueError(f'Player {player_id} does not have a deck')
        if not player.can_draw_card():
            return {'drawn': False, 'reason': 'hand_full'}
        drawn_card = player.deck.draw()
        if drawn_card is None:
            return {'drawn': False, 'reason': 'deck_empty'}
        player.hand.append(drawn_card)
        return {'drawn': True, 'card': drawn_card}

    def draw_cards_for_player(self, player_id: int, count: int):
        draw_results = []
        for _ in range(max(0, int(count))):
            draw_result = self.draw_card_for_player(player_id)
            draw_results.append(draw_result)
            if not draw_result['drawn']:
                break
        return draw_results

    def discard_card_for_player(self, player_id: int, hand_index: int):
        if self.turn <= self.card_unlock_turn:
            raise ValueError(f'Cards cannot be discarded until after turn {self.card_unlock_turn}')
        player = self.map.get_player(player_id) if self.map is not None else None
        if player is None:
            raise ValueError(f'Player {player_id} does not exist')
        if player.deck is None:
            raise ValueError(f'Player {player_id} does not have a deck')
        if hand_index < 0 or hand_index >= len(player.hand):
            raise ValueError(f'Hand selection {hand_index + 1} is out of range')
        if player.hand[hand_index].instance_id in self.get_player_planned_card_instance_ids(player_id):
            raise ValueError(f'{player.hand[hand_index].definition.name} is already planned to be played this turn')
        discarded_card = player.hand.pop(hand_index)
        player.deck.discard(discarded_card)
        return {'discarded': True, 'card': discarded_card}

    def preview_top_cards_for_player(self, player_id: int, count: int):
        player = self.map.get_player(player_id) if self.map is not None else None
        if player is None:
            raise ValueError(f'Player {player_id} does not exist')
        if player.deck is None:
            raise ValueError(f'Player {player_id} does not have a deck')
        return player.deck.peek_top(count)

    def print_player_hand(self, player_id: int):
        player = self.map.get_player(player_id) if self.map is not None else None
        if player is None:
            raise ValueError(f'Player {player_id} does not exist')
        if player.deck is None:
            print('This player has no deck.')
            return
        action_limit = self.get_player_action_limit(player_id)
        card_limit = min(action_limit, self.get_player_card_limit(player_id))
        queued_card_ids = self.get_player_planned_card_instance_ids(player_id)
        print(
            f'CARDS: hand={len(player.hand)}/{player.hand_limit()} | '
            f'planned={self.get_player_planned_card_count(player_id)}/{card_limit} | '
            f'deck={player.deck.cards_remaining()} | discard={len(player.deck.discard_pile)} | '
            f'exhausted={len(player.deck.exhausted_pile)}'
        )
        if not player.hand:
            print('  No cards in hand.')
            print('')
            return
        for index, card in enumerate(player.hand, start=1):
            rarity_color = self.card_library.RARITY_COLORS.get(card.definition.rarity, '')
            rarity_label = card.definition.rarity.title()
            card_label = f'{index}. {card.definition.name} [{rarity_label} | {card.definition.card_type}]'
            if card.instance_id in queued_card_ids:
                card_label += ' [queued]'
            if rarity_color:
                card_label = f'{rarity_color}{card_label}{Style.RESET_ALL}'
            print(f'  {card_label}')
            print(f'     {card.definition.description}')
        print('')

    def _resolve_card_target(self, player: Player, definition: CardDefinition, target_payload: dict):
        target_scope = definition.target_scope
        payload = dict(target_payload) if target_payload is not None else {}
        if target_scope in {'self', 'none'}:
            return {'target_kind': 'player', 'entity': player, 'target_id': player.id}

        target_kind = payload.get('target_kind')
        target_id = payload.get('target_id')
        if target_kind is None or target_id is None:
            raise ValueError(f'Card "{definition.name}" requires a target')

        if target_scope in {'own_regiment', 'enemy_regiment'}:
            if target_kind != 'regiment':
                raise ValueError(f'Card "{definition.name}" must target a regiment')
            regiment = self.map.get_regiment(int(target_id)) if self.map is not None else None
            if regiment is None:
                raise ValueError(f'Regiment {target_id} does not exist')
            is_owned = regiment.owner_id == player.id
            if target_scope == 'own_regiment' and not is_owned:
                raise ValueError(f'Card "{definition.name}" must target one of your regiments')
            if target_scope == 'enemy_regiment':
                if is_owned:
                    raise ValueError(f'Card "{definition.name}" must target an enemy regiment')
                if not self.map.is_regiment_visible_to_player(regiment.id, player.id):
                    raise ValueError(f'Enemy regiment {regiment.id} is not visible to your empire')
            return {'target_kind': 'regiment', 'entity': regiment, 'target_id': regiment.id}

        if target_scope in {'own_city', 'enemy_city'}:
            if target_kind != 'city':
                raise ValueError(f'Card "{definition.name}" must target a city')
            city = self.map.get_city(int(target_id)) if self.map is not None else None
            if city is None:
                raise ValueError(f'City {target_id} does not exist')
            is_owned = city.owner_id == player.id
            if target_scope == 'own_city' and not is_owned:
                raise ValueError(f'Card "{definition.name}" must target one of your cities')
            if target_scope == 'enemy_city':
                if is_owned:
                    raise ValueError(f'Card "{definition.name}" must target an enemy city')
                if not self.map.is_city_visible_to_player(city.id, player.id):
                    raise ValueError(f'Enemy city {city.id} is not visible to your empire')
            return {'target_kind': 'city', 'entity': city, 'target_id': city.id}

        if target_scope == 'enemy_player':
            if target_kind != 'player':
                raise ValueError(f'Card "{definition.name}" must target a player')
            target_player = self.map.get_player(int(target_id)) if self.map is not None else None
            if target_player is None:
                raise ValueError(f'Player {target_id} does not exist')
            if target_player.id == player.id:
                raise ValueError(f'Card "{definition.name}" must target an opponent')
            return {'target_kind': 'player', 'entity': target_player, 'target_id': target_player.id}

        raise ValueError(f'Unsupported card target scope: {target_scope}')

    def _resolve_effect_host_player(self, source_player: Player, resolved_target: dict):
        target_kind = resolved_target.get('target_kind')
        target_entity = resolved_target.get('entity')
        if target_kind == 'player' and target_entity is not None:
            return target_entity
        if target_kind == 'regiment' and target_entity is not None:
            return self.map.get_player(target_entity.owner_id)
        if target_kind == 'city' and target_entity is not None:
            return self.map.get_player(target_entity.owner_id)
        return source_player

    def _apply_duration_effect_delta(self, active_effect: ActiveCardEffect, reverse: bool = False):
        delta = active_effect.magnitude
        if isinstance(delta, (int, float)) and reverse:
            delta = -delta

        if active_effect.target_kind == 'regiment':
            regiment = self.map.get_regiment(active_effect.target_id) if self.map is not None else None
            if regiment is None:
                return
            if active_effect.effect_type == 'regiment_attack_bonus':
                regiment.attack_score_bonus += delta
                regiment.city_attack_score_bonus += delta
            elif active_effect.effect_type == 'regiment_defense_bonus':
                regiment.defense_score_bonus += delta
            elif active_effect.effect_type == 'regiment_influence_multiplier_bonus':
                regiment.influence_score_multiplier = max(0.0, round(regiment.influence_score_multiplier + delta, 4))
                self._refresh_card_affected_map_state()
            elif active_effect.effect_type == 'regiment_extra_attack_bonus':
                regiment.extra_attack_allowance = max(0, regiment.extra_attack_allowance + int(delta))
            elif active_effect.effect_type == 'regiment_move_after_action':
                regiment.move_after_action_sources = max(0, regiment.move_after_action_sources + int(delta))
            elif active_effect.effect_type == 'regiment_movement_lock':
                regiment.movement_blocked_sources = max(0, regiment.movement_blocked_sources + int(delta))
            else:
                raise ValueError(f'Unsupported regiment duration effect: {active_effect.effect_type}')
            return

        if active_effect.target_kind == 'city':
            city = self.map.get_city(active_effect.target_id) if self.map is not None else None
            if city is None:
                return
            if active_effect.effect_type == 'city_defense_bonus':
                city.defense_score_bonus += delta
            elif active_effect.effect_type == 'city_influence_multiplier_bonus':
                city.influence_score_multiplier = max(0.0, round(city.influence_score_multiplier + delta, 4))
                self._refresh_card_affected_map_state()
            else:
                raise ValueError(f'Unsupported city duration effect: {active_effect.effect_type}')
            return

        if active_effect.target_kind == 'player':
            target_player = self.map.get_player(active_effect.target_id) if self.map is not None else None
            if target_player is None:
                return
            if active_effect.effect_type == 'player_card_play_lock':
                target_player.card_play_lock_sources = max(0, target_player.card_play_lock_sources + int(delta))
                return
            raise ValueError(f'Unsupported player duration effect: {active_effect.effect_type}')

        raise ValueError(f'Unsupported duration effect target: {active_effect.target_kind}')

    def _execute_immediate_card_effect(self, source_player: Player, card: Card,
                                       effect: CardEffectDefinition, resolved_target: dict,
                                       target_payload: dict):
        target_entity = resolved_target.get('entity')
        target_kind = resolved_target.get('target_kind')
        payload = dict(target_payload) if target_payload is not None else {}

        if effect.effect_type == 'grant_move_after_action_charge':
            if target_kind != 'regiment':
                raise ValueError('Move-after-action cards must target a regiment')
            target_entity.move_after_action_charges += int(effect.magnitude)
            return [f'{target_entity.symbol()} may keep movement after its next qualifying action.']

        if effect.effect_type == 'grant_terrain_boundary_pass':
            if target_kind != 'regiment':
                raise ValueError('Terrain-pass cards must target a regiment')
            target_entity.terrain_boundary_pass_enabled = True
            return [f'{target_entity.symbol()} can traverse impassable land terrain until it returns to normal terrain.']

        if effect.effect_type == 'add_regiment_hero':
            if target_kind != 'regiment':
                raise ValueError('Hero cards must target a regiment')
            hero_name = payload.get('hero_name') or f'Hero_{self.random.randint(1000, 9999)}'
            target_entity.add_hero(hero_name)
            return [f'{hero_name} joined {target_entity.symbol()}.']

        if effect.effect_type == 'remove_regiment_hero':
            if target_kind != 'regiment':
                raise ValueError('Hero-removal cards must target a regiment')
            removed_hero = target_entity.remove_hero()
            return [f'{removed_hero} was removed from {target_entity.symbol()}.']

        if effect.effect_type == 'modify_regiment_units':
            if target_kind != 'regiment':
                raise ValueError('Unit-modification cards must target a regiment')
            unit_type = str(payload.get('unit_type', '')).strip().lower()
            if unit_type not in {'infantry', 'ranged', 'cavalry', 'siege', 'navy'}:
                raise ValueError('A unit type of infantry, ranged, cavalry, siege, or navy is required')
            current_value = getattr(target_entity, unit_type)
            updated_value = max(0, current_value + int(effect.magnitude))
            if current_value == updated_value and int(effect.magnitude) < 0:
                raise ValueError(f'{target_entity.symbol()} has no {unit_type} to remove')
            target_entity.update_composition(**{unit_type: updated_value})
            self._refresh_card_affected_map_state()
            return [f'{target_entity.symbol()} {unit_type} changed from {current_value} to {updated_value}.']

        if effect.effect_type == 'draw_cards':
            draw_results = self.draw_cards_for_player(source_player.id, int(effect.magnitude))
            drawn_cards = [result['card'].definition.name for result in draw_results if result.get('drawn')]
            if not drawn_cards:
                return ['No additional cards could be drawn.']
            return [f'Drew: {", ".join(drawn_cards)}.']

        if effect.effect_type == 'choose_from_top_cards':
            top_cards = self.preview_top_cards_for_player(source_player.id, int(effect.magnitude))
            if not top_cards:
                return ['No cards remain in the deck to choose from.']
            if not source_player.can_draw_card():
                raise ValueError(f'{source_player.name} cannot take a chosen card because the hand is full')
            choice_index = int(payload.get('choice_index', 0))
            if choice_index < 0 or choice_index >= len(top_cards):
                raise ValueError(f'Choice index must be between 1 and {len(top_cards)}')
            chosen_card = top_cards[choice_index]
            source_player.deck.remove_card(chosen_card)
            source_player.hand.append(chosen_card)
            return [f'Added {chosen_card.definition.name} from the top of the deck to your hand.']

        if effect.effect_type == 'gain_random_card_by_rarity':
            requested_rarity = str(payload.get('rarity', '')).strip().lower()
            if requested_rarity not in effect.metadata.get('allowable_rarities', []):
                raise ValueError('You must choose Uncommon, Rare, or Legendary for this card')
            if not source_player.can_draw_card():
                raise ValueError(f'{source_player.name} cannot receive another card because the hand is full')
            gained_card = self.card_library.build_random_card_of_rarity(requested_rarity, rng=self.random)
            source_player.hand.append(gained_card)
            return [f'Gained a random {requested_rarity.title()} card: {gained_card.definition.name}.']

        if effect.effect_type == 'discard_hand_and_redraw':
            while source_player.hand:
                source_player.deck.discard(source_player.hand.pop())
            draw_count = min(int(effect.magnitude), source_player.hand_limit())
            draw_results = self.draw_cards_for_player(source_player.id, draw_count)
            drawn_cards = [result['card'].definition.name for result in draw_results if result.get('drawn')]
            return [f'Redrew {len(drawn_cards)} card(s): {", ".join(drawn_cards) if drawn_cards else "none"}']

        if effect.effect_type == 'modify_city_radius_and_influence':
            if target_kind != 'city':
                raise ValueError('City expansion cards must target a city')
            target_entity.influence_radius_bonus += int(effect.magnitude)
            target_entity.influence_score_multiplier = max(
                0.0,
                round(
                    target_entity.influence_score_multiplier +
                    float(effect.metadata.get('influence_multiplier_bonus', 0.0)),
                    4,
                ),
            )
            self._refresh_card_affected_map_state(refresh_visibility=True)
            return [
                f'{target_entity.symbol} now has influence radius bonus {target_entity.influence_radius_bonus} '
                f'and influence multiplier {target_entity.influence_score_multiplier:.2f}.'
            ]

        raise ValueError(f'Unsupported immediate card effect: {effect.effect_type}')

    def play_card_for_player(self, player_id: int, hand_index: int, target_payload: dict = None):
        if self.turn <= self.card_unlock_turn:
            raise ValueError(f'Cards cannot be played until after turn {self.card_unlock_turn}')
        if self.map is None:
            raise ValueError('A map must be loaded before cards can be played')
        player = self.map.get_player(player_id)
        if player is None:
            raise ValueError(f'Player {player_id} does not exist')
        if player.deck is None:
            raise ValueError(f'Player {player_id} does not have a deck')
        if not player.can_play_cards():
            raise ValueError(f'{player.name} is currently prevented from playing cards')
        if hand_index < 0 or hand_index >= len(player.hand):
            raise ValueError(f'Hand selection {hand_index + 1} is out of range')

        card = player.hand.pop(hand_index)
        try:
            resolved_target = self._resolve_card_target(player, card.definition, target_payload or {})
            effect_messages = []
            for effect in card.definition.effects:
                if effect.duration_turns > 0 or card.definition.card_type == 'duration':
                    host_player = self._resolve_effect_host_player(player, resolved_target)
                    active_effect = ActiveCardEffect(
                        source_player_id=player.id,
                        host_player_id=host_player.id,
                        card=card,
                        target_kind=resolved_target['target_kind'],
                        target_id=resolved_target['target_id'],
                        effect=effect,
                    )
                    host_player.active_card_effects.append(active_effect)
                    self._apply_duration_effect_delta(active_effect, reverse=False)
                    effect_messages.append(
                        f'{card.definition.name} applied to {resolved_target["target_kind"]} '
                        f'{resolved_target["target_id"]} for {active_effect.turns_remaining} turn(s).'
                    )
                else:
                    effect_messages.extend(self._execute_immediate_card_effect(
                        source_player=player,
                        card=card,
                        effect=effect,
                        resolved_target=resolved_target,
                        target_payload=target_payload or {},
                    ))
        except Exception:
            player.hand.insert(hand_index, card)
            raise

        player.deck.exhaust(card)
        return {'played': True, 'card': card, 'messages': effect_messages}

    def process_active_card_effects_for_new_turn(self, viewer_player_id: int = None):
        if self.map is None:
            return []
        expiration_messages = []
        for player in self.map.players.values():
            remaining_effects = []
            for active_effect in player.active_card_effects:
                active_effect.turns_remaining -= 1
                if active_effect.turns_remaining > 0:
                    remaining_effects.append(active_effect)
                    continue
                self._apply_duration_effect_delta(active_effect, reverse=True)
                if viewer_player_id in {None, active_effect.source_player_id, active_effect.host_player_id, active_effect.target_id}:
                    expiration_messages.append(
                        f'{active_effect.card_name} expired on {active_effect.target_kind} {active_effect.target_id}.'
                    )
            player.active_card_effects = remaining_effects
        return expiration_messages

    def process_influence_card_draws(self, viewer_player_id: int = None):
        if self.map is None or self.turn <= self.card_unlock_turn:
            return []
        draw_messages = []
        for player in self.map.players.values():
            if player.deck is None or not player.can_draw_card():
                continue
            if self.random.random() > self.get_card_draw_probability(player.id):
                continue
            draw_result = self.draw_card_for_player(player.id)
            if draw_result.get('drawn') and player.id == viewer_player_id:
                draw_messages.append(
                    f'Influence draw: {draw_result["card"].definition.name} '
                    f'({draw_result["card"].definition.rarity.title()}).'
                )
        return draw_messages

    def evaluate_victory_conditions(self):
        if self.map is None:
            return None
        for condition_id in self.active_victory_conditions:
            if condition_id == 'capture-all-capitals':
                result = self._check_capture_all_capitals_victory()
            elif condition_id == 'influence-threshold':
                result = self._check_influence_score_victory()
            else:
                raise ValueError(f'Unsupported victory condition: {condition_id}')
            if result is not None:
                return result
        return None

    def _check_capture_all_capitals_victory(self):
        players_with_capitals = self.map.get_players_with_capitals()
        if len(players_with_capitals) != 1:
            return None
        winner_id = next(iter(players_with_capitals))
        capital_count = len(self.map.get_player_capitals(winner_id))
        if capital_count == 0:
            return None
        return {
            'condition_id': 'capture-all-capitals',
            'winner_id': winner_id,
            'details': f'controls the only remaining capital(s): {capital_count}',
        }

    def _check_influence_score_victory(self):
        if self.influence_victory_threshold is None:
            return None
        for player in self.map.players.values():
            influence_score = self.map.get_player_total_influence_score(player.id)
            if influence_score >= self.influence_victory_threshold:
                return {
                    'condition_id': 'influence-threshold',
                    'winner_id': player.id,
                    'details': (
                        f'reached influence {influence_score:.2f} '
                        f'(threshold={self.influence_victory_threshold:.2f})'
                    ),
                }
        return None

    def handle_victory_result(self, victory_result: dict):
        if victory_result is None:
            return False
        winner = self.map.get_player(victory_result['winner_id']) if self.map is not None else None
        winner_name = winner.name if winner is not None else f'Player {victory_result["winner_id"]}'
        print(
            f'VICTORY: {winner_name} wins by {victory_result["condition_id"]}. '
            f'({victory_result["details"]})'
        )
        if self.selected_player_id is not None and self.selected_player_id != victory_result['winner_id']:
            selected_player = self.map.get_player(self.selected_player_id)
            if selected_player is not None:
                print(f'{selected_player.name} has been defeated.')
        self.player_in_loop = False
        return True

    def run(self):

        def start_new_game():
            print('Starting a new game...')
            while True:
                map_name = input('Enter the map file name (e.g., "test_map.map"), or leave empty to cancel: ').strip()
                if not map_name:
                    print('New game creation canceled.')
                    return
                map_path = Path(map_name)
                if not map_path.is_absolute():
                    map_path = Path(__file__).resolve().parent / map_path
                # print(f'#DEBUG: map_path = "{map_path}"')
                # print(f'#DEBUG: map_path.is_file() = {map_path.is_file()}')
                if not map_path.is_file():
                    print(f'Map file "{map_name}" does not exist in the game directory. Please provide a valid map file name.')
                    continue
                maploader = MapLoader(str(map_path))
                self.map = maploader.parse()
                self.turn = 0
                self.regiment_build_queue = []
                if not self.select_player_empire():
                    self.map = None
                    return
                self.initialize_player_economy()
                self.initialize_player_card_system()
                self.initialize_turn_order()
                self.player_in_loop = True
                self.begin_round()
                self.resolve_until_human_turn()
                if not self.player_in_loop:
                    return
                player_loop()
                return

        def quit_to_main_menu():
            print('Are you sure you want to quit to the main menu? (y/n)')
            answer = input().strip().lower()
            if answer in ['y', 'yes']:
                self.player_in_loop = False
            else:
                print('Continuing the game.')

        def print_regiment_build_queue_status(show_empty_message: bool = True):
            selected_player = self.get_selected_player()
            self.print_regiment_build_queue_status(
                viewer_player_id=selected_player.id if selected_player is not None else None,
                show_empty_message=show_empty_message,
            )

        def _parse_delta_coordinates(raw_value: str, label: str = 'Movement delta'):
            return _parse_tile_coordinates(raw_value, label=label)

        def _resolve_owned_port_tile(selection: str, owner_id: int, city_id: int):
            spawn_x, spawn_y = _parse_tile_coordinates(selection, label='Port tile')
            self._validate_navy_spawn_tile(owner_id, city_id, spawn_x, spawn_y)
            return (spawn_x, spawn_y)

        def queue_regiment_order_action():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return

            try:
                city = _resolve_owned_city(
                    input('Enter friendly city id or exact name to queue from: ').strip(),
                    selected_player.id,
                )
                default_name = f'{city.name} Guard'
                regiment_name = input(f'Enter regiment name (default: {default_name}): ').strip() or default_name
                result = self.queue_action_for_player(selected_player.id, {
                    'action_type': 'queue_regiment',
                    'target_id': city.id,
                    'metadata': {'regiment_name': regiment_name},
                })
                print(
                    f"Planned regiment '{regiment_name}' from {city.name}. "
                    f'Actions planned: {result["action_count"]}/{result["action_limit"]}.'
                )
            except ValueError as error:
                print(error)

        def queue_navy_order_action():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return

            try:
                city = _resolve_owned_city(
                    input('Enter friendly city id or exact name to queue from: ').strip(),
                    selected_player.id,
                )
                port_improvements = self.map.get_city_ports(city.id)
                if not port_improvements:
                    raise ValueError(f'{city.name} needs a Port improvement before it can launch navies.')
                if len(port_improvements) == 1:
                    spawn_pos = tuple(port_improvements[0].tile_pos)
                else:
                    print(f'Available ports: {", ".join(str(tuple(port.tile_pos)) for port in port_improvements)}')
                    spawn_pos = _resolve_owned_port_tile(
                        input('Enter port tile for the navy to launch from as x y: ').strip(),
                        selected_player.id,
                        city.id,
                    )
                default_name = f'{city.name} Fleet'
                navy_name = input(f'Enter navy name (default: {default_name}): ').strip() or default_name
                result = self.queue_action_for_player(selected_player.id, {
                    'action_type': 'queue_navy',
                    'target_id': city.id,
                    'metadata': {
                        'regiment_name': navy_name,
                        'spawn_pos': spawn_pos,
                    },
                })
                print(
                    f"Planned navy '{navy_name}' from {city.name} at port {spawn_pos}. "
                    f'Actions planned: {result["action_count"]}/{result["action_limit"]}.'
                )
            except ValueError as error:
                print(error)

        def queue_improvement_order_action():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return

            try:
                Improvement.initialize_definitions()
                city = _resolve_owned_city(
                    input('Enter friendly city id or exact name to build from: ').strip(),
                    selected_player.id,
                )
                print('Available improvements:')
                for definition in Improvement.DEFINITIONS.values():
                    if city.level < definition.min_city_level:
                        continue
                    print(
                        f'  {definition.improvement_kind}: level>={definition.min_city_level} | '
                        f'cost={definition.costs} | turns={definition.build_turns}'
                    )
                improvement_kind = input('Enter improvement kind: ').strip().lower()
                definition = self.get_improvement_definition(improvement_kind)
                target_pos = None
                if not definition.intra_city:
                    valid_positions = self.find_valid_improvement_sites_for_city(city.id, definition.improvement_kind)
                    if not valid_positions:
                        raise ValueError(f'No valid {definition.name} sites are currently available for {city.name}.')
                    print(f'Valid sites: {", ".join(str(position) for position in valid_positions)}')
                    target_pos = _parse_tile_coordinates(
                        input('Enter target tile as x y: ').strip(),
                        label='Improvement tile',
                    )
                result = self.queue_action_for_player(selected_player.id, {
                    'action_type': 'queue_improvement',
                    'target_id': city.id,
                    'metadata': {
                        'improvement_kind': definition.improvement_kind,
                        'improvement_name': definition.name,
                        'target_pos': target_pos,
                    },
                })
                print(
                    f'Planned {definition.name} for {city.name}. '
                    f'Actions planned: {result["action_count"]}/{result["action_limit"]}.'
                )
            except ValueError as error:
                print(error)

        def buy_card_action():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return
            try:
                available_rarities = self.get_available_card_purchase_rarities(selected_player.id)
                print(f'Buyable rarities: {", ".join(available_rarities)}')
                rarity = input('Enter rarity to buy: ').strip().lower()
                result = self.queue_action_for_player(selected_player.id, {
                    'action_type': 'buy_card',
                    'metadata': {'rarity': rarity},
                })
                print(
                    f'Planned {rarity.title()} card purchase. '
                    f'Actions planned: {result["action_count"]}/{result["action_limit"]}.'
                )
            except ValueError as error:
                print(error)

        def recruit_hero_action():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return
            try:
                regiment = _resolve_owned_regiment(
                    input('Enter regiment/navy id or exact name to recruit into: ').strip(),
                    selected_player.id,
                )
                hero_name = input('Enter hero name (leave empty for random): ').strip()
                result = self.queue_action_for_player(selected_player.id, {
                    'action_type': 'recruit_hero',
                    'target_id': regiment.id,
                    'metadata': {'hero_name': hero_name or None},
                })
                print(
                    f'Planned hero recruitment for {regiment.symbol()}. '
                    f'Actions planned: {result["action_count"]}/{result["action_limit"]}.'
                )
            except ValueError as error:
                print(error)

        def refit_force_action():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return
            try:
                regiment = _resolve_owned_regiment(
                    input('Enter regiment/navy id or exact name to refit: ').strip(),
                    selected_player.id,
                )
                upgrade_kind = input('Choose upgrade [r]anged or [s]iege: ').strip().lower()
                upgrade_lookup = {
                    'r': 'ranged',
                    'ranged': 'ranged',
                    's': 'siege',
                    'siege': 'siege',
                }
                if upgrade_kind not in upgrade_lookup:
                    raise ValueError('Upgrade must be ranged or siege.')
                result = self.queue_action_for_player(selected_player.id, {
                    'action_type': 'refit_force',
                    'target_id': regiment.id,
                    'metadata': {'upgrade_kind': upgrade_lookup[upgrade_kind]},
                })
                print(
                    f'Planned {upgrade_lookup[upgrade_kind]} refit for {regiment.symbol()}. '
                    f'Actions planned: {result["action_count"]}/{result["action_limit"]}.'
                )
            except ValueError as error:
                print(error)

        def cancel_regiment_order_action():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return

            try:
                city = _resolve_owned_city(
                    input('Enter friendly city id or exact name to cancel production from: ').strip(),
                    selected_player.id,
                )
                result = self.cancel_regiment_order(selected_player.id, city.id)
                if result.get('order_kind') == 'improvement':
                    print(
                        f"Canceled improvement '{result['improvement_name']}' at {city.name}. "
                        f'It had {max(0, result["turns_remaining"])} turn(s) remaining.'
                    )
                else:
                    print(
                        f"Canceled {result.get('force_kind', 'regiment')} '{result['regiment_name']}' at {city.name}. "
                        f'It had {max(0, result["turns_remaining"])} turn(s) remaining.'
                    )
            except ValueError as error:
                print(error)

        def create_regiment_order():
            action_menu = ConsoleMenu()
            action_menu.add_option('Queue Regiment', queue_regiment_order_action, 'q')
            action_menu.add_option('Queue Navy', queue_navy_order_action, 'n')
            action_menu.add_option('Queue Improvement', queue_improvement_order_action, 'i')
            action_menu.add_option('Cancel Queued Production', cancel_regiment_order_action, 'c')
            action_menu.add_option('View Production Queue', print_regiment_build_queue_status, 'v')
            action_menu.add_option('Back', lambda: None, 'b')
            print('---BUILD / PRODUCE---')
            action_menu.prompt_and_select()

        def _normalize_lookup_name(value: str):
            return str(value).strip().lower()

        def _find_regiments_by_name(name: str, owner_id: int = None):
            normalized_name = _normalize_lookup_name(name)
            if not normalized_name:
                return []
            return [
                regiment for regiment in self.map.regiments.values()
                if _normalize_lookup_name(regiment.name) == normalized_name
                and (owner_id is None or regiment.owner_id == owner_id)
            ]

        def _find_cities_by_name(name: str, owner_id: int = None):
            normalized_name = _normalize_lookup_name(name)
            if not normalized_name:
                return []
            return [
                city for city in self.map.cities.values()
                if _normalize_lookup_name(city.name) == normalized_name
                and (owner_id is None or city.owner_id == owner_id)
            ]

        def _resolve_owned_city(selection: str, owner_id: int):
            normalized = str(selection).strip()
            if not normalized:
                raise ValueError('City selection cannot be empty.')

            compact = normalized.replace(' ', '')
            target_token = compact.upper()
            if target_token.startswith('*C') and compact[2:].isdigit():
                city_id = int(compact[2:])
            elif target_token.startswith('C') and compact[1:].isdigit():
                city_id = int(compact[1:])
            elif normalized.isdigit():
                city_id = int(normalized)
            else:
                city_matches = _find_cities_by_name(normalized, owner_id=owner_id)
                if not city_matches:
                    raise ValueError(f'No city named "{normalized}" belongs to your empire.')
                if len(city_matches) > 1:
                    raise ValueError(f'Multiple cities named "{normalized}" belong to your empire. Use the city id instead.')
                return city_matches[0]

            city = self.map.get_city(city_id)
            if city is None:
                raise ValueError(f'City {city_id} does not exist.')
            if city.owner_id != owner_id:
                raise ValueError(f'City {city_id} belongs to another empire.')
            return city

        def _resolve_owned_regiment(selection: str, owner_id: int):
            normalized = str(selection).strip()
            if not normalized:
                raise ValueError('Attacking regiment selection cannot be empty.')

            compact = normalized.replace(' ', '')
            target_token = compact.upper()
            if target_token.startswith(('R', 'N')) and compact[1:].isdigit():
                regiment_id = int(compact[1:])
                regiment = self.map.get_regiment(regiment_id)
                if regiment is None:
                    raise ValueError(f'Regiment {regiment_id} does not exist.')
                if regiment.owner_id != owner_id:
                    raise ValueError(f'Regiment {regiment_id} belongs to another empire.')
                return regiment

            if normalized.isdigit():
                regiment_id = int(normalized)
                regiment = self.map.get_regiment(regiment_id)
                if regiment is None:
                    raise ValueError(f'Regiment {regiment_id} does not exist.')
                if regiment.owner_id != owner_id:
                    raise ValueError(f'Regiment {regiment_id} belongs to another empire.')
                return regiment

            matches = _find_regiments_by_name(normalized, owner_id=owner_id)
            if not matches:
                raise ValueError(f'No regiment named "{normalized}" belongs to your empire.')
            if len(matches) > 1:
                raise ValueError(f'Multiple regiments named "{normalized}" belong to your empire. Use the regiment id instead.')
            return matches[0]

        def _resolve_attack_target(selection: str, attacker_owner_id: int):
            normalized = str(selection).strip()
            if not normalized:
                raise ValueError('Target selection cannot be empty.')

            def _require_target_visibility(kind: str, entity_id: int, location: tuple[int, int] = None):
                if location is None:
                    raise ValueError(f'{kind} {entity_id} is not on the map.')
                if location not in self.map.get_player_visible_tiles(attacker_owner_id):
                    raise ValueError(f'{kind} {entity_id} is not currently visible to your empire.')

            compact = normalized.replace(' ', '')
            target_token = compact.upper()
            if target_token.startswith('*C') and compact[2:].isdigit():
                city_id = int(compact[2:])
                city = self.map.get_city(city_id)
                if city is None:
                    raise ValueError(f'City {city_id} does not exist.')
                if not city.is_capital:
                    raise ValueError(f'City {city_id} is not a capital.')
                if city.owner_id == attacker_owner_id:
                    raise ValueError('Friendly fire is not allowed.')
                _require_target_visibility('City', city_id, self.map.get_city_location(city_id))
                return {'kind': 'city', 'entity': city}

            if target_token.startswith('C') and compact[1:].isdigit():
                city_id = int(compact[1:])
                city = self.map.get_city(city_id)
                if city is None:
                    raise ValueError(f'City {city_id} does not exist.')
                if city.is_capital:
                    raise ValueError(f'City {city_id} is a capital. Target it as *C{city_id}.')
                if city.owner_id == attacker_owner_id:
                    raise ValueError('Friendly fire is not allowed.')
                _require_target_visibility('City', city_id, self.map.get_city_location(city_id))
                return {'kind': 'city', 'entity': city}

            if target_token.startswith(('R', 'N')) and compact[1:].isdigit():
                regiment_id = int(compact[1:])
                regiment = self.map.get_regiment(regiment_id)
                if regiment is None:
                    raise ValueError(f'Regiment {regiment_id} does not exist.')
                if regiment.owner_id == attacker_owner_id:
                    raise ValueError('Friendly fire is not allowed.')
                _require_target_visibility('Regiment', regiment_id, self.map.get_regiment_location(regiment_id))
                return {'kind': 'regiment', 'entity': regiment}

            regiment_matches = [
                regiment for regiment in _find_regiments_by_name(normalized)
                if regiment.owner_id != attacker_owner_id
                and self.map.is_regiment_visible_to_player(regiment.id, attacker_owner_id)
            ]
            city_matches = [
                city for city in _find_cities_by_name(normalized)
                if city.owner_id != attacker_owner_id
                and self.map.is_city_visible_to_player(city.id, attacker_owner_id)
            ]
            target_matches = (
                [{'kind': 'regiment', 'entity': regiment} for regiment in regiment_matches] +
                [{'kind': 'city', 'entity': city} for city in city_matches]
            )
            if not target_matches:
                raise ValueError(f'No visible enemy regiment or city named "{normalized}" exists.')
            if len(target_matches) > 1:
                raise ValueError(f'Multiple enemy targets named "{normalized}" exist. Use R#, N#, C#, or *C# instead.')
            return target_matches[0]

        def regiment_attack_or_defend():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return

            regiment_input = input('Enter regiment/navy id or exact name to attack/defend with: ').strip()
            try:
                regiment = _resolve_owned_regiment(regiment_input, selected_player.id)
            except ValueError as error:
                print(error)
                return

            try:
                action = input('Choose action: [a]ttack or [d]efend: ').strip().lower()
                if action in ('d', 'defend'):
                    result = self.queue_action_for_player(selected_player.id, {
                        'action_type': 'defend_regiment',
                        'actor_id': regiment.id,
                    })
                    print(
                        f'Planned defensive stance for {regiment.symbol()}. '
                        f'Actions planned: {result["action_count"]}/{result["action_limit"]}.'
                    )
                    return
                if action not in ('a', 'attack'):
                    print('Action must be "attack" or "defend".')
                    return

                target_input = input('Enter target (R#, N#, C#, *C#, or exact name): ').strip()
                target = _resolve_attack_target(target_input, regiment.owner_id)
                if target['kind'] == 'regiment':
                    defending_regiment = target['entity']
                    result = self.queue_action_for_player(selected_player.id, {
                        'action_type': 'attack_regiment',
                        'actor_id': regiment.id,
                        'target_id': defending_regiment.id,
                    })
                    print(
                        f'Planned attack: {regiment.symbol()} -> {defending_regiment.symbol()}. '
                        f'Actions planned: {result["action_count"]}/{result["action_limit"]}.'
                    )
                else:
                    target_city = target['entity']
                    city_type = 'Capital' if target_city.is_capital else 'City'
                    result = self.queue_action_for_player(selected_player.id, {
                        'action_type': 'attack_city',
                        'actor_id': regiment.id,
                        'target_id': target_city.id,
                    })
                    print(
                        f'Planned attack: {regiment.symbol()} -> {city_type} {target_city.id} ({target_city.name}). '
                        f'Actions planned: {result["action_count"]}/{result["action_limit"]}.'
                    )
            except ValueError as error:
                print(error)

        def _parse_tile_coordinates(raw_value: str, label: str = 'Target tile'):
            parts = str(raw_value).strip().split()
            if len(parts) != 2:
                raise ValueError(f'{label} must be provided as two integers: x y')
            if not parts[0].lstrip('-').isdigit() or not parts[1].lstrip('-').isdigit():
                raise ValueError(f'{label} must be numeric coordinates.')
            return int(parts[0]), int(parts[1])

        def _build_split_counts(regiment: Regiment):
            split_counts = {}
            for unit_type in ('infantry', 'ranged', 'cavalry', 'siege', 'navy'):
                percent_raw = input(
                    f'Enter percent of {unit_type} to move into the split regiment '
                    f'(0-100, current={getattr(regiment, unit_type)}): '
                ).strip()
                try:
                    percent = float(percent_raw)
                except ValueError as error:
                    raise ValueError(f'{unit_type.capitalize()} split percent must be a number.') from error
                if percent < 0 or percent > 100:
                    raise ValueError(f'{unit_type.capitalize()} split percent must be between 0 and 100.')
                split_counts[unit_type] = math.floor(getattr(regiment, unit_type) * (percent / 100))
            return split_counts

        def split_regiment_action():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return

            regiment_input = input('Enter regiment/navy id or exact name to split: ').strip()
            try:
                regiment = _resolve_owned_regiment(regiment_input, selected_player.id)
                split_counts = _build_split_counts(regiment)
                print(
                    'New regiment composition: '
                    f"infantry={split_counts['infantry']}, ranged={split_counts['ranged']}, "
                    f"cavalry={split_counts['cavalry']}, siege={split_counts['siege']}, navy={split_counts['navy']}"
                )
                target_x, target_y = _parse_tile_coordinates(
                    input('Enter adjacent tile for the split regiment as x y: '),
                    label='Split tile',
                )
                default_name = f'{regiment.name} Detachment'
                new_regiment_name = input(
                    f'Enter split regiment name (default: {default_name}): '
                ).strip() or default_name
                split_regiment = self.map.split_regiment(
                    regiment.id,
                    target_x,
                    target_y,
                    split_counts,
                    new_name=new_regiment_name,
                )
                print(
                    f"Split {regiment.symbol()} and formed {split_regiment.symbol()} at ({target_x}, {target_y}). "
                    f'Movement remaining: {regiment.symbol()}={regiment.movement_remaining()}, '
                    f'{split_regiment.symbol()}={split_regiment.movement_remaining()}.'
                )
            except ValueError as error:
                print(error)

        def combine_regiments_action():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return

            source_input = input('Enter regiment/navy id or exact name to combine from: ').strip()
            target_input = input('Enter regiment/navy id or exact name to combine into: ').strip()
            try:
                source_regiment = _resolve_owned_regiment(source_input, selected_player.id)
                target_regiment = _resolve_owned_regiment(target_input, selected_player.id)
                combined_regiment = self.map.combine_regiments(source_regiment.id, target_regiment.id)
                print(
                    f'Combined {source_regiment.symbol()} into {combined_regiment.symbol()} at '
                    f'{self.map.get_regiment_location(combined_regiment.id)}. '
                    f'{combined_regiment.symbol()} kept its id and name and has '
                    f'{combined_regiment.movement_remaining()} movement remaining.'
                )
            except ValueError as error:
                print(error)

        def combine_or_split_regiment():
            action_menu = ConsoleMenu()
            action_menu.add_option('Split Regiment', split_regiment_action, 's')
            action_menu.add_option('Combine Regiments', combine_regiments_action, 'c')
            action_menu.add_option('Cancel', lambda: None, 'q')
            print('---COMBINE / SPLIT REGIMENT---')
            action_menu.prompt_and_select()

        def move_regiment():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return

            try:
                regiment = _resolve_owned_regiment(
                    input('Enter regiment/navy id or exact name to move: ').strip(),
                    selected_player.id,
                )
            except ValueError as error:
                print(error)
                return

            def move_regiment_absolute():
                try:
                    target_x, target_y = _parse_tile_coordinates(input('Enter target tile as x y: '))
                    result = self.queue_action_for_player(selected_player.id, {
                        'action_type': 'move_regiment',
                        'actor_id': regiment.id,
                        'target_pos': (target_x, target_y),
                    })
                    print(
                        f'Planned move for {regiment.symbol()} to ({target_x}, {target_y}). '
                        f'Actions planned: {result["action_count"]}/{result["action_limit"]}.'
                    )
                except ValueError as error:
                    print(error)

            def move_regiment_delta():
                try:
                    delta_x, delta_y = _parse_delta_coordinates(input('Enter movement delta as dx dy: '))
                    location = self.map.get_regiment_location(regiment.id)
                    if location is None:
                        raise ValueError(f'Regiment {regiment.id} is not on the map.')
                    target_pos = (location[0] + delta_x, location[1] + delta_y)
                    result = self.queue_action_for_player(selected_player.id, {
                        'action_type': 'move_regiment',
                        'actor_id': regiment.id,
                        'target_pos': target_pos,
                    })
                    print(
                        f'Planned move for {regiment.symbol()} by ({delta_x}, {delta_y}) to '
                        f'({target_pos[0]}, {target_pos[1]}). '
                        f'Actions planned: {result["action_count"]}/{result["action_limit"]}.'
                    )
                except ValueError as error:
                    print(error)

            action_menu = ConsoleMenu()
            action_menu.add_option('Move by Absolute Coordinates', move_regiment_absolute, 'a')
            action_menu.add_option('Move by Delta', move_regiment_delta, 'd')
            action_menu.add_option('Back', lambda: None, 'b')
            print('---MOVE REGIMENT---')
            action_menu.prompt_and_select()

        def print_visible_map():
            selected_player = self.get_selected_player()
            viewer_player_id = selected_player.id if selected_player is not None else None
            self.map.print(viewer_player_id=viewer_player_id)

        def print_visible_city_metadata():
            selected_player = self.get_selected_player()
            viewer_player_id = selected_player.id if selected_player is not None else None
            self.map.print_city_metadata(viewer_player_id=viewer_player_id)

        def print_regiment_metadata_by_id():
            selected_player = self.get_selected_player()
            regiment_id_raw = input('Enter regiment id to inspect: ').strip()
            if not regiment_id_raw.isdigit():
                print('Regiment id must be a positive integer.')
                return

            regiment_id = int(regiment_id_raw)
            regiment = self.map.get_regiment(regiment_id)
            if regiment is None:
                print(f'Regiment {regiment_id} does not exist.')
                return
            if (
                selected_player is not None and
                regiment.owner_id != selected_player.id and
                not self.map.is_regiment_visible_to_player(regiment.id, selected_player.id)
            ):
                print(f'Regiment {regiment_id} is not currently visible to your empire.')
                return
            self.map.print_regiment_metadata(regiment)

        def print_all_owned_regiments_metadata():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return
            try:
                self.print_owned_regiments_metadata(selected_player.id)
            except ValueError as error:
                print(error)

        def print_cards_in_hand():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return
            self.print_player_hand(selected_player.id)

        def print_planned_actions():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return
            self.print_player_planned_actions(selected_player.id)

        def _prompt_for_card_target_payload(selected_player: Player, card: Card):
            payload = {}
            target_scope = card.definition.target_scope

            if target_scope == 'own_regiment':
                regiment = _resolve_owned_regiment(
                    input('Enter friendly regiment/navy id or exact name to target: ').strip(),
                    selected_player.id,
                )
                payload['target_kind'] = 'regiment'
                payload['target_id'] = regiment.id
            elif target_scope == 'enemy_regiment':
                target = _resolve_attack_target(
                    input('Enter enemy regiment/navy target (R#, N#, or exact name): ').strip(),
                    selected_player.id,
                )
                if target['kind'] != 'regiment':
                    raise ValueError('This card must target an enemy regiment.')
                payload['target_kind'] = 'regiment'
                payload['target_id'] = target['entity'].id
            elif target_scope == 'own_city':
                city = _resolve_owned_city(
                    input('Enter friendly city id or exact name to target: ').strip(),
                    selected_player.id,
                )
                payload['target_kind'] = 'city'
                payload['target_id'] = city.id
            elif target_scope == 'enemy_city':
                target = _resolve_attack_target(
                    input('Enter enemy city target (C#, *C#, or exact name): ').strip(),
                    selected_player.id,
                )
                if target['kind'] != 'city':
                    raise ValueError('This card must target an enemy city.')
                payload['target_kind'] = 'city'
                payload['target_id'] = target['entity'].id
            elif target_scope == 'enemy_player':
                player_id_raw = input('Enter enemy player id to target: ').strip()
                if not player_id_raw.isdigit():
                    raise ValueError('Enemy player id must be a positive integer.')
                target_player_id = int(player_id_raw)
                target_player = self.map.get_player(target_player_id)
                if target_player is None:
                    raise ValueError(f'Player {target_player_id} does not exist.')
                if target_player.id == selected_player.id:
                    raise ValueError('You must target an opponent.')
                payload['target_kind'] = 'player'
                payload['target_id'] = target_player.id

            effect_types = {effect.effect_type for effect in card.definition.effects}
            if 'modify_regiment_units' in effect_types:
                unit_type = input('Choose unit type [infantry/ranged/cavalry/siege/navy]: ').strip().lower()
                if unit_type not in {'infantry', 'ranged', 'cavalry', 'siege', 'navy'}:
                    raise ValueError('Unit type must be infantry, ranged, cavalry, siege, or navy.')
                payload['unit_type'] = unit_type

            if 'gain_random_card_by_rarity' in effect_types:
                rarity_raw = input('Choose rarity [u]ncommon / [r]are / [l]egendary: ').strip().lower()
                rarity_lookup = {
                    'u': 'uncommon', 'uncommon': 'uncommon',
                    'r': 'rare', 'rare': 'rare',
                    'l': 'legendary', 'legendary': 'legendary',
                }
                if rarity_raw not in rarity_lookup:
                    raise ValueError('Rarity must be Uncommon, Rare, or Legendary.')
                payload['rarity'] = rarity_lookup[rarity_raw]

            if 'choose_from_top_cards' in effect_types:
                preview_count = next(
                    int(effect.magnitude)
                    for effect in card.definition.effects
                    if effect.effect_type == 'choose_from_top_cards'
                )
                preview_cards = self.preview_top_cards_for_player(selected_player.id, preview_count)
                if not preview_cards:
                    raise ValueError('There are no cards left in the deck to choose from.')
                print('TOP OF DECK:')
                for index, preview_card in enumerate(preview_cards, start=1):
                    print(f'  {index}. {preview_card.definition.name} [{preview_card.definition.rarity.title()}]')
                choice_raw = input(f'Select one of the top {len(preview_cards)} cards by number: ').strip()
                if not choice_raw.isdigit():
                    raise ValueError('Card choice must be a positive integer.')
                choice_index = int(choice_raw) - 1
                if choice_index < 0 or choice_index >= len(preview_cards):
                    raise ValueError(f'Card choice must be between 1 and {len(preview_cards)}.')
                payload['choice_index'] = choice_index

            if 'add_regiment_hero' in effect_types:
                hero_name = input('Enter hero name (leave empty for random): ').strip()
                if hero_name:
                    payload['hero_name'] = hero_name

            return payload

        def play_card_action():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return
            if self.turn <= self.card_unlock_turn:
                print(f'Cards cannot be played until after turn {self.card_unlock_turn}.')
                return
            if not selected_player.can_play_cards():
                print(f'{selected_player.name} is currently prevented from playing cards.')
                return
            if not selected_player.hand:
                print('There are no cards in your hand.')
                return
            if self.get_player_planned_action_count(selected_player.id) >= self.get_player_action_limit(selected_player.id):
                print(f'{selected_player.name} has already planned the maximum actions for this turn.')
                return
            if self.get_player_planned_card_count(selected_player.id) >= min(
                self.get_player_action_limit(selected_player.id),
                self.get_player_card_limit(selected_player.id),
            ):
                print(f'{selected_player.name} has already planned the maximum card plays for this turn.')
                return

            self.print_player_hand(selected_player.id)
            hand_selection = input('Enter the hand slot number to play: ').strip()
            if not hand_selection.isdigit():
                print('Hand slot must be a positive integer.')
                return

            hand_index = int(hand_selection) - 1
            if hand_index < 0 or hand_index >= len(selected_player.hand):
                print(f'Hand slot must be between 1 and {len(selected_player.hand)}.')
                return

            card = selected_player.hand[hand_index]
            try:
                payload = _prompt_for_card_target_payload(selected_player, card)
                result = self.queue_action_for_player(selected_player.id, {
                    'action_type': 'play_card',
                    'metadata': {
                        'card_instance_id': card.instance_id,
                        'card_name': card.definition.name,
                        'target_payload': payload,
                    },
                })
                print(
                    f'Planned card: {card.definition.name}. '
                    f'Actions planned: {result["action_count"]}/{result["action_limit"]} | '
                    f'cards planned: {result["card_count"]}/{result["card_limit"]}.'
                )
            except ValueError as error:
                print(error)

        def discard_card_action():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return
            if self.turn <= self.card_unlock_turn:
                print(f'Cards cannot be discarded until after turn {self.card_unlock_turn}.')
                return
            if not selected_player.hand:
                print('There are no cards in your hand.')
                return

            self.print_player_hand(selected_player.id)
            hand_selection = input('Enter the hand slot number to discard: ').strip()
            if not hand_selection.isdigit():
                print('Hand slot must be a positive integer.')
                return

            hand_index = int(hand_selection) - 1
            try:
                discard_result = self.discard_card_for_player(selected_player.id, hand_index)
                print(f'Discarded {discard_result["card"].definition.name}.')
            except ValueError as error:
                print(error)

        def advance_turn():
            self.end_human_turn()

        def player_loop():
            player_menu = ConsoleMenu()
            player_menu.add_option('Print Map', print_visible_map, 'm')
            player_menu.add_option('Print Players', self.map.print_player_metadata, 'p')
            player_menu.add_option('Print Cities/Capitals', print_visible_city_metadata, 'c')
            player_menu.add_option('View Cards', print_cards_in_hand, 'h')
            player_menu.add_option('View Planned Actions', print_planned_actions, 'l')
            player_menu.add_option('Play Card', play_card_action, 'y')
            player_menu.add_option('Buy Card', buy_card_action, 'k')
            player_menu.add_option('Discard Card', discard_card_action, 'd')
            player_menu.add_option('Build / Produce', create_regiment_order, 'r')
            player_menu.add_option('View Production Queue', print_regiment_build_queue_status, 'b')
            player_menu.add_option('Move Regiment', move_regiment, 'v')
            player_menu.add_option('Combine/Split Regiment', combine_or_split_regiment, 's')
            player_menu.add_option('Regiment Attack/Defend', regiment_attack_or_defend, 'a')
            player_menu.add_option('Recruit Hero', recruit_hero_action, 'e')
            player_menu.add_option('Refit Force', refit_force_action, 'f')
            player_menu.add_option('Inspect All Owned Regiments', print_all_owned_regiments_metadata, 'g')
            player_menu.add_option('Inspect Regiment By Id', print_regiment_metadata_by_id, 'i')
            player_menu.add_option('Next Turn', advance_turn, 't')
            player_menu.add_option('Quit to Main Menu', quit_to_main_menu, 'q')
            self.print_selected_player_round_summary()
            while self.player_in_loop:
                selected_player = self.get_selected_player()
                current_player = self.get_current_turn_player()
                print(f'Turn {self.turn}')
                if selected_player is not None:
                    print(f'Empire: {selected_player.name} (Player {selected_player.id})')
                    if current_player is not None:
                        print(f'Planning empire: {current_player.name} (Player {current_player.id})')
                    action_limit = self.get_player_action_limit(selected_player.id)
                    card_limit = min(action_limit, self.get_player_card_limit(selected_player.id))
                    influence_score = self.map.get_player_total_influence_score(selected_player.id)
                    print(
                        f'Influence={influence_score:.2f} | '
                        f'planned actions={self.get_player_planned_action_count(selected_player.id)}/{action_limit} | '
                        f'planned cards={self.get_player_planned_card_count(selected_player.id)}/{card_limit}'
                    )
                    print(f'Materials: {selected_player.materials_summary()}')
                    if selected_player.deck is not None:
                        print(
                            f'Cards: hand={len(selected_player.hand)}/{selected_player.hand_limit()} | '
                            f'deck={selected_player.deck.cards_remaining()} | '
                            f'discard={len(selected_player.deck.discard_pile)} | '
                            f'exhausted={len(selected_player.deck.exhausted_pile)}'
                        )
                print('---PLAYER OPTIONS---')
                player_menu.prompt_and_select()
                print('\n')

        main_menu = ConsoleMenu()
        main_menu.add_option('New Game', start_new_game, 'n')
        main_menu.add_option('Quit', lambda: setattr(self, 'is_running', False), 'q')

        while self.is_running:
            print('---MAIN MENU---')
            main_menu.prompt_and_select()
        # while(self.is_running):
        #     print(f'Turn {self.turn}:')
        #     print('The game is running. Continue? (y/n)')
        #     answer = input().strip().lower()
        #     if answer in ['y', 'yes']:
        #         self.turn += 1
        #         continue
        #     elif answer in ['n', 'no']:
        #         print('Exiting the game.')
        #         self.is_running = False
        #     else:
        #         print(f'"{answer}" is not a valid input.')

if __name__ == "__main__":
    # Clear the console to start
    os.system('cls' if os.name == 'nt' else 'clear')

    # Initialize and run the game
    game = Game()
    game.run()
