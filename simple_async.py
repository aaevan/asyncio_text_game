import asyncio
import sys
import select 
import tty 
import termios
from blessings import Terminal
from collections import defaultdict
from random import randint

term = Terminal()

class Map_tile:
    """ holds the status and state of each tile. """

    def __init__(self, passable = True, tile=" ", actors = {}):
        """ create a new map tile, location is stored in map_dict"""
        self.passable = passable
        self.tile = tile
        #self.light_level = 0

class Actor:
    """ the representation of a single actor that lives on the map. """
    def __init__(self, x_coord = 0, y_coord = 0, turns_til_dead = None, tile="?"):
        """ create a new actor at position x, y """
        self.x_coord = x_coord
        self.y_coord = y_coord
        self.turns_til_dead = turns_til_dead
        self.tile = tile

#map_dict = defaultdict(lambda: [' ']) #old one
map_dict = defaultdict(lambda: Map_tile()) #new
#actor_dict = defaultdict(lambda: [None]

for x in range(-5, 6):
    for y in range(-5, 6):
        #the lowest level scenery on the tile is index 0.
        map_dict[(x, y)] = Map_tile(tile = "_")

def show_key(key):
    txt.set_text(repr(key))

def isData(): ##
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []) ##

async def handle_input(key, x, y):
    """interpret keycodes and do various actions.

    Right now it's just movement. Considering keys to spawn new wanderers.
    """
    await asyncio.sleep(0)  
    if key == 'a':   
        x -= 1
    if key == 'd':  
        x += 1
    if key == 'w': 
        y -= 1
    if key == 's':
        y += 1
    return x, y

async def fuzzy_view_tile():
    """
    handles displaying data from map_dict

    flickers in and out depending on how distant it is from player

    probability of showing new information (rather than grey last known state)
    is based on euclidean distance from player
    """
    pass

async def get_key(): ##
    """ the closest thing I could get to non-blocking input

    currently contains messy map display code
    """
    old_settings = termios.tcgetattr(sys.stdin)
    #TODO: figure out resizing and auto-centering of @ in terminal
    #rows, columns = os.popen('stty size', 'r').read().split()
    #middle_x = int(int(rows)/2)
    #middle_y = int(int(columns)/2)
    middle_x = term.width 
    middle_y = term.height
    try:
        tty.setcbreak(sys.stdin.fileno())
        x = 0
        y = 0
        while 1:
            await asyncio.sleep(0)  
            if isData():
                key = sys.stdin.read(1)
                if key == 'x1b':  # x1b is ESC
                    break
                x, y = await handle_input(key, x, y)
            else:
                await asyncio.sleep(0)
            #map display code start:
            for x_shift in range(-20, 21):
                for y_shift in range(-20, 21):
                    if x_shift == 0 and y_shift == 0:
                        continue
                    x_coord = middle_x + x_shift
                    y_coord = middle_y + y_shift
                    with term.location(x_coord, y_coord):
                        print(map_dict[(x + x_shift, y + y_shift)].tile)
            #map display code end

            with term.location(middle_x, middle_y):
                print(term.red("@"))
            with term.location(0, 0):
                print(x_coord, y_coord)
    finally: 
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings) 

async def wanderer(start_x, start_y, speed, character="*"):
    """ A coroutine that creates a randomly wandering '*'

    TODO: figure out how to not leave a trail and/or poll from a list of actors 
    instead of writing to the map dicitionary
    """
    #old_value = map_dict[(start_x, start_y)][-1]
    old_value = map_dict[(start_x, start_y)].tile
    map_dict[(start_x, start_y)].tile = character
    x = start_x
    y = start_y
    while 1:
        await asyncio.sleep(speed)
        map_dict[(x, y)].tile = old_value
        x += randint(-1,1)
        y += randint(-1,1)
        old_value = map_dict[(x, y)].tile
        map_dict[(x, y)].tile = character

def main():
    old_settings = termios.tcgetattr(sys.stdin) ##
    loop = asyncio.new_event_loop()

    loop.create_task(get_key())
    loop.create_task(wanderer(5, 5, .2, character = "a"))
    loop.create_task(wanderer(5, 5, .2, character = "b"))
    asyncio.set_event_loop(loop)
    result = loop.run_forever()
    
main()
