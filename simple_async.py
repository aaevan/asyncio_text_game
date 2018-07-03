import asyncio
import sys
import select 
import tty 
import termios
from blessings import Terminal
from collections import defaultdict
from random import randint, choice, random
from math import sqrt

term = Terminal()

class Map_tile:
    """ holds the status and state of each tile. """
    def __init__(self, passable = True, tile=" "):
        """ create a new map tile, location is stored in map_dict"""
        self.passable = passable
        self.tile = tile
        self.actors = defaultdict(lambda:None)

class Actor:
    """ the representation of a single actor that lives on the map. """
    def __init__(self, x_coord = 0, y_coord = 0, speed = .2, turns_til_dead = None, tile="?"):
        """ create a new actor at position x, y """
        self.x_coord = x_coord
        self.y_coord = y_coord
        self.speed = speed
        self.turns_til_dead = turns_til_dead
        self.tile = tile

map_dict = defaultdict(lambda: Map_tile())
actor_dict = defaultdict(lambda: [None])

actor_dict['player'] = Actor(tile = "@")

def box_draw(top_left = (0, 0), x_size = 1, y_size = 1, filled = True, character = ".", passable = True):
    """ Draws a box at the given coordinates.o

    TODO: implement an unfilled box
    """
    x_tuple = (top_left[0], top_left[0] + x_size)
    y_tuple = (top_left[1], top_left[1] + y_size)
    for x in range(*x_tuple):
        for y in range(*y_tuple):
            map_dict[(x, y)] = Map_tile(tile=character, passable=passable)

def draw_line(coord_a = (0, 0), coord_b = (5, 5), palette = "%", passable = True):
    """draws a line to the map_dict connecting the two given points.
    """
    x1, y1 = coord_a
    x2, y2 = coord_b
    dx = x2 - x1
    dy = y2 - y1
    for x in range(x1, x2):
        y = y1 + dy * (x - x1) / dx
        map_dict[(int(x), int(y))].tile = choice(palette)
        map_dict[(int(x), int(y))].passable = passable

def sow_texture(root_x, root_y, palette = ",.'\"`", radius = 5, seeds = 20, passable = True):
    """ given a root node, picks random points within a radius length and writes
    characters from the given palette to their corresponding map_dict cell.
    """
    for i in range(seeds):
        throw = radius + 1
        while throw >= radius:
            x_toss = randint(-radius, radius)
            y_toss = randint(-radius, radius)
            throw = sqrt(x_toss**2 + y_toss**2) #euclidean distance
        toss_coord = (root_x + x_toss, root_y + y_toss)
        random_pick = choice(palette)
        map_dict[toss_coord].tile = random_pick
        map_dict[toss_coord].passable = passable

box_draw(top_left = (-10, -10), x_size = 5, y_size = 5, character = term.blue("#"))
box_draw(top_left = (-5, -5), x_size = 10, y_size = 10, character = ".")
box_draw(top_left = (5, 5), x_size = 10, y_size = 10, character = term.green("/"))
box_draw(top_left = (-15, 0), x_size = 3, y_size = 3, character = term.yellow("!"), passable = False)
sow_texture(10, 10, radius = 20, seeds = 200)
draw_line()
draw_line((-10, 15), (5, 3), palette = "111223", passable = False)

def isData(): ##
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []) ##

async def handle_input(key):
    """interpret keycodes and do various actions."""

    await asyncio.sleep(0)  
    x_shift = 0
    y_shift = 0
    x = actor_dict['player'].x_coord
    y = actor_dict['player'].y_coord
    directions = {'a':(-1, 0), 'd':(1, 0), 'w':(0, -1), 's':(0, 1)}
    x_shift, y_shift = directions[key]
    shifted_x = actor_dict['player'].x_coord + x_shift
    shifted_y = actor_dict['player'].y_coord + y_shift
    if map_dict[(shifted_x, shifted_y)].passable:
        actor_dict['player'].x_coord += x_shift
        actor_dict['player'].y_coord += y_shift
    return actor_dict['player'].x_coord, actor_dict['player'].y_coord

async def fuzzy_view_tile(x_offset = 1, y_offset = 1, threshhold = 100):
    """ handles displaying data from map_dict
    TODO: break tile or actor code from map_display out into separate function

    flickers in and out depending on how distant it is from player

    probability of showing new information (rather than grey last known state)
    is based on euclidean distance from player

    """
    #noise = "▓▒░░░░▖▗▘▙▚▛▜▝▞▟"
    noise = "          ▖▗▘▙▚▛▜▝▞▟"
    await asyncio.sleep(0)
    middle_x = int(term.width / 2 - 2) 
    middle_y = int(term.height / 2 - 2) 
    distance = sqrt(abs(x_offset)**2 + abs(y_offset)**2)
    actor = None
    while(1):
        await asyncio.sleep(.01)
        #await asyncio.sleep(distance/10) #changing delay by distance creates an expanding circle
        x = actor_dict['player'].x_coord + x_offset
        y = actor_dict['player'].y_coord + y_offset
        tile_key = (x, y)
        tile = map_dict[tile_key].tile
        if map_dict[tile_key].actors:
            map_dict_key = next(iter(map_dict[tile_key].actors))
            actor = actor_dict[map_dict_key].tile
        else:
            actor = None
        random_noise = choice(noise)
        flicker_state = randint(0, int(distance))
        print_location = (middle_x + x_offset, middle_y + y_offset)
        with term.location(*print_location):
            if flicker_state < threshhold:
                if actor:
                    print(actor)
                else:
                   print(tile)
            else:
                print(random_noise)

async def get_key(): 
    """the closest thing I could get to non-blocking input"""
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        while 1:
            await asyncio.sleep(0)
            if isData():
                key = sys.stdin.read(1)
                if key == 'x1b':  # x1b is ESC
                    break
                x, y = await handle_input(key)
            else:
                await asyncio.sleep(.01) ###
    finally: 
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings) 

"""
I need to figure out a way to have multiple behaviors and structures that can be inherited by
different actor coroutines.

a wanderer uses an actor to store their x and y coordinates,
    randomly wanders around

A seeker would move in a line towards the player.

a listener would display the status of an actor to the map_dict.
"""

async def wander(x_current, y_current, name_key):
    """ 
    randomly increments or decrements x_current and y_current
    if square to be moved to is passable
   
    TODO:implement movements to be made as a palette to be pulled from, using 0-9
    """
    await asyncio.sleep(0)
    x_move = randint(-1, 1)
    y_move = randint(-1, 1)
    next_move = (x_current + x_move, y_current + y_move)
    if map_dict[next_move].passable:
        x_current += randint(-1, 1)
        y_current += randint(-1, 1)
        actor_dict[(name_key)].x_coord = x_current
        actor_dict[(name_key)].y_coord = y_current
    return (x_current, y_current)

async def seek(name_key, seek_key):
    """TODO: pass as movement function just like wander
    Standardize format to pass movement function.
    """
    target_x = actor_dict[seek_key].x_coord
    target_y = actor_dict[seek_key].y_coord
    seek_coord = (target_x, target_y)

async def get_actor_coords(name_key):
    actor_x = actor_dict[name_key].x_coord
    actor_y = actor_dict[name_key].y_coord
    actor_coords = (actor_x, actor_y)
    return actor_coords

async def basic_actor(start_x = 0, start_y = 0, speed = .2, tile="*", 
        movement_function = wander, name_key = "test"):
    """ A coroutine that creates a randomly wandering '*' """
    actor_dict[(name_key)] = Actor(x_coord=start_x, y_coord=start_y, speed=speed, tile=tile)
    actor_dict[(name_key)].x_coord = start_x
    actor_dict[(name_key)].y_coord = start_y
    coords = await get_actor_coords(name_key)
    while 1:
        await asyncio.sleep(speed)
        if name_key in map_dict[coords].actors:
            del map_dict[coords].actors[name_key]
        coords = await movement_function(*coords, name_key)
        map_dict[coords].actors[name_key] = name_key

async def tracker(actor_key = None):
    """follows the position of an actor and writes their presence to the map."""
    pass

def main():
    old_settings = termios.tcgetattr(sys.stdin) ##
    loop = asyncio.new_event_loop()
    loop.create_task(get_key())
    for x in range(-15,15):
        for y in range(-15, 15):
            loop.create_task(fuzzy_view_tile(x_offset = x, y_offset = y))
    titles = ["A", "B", "C", "D", "E", "F"]
    for title in titles:
        loop.create_task(basic_actor(start_x = 5, start_y = 5, speed = .2, movement_function = wander, tile = title, name_key = "w"+title))
    loop.create_task(basic_actor(start_x = 0, start_y = 5))
    asyncio.set_event_loop(loop)
    result = loop.run_forever()


with term.hidden_cursor():
    main()
