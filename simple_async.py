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

# Variables:

size = 15 #width and height of tiles to be displayed

class Map_tile:
    """ holds the status and state of each tile. """
    def __init__(self, passable=True, tile=" "):
        """ create a new map tile, location is stored in map_dict"""
        self.passable, self.tile = (passable, tile)
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

map_dict = defaultdict(lambda: Map_tile(passable=False))
actor_dict = defaultdict(lambda: [None])
state_dict = defaultdict(lambda: None)
actor_dict['player'] = Actor(tile="@")
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
    else:
        map_dict[top_left].tile = tile
        map_dict[(x_tuple[1], y_tuple[1])].tile = tile
        for x in range(top_left[0], top_left[0] + x_size):
            y = top_left[1]
            map_dict[(x, y)].tile = tile
            y = top_left[1] + y_size
            map_dict[(x, y)].tile = tile
        for y in range(top_left[1], top_left[1] + y_size):
            x = top_left[0]
            map_dict[(x, y)].tile = tile
            x = top_left[0] + x_size
            map_dict[(x, y)].tile = tile

def draw_line(coord_a=(0, 0), coord_b=(5, 5), palette="░", passable=True):
    """draws a line to the map_dict connecting the two given points."""
    x1, y1, x2, y2 = (*coord_a,
                      *coord_b,)
    dx, dy = (x2 - x1,
              y2 - y1,)
    for x in range(x1, x2):
        y = y1 + dy * (x - x1) / dx
        map_dict[(round(x), round(y))].tile = choice(palette)
        map_dict[(round(x), round(y))].passable = passable

def connect_with_passage(x1, y1, x2, y2, segments=2, palette="░"):
    """fills a straight path first then fills the shorter leg, starting from the first coordinate"""
    if segments == 2:
        if abs(x2-x1) > abs(y2-y1):
            for x_coord in range(x1, x2+1):
                map_dict[(x_coord, y1)].tile = choice(palette)
                map_dict[(x_coord, y1)].passable = True
            for y_coord in range(y1, y2+1):
                map_dict[(x2, y_coord)].tile = choice(palette)
                map_dict[(x2, y_coord)].passable = True
        else:
            for y_coord in range(y1, y2+1):
                map_dict[(x1, y_coord)].tile = choice(palette)
                map_dict[(x1, y_coord)].passable = True
            for x_coord in range(x1, x2+1):
                map_dict[(x_coord, y2)].tile = choice(palette)
                map_dict[(x_coord, y2)].passable = True

def center_of_box(x_top_left, y_top_left, width_x, height_y):
    x_middle = round(x_top_left + width_x/2)
    y_middle = round(y_top_left + height_y/2)
    return (x_middle, y_middle)

def pick_point_in_cone(cone_left_edge, cone_right_edge):
    """returns a point at a given distance range in a clockwise propagating cone
    to be used for map creation"""
    pass

def sow_texture(root_x, root_y, palette=",.'\"`", radius=5, seeds=20, 
                passable=False):
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
        map_dict[toss_coord].tile = random_tile
        map_dict[toss_coord].passable = passable

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

def map_init():
    clear()
    sow_texture(20, 20, radius=50, seeds=500)
    #sow_texture(30, 30, radius=20, seeds=200)
    #draw_box(top_left=(-10, -10), x_size=5, y_size=5, tile=term.blue("#"), filled=False)
    #draw_box(top_left=(-5, -5), x_size=10, y_size=10, tile=".", filled=False)
    draw_box(top_left=(-5, -5), x_size=10, y_size=10, tile="░")
    draw_box(top_left=(5, 5), x_size=10, y_size=10, tile="░")
    draw_box(top_left=(15, 15), x_size=10, y_size=10, tile="░")
    draw_box(top_left=(30, 15), x_size=10, y_size=10, tile="░")
    connect_with_passage(7, 7, 17, 17)
    connect_with_passage(17, 17, 25, 10)
    connect_with_passage(20, 20, 35, 20)
    connect_with_passage(0, 0, 17, 17)

    #draw_line(coord_a=(x1, y1), coord_b=(x1, y2), palette=palette)
    #draw_line(coord_a=(x1, y2), coord_b=(x2, y2), palette=palette)
    #draw_box(top_left=(-15, 0), x_size=3, y_size=3, tile=term.yellow("!"), passable=False)
    #draw_line()

def isData(): ##
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []) ##

async def handle_input(key):
    """interpret keycodes and do various actions."""
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
    if map_dict[(shifted_x, shifted_y)].passable:
        actor_dict['player'].x_coord += x_shift
        actor_dict['player'].y_coord += y_shift
    return actor_dict['player'].x_coord, actor_dict['player'].y_coord

async def view_tile(x_offset=1, y_offset=1, distance_effects = False):
    """ handles displaying data from map_dict """
    #await asyncio.sleep(random()/10)
    distance = sqrt(abs(x_offset)**2 + abs(y_offset)**2) #
    await asyncio.sleep(random()/5)
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    previous_actor, previous_tile, actor = None, None, None
    distance_pause = distance 
    print_location = (middle_x + x_offset, middle_y + y_offset)
    while(1):
        if distance_effects:
            if distance >= 5:
                with term.location(*print_location):
                    print(" ")
            await asyncio.sleep(distance_pause * random())
        else:
            await asyncio.sleep(.01)
            distance_pause = 1
        for repeat in range(int(distance_pause)):
            await asyncio.sleep(random()/distance_pause)
            x, y = (actor_dict['player'].x_coord + x_offset,
                    actor_dict['player'].y_coord + y_offset,)
            tile_key = (x, y)
            tile = map_dict[tile_key].tile
            if map_dict[tile_key].actors:
                map_dict_key = next(iter(map_dict[tile_key].actors))
                actor = actor_dict[map_dict_key].tile
            else:
                actor = None
            if actor == previous_actor and tile == previous_tile:
                continue
            with term.location(*print_location):
                if actor:
                    print(actor)
                else:
                   print(tile)
            previous_tile, previous_actor = tile, actor

async def noise_tile(x_offset, y_offset, threshhold=10):
    """ breaks out noisy tile code into a separate routine 

    flickers in and out depending on how distant it is from player

    probability of showing new information (rather than grey last known state)
    is based on euclidean distance from player
    """
    pass
    #noise = "▓▒░░░░▖▗▘▙▚▛▜▝▞▟"
    #distance = sqrt(abs(x_offset)**2 + abs(y_offset)**2) #
    #await asyncio.sleep(distance/10) #changing delay by distance creates an expanding circle
    #random_noise = choice(noise)
    #flicker_state = randint(0, int(distance))
    #if flicker_state < threshhold:
    #else:
    #print(random_noise)

async def shaded_tile(x=15, y=15, on_percent=.5, rate=.01, tile="#"):
    await asyncio.sleep(0)
    wait_on = rate * on_percent
    wait_off = rate - (rate * on_percent)
    while(1):
        with term.location(x, y):
            print(tile)
        await asyncio.sleep(wait_on)
        with term.location(x, y):
            print(" ")
        await asyncio.sleep(wait_off)

async def timer(x_pos=0, y_pos=10, time_minutes=0, time_seconds=5, resolution=1):
    await asyncio.sleep(0)
    timer_text = str(time_minutes).zfill(2) + ":" + str(time_seconds).zfill(2)
    while(1):
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

async def wander(x_current, y_current, name_key):
    """ 
    randomly increments or decrements x_current and y_current
    if square to be moved to is passable
   
    TODO:implement movements to be made as a palette to be pulled from, using 0-9
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
    with term.location(0, 10):
        print("seeking:{}".format(seek_key))
        print("active:{}".format(name_key))
        print("{},{}      ".format(target_x, target_y))
        print("{},{}      ".format(active_x, active_y))
        print("{},{}      ".format(diff_x, diff_y))
    if diff_x > 0 and map_dict[(active_x - 1, active_y)].passable:
        active_x -= 1
    if diff_x < 0 and map_dict[(active_x + 1, active_y)].passable:
        active_x += 1
    if diff_y > 0 and map_dict[(active_x, active_y - 1)].passable:
        active_y -= 1
    if diff_y < 0 and map_dict[(active_x, active_y + 1)].passable:
        active_y += 1
    actor_dict[(name_key)].x_coord = active_x
    actor_dict[(name_key)].y_coord = active_y
    return (active_x, active_y)
    
async def get_actor_coords(name_key):
    await asyncio.sleep(0)
    actor_x = actor_dict[name_key].x_coord
    actor_y = actor_dict[name_key].y_coord
    actor_coords = (actor_x, actor_y)
    return actor_coords

async def snake(start_x=0, start_y=0, speed=.1, head="0", length=5, name_key="snake"):
    """
    the head is always index 0, followed by the rest of the list for each segment.
    when the head moves to a new cell, the next segment in line takes it's coordinates.
    """
    await asyncio.sleep(0)
    segment_locations = [(start_x, start_y)] * length
    rand_direction = randint(1, 4)
    snake_segments = {(1, 2):'╭', (4, 3):'╭', (2, 3):'╮', (1, 4):'╮', (1, 1):'│', (3, 3):'│', 
            (3, 4):'╯', (2, 1):'╯', (3, 2):'╰', (4, 1):'╰', (2, 2):'─', (4, 4):'─', }
    movement_tuples = {1:(0, -1), 2:(1, 0), 3:(0, 1), 4:(-1, 0)}
    segment_names = []
    movement_history = [1] * 10
    for number, segment_coord in enumerate(segment_locations):
        segment_names.append("{}_seg_{}".format(name_key, number))
        actor_dict[(segment_names[-1])] = Actor(x_coord=segment_coord[0], y_coord=segment_coord[1])
    new_x, new_y = 0, 0 
    while 1:
        await asyncio.sleep(speed)
        #deleting all traces of the snake segments from the map_dict's actor list:
        for name_key, coord in zip(segment_names, segment_locations):
            if name_key in map_dict[coord].actors:
                del map_dict[coord].actors[name_key]
        segment_locations.pop()
        #creating a new head location:
        while (new_x, new_y) in segment_locations:
            rand_direction = randint(1, 4)
            movement_history.pop()
            movement_history.insert(0, rand_direction)
            rand_direction_tuple = movement_tuples[rand_direction]
            await asyncio.sleep(0)
            new_x, new_y = (segment_locations[0][0] + rand_direction_tuple[0],
                            segment_locations[0][1] + rand_direction_tuple[1],)
        new_head_coord = (new_x, new_y)
        segment_locations.insert(0, new_head_coord)
        #write the new locations of each segment to the map_dict's tiles' actor lists
        for name_key, coord in zip(segment_names, segment_locations):
            actor_dict[(name_key)].x_coord = coord[0]
            actor_dict[(name_key)].y_coord = coord[1]
            #TODO: fix snake tile display
            #segment_tile_key = (movement_history[int(name_key[-1])], movement_history[int(name_key[-1]) + 1])
            segment_tile_key = 'O'
            with term.location(0, 3):
                print(segment_tile_key)
            if segment_tile_key in snake_segments:
                actor_dict[(name_key)].tile = snake_segments[segment_tile_key]
            else:
                actor_dict[(name_key)].tile = 'o'
            map_dict[coord].actors[name_key] = name_key
        with term.location(0, 0):
            print(segment_locations)
        with term.location(0, 1):
            print(movement_history)

async def basic_actor(start_x=0, start_y=0, speed=.2, tile="*", movement_function=wander, name_key="test"):
    """ A coroutine that creates a randomly wandering '*' """
    actor_dict[(name_key)] = Actor(x_coord=start_x, y_coord=start_y, speed=speed, tile=tile)
    actor_dict[(name_key)].x_coord = start_x
    actor_dict[(name_key)].y_coord = start_y
    coords = await get_actor_coords(name_key)
    while 1:
        await asyncio.sleep(speed)
        if name_key in map_dict[coords].actors:
            del map_dict[coords].actors[name_key]
        coords = await movement_function(x_current=coords[0], y_current=coords[1], name_key=name_key)
        map_dict[coords].actors[name_key] = name_key

async def constant_update_tile(x_offset=0, y_offset=0, tile=term.red('@')):
    await asyncio.sleep(1/30)
    middle_x, middle_y = (int(term.width / 2 - 2),
                          int(term.height / 2 - 2))
    while(1):
        await asyncio.sleep(1/30)
        with term.location(middle_x, middle_y):
            print(tile)

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
    while(1):
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
    while(1):
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
    while(1):
        with term.location(5, 5):
            print("{:8}".format(str(actor_coords)))
        await asyncio.sleep(update_speed)
        actor_coords = (actor_dict['player'].x_coord, actor_dict['player'].y_coord)
        state_dict[state_dict_key] = actor_coords

async def readout(x_coord=0, y_coord=7, listen_to_key=None, update_rate=.1, float_len=3, title=None):
    """listen to a specific key of state_dict
    state dict changes over time according to things happening in other loops """
    await asyncio.sleep(0)
    while(1):
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

def main():
    map_init()
    old_settings = termios.tcgetattr(sys.stdin) ##
    loop = asyncio.new_event_loop()
    loop.create_task(get_key())
    for x in range(-size, size):
        for y in range(-size, size):
            loop.create_task(view_tile(x_offset=x, y_offset=y))
    loop.create_task(basic_actor(*(10, 10), speed=.5, movement_function=seek, tile="%", name_key="test_seeker"))
    loop.create_task(constant_update_tile())
    #for i in range(1,100):
        #loop.create_task(shaded_tile(x=i + 1, on_percent=(i/10)))
    loop.create_task(snake())
    #loop.create_task(timer())
    #loop.create_task(run_every_n())
    #loop.create_task(sin_loop(state_dict_key="sin_loop"))
    #loop.create_task(track_actor_location())
    loop.create_task(readout(x_coord=0, y_coord=5, listen_to_key="player", title="player_coords:"))
    asyncio.set_event_loop(loop)
    result = loop.run_forever()

with term.hidden_cursor():
    main()
