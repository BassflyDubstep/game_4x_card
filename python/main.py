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

    allowable_types = {
        'grass': {'passable_foot': True, 'passable_water': False}, 
        'water': {'passable_foot': False, 'passable_water': True}, 
        'mountain': {'passable_foot': False, 'passable_water': False}, 
        'forest': {'passable_foot': True, 'passable_water': False}, 
        'hill': {'passable_foot': True, 'passable_water': False}
    }

    def __init__(self, type: str = 'grass', regiment_id: int = None, 
                 city_id: int = None, resource_id: int = None):
        if type not in Tile.allowable_types.keys():
            raise ValueError(f'Invalid tile type: {type}')
        self.type = type
        self.regiment_id = regiment_id
        self.city_id = city_id
        self.resource_id = resource_id

class Card:

    def __init__(self):
        pass

class Regiment:

    def __init__(self):
        pass

class Map:

    def __init__(self, width: int = 10, height: int = 10):
        self.width = width
        self.height = height

class MapLoader:
    
    def __init__(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as map_file:
            self.map_data = map_file.read()

    def parse_map(self):
        # Placeholder for map parsing logic
        return Map()

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
