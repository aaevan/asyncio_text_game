import asyncio
import sys
import select 
import tty 
import termios
from blessings import Terminal
from collections import defaultdict
from datetime import datetime
from random import randint, choice, random, shuffle
from math import acos, cos, degrees, pi, radians, sin, sqrt
from itertools import cycle
from subprocess import call
from time import sleep #hack to prevent further input/freeze screen on player death
import os

#Class definitions--------------------------------------------------------------
class Map_tile:
    """ holds the status and state of each tile. """
    def __init__(self, passable=True, tile="▓", blocking=True, 
                 description='', announcing=False, seen=False, 
                 announcement="", distance_trigger=None, is_animated=False,
                 animation="", actors=None, items=None, 
                 magic=False, magic_destination=False):
        """ create a new map tile, location is stored in map_dict
        actors is a dictionary of actor names with value == True if 
                occupied by that actor, otherwise the key is deleted.
                TODO: replace with a set that just lists actor_ids
        contains_items is a set that lists item_ids which the player or
                other actors may draw from.
        """
        self.tile, self.passable, self.blocking = (tile, passable, blocking)
        self.description = description
        self.announcing, self.seen, self.announcement = announcing, seen, announcement
        self.distance_trigger = distance_trigger
        if not actors:
            self.actors = defaultdict(lambda:None)
        #allows for new map_tiles to be initialized with an existing actor list
        else:
            self.actors = actors
        self.items = defaultdict(lambda:None)
        self.is_animated, self.animation = is_animated, animation
        self.magic, self.magic_destination = magic, magic_destination

class Actor:
    """ the representation of a single actor that lives on the map. """
    def __init__(self, x_coord=0, y_coord=0, speed=.2, tile="?", strength=1, 
                 health=50, hurtful=True, moveable=True, is_animated=False,
                 animation="", holding_items={}, leaves_body=False):
        """ create a new actor at position x, y 
        actors hold a number of items that are either used or dropped upon death"""
        self.x_coord, self.y_coord, = (x_coord, y_coord)
        self.speed, self.tile = (speed, tile)
        self.coord = (x_coord, y_coord)
        self.strength, self.health, self.hurtful = strength, health, hurtful
        self.max_health = self.health #max health is set to original value
        self.alive = True
        self.moveable = moveable
        self.is_animated = is_animated
        self.animation = animation
        self.holding_items = holding_items
        self.leaves_body = leaves_body

    def update(self, x, y):
        self.x_coord, self.y_coord = x, y

    def coords(self):
        return (self.x_coord, self.y_coord)

    def move_by(self, coord_move=None, x_move=None, y_move=None):
        if x_move:
            self.x_coord = self.x_coord + x_move
        if y_move:
            self.y_coord = self.y_coord + y_move
        if coord_move:
            self.x_coord, self.y_coord = self.x_coord + coord_move[0], self.y_coord + coord_move[1]

    async def wander(self):
        x_move, y_move = randint(-1, 1), randint(-1, 1)
        next_position = (self.x_coord + x_move, self.y_coord + y_move)
        if map_dict[next_position].passable:
            actor_dict[name_key].move_by(coord_move=(x_move, y_move))
        return next_position


class Animation:
    def __init__(self, animation=None, behavior=None, color_choices=None, preset="grass"):
        presets = {"fire":{"animation":"^∧", "behavior":"random", "color_choices":"3331"},
                   "water":{"animation":"▒▓▓▓████", "behavior":"random", "color_choices":("4"*10 + "6")},
                   "grass":{"animation":("▒"*20 + "▓"), "behavior":"random", "color_choices":("2")},
                   "blob":{"animation":("ööööÖ"), "behavior":"random", "color_choices":("6")},}
        if preset:
            preset_kwargs = presets[preset]
            #calls init again using kwargs, but with preset set to None to 
            #avoid infinite recursion.
            self.__init__(**preset_kwargs, preset=None)
        else:
            self.animation = animation
            self.behavior = behavior
            self.color_choices = color_choices
    
    def __next__(self):
        if self.behavior == "random":
            color_choice = int(choice(self.color_choices))
            return term.color(color_choice)(choice(self.animation))


class Item:
    """
    An item that can be used either by the player or various actors.
    An item:
        can be carried.
        can be picked up on keyboard input.
        have a representation on the ground
        when the player is over a tile with items, the items are displayed in a
                window. 
        can be stored in a container (chests? pots? crates?)
            destructible crates/pots that strew debris around when broken(???)
        can be used (via its usable_power and given power_kwargs (for different
                versions of the same item)
    """
    def __init__(self, name='generic_item', spawn_coord=(0, 0), uses=None, 
                 tile='?', usable_power=None, power_kwargs={}, 
                 broken=False, use_message='You use the item.',
                 broken_text=" is broken."):
        self.name = name
        self.spawn_coord = spawn_coord
        self.uses = uses
        self.tile = tile
        self.usable_power = usable_power
        self.use_message = use_message
        self.broken = broken
        self.broken_text = broken_text
        self.power_kwargs = power_kwargs

    async def use(self):
        await asyncio.sleep(0)
        if self.uses != None and not self.broken:
            with term.location(40, 0):
                print("using {}!".format(repr(self.usable_power)))
            await self.usable_power(**self.power_kwargs)
            if self.uses is not None:
                self.uses -= 1
            await filter_print(output_text=self.use_message)
            if self.uses <= 0:
                self.broken = True
        else:
            await filter_print(output_text="{}{}".format(self.name, self.broken_text))
#-------------------------------------------------------------------------------

#Global state setup-------------------------------------------------------------
term = Terminal()
map_dict = defaultdict(lambda: Map_tile(passable=False, blocking=True))
actor_dict = defaultdict(lambda: [None])
state_dict = defaultdict(lambda: None)
item_dict = defaultdict(lambda: None)
actor_dict['player'] = Actor(tile=term.red("@"), health=100)
map_dict[actor_dict['player'].coords()].actors['player'] = True
state_dict['facing'] = 'n'
state_dict['menu_choices'] = []
actor_dict['player'].just_teleported = False
#-------------------------------------------------------------------------------

#Drawing functions--------------------------------------------------------------
def draw_box(top_left=(0, 0), x_size=1, y_size=1, filled=True, 
             tile=".", passable=True):
    """ Draws a box at the given coordinates."""
    x_tuple = (top_left[0], top_left[0] + x_size)
    y_tuple = (top_left[1], top_left[1] + y_size)
    if filled:
        for x in range(*x_tuple):
            for y in range(*y_tuple):
                map_dict[(x, y)].tile = tile
                map_dict[(x, y)].passable = passable
                map_dict[(x, y)].blocking = False
    else:
        map_dict[top_left].tile = tile
        map_dict[(x_tuple[1], y_tuple[1])].tile = tile
        for x in range(top_left[0], top_left[0] + x_size):
            for y in [top_left[1], top_left[1] + y_size]:
                map_dict[(x, y)].tile = tile
        for y in range(top_left[1], top_left[1] + y_size):
            for x in [top_left[0], top_left[0] + x_size]:
                map_dict[(x, y)].tile = tile

def draw_centered_box(middle_coord=(0, 0), x_size=10, y_size=10, 
                  filled=True, tile=".", passable=True):
    top_left = (middle_coord[0] - int(x_size/2), middle_coord[1] - int(y_size/2))
    draw_box(top_left=top_left, x_size=x_size, y_size=10, filled=True, tile=tile)

async def draw_line(coord_a=(0, 0), coord_b=(5, 5), palette="*",
                    passable=True, blocking = False):
    """draws a line to the map_dict connecting the two given points."""
    await asyncio.sleep(0)
    points = await get_line(coord_a, coord_b)
    for point in points:
        if len(palette) > 1:
            map_dict[point].tile = choice(palette)
        else:
            map_dict[point].tile = palette
        map_dict[point].passable = passable
        map_dict[point].blocking = blocking

async def draw_circle(center_coord=(0, 0), radius=5, palette="░",
                passable=True, blocking=False):
    """
    draws a circle in real time. eats actors right now
    """
    await asyncio.sleep(0)
    for x in range(center_coord[0] - radius, center_coord[0] + radius):
        for y in range(center_coord[1] - radius, center_coord[1] + radius):
            distance_to_center = await point_to_point_distance(point_a=center_coord, point_b=(x, y))
            if distance_to_center <= radius:
                actors = map_dict[(x, y)].actors
                map_dict[(x, y)] = Map_tile(passable=True, tile=" ", blocking=False, 
                                            description='an animation', is_animated=True,
                                            animation=Animation(), actors=actors)

#-------------------------------------------------------------------------------

#Actions------------------------------------------------------------------------
async def laser(coord_a=(0, 0), coord_b=(5, 5), palette="*", speed=.05):
    points = await get_line(coord_a, coord_b)
    with term.location(55, 0):
        print(points)
    print
    for index, point in enumerate(points[1:]):
        await asyncio.sleep(speed)
        if map_dict[point].passable:
            continue
        else:
            points_until_wall = points[:index+1]
            break
    for point in points_until_wall:
        map_dict[point].tile = term.red(choice(palette))
    with term.location(55, 10):
        print(points_until_wall)

async def push(direction=None, pusher=None):
    """
    basic pushing behavior for single-tile actors.
    TODO: implement multi-tile pushable actors. a bookshelf? large crates?▧
    """
    #run if something that has moveable flag has an actor push into it.
    await asyncio.sleep(0)
    dir_coords = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0)}
    chosen_dir = dir_coords[direction]
    pusher_coords = actor_dict[pusher].coords()
    destination_coords = (pusher_coords[0] + chosen_dir[0], pusher_coords[1] + chosen_dir[1])
    if not map_dict[destination_coords].actors:
        with term.location(0, 0):
            print("nothing to push")
        return
    pushed_name = next(iter(map_dict[destination_coords].actors))
    if not actor_dict[pushed_name].moveable:
        return 0
    else:
        pushed_coords = actor_dict[pushed_name].coords()
        pushed_destination = (pushed_coords[0] + chosen_dir[0], pushed_coords[1] + chosen_dir[1])
        if not map_dict[pushed_destination].actors and map_dict[pushed_destination].passable:
            del map_dict[destination_coords].actors[pushed_name]
            actor_dict[pushed_name].update(*pushed_destination)
            map_dict[pushed_destination].actors[pushed_name] = True

async def sword(direction='n', actor='player', length=4, name='sword', speed=.05):
    """extends and retracts a line of characters
    TODO: implement damage dealt to other actors
    TODO: it turns out it looks more like a laser with the speed set very low (0?)
    TODO: end the range once it hits a wall
    """
    await asyncio.sleep(0)
    dir_coords = {'n':(0, -1, '│'), 'e':(1, 0, '─'), 's':(0, 1, '│'), 'w':(-1, 0, '─')}
    starting_coords = actor_dict['player'].coords()
    chosen_dir = dir_coords[direction]
    sword_id = str(round(random(), 5))[2:]
    sword_segment_names = ["{}_{}_{}".format(name, sword_id, segment) for segment in range(length)]
    segment_coords = [(starting_coords[0] + chosen_dir[0] * i, 
                       starting_coords[1] + chosen_dir[1] * i) for i in range(length)]
    for segment_coord, segment_name in zip(segment_coords, sword_segment_names):
        actor_dict[segment_name] = Actor(tile=term.red(chosen_dir[2]))
        map_dict[segment_coord].actors[segment_name] = True
        for actor in map_dict[segment_coord].actors:
            if actor_dict[actor].health >= 0:
                actor_dict[actor].health -= 10
            if actor_dict[actor].health <= 0:
                actor_dict[actor].alive = False
        await asyncio.sleep(speed)
    for segment_coord, segment_name in zip(reversed(segment_coords), reversed(sword_segment_names)):
        if segment_name in map_dict[segment_coord].actors: 
            del map_dict[segment_coord].actors[segment_name]
        del actor_dict[segment_name]
        await asyncio.sleep(speed)

#-------------------------------------------------------------------------------

#Item interaction---------------------------------------------------------------
async def spawn_item_at_coords(coord=(2, 3), instance_of='wand'):
    item_id = "{}_{}".format(instance_of, str(datetime.time(datetime.now())))
    wand_broken_text = " is out of charges."
    item_catalog = {'wand':{'name':instance_of, 'spawn_coord':coord, 'uses':10,
                            'tile':term.blue('/'), 'usable_power':None},
                     'nut':{'name':instance_of, 'spawn_coord':coord, 'tile':term.red('⏣'),
                            'usable_power':None},
             'shield wand':{'name':instance_of, 'spawn_coord':coord, 'uses':10,
                            'tile':term.blue('/'), 'power_kwargs':{'radius':6},
                            'usable_power':spawn_bubble, 'broken_text':wand_broken_text},
               'vine wand':{'name':instance_of, 'spawn_coord':coord, 'uses':10,
                            'tile':term.green('/'), 'usable_power':vine_grow, 
                            'power_kwargs':{'on_actor':'player', 'start_facing':True}, 
                            'broken_text':wand_broken_text}}
    if instance_of in item_catalog:
        item_dict[item_id] = Item(**item_catalog[instance_of])
        map_dict[coord].items[item_id] = True

async def display_items_at_coord(coord=actor_dict['player'].coords(), x_pos=2, y_pos=24):
    last_coord = None
    item_list = ' '
    with term.location(x_pos, y_pos):
        print("Items here:")
    while True:
        await asyncio.sleep(.1)
        player_coords = actor_dict['player'].coords()
        
        await clear_screen_region(x_size=20, y_size=10, screen_coord=(x_pos, y_pos + 1))
        item_list = [item for item in map_dict[player_coords].items]
        for number, item_id in enumerate(item_list):
            with term.location(x_pos, (y_pos + 1) + number):
                print("{} {}".format(item_dict[item_id].tile, item_dict[item_id].name))
        last_coord = player_coords

async def display_items_on_actor(actor_key='player', x_pos=2, y_pos=7):
    item_list = ' '
    while True:
        await asyncio.sleep(.1)
        with term.location(x_pos, y_pos):
            print("Inventory:")
        await clear_screen_region(x_size=15, y_size=10, screen_coord=(x_pos, y_pos+1))
        item_list = [item for item in actor_dict[actor_key].holding_items]
        for number, item_id in enumerate(item_list):
            with term.location(x_pos, (y_pos + 1) + number):
                print("{} {}".format(item_dict[item_id].tile, item_dict[item_id].name))

async def filter_print(output_text="You open the door.", x_coord=20, y_coord=30, 
                       pause_fade_in=.01, pause_fade_out=.01, pause_stay_on=1, delay=0, blocking=False):
    await asyncio.sleep(delay)
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    y_location = term.height - 8
    x_location = middle_x - int(len(output_text) / 2)
    await asyncio.sleep(0)
    numbered_chars = [(place, char) for place, char in enumerate(output_text)]
    shuffle(numbered_chars)
    for char in numbered_chars:
        with term.location(char[0] + x_location, y_location):
            print(char[1])
        if not blocking:
            await asyncio.sleep(pause_fade_in)
        else:
            asyncio.sleep(pause_fade_in)
    shuffle(numbered_chars)
    await asyncio.sleep(pause_stay_on)
    for char in numbered_chars:
        with term.location(char[0] + x_location, y_location):
            print(' ')
        if not blocking:
            await asyncio.sleep(pause_fade_out)
        else:
            asyncio.sleep(pause_fade_out)

def write_description(x_coord=0, y_coord=0, text="this is the origin."):
    map_dict[(x_coord, y_coord)].description = text

def describe_region(top_left=(0, 0), x_size=5, y_size=5, text="testing..."):
    x_tuple = (top_left[0], top_left[0] + x_size)
    y_tuple = (top_left[1], top_left[1] + y_size)
    for x in range(*x_tuple):
        for y in range(*y_tuple):
            map_dict[(x, y)].description = text

def connect_with_passage(x1, y1, x2, y2, segments=2, palette="░"):
    """fills a straight path first then fills the shorter leg, starting from the first coordinate"""
    if segments == 2:
        if abs(x2-x1) > abs(y2-y1):
            for x_coord in range(x1, x2+1):
                map_dict[(x_coord, y1)].tile = choice(palette)
                map_dict[(x_coord, y1)].passable = True
                map_dict[(x_coord, y1)].blocking = False
            for y_coord in range(y1, y2+1):
                map_dict[(x2, y_coord)].tile = choice(palette)
                map_dict[(x2, y_coord)].passable = True
                map_dict[(x2, y_coord)].blocking = False
        else:
            for y_coord in range(y1, y2+1):
                map_dict[(x1, y_coord)].tile = choice(palette)
                map_dict[(x1, y_coord)].passable = True
                map_dict[(x1, y_coord)].blocking = False
            for x_coord in range(x1, x2+1):
                map_dict[(x_coord, y2)].tile = choice(palette)
                map_dict[(x_coord, y2)].passable = True
                map_dict[(x_coord, y2)].blocking = False

def center_of_box(x_top_left, y_top_left, width_x, height_y):
    x_middle = round(x_top_left + width_x/2)
    y_middle = round(y_top_left + height_y/2)
    return (x_middle, y_middle)

def pick_point_in_cone(cone_left_edge, cone_right_edge):
    """returns a point at a given distance range in a clockwise propagating cone
    to be used for map creation"""
    pass

async def sow_texture(root_x, root_y, palette=",.'\"`", radius=5, seeds=20, 
                passable=False, stamp=True, paint=True, color_num=1, description=''):
    """ given a root node, picks random points within a radius length and writes
    characters from the given palette to their corresponding map_dict cell.
    """
    await asyncio.sleep(0)
    for i in range(seeds):
        await asyncio.sleep(.02)
        throw_dist = radius + 1
        while throw_dist >= radius:
            x_toss, y_toss = (randint(-radius, radius),
                              randint(-radius, radius),)
            throw_dist = sqrt(x_toss**2 + y_toss**2) #euclidean distance
        toss_coord = (root_x + x_toss, root_y + y_toss)
        if paint:
            if map_dict[toss_coord].tile not in "▮▯":
                colored_tile = term.color(color_num)(map_dict[toss_coord].tile)
                map_dict[toss_coord].tile = colored_tile
        else:
            random_tile = choice(palette)
            map_dict[toss_coord].tile = term.color(color_num)(random_tile)
        #map_dict[toss_coord].tile = random_tile
        if not stamp:
            map_dict[toss_coord].passable = passable
        if description:
            map_dict[toss_coord].description = description

async def flood_fill(coord=(0, 0), target='░', replacement=' ', depth=0,
                     max_depth=10, random=False):
    """ Algorithm from wikipedia 
    figure out how to still allow player movement after it has started.
    figure out how to end a coroutine.
    TODO: Fix. broken right now.
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

def clear():
    """
    clears the screen.
    """
    # check and make call for specific operating system
    _ = call('clear' if os.name =='posix' else 'cls')

def draw_door(x, y, closed = True):
    """
    creates a door at the specified map_dict coordinate and sets the relevant
    attributes.
    """
    states = [('▮', False, True), ('▯', True, False)]
    if closed:
        tile, passable, blocking = states[0]
    else:
        tile, passable, blocking = states[1]
    map_dict[(x, y)].tile = tile
    map_dict[(x, y)].passable = passable
    map_dict[(x, y)].blocking = blocking

async def magic_door(start_coord=(5, 5), end_coord=(-22, 18)):
    """
    notes for portals/magic doors:
    either gapless teleporting doors or gapped by darkness doors.
    if gapped by darkness, door appears as flickering between different noise states.
    when magic door is stepped on, location becomes an instance of darkness
    when in darkness, the default tile is a choice from a noise palette
    the next door appears on your screen regardless of distance,
        blinks on edge of field of view at set radius
    a counter begins once the player enters the darkness. 
    a tentacle creature spawns a few screens away and approaches
    red eyes are visible from slightly beyond the edge of noise
    noise palette is based on distance from tentacle creature
    far away, the darkness is just empty space
    the closer it gets, glyphs start appearing?
    when within a short distance, the entire field flickers (mostly) red to black
    red within view distance and only you and the tentacle monster are visible
    """
    await asyncio.sleep(0)
    #an interesting thematic option: when blocking, view is entirely blotted out until you move a second time.o
    #teleport temporarily to a pocket dimension (another mini map_dict for each door pair)
    #map_dict[start_coord].blocking = True
    animation = Animation(animation='▮', behavior='random', 
                          color_choices="1234567", preset=None)
    map_dict[start_coord] = Map_tile(tile=" ", blocking=False, passable=True,
                                     magic=True, magic_destination=end_coord,
                                     is_animated=True, animation=animation)
    while(True):
        await asyncio.sleep(.1)
        player_coords = actor_dict['player'].coords()
        just_teleported = actor_dict['player'].just_teleported
        if player_coords == start_coord and not just_teleported:
            asyncio.ensure_future(filter_print(output_text="You are teleported."))
            map_dict[player_coords].passable=True
            del map_dict[player_coords].actors['player']
            actor_dict['player'].update(*end_coord)
            x, y = actor_dict['player'].coords()
            map_dict[(x, y)].actors['player'] = True
            actor_dict['player'].just_teleported = True

async def create_magic_door_pair(loop=None, door_a_coords=(5, 5), door_b_coords=(-25, -25)):
    loop.create_task(magic_door(start_coord=(door_a_coords), end_coord=(door_b_coords)))
    loop.create_task(magic_door(start_coord=(door_b_coords), end_coord=(door_a_coords)))

def map_init():
    clear()
    draw_box(top_left=(-25, -25), x_size=50, y_size=50, tile="░") #large debug room
    draw_box(top_left=(-5, -5), x_size=10, y_size=10, tile="░")
    draw_centered_box(middle_coord=(-5, -5), x_size=10, y_size=10, tile="░")
    actor_dict['box'] = Actor(x_coord=5, y_coord=5, tile='☐')
    map_dict[(7, 7)].actors['box'] = True
    draw_box(top_left=(15, 15), x_size=10, y_size=10, tile="░")
    draw_box(top_left=(30, 15), x_size=10, y_size=10, tile="░")
    draw_box(top_left=(42, 10), x_size=20, y_size=20, tile="░")
    passages = [(7, 7, 17, 17), (17, 17, 25, 10), (20, 20, 35, 20), 
                (0, 0, 17, 17), (39, 20, 41, 20), (-30, -30, 0, 0)]
    doors = [(7, 16), (0, 5), (14, 17), (25, 20), (29, 20), (41, 20)]
    for passage in passages:
        connect_with_passage(*passage)
    for door in doors:
        draw_door(*door)
    write_description()
    announcement_at_coord(coord=(0, 17), distance_trigger=5, announcement="something slithers into the wall as you approach.")
    announcement_at_coord(coord=(7, 17), distance_trigger=1, announcement="you hear muffled scratching from the other side")

def announcement_at_coord(coord=(0, 0), announcement="Testing...", distance_trigger=None):
    """
    creates a one-time announcement at coord.
    split announcement up into separate sequential pieces with pipes
    pipes are parsed in view_tile
    """
    map_dict[coord].announcement = announcement
    map_dict[coord].announcing = True
    map_dict[coord].distance_trigger = distance_trigger

def spawn_stairs(coord=(0, 0), direction="down", level_id="b1"):
    """
    creates a new set of stairs at tile
    """
    pass

async def use_stairs(direction="down"):
    """
    called from handle_input to use stair tiles.
    """
    pass

def isData(): 
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []) 

async def is_number(number="0"):
    await asyncio.sleep(0)
    try:
        float(number)
        return True
    except ValueError:
        return False

#Top level input----------------------------------------------------------------
async def get_key(): 
    """the closest thing I could get to non-blocking input"""
    await asyncio.sleep(0)
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        while True:
            await asyncio.sleep(0)
            if isData():
                key = sys.stdin.read(1)
                if key == 'x1b':  # x1b is ESC
                    break
                x, y = await handle_input(key)
            else:
                await asyncio.sleep(.01) 
    finally: 
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings) 

async def handle_input(key):
    """
    interpret keycodes and do various actions.
    controls:
    wasd to move/push
    ijkl to look in different directions
    e to examine
    spacebar to open doors
    esc to open inventory
    a variable in state_dict to capture input while in menus?
    """
    x_shift, y_shift = 0, 0 
    x, y = actor_dict['player'].coords()
    directions = {'a':(-1, 0), 'd':(1, 0), 'w':(0, -1), 's':(0, 1), 
                  'A':(-10, 0), 'D':(10, 0), 'W':(0, -10), 'S':(0, 10),}
    key_to_compass = {'w':'n', 'a':'w', 's':'s', 'd':'e', 
                      'i':'n', 'j':'w', 'k':'s', 'l':'e'}
    compass_directions = ('n', 'e', 's', 'w')
    fov = 100
    fuzz = 20
    #angles are given in a pair to resolve problems with the split at 360 and 0 degrees.
    angle_pairs = [(360, 0), (90, 90), (180, 180), (270, 270)]
    view_tuples = [(i - fov/2, i, j, j + fov/2) for i, j in angle_pairs]
    view_angles = dict(zip(compass_directions, view_tuples))
    fuzzy_edges = [((i - fuzz), (j - fov/2), (k + fov/2), (l + fuzz)) for i, j, k, l in view_tuples]
    fuzzy_view_angles = dict(zip(compass_directions, fuzzy_edges))
    dir_to_name = {'n':'North', 'e':'East', 's':'South', 'w':'West'}
    await asyncio.sleep(0)  
    if state_dict['in_menu'] == True:
        if await is_number(key):
            if int(key) in state_dict['menu_choices']:
                state_dict['menu_choice'] = key
        else:
            state_dict['menu_choice'] = False
            state_dict['in_menu'] = False
    else:
        if key in directions:
            x_shift, y_shift = directions[key]
            if key in 'wasd':
                await push(pusher='player', direction=key_to_compass[key])
            actor_dict['player'].just_teleported = False
        shifted_x, shifted_y = x + x_shift, y + y_shift
        if key in 'Vv':
            asyncio.ensure_future(vine_grow(start_x=x, start_y=y)),
        if key in 'Ee':
            description = map_dict[(x, y)].description
            asyncio.ensure_future(filter_print(output_text=description)),
        if key in ' ':
            asyncio.ensure_future(toggle_doors()),
        if key in 'g':
            asyncio.ensure_future(item_choices(coords=(x, y)))
        if key in 'Q':
            asyncio.ensure_future(equip_item(slot='q'))
        if key in 'E':
            asyncio.ensure_future(equip_item(slot='e'))
        if key in 'q':
            asyncio.ensure_future(use_item_in_slot(slot='q'))
        if key in 'e':
            asyncio.ensure_future(use_item_in_slot(slot='e'))
        if key in 'u':
            asyncio.ensure_future(use_chosen_item())
        if key in 'f':
            facing_dir = dir_to_name[state_dict['facing']]
            asyncio.ensure_future(filter_print(output_text="facing {}".format(facing_dir)))
        if key in '7':
            asyncio.ensure_future(draw_circle(center_coord=actor_dict['player'].coords())),
        if key in 'b':
            asyncio.ensure_future(spawn_bubble())
        if map_dict[(shifted_x, shifted_y)].passable and (shifted_x, shifted_y) is not (0, 0):
            map_dict[(x, y)].passable = True #make previous space passable
            del map_dict[(x, y)].actors['player']
            actor_dict['player'].update(x + x_shift, y + y_shift)
            x, y = actor_dict['player'].coords()
            map_dict[(x, y)].passable = False #make current space impassable
            map_dict[(x, y)].actors['player'] = True
        if key in "ijkl":
            state_dict['facing'] = key_to_compass[key]
            state_dict['view_angles'] = view_angles[key_to_compass[key]]
            state_dict['fuzzy_view_angles'] = fuzzy_view_angles[key_to_compass[key]]
    with term.location(0, 1):
        print("key is: {}".format(key))
    return x, y

async def toggle_doors():
    x, y = actor_dict['player'].coords()
    door_dirs = {(-1, 0), (1, 0), (0, -1), (0, 1)}
    for door in door_dirs:
        door_coord_tuple = (x + door[0], y + door[1])
        door_state = map_dict[door_coord_tuple].tile 
        if door_state == "▮":
            map_dict[door_coord_tuple].tile = '▯'
            map_dict[door_coord_tuple].passable = True
            map_dict[door_coord_tuple].blocking = False
        elif door_state == '▯':
            map_dict[door_coord_tuple].tile = '▮'
            map_dict[door_coord_tuple].passable = False
            map_dict[door_coord_tuple].blocking = True

#Item Interaction---------------------------------------------------------------
async def print_icon(x_coord=0, y_coord=20, icon_name='wand'):
    """
    prints an item's 3x3 icon representation. tiles are stored within this 
    function.
    """
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    if 'wand' in icon_name:
        icon_name = 'wand'
    icons = {'wand':('┌───┐',
                     '│  *│', 
                     '│ / │',
                     '│/  │',
                     '└───┘',),
              'nut':('┌───┐',
                     '│/ \│', 
                     '│\_/│',
                     '│\_/│',
                     '└───┘',),
            'empty':('┌───┐',
                     '│   │', 
                     '│   │',
                     '│   │',
                     '└───┘',),}
    for (num, line) in enumerate(icons[icon_name]):
        with term.location(x_coord, y_coord + num):
            print(line)

async def choose_item(item_id_choices=None, item_id=None, x_pos=0, y_pos=8):
    """
    Takes a list of item_id values
    Prints to some region of the screen:
    Get stuck in a loop until a choice is made:
    Returns an item_id
    """
    if item_id_choices == None:
        item_id_choices = [item_id for item_id in actor_dict['player'].holding_items]
    if len(item_id_choices) == 0:
        state_dict['in_menu'] = False
        return None
    if len(item_id_choices) == 1:
        state_dict['in_menu'] = False
        return item_id_choices[0]
    menu_choices = [index for index, _ in enumerate(item_id_choices)]
    state_dict['menu_choices'] = menu_choices
    state_dict['in_menu'] = True
    await clear_screen_region(x_size=20, y_size=5, screen_coord=(x_pos, y_pos))
    for (number, item) in enumerate(item_id_choices):
        with term.location(x_pos, y_pos + number):
            print("{}:".format(number))
    while True:
        await asyncio.sleep(.02)
        menu_choice = state_dict['menu_choice']
        if type(menu_choice) == str:
            if menu_choice in [str(i) for i in range(10)]:
                menu_choice = int(menu_choice)
        if menu_choice in menu_choices:
            await clear_screen_region(x_size=2, y_size=len(item_id_choices), 
                                      screen_coord=(x_pos, y_pos))
            state_dict['in_menu'] = False
            state_dict['menu_choice'] = -1 # not in range as 1 evaluates as True.
            return item_id_choices[int(menu_choice)]
    
async def key_slot_checker(slot='q', frequency=.1, centered=True, print_location=(0, 0)):
    """
    make it possible to equip each number to an item
    """
    await asyncio.sleep(0)
    slot_name = "{}_slot".format(slot)
    state_dict[slot_name] = 'empty'
    while True:
        await asyncio.sleep(frequency)
        #the item's id name is stored in state_dict under the key's name.
        equipped_item_id = state_dict["{}_slot".format(slot)]
        if equipped_item_id is not 'empty':
            #if it's equipped, display the icon.
            item_name = item_dict[equipped_item_id].name
        else:
            item_name = 'empty'
        if centered:
            x_coord, y_coord = await offset_of_center(*print_location)
        else:
            x_coord, y_coord = print_location
        with term.location(x_coord + 2, y_coord + 5):
            print(slot)
        await print_icon(x_coord=x_coord, y_coord=y_coord, icon_name=item_name)

async def equip_item(slot='q'):
    """
    each slot must also have a coroutine to use the item's abilities.
    """
    await asyncio.sleep(0)
    item_id_choice = await choose_item()
    state_dict["{}_slot".format(slot)] = item_id_choice
    item_name = item_dict[item_id_choice].name
    equip_message = "Equipped {} to slot {}.".format(item_name, slot)
    await filter_print(output_text=equip_message)
    #with term.location(30, 10):
        #print("equipped {} to slot {}".format(item_id_choice, slot))

async def use_chosen_item():
    #TODO: use is broken when a single item is in the player's inventory.
    await asyncio.sleep(0)
    item_id_choice = await choose_item()
    await item_dict[item_id_choice].use()
    
async def use_item_in_slot(slot='q'):
    await asyncio.sleep(0)
    item_id = state_dict['{}_slot'.format(slot)]
    if item_id is 'empty':
        #await filter_print(output_text='Nothing is equipped to {}!'.format(slot))
        pass
    else:
        if item_dict[item_id].power_kwargs:
            await item_dict[item_id].use()
        else:
            #put custom null action here instead of 'Nothing happens.'
            #as given for each item.
            #TODO: conditional effects, say, being near a door.
            await filter_print(output_text='Nothing happens.')

async def item_choices(coords=None, x_pos=0, y_pos=25):
    """
    -item choices should appear next to the relevant part of the screen.
    -a series of numbers and colons to indicate the relevant choices
    -give a position and list of values and item choices will hang until
     a menu choice is made.
    """
    await asyncio.sleep(0)
    if not map_dict[coords].items:
        asyncio.ensure_future(filter_print(output_text="nothing's here."))
    else:
        item_list = [item for item in map_dict[coords].items]
        if len(item_list) <= 1:
            state_dict['in_menu'] = False
            await get_item(coords=coords, item_id=item_list[0])
            return
        id_choice = await choose_item(item_id_choices=item_list, x_pos=x_pos, y_pos=y_pos)
        await get_item(coords=coords, item_id=id_choice)

async def get_item(coords=(0, 0), item_id=None, target_actor='player'):
    """
    Transfers an item from a map tile to the holding_items dict of an actor.
    """
    await asyncio.sleep(0)
    pickup_text = "picked up {}".format(item_dict[item_id].name)
    del map_dict[coords].items[item_id]
    actor_dict['player'].holding_items[item_id] = True
    asyncio.ensure_future(filter_print(pickup_text))
    return True

#Announcement/message handling--------------------------------------------------
async def parse_announcement(tile_coord_key):
    """ parses an annoucement, with a new printing after each pipe """
    announcement_sequence = map_dict[tile_coord_key].announcement.split("|")
    for delay, line in enumerate(announcement_sequence):
        asyncio.ensure_future(filter_print(output_text=line, delay=delay * 2))

async def trigger_announcement(tile_coord_key, player_coords=(0, 0)):
    if map_dict[tile_coord_key].announcing and not map_dict[tile_coord_key].seen:
        if map_dict[tile_coord_key].distance_trigger:
            distance = await point_to_point_distance(tile_coord_key, player_coords)
            if distance <= map_dict[tile_coord_key].distance_trigger:
                await parse_announcement(tile_coord_key)
                map_dict[tile_coord_key].seen = True
        else:
            await parse_announcement(tile_coord_key)
            map_dict[tile_coord_key].seen = True
    else:
        map_dict[tile_coord_key].seen = True
#-------------------------------------------------------------------------------

#Geometry functions-------------------------------------------------------------
async def point_to_point_distance(point_a=(0, 0), point_b=(5, 5)):
    """ finds 2d distance between two points """
    await asyncio.sleep(0)
    x_run, y_run = [abs(point_a[i] - point_b[i]) for i in (0, 1)]
    distance = round(sqrt(x_run ** 2 + y_run ** 2))
    return distance

async def get_line(start, end):
    """Bresenham's Line Algorithm
    Copied from http://www.roguebasin.com/index.php?title=Bresenham%27s_Line_Algorithm
    Produces a list of tuples from start and end
 
    >>> points1 = get_line((0, 0), (3, 4))
    >>> points2 = get_line((3, 4), (0, 0))
    >>> assert(set(points1) == set(points2))
    >>> print(points1)
    [(0, 0), (1, 1), (1, 2), (2, 3), (3, 4)]
    >>> print(points2)
    [(3, 4), (2, 3), (1, 2), (1, 1), (0, 0)]
    """
    await asyncio.sleep(0)
    x1, y1 = start
    # Setup initial conditions
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    # Determine how steep the line is
    is_steep = abs(dy) > abs(dx)
    # Rotate line
    if is_steep:
        x1, y1 = y1, x1
        x2, y2 = y2, x2
    # Swap start and end points if necessary and store swap state
    swapped = False
    if x1 > x2:
        x1, x2 = x2, x1
        y1, y2 = y2, y1
        swapped = True
    # Recalculate differentials
    dx = x2 - x1
    dy = y2 - y1
    # Calculate error
    error = int(dx / 2.0)
    ystep = 1 if y1 < y2 else -1
    # Iterate over bounding box generating points between start and end
    y = y1
    points = []
    for x in range(x1, x2 + 1):
        coord = (y, x) if is_steep else (x, y)
        points.append(coord)
        error -= abs(dy)
        if error < 0:
            y += ystep
            error += dx
    # Reverse the list if the coordinates were swapped
    if swapped:
        points.reverse()
    return points

async def find_angle(p0=(0, -5), p1=(0, 0), p2=(5, 0), use_degrees=True):
    """
    find the angle between two points around a central point,
    as if the edges of a triangle
    """
    await asyncio.sleep(0)
    a = (p1[0] - p0[0])**2 + (p1[1] - p0[1])**2
    b = (p1[0] - p2[0])**2 + (p1[1] - p2[1])**2
    c = (p2[0] - p0[0])**2 + (p2[1] - p0[1])**2
    divisor = sqrt(4 * a * b)
    if divisor == 0:
        return 0
    else:     
        result = acos((a+b-c) / divisor)
        if use_degrees:
            return degrees(result)
        else:
            return result

async def point_at_distance_and_angle(angle_from_twelve=30, central_point=(0, 0), 
                                      reference_point=(0, 5), radius=10,
                                      rounded=True):
    """
    returns a point that lies at distance radius from point
    central_point. a is reference_point, b is central_point, c is returned point
    
        c
       /|
     r/ |y
     /  |
    a---b
      x
    """
    await asyncio.sleep(0)
    angle = 90 - angle_from_twelve
    x = cos(radians(angle)) * radius
    y = sin(radians(angle)) * radius
    if rounded:
        return (round(central_point[0] + x), round(central_point[1] + y))

async def angle_checker(angle_from_twelve):
    """
    breaks out angle_checking code used in view_tile()
    Determines whether the currently checked view tile is in the
    main clear range or the fuzzy edge.
    """
    angle_min_max = state_dict['view_angles']
    fuzzy_angle_min_max = state_dict['fuzzy_view_angles']
    #check if view_tile is in main cone of view:
    if (angle_min_max[0] <= angle_from_twelve <= angle_min_max[1] or
            angle_min_max[2] <= angle_from_twelve <= angle_min_max[3]):
        display = True
    else:
        display = False
    #check if view_tile is in fuzzy edges of view:
    if (fuzzy_angle_min_max[0] <= angle_from_twelve <= fuzzy_angle_min_max[1] or
        fuzzy_angle_min_max[2] <= angle_from_twelve <= fuzzy_angle_min_max[3]):
        fuzzy = True
    else:
        fuzzy = False
    return fuzzy, display
#-------------------------------------------------------------------------------

#UI/HUD functions---------------------------------------------------------------
async def check_line_of_sight(coord_a=(0, 0), coord_b=(5, 5)):
    """
    intended to be used for occlusion.
    show the tile that the first collision happened at but not the following tile
    """
    await asyncio.sleep(.01)
    open_space, walls, history = 0, 0, []
    points = await get_line(coord_a, coord_b)
    change_x, change_y = coord_b[0] - coord_a[0], coord_b[1] - coord_a[1]
    reference_point = coord_a[0], coord_a[1] + 5
    for point in points:
        # if there is a magic door between, start another check_line_of_sight of length remaining
        if map_dict[point].magic == True:
            last_point = points[-1]
            difference_from_last = last_point[0] - point[0], last_point[1] - point[1]
            destination = map_dict[point].magic_destination
            if difference_from_last is not (0, 0):
                #TODO: fix x-ray vision problem past magic doors into solid wall
                coord_through_door = (destination[0] + difference_from_last[0], 
                                      destination[1] + difference_from_last[1])
                return await check_contents_of_tile(coord_through_door)
        if map_dict[point].blocking == False:
            open_space += 1
        else:
            walls += 1
        if walls > 1:
            return False
    if walls == 0:
        return True
    if map_dict[points[-1]].blocking == True and walls == 1:
        return True

async def view_tile(x_offset=1, y_offset=1, threshold = 12):
    """ handles displaying data from map_dict """
    noise_palette = " " * 5
    #absolute distance from player
    distance = sqrt(abs(x_offset)**2 + abs(y_offset)**2) 
    await asyncio.sleep(random()/5 * distance)
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    previous_actor, previous_tile, actor = None, None, None
    print_location = (middle_x + x_offset, middle_y + y_offset)
    last_printed = ' '
    #view angle setup
    angle_from_twelve = await find_angle(p2=(x_offset, y_offset))
    if x_offset <= 0:
        angle_from_twelve = 360 - angle_from_twelve
    display = False
    fuzzy = False
    while True:
        await asyncio.sleep(.01)
        #pull up the most recent viewing angles based on recent inputs:
        fuzzy, display = await angle_checker(angle_from_twelve)
        if (x_offset, y_offset) == (0, 0):
            print_choice=term.red('@')
        elif display or fuzzy:
            player_x, player_y = actor_dict['player'].coords()
            #add a line in here for different levels/dimensions:
            x_display_coord, y_display_coord = player_x + x_offset, player_y + y_offset
            tile_coord_key = (x_display_coord, y_display_coord)
            if randint(0, round(distance)) < threshold:
                line_of_sight_result = await check_line_of_sight((player_x, player_y), tile_coord_key)
                if line_of_sight_result == True:
                    await trigger_announcement(tile_coord_key, player_coords=(player_x, player_y))
                    print_choice = await check_contents_of_tile(tile_coord_key)
                elif line_of_sight_result != False and line_of_sight_result != None:
                    #catches tiles beyond magic doors:
                    print_choice = line_of_sight_result
                else:
                    #catches tiles blocked from view:
                    print_choice = ' '
            else:
                #catches fuzzy fringe starting at threshold:
                print_choice = ' '
        else:
            #catches tiles that are not within current FOV
            print_choice = ' '
        with term.location(*print_location):
            # only print something if it has changed:
            if last_printed != print_choice:
                print(print_choice)
                last_printed = print_choice
        #distant tiles update slower than near tiles:
        await asyncio.sleep(distance * .015)

async def check_contents_of_tile(coord):
    if map_dict[coord].actors:
        actor_name = next(iter(map_dict[coord].actors))
        if actor_dict[actor_name].is_animated:
            return next(actor_dict[actor_name].animation)
        else:
            return actor_dict[actor_name].tile
    if map_dict[coord].items:
        item_name = next(iter(map_dict[coord].items))
        return item_dict[item_name].tile
        return item_name
    if map_dict[coord].is_animated:
        return next(map_dict[coord].animation)
    else:
        return map_dict[coord].tile

async def offset_of_center(x_offset=0, y_offset=0):
    await asyncio.sleep(0)
    window_width, window_height = term.width, term.height
    middle_x, middle_y = (int(window_width / 2 - 2), 
                      int(window_height / 2 - 2),)
    x_print, y_print = middle_x + x_offset, middle_y + y_offset
    return x_print, y_print

async def clear_screen_region(x_size=10, y_size=10, screen_coord=(0, 0)):
    await asyncio.sleep(0)
    for y in range(screen_coord[1], screen_coord[1] + y_size):
        with term.location(screen_coord[0], y):
            print(' ' * x_size)

async def ui_box_draw(position="top left", box_height=1, box_width=9, x_margin=30, y_margin=4):
    """
    draws a box for UI elements
    <--width-->
    +---------+ ^
    |         | | height = 1
    +---------+ v
    """
    await asyncio.sleep(0)
    top_bar = "┌" + ("─" * box_width) + "┐"
    bottom_bar = "└" + ("─" * box_width) + "┘"
    if position == "top left":
        x_print, y_print = x_margin, y_margin
    if position == "centered":
        window_width, window_height = term.width, term.height
        middle_x, middle_y = (int(window_width / 2 - 2), 
                          int(window_height / 2 - 2),)
        x_print, y_print = middle_x + x_margin, middle_y + y_margin
    while True:
        await asyncio.sleep(1)
        with term.location(x_print, y_print):
            print(top_bar)
        with term.location(x_print, y_print + box_height + 1):
            print(bottom_bar)
        for row in range(y_print + 1, y_print + box_height + 1):
            with term.location(x_print, row):
                print("│")
            with term.location(x_print + box_width + 1, row):
                print("│")

async def status_bar_draw(state_dict_key="health", position="top left", bar_height=1, bar_width=10,
                          x_margin=5, y_margin=4):
    asyncio.ensure_future(ui_box_draw(position=position, bar_height=box_height, bar_width=box_width,
                          x_margin=x_margin, y_margin=y_margin))

async def timer(x_pos=0, y_pos=10, time_minutes=0, time_seconds=5, resolution=1):
    await asyncio.sleep(0)
    timer_text = str(time_minutes).zfill(2) + ":" + str(time_seconds).zfill(2)
    while True:
        await asyncio.sleep(resolution)
        with term.location(x_pos, y_pos):
            print(term.red(timer_text))
        if time_seconds >= 1:
            time_seconds -= resolution
        elif time_seconds == 0 and time_minutes >= 1:
            time_seconds = 59
            time_minutes -= 1
        elif time_seconds == 0 and time_minutes == 0:
            x, y = actor_dict['player'].coords()
            await vine_grow(start_x=x,  start_y=y)
            with term.location(x_pos, y_pos):
                print(" " * 5)
            break
        timer_text = str(time_minutes).zfill(2) + ":" + str(time_seconds).zfill(2)

async def view_init(loop, term_x_radius = 15, term_y_radius = 15, max_view_radius = 15):
    await asyncio.sleep(0)
    for x in range(-term_x_radius, term_x_radius + 1):
       for y in range(-term_y_radius, term_y_radius + 1):
           distance = sqrt(x**2 + y**2)
           #cull view_tile instances that are beyond a certain radius
           if distance < max_view_radius:
               loop.create_task(view_tile(x_offset=x, y_offset=y))

async def readout(x_coord=50, y_coord=35, update_rate=.1, float_len=3, 
                  actor_name=None, attribute=None, title=None, bar=False, 
                  bar_length=20, is_actor=True, is_state=False):
    """listen to a specific key of state_dict """
    await asyncio.sleep(0)
    while True:
        await asyncio.sleep(0)
        if attribute == 'coords':
            key_value = str((getattr(actor_dict[actor_name], 'x_coord'), getattr(actor_dict[actor_name], 'y_coord')))
        else:
            key_value = getattr(actor_dict[actor_name], attribute)
        max_value = getattr(actor_dict[actor_name], "max_health")
        if bar:
            bar_filled = round((int(key_value)/max_value) * bar_length)
            bar_unfilled = bar_length - bar_filled
            bar_characters = "█" * bar_filled + "░" * bar_unfilled
        if title:
            with term.location(x_coord, y_coord):
                if not bar:
                    print("{}{}".format(title, key_value))
                else:
                    print("{}{}".format(title, term.red(bar_characters)))
        else:
            with term.location(x_coord, y_coord):
                print("{}".format(key_value))

async def ui_setup(loop):
    """
    lays out UI elements to the screen at the start of the program.
    """
    await asyncio.sleep(0)
    asyncio.ensure_future(ui_box_draw(x_margin=49, y_margin=35, box_width=23))
    loop.create_task(key_slot_checker(slot='q', print_location=(-30, 10)))
    loop.create_task(key_slot_checker(slot='e', print_location=(30, 10)))
    loop.create_task(display_items_at_coord())
    loop.create_task(display_items_on_actor())
#-------------------------------------------------------------------------------

#Actor behavior functions-------------------------------------------------------
async def wander(x_current, y_current, name_key):
    """ 
    randomly increments or decrements x_current and y_current
    if square to be moved to is passable
    """
    await asyncio.sleep(0)
    x_move, y_move = randint(-1, 1), randint(-1, 1)
    next_position = (x_current + x_move, y_current + y_move)
    if map_dict[next_position].passable:
        actor_dict[name_key].move_by(coord_move=(x_move, y_move))
    return next_position

async def attack(attacker_key=None, defender_key=None, blood=True, spatter_num=9):
    await asyncio.sleep(0)
    attacker_strength = actor_dict[attacker_key].strength
    target_x, target_y = actor_dict[defender_key].coords()
    if blood:
        await sow_texture(root_x=target_x, root_y=target_y, radius=3, paint=True, 
                          seeds=randint(1, spatter_num), description="blood.")
    if actor_dict[defender_key].health >= attacker_strength:
        actor_dict[defender_key].health -= attacker_strength
    else:
        pass

async def seek_actor(current_coord=(0, 0), name_key=None, seek_key='player'):
    """ Standardize format to pass movement function.  """
    await asyncio.sleep(0)
    x_current, y_current = current_coord
    target_x, target_y = actor_dict[seek_key].coords()
    active_x, active_y = x_current, y_current
    diff_x, diff_y = (active_x - target_x), (active_y - target_y)
    hurtful = actor_dict[name_key].hurtful
    player_x, player_y = actor_dict["player"].coords()
    player_x_diff, player_y_diff = (active_x - player_x), (active_y - player_y)
    if hurtful and abs(player_x_diff) <= 1 and abs(player_y_diff) <= 1:
        await attack(attacker_key=name_key, defender_key="player")
    if diff_x > 0 and map_dict[(active_x - 1, active_y)].passable:
        active_x -= 1
    if diff_x < 0 and map_dict[(active_x + 1, active_y)].passable:
        active_x += 1
    if diff_y > 0 and map_dict[(active_x, active_y - 1)].passable:
        active_y -= 1
    if diff_y < 0 and map_dict[(active_x, active_y + 1)].passable:
        active_y += 1
    actor_dict[name_key].update(active_x, active_y)
    return (active_x, active_y)

async def damage_door():
    """ allows actors to break down doors"""
    pass
#-------------------------------------------------------------------------------

#misc utility functions---------------------------------------------------------
async def random_unicode(length=1, clean=True):
    """
    Create a list of unicode characters within the range 0000-D7FF
    adapted from:
    https://stackoverflow.com/questions/37842010/how-can-i-get-a-random-unicode-string/37844413#37844413
    """
    await asyncio.sleep(0)
    random_unicodes = [chr(randrange(0xD7FF)) for _ in range(0, length)] 
    if clean:
        while True:
            sleep(.01)
            a = random_unicode(1)
            if len(repr(a)) == 3:
                print(a)
    return u"".join(random_unicodes)

async def facing_dir_to_num(direction="n"):
    await asyncio.sleep(0)
    dir_to_num = {'n':1, 'e':2, 's':3, 'w':4}
    return dir_to_num[direction]

async def run_every_n(sec_interval=3, repeating_function=None, args=() ):
    while True:
        await asyncio.sleep(sec_interval)
        x, y = actor_dict['player'].coords()
        asyncio.ensure_future(repeating_function(*args))

async def track_actor_location(state_dict_key="player", actor_dict_key="player", update_speed=.1, length=10):
    await asyncio.sleep(0)
    actor_coords = None
    while True:
        await asyncio.sleep(update_speed)
        actor_coords = actor_dict[actor_dict_key].coords()
        state_dict[state_dict_key] = actor_coords
#-------------------------------------------------------------------------------

#Actor creation and controllers----------------------------------------------
async def tentacled_mass(start_coord=(-5, -5), speed=.5, tentacle_length_range=(3, 8),
                         tentacle_rate=.1, tentacle_colors="456"):
    """
    creates a (currently) stationary mass of random length and color tentacles
    move away while distance is far, move slowly towards when distance is near, radius = 20?
    """
    await asyncio.sleep(0)
    while True:
        await asyncio.sleep(tentacle_rate)
        #asyncio.ensure_future(timed_actor(coords=start_coord))
        if random() < .3:
            start_coord = start_coord[0] + randint(-1, 1), start_coord[1] + randint(-1, 1)
        tentacle_color = int(choice(tentacle_colors))
        asyncio.ensure_future(vine_grow(start_x=start_coord[0], start_y=start_coord[1], actor_key="tentacle", 
                       rate=random(), vine_length=randint(*tentacle_length_range), rounded=True,
                       behavior="retract", speed=.01, damage=20, color_num=tentacle_color,
                       extend_wait=.025, retract_wait=.25 ))
    
async def shrouded_horror(start_x=0, start_y=0, speed=.1, shroud_pieces=50, core_name_key="shrouded_horror"):
    """
    X a set core that moves around and an outer shroud of random moving tiles
    X shroud pieces are made of darkness. darkness is represented by an empty square (' ')
    shroud pieces do not stray further than a set distance, some are close, some are far
    X shroud pieces do not go through walls
    X shroud pieces start in one place and wander further or closer from the core
    X shroud pieces follow the path of the core and can trail behind
    X if a door is opened into a place with a shrouded horror, darkness should bleed into the hallway with you.
    short tentacles should grow, seeking out the location of the player.
    X they retract when reaching a maxiumum length. fastfastfast out, slowly retract one tile at a time.
    if they hit a player, the player is dragged a random number of tiles from 0 to the length of the tentacle
    each key pressed that is not the same key in a row removes a tile to be dragged by .25
    shrouded horrors can
        open doors (slowly)
        push boxes
            takes speed**1.2 for each box stacked
    shrouded_horror is a core and a number of shroud pieces
    when it is first run, core is started as a coroutine (as an actor) as is each shroud_location
    """
    await asyncio.sleep(0)
    #initialize all shroud tiles to starting coordinates:
    core_location = (start_x, start_y)
    actor_dict[core_name_key] = Actor(x_coord=core_location[0], y_coord=core_location[1], tile=" ")
    map_dict[core_location].actors[core_name_key] = True
    shroud_locations = [(start_x, start_y)] * shroud_pieces
    #initialize segment actors:
    shroud_piece_names = []
    for number, shroud_coord in enumerate(shroud_locations):
        shroud_piece_names.append("{}_piece_{}".format(core_name_key, number))
    for number, name in enumerate(shroud_piece_names):
        actor_dict[name] = Actor(x_coord=start_x, y_coord=start_y, tile=' ')
    wait = 0
    while True:
        await asyncio.sleep(speed)
        for offset, shroud_name_key in enumerate(shroud_piece_names):
            #deleting instance of the shroud pieces from the map_dict's actor list:
            coord = actor_dict[shroud_name_key].coords()
            if shroud_name_key in map_dict[coord].actors:
                del map_dict[coord].actors[shroud_name_key]
            behavior_val = random()
            if behavior_val < .2:
                new_coord = coord
            elif behavior_val > .6:
                new_coord = await wander(*coord, shroud_name_key)
            else:
                new_coord = await seek_actor(current_coord=coord, name_key=shroud_name_key, 
                                       seek_key=core_name_key)
            map_dict[new_coord].actors[shroud_name_key] = True 
        #move the core
        #TODO: wrap actor movement and deletion of old location into a function.
        core_location = actor_dict[core_name_key].coords()
        if core_name_key in map_dict[core_location].actors:
            del map_dict[core_location].actors[core_name_key]
        core_behavior_val = random()
        if wait > 0:
            wait -= 1
            pass 
        elif core_behavior_val < .05:
            new_core_location = core_location
            asyncio.ensure_future(vine_grow(start_x=core_location[0], start_y=core_location[1])),
            wait = 20
        elif core_behavior_val > .4:
            new_core_location = await wander(*core_location, core_name_key)
        else:
            new_core_location = await seek_actor(current_coord=core_location, 
                                           name_key=core_name_key, seek_key="player")
        map_dict[new_core_location].actors[core_name_key] = True

async def snake(start_x=0, start_y=0, speed=.05, head="0", length=10, name_key="snake"):
    """
    the head is always index 0, followed by the rest of the list for each segment.
    when the head moves to a new cell, the next segment in line takes it's coordinates.
    still broken. perhaps not worth fixing.
    """
    await asyncio.sleep(0)
    #initialize segment locations all to starting coordinates:
    segment_locations = [(start_x, start_y)] * length
    rand_direction = randint(1, 4)
    snake_segments = {(1, 2):'╭', (4, 3):'╭', (2, 3):'╮', (1, 4):'╮', (1, 1):'│', (3, 3):'│', 
                      (3, 4):'╯', (2, 1):'╯', (3, 2):'╰', (4, 1):'╰', (2, 2):'─', (4, 4):'─', 
                      (4, 2):'0', (2, 4):'0', (1, 3):'0', (3, 1):'0'}
    new_x, new_y = 0, 0 
    movement_tuples = {1:(0, -1), 2:(1, 0), 3:(0, 1), 4:(-1, 0)}
    movement_history = [1] * length * 2
    #initialize segment actors:
    segment_names = []
    for number, segment_coord in enumerate(segment_locations):
        segment_names.append("{}_seg_{}".format(name_key, number))
        actor_dict[(segment_names[-1])] = Actor(x_coord=segment_coord[0], y_coord=segment_coord[1])
    print(segment_names)
    while True:
        await asyncio.sleep(speed)
        #deleting all traces of the snake segments from the map_dict's actor list:
        for name_key, coord in zip(segment_names, segment_locations):
            if name_key in map_dict[coord].actors:
                del map_dict[coord].actors[name_key]
        segment_locations.pop()
        #creating a new head location that doesn't overlap with existing segments:
        fail_count = 0
        while (new_x, new_y) in segment_locations or map_dict[(new_x, new_y)].passable == False:
            rand_direction = randint(1, 4)
            rand_direction_tuple = movement_tuples[rand_direction]
            new_x, new_y = (segment_locations[0][0] + rand_direction_tuple[0],
                            segment_locations[0][1] + rand_direction_tuple[1],)
            #an easy but ugly fix for the snake dead-ending.
            #a better fix would be for it to switch directions
            if map_dict[(new_x, new_y)].passable == False:
                fail_count += 1
            if fail_count > 5:
                new_x, new_y = start_x, start_y
        movement_history.pop()
        movement_history.insert(0, rand_direction)
        new_head_coord = (new_x, new_y)
        segment_locations.insert(0, new_head_coord)
        #write the new locations of each segment to the map_dict's tiles' actor lists
        counter = 0
        for name_key, coord in zip(segment_names, segment_locations):
            actor_dict[(name_key)].update(coord)
            segment_tile_coord_key = (movement_history[counter], movement_history[counter - 1])
            if segment_tile_coord_key == (0, -1):
                actor_dict[(name_key)].tile = '1'
            else:
                actor_dict[(name_key)].tile = snake_segments[segment_tile_coord_key]
            map_dict[coord].actors[name_key] = name_key
            counter += 1

async def basic_actor(start_x=0, start_y=0, speed=.1, tile="*", 
        movement_function=wander, name_key="test", hurtful=False,
        is_animated=False, animation=" "):
    """ A coroutine that creates a randomly wandering '*' """
    """
    actors can:
    move from square to square using a movement function
    hold items
    attack or interact with the player
    die
    exist for a set number of turns
    """
    #TODO: separate actor creation and behavior into separate functions?
    actor_dict[(name_key)] = Actor(x_coord=start_x, y_coord=start_y, speed=speed, 
                                   tile=tile, hurtful=hurtful, leaves_body=True,
                                   is_animated=is_animated, animation=animation)
    coords = actor_dict[name_key].coords()
    while True:
        await asyncio.sleep(speed)
        current_coords = actor_dict[name_key].coords() #checked again here because actors can be pushed around
        if name_key in map_dict[current_coords].actors:
            del map_dict[current_coords].actors[name_key]
        coords = await movement_function(current_coord=current_coords, name_key=name_key)
        map_dict[coords].actors[name_key] = name_key
        if not actor_dict[name_key].alive:
            await kill_actor(name_key=name_key)
            return

async def kill_actor(name_key=None, leaves_body=True, blood=True):
    if leaves_body:
        body_tile = term.red(actor_dict[name_key].tile)
    del actor_dict[name_key]
    del map_dict[coords].actors[name_key]
    if blood:
        await sow_texture(root_x=coords[0], root_y=coords[1], radius=5, paint=True, 
                          seeds=10, description="blood.")
    if leaves_body:
        #TODO: replace the body with an item, drop items in spray around actor
        map_dict[coords].tile = body_tile
        map_dict[coords].description = "A body."
    return

async def vine_grow(start_x=0, start_y=0, actor_key="vine", 
                    rate=.1, vine_length=20, rounded=True,
                    behavior="retract", speed=.01, damage=20,
                    extend_wait=.025, retract_wait=.25,
                    color_num=2, on_actor=None, start_facing=False):
    """grows a vine starting at coordinates (start_x, start_y). Doesn't know about anything else.
    TODO: make vines stay within walls (a toggle between clipping and tunneling)
    TODO: vines can be pushed right now. Add immoveable property to actors. make vines immovable
    """
    await asyncio.sleep(rate)
    if on_actor:
        start_x, start_y = actor_dict[on_actor].coords()
    if not rounded:
        vine_picks = {(1, 2):'┌', (4, 3):'┌', (2, 3):'┐', (1, 4):'┐', (1, 1):'│', (3, 3):'│', 
                (3, 4):'┘', (2, 1):'┘', (3, 2):'└', (4, 1):'└', (2, 2):'─', (4, 4):'─', }
    else:
        vine_picks = {(1, 2):'╭', (4, 3):'╭', (2, 3):'╮', (1, 4):'╮', (1, 1):'│', (3, 3):'│', 
                (3, 4):'╯', (2, 1):'╯', (3, 2):'╰', (4, 1):'╰', (2, 2):'─', (4, 4):'─', }
    behaviors = ["grow", "retract", "bolt"]
    exclusions = {(2, 4), (4, 2), (1, 3), (3, 1), }
    vines = [term.green(i) for i in "┌┐└┘─│"]
    prev_dir, next_dir = randint(1, 4), randint(1, 4)
    movement_tuples = {1:(0, -1), 2:(1, 0), 3:(0, 1), 4:(-1, 0)}
    next_tuple = movement_tuples[next_dir]
    vine_locations = []
    vine_id = str(datetime.time(datetime.now()))
    vine_actor_names = ["{}_{}_{}".format(actor_key, vine_id, number) for number in range(vine_length)]
    current_coord = (start_x, start_y)
    if start_facing:
        facing_dir = state_dict['facing']
        next_dir = await facing_dir_to_num(facing_dir)
    else:
        next_dir = randint(1, 4)
    for vine_name in vine_actor_names:
        while (prev_dir, next_dir) in exclusions:
            next_dir = randint(1, 4)
        next_tuple, vine_tile = (movement_tuples[next_dir], 
                                 vine_picks[(prev_dir, next_dir)])
        actor_dict[vine_name] = Actor(x_coord=current_coord[0],
                                      y_coord=current_coord[1],
                                      tile=term.color(color_num)(vine_tile),
                                      moveable=False)
        current_coord = (current_coord[0] + next_tuple[0], current_coord[1] + next_tuple[1])
        prev_dir = next_dir
        #next_dir is generated at the end of the for loop so it can be
        #initialized to a given direction.
        next_dir = randint(1, 4)
    for vine_name in vine_actor_names:
        await asyncio.sleep(extend_wait)
        map_tile = actor_dict[vine_name].tile
        coord = actor_dict[vine_name].coord
        if behavior == "grow":
            map_dict[coord].tile = map_tile
        if behavior == "retract" or "bolt":
            map_dict[coord].actors[vine_name] = True
    if behavior == "retract":
        end_loop, end_wait = reversed(vine_actor_names), retract_wait
    if behavior == "bolt":
        end_loop, end_wait = vine_actor_names, extend_wait
    for vine_name in end_loop:
        coord = actor_dict[vine_name].coord
        await asyncio.sleep(end_wait)
        del map_dict[coord].actors[vine_name]

async def spawn_bubble(centered_on_actor='player', radius=6):
    """
    spawns a circle of animated timed actors that are impassable
    rand_delay in timed_actor is for a fade-in/fade-out effect.
    """
    coords = actor_dict[centered_on_actor].coords()
    await asyncio.sleep(0)
    bubble_id = str(datetime.time(datetime.now()))
    bubble_pieces = {}
    player_coords = actor_dict['player'].coords()
    every_five = [i * 5 for i in range(72)]
    points_at_distance = {await point_at_distance_and_angle(radius=radius, central_point=player_coords, angle_from_twelve=angle) for angle in every_five}
    for num, point in enumerate(points_at_distance):
        actor_name = 'bubble_{}_{}'.format(bubble_id, num)
        asyncio.ensure_future(timed_actor(name=actor_name, coords=(point), rand_delay=.3))

async def timed_actor(death_clock=5, name='timed_actor', coords=(0, 0),
                      rand_delay=0, solid=True):
    """
    spawns an actor at given coords that disappears after a number of turns.
    """
    if name == 'timed_actor':
        name = name + str(datetime.time(datetime.now()))
    if rand_delay:
        await asyncio.sleep(random() * rand_delay)
    actor_dict[name] = Actor(moveable=False, x_coord=coords[0], y_coord=coords[1], 
                             tile=str(death_clock), is_animated=True,
                             animation=Animation(preset='water'))
    map_dict[coords].actors[name] = True
    #TODO: model of passable spaces is flawed. multiple things change whether a space is passable.
    #map_tiles should register a default state to return to or have multiple properties (is_wall)
    #or perhaps check for actors that are solid?
    prev_passable_state = map_dict[coords].passable
    if solid:
        map_dict[coords].passable = False
    while death_clock >= 1:
        await asyncio.sleep(1)
        death_clock -= 1
    del map_dict[coords].actors[name]
    del actor_dict[name]
    map_dict[coords].passable = prev_passable_state

async def orbit(name='particle', radius=5, degrees_per_step=1, on_center=(0, 0), 
                rand_speed=True):
    """
    generates an actor that orbits about a point
    TODO:
    """
    await asyncio.sleep(0)
    angle = randint(0, 360)
    particle_id = "{}_{}".format(name, str(datetime.time(datetime.now())))
    actor_dict[particle_id] = Actor(x_coord=on_center[0], y_coord=on_center[1], 
                                    tile='X', moveable=False, is_animated=True,
                                    animation=Animation(preset='water'))
    map_dict[on_center].actors[particle_id] = True
    point_coord = actor_dict[particle_id].coords()
    if rand_speed:
        speed_multiplier = 1 + (random()/2 - .25)
    else:
        speed_multiplier = 1
    last_location = None
    while True:
        await asyncio.sleep(0.005 * speed_multiplier)
        del map_dict[point_coord].actors[particle_id]
        point_coord = await point_at_distance_and_angle(radius=radius, central_point=on_center, angle_from_twelve=angle)
        if point_coord != last_location:
            actor_dict[particle_id].update(*point_coord)
            last_location = actor_dict[particle_id].coords()
        map_dict[last_location].actors[particle_id] = True
        angle = (angle + degrees_per_step) % 360

#-------------------------------------------------------------------------------

async def death_check():
    await asyncio.sleep(0)
    player_health = actor_dict["player"].health
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    message = "You have died."
    while True:
        await asyncio.sleep(0)
        player_health = actor_dict["player"].health
        if player_health <= 0:
            await filter_print(output_text=message, x_coord=(middle_x - round(len(message)/2)), 
                               y_coord=middle_y, blocking=True)
            sleep(30000)
            await kill_all_tasks()

async def kill_all_tasks():
    await asyncio.sleep(0)
    pending = asyncio.Task.all_tasks()
    for task in pending:
        task.cancel()
        # Now we should await task to execute it's cancellation.
        # Cancelled task raises asyncio.CancelledError that we can suppress:
        with suppress(asyncio.CancelledError):
            loop.run_until_complete(task)
    #TODO, add a function to break given a flag to quit, put this in every task?
    #not working right now,

def main():
    map_init()
    state_dict["player_health"] = 100
    state_dict['view_angles'] = (315, 360, 0, 45)
    state_dict['fuzzy_view_angles'] = (315, 360, 0, 45)
    old_settings = termios.tcgetattr(sys.stdin) 
    loop = asyncio.new_event_loop()
    loop.create_task(get_key())
    loop.create_task(view_init(loop))
    loop.create_task(ui_setup(loop))
    """
    for i in range(30):
        name = 'test_seeker_{}'.format(i)
        start_coord = (randint(-30, -15), randint(-30, -15))
        speed = .5 + random()/2
        loop.create_task(basic_actor(*start_coord, speed=speed, movement_function=seek_actor, 
                                     tile="Ϩ", name_key=name, hurtful=True,
                                     is_animated=True, animation=Animation(preset="blob")))
                                     """
    loop.create_task(track_actor_location())
    loop.create_task(readout(is_actor=True, actor_name="player", attribute='coords', title="coords:"))
    loop.create_task(readout(bar=True, y_coord=36, actor_name='player', attribute='health', title="♥:"))
    #loop.create_task(shrouded_horror(start_x=-8, start_y=-8))
    #loop.create_task(tentacled_mass())
    #loop.create_task(tentacled_mass(start_coord=(9, 4)))
    loop.create_task(create_magic_door_pair(loop=loop, door_a_coords=(-26, 3), door_b_coords=(-7, 3)))
    loop.create_task(create_magic_door_pair(loop=loop, door_a_coords=(-26, 4), door_b_coords=(-7, 4)))
    loop.create_task(create_magic_door_pair(loop=loop, door_a_coords=(-26, 5), door_b_coords=(-7, 5)))
    for i in range(5):
        loop.create_task(spawn_item_at_coords(coord=(5, 5)))
    loop.create_task(spawn_item_at_coords(coord=(6, 6), instance_of='vine wand'))
    loop.create_task(spawn_item_at_coords(coord=(7, 7), instance_of='shield wand'))
    loop.create_task(spawn_item_at_coords(coord=(5, 4), instance_of='nut'))
    loop.create_task(spawn_item_at_coords(coord=(5, 4), instance_of='nut'))
    loop.create_task(death_check())
    for i in range(50):
        loop.create_task(orbit(radius=5))
    asyncio.set_event_loop(loop)
    result = loop.run_forever()

#TODO: add an aiming reticule and/or a bullet actor that is spawned by a keypress

with term.hidden_cursor():
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        main()
    finally: 
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings) 
