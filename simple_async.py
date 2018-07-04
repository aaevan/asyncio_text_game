import asyncio
import sys
import select 
import tty 
import termios
from blessings import Terminal
from collections import defaultdict
from random import randint, choice, random, shuffle
from math import sqrt
from subprocess import call
import os

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

#Drawing functions---------------------------------------------------------------------------------

def draw_box(top_left = (0, 0), x_size = 1, y_size = 1, filled = True, character = ".", passable = True):
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

async def flood_fill(coord = (0, 0), target = '/', replacement = ' ', depth = 0, max_depth = 10, random = False):
    """ Algorithm from wikipedia 
    figure out how to still allow player movement after it has started.
    figure out how to end a coroutine.
    """
    await asyncio.sleep(0)
    if depth == max_depth:
        return
    if map_dict[coord].tile == replacement:
        return
    if map_dict[coord].tile != target:
        return
    map_dict[coord].tile = replacement
    args = (target, replacement, depth + 1, max_depth, random)
    coord_dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    if random:
        shuffle(coord_dirs)
    for direction in coord_dirs:
        await flood_fill((coord[0] + direction[0], coord[1] + direction[1]), *args)

async def palette_keys(key):
    """ when a key is pressed, store the value of the current map tile for use in other drawing functions"""

def clear():
    # check and make call for specific operating system
    _ = call('clear' if os.name =='posix' else 'cls')

def map_init():
    clear()
    draw_box(top_left = (-10, -10), x_size = 5, y_size = 5, character = term.blue("#"))
    draw_box(top_left = (-5, -5), x_size = 10, y_size = 10, character = ".")
    draw_box(top_left = (5, 5), x_size = 10, y_size = 10, character = term.green("/"))
    draw_box(top_left = (-15, 0), x_size = 3, y_size = 3, character = term.yellow("!"), passable = False)
    sow_texture(10, 10, radius = 20, seeds = 200)
    sow_texture(30, 30, radius = 20, seeds = 200)
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
    directions = {'a':(-1, 0), 'd':(1, 0), 'w':(0, -1), 's':(0, 1), 
            'A':(-10, 0), 'D':(10, 0), 'W':(0, -10), 'S':(0, 10),}
    if key in directions:
        x_shift, y_shift = directions[key]
    shifted_x = actor_dict['player'].x_coord + x_shift
    shifted_y = actor_dict['player'].y_coord + y_shift
    if key == 'Ff':
        await flood_fill((x, y), target = map_dict[(x, y)].tile, replacement = '*', random = True)
    if key in 'Vv':
        asyncio.ensure_future(vine_grow(start_x = x, start_y = y)),
    if map_dict[(shifted_x, shifted_y)].passable:
        actor_dict['player'].x_coord += x_shift
        actor_dict['player'].y_coord += y_shift
    return actor_dict['player'].x_coord, actor_dict['player'].y_coord

async def view_tile(x_offset = 1, y_offset = 1):
    """ handles displaying data from map_dict """
    await asyncio.sleep(random()/10)
    middle_x = int(term.width / 2 - 2) 
    middle_y = int(term.height / 2 - 2) 
    previous_actor = None
    previous_tile = None
    actor = None
    while(1):
        await asyncio.sleep(1/1000)
        x = actor_dict['player'].x_coord + x_offset
        y = actor_dict['player'].y_coord + y_offset
        tile_key = (x, y)
        tile = map_dict[tile_key].tile
        if map_dict[tile_key].actors:
            map_dict_key = next(iter(map_dict[tile_key].actors))
            actor = actor_dict[map_dict_key].tile
        else:
            actor = None
        if actor == previous_actor and tile == previous_tile:
            continue
        print_location = (middle_x + x_offset, middle_y + y_offset)
        with term.location(*print_location):
            if actor:
                print(actor)
            else:
               print(tile)
        previous_tile = tile
        previous_actor = actor

async def noise_tile(x_offset, y_offset, threshhold = 10):
    """ breaks out noisy tile code into a separate routine 

    flickers in and out depending on how distant it is from player

    probability of showing new information (rather than grey last known state)
    is based on euclidean distance from player
    """
    pass
    #noise = "▓▒░░░░▖▗▘▙▚▛▜▝▞▟"
    #noise = "          ▖▗▘▙▚▛▜▝▞▟"
    #distance = sqrt(abs(x_offset)**2 + abs(y_offset)**2) #
    #await asyncio.sleep(distance/10) #changing delay by distance creates an expanding circle
    #random_noise = choice(noise)
    #flicker_state = randint(0, int(distance))
    #if flicker_state < threshhold:
    #else:
    #print(random_noise)

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

async def constant_update_tile(x_offset = 0, y_offset = 0, tile = term.red('@')):
    await asyncio.sleep(1/30)
    middle_x = int(term.width / 2 - 2) 
    middle_y = int(term.height / 2 - 2) 
    while(1):
        await asyncio.sleep(1/30)
        with term.location(middle_x, middle_y):
            print(tile)

async def tracker(actor_key = None):
    """follows the position of an actor and writes their tile to the map."""
    pass

async def vine_grow(start_x = -10, start_y = -10, actor_key = "vine", rate = .01, death_clock = 100):
    """grows a vine starting at a particular tile. Doesn't know about anything else."""
    await asyncio.sleep(rate)
    current_coord = (start_x, start_y)
    vine_picks = {(1, 2):'┌', (4, 3):'┌', (2, 3):'┐', (1, 4):'┐', (1, 1):'│', (3, 3):'│', 
            (3, 4):'┘', (2, 1):'┘', (3, 2):'└', (4, 1):'└', (2, 2):'─', (4, 4):'─', }
    prev_dir = randint(1, 4)
    next_dir = randint(1, 4)
    movement_tuples = {1:(0, -1), 2:(1, 0), 3:(0, 1), 4:(-1, 0)}
    next_tuple = movement_tuples[next_dir]
    exclusions = {(2, 4), (4, 2), (1, 3), (3, 1), }
    vines = [term.green(i) for i in "┌┐└┘─│"]
    while(1):
        await asyncio.sleep(rate)
        next_dir = randint(1, 4)
        while (prev_dir, next_dir) in exclusions:
            next_dir = randint(1, 4)
        next_tuple = movement_tuples[next_dir]
        vine_tile = vine_picks[(prev_dir, next_dir)]
        if map_dict[current_coord].tile not in vines:
            map_dict[current_coord].tile = term.green(vine_tile)
        current_coord = (current_coord[0] + next_tuple[0], current_coord[1] + next_tuple[1])
        prev_dir = next_dir
        death_clock -= 1
        if death_clock <= 0:
            break

def main():
    map_init()
    old_settings = termios.tcgetattr(sys.stdin) ##
    loop = asyncio.new_event_loop()
    loop.create_task(get_key())
    for x in range(-15,15):
        for y in range(-15, 15):
            loop.create_task(view_tile(x_offset = x, y_offset = y))
    titles = ["A", "B", "C", "D", "E", "F"]
    for title in titles:
        start_coord = (5, 5)
        loop.create_task(basic_actor(*start_coord, speed = .05, movement_function = wander,
                tile = title, name_key = "w"+title))
    loop.create_task(constant_update_tile())
    loop.create_task(basic_actor(start_x = 0, start_y = 5))
    loop.create_task(vine_grow())
    asyncio.set_event_loop(loop)
    result = loop.run_forever()


with term.hidden_cursor():
    main()
