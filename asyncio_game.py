import asyncio
import sys
import select 
import tty 
import termios
from blessings import Terminal
from collections import defaultdict
from datetime import datetime
from random import randint, choice, random, shuffle
from math import acos, degrees, pi, sin, sqrt
from itertools import cycle
from subprocess import call
from time import sleep #hack to prevent further input/freeze screen on player death
import os

class Map_tile:
    """ holds the status and state of each tile. """
    def __init__(self, passable=True, tile="▓", blocking=True, 
                 description='', announcing=False, seen=False, 
                 announcement="", distance_trigger=None, is_animated=False,
                 animation="", actors=None):
        """ create a new map tile, location is stored in map_dict"""
        self.passable, self.tile, self.blocking, self.description = (passable, tile, blocking, description)
        self.announcing, self.seen, self.announcement = announcing, seen, announcement
        self.distance_trigger = distance_trigger
        if not actors:
            self.actors = defaultdict(lambda:None)
        #allows for new map_tiles to be initialized with an existing actor list
        else:
            self.actors = actors
        self.is_animated = is_animated
        self.animation = animation
        self.magic = False

class Actor:
    """ the representation of a single actor that lives on the map. """
    def __init__(self, x_coord=0, y_coord=0, speed=.2, tile="?", strength=1, 
                 health=50, hurtful=True, moveable=True, is_animated=False,
                 animation=""):
        """ create a new actor at position x, y """
        self.x_coord, self.y_coord, = (x_coord, y_coord)
        self.speed, self.tile = (speed, tile)
        self.coord = (x_coord, y_coord)
        self.strength, self.health, self.hurtful = strength, health, hurtful
        self.max_health = self.health #max health is set to original value
        self.alive = True
        self.moveable = moveable
        self.is_animated = is_animated
        self.animation = animation

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


class Animation:
    def __init__(self, animation=None, behavior=None, color_choices=None, preset="grass"):
        presets = {"fire":{"animation":"^∧", "behavior":"random", "color_choices":"3331"},
                   "water":{"animation":"▒▓▓▓████", "behavior":"random", "color_choices":("4"*10 + "6")},
                   "grass":{"animation":("▒"*20 + "▓"), "behavior":"random", "color_choices":("2")},
                   "blob":{"animation":("ööööÖ"), "behavior":"random", "color_choices":("6")},}
        if preset:
            preset_kwargs = presets[preset]
            #self.preset = None
            self.__init__(**preset_kwargs, preset=None)
        else:
            self.animation = animation
            self.behavior = behavior
            self.color_choices = color_choices
    
    def __next__(self):
        if self.behavior == "random":
            color_choice = int(choice(self.color_choices))
            return term.color(color_choice)(choice(self.animation))


map_dict = defaultdict(lambda: Map_tile(passable=False, blocking=True))
actor_dict = defaultdict(lambda: [None])
state_dict = defaultdict(lambda: None)
actor_dict['player'] = Actor(tile="@", health=100)
state_dict['facing'] = 'n'
actor_dict['player'].just_teleported = False
term = Terminal()

#Drawing functions---------------------------------------------------------------------------------

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
                #map_dict[(x, y)].tile = choice(palette)
                #map_dict[(x, y)].passable = passable
                #map_dict[(x, y)].blocking = blocking
                map_dict[(x, y)] = Map_tile(passable=True, tile=" ", blocking=False, 
                                         description='an animation', is_animated=True,
                                         animation=Animation(), actors=actors)
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
                #del actor_dict[actor]
                #del map_dict[segment_coord].actors[actor]
                
        await asyncio.sleep(speed)
    for segment_coord, segment_name in zip(reversed(segment_coords), reversed(sword_segment_names)):
        if segment_name in map_dict[segment_coord].actors: 
            del map_dict[segment_coord].actors[segment_name]
        del actor_dict[segment_name]
        await asyncio.sleep(speed)

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

async def is_clear_between(coord_a=(0, 0), coord_b=(5, 5)):
    """
    intended to be used for occlusion.
    show the tile that the first collision happened at but not the following tile
    TODO: doors are not visible
    """
    await asyncio.sleep(.01)
    open_space, walls, history = 0, 0, []
    points = await get_line(coord_a, coord_b)
    change_x, change_y = coord_b[0] - coord_a[0], coord_b[1] - coord_a[1]
    reference_point = coord_a[0], coord_a[1] + 5
    #get angle between two points so we can use it for magic doors
    for number, point in enumerate(points):
        remaining_points = ()
        # if there is a magic door between, start another is_clear_between of length remaining
        if map_dict[point].magic == True:
            last_point = points[-1]
            difference_from_last = last_point[0] - point[0], last_point[1] - point[1]
            destination = map_dict[point].magic_destination
            if difference_from_last is not (0, 0):
                coord_through_door = (destination[0] + difference_from_last[0], destination[1] + difference_from_last[1])
                if map_dict[coord_through_door].blocking:
                    return ' '
                if map_dict[coord_through_door].is_animated:
                    return next(map_dict[coord_through_door].animation)
                else:
                    return map_dict[coord_through_door].tile
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
    # check and make call for specific operating system
    _ = call('clear' if os.name =='posix' else 'cls')

def draw_door(x, y, closed = True):
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
    when a view_tile line of sight check passes through a tile that is magic,
    check what direction it's coming from
    when a tile is stepped on, a random effect happens:
        vines of noise_tiles spawning from stepped on tile?
        a flicker then fade of surrounding simliar tiles?
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
    map_dict[start_coord].tile = " "
    map_dict[start_coord].blocking = False
    map_dict[start_coord].passable = True
    map_dict[start_coord].magic = True
    map_dict[start_coord].magic_destination = end_coord
    map_dict[start_coord].is_animated = True
    map_dict[start_coord].animation = Animation(animation="▮", 
                                                   behavior='random', 
                                                   color_choices="1234567",
                                                   preset=None)
    while(True):
        await asyncio.sleep(.1)
        player_coords = actor_dict['player'].coords()
        just_teleported = actor_dict['player'].just_teleported
        if player_coords == start_coord and not just_teleported:
            asyncio.ensure_future(filter_print(output_text="You are teleported."))
            map_dict[player_coords].passable=True
            actor_dict['player'].update(*end_coord)
            actor_dict['player'].just_teleported = True

async def create_magic_door_pair(loop=None, door_a_coords=(5, 5), door_b_coords=(-25, -25)):
    loop.create_task(magic_door(start_coord=(door_a_coords), end_coord=(door_b_coords)))
    loop.create_task(magic_door(start_coord=(door_b_coords), end_coord=(door_a_coords)))

def map_init():
    clear()
    draw_box(top_left=(-25, -25), x_size=50, y_size=50, tile="░") #large debug room
    #sow_texture(20, 20, radius=50, seeds=500, color_num=7)
    draw_box(top_left=(-5, -5), x_size=10, y_size=10, tile="░")
    draw_centered_box(middle_coord=(-5, -5), x_size=10, y_size=10, tile="░")
    #map_dict[(3, 3)].tile = '☐'
    actor_dict['box'] = Actor(x_coord=5, y_coord=5, tile='☐')
    map_dict[(7, 7)].actors['box'] = True
    #map_dict[(7, 7)].magic = True
    #map_dict[(3, 3)].passable = False
    draw_box(top_left=(15, 15), x_size=10, y_size=10, tile="░")
    draw_box(top_left=(30, 15), x_size=10, y_size=10, tile="░")
    draw_box(top_left=(42, 10), x_size=20, y_size=20, tile="░")
    connect_with_passage(7, 7, 17, 17)
    connect_with_passage(17, 17, 25, 10)
    connect_with_passage(20, 20, 35, 20)
    connect_with_passage(0, 0, 17, 17)
    connect_with_passage(39, 20, 41, 20)
    draw_door(7, 16)
    draw_door(0, 5)
    write_description()
    draw_door(14, 17)
    draw_door(25, 20)
    draw_door(25, 20)
    draw_door(29, 20)
    draw_door(41, 20)
    #draw_circle(center_coord=(-30, -30))
    #connect_with_passage(0, 0, -30, -30)
    connect_with_passage(-30, -30, 0, 0)
    #sow_texture(55, 25, radius=5, seeds=10, palette=":,~.:\"`", color_num=1, 
                #passable=True, description="something gross")
    announcement_at_coord(coord=(0, 17), distance_trigger=5, announcement="something slithers into the wall as you approach.")
    announcement_at_coord(coord=(7, 17), distance_trigger=1, announcement="you hear muffled scratching from the other side")

def announcement_at_coord(coord=(0, 0), announcement="Testing...", distance_trigger=None):
    """
    creates a one-time announcement at coord.
    """
    #split announcement up into separate sequential pieces with pipes
    #pipes are parsed in view_tile
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


def rand_map(x_min=-50, x_max=50, y_min=-50, y_max=50, palette = "░",
             root_node_coords=(0, 0), rooms=10, root_room_size = (10, 10)):
    root_room_x_size, root_room_y_size = root_room_size
    floor_tile = choice(palette)
    draw_centered_box(middle_coord = root_node_coords, x_size=root_room_x_size, 
                      y_size=root_room_y_size, tile=floor_tile)
    room_centers = [(randint(x_min, x_max), randint(y_min, y_max)) for _ in range(rooms)]
    for room in room_centers:
        draw_centered_box(middle_coord=(20, 20), x_size=randint(5,15), y_size=randint(5, 15), tile=floor_tile)
        for _ in range(2):
            connection_choice = choice(room_centers)
            connect_with_passage(*room, *connection_choice, palette=floor_tile)
    connect_with_passage(*root_node_coords, *choice(room_centers), palette=floor_tile)

def isData(): 
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []) 

async def handle_input(key):
    """
    interpret keycodes and do various actions.
    """
    await asyncio.sleep(0)  
    x_shift, y_shift = 0, 0 
    x, y = actor_dict['player'].coords()
    directions = {'a':(-1, 0), 'd':(1, 0), 'w':(0, -1), 's':(0, 1), 
                  'A':(-10, 0), 'D':(10, 0), 'W':(0, -10), 'S':(0, 10),}
    key_to_compass = {'w':'n', 'a':'w', 's':'s', 'd':'e', 'i':'n', 'j':'w', 'k':'s', 'l':'e'}
    #generate dual cones of view for normal viewing_range and fuzzy edges
    #logic is split between here and view tile. it's a giant kludge.
    compass_directions = ('n', 'e', 's', 'w')
    fov = 100
    fuzz = 20
    view_tuples = [(i - fov/2, i, j, j + fov/2) for i, j in [(360, 0), (90, 90), (180, 180), (270, 270)]]
    view_angles = dict(zip(compass_directions, view_tuples))
    fuzzy_edges = [((i - fuzz), (j - fov/2), (k + fov/2), (l + fuzz)) for i, j, k, l in view_tuples]
    fuzzy_view_angles = dict(zip(compass_directions, fuzzy_edges))
    dir_to_name = {'n':'North', 'e':'East', 's':'South', 'w':'West'}
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
    if key in 'f':
        facing_dir = dir_to_name[state_dict['facing']]
        asyncio.ensure_future(filter_print(output_text="facing {}".format(facing_dir)))
    if key in '7':
        asyncio.ensure_future(draw_circle(center_coord=actor_dict['player'].coords())),
    if map_dict[(shifted_x, shifted_y)].passable and (shifted_x, shifted_y) is not (0, 0):
        map_dict[(x, y)].passable = True #make previous space passable
        actor_dict['player'].update(x + x_shift, y + y_shift)
        x, y = actor_dict['player'].coords()
        map_dict[(x, y)].passable = False #make current space impassable
    if key in "ijkl":
        with term.location(0, 5):
            print(view_angles[key_to_compass[key]])
        state_dict['facing'] = key_to_compass[key]
        state_dict['view_angles'] = view_angles[key_to_compass[key]]
        state_dict['fuzzy_view_angles'] = fuzzy_view_angles[key_to_compass[key]]
        with term.location(0, 6):
            print(state_dict['view_angles'], state_dict['view_angles'][0])
        #await sword(direction=key_to_compass[key])
    return x, y

async def point_to_point_distance(point_a=(0, 0), point_b=(5, 5)):
    """ finds 2d distance between two points """
    await asyncio.sleep(0)
    x_run = abs(point_a[0] - point_b[0])
    y_run = abs(point_a[1] - point_b[1])
    distance = round(sqrt(x_run ** 2 + y_run ** 2))
    return distance

async def parse_announcement(tile_key):
    """ parses an annoucement, with a new printing after each pipe """
    announcement_sequence = map_dict[tile_key].announcement.split("|")
    for delay, line in enumerate(announcement_sequence):
        asyncio.ensure_future(filter_print(output_text=line, delay=delay * 2))

async def trigger_announcement(tile_key, player_coords=(0, 0)):
    if map_dict[tile_key].announcing == True and map_dict[tile_key].seen == False:
        if map_dict[tile_key].distance_trigger:
            distance = await point_to_point_distance(tile_key, player_coords)
            if distance <= map_dict[tile_key].distance_trigger:
                await parse_announcement(tile_key)
                map_dict[tile_key].seen = True
        else:
            await parse_announcement(tile_key)
            map_dict[tile_key].seen = True
    else:
        map_dict[tile_key].seen = True


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
                                      reference_point=(0, 5), distance_from_center=30,
                                      rounded=True):
    """
    returns a point that lies at distance distance_from_center from point
    central_point. a is reference_point, b is central_point, c is returned point
    
        c
       /|
     r/ |y
     /  |
    a---b
      x
    """
    angle = 90 - angle_from_twelve
    print(angle)
    x = cos(angle) * distance_from_center
    y = sin(angle) * distance_from_center
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

async def view_tile(x_offset=1, y_offset=1, threshold = 18):
    """ handles displaying data from map_dict """
    #TODO:
    #fuzzy edges flicker too erratically. find smoother way.
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
            tile_key = (x_display_coord, y_display_coord)
            tile = map_dict[tile_key].tile
            if map_dict[tile_key].actors:
                actor_name = next(iter(map_dict[tile_key].actors))
                if actor_dict[actor_name].is_animated:
                    actor_tile = next(actor_dict[actor_name].animation)
                else:
                    actor_tile = actor_dict[actor_name].tile
            else:
                actor_tile = None
            if randint(0, round(distance)) < threshold:
                clear_between_result = await is_clear_between((player_x, player_y), tile_key)
                #if await is_clear_between((player_x, player_y), tile_key):
                if clear_between_result == True:
                    await trigger_announcement(tile_key, player_coords=(player_x, player_y))
                    if actor_tile:
                        print_choice = actor_tile
                    else:
                        if map_dict[tile_key].is_animated:
                            print_choice = next(map_dict[tile_key].animation)
                        else:
                            print_choice = tile
                elif clear_between_result != False and clear_between_result != None:
                    print_choice = clear_between_result
                else:
                    print_choice = ' '
            else:
                print_choice = choice(noise_palette)
        else:
            print_choice = ' '
        #if fuzzy and random() < .3:
            #print_choice = ' ' 
        with term.location(*print_location):
            if last_printed != print_choice:
                print(print_choice)
                last_printed = print_choice
        await asyncio.sleep(distance * .015)

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

async def seek(current_coord=(0, 0), name_key=None, seek_key='player'):
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

async def damage_door():
    """ allows actors to break down doors"""
    pass

async def tentacled_mass(start_coord=(-5, -5), speed=.5, tentacle_length_range=(3, 8),
                         tentacle_rate=.05, tentacle_colors="456"):
    """
    creates a (currently) stationary mass of random length and color tentacles
    move away while distance is far, move slowly towards when distance is near, radius = 20?
    """
    await asyncio.sleep(0)
    while True:
        await asyncio.sleep(tentacle_rate)
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
            coord = (actor_dict[shroud_name_key].x_coord, actor_dict[shroud_name_key].y_coord)
            if shroud_name_key in map_dict[coord].actors:
                del map_dict[coord].actors[shroud_name_key]
            behavior_val = random()
            if behavior_val < .2:
                new_coord = coord
            elif behavior_val > .6:
                new_coord = await wander(*coord, shroud_name_key)
            else:
                new_coord = await seek(current_coord=coord, name_key=shroud_name_key, 
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
            new_core_location = await seek(current_coord=core_location, 
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
            actor_dict[(name_key)].x_coord = coord[0]
            actor_dict[(name_key)].y_coord = coord[1]
            segment_tile_key = (movement_history[counter], movement_history[counter - 1])
            if segment_tile_key == (0, -1):
                actor_dict[(name_key)].tile = '1'
            else:
                actor_dict[(name_key)].tile = snake_segments[segment_tile_key]
            map_dict[coord].actors[name_key] = name_key
            counter += 1

async def basic_actor(start_x=0, start_y=0, speed=.1, tile="*", 
        movement_function=wander, name_key="test", hurtful=False,
        is_animated=False, animation=" "):
    """ A coroutine that creates a randomly wandering '*' """
    if len(tile) >= 1:
        animated = True
    actor_dict[(name_key)] = Actor(x_coord=start_x, y_coord=start_y, speed=speed, tile=tile, hurtful=hurtful,
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
            body_tile = term.red(actor_dict[name_key].tile)
            del actor_dict[name_key]
            del map_dict[coords].actors[name_key]
            await sow_texture(root_x=coords[0], root_y=coords[1], radius=5, paint=True, 
                              seeds=10, description="blood.")
            map_dict[coords].tile = body_tile
            map_dict[coords].description = "A body."
            return

async def constant_update_tile(x_offset=0, y_offset=0, tile=term.red('@')):
    await asyncio.sleep(1/30)
    middle_x, middle_y = (int(term.width / 2 - 2),
                          int(term.height / 2 - 2))
    while True:
        await asyncio.sleep(1/30)
        with term.location(middle_x, middle_y):
            print(tile)

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

async def vine_grow(start_x=0, start_y=0, actor_key="vine", 
                    rate=.1, vine_length=15, rounded=True,
                    behavior="retract", speed=.01, damage=20,
                    extend_wait=.025, retract_wait=.25,
                    color_num=2):
    """grows a vine starting at coordinates (start_x, start_y). Doesn't know about anything else.
    TODO: make vines stay within walls (a toggle between clipping and tunneling)
    TODO: vines can be pushed right now. Add immoveable property to actors. make vines immovable
    """
    await asyncio.sleep(rate)
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
    #vine_id = str(round(random(), 5))[2:]
    vine_id = str(datetime.time(datetime.now()))
    vine_actor_names = ["{}_{}_{}".format(actor_key, vine_id, number) for number in range(vine_length)]
    current_coord = (start_x, start_y)
    for vine_name in vine_actor_names:
        next_dir = randint(1, 4)
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

async def run_every_n(sec_interval=3, repeating_function=vine_grow, args=() ):
    while True:
        await asyncio.sleep(sec_interval)
        x, y = actor_dict['player'].coords()
        asyncio.ensure_future(repeating_function(*args))

async def sin_loop(state_dict_key="testsin", update_speed=.1, length=10):
    await asyncio.sleep(0)
    sins = [sin((pi/length) * i) for i in range(length * 2)]
    for num in cycle(sins):
        await asyncio.sleep(update_speed)
        state_dict[state_dict_key] = num

async def track_actor_location(state_dict_key="player", actor_dict_key="player", update_speed=.1, length=10):
    await asyncio.sleep(0)
    actor_coords = None
    while True:
        await asyncio.sleep(update_speed)
        actor_coords = (actor_dict['player'].x_coord, actor_dict['player'].y_coord)
        state_dict[state_dict_key] = actor_coords

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

async def health_test():
    while True:
        await asyncio.sleep(2)
        if state_dict["player_health"] < 100:
            state_dict["player_health"] += 1

async def view_init(loop, term_x_radius = 23, term_y_radius = 23, max_view_radius = 22):
    await asyncio.sleep(0)
    for x in range(-term_x_radius, term_x_radius + 1):
       for y in range(-term_y_radius, term_y_radius + 1):
           distance = sqrt(x**2 + y**2)
           #cull view_tile instances that are beyond a certain radius
           if distance < max_view_radius:
               loop.create_task(view_tile(x_offset=x, y_offset=y))

async def ui_tasks(loop):
    await asyncio.sleep(0)
    asyncio.ensure_future(ui_box_draw(x_margin=49, y_margin=35, box_width=23))
    asyncio.ensure_future(ui_box_draw(x_margin=-30, y_margin=10, box_width=5, box_height=3, position="centered"))
    asyncio.ensure_future(ui_box_draw(x_margin=30, y_margin=10, box_width=5, box_height=3, position="centered"))

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
    loop.create_task(ui_tasks(loop))
    #loop.create_task(basic_actor(*(7, 13), speed=.5, movement_function=seek, 
                                 #tile="Ϩ", name_key="test_seeker1", hurtful=True,
                                 #is_animated=True, animation=Animation(preset="blob")))
    #loop.create_task(basic_actor(*(35, 16), speed=.5, movement_function=seek, 
                                 #tile="Ϩ", name_key="test_seeker2", hurtful=True))
    loop.create_task(track_actor_location())
    loop.create_task(readout(is_actor=True, actor_name="player", attribute='coords', title="coords:"))
    loop.create_task(readout(bar=True, y_coord=36, actor_name='player', attribute='health', title="♥:"))
    #loop.create_task(shrouded_horror(start_x=-8, start_y=-8))
    loop.create_task(tentacled_mass())
    #loop.create_task(create_magic_door_pair(loop=loop))
    loop.create_task(create_magic_door_pair(loop=loop, door_a_coords=(-26, 3), door_b_coords=(25, 3)))
    loop.create_task(create_magic_door_pair(loop=loop, door_a_coords=(-26, 4), door_b_coords=(25, 4)))
    loop.create_task(create_magic_door_pair(loop=loop, door_a_coords=(-26, 5), door_b_coords=(25, 5)))
    #loop.create_task(magic_door(start_coord=(5, 5), end_coord=(-22, 18)))
    #loop.create_task(magic_door(start_coord=(-22, 18), end_coord=(5, 5)))
    loop.create_task(health_test())
    loop.create_task(death_check())
    asyncio.set_event_loop(loop)
    result = loop.run_forever()

#TODO: add an aiming reticule and/or a bullet actor that is spawned by a keypress
#TODO: add a function that returns the points of a path that goes until it hits the next wall.
    #for point in points in line, if passable, continue, else, 
    #return points up to but not including the current point

with term.hidden_cursor():
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        main()
    finally: 
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings) 
