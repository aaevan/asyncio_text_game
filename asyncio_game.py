import asyncio
import os
import sys
import select 
import tty 
import termios
import numpy as np
from blessings import Terminal
from copy import copy, deepcopy
from collections import defaultdict
from datetime import datetime
from itertools import cycle, repeat, combinations
from math import acos, cos, degrees, pi, radians, sin, sqrt
from random import randint, choice, gauss, random, shuffle
from subprocess import call
from time import sleep

#Class definitions--------------------------------------------------------------

class Map_tile:
    """ holds the status and state of each tile. """
    def __init__(self, passable=True, tile='𝄛', blocking=True, 
                 description='', announcing=False, seen=False, 
                 announcement='', distance_trigger=None, is_animated=False,
                 animation='', actors=None, items=None, 
                 magic=False, magic_destination=False, 
                 mutable=True, override_view=False,
                 is_door=False, locked=False, key=''):
        """ create a new map tile, map_dict holds tiles.
        A Map_tile is accessed from map_dict via a tuple key, ex. (0, 0).
        The tile representation of Map_tile at coordinate (0, 0) is accessed 
        with map_dict[(0, 0)].tile.
        actors is a dictionary of actor names with value == True if 
        occupied by that actor, otherwise the key is deleted.
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
        self.mutable = mutable
        self.override_view = override_view
        self.is_door = is_door
        self.locked = locked
        self.key = key

class Actor:
    """ the representation of a single actor that lives on the map. """
    def __init__(self, name='', x_coord=0, y_coord=0, speed=.2, tile="?", 
                 strength=1, health=50, stamina=50, hurtful=True, moveable=True,
                 is_animated=False, animation="", holding_items={}, 
                 leaves_body=False, breakable=False, multi_tile_parent=None, 
                 blocking=False):
        self.name = name
        self.x_coord, self.y_coord, = (x_coord, y_coord)
        self.speed, self.tile = (speed, tile)
        self.coord = (x_coord, y_coord)
        self.strength, self.health, self.hurtful = strength, health, hurtful
        self.stamina = stamina
        self.max_health = self.health #max health is set to starting value
        self.alive = True
        self.moveable = moveable
        self.is_animated = is_animated
        self.animation = animation
        self.leaves_body = leaves_body
        self.holding_items = holding_items
        self.breakable = breakable
        self.last_location = (x_coord, y_coord)
        self.multi_tile_parent = multi_tile_parent
        self.blocking = blocking

    def update(self, x, y):
        self.last_location = (self.x_coord, self.y_coord)
        if self.name in map_dict[self.coords()].actors:
            del map_dict[self.coords()].actors[self.name]
        self.x_coord, self.y_coord = x, y
        map_dict[self.coords()].actors[self.name] = True

    def coords(self):
        return (self.x_coord, self.y_coord)

    def move_by(self, coord_move=None, x_move=None, y_move=None):
        if x_move:
            self.x_coord = self.x_coord + x_move
        if y_move:
            self.y_coord = self.y_coord + y_move
        if coord_move:
            self.x_coord, self.y_coord = (self.x_coord + coord_move[0], 
                                          self.y_coord + coord_move[1])

class Animation:
    def __init__(self, animation=None, base_tile='o', behavior=None, color_choices=None, 
                 preset="none", background=None):
        presets = {'fire':{'animation':'^∧', 
                           'behavior':'random', 
                           'color_choices':'3331'},
                  'water':{'animation':'███████▒▓▒', 
                           'behavior':'walk both',
                           'color_choices':('446')},
                  'grass':{'animation':('▒' * 20 + '▓'), 
                           'behavior':'random',
                           'color_choices':('2'),},
                   'blob':{'animation':('ööööÖ'),
                           'behavior':'loop tile',
                           'color_choices':('2')},
                  'mouth':{'animation':('▲▸▼◀'),
                           'behavior':'loop tile',
                           'color_choices':('456')},
                  'noise':{'animation':('      ▒▓▒ ▒▓▒'), 
                           'behavior':'loop tile', 
                           'color_choices':'4'},
           'sparse noise':{'animation':(' ' * 100 + '█▓▒'), 
                           'behavior':'random', 
                           'color_choices':'1' * 5 + '7'},
                'shimmer':{'animation':(base_tile), 
                           'behavior':'random', 
                           'color_choices':'1234567'},
            'energy block':{'animation':'▤▥▦▧▨▩', 
                           'behavior':'random', 
                           'color_choices':'456'},
                  'blank':{'animation':' ', 
                           'behavior':'random', 
                           'color_choices':'0'},
              'explosion':{'animation':('█▓▒'), 
                           'behavior':'random', 
                           'color_choices':'111333',
                           'background':'0111333'},
              'loop test':{'animation':('0123456789abcdefghi'), 
                           'behavior':'walk both', 
                           'color_choices':'33333344444'},
                   'bars':{'animation':(' ▁▂▃▄▅▆▇█'), 
                           'behavior':'walk both', 
                           'color_choices':'2'},
                 'spikes':{'animation':('∧∧∧∧‸‸‸     '), 
                           'behavior':'loop both', 
                           'color_choices':'7'},
                 'bullet':{'animation':('◦◦◦○'),
                           'behavior':'random',
                           'color_choices':'446'},
                   'door':{'animation':('▯'), 
                           'behavior':'random', 
                           'color_choices':'78888'},
                 'writhe':{'animation':('─│╭╮╯╰'),
                           'behavior':'random',
                           'color_choices':'456'}}
        if preset:
            preset_kwargs = presets[preset]
            #calls init again using kwargs, but with preset set to None to 
            #avoid infinite recursion.
            self.__init__(**preset_kwargs, preset=None)
        else:
            self.frame_number = 0
            self.color_frame_number = 0
            self.animation = animation
            self.base_tile = base_tile
            self.behavior = behavior
            self.color_choices = color_choices
            self.background = background
    
    def __next__(self):
        behavior_lookup = {'random':{'color':'random', 'tile':'random'},
                           'loop color':{'color':'loop', 'tile':'random'},
                           'loop tile':{'color':'random', 'tile':'loop'},
                           'loop both':{'color':'loop', 'tile':'loop'},
                           'walk color':{'color':'walk', 'tile':'random'},
                           'walk frame':{'color':'random', 'tile':'walk'},
                           'walk both':{'color':'walk', 'tile':'walk'},
                           'breathe':{'color':'breathe', 'tile':'breathe'}}

        current_behavior = behavior_lookup[self.behavior]
        #color behavior:
        if current_behavior['color'] == 'random':
            color_choice = int(choice(self.color_choices))
        elif current_behavior['color'] == 'loop':
            color_choice = int(list(self.color_choices)[self.color_frame_number])
            self.color_frame_number = (self.color_frame_number + 1) % len(self.color_choices)
        elif current_behavior['color'] == 'walk':
            self.color_frame_number = (self.color_frame_number + randint(-1, 1)) % len(self.color_choices)
            color_choice = int(list(self.color_choices)[self.color_frame_number])
        else:
            color_choice = 5 #purple
        #tile behavior
        if current_behavior['tile'] == 'random':
            tile_choice = choice(self.animation)
        elif current_behavior['tile'] == 'loop':
            tile_choice = list(self.animation)[self.frame_number]
            self.frame_number = (self.frame_number + 1) % len(self.animation)
        elif current_behavior['tile'] == 'walk':
            self.frame_number = (self.frame_number + randint(-1, 1)) % len(self.animation)
            tile_choice = list(self.animation)[self.frame_number]
        else:
            tile_choice = '?'
        #background behavior
        if self.background:
            background_choice = int(choice(self.background))
        else:
            background_choice = 0
        #combined output
        return term.on_color(background_choice)(term.color(color_choice)(tile_choice))


class Item:
    """
    An item that can be used either by the player or various actors.
    An item:
        can be carried.
        can be picked up on keyboard input.
        have a representation on the ground
        when the player is over a tile with items, 
            the items are displayed in a window. 
        can be stored in a container (chests? pots? crates?)
            destructible crates/pots that strew debris around when broken(???)
        can be used (via its usable_power and given power_kwargs (for different
                versions of the same item)
    """
    def __init__(self, name='generic_item', item_id=None, spawn_coord=(0, 0), uses=None, 
                 tile='?', current_location=None, usable_power=None, power_kwargs={}, 
                 broken=False, use_message='You use the item.',
                 broken_text=" is broken.", mutable=True):
        self.name = name
        self.item_id = item_id
        self.spawn_coord = spawn_coord
        self.current_location = self.spawn_coord
        self.uses = uses
        self.tile = tile
        self.usable_power = usable_power
        self.use_message = use_message
        self.broken = broken
        self.broken_text = broken_text
        self.power_kwargs = power_kwargs
        self.mutable = mutable

    async def use(self):
        if self.uses is not None and not self.broken:
            if self.use_message is not None:
                asyncio.ensure_future(filter_print(output_text=self.use_message))
            asyncio.ensure_future(self.usable_power(**self.power_kwargs))
            if self.uses is not None:
                self.uses -= 1
            if self.uses <= 0:
                self.broken = True
        else:
            await filter_print(output_text="{}{}".format(self.name, self.broken_text))

class Multi_tile_entity:
    #TODO: fix problems with damaged parts
    #TODO: option to turn into scenery parts that have no living neighbors
    #TODO: make detached segments (with no continuous route to the majority of the segments) cleave off
    #      and require separate pushing (spawning a smaller split MTE for each half)
    """
    when the new location is checked as passable, it has to do so for each element
    if any of the four pieces would be somewhere that is impassable, the whole does not move
    each pushable actor has a parent that tracks locations of each of the children
    if any piece would be pushed, the push command is forwarded to the parent node.
        the parent node checks the new possible locations.
        if none of the new locations have actors or impassable cells, 
            update the location for each of the children nodes
        else:
            nothing happens and nothing is pushed.

    if we have a 4 tile object, and we name each of the siblings/members of the set:

         | ... if C is pushed from the north to the south
         V
         @
      A->┏┓<-B
      C->┗┛<-D

    push() first sees A. A then needs to check with its parent Multi_tile_entity.

    [X]an actor must then have an attribute for whether it's part of a multi-tile entity.
    
    if we check and find that an actor is part of an MTE (the MTE attribute is not None),
        call the named MTE's location_clear method to figure out whether it will fit in a new orientation

    else:
        push the actor/entity as normal

    Otherwise, each member of a MTE could have a single pointer/label for a higher
    level object that it's part of. 

    Each lower level (child) of the parent MTE only tells the parent that it wants to move the cluster.
    The child sends a proposed location to the parent. The parent can then return True or False
    to whether the new location would be a viable location.

    If we don't want to clip through things, The actual location of the 
    MTE is only updated after checking whether the ground is clear.

    TODO: A method to split an MTE into multiple smaller MTEs.
        If an entity is only one tile, its parent is None.
    """
 
    def __init__(self, name='mte', anchor_coord=(0, 0), preset='fireball', 
                 blocking=True, fill_color=3, offset=(-1, -1)):
        self.name = name
        animation_key = {'E':'explosion', 'W':'writhe'}
        #Note: ' ' entries are ignored but keep the shape of the preset
        presets = {'2x2':(('┏', '┓'),
                          ('┗', '┛'),),
              'bold_2x2':(('▛', '▜'),
                          ('▙', '▟'),),
             '2x2_block':(('╔', '╗'),
                          ('╚', '╝'),),
             '3x3_block':(('╔', '╦', '╗'),
                          ('╠', '╬', '╣'),
                          ('╚', '╩', '╝'),),
                   '3x2':(('┏', '━', '┓'),
                          ('┗', '━', '┛'),),
                   '3x3':(('┏', '━', '┓'),
                          ('┃', ' ', '┃'),
                          ('┗', ' ', '┛'),),
              '3x3 fire':(('┏', '━', '┓'),
                          ('┃', 'E', '┃'),
                          ('┗', '━', '┛'),),
            'writheball':((' ', 'W', 'W', ' '),
                          ('W', 'W', 'W', 'W'),
                          ('W', 'W', 'W', 'W'),
                          (' ', 'W', 'W', ' '),),
              'fireball':((' ', 'E', 'E', ' '),
                          ('E', 'E', 'E', 'E'),
                          ('E', 'E', 'E', 'E'),
                          (' ', 'E', 'E', ' '),),
           'ns_bookcase':(('▛'),
                          ('▌'),
                          ('▌'),
                          ('▙'),),
           'ew_bookcase':(('▛'), ('▀'), ('▀'), ('▜'),),
              'add_sign':((' ', '╻', ' '),
                          ('╺', '╋', '╸'),
                          (' ', '╹', ' '),),}
        self.member_actors = {}
        self.member_names = []
        tiles = presets[preset]
        for y in range(len(tiles)):
            for x in range(len(tiles[0])):
                offset_coord = add_coords((x, y), offset)
                write_coord = add_coords(offset_coord, anchor_coord)
                if tiles[y][x] not in animation_key:
                    member_tile = term.color(fill_color)(tiles[y][x])
                if tiles[y][x] is ' ':
                    member_tile = None
                else:
                    member_tile = term.color(fill_color)(tiles[y][x])
                if member_tile is not None:
                    self.member_actors[offset_coord] = (member_tile, write_coord, (x, y))
        for member in self.member_actors.values():
            segment_name = '{}_{}'.format(self.name, member[2])
            if member[0] in animation_key:
                member_name = spawn_static_actor(base_name=segment_name, 
                                                 spawn_coord=member[1], 
                                                 animation_preset=animation_key[member[0]],
                                                 multi_tile_parent=self.name,
                                                 blocking=blocking, 
                                                 literal_name=True)
            else:
                member_name = spawn_static_actor(base_name=segment_name, 
                                                 spawn_coord=member[1], 
                                                 tile=member[0],
                                                 multi_tile_parent=self.name,
                                                 blocking=blocking, 
                                                 literal_name=True)
            self.member_names.append(member_name)

    def check_collision(self, move_by=(0, 0)):
        """
        Checks whether all of the member actors can fit into a new configuration
        """
        #TODO: allow for an mte to move into a space currently occupied by the player.
        #TODO: allow or disallow multi-pushes that would contact another block
        check_position = {}
        for member_name in self.member_names:
            current_coord = actor_dict[member_name].coords()
            check_coord = add_coords(current_coord, move_by)
            if not map_dict[check_coord].passable:
                return False
            for actor in map_dict[check_coord].actors:
                if actor not in self.member_names:
                    return False
        return True

    def move(self, move_by=(3, 3)):
        for member_name in self.member_names:
            current_coord = actor_dict[member_name].coords()
            actor_dict[member_name].update(*add_coords(current_coord, move_by))

    def check_continuity(self, root_node=None, connection_path=None):
        """
        does a recursive search through the parts of an mte, starting at a given root node.

        for (1, 1) as the root node,

        (1, 1) first finds if adjacent nodes exist:
            check each adjacent coordinate (of possible mte members)

                    (1, 0)
                      /\

         (0, 1) <-- (1, 1) --> (2, 1)

                      \/
                    (1, 2)

        if a node exists (in the list of member actors in the parent MTE, 
        run the function again on the child node with the parent node appended to the path.

        (1, 1) (2, 1)   --
        (1, 2)   --   (3, 2)
          --   (2, 3) (3, 3)

        Only check adjacency for nodes not in the path.

        If there are no new nodes turned up by a search, return the path.
        The next level up will return its path.

        the root node then explores the next viable adjacent tile, ignoring tiles 
        present in the first returned path.

        the first version will just see if an actor exists.
        it will assume that two actors with adjacent name_coords 
        (i.e. (1, 1) and (2, 1)) are connected. Nodes diagonal from one
        another are not connected.

        -------------------------------------------------------------------
        starting with the root node:
        we look for the neighbors of the node (one in each direction)
        and check whether they exist as actors.

        when an actor (neighbor) is found that exists,
        the function runs again on its child and is passed any path history and walked cells.

        explored at t1: (1, 1)
        unexplored at t1: None

        checked (1, 0), (2, 1), (1, 2), (0, 1)
        (2, 1) and (1, 2) exist in mte parent
        and are added to unexplored

        explored at t2: (1, 1)
        unexplored at t2: (2, 1), (1, 2)

        [we pick the first unexplored cell and see whether it exists]

        explored at t3: (1, 1), (2, 1)
        passed (1, 1) as parent

        if an MTE splits, it is appended with "_a" and "_b"

        """
        
        #neighbors = ((0, -1), (1, 0), (0, 1), (-1, 0))


async def spawn_mte(base_name='mte', spawn_coord=(0, 0), preset='3x3_block'):
    mte_id = generate_id(base_name=base_name)
    mte_dict[mte_id] = Multi_tile_entity(name=mte_id, anchor_coord=spawn_coord, preset=preset)

def multi_push(push_dir='e', pushed_actor=None, mte_parent=None):
    """
    pushes a multi_tile entity.
    """
    if pushed_actor is None and mte_parent is None:
        return False
    elif pushed_actor is not None and mte_parent is None:
        mte_parent = actor_dict[pushed_actor].multi_tile_parent
    dir_coords = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0)}
    move_by = dir_coords[push_dir]
    if mte_dict[mte_parent].check_collision(move_by=move_by):
        mte_dict[mte_parent].move(move_by=move_by)
        return True

async def rand_blink(actor_name='player', radius_range=(4, 8)):
    #TODO: fix update so it doesn't leave invisible blocking spaces
    rand_angle = randint(0, 360)
    rand_radius = randint(*radius_range)
    start_point = actor_dict[actor_name].coords()
    end_point = add_coords(start_point, point_given_angle_and_radius(angle=rand_angle, radius=rand_radius))
    travel_line = get_line(start_point, end_point)
    await drag_actor_along_line(actor_name=actor_name, line=travel_line)

async def drag_actor_along_line(actor_name='player', line=None, linger_time=.02):
    """
    Takes a list of coordinates as input.
    Moves an actor along the given points pausing linger_time seconds each step.
    """
    if actor_name is None:
        return False
    if line is None:
        player_coords = actor_dict['player'].coords()
        destination = add_coords(player_coords, (5, 5))
        line = get_line(player_coords, destination)
    for point in line:
        await asyncio.sleep(linger_time)
        actor_dict[actor_name].update(*point)

async def disperse_all_mte():
    for mte_name in mte_dict:
        if not hasattr(mte_dict[mte_name], 'dead'):
            asyncio.ensure_future(disperse_mte(mte_name))

async def disperse_mte(mte_name=None, radius_range=(4, 8), kills=True):
    if mte_name is None:
        return False
    if kills:
        mte_dict[mte_name].dead = True
    for segment in mte_dict[mte_name].member_names:
        actor_dict[segment].multi_tile_parent = None
        actor_dict[segment].moveable = True
        actor_dict[segment].blocking = False
        asyncio.ensure_future(rand_blink(actor_name=segment))

#Global state setup-------------------------------------------------------------
term = Terminal()
map_dict = defaultdict(lambda: Map_tile(passable=False, blocking=True))
mte_dict = {}
room_centers = set()
actor_dict = defaultdict(lambda: [None])
state_dict = defaultdict(lambda: None)
item_dict = defaultdict(lambda: None)
actor_dict['player'] = Actor(name='player', tile=term.red("@"), health=100, stamina=100)
actor_dict['player'].just_teleported = False
map_dict[actor_dict['player'].coords()].actors['player'] = True
state_dict['facing'] = 'n'
state_dict['menu_choices'] = []
state_dict['plane'] = 'normal'
state_dict['printing'] = False
state_dict['known location'] = True

#Drawing functions--------------------------------------------------------------
def draw_box(top_left=(0, 0), x_size=1, y_size=1, filled=True, 
             tile=".", passable=True):
    """ Draws a box to map_dict at the given coordinates."""
    x_min, y_min = top_left[0], top_left[1]
    x_max, y_max = x_min + x_size, y_min + y_size
    x_values = (x_min, x_max)
    y_values = (y_min, y_max)
    if filled:
        for x in range(*x_values):
            for y in range(*y_values):
                map_dict[(x, y)].tile = tile
                map_dict[(x, y)].passable = passable
                map_dict[(x, y)].blocking = False
    else:
        map_dict[x_min, y_min].tile = tile
        map_dict[(x_max, y_max)].tile = tile
        for x in range(x_min, x_max):
            for y in (y_min, y_max):
                map_dict[(x, y)].tile = tile
        for y in range(y_min, y_max):
            for x in (x_min, x_max):
                map_dict[(x, y)].tile = tile

def draw_centered_box(middle_coord=(0, 0), x_size=10, y_size=10, 
                  filled=True, tile=".", passable=True):
    top_left = (middle_coord[0] - x_size//2, middle_coord[1] - y_size//2)
    draw_box(top_left=top_left, x_size=x_size, y_size=y_size, filled=filled, tile=tile)

def draw_line(coord_a=(0, 0), coord_b=(5, 5), palette="*",
                    passable=True, blocking=False):
    """draws a line to the map_dict connecting the two given points."""
    points = get_line(coord_a, coord_b)
    for point in points:
        if len(palette) > 1:
            map_dict[point].tile = choice(palette)
        else:
            map_dict[point].tile = palette
        map_dict[point].passable = passable
        map_dict[point].blocking = blocking

#TODO: a function to make a bumpy passage of randomly oscillating size?

def halfway_point(point_a=(0, 0), point_b=(10, 10)):
    """
    returns the point halfway between two points.
    """
    x_diff = point_b[0] - point_a[0]
    y_diff = point_b[1] - point_a[1]
    return add_coords(point_a, (x_diff//2, y_diff//2))

def find_centroid(points=((0, 0), (2, 2), (-1, -1)), rounded=True):
    sum_x = sum(point[0] for point in points)
    sum_y = sum(point[1] for point in points)
    result = (sum_x / len(points), sum_y / len(points))
    if rounded:
        return (round(result[0]), round(result[1]))
    else:
        return result

def point_within_square(radius=20, center=(0, 0)):
    point_in_square = randint(-radius, radius), randint(-radius, radius)
    return add_coords(center, point_in_square)

def point_within_radius(radius=20, center=(0, 0)):
    stuck_count = 0
    while True:
        stuck_count += 1
        point = point_within_square(radius=radius, center=center)
        distance_from_center = abs(point_to_point_distance(point_a=point, point_b=center))
        if distance_from_center <= radius:
            break
        if stuck_count >= 50:
            with term.location(15, 0):
                print(radius, center, distance_from_center, point)
            sleep(1)
    return point

def check_point_within_arc(checked_point=(-5, 5), facing_angle=None, arc_width=90, center=None):
    """
    checks whether a point falls within an arc sighted from another point.
    """
    if facing_angle is None:
        dir_to_angle = {'n':0, 'e':90, 's':180, 'w':270}
        facing_angle = dir_to_angle[state_dict['facing']]
        center = actor_dict['player'].coords()
    if center is None:
        center = (0, 0)
    half_arc = arc_width / 2
    twelve_reference = (center[0], center[1] - 5)
    arc_range = ((facing_angle - half_arc) % 360,
                 (facing_angle + half_arc) % 360)
    with term.location(0, 1):
        found_angle = round(find_angle(p0=twelve_reference, p1=center, p2=checked_point))
        if checked_point[0] < center[0]:
            found_angle = 360 - found_angle
        print("found: {}, facing: {}, arc_range: {}".format(found_angle, facing_angle, arc_range))
        result = in_angle_bracket(given_angle=found_angle,
                                  arc_begin=arc_range[0], arc_end=arc_range[1])
    return result

def in_angle_bracket(given_angle, arc_begin=45, arc_end=135):
    if arc_begin > arc_end:
        if given_angle < 90:
            result = given_angle <= arc_end
        elif given_angle > 270:
            result = arc_begin <= given_angle
        else:
            result = False
    else:
        result = arc_begin < given_angle < arc_end
    return result

def draw_net(radius=50, points=100, cull_connections_of_distance=10, center=(0, 0)):
    net_points = [point_within_radius(radius=radius, center=center) for _ in range(points)]
    lines = combinations(net_points, 2)
    for line in lines:
        line_length = point_to_point_distance(point_a=line[0], point_b=line[1])
        if line_length < cull_connections_of_distance:
            n_wide_passage(coord_a=line[0], coord_b=line[1],
                           width=2, passable=True, blocking=False,
                           palette="░")
    #cull points that are too close together?

def points_around_point(radius=5, radius_spread=2, middle_point=(0, 0), 
                        in_cone=(0, 90), num_points=5):
    """
    returns a number of points fanned out around a middle point.
    given radius_spread values, the points will be at a random radius.
    if in_cone is not None, the returned points are restricted to an arc.
    """
    points = []
    radius_range = (radius - radius_spread, radius + radius_spread)
    for _ in range(num_points):
        rand_angle = randint(*in_cone)
        rand_radius = randint(*radius_range)
        points.append(point_given_angle_and_radius(angle=rand_angle, 
                                                   radius=rand_radius))
    return points

def get_cells_along_line(start_point=(0, 0), end_point=(10, 10), num_points=5):
    """
    Writes a jagged passage between two points of a variable number of segments
    to map_dict.

    Uses np.linspace, np.astype and .tolist()

    returns nothing
    """
    x_value_range = (start_point[0], end_point[0])
    y_value_range = (start_point[1], end_point[1])
    x_values = np.linspace(*x_value_range, num=num_points).astype(int)
    y_values = np.linspace(*y_value_range, num=num_points).astype(int)
    points = list(zip(x_values.tolist(), y_values.tolist()))
    return points

def add_jitter_to_middle(cells=None, jitter=5):
    """
    takes a list of points and returns the same head and tail but with randomly
    shifted points in the middle.
    """
    if cells is not None:
        head, *body, tail = cells #tuple unpacking
        new_body = []
        for point in body:
            rand_shift = [randint(-jitter, jitter) for i in range(2)]
            new_body.append(add_coords(rand_shift, point))
        output = head, *new_body, tail #pack tuples back into one list o
        return output
    else:
        return []

def chained_pairs_of_items(pairs=None):
    """
    Used for taking a list of points and returning pairs of points for drawing
    lines.

    input: ((1, 1), (2, 2), (3, 3), (4, 4))
    output: (((1, 1), (2, 2)), ((2, 2), (3, 3)), ((3, 3), (4, 4)))
    """
    if pairs is None:
        pairs = [(i, i * 2) for i in range(10)]
    return [(pairs[i], pairs[i + 1]) for i in range(len(pairs) - 1)]

def multi_segment_passage(points=None, palette="░", width=3, 
                          passable=True, blocking=False):
    coord_pairs = chained_pairs_of_items(pairs=points)
    for coord_pair in coord_pairs:
        n_wide_passage(coord_a=coord_pair[0], coord_b=coord_pair[1],
                       width=width, passable=passable, blocking=blocking,
                       palette=palette)

def n_wide_passage(coord_a=(0, 0), coord_b=(5, 5), palette="░", 
                   passable=True, blocking=False, width=3):
    origin = (0, 0)
    if width == 0:
        return
    offsets = ((x, y) for x in range(-width, width + 1) 
                      for y in range(-width, width + 1))
    trimmed_offsets = [offset for offset in offsets if
                       point_to_point_distance(point_a=offset, point_b=origin) <= width / 2]
    points_to_write = set()
    for offset in trimmed_offsets:
        offset_coord_a = add_coords(coord_a, offset)
        offset_coord_b = add_coords(coord_b, offset)
        line_points = get_line(offset_coord_a, offset_coord_b)
        for point in line_points:
            points_to_write.add(point)
    with term.location(0, 1):
        print("len(points_to_write) is: {}".format(len(points_to_write)))
    for point in points_to_write:
        if len(palette) > 1:
            map_dict[point].tile = choice(palette)
        else:
            map_dict[point].tile = palette[0]
        map_dict[point].passable = passable
        map_dict[point].blocking = blocking

def arc_of_points(start_coord=(0, 0), starting_angle=0, segment_length=4, 
                  segment_angle_increment=5, segments=10, random_shift=True,
                  shift_choices=(-10, 10)):
    last_point, last_angle = start_coord, starting_angle
    output_points = [start_coord]
    for _ in range(segment_length):
        coord_shift = point_given_angle_and_radius(angle=last_angle,
                                                        radius=segment_length)
        next_point = add_coords(last_point, coord_shift)
        output_points.append(next_point)
        last_point = next_point
        if random_shift:
            last_angle += choice(shift_choices)
        else:
            last_angle += segment_angle_increment
    return output_points, last_angle

def chain_of_arcs(start_coord=(0, 0), num_arcs=20, starting_angle=90, 
                  width=(2, 20), draw_mode='taper', palette="░"):
    """
    chain of arcs creates a chain of curved passages of optionally variable width.

    if width is given as a single number, width is fixed.
    if width is given as a 2-length tuple, width is a random number

    draw_mode controls the width of the passage
    """
    arc_start = start_coord
    if draw_mode == 'even': #same passage length throughout
        segment_widths = [width[0]] * num_arcs
    elif draw_mode == 'random': #passage width is random
        segment_widths = [randint(*width) for _ in range(num_arcs)]
    elif draw_mode == 'taper': #passage starts at width[0], ends at width[1]
        segment_widths = np.linspace(*width, num=num_arcs).astype(int)
    for segment_width in segment_widths:
        rand_segment_angle = choice((-20, -10, 10, 20))
        points, starting_angle = arc_of_points(starting_angle=starting_angle, 
                                               segment_angle_increment=rand_segment_angle,
                                               start_coord=arc_start,
                                               random_shift=False)
        with term.location(30, 2):
            print("POINTS: {}".format(points))
        for point in points:
            map_dict[point].tile = term.red("X")
        arc_start = points[-1] #set the start point of the next passage.
        multi_segment_passage(points=points, width=segment_width, palette=palette)


def cave_room(trim_radius=40, width=100, height=100, 
              iterations=20, debug=False, 
              kernel=True, kernel_offset=(0, 0), kernel_radius=3):
    neighbors = [(x, y) for x in (-1, 0, 1)
                        for y in (-1, 0, 1)]
    #get kernel cells:
    #the kernel is a round open space in the middle of the room.
    if kernel:
        middle_coord = (width // 2, height // 2)
        kernel_base_coord = add_coords(kernel_offset, middle_coord)
        kernel_cells = {coord:'#' for coord in 
                        get_circle(center=kernel_base_coord, radius=kernel_radius)}
    #initialize the room:
    input_space = {(x, y):choice(['#', ' ']) for x in range(width) for y in range(height)}
    if trim_radius:
        input_space = trim_outside_circle(input_dict=input_space, width=width,
                                         height=height, trim_radius=trim_radius)
    adjacency = {(x, y):0 for x in range(width) for y in range(height)}
    check_coords = [(x, y) for x in range(width)
                           for y in range(height)]
    if kernel:
        for coord, value in kernel_cells.items():
            input_space[coord] = '#'
    for iteration_number in range(iterations):
        #build adjacency map
        for coord in check_coords:
            neighbor_count = 0
            for neighbor in neighbors:
                check_cell_coord = add_coords(coord_a=coord, coord_b=neighbor)
                if check_cell_coord not in input_space:
                    continue
                if input_space[check_cell_coord] == '#':
                    neighbor_count += 1
            adjacency[coord] = neighbor_count
        #step through adjacency map, apply changes
        for coord in check_coords:
            if adjacency[coord] >= 5:
                input_space[coord] = '#'
            else:
                input_space[coord] = ' '
    return input_space

def trim_outside_circle(input_dict={}, width=20, height=20, trim_radius=8, outside_radius_char=' '):
    center_coord = width // 2, height // 2
    for coord in input_dict:
        distance_from_center = point_to_point_distance(point_a=coord, point_b=center_coord)
        if distance_from_center >= trim_radius:
            input_dict[coord] = outside_radius_char
    return input_dict

def write_room_to_map(room={}, top_left_coord=(0, 0), space_char=' ', hash_char='░'):
    for coord, value in room.items():
        write_coord = add_coords(coord, top_left_coord)
        with term.location(80, 0):
            print(write_coord, value)
        if value == ' ':
            continue
        if value == '#':
            map_dict[write_coord].passable = True
            map_dict[write_coord].blocking = False
            map_dict[write_coord].tile = hash_char

async def draw_circle(center_coord=(0, 0), radius=5, palette="░",
                passable=True, blocking=False, animation=None, delay=0,
                description=None):
    """
    draws a filled circle onto map_dict.
    """
    await asyncio.sleep(0)
    x_bounds = center_coord[0] - radius, center_coord[0] + radius
    y_bounds = center_coord[1] - radius, center_coord[1] + radius
    for x in range(*x_bounds):
        for y in range(*y_bounds):
            if delay != 0:
                await asyncio.sleep(delay)
            if not map_dict[(x, y)].mutable:
                continue
            distance_to_center = point_to_point_distance(point_a=center_coord, point_b=(x, y))
            if animation:
                is_animated = True
            else:
                is_animated = False
            if distance_to_center <= radius:
                #assigned as separate attributes to preserve items and actors on each tile.
                map_dict[x, y].passable = passable
                map_dict[x, y].tile = choice(palette)
                map_dict[x, y].blocking = blocking 
                map_dict[x, y].description = description
                map_dict[x, y].is_animated = is_animated
                map_dict[x, y].animation = copy(animation)

#Actions------------------------------------------------------------------------
async def throw_item(thrown_item_id=False, source_actor='player', direction=None, throw_distance=13, rand_drift=2):
    """
    Moves item from player's inventory to another tile at distance 
    throw_distance
    """
    directions = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
    if direction is None:
        direction_tuple = directions[state_dict['facing']]
    if not thrown_item_id:
        thrown_item_id = await choose_item()
    if thrown_item_id == None:
        await filter_print(output_text="Nothing to throw!")
        return False
    del actor_dict['player'].holding_items[thrown_item_id]
    starting_point = actor_dict[source_actor].coords()
    destination = (starting_point[0] + direction_tuple[0] * throw_distance,
                   starting_point[1] + direction_tuple[1] * throw_distance)
    if rand_drift:
        destination = (destination[0] + randint(0, rand_drift),
                       destination[1] + randint(0, rand_drift))
    if not hasattr(item_dict[thrown_item_id], 'tile'):
        return False
    line_of_sight_result = await check_line_of_sight(coord_a=starting_point, coord_b=destination)
    #find last open tile before wall and place item there.
    if not line_of_sight_result:
        last_open = None
        points = get_line(starting_point, destination)
        #ignore the first point, that's where the player is standing.
        for point in points[1:]:
            if map_dict[point].passable:
                last_open = point
            else:
                break
        destination = last_open
    item_tile = item_dict[thrown_item_id].tile
    throw_text = "throwing {} {}.(destination: {})".format(item_dict[thrown_item_id].name, direction, destination)
    asyncio.ensure_future(filter_print(throw_text))
    await travel_along_line(name='thrown_item_id', start_coord=starting_point, 
                            end_coords=destination, speed=.05, tile=item_tile, 
                            animation=None, debris=None)
    map_dict[destination].items[thrown_item_id] = True
    item_dict[thrown_item_id].current_location = destination
    return True

async def display_fuse(fuse_length=3, item_id=None, reset_tile=True):
    await asyncio.sleep(0)
    original_tile = item_dict[item_id].tile
    for count in reversed(range(fuse_length + 1)):
        await asyncio.sleep(.5)
        item_dict[item_id].tile = original_tile
        await asyncio.sleep(.5)
        item_dict[item_id].tile = term.red(str(count))
    if reset_tile:
        item_dict[item_id].tile = original_tile

async def explosion_effect(center=(0, 0), radius=6, damage=75, particle_count=25, destroys_terrain=True):
    await radial_fountain(tile_anchor=center, anchor_actor='player', 
                          frequency=.001, radius=(radius, radius + 3), speed=(1, 2), 
                          collapse=False, debris='`.,\'', deathclock=particle_count,
                          animation=Animation(preset='explosion'))
    if destroys_terrain:
        await draw_circle(center_coord=center, radius=radius)
    if damage:
        await damage_within_circle(center=center, radius=radius, damage=damage)

async def fused_throw_action(fuse_length=3, thrown_item_id=None, source_actor='player', 
                             direction=None, throw_distance=13, rand_drift=2, 
                             radius=6, damage=75, particle_count=25):
    await throw_item(thrown_item_id=thrown_item_id, source_actor=source_actor,
                     direction=direction, throw_distance=throw_distance, 
                     rand_drift=rand_drift)
    item_location = item_dict[thrown_item_id].current_location
    await display_fuse(fuse_length=fuse_length, item_id=thrown_item_id)
    if thrown_item_id in map_dict[item_location].items:
        del map_dict[item_location].items[thrown_item_id]
    del item_dict[thrown_item_id]
    await explosion_effect(center=item_location, radius=radius, 
                           damage=damage, particle_count=particle_count)

async def damage_all_actors_at_coord(coord=(0, 0), damage=10, source_actor=None):
    actor_list = map_dict[coord].actors.items()
    for actor in actor_list:
        if actor[0] == 'player' and source_actor is not None:
            asyncio.ensure_future(directional_damage_alert(source_actor=source_actor))
        await damage_actor(actor=actor[0], damage=damage, display_above=False)

async def damage_within_circle(center=(0, 0), radius=6, damage=75):
    area_of_effect = get_circle(center=center, radius=radius)
    for coord in area_of_effect:
        await damage_all_actors_at_coord(coord=coord, damage=damage)

async def damage_actor(actor=None, damage=10, display_above=True,
                       leaves_body=False, blood=False, material='wood'):
    if hasattr(actor_dict[actor], 'health'):
        current_health = actor_dict[actor].health
    else:
        return
    if current_health - damage <= 0:
        actor_dict[actor].health = 0
    else:
        actor_dict[actor].health = current_health - damage
    exclusions = ('sword', 'particle', 'vine', 'shroud')
    for word in exclusions:
        if word in actor:
            return
    if display_above:
        asyncio.ensure_future(damage_numbers(damage=damage, actor=actor))
    if actor_dict[actor].health <= 0 and actor_dict[actor].breakable == True:
        root_x, root_y = actor_dict[actor].coords()
        asyncio.ensure_future(sow_texture(root_x, root_y, palette=',.\'', radius=3, seeds=6, 
                              passable=True, stamp=True, paint=False, color_num=8,
                              description='Broken {}.'.format(material),
                              pause_between=.06))
        await kill_actor(name_key=actor, blood=blood, leaves_body=leaves_body)

async def damage_numbers(actor=None, damage=10, squares_above=5):
    if not hasattr(actor_dict[actor], 'coords'):
        return
    actor_coords = actor_dict[actor].coords()
    digit_to_superscript = {'1':'¹', '2':'²', '3':'³', '4':'⁴', '5':'⁵',
                            '6':'⁶', '7':'⁷', '8':'⁸', '9':'⁹', '0':'⁰',
                            '-':'⁻', '+':'⁺'}
    if damage >= 0:
        damage = '-' + str(damage)
    else:
        damage = '+' + str(damage)[1:]
    for x_pos, digit in enumerate(damage):
        start_coord = actor_coords[0] + (x_pos - 1), actor_coords[1] - 1
        end_coords = start_coord[0], start_coord[1] - squares_above
        if damage[0] == '-':
            tile = term.red(digit_to_superscript[digit])
        else:
            tile = term.green(digit_to_superscript[digit])
        asyncio.ensure_future(travel_along_line(tile=tile,
                                                speed=.12,
                                                start_coord=start_coord, 
                                                end_coords=end_coords,
                                                debris=False,
                                                animation=False))

async def unlock_door(actor_key='player', opens='red'):
    directions = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
    check_dir = state_dict['facing']
    actor_coord = actor_dict[actor_key].coords()
    door_coord = add_coords(actor_coord, directions[check_dir])
    door_type = map_dict[door_coord].key
    if opens in map_dict[door_coord].key and map_dict[door_coord].is_door:
        if map_dict[door_coord].locked:
            output_text = "You unlock the {} door.".format(opens)
            map_dict[door_coord].locked = False
        elif not map_dict[door_coord].locked:
            output_text = "You lock the {} door.".format(opens)
            map_dict[door_coord].locked = True
    elif not map_dict[door_coord].is_door:
        output_text = "That isn't a door."
    else:
        output_text = "Your {} key doesn't fit the {} door.".format(opens, door_type)
    asyncio.ensure_future(filter_print(output_text=output_text))


#TODO: an entity that moves around with momentum,
#      others that follow the last n moves
#      billiard balls?

def occupied(checked_coords=(0, 0)):
    if not map_dict[checked_coords].actors and map_dict[checked_coords].passable:
        return True
    else:
        return False

def push(direction='n', pusher='player'):
    """
    basic pushing behavior for single-tile actors.
    objects do not clip into other objects or other actors.
    """
    dir_coords = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0)}
    chosen_dir = dir_coords[direction]
    pusher_coords = actor_dict[pusher].coords()
    destination_coords = add_coords(pusher_coords, chosen_dir)
    if not map_dict[destination_coords].actors:
        return
    pushed_name = next(iter(map_dict[destination_coords].actors))
    mte_parent = actor_dict[pushed_name].multi_tile_parent
    if mte_parent is not None:
        multi_push(push_dir=direction, mte_parent=mte_parent)
        return
    elif not actor_dict[pushed_name].moveable:
        return
    else:
        pushed_coords = actor_dict[pushed_name].coords()
        pushed_destination = add_coords(pushed_coords, chosen_dir)
        if not map_dict[pushed_destination].actors and map_dict[pushed_destination].passable:
            actor_dict[pushed_name].update(*pushed_destination)

async def follower_actor(name="follower", refresh_speed=.01, parent_actor='player', 
                         offset=(-1,-1), alive=True, tile=" "):
    await asyncio.sleep(refresh_speed)
    follower_id = generate_id(base_name=name)
    actor_dict[follower_id] = Actor(name=follower_id, tile=tile)
    while alive:
        await asyncio.sleep(refresh_speed)
        parent_coords = actor_dict[parent_actor].coords()
        follow_x, follow_y = (parent_coords[0] + offset[0], 
                              parent_coords[1] + offset[1])
        actor_dict[follower_id].update(follow_x, follow_y)

async def circle_of_darkness(start_coord=(0, 0), name='darkness', circle_size=4):
    actor_id = generate_id(base_name=name)
    loop = asyncio.get_event_loop()
    loop.create_task(basic_actor(*start_coord, speed=.5, movement_function=seek_actor, 
                                 tile=" ", name_key=actor_id, hurtful=True,
                                 is_animated=True, animation=Animation(preset="none")))
    await asyncio.sleep(0)
    range_tuple = (-circle_size, circle_size + 1)
    for x in range(*range_tuple):
        for y in range(*range_tuple):
            distance_to_center = point_to_point_distance(point_a=(0, 0), 
                                                         point_b=(x, y))
            if distance_to_center <= circle_size:
                loop.create_task(follower_actor(parent_actor=actor_id, 
                                                offset=(x, y)))
                #shadow in nightmare space
                loop.create_task(follower_actor(tile=term.on_white(" "), 
                                                parent_actor=actor_id, 
                                                offset=(1000 + x, 1000 + y)))
            else:
                pass
    loop.create_task(radial_fountain(anchor_actor=actor_id,
                                     animation=Animation(preset='sparse noise')))

async def multi_spike_trap(base_name='multitrap', base_coord=(10, 10), 
                           nodes=[(i, -5, 's') for i in range(-5, 4)],
                           damage=75, length=7, rate=.25,
                           speed=.1, retract_speed=1, patch_to_key='switch_1',
                           mid_trap_delay_time=.1):
    """
    pressure plate is centered, nodes are arrayed in offsets around
    the pressure plate. all nodes trigger at once when pressure plate is
    activated.
    """
    loop = asyncio.get_event_loop()
    state_dict[patch_to_key] = {}
    loop.create_task(pressure_plate(spawn_coord=base_coord, patch_to_key=patch_to_key))
    node_data = []
    for number, node in enumerate(nodes):
        node_coord = node[0] + base_coord[0], node[1] + base_coord[1]
        node_name = '{}_{}'.format(base_name, str(number))
        node_data.append((node_name, node[2]))
        actor_dict[node_name] = Actor(name=node_name, moveable=False,
                                           tile=term.color(7)('◘'))
        actor_dict[node_name].update(*node_coord)
    while True:
        await asyncio.sleep(rate)
        if await any_true(trigger_key=patch_to_key):
            for node in node_data:
                asyncio.ensure_future(sword(direction=node[1], actor=node[0], length=length, 
                                            damage=damage, sword_color=7, speed=speed, 
                                            retract_speed=retract_speed))

async def spike_trap(base_name='spike_trap', coord=(10, 10), 
                     direction='n', damage=20, length=5, rate=.25, 
                     speed=.1, patch_to_key='switch_1'):
    """
    Generate a stationary, actor that periodically puts out spikes in each
    direction given at rate spike_rate.
    """
    trap_origin_id = generate_id(base_name=base_name)
    actor_dict[trap_origin_id] = Actor(name=trap_origin_id, moveable=False,
                                       tile=term.color(7)('◘'))
    actor_dict[trap_origin_id].update(*coord)
    while True:
        await asyncio.sleep(rate)
        if await any_true(trigger_key=patch_to_key):
            asyncio.ensure_future(sword(direction=direction, actor=trap_origin_id, length=length, 
                                        damage=damage, sword_color=7, speed=speed))

async def check_actors_on_tile(coords=(0, 0), positives=''):
    actors_on_square = [actor for actor in map_dict[coords].actors.items()]
    for actor in actors_on_square:
        for weight in positives:
            if weight in actor[0]:
                return True
                break
    return False

async def trigger_on_presence(trigger_actor='player', listen_tile=(5, 5), 
                              on_grid=(11, 11), room_size=(10, 10), origin=(0, 0)):
    room_centers.add(listen_tile)
    map_dict[listen_tile].tile = 'X'
    while True:
        await asyncio.sleep(.1)
        if 'player' in map_dict[listen_tile].actors:
            break
    with term.location(70, 0):
        print(room_centers)
    map_dict[listen_tile].tile = 'O'
    loop = asyncio.get_event_loop()
    coord_dirs = ((-1, 0), (1, 0), (0, -1), (0, 1))
    door_dirs = [(coord[0] * on_grid[0],
                  coord[1] * on_grid[1]) 
                 for coord in coord_dirs]
    unexplored = [add_coords(listen_tile, door_dir) for door_dir in door_dirs]
    with term.location(0, 2):
        print(unexplored)
    direction_choices = []
    for location in unexplored:
        if location not in room_centers:
            direction_choices.append(location)
    with term.location(70, 2):
        print(direction_choices)
    for direction_choice in direction_choices:
        if direction_choice not in room_centers:
            with term.location(70, 0):
                print("new room at {}!".format(direction_choice))
            draw_centered_box(middle_coord=direction_choice, x_size=room_size[0], y_size=room_size[1], tile="░")
            loop.create_task(trigger_on_presence(listen_tile=direction_choice, on_grid=on_grid, room_size=room_size))
            draw_line(coord_a=listen_tile, coord_b=direction_choice, palette="░")
            map_dict[direction_choice].tile = 'x'

async def export_map(width=140, height=45):
    #store the current tile at the player's location:
    temp_tile = map_dict[actor_dict['player'].coords()].tile
    #temporary lay down a '@':
    map_dict[actor_dict['player'].coords()].tile = '@'
    filename = "{}.txt".format('exported_map')
    if os.path.exists(filename): 
        os.remove(filename)
    player_location = actor_dict['player'].coords()
    x_spread = (-width // 2 + player_location[0], 
                 width // 2 + player_location[0])
    y_spread = (-height // 2 + player_location[1], 
                 height // 2 + player_location[1])
    with open(filename, 'a') as the_file:
        for y_pos, y in enumerate(range(*y_spread)):
            with term.location(60, y_pos):
                line_output = "{}\n".format("".join([map_dict[i, y].tile for i in range(*x_spread)]))
                the_file.write(line_output)
    with term.location(80, 0):
        print("finished writing map segment to {}.".format(filename))
    #return the tile to its original state:
    map_dict[actor_dict['player'].coords()].tile = temp_tile

async def display_current_tile():
    #TODO: a larger problem: store colors not on the tiles themselves but
    #      numbers to be retrieved when the tile or actor or item is accessed?
    await asyncio.sleep(1)
    while True:
        await asyncio.sleep(.1)
        current_coords = actor_dict['player'].coords()
        current_tile = map_dict[current_coords].tile
        with term.location(80, 0):
            print("current tile: {}".format(current_tile))
        with term.location(80, 1):
            print("repr() of tile: {}".format(repr(current_tile)))

async def pressure_plate(appearance='▓░', spawn_coord=(4, 0), 
                         patch_to_key='switch_1', off_delay=.5, 
                         tile_color=7, test_rate=.1, display_timer=False,
                         positives=None, sound_choice='default'):
    #TODO: rewrite pressure plate to be a thing that reacts to change rather
    #than constantly check for change.
    """
    creates a pressure plate on the map at specified spawn_coord.

    If positives is a list (instead of None), it will only accept things
    with names containing one of the specified colors/attributes. 
    Otherwise, it will be a list of generic objects that tend to trigger
    pressure plates.
    """
    appearance = [term.color(tile_color)(char) for char in appearance]
    map_dict[spawn_coord].tile = appearance[0]
    plate_id = generate_id(base_name='pressure_plate')
    state_dict[patch_to_key][plate_id] = False
    exclusions = ('sword', 'particle')
    sound_effects = {'default':'*click*',
                       'stone':'*stone on stone nearby*'}
    if positives is None:
        positives = ('player', 'weight', 'crate', 'static')
    count = 0
    triggered = False
    while True:
        count = (count + 1) % 100
        await asyncio.sleep(test_rate)
        positive_result = await check_actors_on_tile(coords=spawn_coord, positives=positives)
        if positive_result:
            if not triggered:
                asyncio.ensure_future(filter_print(output_text=sound_effects[sound_choice]))
            triggered = True
            map_dict[spawn_coord].tile = appearance[1]
            state_dict[patch_to_key][plate_id] = True
            if display_timer:
                x_pos, y_pos = (int(term.width / 2 - 2), 
                                int(term.height / 2 - 2),)
                await timer(x_pos=x_pos - 8, y_pos=(y_pos + 15), time_minutes=0, time_seconds=5, resolution=1)
            if off_delay:
                await asyncio.sleep(off_delay)
        else:
            triggered = False
            state_dict[patch_to_key][plate_id] = False
            map_dict[spawn_coord].tile = appearance[0]

async def puzzle_pair(block_coord=(-10, -10), plate_coord=(-10, -7), puzzle_name='puzzle_0', 
                      color_num=3, block_char='☐'):
    """
    creates a paired pressure plate and uniquely keyed block that will trigger
    the plate when pushed atop
    """
    state_dict[puzzle_name] = {}
    block_tile = term.color(color_num)(block_char)
    asyncio.ensure_future(spawn_weight(base_name=puzzle_name, 
                                       spawn_coord=block_coord, 
                                       tile=block_tile))
    asyncio.ensure_future(pressure_plate(spawn_coord=plate_coord, 
                                         tile_color=color_num,
                                         positives=(puzzle_name, 'null'), #positives needs to be a tuple
                                         patch_to_key=puzzle_name))
    return puzzle_name
            
async def any_true(trigger_key):
    return any(i for i in state_dict[trigger_key].values())

async def state_toggle(sequence=(0, 1), time_between_triggers=1, trigger_key='test', channel=1):
    looping_values = cycle(sequence)
    state_dict[trigger_key] = {channel:1}
    while True:
        state_dict[trigger_key][channel] = next(looping_values)
        map_dict[9, 9].tile = str(state_dict[trigger_key][channel])[0]
        await asyncio.sleep(time_between_triggers)

async def flip_sync(listen_key='test', trigger_key='test2', channel=1, listen_interval=.1):
    state_dict[trigger_key] = {channel:1}
    while True:
        state_dict[trigger_key][channel] = not state_dict[trigger_key][channel]
        map_dict[11, 9].tile = str(state_dict[trigger_key][channel])[0]
        await asyncio.sleep(listen_interval)

async def trigger_door(patch_to_key='switch_1', door_coord=(0, 0), default_state='closed'):
    draw_door(*door_coord, description='iron', locked=True)
    while True:
        await asyncio.sleep(.25)
        trigger_state = await any_true(trigger_key=patch_to_key)
        if trigger_state == True:
            if default_state == 'closed':
                open_door(door_coord)
            else:
                close_door(door_coord)
        else:
            if default_state == 'closed':
                close_door(door_coord)
            else:
                open_door(door_coord)

async def sword(direction='n', actor='player', length=5, name='sword', 
                speed=.1, retract_speed=.1, damage=100, sword_color=1):
    """extends and retracts a line of characters
    TODO: end the range once it hits a wall
    """
    if 'sword_out' in state_dict and state_dict['sword_out'] == True:
        return False
    await asyncio.sleep(0)
    state_dict['sword_out'] = True
    dir_coords = {'n':(0, -1, '│'), 'e':(1, 0, '─'), 's':(0, 1, '│'), 'w':(-1, 0, '─')}
    opposite_directions = {'n':'s', 'e':'w', 's':'n', 'w':'e'}
    starting_coords = actor_dict[actor].coords()
    chosen_dir = dir_coords[direction]
    sword_id = generate_id(base_name=name)
    sword_segment_names = ["{}_{}_{}".format(name, sword_id, segment) for segment in range(1, length)]
    segment_coords = [(starting_coords[0] + chosen_dir[0] * i, 
                       starting_coords[1] + chosen_dir[1] * i) 
                      for i in range(1, length)]
    to_damage_names = []
    for segment_coord, segment_name in zip(segment_coords, sword_segment_names):
        actor_dict[segment_name] = Actor(name=segment_name, moveable=False,
                                         tile=term.color(sword_color)(chosen_dir[2]))
        map_dict[segment_coord].actors[segment_name] = True
        for actor in map_dict[segment_coord].actors.items():
            if 'sword' not in actor[0]:
                to_damage_names.append(actor[0])
        await asyncio.sleep(speed)
    for actor in to_damage_names:
        damage_direction = opposite_directions[direction]
        if actor == 'player':
            asyncio.ensure_future(directional_damage_alert(source_direction=damage_direction))
        asyncio.ensure_future(damage_actor(actor=actor, damage=damage))
    for segment_coord, segment_name in zip(reversed(segment_coords), reversed(sword_segment_names)):
        if segment_name in map_dict[segment_coord].actors: 
            del map_dict[segment_coord].actors[segment_name]
        del actor_dict[segment_name]
        await asyncio.sleep(retract_speed)
    state_dict['sword_out'] = False

async def sword_item_ability(length=3):
    facing_dir = state_dict['facing']
    asyncio.ensure_future(sword(facing_dir, length=length))

async def dash_ability(dash_length=20, direction=None, time_between_steps=.03):
    if direction is None:
        direction = state_dict['facing']
    asyncio.ensure_future(dash_along_direction(distance=dash_length, direction=direction, 
                                               time_between_steps=time_between_steps))

async def teleport_in_direction(direction=None, distance=15, flashy=True):
    if direction is None:
        direction = state_dict['facing']
    directions_to_offsets = {'n':(0, -distance), 'e':(distance, 0), 
                             's':(0, distance), 'w':(-distance, 0),}
    player_coords = actor_dict['player'].coords()
    destination_offset = directions_to_offsets[direction]
    destination = add_coords(player_coords, destination_offset)
    if flashy:
        await flashy_teleport(destination=destination)

async def flashy_teleport(destination=(0, 0), actor='player'):
    """
    does a flash animation of drawing in particles then teleports the player
        to a given location.
    uses 2adial_fountain in collapse mode for the effect
    upon arrival, a random nova of particles is released (also using 
        radial_fountain but in reverse
    """
    await asyncio.sleep(.25)
    if map_dict[destination].passable:
        await radial_fountain(frequency=.02, deathclock=75, radius=(5, 18), speed=(1, 1))
        await asyncio.sleep(.2)
        actor_dict[actor].update(1000, 1000)
        await asyncio.sleep(.8)
        actor_dict[actor].update(*destination)
        await radial_fountain(frequency=.002, collapse=False, radius=(5, 12),
                              deathclock=30, speed=(1, 1))
    else:
        await filter_print(output_text="Something is in the way.")
    
async def random_blink(actor='player', radius=20):
    current_location = actor_dict[actor].coords()
    await asyncio.sleep(.2)
    actor_dict[actor].update(*(500, 500))
    await asyncio.sleep(.2)
    while True:
        await asyncio.sleep(.01)
        rand_x = randint(-radius, radius) + current_location[0]
        rand_y = randint(-radius, radius) + current_location[1]
        blink_to = (rand_x, rand_y)
        distance = point_to_point_distance(point_a=blink_to, 
                                           point_b=current_location)
        if distance > radius:
            continue
        line_of_sight_result = await check_line_of_sight(coord_a=current_location, coord_b=blink_to)
        if line_of_sight_result is None:
            continue
        if type(line_of_sight_result) is bool:
            if line_of_sight_result is True:
                actor_dict[actor].update(*blink_to)
                return
            else:
                continue
        else:
            actor_dict[actor].update(*line_of_sight_result)
            return

async def temporary_block(duration=5, animation_preset='energy block'):
    directions = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
    facing_dir_offset = directions[state_dict['facing']]
    actor_coords = actor_dict['player'].coords()
    spawn_coord = (actor_coords[0] + facing_dir_offset[0],
                   actor_coords[1] + facing_dir_offset[1])
    block_id = generate_id(base_name='weight')
    asyncio.ensure_future(timed_actor(death_clock=duration, name=block_id, coords=spawn_coord,
                          rand_delay=0, solid=False, moveable=True, 
                          animation_preset=animation_preset))

async def temp_view_circle(duration=5, radius=6, center_coord=(0, 0)):
    """
    carves out a temporary zone of the map that can be viewed regardless
    of whether it's through a wall or behind the player's fov arc.
    """
    temp_circle = get_circle(center=center_coord, radius=radius)
    shuffle(temp_circle)
    for coord in temp_circle:
        await asyncio.sleep(.01)
        map_dict[coord].override_view = True
    await asyncio.sleep(duration)
    shuffle(temp_circle)
    for coord in temp_circle:
        asyncio.sleep(.01)
        map_dict[coord].override_view = False

#Item interaction---------------------------------------------------------------

#TODO: create a weight that can be picked up and stored in one's inventory.
#      alternatively: an item that disappears when used and returns when the
#TODO: an item that when thrown, temporarily creates a circle of overriden_view == True
#      acts like a security camera?
#      cooldown expires.
#TODO: items that are used immediately upon pickup

def spawn_item_at_coords(coord=(2, 3), instance_of='wand', on_actor_id=False):
    wand_broken_text = " is out of charges."
    shift_amulet_kwargs = {'x_offset':1000, 'y_offset':1000, 'plane_name':'nightmare'}
    possible_items = ('wand', 'nut', 'fused charge', 'shield wand', 'red potion',
                      'shiny stone', 'shift amulet', 'red sword', 'vine wand',
                      'eye trinket', 'high explosives', 'red key', 'green key', 
                      'rusty key')
    block_wand_text = "A shimmering block appears."
    if instance_of == 'random':
        instance_of = choice(possible_items)
    item_id = generate_id(base_name=instance_of)
    item_catalog = {'wand':{'uses':10, 'tile':term.blue('/'), 'usable_power':temporary_block,
                            'power_kwargs':{'duration':5}, 'use_message':block_wand_text},
                     'nut':{'uses':9999, 'tile':term.red('⏣'), 'usable_power':throw_item, 
                            'power_kwargs':{'thrown_item_id':item_id}},
            'fused charge':{'uses':9999, 'tile':term.green('⏣'), 'usable_power':fused_throw_action, 
                            'power_kwargs':{'thrown_item_id':item_id, 'radius':6}},
         'high explosives':{'uses':9999, 'tile':term.red('\\'), 'usable_power':fused_throw_action, 
                            'power_kwargs':{'thrown_item_id':item_id, 'throw_distance':1, 
                                            'radius':15, 'damage':150, 'fuse_length':9,
                                            'particle_count':30, 'rand_drift':0}},
             'shield wand':{'uses':10, 'tile':term.blue('/'), 'power_kwargs':{'radius':6},
                            'usable_power':spawn_bubble, 'broken_text':wand_broken_text},
              'red potion':{'uses':1, 'tile':term.red('◉'), 'power_kwargs':{'item_id':item_id, 
                            'total_restored':50}, 'usable_power':health_potion, 
                            'broken_text':wand_broken_text},
             'shiny stone':{'uses':9999, 'tile':term.blue('o'), 
                            'power_kwargs':{'radius':5, 'track_actor':'player'}, 
                            'usable_power':orbit, 'broken_text':wand_broken_text},
            'shift amulet':{'uses':999, 'tile':term.blue('O̧'), 'power_kwargs':shift_amulet_kwargs,
                            'usable_power':pass_between, 'broken_text':"Something went wrong."},
               'red sword':{'uses':9999, 'tile':term.red('ļ'), 'power_kwargs':{'length':3},
                            'usable_power':sword_item_ability, 'broken_text':"Something went wrong."},
               'vine wand':{'uses':9999, 'tile':term.green('/'), 'usable_power':vine_grow, 
                            'power_kwargs':{'on_actor':'player', 'start_facing':True}, 
                            'broken_text':wand_broken_text},
            'dash trinket':{'uses':9999, 'tile':term.blue('⥌'), 'usable_power':dash_ability, 
                            'power_kwargs':{'dash_length':20}, 'broken_text':wand_broken_text},
                 'red key':{'uses':9999, 'tile':term.red('⚷'), 'usable_power':unlock_door, 
                            'power_kwargs':{'opens':'red'}, 'broken_text':wand_broken_text,
                            'use_message':''},
               'green key':{'uses':9999, 'tile':term.green('⚷'), 'usable_power':unlock_door, 
                            'power_kwargs':{'opens':'green'}, 'broken_text':wand_broken_text,
                            'use_message':None},
               'rusty key':{'uses':3, 'tile':term.color(3)('⚷'), 'usable_power':unlock_door, 
                            'power_kwargs':{'opens':'rusty'}, 'broken_text':'the key breaks off in the lock',
                            'use_message':None},
             'eye trinket':{'uses':9999, 'tile':term.blue('⚭'), 'usable_power':random_blink, 
                            'power_kwargs':{'radius':50}, 'broken_text':wand_broken_text}}
    #item generation:
    if instance_of in item_catalog:
        item_dict[item_id] = Item(name=instance_of, item_id=item_id, spawn_coord=coord,
                                  **item_catalog[instance_of])
        if not on_actor_id:
            map_dict[coord].items[item_id] = True
        else:
            actor_dict[on_actor_id].holding_items[item_id] = True

async def display_items_at_coord(coord=actor_dict['player'].coords(), x_pos=2, y_pos=16):
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

async def display_items_on_actor(actor_key='player', x_pos=2, y_pos=1):
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

async def filter_print(output_text="You open the door.", x_offset=0, y_offset=-8, 
                       pause_fade_in=.01, pause_fade_out=.01, pause_stay_on=1, 
                       delay=0, blocking=False, hold_for_lock=True):
    if hold_for_lock:
        count = 0
        while True:
            if state_dict['printing'] == True:
                await asyncio.sleep(.1)
            else:
                break
    if x_offset == 0:
        x_offset = -int(len(output_text) / 2)
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    y_location = term.height + y_offset
    x_location = middle_x + x_offset
    await asyncio.sleep(0)
    numbered_chars = [(place, char) for place, char in enumerate(output_text)]
    shuffle(numbered_chars)
    for char in numbered_chars:
        with term.location(char[0] + x_location, y_location):
            print(char[1])
        if not blocking:
            await asyncio.sleep(pause_fade_in)
    shuffle(numbered_chars)
    await asyncio.sleep(pause_stay_on)
    for char in numbered_chars:
        with term.location(char[0] + x_location, y_location):
            print(' ')
        if not blocking:
            await asyncio.sleep(pause_fade_out)
        else:
            asyncio.sleep(pause_fade_out)
    state_dict['printing'] = False #releasing hold on printing to the screen
    await asyncio.sleep(1)
    with term.location(50, 7):
        print(" " * 100)

async def filter_fill(top_left_coord=(30, 10), x_size=10, y_size=10, 
                      pause_between_prints=.005, pause_stay_on=3, 
                      fill_char=term.red('X'), random_order=True):
    coord_list = [(x, y) for x in range(x_size) for y in range(y_size)]
    fill_char = choice('123456789')
    if random_order:
        shuffle(coord_list) #shuffle coord_list in place
    x_offset, y_offset = top_left_coord
    for pair in coord_list:
        await asyncio.sleep(pause_between_prints)
        print_coord = pair[0] + x_offset, pair[1] + y_offset
        with term.location(*print_coord):
            print(fill_char)

def print_screen_grid():
    """
    prints an overlay for finding positions of text
    """
    for y in range(term.height // 5):
        for x in range(term.width // 5):
            with term.location(x * 5, y * 5):
                print(".")

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
                passable=False, stamp=True, paint=True, color_num=1, description='',
                pause_between=.02):
    """ given a root node, picks random points within a radius length and writes
    characters from the given palette to their corresponding map_dict cell.
    """
    await asyncio.sleep(0)
    for i in range(seeds):
        await asyncio.sleep(pause_between)
        throw_dist = radius + 1
        while throw_dist >= radius:
            x_toss, y_toss = (randint(-radius, radius),
                              randint(-radius, radius),)
            throw_dist = sqrt(x_toss**2 + y_toss**2) #distance
        toss_coord = (root_x + x_toss, root_y + y_toss)
        if paint:
            if map_dict[toss_coord].tile not in "▮▯":
                colored_tile = term.color(color_num)(map_dict[toss_coord].tile)
                map_dict[toss_coord].tile = colored_tile
        else:
            random_tile = choice(palette)
            map_dict[toss_coord].tile = term.color(color_num)(random_tile)
        if not stamp:
            map_dict[toss_coord].passable = passable
        if description:
            map_dict[toss_coord].description = description

def clear():
    """
    clears the screen.
    """
    # check and make call for specific operating system
    _ = call('clear' if os.name =='posix' else 'cls')

def draw_door(x, y, closed=True, locked=False, description='wooden', is_door=True):
    """
    creates a door at the specified map_dict coordinate and sets the relevant
    attributes.
    """
    door_colors = {'red':1, 'green':2, 'orange':3, 'wooden':3, 'rusty':3, 
                   'blue':4, 'purple':5, 'cyan':6, 'grey':7, 'white':8,
                   'iron':7}
    states = [('▮', False, True), ('▯', True, False)]
    if closed:
        tile, passable, blocking = states[0]
    else:
        tile, passable, blocking = states[1]
    map_dict[(x, y)].tile = term.color(door_colors[description])(tile)
    map_dict[(x, y)].passable = passable
    map_dict[(x, y)].blocking = blocking
    map_dict[(x, y)].is_door = is_door
    map_dict[(x, y)].locked = locked
    map_dict[(x, y)].key = description

async def fake_stairs(coord_a=(8, 0), coord_b=(41, 10), 
                      hallway_offset=(-1000, -1000), hallway_length=15):
    #draw hallway
    draw_box(top_left=hallway_offset, x_size=hallway_length, y_size=1, tile="░")
    coord_a_hallway = hallway_offset
    coord_b_hallway = add_coords(hallway_offset, (hallway_length, 0))
    #create magic doors:
    await create_magic_door_pair(door_a_coords=coord_a, door_b_coords=coord_a_hallway, silent=True)
    await create_magic_door_pair(door_a_coords=coord_b, door_b_coords=coord_b_hallway, silent=True)

#TODO: create a mirror

async def magic_door(start_coord=(5, 5), end_coords=(-22, 18), 
                     horizon_orientation='vertical', silent=False,
                     destination_plane='normal'):
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
    direction_offsets = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
    await asyncio.sleep(0)
    animation = Animation(base_tile='▮', preset='door')
    map_dict[start_coord] = Map_tile(tile=" ", blocking=False, passable=True,
                                     magic=True, magic_destination=end_coords,
                                     is_animated=True, animation=animation)
    while(True):
        await asyncio.sleep(.1)
        player_coords = actor_dict['player'].coords()
        just_teleported = actor_dict['player'].just_teleported
        #TODO: add an option for non-player actors to go through.
        if player_coords == start_coord and not just_teleported:
            last_location = state_dict['last_location']
            difference_from_door_coords = (start_coord[0] - last_location[0], 
                                           start_coord[1] - last_location[1])
            destination = add_coords(end_coords, difference_from_door_coords)
            if map_dict[destination].passable:
                if not silent:
                    asyncio.ensure_future(filter_print(output_text="You are teleported."))
                map_dict[player_coords].passable=True
                actor_dict['player'].update(*destination)
                actor_dict['player'].just_teleported = True
                state_dict['plane'] = destination_plane

async def create_magic_door_pair(door_a_coords=(5, 5), door_b_coords=(-25, -25), silent=False,
                                 source_plane='normal', destination_plane='normal'):
    loop = asyncio.get_event_loop()
    loop.create_task(magic_door(start_coord=(door_a_coords), end_coords=(door_b_coords), silent=silent, 
                                destination_plane=destination_plane),)
    loop.create_task(magic_door(start_coord=(door_b_coords), end_coords=(door_a_coords), silent=silent,
                                destination_plane=source_plane))

async def spawn_container(base_name='box', spawn_coord=(5, 5), tile='☐',
                          breakable=True, moveable=True, preset='random'):
    box_choices = ['', 'nut', 'high explosives', 'red potion', 'fused charge']
    if preset == 'random':
        contents = [choice(box_choices)]
    container_id = spawn_static_actor(base_name=base_name, spawn_coord=spawn_coord,
                                      tile=tile, moveable=moveable, breakable=breakable)
    actor_dict[container_id].holding_items = contents
    #add holding_items after container is spawned.

async def spawn_weight(base_name='weight', spawn_coord=(-2, -2), tile='█'):
    """
    spawns a pushable box to trigger pressure plates or other puzzle elements.
    """
    weight_id = spawn_static_actor(base_name=base_name, 
                                   spawn_coord=spawn_coord,
                                   tile=tile, breakable=False, 
                                   moveable=True)

def spawn_static_actor(base_name='static', spawn_coord=(5, 5), tile='☐',
                       animation_preset=None, breakable=True, moveable=False,
                       multi_tile_parent=None, blocking=False, literal_name=False):
    """
    Spawns a static (non-controlled) actor at coordinates spawn_coord
    and returns the static actor's id.
    """
    #TODO: add an alternate way of returning a name given a leading '_'
    if literal_name:
        actor_id = base_name
    else:
        actor_id = generate_id(base_name=base_name)
    if animation_preset is not None:
        is_animated = True
        animation = Animation(preset=animation_preset)
    else:
        is_animated = False
        animation = None
    actor_dict[actor_id] = Actor(name=actor_id, tile=tile,
                                 is_animated=is_animated, animation=animation,
                                 x_coord=spawn_coord[0], y_coord=spawn_coord[1], 
                                 breakable=breakable, moveable=moveable,
                                 multi_tile_parent=multi_tile_parent,
                                 blocking=blocking)
    map_dict[spawn_coord].actors[actor_id] = True
    return actor_id

def map_init():
    clear()
    draw_box(top_left=(-25, -25), x_size=50, y_size=50, tile="░") #large debug room
    draw_centered_box(middle_coord=(0, 0), x_size=10, y_size=10, tile="░")
    draw_box(top_left=(15, 15), x_size=10, y_size=10, tile="░")
    draw_box(top_left=(30, 15), x_size=10, y_size=11, tile="░")
    draw_box(top_left=(42, 10), x_size=20, y_size=20, tile="░")
    draw_box(top_left=(7, 5), x_size=5, y_size=5, tile="░")
    passages = [(7, 5, 7, 17), (17, 17, 25, 10), (20, 20, 35, 20), 
                (0, 0, 17, 17), (39, 20, 41, 20), (60, 20, 90, 20)]
    doors = [(7, 16), (14, 17), (29, 20), (41, 20)]
    for passage in passages:
        connect_with_passage(*passage)
    for door in doors:
        draw_door(*door, locked=False)
    draw_door(*(-5, -5), locked=True, description='green')
    draw_door(0, 5, locked=True, description='rusty', is_door=True)
    spawn_item_at_coords(coord=(-1, 1), instance_of='rusty key', on_actor_id=False)
    announcement_at_coord(coord=(0, 17), distance_trigger=5, 
                          announcement="something slithers into the wall as you approach.")
    announcement_at_coord(coord=(7, 17), distance_trigger=1, 
                          announcement="you hear muffled scratching from the other side")

def announcement_at_coord(coord=(0, 0), announcement="Testing...", distance_trigger=None):
    """
    creates a one-time announcement at coord.
    split announcement up into separate sequential pieces with pipes
    pipes are parsed in view_tile
    """
    map_dict[coord].announcement = announcement
    map_dict[coord].announcing = True
    map_dict[coord].distance_trigger = distance_trigger

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
    """handles raw keyboard data, passes to handle_input if its interesting.
    Also, displays help tooltip if no input for a time."""
    debug_text = "key is: {}, same_count is: {}           "
    help_text = 'Press ? for help menu.'
    await asyncio.sleep(0)
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        key = None
        state_dict['same_count'] = 0
        old_key = None
        while True:
            await asyncio.sleep(0.01)
            if isData():
                key = sys.stdin.read(1)
                if key == '\x7f':  # x1b is ESC
                    state_dict['exiting'] = True
                if key is not None:
                    await handle_input(key)
            if old_key == key:
                state_dict['same_count'] += 1
            else:
                state_dict['same_count'] = 0
            old_key = key
            if state_dict['same_count'] >= 600 and state_dict['same_count'] % 600 == 0:
                asyncio.ensure_future(filter_print(output_text=help_text, pause_stay_on=2))
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
    directions = {'a':(-1, 0), 'd':(1, 0), 'w':(0, -1), 's':(0, 1),}
    key_to_compass = {'w':'n', 'a':'w', 's':'s', 'd':'e', 
                      'W':'n', 'A':'w', 'S':'s', 'D':'e', 
                      'i':'n', 'j':'w', 'k':'s', 'l':'e'}
    compass_directions = ('n', 'e', 's', 'w')
    fov = 120
    dir_to_name = {'n':'North', 'e':'East', 's':'South', 'w':'West'}
    await asyncio.sleep(0)  
    if state_dict['in_menu'] == True:
        if await is_number(key):
            if int(key) in state_dict['menu_choices']:
                state_dict['menu_choice'] = key
        else:
            state_dict['menu_choice'] = False
            state_dict['in_menu'] = False
    elif state_dict['exiting'] == True:
        middle_x, middle_y = (int(term.width / 2 - 2), 
                              int(term.height / 2 - 2),)
        quit_question_text = 'Really quit? (y/n)'
        term_location = (middle_x - int(len(quit_question_text)/2), middle_y - 16)
        with term.location(*term_location):
            print(quit_question_text)
        if key in 'yY':
            state_dict['killall'] = True #trigger shutdown condition
        elif key in 'nN': #exit menus
            with term.location(*term_location):
                print(' ' * len(quit_question_text))
            state_dict['exiting'] = False
    else:
        player_coords = actor_dict['player'].coords()
        if key in directions:
            push_return_val = None
            if key in 'wasd': #try to push adjacent things given movement keys
                if actor_dict['player'].stamina >= 20:
                    push(pusher='player', direction=key_to_compass[key])
                    walk_destination = add_coords(player_coords, directions[key])
                    if occupied(walk_destination):
                        actor_dict['player'].stamina -= 2
                        x_shift, y_shift = directions[key]
                else:
                    asyncio.ensure_future(filter_print(output_text='Out of breath!'))
            actor_dict['player'].just_teleported = False #used by magic_doors
        if key in 'WASD': 
            if actor_dict['player'].stamina >= 15:
                asyncio.ensure_future(dash_ability(dash_length=5, direction=key_to_compass[key], 
                                                   time_between_steps=.04))
                actor_dict['player'].stamina -= 15
            else:
                asyncio.ensure_future(filter_print(output_text='Out of breath!'))
        if key in '?':
            await display_help() 
        if key in '3': #shift dimensions
            asyncio.ensure_future(pass_between(x_offset=1000, y_offset=1000, plane_name='nightmare'))
        if key in '4':
            with term.location(50, 0):
                draw_net()
        if key in '8': #export map
            asyncio.ensure_future(export_map())
        if key in 'Xx': #examine
            description = map_dict[(x, y)].description
            asyncio.ensure_future(filter_print(output_text=description))
        if key in ' ': #toggle doors
            toggle_doors()
        if key in '@': #spawn debug items in player inventory
            spawn_item_at_coords(coord=player_coords, instance_of='fused charge', on_actor_id='player')
        if key in 'Z': #test out points_around_point and write result to map_dict
            points = points_around_point()
            for point in points:
                map_dict[add_coords(point, player_coords)].tile = '$'
        if key in '$':
            print_screen_grid() 
        if key in '(':
            spawn_coords = add_coords(player_coords, (2, 2))
            asyncio.ensure_future(spawn_mte(spawn_coord=spawn_coords))
        if key in ')':
            for mte_name in mte_dict:
                multi_push(mte_parent=mte_name)
        if key in '9': #creates a passage in a random direction from the player
            dir_to_angle = {'n':270, 'e':0, 's':90, 'w':180}
            facing_angle = dir_to_angle[state_dict['facing']]
            chain_of_arcs(starting_angle=facing_angle, start_coord=player_coords, num_arcs=5)
        if key in '^':
            cells = get_cells_along_line(num_points=10, end_point=(0, 0),
                                         start_point=player_coords)
            cells = add_jitter_to_middle(cells=cells)
            chained_pairs = chained_pairs_of_items(cells)
            multi_segment_passage(cells)
        if key in 'g': #pick up an item from the ground
            asyncio.ensure_future(item_choices(coords=(x, y)))
        if key in 'Q': #equip an item to slot q
            asyncio.ensure_future(equip_item(slot='q'))
        if key in 'E': #equip an item to slot e
            asyncio.ensure_future(equip_item(slot='e'))
        if key in 't': #throw a chosen item
            asyncio.ensure_future(throw_item())
        if key in 'q': #use item in slot q
            asyncio.ensure_future(use_item_in_slot(slot='q'))
        if key in 'e': #use item in slot e
            asyncio.ensure_future(use_item_in_slot(slot='e'))
        if key in 'h': #debug health restore
            asyncio.ensure_future(health_potion())
        if key in 'v': #debug health restore
            asyncio.ensure_future(vine_grow())
        if key in 'u':
            asyncio.ensure_future(use_chosen_item())
        if key in 'M':
            #asyncio.ensure_future(drag_actor_along_line(actor_name='player', line=None, linger_time=.2))
            #asyncio.ensure_future(rand_blink())
            asyncio.ensure_future(disperse_all_mte())
            #append_to_log()
        if key in '#':
            actor_dict['player'].update(49, 21) #jump to debug location
        if key in 'Y':
            player_coords = actor_dict['player'].coords()
            asyncio.ensure_future(temp_view_circle(center_coord=player_coords))
        if key in '%': #place a temporary pushable block
            asyncio.ensure_future(temporary_block())
        if key in 'f': #use sword in facing direction
            await sword_item_ability()
        if key in '7':
            asyncio.ensure_future(draw_circle(center_coord=actor_dict['player'].coords(), 
                                  animation=Animation(preset='water')))
        if key in 'R': #generate a random cave room around the player
            player_coords = add_coords(actor_dict['player'].coords(), (-50, -50))
            test_room = cave_room()
            write_room_to_map(room=test_room, top_left_coord=player_coords)
        if key in 'b': #spawn a force field around the player.
            asyncio.ensure_future(spawn_bubble())
        if key in '1': #draw a passage on the map back to (0, 0).
            n_wide_passage(coord_a=(actor_dict['player'].coords()), coord_b=(0, 0), palette="░", width=5)
        shifted_x, shifted_y = x + x_shift, y + y_shift
        if map_dict[(shifted_x, shifted_y)].passable and (shifted_x, shifted_y) is not (0, 0):
            state_dict['last_location'] = (x, y)
            map_dict[(x, y)].passable = True #make previous space passable
            actor_dict['player'].update(x + x_shift, y + y_shift)
            x, y = actor_dict['player'].coords()
            map_dict[(x, y)].passable = False #make current space impassable
        if key in "ijkl": #change viewing direction
            state_dict['facing'] = key_to_compass[key]
            with term.location(40, 1):
                print(state_dict['facing'])

def open_door(door_coord, door_tile='▯'):
    map_dict[door_coord].tile = door_tile
    map_dict[door_coord].passable = True
    map_dict[door_coord].blocking = False

def close_door(door_coord, door_tile='▮'):
    map_dict[door_coord].tile = door_tile
    map_dict[door_coord].passable = False
    map_dict[door_coord].blocking = True

def toggle_door(door_coord):
    door_state = map_dict[door_coord].tile 
    open_doors = [term.color(i)('▯') for i in range(10)]
    open_doors.append('▯')
    closed_doors = [term.color(i)('▮') for i in range(10)]
    closed_doors.append('▮')
    if map_dict[door_coord].locked:
        description = map_dict[door_coord].key
        output_text="The {} door is locked.".format(description)
        asyncio.ensure_future(filter_print(output_text=output_text))
        return
    if door_state in closed_doors:
        open_door_tile = open_doors[closed_doors.index(door_state)]
        open_door(door_coord, door_tile=open_door_tile)
    elif door_state in open_doors:
        closed_door_tile = closed_doors[open_doors.index(door_state)]
        close_door(door_coord, door_tile=closed_door_tile)

def toggle_doors():
    x, y = actor_dict['player'].coords()
    door_dirs = {(-1, 0), (1, 0), (0, -1), (0, 1)}
    for door in door_dirs:
        door_coord = (x + door[0], y + door[1])
        toggle_door(door_coord)

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
        'red sword':('┌───┐',
                     '│  {}│'.format(term.red('╱')),
                     '│ {} │'.format(term.red('╱')),
                     '│{}  │'.format(term.bold(term.red('╳'))),
                     '└───┘',),
              'nut':('┌───┐',
                     '│/ \│', 
                     '│\_/│',
                     '│\_/│',
                     '└───┘',),
     'dash trinket':('┌───┐',
                     '│ ║╲│', 
                     '│ ║ │',
                     '│╲║ │',
                     '└───┘',),
       'red potion':('┌───┐',
                     '│┌O┐│', 
                     '│|{}|│'.format(term.red('█')),
                     '│└─┘│',
                     '└───┘',),
     'fused charge':('┌───┐',
                     '│/*\│', 
                     '│\_/│',
                     '│\_/│',
                     '└───┘',),
  'high explosives':('┌───┐',
                     '│ ╭ │', 
                     '│ {} │'.format(term.red('█')),
                     '│ {} │'.format(term.red('█')),
                     '└───┘',),
     'shift amulet':('┌───┐',
                     '│╭─╮│', 
                     '││ ││',
                     '│╰ʘ╯│',
                     '└───┘',),
      'eye trinket':('┌───┐',
                     '│   │', 
                     '│<ʘ>│',
                     '│   │',
                     '└───┘',),
          'red key':('┌───┐',
                     '│ {} │'.format(term.red('╒')),
                     '│ {} │'.format(term.red('│')),
                     '│ {} │'.format(term.red('O')),
                     '└───┘',),
        'green key':('┌───┐',
                     '│ {} │'.format(term.green('╒')),
                     '│ {} │'.format(term.green('│')),
                     '│ {} │'.format(term.green('O')),
                     '└───┘',),
        'rusty key':('┌───┐',
                     '│ {} │'.format(term.color(3)('╒')),
                     '│ {} │'.format(term.color(3)('│')),
                     '│ {} │'.format(term.color(3)('O')),
                     '└───┘',),
      'shiny stone':('┌───┐',   #effect while equipped: orbit
                     '│ _ │', 
                     '│(_)│',
                     '│   │',
                     '└───┘',),
            'empty':('┌───┐',
                     '│   │', 
                     '│   │',
                     '│   │',
                     '└───┘',),}
    for (num, line) in enumerate(icons[icon_name]):
        with term.location(x_coord, y_coord + num):
            print(line)

async def choose_item(item_id_choices=None, item_id=None, x_pos=0, y_pos=10):
    """
    Takes a list of item_id values
    Prints to some region of the screen:
    Get stuck in a loop until a choice is made:
    Returns an item_id
    """
    #defaults to items in player's inventory if item_id_choices is passed None
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
            #TODO: fix limited slots in inventory choices
            if menu_choice in [str(i) for i in range(10)]:
                menu_choice = int(menu_choice)
        if menu_choice in menu_choices:
            await clear_screen_region(x_size=2, y_size=len(item_id_choices), 
                                      screen_coord=(x_pos, y_pos))
            state_dict['in_menu'] = False
            state_dict['menu_choice'] = -1 # not in range as 1 evaluates as True.
            return item_id_choices[int(menu_choice)]

async def console_box(width=40, height=10, x_margin=4, y_margin=30):
    #await asyncio.sleep(3)
    state_dict['messages'] = [''] * height
    asyncio.ensure_future(ui_box_draw(box_height=height, box_width=width, 
                                      x_margin=x_margin - 1, y_margin=y_margin - 1))
    garbage = [(i, random()) for i in range(15)]
    window = 0
    while True:
        for index, line_y in enumerate(range(y_margin, y_margin + height)):
            #we want to print the last <height> lines of the message queue
            #we want the indices to go from -10 to -1. state_dict['messages'][-height + index]
            with term.location(x_margin, line_y):
                #print(garbage[(index + window) % len(garbage)])
                print(state_dict['messages'][-height + index])
        window = (window + 1) % len(garbage)
        await asyncio.sleep(.4)
        #rand_index = randint(0, 9)
        #state_dict['messages'][rand_index] = randint(0, 20)

def append_to_log(message="This is a test ({})".format(round(random(), 2))):
    state_dict['messages'].append(message)
    
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
        equipped_item_id = state_dict[slot_name]
        if equipped_item_id not in actor_dict['player'].holding_items:
            item_name = 'empty'
            state_dict[slot_name] = 'empty'
        elif equipped_item_id not in ('empty', None):
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
    slot_name = "{}_slot".format(slot)
    item_id_choice = await choose_item()
    state_dict[slot_name] = item_id_choice
    if hasattr(item_dict[item_id_choice], 'name'):
        item_name = item_dict[item_id_choice].name
        equip_message = "Equipped {} to slot {}.".format(item_name, slot)
        #await filter_print(output_text=equip_message)
        append_to_log(message=equip_message)
    else:
        #await filter_print(output_text="Nothing to equip!")
        append_to_log(message="Nothing to equip!")

async def use_chosen_item():
    item_id_choice = await choose_item()
    if item_id_choice != None:
        asyncio.ensure_future(item_dict[item_id_choice].use())
    
async def use_item_in_slot(slot='q'):
    item_id = state_dict['{}_slot'.format(slot)]
    if item_id is 'empty':
        pass
    else:
        if item_dict[item_id].power_kwargs:
            asyncio.ensure_future(item_dict[item_id].use())
        else:
            #put custom null action here instead of 'Nothing happens.'
            #as given for each item.
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
    #asyncio.ensure_future(filter_print(pickup_text))
    append_to_log(message=pickup_text)
    return True

#Announcement/message handling--------------------------------------------------
async def parse_announcement(tile_coord_key):
    """ parses an annoucement, with a new line printed after each pipe """
    announcement_sequence = map_dict[tile_coord_key].announcement.split("|")
    for delay, line in enumerate(announcement_sequence):
        asyncio.ensure_future(filter_print(output_text=line, delay=delay * 2))

async def trigger_announcement(tile_coord_key, player_coords=(0, 0)):
    if map_dict[tile_coord_key].announcing and not map_dict[tile_coord_key].seen:
        if map_dict[tile_coord_key].distance_trigger:
            distance = point_to_point_distance(tile_coord_key, player_coords)
            if distance <= map_dict[tile_coord_key].distance_trigger:
                await parse_announcement(tile_coord_key)
                map_dict[tile_coord_key].seen = True
        else:
            await parse_announcement(tile_coord_key)
            map_dict[tile_coord_key].seen = True
    else:
        map_dict[tile_coord_key].seen = True

#Geometry functions-------------------------------------------------------------
def point_to_point_distance(point_a=(0, 0), point_b=(5, 5)):
    """ finds 2d distance between two points """
    x_run, y_run = [abs(point_a[i] - point_b[i]) for i in (0, 1)]
    distance = round(sqrt(x_run ** 2 + y_run ** 2))
    return distance

def get_circle(center=(0, 0), radius=5):
    radius_range = [i for i in range(-radius, radius + 1)]
    result = []
    for x in radius_range:
       for y in radius_range:
           distance = sqrt(x**2 + y**2)
           if distance <= radius:
               result.append((center[0] + x, center[1] + y))
    return result

def get_line(start, end):
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

def find_angle(p0=(0, -5), p1=(0, 0), p2=(5, 0), use_degrees=True):
    """
    find the angle between two points around a central point,
    as if the edges of a triangle
    """
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

async def point_angle_from_facing(actor_key='player', facing_dir=None, 
                                  offset_angle=0, radius=5):
    """
    returns a point nearest to the given radius at angle offset_angle degrees 
    from the given direction.

    -20 degrees from 'n' is 340 degrees.
     25 degrees from 'e' is 115 degrees.
    """
    if facing_dir is None:
        facing_dir = state_dict['facing']
    dir_to_angle = {'n':180, 'e':90, 's':0, 'w':270}
    #negative numbers into modulo wrap back around the other way.
    point_angle = (dir_to_angle[facing_dir] + offset_angle) % 360
    actor_coords = actor_dict[actor_key].coords()
    reference_point = (actor_coords[0], actor_coords[1] + 5)
    point = await point_at_distance_and_angle(angle_from_twelve=point_angle,
                                              central_point=actor_coords,
                                              reference_point=reference_point,
                                              radius=radius)
    with term.location(50, 0):
        print('facing: {}, point_angle: {}'.format(facing_dir, point_angle))
    return point

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

async def angle_checker(angle_from_twelve=0, fov=120):
    """
    breaks out angle_checking code used in view_tile()
    Determines whether the currently checked view tile is in the
    main field of view.
    """
    angle_from_twelve = int(angle_from_twelve)
    half_fov = fov // 2
    directions = ('n', 'e', 's', 'w')
    angle_pairs = ((360, 0), (90, 90), (180, 180), (270, 270))
    dir_to_angle_pair = dict(zip(directions, angle_pairs))
    facing = state_dict['facing'] 
    arc_pair = dir_to_angle_pair[facing] #of the format (angle, angle)
    is_in_left = (arc_pair[0] - half_fov) <= angle_from_twelve <= arc_pair[0] + half_fov
    is_in_right = (arc_pair[1] - half_fov) <= angle_from_twelve <= arc_pair[1] + half_fov
    if is_in_left or is_in_right:
        return True
    else:
        return False

async def angle_swing(radius=15):
    dir_to_angle = {'n':180, 'e':90, 's':360, 'w':270}
    current_angle = dir_to_angle[state_dict['facing']]
    while True:
        pull_angle = dir_to_angle[state_dict['facing']]
        difference = current_angle - pull_angle
        if difference < -180:
            difference %= 360
        if difference > 180:
            difference -= 360
        if difference < 0:
            current_angle += 5
        elif difference > 0:
            current_angle -= 5
        state_dict['current_angle'] = current_angle
        await asyncio.sleep(.01)

async def crosshairs(radius=15, crosshair_chars=('.', '*', '.'), fov=30, 
                     refresh_delay=.05):
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    central_point = (middle_x, middle_y)
    last_angle = None
    old_points = None #used for clearing out print location
    while True:
        current_angle = state_dict['current_angle']
        #clear last known location of crosshairs:
        if last_angle != current_angle:
            angles = (current_angle + fov, current_angle, current_angle - fov)
            points = [await point_at_distance_and_angle(radius=radius,
                                                        central_point=central_point,
                                                        angle_from_twelve=angle)
                                                        for angle in angles]
            if old_points is not None:
                for point in old_points:
                    with term.location(*point):
                        print(' ')
            #write current location of crosshairs to screen
            for char, point in zip(crosshair_chars, points):
                with term.location(*point):
                    print(char)
            old_points = points
        last_angle = current_angle
        await asyncio.sleep(refresh_delay)
#UI/HUD functions---------------------------------------------------------------

async def display_help():
    """
    displays controls at an unused part of the screen.
    """
    x_offset, y_offset = await offset_of_center(x_offset=-10, y_offset=-5)
    help_text = ( " wasd: move               ",
                  "space: open/close doors   ",
                  " ijkl: look               ",
                  "    g: grab item menu,    ",
                  "       0-9 to choose      ",
                  "  Q/E: equip item to slot,",
                  "       0-9 to choose      ",
                  "  q/e: use equipped item, ",
                  "    t: throw chosen item  ",
                  "    u: use selected item  ",
                  "    x: examine tile       ",)
    for line_number, line in enumerate(help_text):
        x_print_coord, y_print_coord = 0, 0
        asyncio.ensure_future(filter_print(output_text=line, pause_stay_on=5,
                              pause_fade_in=.015, pause_fade_out=.015,
                              x_offset=-40, y_offset=-30 + line_number,
                              hold_for_lock=False))

async def check_line_of_sight(coord_a=(0, 0), coord_b=(5, 5)):
    """
    intended to be used for occlusion.
    show the tile that the first collision happened at but not the following tile
    """
    walls = 0
    points = get_line(coord_a, coord_b)
    blocking_actor_index = None
    for index, point in enumerate(points):
        #TODO: make magic doors correctly be blocked behind MTEs
        if map_dict[point].magic == True:
            return await handle_magic_door(point=point, last_point=points[-1])
        elif map_dict[point].blocking == False:
            if map_dict[point].actors is not None:
                for actor in map_dict[point].actors:
                    if actor_dict[actor].blocking:
                        blocking_actor_index = index
                        break
        else:
            walls += 1
        if walls > 1: #exit early if there's a wall in the way
            return False
    if blocking_actor_index is not None:
        if blocking_actor_index < len(points) - 1:
            return False
        else:
            return True
    #if there's only open space among the checked points, display it.
    elif walls == 0:
        return True
    #If the last point is blocking and it's a wall, display it:
    elif map_dict[points[-1]].blocking == True and walls == 1:
        return True
    else:
        return False

async def handle_magic_door(point=(0, 0), last_point=(5, 5)):
    difference_from_last = last_point[0] - point[0], last_point[1] - point[1]
    destination = map_dict[point].magic_destination
    if difference_from_last is not (0, 0):
        coord_through_door = (destination[0] + difference_from_last[0], 
                              destination[1] + difference_from_last[1])
        door_points = get_line(destination, coord_through_door)
        if len(door_points) >= 2:
            line_of_sight_result = await check_line_of_sight(door_points[1], coord_through_door)
        else:
            line_of_sight_result = True
        if line_of_sight_result != False and line_of_sight_result != None:
            return coord_through_door
        else:
            return line_of_sight_result

#TODO: add view distance limiting based on light level of current cell.
#      an enemy that carves a path through explored map tiles and causes it to be forgotten.
#      [ ]the tile displayed by gradient_tile_pairs is modified by the light level of the tile
#      [ ]actors have a chance to not display based on the light level of the tile they are sitting on.
#      [ ]actors which stay in darkness until lit up or a condition is met and then they change behavior
#             seek or flee
#      [X]implement flee behavior
#      [ ]an enemy that switches between:
                #[X]flee behavior, 
                #[X]seeking behavior
                #[ ]a random orbit at random distance (at random radial speed)
                #[ ]path of orbit changes when direction is in cone of view,
                #[X]tries to escape when visible, seeks quickly when not visible
                #[ ]when clear line of sight of player and not within ijkl cone of vision
                #seek player, else, stand still.
#an enemy that can push the player
#an enemy that cannot be killed
#an enemy that doesn't do any damage but cannot be pushed, passed through or seen through
#a stamina bar?? (souls-like?)
#a between move timeout clock (decremented n times a second, must wait to move again.
#    if move is received during timeout, clock does not change, player does not move.

async def view_tile(x_offset=1, y_offset=1, threshold=12, fov=120):
    """ handles displaying data from map_dict """
    #distance from offsets to center of field of view
    distance = sqrt(abs(x_offset)**2 + abs(y_offset)**2) 
    await asyncio.sleep(random()/5 * distance) #stagger starting_time
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    previous_tile = None
    print_location = (middle_x + x_offset, middle_y + y_offset)
    last_print_choice = ' '
    angle_from_twelve = find_angle(p0=(0, 5), p2=(x_offset, y_offset))
    if x_offset <= 0:
        angle_from_twelve = 360 - angle_from_twelve
    display = False
    while True:
        await asyncio.sleep(distance * .015) #update speed
        #await asyncio.sleep(.1) #update speed
        player_coords = actor_dict['player'].coords()
        x_display_coord, y_display_coord = add_coords(player_coords, (x_offset, y_offset))
        #check whether the current tile is within the current field of view
        current_angle = state_dict['current_angle']
        l_angle, r_angle = ((current_angle - fov // 2) % 360, 
                            (current_angle + fov // 2) % 360)
        display = in_angle_bracket(angle_from_twelve, arc_begin=l_angle, arc_end=r_angle)
        if map_dict[x_display_coord, y_display_coord].override_view:
            display = True
        if (x_offset, y_offset) == (0, 0):
            print_choice=term.color(6)('@')
        elif display:
            #add a line in here for different levels/dimensions:
            tile_coord_key = (x_display_coord, y_display_coord)
            random_distance = abs(gauss(distance, 1))
            if random_distance < threshold: 
                line_of_sight_result = await check_line_of_sight(player_coords, tile_coord_key)
                if type(line_of_sight_result) is tuple:
                    print_choice = await check_contents_of_tile(line_of_sight_result) #
                elif line_of_sight_result == True:
                    await trigger_announcement(tile_coord_key, player_coords=player_coords)
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
        elif not display and map_dict[x_display_coord, y_display_coord].seen:
            if state_dict['plane'] == 'nightmare':
                color_choice = 0
            else:
                color_choice = 7
            remembered_tile = map_dict[x_display_coord, y_display_coord].tile
            print_choice = term.on_color(0)(term.color(color_choice)(remembered_tile))
            #if random() < .95:
                #TODO: add an attribute to map_tile (perhaps stored in seen) for
                #      the last thing that was seen at this space
                #remembered_tile = map_dict[x_display_coord, y_display_coord].tile
                #print_choice = term.on_color(0)(term.color(color_choice)(remembered_tile))
            #else:
                #print_choice = ' '
        else:
            #catches tiles that are not within current FOV
            print_choice = ' '
        with term.location(*print_location):
            # only print something if it has changed:
            if last_print_choice != print_choice:
                if print_choice == "░":
                    print_choice = find_brightness_tile(distance=distance)
                print(print_choice)
                last_print_choice = print_choice

def find_brightness_tile(distance=0, std_dev=.5):
    """
    returns the appropriate light-level shifted tile based on distance.
    """
    gradient_tile_pairs = ((0, ' '),        #dark
                           (7, "░"),
                           (8, "░"), 
                           (7, "▒"),
                           (8, "▒"), 
                           (7, "▓"), 
                           (7, "█"), 
                          *((8, "▓"),) * 2,
                          *((8, "█"),) * 6) #bright

    bw_gradient = tuple([term.color(pair[0])(pair[1]) for pair in gradient_tile_pairs])
    bright_to_dark = {num:val for num, val in enumerate(reversed(bw_gradient))}

    brightness_index = distance #+ gauss(1, std_dev) 
    if brightness_index <= 0:
        brightness_index = 0
    elif brightness_index >= 15:
        brightness_index = 14
    print_choice = bright_to_dark[int(brightness_index)]
    return print_choice

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

async def ui_box_draw(position="top left", 
                      box_height=1, box_width=9, 
                      x_margin=30, y_margin=4,
                      one_time=False):
    """
    draws a box for UI elements
    <--width-->
    +---------+ ^
    |         | | height = 1
    +---------+ v
    """
    await asyncio.sleep(0)
    top_bar = "┌{}┐".format("─" * box_width)
    bottom_bar = "└{}┘".format("─" * box_width)
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
        if one_time:
            break

async def status_bar_draw(state_dict_key="health", position="top left", bar_height=1, bar_width=10,
                          x_margin=5, y_margin=4):
    asyncio.ensure_future(ui_box_draw(position=position, bar_height=box_height, bar_width=box_width,
                          x_margin=x_margin, y_margin=y_margin))

async def random_angle(centered_on_angle=0, total_cone_angle=60):
    rand_shift = round(randint(0, total_cone_angle) - (total_cone_angle / 2))
    return (centered_on_angle + rand_shift) % 360

async def directional_damage_alert(source_angle=None, source_actor=None, source_direction=None,
                                   warning_ui_radius=17, warning_ui_radius_spread=3):
    """
    generates a spray of red tiles beyond the normal sight radius in the
    direction of a damage source.
    """
    if source_actor:
        source_angle = angle_actor_to_actor(actor_a='player', actor_b=source_actor)
    elif source_direction is not None:
        source_directions = {'n':0, 'ne':45, 'e':90, 'se':135,
                             's':180, 'sw':225, 'w':270, 'nw':315}
        if source_direction in source_directions:
            source_angle = source_directions[source_direction]
    elif source_angle is None:
        return
    source_angle = 180 - source_angle
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    warning_ui_points = []
    for _ in range(40):
        radius = warning_ui_radius + randint(0, warning_ui_radius_spread)
        central_point = (middle_x, middle_y)
        angle = await random_angle(centered_on_angle=source_angle)
        point = await point_at_distance_and_angle(radius=radius,
                                                  central_point=central_point,
                                                  angle_from_twelve=angle,)
        warning_ui_points.append(point)
    for tile in [term.red("█"), ' ']:
        shuffle(warning_ui_points)
        for point in warning_ui_points:
            await asyncio.sleep(random()/70)
            with term.location(*point):
                print(tile)

async def timer(x_pos=0, y_pos=10, time_minutes=0, time_seconds=5, resolution=1):
    timer_text = "⌛ " + str(time_minutes).zfill(2) + ":" + str(time_seconds).zfill(2)
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
            await asyncio.sleep(.5)
            x, y = actor_dict['player'].coords()
            with term.location(x_pos, y_pos):
                print(" " * 7)
            break
        timer_text = "⌛ " + str(time_minutes).zfill(2) + ":" + str(time_seconds).zfill(2)
    return

async def view_init(loop, term_x_radius=15, term_y_radius=15, max_view_radius=15):
    await asyncio.sleep(0)
    for x in range(-term_x_radius, term_x_radius + 1):
       for y in range(-term_y_radius, term_y_radius + 1):
           distance = sqrt(x**2 + y**2)
           #cull view_tile instances that are beyond a certain radius
           if distance < max_view_radius:
               loop.create_task(view_tile(x_offset=x, y_offset=y))
    #minimap init:
    asyncio.ensure_future(ui_box_draw(position='centered', x_margin=46, y_margin=-18, 
                                      box_width=21, box_height=21))
    for x in range(-20, 21, 2):
        for y in range(-20, 21, 2):
            half_scale = x // 2, y // 2
            loop.create_task(minimap_tile(player_position_offset=(x, y),
                                          display_coord=(add_coords((126, 12), half_scale))))

async def async_map_init():
    """
    a map function that makes two different features, one with a normal small
    number coordinate and the other with an unreachably large number.
    
    a map that generates as the player gets close to its existing nodes

    when a node is approached, spawn a new chunk while still out of sight

    The player can teleport between the two areas with an item and they are set
    up 1 to 1 with one another with differences between the two areas.

    One is barren except for a few very scary monsters? 
    """
    #scary nightmare land
    loop = asyncio.get_event_loop()
    loop.create_task(draw_circle(center_coord=(1000, 1000), radius=50, animation=Animation(preset='noise')))
    #a small dark room
    loop.create_task(draw_circle(center_coord=(500, 500), radius=15, animation=Animation(preset='blank')))
    for _ in range(10):
        x, y = randint(-18, 18), randint(-18, 18)
        loop.create_task(tentacled_mass(start_coord=(1000 + x, 1000 + y)))
    loop.create_task(create_magic_door_pair(door_a_coords=(-8, -8), door_b_coords=(1005, 1005),
                                            destination_plane='nightmare'))
    loop.create_task(spawn_container(spawn_coord=(3, -2)))
    loop.create_task(spawn_container(spawn_coord=(3, -3)))
    loop.create_task(spawn_container(spawn_coord=(3, -4)))
    spawn_item_at_coords(coord=(-3, -0), instance_of='wand', on_actor_id=False)
    spawn_item_at_coords(coord=(-3, -3), instance_of='red key', on_actor_id=False)
    spawn_item_at_coords(coord=(-2, -2), instance_of='green key', on_actor_id=False)
    spawn_static_actor(spawn_coord=(5, 5), moveable=True)
    spawn_static_actor(spawn_coord=(6, 6), moveable=True)
    loop.create_task(trap_init())

async def trap_init():
    loop = asyncio.get_event_loop()
    node_offsets = ((-6, 's'), (6, 'n'))
    nodes = [(i, *offset) for i in range(-5, 5) for offset in node_offsets]
    base_coord = (35, 20)
    rand_coords = {(randint(-5, 5) + base_coord[0], 
                    randint(-5, 5) + base_coord[1]) for _ in range(20)}
    state_dict['switch_1'] = {}
    for coord in rand_coords:
       loop.create_task(pressure_plate(spawn_coord=coord, patch_to_key='switch_1'))
    loop.create_task(multi_spike_trap(nodes=nodes, base_coord=(35, 20), patch_to_key='switch_1'))
    state_dict['switch_2'] = {}
    loop.create_task(pressure_plate(spawn_coord=(19, 19), patch_to_key='switch_2'))
    loop.create_task(pressure_plate(spawn_coord=(20, 20), patch_to_key='switch_2'))
    loop.create_task(pressure_plate(spawn_coord=(21, 21), patch_to_key='switch_2'))
    state_dict['switch_3'] = {}
    loop.create_task(pressure_plate(spawn_coord=(54, 19), patch_to_key='switch_3'))
    loop.create_task(spawn_turret())
    loop.create_task(trigger_door(door_coord=(25, 20), patch_to_key='switch_2'))
    loop.create_task(state_toggle(trigger_key='test'))
    loop.create_task(puzzle_pair(puzzle_name='brown'))
    loop.create_task(puzzle_pair(puzzle_name='cyan', block_coord=(-10, -7), plate_coord=(-7, -7), color_num=6))

#TODO: create a map editor mode, accessible with a keystroke??

async def pass_between(x_offset, y_offset, plane_name='nightmare'):
    """
    shift from default area to alternate area and vice versa.
    """
    await asyncio.sleep(0)
    player_x, player_y = actor_dict['player'].coords()
    if state_dict['plane'] == 'normal':
        destination, plane = (player_x + x_offset, player_y + y_offset), plane_name
    elif state_dict['plane'] == plane_name:
        destination, plane = (player_x - x_offset, player_y - y_offset), 'normal'
    else:
        return False
    if map_dict[destination].passable:
        map_dict[player_x, player_y].passable = True
        actor_dict['player'].update(*destination)
        state_dict['plane'] = plane
        with term.location(0, 0):
            print('plane: {}, known location: {}'.format(plane, state_dict['known location']))
        if plane != 'normal':
            state_dict['known location'] = False
        else:
            state_dict['known location'] = True
    else:
        asyncio.ensure_future(filter_print(output_text="Something is in the way."))

async def printing_testing(distance=0, x_coord=90, y_coord=1):
    await asyncio.sleep(0)

    bw_gradient = ((" "),                #0
                   term.color(7)("░"),   #1
                   term.color(8)("░"),   #3
                   term.color(7)("▒"),   #5
                   term.color(8)("▒"),   #7
                   term.color(7)("▓"),   #9
                   term.color(7)("█"),   #10
                   term.color(8)("▓"),   #11
                   term.color(8)("▓"),   #11
                   term.color(8)("▓"),   #11
                   term.color(8)("▓"),   #11
                   term.color(8)("█"),   #12
                   term.color(8)("█"),   #13
                   term.color(8)("█"),   #14
                   term.color(8)("█"),   #15
                   )
    bright_to_dark = bw_gradient[::-1]
    for number, tile in enumerate(bw_gradient):
        with term.location(number + x_coord, y_coord):
            print(term.bold(str(number)))
    for number, tile in enumerate(reversed(bw_gradient)):
        with term.location(number + x_coord, 1 + y_coord):
            print(tile)
    for number in range(10):
        with term.location(number + x_coord, 2 + y_coord):
            print(term.color(number)(str(number)))
        with term.location(number + x_coord, 3 + y_coord):
            print(term.on_color(number)(str(number)))
    if distance <= len(bright_to_dark) -1: return bright_to_dark[int(distance)]
    else:
        return " "

async def status_bar(actor_name='player', attribute='health', x_offset=0, y_offset=0, centered=True, 
                     bar_length=20, title=None, refresh_time=.1,
                     max_value=100, bar_color=1):
    if centered:
        middle_x, middle_y = (int(term.width / 2), int(term.height / 2))
        x_print_coord = int(bar_length / 2)
        y_print_coord = y_offset
        print_coord = (middle_x - x_print_coord, middle_y + y_print_coord)
    while True:
        attr_value = getattr(actor_dict[actor_name], attribute)
        bar_filled = round((int(attr_value)/max_value) * bar_length)
        bar_unfilled = bar_length - bar_filled
        bar_characters = "█" * bar_filled + "░" * bar_unfilled
        await asyncio.sleep(refresh_time)
        with term.location(*print_coord):
            print("{}{}".format(title, term.color(bar_color)(bar_characters)))

async def player_coord_readout(x_offset=0, y_offset=0, refresh_time=.1, centered=True):
    if centered:
        middle_x, middle_y = (int(term.width / 2), int(term.height / 2))
        print_coord = (middle_x - x_offset, middle_y + y_offset)
    while True:
        await asyncio.sleep(refresh_time)
        player_coords = actor_dict['player'].coords()
        if state_dict['plane'] == 'normal':
            printed_coords = player_coords
        else:
            #TODO: create more convincing noise
            noise = "1234567890ABCDEF       ░░░░░░░░░░░ " 
            printed_coords = ''.join([choice(noise) for _ in range(7)])
        with term.location(*add_coords(print_coord, (0, 1))):
            print("❌ {}      ".format(printed_coords))

async def stamina_regen():
    while True:
        await asyncio.sleep(.1)
        if actor_dict['player'].stamina < 100:
            actor_dict['player'].stamina += 1

async def ui_setup():
    """
    lays out UI elements to the screen at the start of the program.
    """
    await asyncio.sleep(0)
    loop = asyncio.get_event_loop()
    loop.create_task(key_slot_checker(slot='q', print_location=(46, 5)))
    loop.create_task(key_slot_checker(slot='e', print_location=(52, 5)))
    loop.create_task(console_box())
    loop.create_task(display_items_at_coord())
    loop.create_task(display_items_on_actor())
    health_title = "{} ".format(term.color(1)("♥"))
    stamina_title = "{} ".format(term.color(3)("⚡"))
    loop.create_task(status_bar(y_offset=16, actor_name='player', attribute='health', title=health_title, bar_color=1))
    loop.create_task(status_bar(y_offset=17, actor_name='player', attribute='stamina', title=stamina_title, bar_color=3))
    loop.create_task(stamina_regen())
    loop.create_task(player_coord_readout(x_offset=10, y_offset=18))
    loop.create_task(angle_swing())
    loop.create_task(crosshairs())

async def shimmer_text(output_text=None, screen_coord=(0, 1), speed=.1):
    """
    an attempt at creating fake whole-screen noise
    """
    x_size, y_size = (term.width - 2, term.height - 2)
    rand_coords = []
    old_coords = []
    noise = '      ▒▓▒ ▒▓▒' 
    while True:
        if output_text is None:
            output_text = "the quick brown fox jumps over the lazy dog"
        rand_color = [term.color(choice((7, 8)))(char) for char in output_text]
        shimmer_text = ''.join(rand_color)
        with term.location(*screen_coord):
            print(shimmer_text)
        await asyncio.sleep(speed)

#Actor behavior functions-------------------------------------------------------
async def wander(name_key=None, **kwargs):
    """ 
    randomly increments or decrements x_current and y_current
    if square to be moved to is passable
    """
    x_current, y_current = actor_dict[name_key].coords()
    x_move, y_move = randint(-1, 1), randint(-1, 1)
    next_position = add_coords((x_current, y_current), (x_move, y_move))
    if map_dict[next_position].passable:
        return next_position
    else:
        return x_current, y_current

async def attack(attacker_key=None, defender_key=None, blood=True, spatter_num=9):
    await asyncio.sleep(0)
    attacker_strength = actor_dict[attacker_key].strength
    target_x, target_y = actor_dict[defender_key].coords()
    if blood:
        await sow_texture(root_x=target_x, root_y=target_y, radius=3, paint=True,
                          seeds=randint(1, spatter_num), description="blood.")
    actor_dict[defender_key].health -= attacker_strength
    if actor_dict[defender_key].health <= 0:
        actor_dict[defender_key].health = 0
    asyncio.ensure_future(directional_damage_alert(source_actor=attacker_key))

async def seek_actor(name_key=None, seek_key='player', repel=False):
    """ Standardize format to pass movement function.  """
    if not repel:
        polarity = 1
    else:
        polarity = -1
    x_current, y_current = actor_dict[name_key].coords()
    target_x, target_y = actor_dict[seek_key].coords()
    next_x, next_y = x_current, y_current
    diff_x, diff_y = (x_current - target_x), (y_current - target_y)
    is_hurtful = actor_dict[name_key].hurtful
    player_x, player_y = actor_dict["player"].coords()
    player_x_diff, player_y_diff = (x_current - player_x), (y_current - player_y)
    if is_hurtful and abs(player_x_diff) <= 1 and abs(player_y_diff) <= 1:
        await attack(attacker_key=name_key, defender_key="player")
    if diff_x > 0:
        next_x = x_current + (polarity * -1)
    elif diff_x < 0:
        next_x = x_current + (polarity * 1)
    if diff_y > 0: 
        next_y = y_current + (polarity * -1)
    elif diff_y < 0:
        next_y = y_current + (polarity * 1)
    coord_tuple = next_x, next_y
    if map_dict[coord_tuple].passable and len(map_dict[coord_tuple].actors) == 0:
        return (next_x, next_y)
    else:
        return (x_current, y_current)

async def wait(name_key=None, **kwargs):
    """
    Takes no action. Stays in place.
    """
    actor_location = actor_dict[name_key].coords()
    return actor_location

async def waver(name_key=None, seek_key='player', **kwargs):
    """
    Seeks player if out of sight, flees if within fov of player
    """
    actor_location = actor_dict[name_key].coords()
    within_fov = check_point_within_arc(checked_point=actor_location, arc_width=120)
    distance_to_player = distance_to_actor(actor_a=name_key, actor_b='player')
    #TODO: flee only within certain distance of the player, chance to wait
    #      increases towards margin of FOV cone/distance from player
    if distance_to_player >= 15:
        movement_choice = await wander(name_key=name_key)
    elif within_fov and distance_to_player < 10:
        movement_choice = await seek_actor(name_key=name_key, seek_key=seek_key, repel=True)
    else:
        movement_choice = await seek_actor(name_key=name_key, seek_key=seek_key, repel=False)
    #fuzzy_forget(name_key=name_key) #for use in a different context
    return movement_choice

async def angel_seek(name_key=None, seek_key='player'):
    """
    Seeks only when the player isn't looking.
    """
    actor_location = actor_dict[name_key].coords()
    within_fov = check_point_within_arc(checked_point=actor_location, arc_width=120)
    if within_fov:
        movement_choice = actor_location
    else:
        movement_choice = await seek_actor(name_key=name_key, seek_key=seek_key, repel=False)
    return movement_choice

#TODO: implement an invisible attribute for actors
def fuzzy_forget(name_key=None, radius=3, forget_count=5):
    actor_location = actor_dict[name_key].coords()
    for _ in range(forget_count):
        rand_point = point_within_radius(radius=radius, center=actor_location)
        map_dict[rand_point].seen = False

#TODO: an invisible actor that can still be damaged.

async def damage_door():
    """ allows actors to break down doors"""
    pass

#misc utility functions---------------------------------------------------------
def add_coords(coord_a=(0, 0), coord_b=(10, 10)):
    output = (coord_a[0] + coord_b[0],
              coord_a[1] + coord_b[1])
    return output

def generate_id(base_name="name"):
    return "{}_{}".format(base_name, str(datetime.time(datetime.now())))

async def facing_dir_to_num(direction="n"):
    dir_to_num = {'n':2, 'e':1, 's':0, 'w':3}
    return dir_to_num[direction]

async def run_every_n(sec_interval=3, repeating_function=None, kwargs={}):
    while True:
        await asyncio.sleep(sec_interval)
        x, y = actor_dict['player'].coords()
        asyncio.ensure_future(repeating_function(**kwargs))

async def track_actor_location(state_dict_key="player", actor_dict_key="player", update_speed=.1, length=10):
    await asyncio.sleep(0)
    actor_coords = None
    while True:
        await asyncio.sleep(update_speed)
        actor_coords = actor_dict[actor_dict_key].coords()
        state_dict[state_dict_key] = actor_coords

#Actor creation and controllers----------------------------------------------
async def tentacled_mass(start_coord=(-5, -5), speed=1, tentacle_length_range=(3, 8),
                         tentacle_rate=.1, tentacle_colors="456"):
    """
    creates a (currently) stationary mass of random length and color tentacles
    move away while distance is far, move slowly towards when distance is near, radius = 20?
    """
    await asyncio.sleep(0)
    tentacled_mass_id = generate_id(base_name='tentacled_mass')
    actor_dict[tentacled_mass_id] = Actor(name=tentacled_mass_id, moveable=False, tile='*',
                                          is_animated=True, animation=Animation(preset='mouth'))
    actor_dict[tentacled_mass_id].update(*start_coord)
    current_coord = start_coord
    while True:
        await asyncio.sleep(tentacle_rate)
        current_coord = await choose_core_move(core_name_key=tentacled_mass_id,
                                               tentacles=False)
        if current_coord:
            actor_dict[tentacled_mass_id].update(*current_coord)
        tentacle_color = int(choice(tentacle_colors))
        asyncio.ensure_future(vine_grow(start_x=current_coord[0], 
                start_y=current_coord[1], actor_key="tentacle", 
                rate=random(), vine_length=randint(*tentacle_length_range), rounded=True,
                behavior="retract", speed=.01, damage=10, color_num=tentacle_color,
                extend_wait=.025, retract_wait=.25 ))
        actor_dict[tentacled_mass_id].update(*current_coord)
    
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
    actor_dict[core_name_key] = Actor(name=core_name_key, moveable=False, tile=' ')
    actor_dict[core_name_key].update(*core_location)
    shroud_locations = [(start_x, start_y)] * shroud_pieces
    #initialize segment actors:
    shroud_piece_names = []
    for number, shroud_coord in enumerate(shroud_locations):
        shroud_piece_names.append("{}_piece_{}".format(core_name_key, number))
    for number, name in enumerate(shroud_piece_names):
        actor_dict[name] = Actor(name=name, moveable=False, x_coord=start_x, y_coord=start_y, tile=' ')
    wait = 0
    while True:
        await asyncio.sleep(speed)
        for offset, shroud_name_key in enumerate(shroud_piece_names):
            #deleting instance of the shroud pieces from the map_dict's actor list:
            new_coord = await choose_shroud_move(shroud_name_key=shroud_name_key,
                                                 core_name_key=core_name_key)
            if new_coord:
                actor_dict[shroud_name_key].update(*new_coord)
        core_location = actor_dict[core_name_key].coords()
        if wait > 0:
            wait -= 1
            pass 
        else:
            new_core_location = await choose_core_move(core_name_key=core_name_key)
        if new_core_location:
            actor_dict[core_name_key].update(*new_core_location)

async def choose_core_move(core_name_key='', tentacles=True):
    """
    breaks out random movement of core into separate function
    """
    core_behavior_val = random()
    core_location = actor_dict[core_name_key].coords()
    if core_behavior_val < .05 and tentacles:
        new_core_location = actor_dict[core_name_key].coords()
        asyncio.ensure_future(vine_grow(start_x=core_location[0], start_y=core_location[1])),
        wait = 20
    elif core_behavior_val > .4:
        new_core_location = await wander(name_key=core_name_key)
    else:
        new_core_location = await seek_actor(name_key=core_name_key, seek_key="player")
    return new_core_location

async def choose_shroud_move(shroud_name_key='', core_name_key=''):
    """
    breaks out random movement of core into separate function
    """
    await asyncio.sleep(0)
    coord = actor_dict[shroud_name_key].coords()
    behavior_val = random()
    if behavior_val < .2:
        new_shroud_location = coord
    elif behavior_val > .6:
        new_shroud_location = await wander(name_key=shroud_name_key)
    else:
        new_shroud_location = await seek_actor(name_key=shroud_name_key, seek_key=core_name_key)
    return new_shroud_location

async def basic_actor(start_x=0, start_y=0, speed=1, tile="*", 
        movement_function=wander, name_key="test", hurtful=False,
        strength=5, is_animated=False, animation=" ", holding_items=[],
        movement_function_kwargs={}):
    """
    actors can:
    move from square to square using a movement function
    hold items
    attack or interact with the player
    die
    exist for a set number of turns
    """
    await asyncio.sleep(0)
    actor_dict[(name_key)] = Actor(name=name_key, x_coord=start_x, y_coord=start_y, 
                                   speed=speed, tile=tile, hurtful=hurtful, 
                                   leaves_body=True, strength=strength, 
                                   is_animated=is_animated, animation=animation,
                                   holding_items=holding_items)
    coords = actor_dict[name_key].coords()
    while True:
        if actor_dict[name_key].health <= 0:
            await kill_actor(name_key=name_key)
            return
        await asyncio.sleep(speed)
        next_coords = await movement_function(name_key=name_key, **movement_function_kwargs)
        current_coords = actor_dict[name_key].coords() #checked again here because actors can be pushed around
        if current_coords != next_coords:
            if name_key in map_dict[current_coords].actors:
                del map_dict[current_coords].actors[name_key]
            map_dict[next_coords].actors[name_key] = True
            actor_dict[name_key].update(*next_coords)

def distance_to_actor(actor_a=None, actor_b='player'):
    if actor_a is None:
        return 0
    a_coord = actor_dict[actor_a].coords()
    b_coord = actor_dict[actor_b].coords()
    return point_to_point_distance(point_a=a_coord, point_b=b_coord)

async def actor_turret(track_to_actor=None, fire_rate=.0, reach=15):
    if track_to_actor == None:
        return
    while True:
        await asyncio.sleep(fire_rate)
        actor_health = actor_dict[track_to_actor].health
        if actor_health <= 0:
            break
        distance_to_player = distance_to_actor(actor_a=track_to_actor, actor_b='player')
        if distance_to_player <= reach:
            firing_angle = angle_actor_to_actor(actor_a=track_to_actor, actor_b='player') - 90
            asyncio.ensure_future(fire_projectile(actor_key=track_to_actor, 
                                                  firing_angle=firing_angle,
                                                  degree_spread=(-5, 5),
                                                  animation_preset='bullet'))
        
async def kill_actor(name_key=None, leaves_body=True, blood=True):
    coords = actor_dict[name_key].coords()
    holding_items = actor_dict[name_key].holding_items
    if leaves_body:
        body_tile = term.red(actor_dict[name_key].tile)
    if actor_dict[name_key].multi_tile_parent is not None:
        parent_name = actor_dict[name_key].multi_tile_parent
        actor_index = mte_dict[parent_name].member_names.index(name_key)
        del mte_dict[parent_name].member_names[actor_index]
    del actor_dict[name_key]
    del map_dict[coords].actors[name_key]
    if blood:
        await sow_texture(root_x=coords[0], root_y=coords[1], radius=3, paint=True, 
                          seeds=5, description="blood.")
    if leaves_body:
        map_dict[coords].tile = body_tile
        map_dict[coords].description = "A body."
    spawn_item_spray(base_coord=coords, items=holding_items)
    return

def spawn_item_spray(base_coord=(0, 0), items=[], random=False, radius=2):
    if items is None:
        return
    loop = asyncio.get_event_loop()
    coord_choices = get_circle(center=base_coord, radius=radius)
    for item in items:
        item_coord = choice(coord_choices)
        spawn_item_at_coords(coord=item_coord, instance_of=item)

async def vine_grow(start_x=0, start_y=0, actor_key="vine", 
                    rate=.1, vine_length=20, rounded=True,
                    behavior="retract", speed=.01, damage=0,
                    extend_wait=.025, retract_wait=.25,
                    color_num=2, on_actor=None, start_facing=False):
    """grows a vine starting at coordinates (start_x, start_y). Doesn't know about anything else.
    TODO: make vines stay within walls (a toggle between clipping and tunneling)
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
    vine_id = generate_id(base_name='')
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
        actor_dict[vine_name] = Actor(name=vine_name, x_coord=current_coord[0],
                                      y_coord=current_coord[1],
                                      tile=term.color(color_num)(vine_tile),
                                      moveable=False)
        #current_coord = (current_coord[0] + next_tuple[0], current_coord[1] + next_tuple[1])
        current_coord = add_coords(current_coord, next_tuple)
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
        if damage:
            await damage_all_actors_at_coord(coord=coord, damage=damage)
    if behavior == "retract":
        end_loop = reversed(vine_actor_names)
        end_wait = retract_wait
    if behavior == "bolt":
        end_loop, end_wait = vine_actor_names, extend_wait
    for vine_name in end_loop:
        coord = actor_dict[vine_name].coord
        await asyncio.sleep(end_wait)
        del map_dict[coord].actors[vine_name]
        del actor_dict[vine_name]

async def health_potion(item_id=None, actor_key='player', total_restored=25, 
                        duration=2, sub_second_step=.1):
    await asyncio.sleep(0)
    if item_id:
        del item_dict[item_id]
        del actor_dict['player'].holding_items[item_id]
    num_steps = duration / sub_second_step
    health_per_step = total_restored / num_steps
    asyncio.ensure_future(damage_numbers(actor='player', damage=-total_restored))
    for i in range(int(num_steps)):
        with term.location(80, 0):
            print(i)
        await asyncio.sleep(sub_second_step)
        if (actor_dict[actor_key].health + health_per_step >= actor_dict[actor_key].max_health):
            actor_dict[actor_key].health = actor_dict[actor_key].max_health
        else:
            actor_dict[actor_key].health += health_per_step

async def spawn_bubble(centered_on_actor='player', radius=6, duration=10):
    """
    spawns a circle of animated timed actors that are impassable
    rand_delay in timed_actor is for a fade-in/fade-out effect.
    """
    if state_dict['bubble_cooldown']:
        await filter_print(output_text="Nothing happens.")
        return False
    coords = actor_dict[centered_on_actor].coords()
    await asyncio.sleep(0)
    bubble_id = generate_id(base_name='')
    bubble_pieces = {}
    player_coords = actor_dict['player'].coords()
    every_five = [i * 5 for i in range(72)]
    points_at_distance = {await point_at_distance_and_angle(radius=radius, central_point=player_coords, angle_from_twelve=angle) for angle in every_five}
    state_dict['bubble_cooldown'] = True
    for num, point in enumerate(points_at_distance):
        actor_name = 'bubble_{}_{}'.format(bubble_id, num)
        asyncio.ensure_future(timed_actor(name=actor_name, coords=(point), 
                              rand_delay=.3, death_clock=duration))
    await asyncio.sleep(duration)
    state_dict['bubble_cooldown'] = False
    return True

async def points_at_distance(radius=5, central_point=(0, 0)):
    every_five = [i * 5 for i in range(72)]
    points = []
    for angle in every_five:
        point = await point_at_distance_and_angle(radius=radius, 
                                                  central_point=player_coords, 
                                                  angle_from_twelve=angle)
        points.append(point)
    return set(points)

async def timed_actor(death_clock=10, name='timed_actor', coords=(0, 0),
                      rand_delay=0, solid=True, moveable=False, 
                      animation_preset='shimmer'):
    """
    spawns an actor at given coords that disappears after a number of turns.
    """
    if name == 'timed_actor':
        name = name + generate_id(base_name='')
    if rand_delay:
        await asyncio.sleep(random() * rand_delay)
    actor_dict[name] = Actor(name=name, moveable=moveable, x_coord=coords[0], y_coord=coords[1], 
                             tile=str(death_clock), is_animated=True,
                             animation=Animation(preset=animation_preset))
    map_dict[coords].actors[name] = True
    prev_passable_state = map_dict[coords].passable
    if solid:
        map_dict[coords].passable = False
    while death_clock >= 1:
        await asyncio.sleep(1)
        death_clock -= 1
    #because the block may have moved, update coordinates.
    coords = actor_dict[name].coords() 
    del map_dict[coords].actors[name]
    del actor_dict[name]
    map_dict[coords].passable = prev_passable_state

async def spawn_turret(spawn_coord=(54, 16), firing_angle=180, trigger_key='switch_3', 
                       facing='e', spread=20, damage=10, radius=12, rate=.02):
    firing_angle = (firing_angle - 90) % 360
    turret_id = generate_id(base_name='turret')
    closed_tile = term.on_color(7)(term.color(0)('◫'))
    open_tile = term.on_color(7)(term.color(0)('◼'))
    actor_dict[turret_id] = Actor(name=turret_id, moveable=False,
                                       tile=closed_tile)
    actor_dict[turret_id].update(*spawn_coord)
    map_dict[spawn_coord].actors[turret_id] = True
    while True:
        await asyncio.sleep(rate)
        if await any_true(trigger_key=trigger_key):
            asyncio.ensure_future(fire_projectile(actor_key=turret_id, 
                                                  firing_angle=firing_angle,
                                                  radius_spread=(5, 8)))
            actor_dict[turret_id].tile = open_tile
        else:
            actor_dict[turret_id].tile = closed_tile


async def beam_spire(spawn_coord=(0, 0)):
    """
    spawns a rotating flame source
    """
    turret_id = generate_id(base_name='turret')
    closed_tile = term.on_color(7)(term.color(0)('◫'))
    open_tile = term.on_color(7)(term.color(0)('◼'))
    actor_dict[turret_id] = Actor(name=turret_id, moveable=False,
                                       tile=closed_tile)
    actor_dict[turret_id].update(*spawn_coord)
    while True:
        for angle in [i * 5 for i in range(72)]:
            for i in range(10):
                asyncio.ensure_future(fire_projectile(actor_key=turret_id,
                                                      firing_angle=angle))
            await asyncio.sleep(.05)

async def fire_projectile(actor_key='player', firing_angle=45, radius=10, 
                          radius_spread=(10, 14), degree_spread=(-20, 20),
                          damage=5, animation_preset='explosion'):
    rand_radius = randint(*radius_spread) + radius
    rand_angle = randint(*degree_spread) + firing_angle
    actor_coords = actor_dict[actor_key].coords()
    x_shift, y_shift = point_given_angle_and_radius(angle=rand_angle,
                                                    radius=rand_radius)
    end_coords = add_coords(actor_coords, (x_shift, y_shift))
    actor_coords = actor_dict[actor_key].coords()
    start_coords = actor_coords
    await travel_along_line(name='particle', start_coord=start_coords, 
                            end_coords=end_coords, damage=damage, 
                            animation=Animation(preset=animation_preset), 
                            ignore_head=True, source_actor=actor_key)

def point_given_angle_and_radius(angle=0, radius=10):
    x = round(cos(radians(angle)) * radius)
    y = round(sin(radians(angle)) * radius)
    return x, y

def angle_actor_to_actor(actor_a='player', actor_b=None):
    """
    returns degrees as measured clockwise from 12 o'clock
    with actor_a at the center of the clock and actor_b along 
    the circumference.

    12
    |  B (3, 3)
    | /
    |/
    A (0, 0)

    ... would return an angle of 45 degrees.
    """
    if actor_b is None:
        return 0
    else:
        actor_a_coords = actor_dict[actor_a].coords()
        actor_b_coords = actor_dict[actor_b].coords()
        x_run, y_run = (actor_a_coords[0] - actor_b_coords[0],
                        actor_a_coords[1] - actor_b_coords[1])
        hypotenuse = sqrt(x_run ** 2 + y_run ** 2)
        if hypotenuse == 0:
            return 0
        a_angle = degrees(acos(y_run/hypotenuse))
    if x_run > 0:
        a_angle = 360 - a_angle
    return a_angle

async def travel_along_line(name='particle', start_coord=(0, 0), end_coords=(10, 10),
                            speed=.05, tile="X", animation=Animation(preset='explosion'),
                            debris=None, damage=None, ignore_head=False, no_clip=True,
                            source_actor=None):
    asyncio.sleep(0)
    points = get_line(start_coord, end_coords)
    if no_clip:
        for index, point in enumerate(points):
            if not map_dict[point].passable:
                points = points[:index]
                break
        if len(points) < 1:
            return
    particle_id = generate_id(base_name=name)
    if animation:
        is_animated = True
    else:
        is_animated = False
    actor_dict[particle_id] = Actor(name=particle_id, x_coord=start_coord[0], y_coord=start_coord[1], 
                                    tile=tile, moveable=False, is_animated=is_animated,
                                    animation=animation)
    map_dict[start_coord].actors[particle_id] = True
    last_location = points[0]
    if ignore_head:
        points = points[1:]
    for point in points:
        await asyncio.sleep(speed)
        if particle_id in map_dict[last_location].actors:
            del map_dict[last_location].actors[particle_id]
        map_dict[point].actors[particle_id] = True
        actor_dict[particle_id].update(*point)
        if damage is not None:
            await damage_all_actors_at_coord(coord=point, damage=damage, 
                                             source_actor=source_actor)
        last_location = actor_dict[particle_id].coords()
    if debris:
        if random() > .8:
            map_dict[last_location].tile = choice(debris)
            map_dict[last_location].description = "Debris."
    del map_dict[last_location].actors[particle_id]
    del actor_dict[particle_id]

async def radial_fountain(anchor_actor='player', tile_anchor=None, 
                          angle_range=(0, 360), frequency=.1, radius=(3, 30),
                          speed=(1, 7), collapse=True, debris=None, 
                          deathclock=None, animation=Animation(preset='water')):
    """
    creates a number of short lived actors that move towards or away from a
    given actor, depending on collapse.

    speed determines the rate at which particles will travel.

    frequency determines the rate at which new temporary actors are spawned.

    Debris is both palette and switch for whether the tile where the actor ends
    will be changed.

    Deathclock decides how long the fountain lasts.

    angle_range, radius and speed are given in the range that will be passed
    to randint. Speed is divided by 100 so that randint can be used easily.

    angle_range can be defined as a cone (example: (45, 135)) for a cone shaped 
    effect.
    """
    await asyncio.sleep(0)
    while True:
        await asyncio.sleep(frequency)
        rand_angle = randint(*angle_range)
        if tile_anchor:
            origin_coord = tile_anchor
        else:
            origin_coord = actor_dict[anchor_actor].coords()
        reference = (origin_coord[0], origin_coord[1] + 5)
        rand_radius = randint(*radius)
        rand_speed = randint(*speed) / 100
        point = await point_at_distance_and_angle(angle_from_twelve=rand_angle, 
                                                  central_point=origin_coord,
                                                  reference_point=reference, 
                                                  radius=rand_radius)
        if collapse:
            start_coord, end_coords = point, origin_coord
        else:
            start_coord, end_coords = origin_coord, point
        asyncio.ensure_future(travel_along_line(start_coord=start_coord, 
                                                end_coords=end_coords,
                                                debris=debris,
                                                animation=animation))
        if deathclock:
            deathclock -= 1
            if deathclock <= 0:
                break

async def dash_along_direction(actor_key='player', direction='n',
                               distance=10, time_between_steps=.03):
    directions = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
    current_coord = actor_dict[actor_key].coords()
    direction_step = directions[direction]
    destination = (current_coord[0] + direction_step[0] * distance,
                   current_coord[1] + direction_step[1] * distance)
    coord_list = get_line(current_coord, destination)
    await move_through_coords(actor_key=actor_key, coord_list=coord_list,
                            time_between_steps=time_between_steps)

async def move_through_coords(actor_key=None, coord_list=[(i, i) for i in range(10)],
                            drag_through_solid=False, time_between_steps=.1):
    """
    Takes a list of coords and moves the actor along them.
    if apply_offset is True, the path starts at actor's current location.
    drag_through solid toggles whether solid obstacles stop the motion.
    """
    steps = await path_into_steps(coord_list)
    for step in steps:
        actor_coords = actor_dict[actor_key].coords()
        new_position = add_coords(actor_coords, step)
        if map_dict[new_position].passable and not drag_through_solid:
            if not map_dict[actor_coords].passable:
                map_dict[actor_coords].passable = True
            actor_dict[actor_key].update(*new_position)
        else:
            return
        await asyncio.sleep(time_between_steps)

async def path_into_steps(coord_list):
    """
    takes a list of coordinates and returns a series of piecewise steps to 
    shift something along that line. 

    Useful for working with multiple competing movement sources.

    input:((0, 0), (1, 1), (2, 2), (4, 4), (8, 8))
                  |       |       |       |
                  V       V       V       V
        output:((1, 1), (1, 1), (2, 2), (4, 4))

    """
    steps = []
    for index, coord in enumerate(coord_list):
        if index < len(coord_list) - 1:
            next_coord = coord_list[index + 1]
            current_step = (next_coord[0] - coord[0], 
                            next_coord[1] - coord[1])
            steps.append(current_step)
        else:
            return steps

async def orbit(name='particle', radius=5, degrees_per_step=1, on_center=(0, 0), 
                rand_speed=False, track_actor=None, 
                sin_radius=False, sin_radius_amplitude=3):
    """
    generates an actor that orbits about a point
    TODO: particles that follow an arbitrary path
    """
    await asyncio.sleep(0)
    angle = randint(0, 360)
    particle_id = generate_id(base_name=name)
    actor_dict[particle_id] = Actor(name=particle_id, x_coord=on_center[0], y_coord=on_center[1], 
                                    moveable=False, is_animated=True,
                                    animation=Animation(base_tile='◉', preset='shimmer'))
    map_dict[on_center].actors[particle_id] = True
    point_coord = actor_dict[particle_id].coords()
    original_radius = radius
    if sin_radius:
        # a cyclical generator expression for each value in 360.
        sin_cycle = ((sin(radians(i)) * sin_radius_amplitude) + original_radius for i in cycle(range(360)))
    if rand_speed:
        speed_multiplier = 1 + (random()/2 - .25)
    else:
        speed_multiplier = 1
    last_location = None
    while True:
        if sin_radius:
            radius = next(sin_cycle)
        await asyncio.sleep(0.005 * speed_multiplier)
        if track_actor:
            on_center = actor_dict['player'].coords()
        del map_dict[point_coord].actors[particle_id]
        point_coord = await point_at_distance_and_angle(radius=radius, central_point=on_center, angle_from_twelve=angle)
        if point_coord != last_location:
            actor_dict[particle_id].update(*point_coord)
            last_location = actor_dict[particle_id].coords()
        map_dict[last_location].actors[particle_id] = True
        angle = (angle + degrees_per_step) % 360

async def death_check():
    await asyncio.sleep(0)
    player_health = actor_dict["player"].health
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    death_message = "You have died."
    while True:
        await asyncio.sleep(0)
        player_health = actor_dict["player"].health
        if player_health <= 0:
            asyncio.ensure_future(filter_print(pause_stay_on=99, output_text=death_message))
            state_dict['halt_input'] = True
            await asyncio.sleep(3)
            state_dict['killall'] = True

async def environment_check(rate=.1):
    """
    checks actors that share a space with the player and applies status effects
    and/or damage over time for obstacle-type actors such as tentacles from 
    vine_grow().
    """
    await asyncio.sleep(0)
    while actor_dict['player'].health >= 0:
        await asyncio.sleep(rate)
        player_coords = actor_dict['player'].coords()
        with term.location(40, 0):
            print(" " * 10)
        with term.location(40, 0):
            print(len([i for i in map_dict[player_coords].actors.items()]))
#
async def spawn_preset_actor(coords=(0, 0), preset='blob', speed=1, holding_items=[]):
    """
    spawns an entity with various presets based on preset given.
    *** does not need to be set at top level. Can be nested in map and character
    placement.
    """
    asyncio.sleep(0)
    loop = asyncio.get_event_loop()
    actor_id = generate_id(base_name=preset)
    name = "{}_{}".format(preset, actor_id)
    start_coord = coords
    if preset == 'blob':
        item_drops = ['red potion']
        loop.create_task(basic_actor(*coords, speed=.3, movement_function=waver, 
                                     tile='ö', name_key=name, hurtful=True, strength=10,
                                     is_animated=True, animation=Animation(preset="blob"),
                                     holding_items=item_drops))
    if preset == 'angel':
        item_drops = ['dash trinket']
        loop.create_task(basic_actor(*coords, speed=.15, movement_function=angel_seek, 
                                     tile='A', name_key=name, hurtful=True, strength=20,
                                     is_animated=None, holding_items=item_drops))
    if preset == 'test':
        item_drops = ['nut']
        loop.create_task(basic_actor(*coords, speed=.75, movement_function=seek_actor, 
                                     tile='?', name_key=name, hurtful=True, strength=33,
                                     is_animated=True, animation=Animation(preset="mouth"),
                                     holding_items=item_drops))
        loop.create_task(actor_turret(track_to_actor=name, fire_rate=.5, reach=10))

    else:
        pass

async def minimap_tile(display_coord=(0, 0), player_position_offset=(0, 0)):
    """
    displays a miniaturized representation of the seen map using 

    conversion from decimal to binary to block elements:

    01 02 03 04 05 06 07 08 09 10 11 12 13 14 15

    01 10 11 00 01 10 11 00 01 10 11 00 01 10 11
    00 00 00 01 01 01 01 10 10 10 10 11 11 11 11

    .# #. ## .. .# #. ## .. .# #. ## .. .# #. ##
    .. .. .. .# .# .# .# #. #. #. #. ## ## ## ##

    ▝  ▘  ▀  ▗  ▐  ▚  ▜  ▖  ▞  ▌  ▛  ▄  ▟  ▙  █ 
    """
    await asyncio.sleep(random())
    blocks = (' ', '▝', '▘', '▀', '▗', '▐', '▚', '▜', 
              '▖', '▞', '▌', '▛', '▄', '▟', '▙', '█',)
    offsets = ((0, 1), (1, 1), (0, 0), (1, 0))
    listen_coords = [add_coords(offset, player_position_offset) for offset in offsets]
    await asyncio.sleep(random()) #stagger update times
    if player_position_offset == (0, 0):
        blink_switch = cycle((0, 1))
    else:
        blink_switch = repeat(1)
    while True:
        if random() > .9:
            await asyncio.sleep(1)
        else:
            await asyncio.sleep(random())
        player_coord = actor_dict['player'].coords()
        bin_string = ''.join([one_for_passable(add_coords(player_coord, coord)) for coord in listen_coords])
        actor_presence = any(map_dict[add_coords(player_coord, coord)].actors for coord in listen_coords)
        state_index = int(bin_string, 2)
        if state_dict['plane'] == 'nightmare':
            print_char = choice('        ▒▓▒')
        else:
            print_char = blocks[state_index]
        with term.location(*display_coord):
            blink_state = next(blink_switch)
            if (player_position_offset == (0, 0) or actor_presence) and blink_state:
                if state_dict['plane'] != 'nightmare':
                    print(term.on_color(1)(term.green(print_char)))
                else:
                    print(term.on_color(0)(term.green(print_char)))
            else:
                print(term.green(print_char))

def one_for_passable(map_coords=(0, 0)):
    return str(int(map_dict[map_coords].passable))

async def quitter_daemon():
    while True:
        await asyncio.sleep(0.2)
        if state_dict['killall'] == True:
            loop = asyncio.get_event_loop()
            loop.stop()
            loop.close()

def main():
    map_init()
    state_dict["player_health"] = 100
    state_dict["player_stamina"] = 100
    old_settings = termios.tcgetattr(sys.stdin) 
    loop = asyncio.new_event_loop()
    loop.create_task(get_key())
    loop.create_task(view_init(loop))
    loop.create_task(ui_setup()) #UI_SETUP
    loop.create_task(printing_testing())
    loop.create_task(track_actor_location())
    loop.create_task(async_map_init())
    #loop.create_task(shrouded_horror(start_x=-8, start_y=-8))
    item_spawns = []
    loop.create_task(death_check())
    loop.create_task(environment_check())
    loop.create_task(quitter_daemon())
    loop.create_task(fake_stairs())
    #loop.create_task(display_current_tile()) #debug for map generation
    loop.create_task(trigger_on_presence())
    #test enemies
    #for i in range(2):
        #rand_coord = (randint(-5, -5), randint(-5, 5))
        #loop.create_task(spawn_preset_actor(coords=rand_coord, preset='angel'))
    asyncio.set_event_loop(loop)
    result = loop.run_forever()

with term.hidden_cursor():
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        main()
    finally: 
        clear()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings) 
