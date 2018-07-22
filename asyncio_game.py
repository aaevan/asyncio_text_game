import asyncio
import sys
import select 
import tty 
import termios
from blessings import Terminal
from collections import defaultdict
from random import randint, choice, random, shuffle
from math import sqrt, sin, pi
from itertools import cycle
from subprocess import call
import os

class Map_tile:
    """ holds the status and state of each tile. """
    def __init__(self, passable=True, tile=" ", blocking=True, description='', announcing=False, seen=False, announcement="", distance_trigger=None):
        """ create a new map tile, location is stored in map_dict"""
        self.passable, self.tile, self.blocking, self.description = (passable, tile, blocking, description)
        self.announcing, self.seen, self.announcement = announcing, seen, announcement
        self.distance_trigger = distance_trigger
        self.actors = defaultdict(lambda:None)

class Actor:
    """ the representation of a single actor that lives on the map. """
    def __init__(self, x_coord=0, y_coord=0, speed=.2, tile="?"):
        """ create a new actor at position x, y """
        self.x_coord, self.y_coord, = (x_coord, y_coord)
        self.speed, self.tile = (speed, tile)

    def update(x, y):
        self.x_coord, self.y_coord = x, y

    def coords():
        return (self.x_coord, self.y_coord)

map_dict = defaultdict(lambda: Map_tile(passable=False, blocking=True))
actor_dict = defaultdict(lambda: [None])
state_dict = defaultdict(lambda: None)
actor_dict['player'] = Actor(tile="@")
term = Terminal()

#TODO make actors display messages when near a door at random intervals, "you hear a scratching sound"

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
            #map_dict[(x, y)].tile = tile
        for y in range(top_left[1], top_left[1] + y_size):
            for x in [top_left[0], top_left[0] + x_size]:
                map_dict[(x, y)].tile = tile
            #map_dict[(x, y)].tile = tile

def draw_centered_box(middle_coord=(0, 0), x_size=10, y_size=10, 
                  filled=True, tile=".", passable=True):
    top_left = (middle_coord[0] - int(x_size/2), middle_coord[1] - int(y_size/2))
    draw_box(top_left=top_left, x_size=x_size, y_size=10, filled=True, tile=tile)

async def draw_line(coord_a=(0, 0), coord_b=(5, 5), palette="*", passable=True, blocking = False):
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
    for point in points:
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
                       pause_fade_in=.01, pause_fade_out=.01, pause_stay_on=1, delay=0):
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
        await asyncio.sleep(pause_fade_in)
    shuffle(numbered_chars)
    await asyncio.sleep(pause_stay_on)
    for char in numbered_chars:
        with term.location(char[0] + x_location, y_location):
            print(' ')
        await asyncio.sleep(pause_fade_out)

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

def sow_texture(root_x, root_y, palette=",.'\"`", radius=5, seeds=20, 
                passable=False, color_num=7, description=''):
    """ given a root node, picks random points within a radius length and writes
    characters from the given palette to their corresponding map_dict cell.
    """
    for i in range(seeds):
        throw_dist = radius + 1
        while throw_dist >= radius:
            x_toss, y_toss = (randint(-radius, radius),
                              randint(-radius, radius),)
            throw_dist = sqrt(x_toss**2 + y_toss**2) #euclidean distance
        toss_coord = (root_x + x_toss, root_y + y_toss)
        random_tile = choice(palette)
        map_dict[toss_coord].tile = term.color(color_num)(random_tile)
        #map_dict[toss_coord].tile = random_tile
        map_dict[toss_coord].passable = passable
        if description:
            map_dict[toss_coord].description = description

async def flood_fill(coord=(0, 0), target='/', replacement=' ', depth=0,
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

def is_magic_door(x_pos, y_pos):
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

def map_init():
    clear()
    #draw_box(top_left=(-25, -25), x_size=50, y_size=50, tile="░") #large debug room
    sow_texture(20, 20, radius=50, seeds=500, color_num=7)
    draw_box(top_left=(-5, -5), x_size=10, y_size=10, tile="░")
    draw_centered_box(middle_coord=(-5, -5), x_size=10, y_size=10, tile="░")
    map_dict[(3, 3)].tile = '☐'
    map_dict[(3, 3)].passable = False
    #draw_box(top_left=(6, 6), x_size=9, y_size=10, tile="░")
    #announcement_at_coord(coord=(9,9), announcement="a room where things happen")
    draw_box(top_left=(15, 15), x_size=10, y_size=10, tile="░")
    draw_box(top_left=(30, 15), x_size=10, y_size=10, tile="░")
    draw_box(top_left=(42, 10), x_size=20, y_size=20, tile="░")
    #announcement_at_coord(coord=(61, 20), announcement=rant)
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
    sow_texture(55, 25, radius=5, seeds=10, palette=":,~.:\"`", color_num=1, 
                passable=True, description="something gross")
    announcement_at_coord(coord=(0, 17), distance_trigger=5, announcement="something slithers into the wall as you approach.")
    announcement_at_coord(coord=(7, 17), distance_trigger=1, announcement="you hear muffled scratching from the other side")
    #rand_map()

def announcement_at_coord(coord=(0, 0), announcement="Testing...", distance_trigger=None):
    #split announcement up into separate sequential pieces with pipes
    #pipes are parsed in view_tile
    #lines = announcement.split('|')
    map_dict[coord].announcement = announcement
    map_dict[coord].announcing = True
    map_dict[coord].distance_trigger = distance_trigger

async def sequential_announcement_parse():
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
    """interpret keycodes and do various actions.
    implement pushing a box around 
    """
    await asyncio.sleep(0)  
    x_shift, y_shift = 0, 0 
    x, y = (actor_dict['player'].x_coord,
            actor_dict['player'].y_coord,)
    directions = {'a':(-1, 0), 'd':(1, 0), 'w':(0, -1), 's':(0, 1), 
                  'A':(-10, 0), 'D':(10, 0), 'W':(0, -10), 'S':(0, 10),}
    if key in directions:
        x_shift, y_shift = directions[key]
    shifted_x, shifted_y = (actor_dict['player'].x_coord + x_shift,
                            actor_dict['player'].y_coord + y_shift,)
    if key in 'Vv':
        asyncio.ensure_future(vine_grow(start_x=x, start_y=y)),
    if key in 'Ee':
        description = map_dict[(x, y)].description
        asyncio.ensure_future(filter_print(output_text=description)),
    if key in ' ':
        asyncio.ensure_future(toggle_doors()),
    if key in '4':
        asyncio.ensure_future(filter_print()),
    if map_dict[(shifted_x, shifted_y)].passable:
        map_dict[(x, y)].passable = True
        actor_dict['player'].x_coord += x_shift
        actor_dict['player'].y_coord += y_shift
        x, y = (actor_dict['player'].x_coord,
                actor_dict['player'].y_coord,)
        map_dict[(x, y)].passable = False
    return actor_dict['player'].x_coord, actor_dict['player'].y_coord

async def debug_grid(x_print_coord=0, y_print_coord=6):
    """
    print a grid of ones and zeroes running is_clear_between on the area surrounding player location.
    """
    await asyncio.sleep(0)
    player_x, player_y = (actor_dict['player'].x_coord,
                          actor_dict['player'].y_coord)
    output_array = [[0 for i in range(10)] for j in range(10)]
    for x_index, x_coord in enumerate(range(-5, 5)):
        for y_index, y_coord in enumerate(range(-5, 5)):
            if (x_coord, y_coord) == (player_x, player_y):
                output_array[y_index][x_index] = '@'
            else:
                target_tuple = (player_x + x_coord, player_y + y_coord)
                output_array[y_index][x_index] = int(await is_clear_between((player_x, player_y), target_tuple))
    with term.location(x_print_coord, y_print_coord):
        for row in output_array:
            print(''.join([str(i) for i in row]))

async def point_to_point_distance(point_a=(0, 0), point_b=(5, 5)):
    x_run = abs(point_a[0] - point_b[0])
    y_run = abs(point_a[1] - point_b[1])
    distance = round(sqrt(x_run ** 2 + y_run ** 2))
    return distance

async def parse_announcement(tile_key):
    announcement_sequence = map_dict[tile_key].announcement.split("|")
    for delay, line in enumerate(announcement_sequence):
        asyncio.ensure_future(filter_print(output_text=line, delay=delay * 2))

async def trigger_announcement(tile_key, player_coords=(0, 0)):
    if map_dict[tile_key].announcing == True and map_dict[tile_key].seen == False:
        if map_dict[tile_key].distance_trigger:
            distance = await point_to_point_distance(tile_key, player_coords)
            if distance <= map_dict[tile_key].distance_trigger:
                with term.location(0, 30):
                    print("triggered tile {}".format(tile_key))
                await parse_announcement(tile_key)
                map_dict[tile_key].seen = True
            else:
                with term.location(0, 30):
                    print("not close enough...")
                pass
        else:
            await parse_announcement(tile_key)
            map_dict[tile_key].seen = True
    #elif not map_dict[tile_key].distance_trigger:
    else:
        map_dict[tile_key].seen = True

async def view_tile(x_offset=1, y_offset=1, threshold = 12):
    """ handles displaying data from map_dict """
    noise_palette = " " * 5
    distance = sqrt(abs(x_offset)**2 + abs(y_offset)**2) #
    await asyncio.sleep(random()/5 * distance)
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    previous_actor, previous_tile, actor = None, None, None
    print_location = (middle_x + x_offset, middle_y + y_offset)
    last_printed = ' '
    while True:
        await asyncio.sleep(.01)
        player_x, player_y = (actor_dict['player'].x_coord,
                              actor_dict['player'].y_coord)
        x, y = (actor_dict['player'].x_coord + x_offset,
                actor_dict['player'].y_coord + y_offset,)
        tile_key = (x, y)
        tile = map_dict[tile_key].tile
        if map_dict[tile_key].actors:
            map_dict_key = next(iter(map_dict[tile_key].actors))
            actor = actor_dict[map_dict_key].tile
        else:
            actor = None
        if randint(0, round(distance)) < threshold:
            if await is_clear_between((player_x, player_y), (x, y)):
                await trigger_announcement(tile_key, player_coords=(player_x, player_y))
                if actor:
                    print_choice = actor
                else:
                    print_choice = tile
            else:
                print_choice = ' '
        else:
            print_choice = choice(noise_palette)
        with term.location(*print_location):
            if last_printed != print_choice:
                print(print_choice)
                last_printed = print_choice
            await asyncio.sleep(distance * .015)

async def shaded_tile(x=15, y=15, on_percent=.5, rate=.01, tile="#"):
    await asyncio.sleep(0)
    wait_on = rate * on_percent
    wait_off = rate - (rate * on_percent)
    while True:
        with term.location(x, y):
            print(tile)
        await asyncio.sleep(wait_on)
        with term.location(x, y):
            print(" ")
        await asyncio.sleep(wait_off)

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
            x, y = (actor_dict['player'].x_coord,
                    actor_dict['player'].y_coord,)
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
    next_move = (x_current + x_move, y_current + y_move)
    if map_dict[next_move].passable:
        x_current += x_move
        y_current += y_move
        actor_dict[(name_key)].x_coord = x_current
        actor_dict[(name_key)].y_coord = y_current
    return (x_current, y_current)

async def seek(x_current, y_current, name_key, seek_key='player'):
    """ Standardize format to pass movement function.  """
    await asyncio.sleep(0)
    target_x, target_y = actor_dict[seek_key].x_coord, actor_dict[seek_key].y_coord
    active_x, active_y = x_current, y_current
    diff_x, diff_y = (active_x - target_x), (active_y - target_y)
    if diff_x > 0 and map_dict[(active_x - 1, active_y)].passable:
        active_x -= 1
    if diff_x < 0 and map_dict[(active_x + 1, active_y)].passable:
        active_x += 1
    if diff_y > 0 and map_dict[(active_x, active_y - 1)].passable:
        active_y -= 1
    if diff_y < 0 and map_dict[(active_x, active_y + 1)].passable:
        active_y += 1
    return (active_x, active_y)
    
async def get_actor_coords(name_key):
    await asyncio.sleep(0)
    actor_x = actor_dict[name_key].x_coord
    actor_y = actor_dict[name_key].y_coord
    actor_coords = (actor_x, actor_y)
    return actor_coords

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
        #await asyncio.sleep(speed)
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
            #with term.location(0, 13):
                #print(movement_history)
            #with term.location(0, 15 + counter):
                #print(name_key, coord)
            actor_dict[(name_key)].x_coord = coord[0]
            actor_dict[(name_key)].y_coord = coord[1]
            #segment_tile_key = (movement_history[int(name_key[-1])], movement_history[int(name_key[-1]) + 1])
            segment_tile_key = (movement_history[counter], movement_history[counter - 1])
            #with term.location(24, 15 + counter):
                #print(movement_history[counter], movement_history[counter - 1])
            if segment_tile_key == (0, -1):
                actor_dict[(name_key)].tile = '1'
            else:
                #assign tile:
                #with term.location(0, 30 + counter):
                    #print(segment_tile_key)
                actor_dict[(name_key)].tile = snake_segments[segment_tile_key]
                #with term.location(21, 15 + counter):  ###
                    #print(actor_dict[(name_key)].tile) ###
            map_dict[coord].actors[name_key] = name_key
            counter += 1

async def basic_actor(start_x=0, start_y=0, speed=.2, tile="*", 
        movement_function=wander, name_key="test"):
    """ A coroutine that creates a randomly wandering '*' """
    if len(tile) >= 1:
        animated = True
    actor_dict[(name_key)] = Actor(x_coord=start_x, y_coord=start_y, speed=speed, tile=tile)
    actor_dict[(name_key)].x_coord = start_x
    actor_dict[(name_key)].y_coord = start_y
    coords = await get_actor_coords(name_key)
    while True:
        #if animated:
        #    actor_dict[(name_key)]
        await asyncio.sleep(speed)
        if name_key in map_dict[coords].actors:
            del map_dict[coords].actors[name_key]
        coords = await movement_function(x_current=coords[0], y_current=coords[1], name_key=name_key)
        map_dict[coords].actors[name_key] = name_key

async def constant_update_tile(x_offset=0, y_offset=0, tile=term.red('@')):
    await asyncio.sleep(1/30)
    middle_x, middle_y = (int(term.width / 2 - 2),
                          int(term.height / 2 - 2))
    while True:
        await asyncio.sleep(1/30)
        with term.location(middle_x, middle_y):
            print(tile)

async def toggle_doors():
    x, y = (actor_dict['player'].x_coord,
            actor_dict['player'].y_coord,)
    door_dirs = {(-1, 0), (1, 0), (0, -1), (0, 1)}
    for door in door_dirs:
        door_coord_tuple = (x + door[0], y + door[1])
        door_state = map_dict[door_coord_tuple].tile 
        if door_state == "▮":
            #asyncio.ensure_future(filter_print(output_text = "You open the door."))
            map_dict[door_coord_tuple].tile = '▯'
            map_dict[door_coord_tuple].passable = True
            map_dict[door_coord_tuple].blocking = False
        elif door_state == '▯':
            #asyncio.ensure_future(filter_print(output_text = "You close the door."))
            map_dict[door_coord_tuple].tile = '▮'
            map_dict[door_coord_tuple].passable = False
            map_dict[door_coord_tuple].blocking = True

async def vine_grow(start_x=0, start_y=0, actor_key="vine", 
                    rate=.001, death_clock=100, rounded=True):
    """grows a vine starting at coordinates (start_x, start_y). Doesn't know about anything else."""
    await asyncio.sleep(rate)
    current_coord = (start_x, start_y)
    if not rounded:
        vine_picks = {(1, 2):'┌', (4, 3):'┌', (2, 3):'┐', (1, 4):'┐', (1, 1):'│', (3, 3):'│', 
                (3, 4):'┘', (2, 1):'┘', (3, 2):'└', (4, 1):'└', (2, 2):'─', (4, 4):'─', }
    else:
        vine_picks = {(1, 2):'╭', (4, 3):'╭', (2, 3):'╮', (1, 4):'╮', (1, 1):'│', (3, 3):'│', 
                (3, 4):'╯', (2, 1):'╯', (3, 2):'╰', (4, 1):'╰', (2, 2):'─', (4, 4):'─', }
    exclusions = {(2, 4), (4, 2), (1, 3), (3, 1), }
    vines = [term.green(i) for i in "┌┐└┘─│"]
    prev_dir, next_dir = randint(1, 4), randint(1, 4)
    movement_tuples = {1:(0, -1), 2:(1, 0), 3:(0, 1), 4:(-1, 0)}
    next_tuple = movement_tuples[next_dir]
    while True:
        await asyncio.sleep(rate)
        next_dir = randint(1, 4)
        while (prev_dir, next_dir) in exclusions:
            next_dir = randint(1, 4)
        next_tuple, vine_tile = (movement_tuples[next_dir], 
                                 vine_picks[(prev_dir, next_dir)])
        if map_dict[current_coord].tile not in vines:
            map_dict[current_coord].tile = term.green(vine_tile)
        current_coord = (current_coord[0] + next_tuple[0], current_coord[1] + next_tuple[1])
        prev_dir = next_dir
        death_clock -= 1
        if death_clock <= 0:
            return

async def run_every_n(sec_interval=3, repeating_function=vine_grow, args=() ):
    while True:
        await asyncio.sleep(sec_interval)
        x, y = (actor_dict['player'].x_coord,
                actor_dict['player'].y_coord,)
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
        with term.location(5, 5):
            print("{:8}".format(str(actor_coords)))
        await asyncio.sleep(update_speed)
        actor_coords = (actor_dict['player'].x_coord, actor_dict['player'].y_coord)
        state_dict[state_dict_key] = actor_coords

async def readout(x_coord=0, y_coord=7, listen_to_key=None, update_rate=.1, float_len=3, title=None):
    """listen to a specific key of state_dict
    state dict changes over time according to things happening in other loops 
    modify to be able to display status bars, ie, 'LIFE:█████░░░░░'
    """
    await asyncio.sleep(0)
    while True:
        await asyncio.sleep(0)
        key_value = state_dict[listen_to_key]
        if type(key_value) is float:
            if title:
                with term.location(x_coord, y_coord):
                    print("{}:{:6.3f}".format(title, key_value))
            else:
                with term.location(x_coord, y_coord):
                    print("{:6.3f}".format(key_value))
        else:
            pass

async def view_init(loop, term_x_radius = 20, term_y_radius = 20, max_view_radius = 18):
    await asyncio.sleep(0)
    for x in range(-term_x_radius, term_x_radius + 1):
       for y in range(-term_y_radius, term_y_radius + 1):
           distance = sqrt(x**2 + y**2)
           #cull view_tile instances that are beyond a certain radius
           if distance < max_view_radius:
               loop.create_task(view_tile(x_offset=x, y_offset=y))

async def ui_tasks(loop):
    await asyncio.sleep(0)

def main():
    map_init()
    old_settings = termios.tcgetattr(sys.stdin) 
    loop = asyncio.new_event_loop()
    loop.create_task(get_key())
    loop.create_task(view_init(loop))
    #loop.create_task(snake())
    loop.create_task(basic_actor(*(7, 13), speed=.5, movement_function=seek, tile="Ø", name_key="test_seeker1"))
    loop.create_task(constant_update_tile())
    loop.create_task(track_actor_location())
    loop.create_task(readout(x_coord=0, y_coord=5, listen_to_key="player", title="player_coords:"))
    asyncio.set_event_loop(loop)
    result = loop.run_forever()

with term.hidden_cursor():
    main()
