# main.py
import os
import sys
import math
import random
from pathlib import Path
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

class Player:

    def __init__(self, id: int, name: str, color: str):
        self.id = id
        self.name = name
        self.color = color

class City:

    _city_symbols = {'City': 'C', 'Capital': '*C'}
    
    def __init__(self, id: int, name: str, owner_id: int, 
                 population: int = 1000, is_capital: bool = False,
                 defense_score: float = None):
        self.id = id
        self.name = name
        self.owner_id = owner_id
        self.population = population
        self.is_capital = is_capital
        self.defense_score = defense_score if defense_score is not None else self._default_defense_score()
        self.symbol = f'C{self.id}({self.owner_id})' if not is_capital else f'*C{self.id}({self.owner_id})'

    def mark_as_capital(self):
        self.is_capital = True
        self.symbol = f'*C{self.id}({self.owner_id})'
        self.defense_score = self._default_defense_score()

    def _default_defense_score(self):
        # Population and capital status provide a simple defensive baseline.
        return round(20 + (self.population / 200) + (10 if self.is_capital else 0), 2)

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
                 resource_id: int = None):
        if type not in Tile._allowable_types.keys():
            raise ValueError(f'Invalid tile type: {type}')
        self.type = type
        self.x = x
        self.y = y
        self.regiment_id = regiment_id
        self.city_id = city_id
        self.resource_id = resource_id
        self.passable_foot = self._allowable_types[type]['passable_foot']
        self.passable_water = self._allowable_types[type]['passable_water']
        self.symbol = self._allowable_types[type]['symbol']

class Card:

    def __init__(self):
        pass

class Regiment:

    REGIMENT_ATTACK_WEIGHTS = {
        'infantry': 1.0,
        'ranged': 0.85,
        'cavalry': 1.15,
    }

    CITY_ATTACK_WEIGHTS = {
        'infantry': 0.8,
        'ranged': 0.7,
        'cavalry': 0.6,
        'siege': 1.6,
    }

    def __init__(self, id: int = None, name: str = 'Unnamed Regiment', owner_id: int = None,
                 infantry: int = 0, ranged: int = 0, cavalry: int = 0,
                 siege: int = 0, heroes: list[str] = None):
        self.id = id
        self.name = name
        self.owner_id = owner_id
        self.infantry = self._validate_unit_count(infantry, 'infantry')
        self.ranged = self._validate_unit_count(ranged, 'ranged')
        self.cavalry = self._validate_unit_count(cavalry, 'cavalry')
        self.siege = self._validate_unit_count(siege, 'siege')
        self.heroes = list(heroes) if heroes is not None else []

        self.regiment_attack_score = 0.0
        self.city_attack_score = 0.0
        self.recalculate_attack_scores()

    def _validate_unit_count(self, value: int, unit_type: str):
        if not isinstance(value, int) or value < 0:
            raise ValueError(f'{unit_type} count must be a non-negative integer')
        return value

    def total_units(self):
        return self.infantry + self.ranged + self.cavalry + self.siege

    def hero_count(self):
        return len(self.heroes)

    def update_composition(self, infantry: int = None, ranged: int = None,
                           cavalry: int = None, siege: int = None):
        if infantry is not None:
            self.infantry = self._validate_unit_count(infantry, 'infantry')
        if ranged is not None:
            self.ranged = self._validate_unit_count(ranged, 'ranged')
        if cavalry is not None:
            self.cavalry = self._validate_unit_count(cavalry, 'cavalry')
        if siege is not None:
            self.siege = self._validate_unit_count(siege, 'siege')
        self.recalculate_attack_scores()

    def add_hero(self, hero_name: str):
        normalized_name = str(hero_name).strip()
        if not normalized_name:
            raise ValueError('Hero name must be a non-empty string')
        self.heroes.append(normalized_name)
        self.recalculate_attack_scores()

    def symbol(self):
        return f'R{self.id}({self.owner_id})'

    def movement_range(self):
        # Larger and stronger regiments move less distance per turn.
        movement = 8 - (self.total_units() / 25) - (self.regiment_attack_score / 120)
        return max(1, int(round(movement)))

    def recalculate_attack_scores(self):
        self.regiment_attack_score = self._compute_weighted_score(
            self.REGIMENT_ATTACK_WEIGHTS,
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
        return round((total_weighted_units / total_units) * hero_bonus * 100, 2)

class Map:

    def __init__(self, width: int = 10, height: int = 10,
                 default_tile: str = 'grass'):
        self.width = width
        self.height = height
        self.default_tile = default_tile
        self.tiles = {}
        self.players: dict[int, Player] = {}
        self.cities: dict[int, City] = {}
        self.regiments: dict[int, Regiment] = {}
        self.regiment_movement_used: dict[int, int] = {}
        self.next_regiment_id = 1

    def add_player(self, player: Player):
        self.players[player.id] = player

    def add_city(self, city: City):
        if city.owner_id not in self.players:
            raise ValueError(f'City {city.id} references missing player {city.owner_id}')
        self.cities[city.id] = city

    def get_player(self, player_id: int):
        return self.players.get(player_id)

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

    def add_regiment(self, regiment: Regiment, x: int, y: int):
        if regiment.owner_id not in self.players:
            raise ValueError(f'Regiment owner {regiment.owner_id} does not exist')
        if (x, y) not in self.tiles:
            raise ValueError(f'Tile ({x}, {y}) is out of bounds')
        tile = self.tiles[(x, y)]
        if tile.regiment_id is not None:
            raise ValueError(f'Tile ({x}, {y}) already has a regiment')
        if not tile.passable_foot:
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
        if not target_tile.passable_foot:
            raise ValueError(f'Target tile ({target_x}, {target_y}) is not passable for land regiments')

        delta_x = abs(target_x - start[0])
        delta_y = abs(target_y - start[1])
        distance = max(delta_x, delta_y)
        max_distance = regiment.movement_range()
        used_distance = self.regiment_movement_used.get(regiment_id, 0)
        remaining_distance = max_distance - used_distance
        if distance > remaining_distance:
            raise ValueError(
                f'Regiment {regiment_id} can move at most {remaining_distance} more tiles this turn '
                f'({used_distance}/{max_distance} used)'
            )

        self.tiles[start].regiment_id = None
        target_tile.regiment_id = regiment_id
        self.regiment_movement_used[regiment_id] = used_distance + distance

    def reset_regiment_movement(self):
        self.regiment_movement_used.clear()

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
        print(f'  id={regiment.id} | name={regiment.name} | owner={owner_name} | location={location_text}')
        print(f'  composition: infantry={regiment.infantry}, ranged={regiment.ranged}, cavalry={regiment.cavalry}, siege={regiment.siege}, heroes={regiment.hero_count()}')
        print(f'  scores: vs_regiment={regiment.regiment_attack_score}, vs_city={regiment.city_attack_score} | move_range={regiment.movement_range()}')
        if regiment.heroes:
            print(f'  heroes: {", ".join(regiment.heroes)}')
        print('')

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
        normalized = str(player_color).strip().lower().replace('_', '').replace('-', '')
        return color_map.get(normalized, '')

    def print(self):
        # Get the max character length for each column of the map for proper alignment
        col_widths = []
        for x in range(self.width):
            col_width = 0
            for y in range(self.height):
                tile = self.tiles[(x, y)]
                city = self.get_city(tile.city_id) if tile.city_id is not None else None
                regiment = self.get_regiment(tile.regiment_id) if tile.regiment_id is not None else None
                if regiment is not None:
                    symbol = regiment.symbol()
                elif city is not None:
                    symbol = city.symbol
                else:
                    symbol = tile.symbol
                col_width = max(col_width, len(symbol))
            col_widths.append(col_width)

        # Print the map
        print(f'\nMAP:')
        for y in range(self.height):
            for x in range(self.width):
                tile = self.tiles[(x, y)]
                city = self.get_city(tile.city_id) if tile.city_id is not None else None
                regiment = self.get_regiment(tile.regiment_id) if tile.regiment_id is not None else None
                if regiment is not None:
                    symbol = regiment.symbol()
                elif city is not None:
                    symbol = city.symbol
                else:
                    symbol = tile.symbol
                display_symbol = symbol.center(col_widths[x])
                if regiment is not None:
                    owner = self.get_player(regiment.owner_id)
                    color_code = self._get_player_color_code(owner.color) if owner is not None else ''
                    if color_code:
                        display_symbol = f'{color_code}{display_symbol}{Style.RESET_ALL}'
                elif city is not None:
                    owner = self.get_player(city.owner_id)
                    color_code = self._get_player_color_code(owner.color) if owner is not None else ''
                    if color_code:
                        display_symbol = f'{color_code}{display_symbol}{Style.RESET_ALL}'
                print(display_symbol, end=' ')
            print('')

        # Print the legend
        legend_entries = [f"{t}={Tile._allowable_types[t]['symbol']}" \
                          for t in Tile._allowable_types.keys()]
        for s in City._city_symbols:
            legend_entries.append(f'{s}={City._city_symbols[s]}')
        legend_entries.append('Regiment=R<id>(owner_id)')
        print('-----\nLEGEND:')
        for l in legend_entries:
            print(l, end='; ') if l != legend_entries[-1] else print(l)
        print('\n')

    def print_player_metadata(self):
        if not self.players:
            print('No player metadata is loaded.')
            return

        print('PLAYERS:')
        for player in self.players.values():
            color_code = self._get_player_color_code(player.color)
            player_text = f'P{player.id}: {player.name} ({player.color})'
            if color_code:
                player_text = f'{color_code}{player_text}{Style.RESET_ALL}'
            print(f'  {player_text}')
        print('')

    def print_city_metadata(self):
        if not self.cities:
            print('No city metadata is loaded.')
            return

        print('CITIES:')
        for city in self.cities.values():
            city_type = 'Capital' if city.is_capital else 'City'
            owner = self.get_player(city.owner_id)
            owner_name = owner.name if owner is not None else f'Unknown({city.owner_id})'
            owner_color = self._get_player_color_code(owner.color) if owner is not None else ''
            if owner_color:
                owner_name = f'{owner_color}{owner_name}{Style.RESET_ALL}'
            location = self.get_city_location(city.id)
            location_text = f'({location[0]}, {location[1]})' if location is not None else 'UNPLACED'
            print(f'  {city_type} {city.id}: {city.name} | owner={owner_name} | population={city.population} | defense={city.defense_score} | location={location_text}')
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

class Game:

    def __init__(self, map = None):
        print('Game initialized.')
        self.map = map
        self.is_running = True
        self.player_in_loop = False
        self.turn = 0
        self.regiment_build_queue = []

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
                self.player_in_loop = True
                player_loop()
                return

        def quit_to_main_menu():
            print('Are you sure you want to quit to the main menu? (y/n)')
            answer = input().strip().lower()
            if answer in ['y', 'yes']:
                self.player_in_loop = False
            else:
                print('Continuing the game.')

        def _determine_regiment_build_turns(city: City):
            return max(1, min(6, math.ceil(3000 / max(city.population, 1))))

        def _create_random_regiment_for_city(city: City, owner_id: int, regiment_name: str):
            total_units = max(8, city.population // 45 + random.randint(0, max(3, city.population // 200)))
            infantry = random.randint(total_units // 4, total_units // 2)
            remaining = total_units - infantry
            ranged = random.randint(0, remaining)
            remaining -= ranged
            cavalry = random.randint(0, remaining)
            siege = remaining - cavalry
            heroes = [f'Hero_{random.randint(1, 999)}'] if random.random() < 0.35 else []
            return Regiment(
                name=regiment_name,
                owner_id=owner_id,
                infantry=infantry,
                ranged=ranged,
                cavalry=cavalry,
                siege=siege,
                heroes=heroes,
            )

        def process_regiment_build_queue():
            if not self.regiment_build_queue:
                return

            completed_orders = []
            for order in self.regiment_build_queue:
                order['turns_remaining'] -= 1
                if order['turns_remaining'] > 0:
                    continue

                city = self.map.get_city(order['city_id'])
                city_location = self.map.get_city_location(order['city_id'])
                if city is None or city_location is None:
                    print(f"Build order canceled: City {order['city_id']} no longer has a valid location.")
                    completed_orders.append(order)
                    continue

                try:
                    regiment = _create_random_regiment_for_city(
                        city=city,
                        owner_id=order['owner_id'],
                        regiment_name=order['regiment_name'],
                    )
                    self.map.add_regiment(regiment, city_location[0], city_location[1])
                    print(f'Regiment formed: {regiment.symbol()} at city {city.name}.')
                    completed_orders.append(order)
                except ValueError as error:
                    # If the spawn tile is blocked, keep trying next turn.
                    print(f"Build order delayed for city {city.id}: {error}")
                    order['turns_remaining'] = 1

            self.regiment_build_queue = [o for o in self.regiment_build_queue if o not in completed_orders]

        def create_regiment_order():
            city_id_raw = input('Enter city id to spawn regiment from: ').strip()
            if not city_id_raw.isdigit():
                print('City id must be a positive integer.')
                return

            city_id = int(city_id_raw)
            city = self.map.get_city(city_id)
            if city is None:
                print(f'City {city_id} does not exist.')
                return

            owner = self.map.get_player(city.owner_id)
            owner_name = owner.name if owner is not None else f'Unknown({city.owner_id})'
            default_name = f'{city.name} Guard'
            regiment_name = input(f'Enter regiment name (default: {default_name}): ').strip() or default_name

            turns_to_build = _determine_regiment_build_turns(city)
            self.regiment_build_queue.append({
                'city_id': city.id,
                'owner_id': city.owner_id,
                'regiment_name': regiment_name,
                'turns_remaining': turns_to_build,
            })
            print(f"Queued regiment '{regiment_name}' for {owner_name} from {city.name}. Ready in {turns_to_build} turn(s).")

        def move_regiment():
            regiment_id_raw = input('Enter regiment id to move: ').strip()
            if not regiment_id_raw.isdigit():
                print('Regiment id must be a positive integer.')
                return
            regiment_id = int(regiment_id_raw)
            regiment = self.map.get_regiment(regiment_id)
            if regiment is None:
                print(f'Regiment {regiment_id} does not exist.')
                return

            target_raw = input('Enter target tile as x y: ').strip().split()
            if len(target_raw) != 2:
                print('Target must be provided as two integers: x y')
                return
            if not target_raw[0].lstrip('-').isdigit() or not target_raw[1].lstrip('-').isdigit():
                print('Target must be numeric coordinates.')
                return
            target_x, target_y = int(target_raw[0]), int(target_raw[1])

            try:
                self.map.move_regiment(regiment_id, target_x, target_y)
                print(f'Moved {regiment.symbol()} to ({target_x}, {target_y}).')
            except ValueError as error:
                print(error)

        def print_regiment_metadata_at_tile():
            target_raw = input('Enter tile to inspect as x y: ').strip().split()
            if len(target_raw) != 2:
                print('Tile must be provided as two integers: x y')
                return
            if not target_raw[0].lstrip('-').isdigit() or not target_raw[1].lstrip('-').isdigit():
                print('Tile must be numeric coordinates.')
                return
            target_x, target_y = int(target_raw[0]), int(target_raw[1])
            regiment = self.map.get_regiment_at(target_x, target_y)
            if regiment is None:
                print(f'No regiment found at ({target_x}, {target_y}).')
                return
            self.map.print_regiment_metadata(regiment)

        def advance_turn():
            self.turn += 1
            self.map.reset_regiment_movement()
            process_regiment_build_queue()
            self.map.print()

        def player_loop():
            player_menu = ConsoleMenu()
            player_menu.add_option('Print Map', self.map.print, 'm')
            player_menu.add_option('Print Players', self.map.print_player_metadata, 'p')
            player_menu.add_option('Print Cities/Capitals', self.map.print_city_metadata, 'c')
            player_menu.add_option('Create Regiment', create_regiment_order, 'r')
            player_menu.add_option('Move Regiment', move_regiment, 'v')
            player_menu.add_option('Inspect Regiment At Tile', print_regiment_metadata_at_tile, 'i')
            player_menu.add_option('Next Turn', advance_turn, 't')
            player_menu.add_option('Quit to Main Menu', quit_to_main_menu, 'q')
            advance_turn()  # Print the map at the start of the player loop
            while self.player_in_loop:
                print(f'Turn {self.turn}')
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
