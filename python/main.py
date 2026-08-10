# main.py
import os
import sys
import math

class Player:

    def __init__(self):
        pass

class City:
    
    def __init__(self, id: int, name: str, owner_id: int, 
                 population: int = 1000, is_capital: bool = False):
        self.id = id
        self.name = name
        self.owner_id = owner_id
        self.population = population
        self.is_capital = is_capital

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

    def __init__(self):
        pass

class Map:

    def __init__(self, width: int = 10, height: int = 10,
                 default_tile: str = 'grass'):
        self.width = width
        self.height = height
        self.default_tile = default_tile
        self.tiles = {}

    def print(self):
        for y in range(self.height):
            for x in range(self.width):
                print(self.tiles[(x, y)].symbol, end=' ')
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

        for line in self.map_data.splitlines():
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            parts = line.split()
            if parts[0] == 'size' and len(parts) == 3:
                width, height = int(parts[1]), int(parts[2])
            elif parts[0] == 'default' and len(parts) == 2:
                default_type = parts[1]
            elif len(parts) == 3:
                x, y, tile_type = int(parts[0]), int(parts[1]), parts[2]
                explicit_tiles[(x, y)] = tile_type

        if width is None or height is None:
            raise ValueError('Map file missing required "size" directive')

        game_map = Map(width=width, height=height, default_tile=default_type)
        for y in range(height):
            for x in range(width):
                tile_type = explicit_tiles.get((x, y), default_type)
                game_map.tiles[(x, y)] = Tile(type=tile_type, x=x, y=y)

        return game_map

class Menu:

    def __init__(self):
        pass

class ConsoleMenu(Menu):

    def __init__(self):
        super().__init__()

class Game:

    def __init__(self, map = None):
        print('Game initialized.')
        self.map = map
        self.is_running = True
        self.turn = 0

    def run(self):
        while(self.is_running):
            print(f'Turn {self.turn}:')
            print('The game is running. Continue? (y/n)')
            answer = input().strip().lower()
            if answer in ['y', 'yes']:
                self.turn += 1
                continue
            elif answer in ['n', 'no']:
                print('Exiting the game.')
                self.is_running = False
            else:
                print(f'"{answer}" is not a valid input.')

if __name__ == "__main__":
    game = Game()
    game.run()
