import asyncio
import re
import os
import sys
import select 
import tty 
import termios
import textwrap
from ast import literal_eval
from numpy import linspace
from blessings import Terminal
from copy import copy
from collections import defaultdict
from datetime import datetime
from itertools import cycle, repeat
from math import acos, cos, degrees, pi, radians, sin, sqrt
from random import randint, choice, gauss, random, shuffle
from subprocess import call
from time import sleep

#Class definitions--------------------------------------------------------------

class Map_tile:
    """ 
    Holds the appearance, contents and state of each tile. 
    """
    def __init__(self, passable=True, tile='𝄛', blocking=True, 
                 description='A rough stone wall.', announcing=False, seen=False,
                 announcement='', distance_trigger=None, is_animated=False,
                 animation='', actors=None, items=None, 
                 magic=False, magic_destination=False, 
                 mutable=True, override_view=False, color_num=8,
                 is_door=False, locked=False, key=''):
        """ 
        Create a new Map_tile, map_dict holds tiles.
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
        self.color_num = color_num
        self.is_door = is_door
        self.locked = locked
        self.key = key #holds what keys fit this tile (if it's a door)

class Actor:
    """ the representation of a single actor that lives on the map. """
    def __init__(self, name='', x_coord=0, y_coord=0, speed=.2, tile="?", 
                 strength=1, health=50, stamina=50, hurtful=True, moveable=True,
                 is_animated=False, animation="", holding_items={}, 
                 leaves_body=False, breakable=False, multi_tile_parent=None, 
                 blocking=False, tile_color=8, description="A featureless gray blob"):
        tile_color_lookup = {'black':0, 'red':1, 'green':2, 'orange':3, 
                             'blue':4, 'purple':5, 'cyan':6, 'grey':7}
        self.name = name
        self.x_coord, self.y_coord, = (x_coord, y_coord)
        self.speed = speed
        self.tile = tile
        if tile_color in tile_color_lookup:
            self.tile_color = tile_color_lookup[tile_color]
        else:
            self.tile_color = tile_color
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
        self.description = description

    def update(self, coord=(0, 0)):
        self.last_location = (self.x_coord, self.y_coord)
        map_dict[self.last_location].passable = True #make previous space passable
        if self.name in map_dict[self.coords()].actors:
            del map_dict[self.coords()].actors[self.name]
        self.x_coord, self.y_coord = coord
        map_dict[self.coords()].actors[self.name] = True

    def coords(self):
        return (self.x_coord, self.y_coord)

    def get_view(self):
        """
        returns the current appearance of the actor.
        With an animation, it returns the next frame.
        With a static tile, it returns the tile along with the color.
        """
        if self.is_animated:
            return next(self.animation)
        else:
            return term.color(self.tile_color)(self.tile)

class Animation:
    def __init__(self, animation=None, base_tile='o', behavior=None, color_choices=None, 
                 preset="none", background=None):
        presets = {'fire':{'animation':'^∧', 
                           'behavior':'random', 
                           'color_choices':'3331'},
                  'water':{'animation':'███████▒▓▒', 
                           'behavior':'walk both',
                           'color_choices':('6' * 10 + '4')},
                  'grass':{'animation':('▒' * 20 + '▓'), 
                           'behavior':'random',
                           'color_choices':('2'),},
                   'blob':{'animation':('ööööÖ'),
                           'behavior':'loop tile',
                           'color_choices':('2')},
                  'mouth':{'animation':('✳✳✳✳✳✸✸'),
                           'behavior':'loop tile',
                           'color_choices':('456')},
                  'noise':{'animation':('      ▒▓▒ ▒▓▒'), 
                           'behavior':'loop tile', 
                           'color_choices':'4'},
                  'chasm':{'animation':(' ' * 10 + '.'), 
                           'behavior':'random', 
                           'color_choices':'0' * 10 + '8'},
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
                 'writhe':{'animation':('╭╮╯╰╭╮╯╰'),
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
        #color behavior------------------------------------
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
        #tile behavior-------------------------------------
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
        #background behavior-------------------------------
        if self.background:
            background_choice = int(choice(self.background))
        else:
            background_choice = 0
        #combined output
        return term.on_color(background_choice)(term.color(color_choice)(tile_choice))

class Rand_repr:
    """
    A class that acts like a string but returns something
    different each time it's printed.
    """
    def __init__(self, *choices):
        self.choices = [str(item) for item in choices]
    def __repr__(self):
        return choice(self.choices)

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
                await append_to_log(message=self.use_message)
            asyncio.ensure_future(self.usable_power(**self.power_kwargs))
            if self.uses is not None:
                self.uses -= 1
            if self.uses <= 0:
                self.broken = True
        else:
            await append_to_log(message="The {}{}".format(self.name, self.broken_text))

class Multi_tile_entity:
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
        figure out whether it will fit in a new orientation

    else:
        push the actor/entity as normal

    Otherwise, each member of a MTE could have a single pointer/label for a higher
    level object that it's part of. 

    Each lower level (child) of the parent MTE only tells the parent that it wants to move the cluster.
    The child sends a proposed location to the parent. The parent can then return True or False
    to whether the new location would be a viable location.

    If we don't want to clip through things, The actual location of the 
    MTE is only updated after checking whether the ground is clear.
    """
 
    def __init__(self, name='mte', anchor_coord=(0, 0), preset='fireball', 
                 blocking=False, fill_color=3, offset=(-1, -1)):
        self.name = name
        #Note: ' ' entries are ignored but keep the shape of the preset
        presets = {'2x2':(('┏', '┓'),
                          ('┗', '┛'),),
                 'empty':((' ')),
              'bold_2x2':(('▛', '▜'),
                          ('▙', '▟'),),
             '2x2_block':(('╔', '╗'),
                          ('╚', '╝'),),
             '3x3_block':(('╔', '╦', '╗'),
                          ('╠', '╬', '╣'),
                          ('╚', '╩', '╝'),),
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
            'test_block':(('X', 'X', 'X', 'X', 'X'),
                          ('X', 'W', 'X', 'W', 'X'),
                          ('X', 'X', 'X', 'X', 'X'),
                          ('X', 'W', 'X', 'W', 'X'),
                          ('X', 'X', 'X', 'X', 'X'),),
              'fireball':((' ', 'E', 'E', ' '),
                          ('E', 'E', 'E', 'E'),
                          ('E', 'E', 'E', 'E'),
                          (' ', 'E', 'E', ' '),),
            '4x4 tester':(('1', '1', ' ', '3'),
                          ('1', ' ', '3', '3'),
                          (' ', '2', ' ', ' '),
                          (' ', '2', ' ', '4'),),
            '5x5 tester':(('1', '1', ' ', '1', ' '),
                          ('1', ' ', '1', '1', ' '),
                          (' ', '1', ' ', ' ', '1'),
                          ('1', ' ', '1', ' ', '1'),
                          (' ', ' ', '1', '1', ' '),),
           'ns_bookcase':(('▛'),
                          ('▌'),
                          ('▌'),
                          ('▙'),),
           'ew_bookcase':(('▛'), ('▀'), ('▀'), ('▜'),),
              'add_sign':((' ', '╻', ' '),
                          ('╺', '╋', '╸'),
                          (' ', '╹', ' '),),}
        self.member_data = {}
        self.member_names = []
        tiles = presets[preset]
        for y in range(len(tiles)):
            for x in range(len(tiles[0])):
                offset_coord = add_coords((x, y), offset)
                write_coord = add_coords(offset_coord, anchor_coord)
                #skip over empty cells to preserve shape of preset:
                if tiles[y][x] is ' ':
                    continue
                else:
                    segment_tile = tiles[y][x]
                segment_name = f'{self.name}_{(x, y)}'
                self.add_segment(segment_tile=segment_tile,
                                 write_coord=write_coord,
                                 offset=(x, y),
                                 segment_name=segment_name,
                                 blocking=blocking,
                                 fill_color=fill_color)

    def add_segment(self, segment_tile='?', write_coord=(0, 0), offset=(0, 0), 
                    segment_name='test', literal_name=True, animation_preset=None,
                    blocking=False, fill_color=8, moveable=True, breakable=True):
        animation_key = {'E':'explosion', 'W':'writhe'}
        self.member_data[offset] = {'tile':segment_tile, 
                                    'write_coord':write_coord,
                                    'offset':offset,
                                    'name':segment_name,
                                    'blocking':blocking}
        if segment_tile in animation_key:
            animation_preset=animation_key[segment_tile]
        else:
            animation_preset=None
        written_tile = term.color(fill_color)(segment_tile)
        member_name = spawn_static_actor(base_name=segment_name, 
                                         tile=written_tile,
                                         spawn_coord=write_coord, 
                                         animation_preset=animation_preset,
                                         multi_tile_parent=self.name,
                                         blocking=blocking,
                                         moveable=moveable,
                                         literal_name=True,
                                         breakable=breakable)
        self.member_names.append(segment_name)
        return segment_name

    def check_collision(self, move_by=(0, 0)):
        """
        Checks whether all of the member actors can fit into a new configuration
        """
        #TODO: allow for an mte to move into a space currently occupied by the player.
        #TODO: allow or disallow multi-pushes that would contact another block
        coord_to_dir = {(0, -1):'n', (1, 0):'e', (0, 1):'s', (-1, 0):'w'}
        check_position = {}
        for member_name in self.member_names:
            if not actor_dict[member_name].moveable:
                with term.location(80, 4):
                    return False
            current_coord = actor_dict[member_name].coords()
            check_coord = add_coords(current_coord, move_by)
            if 'player' in map_dict[check_coord].actors:
                return True
            elif not map_dict[check_coord].passable:
                return False
            for actor in map_dict[check_coord].actors:
                if actor not in self.member_names:
                    return False
        return True

    def move(self, move_by=(3, 3)):
        for member_name in self.member_names:
            current_coord = actor_dict[member_name].coords()
            actor_dict[member_name].update(coord=add_coords(current_coord, move_by))

    def find_connected(self, root_node=None, traveled=None, depth=0, exclusions=set()):
        """
        does a recursive search through the parts of an mte, starting at a given
        root node and returning the connected (adjacent without gaps) cells.

         1 and 2   |     1 and 2
        connected: |  not connected:
                   |
           11      |      11
            22     |        22
                   |
           1122    |     11 22
                   |
            11     |       11
            2      |      2
            2      |      2

        find_connected is passed:
            root_node: the starting place for the search
            traveled: the path that the search has traveled so far 
                (i.e. [(1, 1), (1, 2), (1, 3)])
        for (1, 1) as the root node,
            first check if any of the possible neighbor nodes exist
            (generate set of possible neighbors, find intersect with explored.
            for each of the unexplored neighbors, start another call of find_connected
        if no new unexplored neighbors found, return the connection path.

        the top level function returns the combination of traveled.

        returns the connected cells, excluding cells listed in traveled.

        exclusions is for taking into account cells traveled on a 
        separate pass
        """
        neighbor_dirs = ((0, -1), (1, 0), (0, 1), (-1, 0))
        if traveled == None:
            traveled = set()
        segment_keys = {key for key in self.member_data if key not in traveled}
        if exclusions is not set():
            segment_keys -= exclusions
        if segment_keys == set():
            return set()
        if root_node is None:
            root_node = next(iter(segment_keys))
        traveled.add(root_node)
        possible_paths = {add_coords(neighbor_dir, root_node) for neighbor_dir in neighbor_dirs}
        walkable = set(segment_keys) & set(possible_paths) #intersection
        traveled |= walkable #union
        if walkable == set(): #is empty set
            return {root_node} #i.e. {(0, 0)}
        for direction in walkable:
            child_path = self.find_connected(root_node=direction, traveled=traveled, depth=depth + 1)
            traveled |= child_path #union
        return traveled

    def find_subregions(self, debug=True):
        """
        takes an mte and finds connected segments of an MTE 

        Returns a list of regions.

           0123
          +----
         0|11 3
         1|1 33
         2| 2  
         3| 2 4

        runs find_connected multiple times on progressively smaller chunks of an MTE.

        We start with cells:
        ((0, 0), (1, 0), (3, 0), (0, 1), (2, 1), (3, 1), (1, 2), (1, 3), (3, 3))

        and an empty list to hold the connected regions: []

        ...if group one is returned by the first pass ((0, 0), (1, 0), (0, 1)),

        regions = [((0, 0), (1, 0), (0, 1)),]

        the next round of find_connected is passed:
        ((3, 0), (2, 1), (3, 1), (1, 2), (1, 3), (3, 3))

        ...this returns (at random) one of the remaining regions: ((3, 0), (2, 1), (3, 1))

        regions = [((0, 0), (1, 0), (0, 1)), 
                   ((3, 0), (2, 1), (3, 1)),]
        
        the next round of find_connected is passed:
        ((1, 2), (1, 3), (3, 3))

        ...this returns (at random) the second to last region: ((1, 2), (1, 3))

        regions = [((0, 0), (1, 0), (0, 1)), 
                   ((3, 0), (2, 1), (3, 1)),
                   ((1, 2), (1, 3)),]

        the last round of find_connected sees only a single tuple passed to it:
        ((3, 3))

        ...this is the final unconnected region: ((3, 3))

        regions = [((0, 0), (1, 0), (0, 1)), 
                   ((3, 0), (2, 1), (3, 1)),
                   ((1, 2), (1, 3)),
                   ((3, 3))]

        """
        unchecked_cells = {key for key in self.member_data}
        seen_cells = set()
        regions = []
        found_region = None
        while unchecked_cells is not set():
            found_region = self.find_connected(exclusions=seen_cells)
            if found_region == set():
                break
            unchecked_cells -= found_region #a set operation
            seen_cells |= found_region
            regions.append(found_region)
        colors = [i for i in range(10)]
        for number, region in enumerate(regions):
            if debug:
                for cell in region:
                    actor_name = self.member_data[cell]['name']
                    if hasattr(actor_dict[actor_name], 'tile'):
                        actor_dict[actor_name].tile = term.color(number + 1)(str(number + 1))
                    else:
                        pass
                        print("549: doesn't hasattr")
        return regions

    def split_along_subregions(self, debug=False):
        regions = self.find_subregions(debug=debug)
        if len(regions) == 1:
            return
        for number, region in enumerate(regions):
            new_mte_name = '{}_{}'.format(self.name, number)
            mte_dict[new_mte_name] = Multi_tile_entity(name=new_mte_name, preset='empty')
            for segment in region:
                segment_data = self.member_data[segment]
                if not debug:
                    new_tile = segment_data['tile']
                else:
                    new_tile = term.on_color(number + 3 % 8)(term.color(number)(str(number)))
                current_location = actor_dict[segment_data['name']].coords()
                mte_dict[new_mte_name].add_segment(
                        segment_tile=new_tile,
                        write_coord=current_location,
                        offset=segment_data['offset'],
                        segment_name='{}_{}'.format(segment_data['name'], number),
                        blocking=segment_data['blocking'],
                        literal_name=True, animation_preset=None)
        for member_name in self.member_names:
            del map_dict[actor_dict[member_name].coords()].actors[member_name]
        del mte_dict[self.name]
        return

async def spawn_mte(base_name='mte', spawn_coord=(0, 0), preset='3x3_block'):
    mte_id = generate_id(base_name=base_name)
    mte_dict[mte_id] = Multi_tile_entity(name=mte_id, anchor_coord=spawn_coord, preset=preset)
    return mte_id

def multi_push(push_dir='e', pushed_actor=None, mte_parent=None):
    """
    pushes a multi_tile entity.
    TODO: allow pushes of arbitrarily chained MTEs:
    This requires that we check each leading face for additional entities:
    aaa->     @: player
    a@a->     a: first mte
    aaabbb->  b: second mte
       bbbA-> A: other actor
       bbb->
    """
    if pushed_actor is None and mte_parent is None:
        return False
    elif pushed_actor is not None and mte_parent is None:
        mte_parent = actor_dict[pushed_actor].multi_tile_parent
        print('mte_parent: {}'.format(mte_parent))
    dir_coords = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0)}
    move_by = dir_coords[push_dir]
    if mte_dict[mte_parent].check_collision(move_by=move_by):
        mte_dict[mte_parent].move(move_by=move_by)
        return True

async def rand_blink(actor_name='player', radius_range=(2, 4), delay=.2):
    await asyncio.sleep(delay)
    rand_angle = randint(0, 360)
    rand_radius = randint(*radius_range)
    start_point = actor_dict[actor_name].coords()
    end_point = add_coords(start_point, point_given_angle_and_radius(angle=rand_angle, radius=rand_radius))
    if map_dict[end_point].passable:
        actor_dict[actor_name].update(coord=end_point)

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
        actor_dict[actor_name].update(coord=point)

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

def read_brightness_preset_file(filename='brightness_preset.txt'):
    with open('brightness_preset.txt', 'r') as file:
        for line in file:
            output = literal_eval(line) #assumes a one-line file
    return output

#Global state setup-------------------------------------------------------------
term = Terminal()
brightness_vals = read_brightness_preset_file()
map_dict = defaultdict(lambda: Map_tile(passable=False, blocking=True))
mte_dict = {}
room_centers = set()
actor_dict = defaultdict(lambda: [None])
state_dict = defaultdict(lambda: None)
item_dict = defaultdict(lambda: None)
actor_dict['player'] = Actor(name='player', tile='@', tile_color='cyan', health=100, stamina=100)
actor_dict['player'].just_teleported = False
map_dict[actor_dict['player'].coords()].actors['player'] = True
state_dict['facing'] = 'n'
state_dict['menu_choices'] = []
state_dict['plane'] = 'normal'
state_dict['printing'] = False
state_dict['known location'] = True
state_dict['teleporting'] = False

#Drawing functions--------------------------------------------------------------
def tile_preset(preset='floor'):
    presets = {'floor':Map_tile(tile="░", blocking=False, passable=True,
                                description='A smooth patch of stone floor.',
                                magic=True, is_animated=False, animation=None),
                'wall':Map_tile(tile="𝄛", blocking=False, passable=True,
                                description='A rough stone wall.',
                                magic=True, is_animated=False, animation=None)}
    return presets[preset]

def paint_preset(tile_coords=(0, 0), preset='floor'):
    """
    Applies a preset to an existing map tile.

    Each attribute is individually set so that actors and items are preserved.
    """
    presets = {'floor':Map_tile(tile="░", blocking=False, passable=True,
                                description='A smooth patch of stone floor.',
                                magic=False, is_animated=False, animation=None),
                'wall':Map_tile(tile="𝄛", blocking=False, passable=True,
                                description='A rough stone wall.',
                                magic=False, is_animated=False, animation=None),
               'noise':Map_tile(tile='.', blocking=False, passable=True,
                                description='A shimmering insubstantial surface.',
                                magic=False, is_animated=True, 
                                animation=Animation(preset='noise')),
               'chasm':Map_tile(tile=' ', blocking=False, passable=False,
                                description='A gaping void',
                                magic=False, is_animated=True, 
                                animation=Animation(preset='chasm')),
               'grass':Map_tile(tile='▒', blocking=False, passable=True,
                                description='Soft ankle length grass',
                                magic=False, is_animated=True, 
                                animation=Animation(preset='grass')),
               'water':Map_tile(tile='█', blocking=False, passable=True,
                                description='Water.',
                                magic=False, is_animated=True, 
                                animation=Animation(preset='water')),
               'error':Map_tile(tile='?', blocking=False, passable=True,
                                description='ERROR',
                                magic=False, is_animated=False)}
    map_dict[tile_coords].passable = presets[preset].passable
    map_dict[tile_coords].tile = presets[preset].tile
    map_dict[tile_coords].blocking = presets[preset].blocking 
    map_dict[tile_coords].description = presets[preset].description
    if presets[preset].is_animated:
        map_dict[tile_coords].is_animated = presets[preset].is_animated
        map_dict[tile_coords].animation = Animation(preset=preset)
    else:
        map_dict[tile_coords].is_animated = False

def draw_box(top_left=(0, 0), x_size=1, y_size=1, filled=True, 
             tile=".", passable=True, preset='floor'):
    """ Draws a box to map_dict at the given coordinates."""
    x_min, y_min = top_left[0], top_left[1]
    x_max, y_max = x_min + x_size, y_min + y_size
    x_values = range(x_min, x_max)
    y_values = range(y_min, y_max)
    write_coords = []
    if filled:
        for x in x_values:
            for y in y_values:
                write_coords.append((x, y))
    else:
        corners = [(x_min, y_min), (x_min, y_min), (x_max, y_max)]
        write_coords.extend(corners)
        for x in range(x_min, x_max):
            for y in (y_min, y_max):
                write_coords.append((x, y))
        for y in range(y_min, y_max):
            for x in (x_min, x_max):
                write_coords.append((x, y))
    for point in write_coords:
        paint_preset(tile_coords=point, preset=preset)

def draw_centered_box(middle_coord=(0, 0), x_size=10, y_size=10, 
                  filled=True, tile='░', passable=True):
    top_left = (middle_coord[0] - x_size//2, middle_coord[1] - y_size//2)
    draw_box(top_left=top_left, x_size=x_size, y_size=y_size, filled=filled, tile=tile)

def draw_line(coord_a=(0, 0), coord_b=(5, 5), preset='floor',
                    passable=True, blocking=False):
    """draws a line to the map_dict connecting the two given points."""
    points = get_line(coord_a, coord_b)
    for point in points:
        paint_preset(tile_coords=point, preset=preset)
        map_dict[point].passable = passable
        map_dict[point].blocking = blocking

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

def point_within_circle(radius=20, center=(0, 0)):
    while True:
        point = point_within_square(radius=radius, center=center)
        distance_from_center = abs(point_to_point_distance(point_a=point, point_b=center))
        if distance_from_center <= radius:
            break
    return point


def check_point_within_arc(checked_point=(-5, 5), facing_angle=None, arc_width=90, center=None):
    """
    checks whether a point falls within an arc sighted from another point.
    """
    if facing_angle is None:
        facing_angle = dir_to_angle(state_dict['facing'], mirror_ns=True)
        with term.location(60, 5):
            print(822, facing_angle, checked_point, "    ")
        center = actor_dict['player'].coords()
    elif center is None:
        center = (0, 0)
    half_arc = arc_width / 2
    twelve_reference = (center[0], center[1] - 5)
    with term.location(60, 7):
        print("(829) twelve_reference:", twelve_reference)
    arc_range = ((facing_angle - half_arc) % 360,
                 (facing_angle + half_arc) % 360)
    found_angle = round(find_angle(p0=twelve_reference, p1=center, p2=checked_point))
    if checked_point[0] < center[0]:
        found_angle = 360 - found_angle
    result = angle_in_arc(given_angle=found_angle,
                          arc_begin=arc_range[0], 
                          arc_end=arc_range[1])
    return result


def angle_in_arc(given_angle, arc_begin=45, arc_end=135):
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

def points_around_point(radius=5, radius_spread=2, middle_point=(0, 0), 
                        in_cone=(0, 90), num_points=5):
    """
    returns a number of points fanned out around a middle point.
    given a non-zero radius_spread value, the points will be at a random radius
    centered on radius. 
    
    example: radius 5, radius_spread 2 becomes 5 +/- 2 or randint(3, 7)
    if in_cone is not None, the returned points are restricted to an arc.
    """
    #TODO: possibly useful for arc of blood in opposite direction from attack
    points = []
    radius_range = (radius - radius_spread, radius + radius_spread)
    for _ in range(num_points):
        rand_angle = randint(*in_cone)
        rand_radius = randint(*radius_range)
        points.append(point_given_angle_and_radius(angle=rand_angle, 
                                                   radius=rand_radius))
    return points

def get_points_along_line(start_point=(0, 0), end_point=(10, 10), num_points=5):
    """
    Writes a jagged passage between two points of a variable number of segments
    to map_dict.

    Uses np.linspace, np.astype and .tolist()

    returns nothing
    """
    x_value_range = (start_point[0], end_point[0])
    y_value_range = (start_point[1], end_point[1])
    x_values = linspace(*x_value_range, num=num_points).astype(int)
    y_values = linspace(*y_value_range, num=num_points).astype(int)
    points = list(zip(x_values.tolist(), y_values.tolist()))
    return points


def carve_jagged_passage(start_point=(0, 0), end_point=(10, 10), 
                         num_points=5, jitter=5, width=3,
                         preset='floor'):
    points = get_points_along_line(num_points=num_points,
                                  start_point=start_point,
                                  end_point=end_point,)
    points = add_jitter_to_middle(cells=points, jitter=jitter)
    multi_segment_passage(cells, width=3, preset=preset)

def add_jitter_to_middle(points=None, jitter=5):
    """
    takes a list of points and returns the same head and tail but with randomly
    shifted points in the middle.
    """
    if points is not None:
        head, *body, tail = points #tuple unpacking
        new_body = []
        for point in body:
            rand_shift = [randint(-jitter, jitter) for i in range(2)]
            new_body.append(add_coords(rand_shift, point))
        output = head, *new_body, tail #pack tuples back into one list
        return output
    else:
        return []


def chained_pairs(pairs=None):
    """
    Used for taking a list of points and returning pairs of points for drawing
    lines.

    input: ((1, 1), (2, 2), (3, 3), (4, 4))
    output: (((1, 1), (2, 2)), ((2, 2), (3, 3)), ((3, 3), (4, 4)))
    """
    if pairs is None:
        pairs = [(i, i * 2) for i in range(10)]
    return [(pairs[i], pairs[i + 1]) for i in range(len(pairs) - 1)]

def multi_segment_passage(points=None, preset='floor', width=3, 
                          passable=True, blocking=False):
    coord_pairs = chained_pairs(pairs=points)
    for coord_pair in coord_pairs:
        n_wide_passage(coord_a=coord_pair[0], coord_b=coord_pair[1],
                       width=width, passable=passable, blocking=blocking,
                       preset=preset)

def n_wide_passage(coord_a=(0, 0), coord_b=(5, 5), preset='floor',
                   passable=True, blocking=False, width=3,
                   fade_to_preset=None, fade_bracket=(.25, .75)):
    total_distance = point_to_point_distance(point_a=coord_a, point_b=coord_b)
    origin = (0, 0)
    if width == 0:
        return
    offsets = ((x, y) for x in range(-width, width + 1) 
                      for y in range(-width, width + 1))
    trimmed_offsets = {offset for offset in offsets if
                       point_to_point_distance(point_a=offset, point_b=origin) <= width / 2}
    points_to_write = set()
    for offset in trimmed_offsets:
        offset_coord_a = add_coords(coord_a, offset)
        offset_coord_b = add_coords(coord_b, offset)
        line_points = get_line(offset_coord_a, offset_coord_b)
        for point in line_points:
            points_to_write.add(point)
    for point in points_to_write:
        if fade_to_preset is not None:
            if prob_fade_point_to_point(start_point=coord_a, end_point=coord_b, 
                                        point=point, fade_bracket=fade_bracket):
                write_preset = preset
            else:
                write_preset = fade_to_preset
            paint_preset(tile_coords=point, preset=write_preset)
        else:
            paint_preset(tile_coords=point, preset=preset)

def prob_fade_point_to_point(start_point=(0, 0), end_point=(10, 10), 
                             point=(5, 5), fade_bracket=(.25, .75)):
    fade_slope = 1 / (fade_bracket[1] - fade_bracket[0])
    with term.location(80, 0):
        print(fade_slope)
    fade_intercept = fade_slope * -fade_bracket[0]
    total_distance = point_to_point_distance(point_a=start_point, point_b=end_point)
    point_distance = point_to_point_distance(point_a=start_point, point_b=point)
    if total_distance == 0:
        return False
    fade_threshold = ((point_distance / total_distance) * fade_slope) + fade_intercept
    if fade_threshold < 0:
        return True
    elif fade_threshold > 1:
        return False
    if fade_threshold > random():
        return False
    else:
        return True

def arc_of_points(start_coord=(0, 0), starting_angle=0, segment_length=4, 
                  fixed_angle_increment=5, segments=10, random_shift=True,
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
            last_angle += fixed_angle_increment
    return output_points, last_angle

def chain_of_arcs(start_coord=(0, 0), num_arcs=20, starting_angle=90, 
                  width=(2, 20), draw_mode='even', preset='floor'):
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
        segment_widths = linspace(*width, num=num_arcs).astype(int)
    for segment_width in segment_widths:
        rand_segment_angle = choice((-20, -10, 10, 20))
        points, starting_angle = arc_of_points(starting_angle=starting_angle, 
                                               fixed_angle_increment=rand_segment_angle,
                                               start_coord=arc_start,
                                               random_shift=False)
        for point in points:
            map_dict[point].tile = term.red("X")
        arc_start = points[-1] #set the start point of the next passage.
        multi_segment_passage(points=points, width=segment_width, preset=preset)

def cave_room(trim_radius=40, width=100, height=100, 
              iterations=20, debug=False, 
              kernel=True, kernel_offset=(0, 0), kernel_radius=3):
    """
    Generates a smooth cave-like series of rooms within a given radius
    and around a given starting point.
    """
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
    input_space = {(x, y):choice(['#', ' ']) 
                   for x in range(width) 
                   for y in range(height)}
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
    """
    Writes a dictionary representation of a region of space into the map_dict.
    """
    for coord, value in room.items():
        write_coord = add_coords(coord, top_left_coord)
        with term.location(80, 0):
            print(write_coord, value)
        if value == space_char:
            continue
        if value == hash_char:
            map_dict[write_coord].passable = True
            map_dict[write_coord].blocking = False
            map_dict[write_coord].tile = hash_char

def draw_circle(center_coord=(0, 0), radius=5, animation=None, preset='floor', filled=True,
                border_thickness=0, border_preset='chasm'):
    """
    draws a filled circle onto map_dict.
    """
    x_bounds = center_coord[0] - radius, center_coord[0] + radius
    y_bounds = center_coord[1] - radius, center_coord[1] + radius
    points = get_circle(center=center_coord, radius=radius)
    for point in points:
        if not map_dict[point].mutable:
            continue
        distance_to_center = point_to_point_distance(point_a=center_coord, point_b=point)
        if distance_to_center <= radius:
            paint_preset(tile_coords=point, preset=preset)
    if border_thickness > 0:
        boundary_circle = get_circle(radius=radius + border_thickness, center=center_coord)
        for point in set(boundary_circle) - set(points):
            paint_preset(tile_coords=point, preset=border_preset)

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
        await append_to_log(message="Nothing to throw!")
        return False
    del actor_dict['player'].holding_items[thrown_item_id]
    starting_point = actor_dict[source_actor].coords()
    throw_vector = (direction_tuple[0] * throw_distance,
                    direction_tuple[1] * throw_distance)
    destination = add_coords(starting_point, throw_vector)
    if rand_drift:
        drift = randint(0, rand_drift), randint(0, rand_drift)
        destination = add_coords(destination, drift)
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
    throw_text = "throwing {} {}.".format(item_dict[thrown_item_id].name)
    await append_to_log(message=throw_text)
    await travel_along_line(name='thrown_item_id', start_coord=starting_point, 
                            end_coords=destination, speed=.05, tile=item_tile, 
                            animation=None, debris=None)
    map_dict[destination].items[thrown_item_id] = True
    item_dict[thrown_item_id].current_location = destination
    return True

async def display_fuse(fuse_length=3, item_id=None, reset_tile=True):
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
        draw_circle(center_coord=center, radius=radius)
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
    actor_list = [actor for actor in map_dict[coord].actors.items()]
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
    debris_dict = {'wood':('SMASH!', ',.\''),
                   'stone':('SMASH!', '..:o')}
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
        message, palette = debris_dict[material]
        await append_to_log(message=message)
        root_x, root_y = actor_dict[actor].coords()
        asyncio.ensure_future(sow_texture(root_x, root_y, palette=palette, radius=3, seeds=6, 
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
    await append_to_log(message=output_text)

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
            actor_dict[pushed_name].update(coord=pushed_destination)

#REVIEWED TO HERE

async def bay_door(hinge_coord=(3, 3), patch_to_key="bay_door_0", 
                   orientation='n', segments=5, blocking=True, 
                   color_num=6, preset='thin', debug=False,
                   message_preset=None):
    """
    Instantiates an MTE that moves to one side when a pressure plate 
    (or other trigger) is activated.
    hinge_coord is the location of the "doorframe", where the door 
    disappears into.
    orientation is the direction that the door will propagate from hinge_coord
    A bay_door with 'n' orientation and segments 5, hinging on (0, 0) will have
    door segments at coords, (0, -1), (0, -2), (0, -3), (0, -4) and (0, -5)

    TODO: have bay doors (when closing) push any actor towards the direction 
          that they're closing.
    TODO: account for crushing damage if the actor can be destroyed,
    TODO: stop closing of door (i.e. jammed with a crate or tentacle) 
          if actor cannot be crushed (destroyed?)
    TODO: use ╞ type characters for interface with wall hinge tile?
    """
    state_dict[patch_to_key] = {}
    if orientation in ('n', 's'):
        style_dir = 'ns'
    elif orientation in ('e', 'w'):
        style_dir = 'ew'
    door_style = { 'secret':{'ns':'𝄛', 'ew':'𝄛'},
                   'thick':{'ns':'‖', 'ew':'═'},
                   'thin':{'ns':'│', 'ew':'─'},}
    message_presets = { 'ksh':['*kssshhhhh*'] * 2 }
    door_segment_tile = door_style[preset][style_dir]
    if debug:
        print(preset, style_dir, door_segment_tile)
    door = await spawn_mte(base_name=patch_to_key, spawn_coord=hinge_coord, preset='empty')
    dir_offsets = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0)}
    dir_coord_increment = dir_offsets[orientation]
    segment_names = []
    door_id = generate_id(base_name=patch_to_key)
    for segment_num in range(segments):
        offset = (dir_coord_increment[0] * (1 + segment_num), 
                  dir_coord_increment[1] * (1 + segment_num))
        spawn_coord = add_coords(hinge_coord, offset)
        segment_name = '{}_{}'.format(door_id, segment_num)
        segment_names.append((segment_name, spawn_coord))
        mte_dict[door].add_segment(write_coord=spawn_coord,
                                   segment_tile=door_segment_tile,
                                   offset=offset,
                                   segment_name=segment_name,
                                   moveable=False,
                                   blocking=blocking, 
                                   breakable=False)
    door_message = None
    if message_preset is not None and message_preset in message_presets: 
        door_message = message_presets[message_preset]
    door_state = None
    while True:
        if debug:
            with term.location(80, 5):
                print("1358: inside bay_door.", counter, patch_to_key)
        await asyncio.sleep(.1)
        for segment in segment_names:
            if segment_name[0] not in actor_dict:
                continue
        if await any_true(trigger_key=patch_to_key):
            if door_state is not 'open':
                door_state = 'open'
                if door_message is not None:
                    await append_to_log(message=door_message[0])
            for segment in reversed(segment_names):
                await asyncio.sleep(.2)
                actor_dict[segment[0]].update(('', '')) #move to nowhere
        else:
            if door_state is not 'close':
                door_state = 'close'
                if door_message is not None:
                    await append_to_log(message=door_message[1])
            for segment in segment_names:
                await asyncio.sleep(.2)
                actor_dict[segment[0]].update(segment[1])

async def bay_door_pair(hinge_a_coord, hinge_b_coord, patch_to_key='bay_door_pair_1',
        preset='thin', pressure_plate_coord=None, message_preset=None):
    """
    writes a pair of bay_doors to the map that listen on the same key.
    
    width of doorway is determined by the given coordinates.
    
    hinge_a_coord will take up the slack if the distance is an odd number
    """
    if hinge_a_coord[1] == hinge_b_coord[1]:
        if hinge_a_coord[0] > hinge_b_coord[0]:
            hinge_a_dir, hinge_b_dir = 'w', 'e'
            span = hinge_a_coord[0] - hinge_b_coord[0] - 1
            a_segments = span // 2
            b_segments = span - a_segments
        else:
            hinge_a_dir, hinge_b_dir = 'e', 'w'
            span = hinge_b_coord[0] - hinge_a_coord[0] - 1
            a_segments = span // 2
            b_segments = span - a_segments
    elif hinge_a_coord[0] == hinge_b_coord[0]:
        if hinge_a_coord[1] > hinge_b_coord[1]:
            hinge_a_dir, hinge_b_dir = 'n', 's'
            span = hinge_b_coord[1] - hinge_a_coord[1] - 1
            a_segments = span // 2
            b_segments = span - a_segments
        else:
            hinge_a_dir, hinge_b_dir = 's', 'n'
            span = hinge_a_coord[1] - hinge_b_coord[1] - 1
            a_segments = span // 2
            b_segments = span - a_segments
    else:
        return
    with term.location(60, 8):
        print("segments:", a_segments, b_segments)
    state_dict[patch_to_key] = {}
    if pressure_plate_coord is not None:
        asyncio.ensure_future(pressure_plate(spawn_coord=pressure_plate_coord,
                                             patch_to_key=patch_to_key,))
    asyncio.ensure_future(bay_door(hinge_coord=hinge_a_coord,
                                   patch_to_key=patch_to_key,
                                   orientation=hinge_a_dir,
                                   segments=a_segments,
                                   preset=preset,
                                   message_preset=message_preset)) 
    #one door is silent to prevent message repeats
    asyncio.ensure_future(bay_door(hinge_coord=hinge_b_coord,
                                   patch_to_key=patch_to_key,
                                   orientation=hinge_b_dir,
                                   segments=b_segments,
                                   preset=preset,
                                   message_preset=None))

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
        actor_dict[follower_id].update(coord=(follow_x, follow_y))

async def circle_of_darkness(start_coord=(0, 0), name='darkness', circle_size=4):
    actor_id = generate_id(base_name=name)
    loop = asyncio.get_event_loop()
    loop.create_task(basic_actor(*start_coord, speed=.5, movement_function=seek_actor, 
                                 tile=" ", name_key=actor_id, hurtful=True,
                                 is_animated=True, animation=Animation(preset="none")))
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
                                           tile='◘', tile_color='grey')
        actor_dict[node_name].update(coord=node_coord)
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
                                       tile='◘', tile_color='grey')
    actor_dict[trap_origin_id].update(coord=coord)
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

async def export_map(width=140, height=45):
    #store the current tile at the player's location:
    temp_tile = map_dict[actor_dict['player'].coords()].tile
    #represent the player's current location with an @ symbol:
    map_dict[actor_dict['player'].coords()].tile = '@'
    filename = "{}.txt".format('exported_map')
    if os.path.exists(filename): 
        os.remove(filename)
    player_location = actor_dict['player'].coords()
    x_spread = (-width // 2 + player_location[0], 
                 width // 2 + player_location[0])
    y_spread = (-height // 2 + player_location[1], 
                 height // 2 + player_location[1])
    with open(filename, 'a') as map_file:
        for y_pos, y in enumerate(range(*y_spread)):
            with term.location(60, y_pos):
                line_output = "{}\n".format("".join([map_dict[i, y].tile for i in range(*x_spread)]))
                map_file.write(line_output)
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
        with term.location(105, 6):
            print("current tile: {}".format(current_tile))
        tile_color = map_dict[current_coords].color_num
        with term.location(105, 7):
            print("tile_color: {}".format(tile_color))
        with term.location(105, 8):
            print("tile w/ color: {}".format(term.color(tile_color)(current_tile)))
        with term.location(105, 9):
            print("repr() of tile:")
        with term.location(105, 10):
            print("{}".format(repr(current_tile)))

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
                    #'bay door':'*kssshhhhhh*'}
    if positives is None:
        positives = ('player', 'weight', 'crate', 'static')
    triggered = False
    while True:
        await asyncio.sleep(test_rate)
        with term.location(80, 3):
            print(triggered, patch_to_key, plate_id, 1572)
        positive_result = await check_actors_on_tile(coords=spawn_coord, positives=positives)
        if positive_result:
            if not triggered:
                await append_to_log(message=sound_effects[sound_choice])
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
    draw_door(door_coord=door_coord, description='iron', locked=True)
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
    dir_coords = {'n':(0, -1, '│'), 'e':(1, 0, '─'), 's':(0, 1, '│'), 'w':(-1, 0, '─')}
    opposite_directions = {'n':'s', 'e':'w', 's':'n', 'w':'e'}
    if 'sword_out' in state_dict and state_dict['sword_out'] == True:
        return False
    state_dict['sword_out'] = True
    starting_coords = actor_dict[actor].coords()
    chosen_dir = dir_coords[direction]
    sword_id = generate_id(base_name=name)
    sword_segment_names = ["{}_{}_{}".format(name, sword_id, segment) for segment in range(1, length)]
    segment_coords = [(starting_coords[0] + chosen_dir[0] * i, 
                       starting_coords[1] + chosen_dir[1] * i) 
                      for i in range(1, length)]
    to_damage_names = []
    player_coords = actor_dict['player'].coords()
    for segment_coord, segment_name in zip(segment_coords, sword_segment_names):
        actor_dict[segment_name] = Actor(name=segment_name, moveable=False,
                                         tile=chosen_dir[2], tile_color=sword_color)
        map_dict[segment_coord].actors[segment_name] = True
        await damage_all_actors_at_coord(coord=segment_coord, damage=damage, source_actor='player')
        await asyncio.sleep(speed)
    retract_order = zip(reversed(segment_coords), reversed(sword_segment_names))
    for segment_coord, segment_name in retract_order:
        if segment_name in map_dict[segment_coord].actors: 
            del map_dict[segment_coord].actors[segment_name]
        del actor_dict[segment_name]
        await asyncio.sleep(retract_speed)
    state_dict['sword_out'] = False

async def sword_item_ability(length=3, speed=.05):
    facing_dir = state_dict['facing']
    asyncio.ensure_future(sword(facing_dir, length=length, 
                                speed=speed, retract_speed=speed))

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
        actor_dict[actor].update(coord=(1000, 1000))
        await asyncio.sleep(.8)
        actor_dict[actor].update(coord=(destination))
        await radial_fountain(frequency=.002, collapse=False, radius=(5, 12),
                              deathclock=30, speed=(1, 1))
    else:
        await append_to_log(message="Something is in the way.")
    
async def random_blink(actor='player', radius=20):
    current_location = actor_dict[actor].coords()
    await asyncio.sleep(.2)
    actor_dict[actor].update(coord=(500, 500))
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
                actor_dict[actor].update(coord=(blink_to))
                return
            else:
                continue
        else:
            actor_dict[actor].update(coord=(line_of_sight_result))
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
                            'power_kwargs':{'duration':5}, 'use_message':block_wand_text,
                            'broken_text':' is out of charges'},
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
               #'vine wand':{'uses':9999, 'tile':term.green('/'), 'usable_power':vine_grow, 
                            #'power_kwargs':{'on_actor':'player', 'start_facing':True}, 
                            #'broken_text':wand_broken_text},
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
            if len(map_dict[coord].items) < 10:
                map_dict[coord].items[item_id] = True
            else:
                for coord in adjacent_passable_tiles(base_coord=coord):
                    if len(map_dict[coord].items) < 10:
                        map_dict[coord].items[item_id] = True
                        break
        else:
            actor_dict[on_actor_id].holding_items[item_id] = True

def adjacent_passable_tiles(base_coord=(0, 0), orthagonal=False):
    """
    Returns the tiles adjacent to a given coordinate that are passable.
    """
    direction_offsets = ((0, -1), (1, 0), (0, 1), (-1, 0))
    valid_directions = []
    for offset in direction_offsets:
        coord = add_coords(base_coord, offset)
        if map_dict[coord].passable:
            valid_directions.append(coord)
    return valid_directions

async def display_items_at_coord(coord=actor_dict['player'].coords(), x_pos=2, y_pos=12):
    last_coord = None
    item_list = ' '
    with term.location(x_pos, y_pos):
        print("Items here:")
    while True:
        await asyncio.sleep(.1)
        player_coords = actor_dict['player'].coords()
        
        clear_screen_region(x_size=20, y_size=10, screen_coord=(x_pos, y_pos + 1))
        item_list = [item for item in map_dict[player_coords].items]
        for number, item_id in enumerate(item_list):
            with term.location(x_pos, (y_pos + 1) + number):
                print("{} {}".format(item_dict[item_id].tile, item_dict[item_id].name))
        last_coord = player_coords

async def display_items_on_actor(actor_key='player', x_pos=2, y_pos=24):
    item_list = ' '
    while True:
        await asyncio.sleep(.1)
        with term.location(x_pos, y_pos):
            print("Inventory:")
        clear_screen_region(x_size=15, y_size=10, screen_coord=(x_pos, y_pos+1))
        item_list = [item for item in actor_dict[actor_key].holding_items]
        for number, item_id in enumerate(item_list):
            with term.location(x_pos, (y_pos + 1) + number):
                print("{} {}".format(item_dict[item_id].tile, item_dict[item_id].name))

async def filter_print(output_text="You open the door.", x_offset=0, y_offset=-8, 
                       pause_fade_in=.01, pause_fade_out=.01, pause_stay_on=1, 
                       delay=0, blocking=False, hold_for_lock=True):
    if hold_for_lock:
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
                pause_between=.02, only_passable=True):
    """ given a root node, picks random points within a radius length and writes
    characters from the given palette to their corresponding map_dict cell.
    """
    for i in range(seeds):
        await asyncio.sleep(pause_between)
        throw_dist = radius + 1
        while throw_dist >= radius:
            x_toss, y_toss = (randint(-radius, radius),
                              randint(-radius, radius),)
            throw_dist = sqrt(x_toss**2 + y_toss**2) #distance
        #doors will be ignored:
        toss_coord = add_coords((root_x, root_y), (x_toss, y_toss))
        if only_passable and not map_dict[toss_coord].passable:
            continue
        if map_dict[toss_coord].mutable == False:
            continue
        if map_dict[toss_coord].magic == True:
            continue
        if paint:
            if map_dict[toss_coord].tile not in "▮▯":
                #colored_tile = term.color(color_num)(map_dict[toss_coord].tile)
                map_dict[toss_coord].color_num = 1
                #map_dict[toss_coord].tile = colored_tile
        else:
            random_tile = choice(palette)
            #map_dict[toss_coord].tile = term.color(color_num)(random_tile)
            map_dict[toss_coord].color_num = color_num
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

def secret_door(door_coord=(0, 0), tile_description="The wall looks a little different here."):
    draw_door(door_coord=door_coord, locked=False, description='secret')
    map_dict[door_coord].description = tile_description

def secret_room(wall_coord=(0, 0), room_offset=(10, 0), square=True, size=5):
    room_center = add_coords(wall_coord, room_offset)
    n_wide_passage(coord_a=wall_coord, coord_b=room_center, width=1)
    secret_door(door_coord=wall_coord)
    announcement_at_coord(coord=room_center, announcement="You found a secret room!" )
    if square:
        draw_centered_box(middle_coord=room_center, x_size=size, y_size=size, tile="░")
    else:
        draw_circle(center_coord=room_center, radius=size)

def draw_door(door_coord=(0, 0), closed=True, locked=False, description='wooden', is_door=True):
    """
    creates a door at the specified map_dict coordinate and sets the relevant
    attributes.
    """
    door_colors = {'red':1, 'green':2, 'orange':3, 'wooden':3, 'rusty':3, 
                   'blue':4, 'purple':5, 'cyan':6, 'grey':7, 'white':8,
                   'iron':7, 'secret':7}
    if description == 'secret':
        states = [('𝄛', False, True), ('▯', True, False)]
    else:
        states = [('▮', False, True), ('▯', True, False)]
    if closed:
        tile, passable, blocking = states[0]
    else:
        tile, passable, blocking = states[1]
    map_dict[door_coord].tile = term.color(door_colors[description])(tile)
    map_dict[door_coord].passable = passable
    map_dict[door_coord].blocking = blocking
    map_dict[door_coord].is_door = is_door
    map_dict[door_coord].locked = locked
    map_dict[door_coord].key = description
    map_dict[door_coord].mutable = False

async def fake_stairs(coord_a=(8, 0), coord_b=(-10, 0), 
                      hallway_offset=(-1000, -1000), hallway_length=15):
    #draw hallway
    draw_box(top_left=hallway_offset, x_size=hallway_length, y_size=1, tile="░")
    coord_a_hallway = add_coords(coord_a, hallway_offset)
    coord_b_hallway = add_coords(coord_a_hallway, (hallway_length, 0))
    #create magic doors:
    await create_magic_door_pair(door_a_coords=coord_a, door_b_coords=coord_a_hallway, silent=True)
    await create_magic_door_pair(door_a_coords=coord_b, door_b_coords=coord_b_hallway, silent=True)

async def under_passage(start=(-20, 27), end=(-20, 13), offset=(-1000, -1000), 
                        width=1, direction='ns', length=10):
    """
    Assumes parallel starting and ending directions.
    """
    under_start = add_coords(start, offset)
    end_offsets = {'ns':(0, length), 'ew':(length, 0)}
    under_end = add_coords(under_start, end_offsets[direction])
    n_wide_passage(coord_a=under_start, coord_b=under_end, width=width)
    await create_magic_door_pair(door_a_coords=start, door_b_coords=under_start, silent=True)
    await create_magic_door_pair(door_a_coords=end, door_b_coords=under_end, silent=True)

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
    animation = Animation(base_tile='▮', preset='door')
    map_dict[start_coord] = Map_tile(tile=" ", blocking=False, passable=True,
                                     magic=True, magic_destination=end_coords,
                                     is_animated=True, animation=animation)
    map_dict[start_coord].description = "The air shimmers slightly between you and the space beyond."
    map_dict[start_coord].tile = "M"
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
                    await append_to_log(message="You are teleported.")
                map_dict[player_coords].passable=True
                actor_dict['player'].update(coord=destination)
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
                          breakable=True, moveable=True, preset='random',
                          description='A wooden box'):
    box_choices = ['', 'nut', 'high explosives', 'red potion', 'fused charge']
    if preset == 'random':
        contents = [choice(box_choices)]
    container_id = spawn_static_actor(base_name=base_name, spawn_coord=spawn_coord,
                                      tile=tile, moveable=moveable, breakable=breakable,
                                      description=description)
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
                       multi_tile_parent=None, blocking=False, literal_name=False,
                       description='STATIC ACTOR'):
    """
    Spawns a static (non-controlled) actor at coordinates spawn_coord
    and returns the static actor's id.
    """
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
                                 blocking=blocking, description=description)
    map_dict[spawn_coord].actors[actor_id] = True
    return actor_id

def map_init():
    clear()
    room_a = (0, 0)
    room_b = (5, -20)
    room_c = (28, -28)
    room_d = (9, -39)
    room_e = (-20, 20)
    room_f = (-35, 20)
    room_g = (28, -34)
    draw_circle(center_coord=room_a, radius=10)
    draw_circle(center_coord=room_b, radius=5)
    draw_circle(center_coord=room_c , radius=7)
    draw_circle(center_coord=room_d , radius=8)
    draw_circle(center_coord=room_e, radius=6)
    draw_circle(center_coord=room_g, radius=6, preset='chasm')
    draw_centered_box(middle_coord=room_f, x_size=5, y_size=5, tile="░")
    n_wide_passage(coord_a=room_a, coord_b=room_b)
    n_wide_passage(coord_a=room_b, coord_b=room_c)
    n_wide_passage(coord_a=room_d, coord_b=room_c)
    n_wide_passage(coord_a=room_b, coord_b=room_d)
    n_wide_passage(coord_a=room_a, coord_b=room_e, width=5)
    n_wide_passage(coord_a=room_e, coord_b=room_f, width=1)
    secret_room(wall_coord=(-27, 20), room_offset=(-10, 0))
    secret_room(wall_coord=(35, -31))
    secret_room(wall_coord=(-40, 22), room_offset=(-3, 0), size=3)
    secret_room(wall_coord=(-40, 18), room_offset=(-3, 0), size=3)
    basement_door = (-28, 45)
    draw_door(door_coord=(0, 10))
    #announcement_at_coord()

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

def is_number(number="0"):
    try:
        float(number)
        return True
    except ValueError:
        return False

#Top level input----------------------------------------------------------------
async def get_key(help_wait_count=100): 
    """handles raw keyboard data, passes to handle_input if its interesting.
    Also, displays help tooltip if no input for a time."""
    debug_text = "key is: {}, same_count is: {}           "
    help_text = 'Press ? for help menu.'
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        key = None
        state_dict['same_count'] = 0
        old_key = None
        while True:
            await asyncio.sleep(0.03)
            if isData():
                key = sys.stdin.read(1)
                if key == '\x7f':  # x1b is ESC
                    state_dict['exiting'] = True
                if key is not None:
                    player_health = actor_dict["player"].health
                    #with term.location(0, 0):
                        #print(f'health: {player_health}'.ljust(12, 'X'))
                    if player_health > 0:
                        await handle_input(key)
            if old_key == key:
                state_dict['same_count'] += 1
            else:
                state_dict['same_count'] = 0
            old_key = key
            if (state_dict['same_count'] >= help_wait_count and 
                state_dict['same_count'] % help_wait_count == 0):
                if not any (help_text in line for line in state_dict['messages'][-10:]):
                    await append_to_log(message=help_text)
    finally: 
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings) 

async def handle_input(key):
    """
    interpret keycodes and do various actions.
    controls:
    wasd to move/push
    ijkl to look in different directions
    x to examine
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
    if state_dict['in_menu'] == True:
        if is_number(key):
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
                    await append_to_log(message='Out of breath!')
            actor_dict['player'].just_teleported = False #used by magic_doors
        if key in 'WASD': 
            if actor_dict['player'].stamina >= 15:
                asyncio.ensure_future(dash_ability(dash_length=5, direction=key_to_compass[key], 
                                                   time_between_steps=.04))
                actor_dict['player'].stamina -= 15
            else:
                await append_to_log(message='Out of breath!')
        if key in '?':
            await display_help() 
        if key in '3': #shift dimensions
            asyncio.ensure_future(pass_between(x_offset=1000, y_offset=1000, plane_name='nightmare'))
        if key in '4':
            draw_net()
        #if key in '8': #export map
            #asyncio.ensure_future(export_map())
        if key in 'Xx': #examine
            await examine_facing()
        if key in ' ': #toggle doors
            await toggle_doors()
        if key in 'Z': #test out points_around_point and write result to map_dict
            points = points_around_point()
            for point in points:
                map_dict[add_coords(point, player_coords)].tile = '$'
        if key in '$':
            print_screen_grid() 
        if key in '(':
            #spawn_coord = add_coords(player_coords, (2, 2))
            spawn_coord = player_coords
            #asyncio.ensure_future(spawn_mte(spawn_coord=spawn_coord))
            vine_name = "testing"
            asyncio.ensure_future(follower_vine(spawn_coord=spawn_coord))
        if key in '9': #creates a passage in a random direction from the player
            facing_angle = dir_to_angle(state_dict['facing'])
            chain_of_arcs(starting_angle=facing_angle, start_coord=player_coords, num_arcs=5)
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
        if key in 'u':
            asyncio.ensure_future(use_chosen_item())
        if key in 'M':
            spawn_coords = add_coords(player_coords, (2, 2))
            mte_id = await spawn_mte(spawn_coord=spawn_coords, preset='test_block')
        if key in 'y':
            #actor_dict['player'].update(coord=(-32, 20)) #jump to debug location
            destination = (-32, 20)
            actor_dict['player'].update(coord=destination)
            #actor_dict['player'].update(coord=(5, 5)) #jump to debug location
            state_dict['facing'] = 'w'
            return
        if key in 'Y':
            player_coords = actor_dict['player'].coords()
            asyncio.ensure_future(temp_view_circle(center_coord=player_coords))
        if key in '%': #place a temporary pushable block
            asyncio.ensure_future(temporary_block())
        if key in 'f': #use sword in facing direction
            await sword_item_ability(length=6)
        if key in '7':
            draw_circle(center_coord=actor_dict['player'].coords(), preset='floor')
        if key in '8':
            center_coord = actor_dict['player'].coords()
            endpoint = add_coords(center_coord, (90, 0))
            n_wide_passage(width = 5, coord_a=center_coord, coord_b=endpoint, 
                           #fade_to_preset='water', fade_bracket=(.2, .8)) 
                           fade_to_preset='grass', fade_bracket=(.2, .8))
        if key in 'R': #generate a random cave room around the player
            player_coords = add_coords(actor_dict['player'].coords(), (-50, -50))
            test_room = cave_room()
            write_room_to_map(room=test_room, top_left_coord=player_coords)
        if key in 'b': #spawn a force field around the player.
            asyncio.ensure_future(rand_blink())
        if key in '1': #draw a passage on the map back to (0, 0).
            n_wide_passage(coord_a=(actor_dict['player'].coords()), coord_b=(0, 0), preset='floor', width=5)
        shifted_x, shifted_y = x + x_shift, y + y_shift
        if map_dict[(shifted_x, shifted_y)].passable and (shifted_x, shifted_y) is not (0, 0):
            state_dict['last_location'] = (x, y)
            map_dict[(x, y)].passable = True #make previous space passable
            actor_dict['player'].update(coord=add_coords((x, y), (x_shift, y_shift)))
            x, y = actor_dict['player'].coords()
            map_dict[(x, y)].passable = False #make current space impassable
        if key in "ijkl": #change viewing direction
            state_dict['facing'] = key_to_compass[key]

async def examine_facing():
    direction = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
    player_coords = actor_dict['player'].coords()
    facing_offset = direction[state_dict['facing']]
    examined_coord = add_coords(player_coords, facing_offset)
    #add descriptions for actors
    if map_dict[examined_coord].actors:
        actor_name = list(map_dict[examined_coord].actors)[0]#"There's an actor there!"
        description_text = actor_dict[actor_name].description
    elif map_dict[examined_coord].items:
        description_text = "Theres an item here!"
    else:
        description_text = map_dict[examined_coord].description
    if description_text is not None:
        await append_to_log(message=description_text)

def open_door(door_coord, door_tile='▯'):
    map_dict[door_coord].tile = door_tile
    map_dict[door_coord].passable = True
    map_dict[door_coord].blocking = False

def close_door(door_coord, door_tile='▮'):
    map_dict[door_coord].tile = door_tile
    map_dict[door_coord].passable = False
    map_dict[door_coord].blocking = True

async def toggle_door(door_coord):
    door_state = map_dict[door_coord].tile 
    open_doors = [term.color(i)('▯') for i in range(10)]
    open_doors.append('▯')
    open_doors.append('▯')
    closed_doors = [term.color(i)('▮') for i in range(10)]
    closed_doors.append('▮')
    secret_tile = term.color(7)('𝄛')
    closed_doors.append(secret_tile)
    if map_dict[door_coord].locked:
        description = map_dict[door_coord].key
        output_text="The {} door is locked.".format(description)
        await append_to_log(message=output_text)
    elif door_state in closed_doors :
        open_door_tile = open_doors[closed_doors.index(door_state)]
        open_door(door_coord, door_tile=open_door_tile)
        if door_state != secret_tile:
            output_text = "You open the door."
            await append_to_log(message=output_text)
    elif door_state in open_doors:
        closed_door_tile = closed_doors[open_doors.index(door_state)]
        close_door(door_coord, door_tile=closed_door_tile)
        output_text = "You close the door."
        await append_to_log(message=output_text)

async def toggle_doors():
    x, y = actor_dict['player'].coords()
    player_coords = actor_dict['player'].coords()
    facing = state_dict['facing']
    directions = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
    door_coords = add_coords(player_coords, directions[facing])
    await toggle_door(door_coords)
    #door_dirs = {(-1, 0), (1, 0), (0, -1), (0, 1)}
    #for door in door_dirs:
        #door_coord = (x + door[0], y + door[1])
        #await toggle_door(door_coord)

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

async def choose_item(item_id_choices=None, item_id=None, x_pos=0, y_pos=25):
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
    clear_screen_region(x_size=20, y_size=5, screen_coord=(x_pos, y_pos))
    for (number, item) in enumerate(item_id_choices):
        with term.location(x_pos, y_pos + number):
            print("{}:".format(number))
    menu_choices = [str(i) for i in range(10)] #limit to 10 items on a square
    #while True:
    while state_dict['in_menu']:
        await asyncio.sleep(.1)
        menu_choice = state_dict['menu_choice']
        if type(menu_choice) == str:
            #TODO: fix limited slots in inventory choices
            if menu_choice not in menu_choices:
                return None
                menu_choice = int(menu_choice)
        if menu_choice in menu_choices:
            state_dict['in_menu'] = False
            state_dict['menu_choice'] = -1 # not in range as 1 evaluates as True.
            return item_id_choices[int(menu_choice)]
    clear_screen_region(x_size=2, y_size=len(item_id_choices), 
                              screen_coord=(x_pos, y_pos))

async def console_box(width=40, height=10, x_margin=2, y_margin=1, refresh_rate=.05):
    state_dict['messages'] = [''] * height
    asyncio.ensure_future(ui_box_draw(box_height=height, box_width=width, 
                                      x_margin=x_margin - 1, y_margin=y_margin - 1))
    while True:
        for index, line_y in enumerate(range(y_margin, y_margin + height)):
            #line_text = state_dict['messages'][-height + index] #bottom is newest
            line_text = state_dict['messages'][-index - 1] #top is newest
            with term.location(x_margin, line_y):
                print(line_text.ljust(width, ' '))
        await asyncio.sleep(refresh_rate)

async def append_to_log(message="This is a test"):
    message_lines = textwrap.wrap(message, 40)
    #first, add just the empty strings to the log:
    for index_offset, line in enumerate(reversed(message_lines)):
        await asyncio.sleep(.075)
        line_index = len(state_dict['messages'])
        state_dict['messages'].append('')
        asyncio.ensure_future(filter_into_log(message=line, line_index=line_index))

async def filter_into_log(message="This is a test", line_index=0, 
                          time_between_chars=.02):
    written_string = [' '] * len(message)
    indexes = [index for index in range(len(message))]
    shuffle(indexes)
    for index in indexes:
        await asyncio.sleep(time_between_chars)
        written_string[index] = message[index]
        state_dict['messages'][line_index] = ''.join(written_string)

async def key_slot_checker(slot='q', frequency=.1, centered=True, print_location=(0, 0)):
    """
    make it possible to equip each number to an item
    """
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
            x_coord, y_coord = offset_of_center(*print_location)
        else:
            x_coord, y_coord = print_location
        with term.location(x_coord + 2, y_coord + 5):
            print(slot)
        await print_icon(x_coord=x_coord, y_coord=y_coord, icon_name=item_name)

async def equip_item(slot='q'):
    """
    each slot must also have a coroutine to use the item's abilities.
    """
    slot_name = "{}_slot".format(slot)
    item_id_choice = await choose_item()
    state_dict[slot_name] = item_id_choice
    if hasattr(item_dict[item_id_choice], 'name'):
        item_name = item_dict[item_id_choice].name
        equip_message = "Equipped {} to slot {}.".format(item_name, slot)
        await append_to_log(message=equip_message)
    else:
        await append_to_log(message="Nothing to equip!")

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
            await append_to_log(message='Nothing happens.')

async def item_choices(coords=None, x_pos=0, y_pos=25):
    """
    -item choices should appear next to the relevant part of the screen.
    -a series of numbers and colons to indicate the relevant choices
    -give a position and list of values and item choices will hang until
     a menu choice is made.
    """
    if not map_dict[coords].items:
        await append_to_log(message="There's nothing here to pick up.")
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
    pickup_text = "You pick up the {}.".format(item_dict[item_id].name)
    del map_dict[coords].items[item_id]
    actor_dict['player'].holding_items[item_id] = True
    await append_to_log(message=pickup_text)
    return True

#Announcement/message handling--------------------------------------------------
async def parse_announcement(tile_coord_key):
    """ parses an annoucement, with a new line printed after each pipe """
    announcement_sequence = map_dict[tile_coord_key].announcement.split("|")
    for delay, line in enumerate(announcement_sequence):
        await append_to_log(message=line)

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
    #negative numbers into modulo wrap back around the other way.
    point_angle = (dir_to_angle(facing_dir) + offset_angle) % 360
    actor_coords = actor_dict[actor_key].coords()
    reference_point = (actor_coords[0], actor_coords[1] + 5)
    point = point_at_distance_and_angle(angle_from_twelve=point_angle,
                                              central_point=actor_coords,
                                              reference_point=reference_point,
                                              radius=radius)
    return point

def point_at_distance_and_angle(angle_from_twelve=30, central_point=(0, 0), 
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
    directions = ('n', 'e', 's', 'w',
                  'ne', 'se', 'sw', 'nw')
    angle_pairs = ((360, 0), (90, 90), (180, 180), (270, 270),
                   (135, 135), (35, 35), (315, 315), (225, 225))
    dir_to_angle_pair = dict(zip(directions, angle_pairs))
    facing = state_dict['facing'] 
    arc_pair = dir_to_angle_pair[facing] #of the format (angle, angle)
    is_in_left = (arc_pair[0] - half_fov) <= angle_from_twelve <= arc_pair[0] + half_fov
    is_in_right = (arc_pair[1] - half_fov) <= angle_from_twelve <= arc_pair[1] + half_fov
    if is_in_left or is_in_right:
        return True
    else:
        return False

def dir_to_angle(facing_dir, offset=0, mirror_ns=False):
    dirs_to_angle = {'n':180, 'e':90, 's':360, 'w':270,
                'ne':135, 'se':35, 'sw':315, 'nw':225}
    if mirror_ns:
        dirs_to_angle['n'] = 360
        dirs_to_angle['s'] = 180
    return (dirs_to_angle[facing_dir] + offset) % 360

async def angle_swing(radius=15):
    current_angle = dir_to_angle(state_dict['facing'])
    while True:
        pull_angle = dir_to_angle(state_dict['facing'])
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
            points = [point_at_distance_and_angle(radius=radius,
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
    x_offset, y_offset = offset_of_center(x_offset=-10, y_offset=-5)
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
        asyncio.ensure_future(filter_print(output_text=line, pause_stay_on=7,
                              pause_fade_in=.015, pause_fade_out=.015,
                              x_offset=-40, y_offset=-30 + line_number,
                              hold_for_lock=False))

async def tile_debug_info(x_print=18, y_print=0):
    dummy_text = []
    while True:
        directions = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
        check_dir = state_dict['facing']
        check_coord = add_coords(actor_dict['player'].coords(), directions[check_dir])
        for y_offset, line in enumerate(dummy_text):
            with term.location(*add_coords((x_print, y_print), (0, y_offset))):
                print(line)
        output_text = [f'tile_debug_info:',
                       f'facing: {check_dir}',
                       f' coord: {check_coord}',
                       f'actors: {map_dict[check_coord].actors.keys()}',
                       f'  tile: {map_dict[check_coord].tile}',]
        dummy_text = [' ' * len(line) for line in output_text]
        for y_offset, line in enumerate(output_text):
            with term.location(*add_coords((x_print, y_print), (0, y_offset))):
                print(line)
        await asyncio.sleep(.2)

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

async def view_tile(x_offset=1, y_offset=1, threshold=12, fov=140):
    """ handles displaying data from map_dict """
    #distance from offsets to center of field of view
    distance = sqrt(abs(x_offset)**2 + abs(y_offset)**2) 
    await asyncio.sleep(random()/5 * distance) #stagger starting_time
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    previous_tile = None
    #print_location = (middle_x + x_offset, middle_y + y_offset)
    print_location = add_coords((middle_x, middle_y), (x_offset, y_offset))
    last_print_choice = ' '
    angle_from_twelve = find_angle(p0=(0, 5), p2=(x_offset, y_offset))
    if x_offset <= 0:
        angle_from_twelve = 360 - angle_from_twelve
    display = False
    while True:
        await asyncio.sleep(distance * .015) #update speed
        player_coords = actor_dict['player'].coords()
        x_display_coord, y_display_coord = add_coords(player_coords, (x_offset, y_offset))
        tile_coord_key = (x_display_coord, y_display_coord)
        #check whether the current tile is within the current field of view
        current_angle = state_dict['current_angle']
        l_angle, r_angle = ((current_angle - fov // 2) % 360, 
                            (current_angle + fov // 2) % 360)
        display = angle_in_arc(angle_from_twelve, arc_begin=l_angle, arc_end=r_angle)
        if map_dict[x_display_coord, y_display_coord].override_view:
            display = True
        if (x_offset, y_offset) == (0, 0):
            print_choice=term.color(6)('@')
        elif display:
            #add a line in here for different levels/dimensions:
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
                color_choice = 8
            remembered_tile = map_dict[x_display_coord, y_display_coord].tile
            print_choice = term.color(color_choice)(remembered_tile)
        else:
            #catches tiles that are not within current FOV
            print_choice = ' '
        with term.location(*print_location):
            # only print something if it has changed:
            if last_print_choice != print_choice:
                tile_color = map_dict[tile_coord_key].color_num
                color_tuple = brightness_vals[int(distance)]
                if print_choice == "░":
                    print_choice = term.color(color_tuple[0])(color_tuple[1])
                elif print_choice == '𝄛':
                    print_choice = term.color(color_tuple[0])('𝄛')
                else:
                    print_choice = term.color(tile_color)(print_choice)
                print(print_choice)
                last_print_choice = print_choice
            # only print something if it has changed:

def find_brightness_tile(print_choice=None, distance=0):
    """
    returns the appropriate light-level shifted tile based on distance.
    """
    gradient_tile_pairs = {'░': ((0, ' '),          #dark
                                 (7, "░"),
                                 (8, "░"), 
                                 (7, "▒"),
                                 (8, "▒"), 
                                 (7, "▓"), 
                                 (7, "█"), 
                                 *((8, "▓"),) * 2,
                                 *((8, "█"),) * 6), #bright
                           '𝄛': ((8, ' '),
                                 (7, '𝄛'),
                                 (7, '𝄛'),
                                 (7, '𝄛'),
                                 (7, '𝄛'),
                                 (7, '𝄛'),
                                 (7, '𝄛'),
                                 (8, '𝄛'),
                                 (8, '𝄛'),
                                 (8, '𝄛'),
                                 (8, '𝄛'),
                                 (8, '𝄛'),
                                 (8, '𝄛'),
                                 (8, '𝄛'),
                                 (8, '𝄛'),)}

    bw_gradient = tuple([term.color(pair[0])(pair[1]) for pair in gradient_tile_pairs[print_choice]])
    bright_to_dark = {num:val for num, val in enumerate(reversed(bw_gradient))}

    brightness_index = distance
    if brightness_index <= 0:
        brightness_index = 0
    elif brightness_index >= 15:
        brightness_index = 14
    print_choice = bright_to_dark[int(brightness_index)]
    return print_choice

async def check_contents_of_tile(coord):
    if map_dict[coord].actors:
        actor_name = next(iter(map_dict[coord].actors))
        return actor_dict[actor_name].get_view()
    if map_dict[coord].items:
        item_name = next(iter(map_dict[coord].items))
        return item_dict[item_name].tile
    if map_dict[coord].is_animated:
        return next(map_dict[coord].animation)
    else:
        if map_dict[coord].color_num not in (7, 8):
            tile_color = map_dict[coord].color_num
            return term.color(tile_color)(map_dict[coord].tile)
        else:
            return map_dict[coord].tile

def offset_of_center(x_offset=0, y_offset=0):
    window_width, window_height = term.width, term.height
    middle_x, middle_y = (int(window_width / 2 - 2), 
                      int(window_height / 2 - 2),)
    x_print, y_print = middle_x + x_offset, middle_y + y_offset
    return x_print, y_print

def clear_screen_region(x_size=10, y_size=10, screen_coord=(0, 0), debug=False):
    if debug:
        marker = str(randint(0, 9))
    else:
        marker = ' '
    for y in range(screen_coord[1], screen_coord[1] + y_size):
        with term.location(screen_coord[0], y):
            print(marker * x_size)

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

async def directional_damage_alert(particle_count=40, source_angle=None, 
                                   source_actor=None, source_direction=None,
                                   radius=17, radius_spread=3, warning_color=1,
                                   angle_spread=60, preset='damage'):
    """
    generates a spray of red tiles beyond the normal sight radius in the
    direction of a damage source.
    """
    presets = {'damage':{'radius':15, 
                         'radius_spread':3, 
                         'angle_spread': 60,
                         'warning_color':1},
                'sound':{'radius':12,
                         'radius_spread':1,
                         'angle_spread': 80,
                         'warning_color':2,}}
    if preset is not None and preset in presets:
        preset_kwargs = presets[preset]
        await directional_damage_alert(**preset_kwargs, source_actor=source_actor, preset=None)
        return
    if source_actor:
        if source_actor not in actor_dict:
            return
        source_angle = angle_actor_to_actor(actor_a='player', actor_b=source_actor)
    elif source_direction is not None:
        if source_direction in source_directions:
            source_angle = dir_to_angle(source_direction)
    elif source_angle is None:
        return
    source_angle = 180 - source_angle
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    ui_points = []
    for _ in range(particle_count):
        point_radius = radius + randint(0, radius_spread)
        central_point = (middle_x, middle_y)
        angle = await random_angle(centered_on_angle=source_angle, 
                                   total_cone_angle=angle_spread)
        point = point_at_distance_and_angle(radius=point_radius,
                                            central_point=central_point,
                                            angle_from_twelve=angle,)
        ui_points.append(point)
    for tile in [term.color(warning_color)("█"), ' ']:
        shuffle(ui_points)
        for point in ui_points:
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

async def view_tile_init(loop, term_x_radius=15, term_y_radius=15, max_view_radius=15):
    for x in range(-term_x_radius, term_x_radius + 1):
       for y in range(-term_y_radius, term_y_radius + 1):
           distance = sqrt(x**2 + y**2)
           #cull view_tile instances that are beyond a certain radius
           if distance < max_view_radius:
               loop.create_task(view_tile(x_offset=x, y_offset=y))

async def minimap_init(loop, box_width=21, box_height=21):
    width_span = range(-20, 21, 2)
    height_span = range(-20, 21, 2)
    width, height = (term.width, term.height)
    x_offset, y_offset = (width - (box_width // 2) - 2), 1 + (box_height // 2)
    if width % 2 == 0:
        box_x_offset, box_y_offset = (width // 2) - box_width, -box_height - 1
    else:
        box_x_offset, box_y_offset = (width // 2) - box_width + 1, -box_height - 1

    asyncio.ensure_future(ui_box_draw(position='centered', x_margin=box_x_offset, y_margin=box_y_offset, 
                                      box_width=box_width, box_height=box_height))
    for x in width_span:
        for y in height_span:
            half_scale = x // 2, y // 2
            loop.create_task(minimap_tile(player_position_offset=(x, y),
                                          display_coord=(add_coords((x_offset, y_offset), half_scale))))

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
    #map drawing-------------------------------------------
    draw_circle(center_coord=(1000, 1000), radius=50, preset='noise')
    #features drawing--------------------------------------
    containers = [(3, -2), (3, -3), (-44, 21), (-36, 18), (-36, 22)]
    for coord in containers:
        loop.create_task(spawn_container(spawn_coord=coord))
    #item creation-----------------------------------------
    items = (((-3, 0), 'wand'), 
             ((-3, -3), 'red key'), 
             ((-2, -2), 'green key'),)
    for coord, item_name in items:
        spawn_item_at_coords(coord=coord, instance_of=item_name, on_actor_id=False)
    #actor creation----------------------------------------
    #for _ in range(10):
        #x, y = randint(-18, 18), randint(-18, 18)
        #loop.create_task(tentacled_mass(start_coord=(1000 + x, 1000 + y)))
    loop.create_task(create_magic_door_pair(door_a_coords=(-8, -8), door_b_coords=(1005, 1005),
                                            destination_plane='nightmare'))
    loop.create_task(spawn_container(spawn_coord=(3, -4)))
    #for i in range(3):
        #asyncio.ensure_future(follower_vine(root_node_key='tester', 
                                            #spawn_coord=tester_coord, 
                                            #facing_dir='s',
                                            #color_choice=2))
    loop.create_task(trap_init())

async def trap_init():
    loop = asyncio.get_event_loop()
    node_offsets = ((-6, 's'), (6, 'n'))
    nodes = [(i, *offset) for i in range(-5, 5) for offset in node_offsets]
    base_coord = (35, 20)
    rand_coords = {(randint(-5, 5) + base_coord[0], 
                    randint(-5, 5) + base_coord[1]) for _ in range(20)}
    state_dict['switch_1'] = {}
    #for coord in rand_coords:
       #loop.create_task(pressure_plate(spawn_coord=coord, patch_to_key='switch_1'))
    #loop.create_task(multi_spike_trap(nodes=nodes, base_coord=(35, 20), patch_to_key='switch_1'))
    #state_dict['switch_2'] = {}
    #loop.create_task(pressure_plate(spawn_coord=(19, 19), patch_to_key='switch_2'))
    #loop.create_task(pressure_plate(spawn_coord=(20, 20), patch_to_key='switch_2'))
    #loop.create_task(pressure_plate(spawn_coord=(21, 21), patch_to_key='switch_2'))
    #state_dict['switch_3'] = {}
    #loop.create_task(pressure_plate(spawn_coord=(54, 19), patch_to_key='switch_3'))
    #loop.create_task(spawn_turret())
    #loop.create_task(trigger_door(door_coord=(25, 20), patch_to_key='switch_2'))
    #loop.create_task(state_toggle(trigger_key='test'))
    #loop.create_task(puzzle_pair(puzzle_name='brown'))
    #loop.create_task(puzzle_pair(puzzle_name='cyan', block_coord=(-10, -7), plate_coord=(-7, -7), color_num=6))

#TODO: create a map editor mode, accessible with a keystroke??

async def pass_between(x_offset, y_offset, plane_name='nightmare'):
    """
    shift from default area to alternate area and vice versa.
    """
    player_x, player_y = actor_dict['player'].coords()
    if state_dict['plane'] == 'normal':
        destination, plane = (player_x + x_offset, player_y + y_offset), plane_name
    elif state_dict['plane'] == plane_name:
        destination, plane = (player_x - x_offset, player_y - y_offset), 'normal'
    else:
        return False
    if map_dict[destination].passable:
        map_dict[player_x, player_y].passable = True
        actor_dict['player'].update(coord=destination)
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
    loop = asyncio.get_event_loop()
    loop.create_task(display_items_at_coord())
    loop.create_task(display_items_on_actor())
    loop.create_task(key_slot_checker(slot='q', print_location=(46, 5)))
    loop.create_task(key_slot_checker(slot='e', print_location=(52, 5)))
    loop.create_task(console_box())
    health_title = "{} ".format(term.color(1)("♥"))
    stamina_title = "{} ".format(term.color(3)("⚡"))
    #loop.create_task(tile_debug_info())
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

async def delay_follow(name_key='player', window_length=20, speed=.02, delay_offset=10):
    moves = [[None, None]] * window_length
    grab_index = 0
    delay_index = delay_offset
    current_coords = actor_dict[name_key].coords()
    delay_id = spawn_static_actor(base_name='static', spawn_coord=current_coords, tile=' ',
                                  breakable=False, moveable=False,
                                  multi_tile_parent=None, blocking=False, literal_name=False,
                                  description='Your shadow.')
    while True:
        await asyncio.sleep(speed)
        grab_index = (grab_index + 1) % window_length
        delay_index = (delay_index + 1) % window_length
        moves[grab_index] = actor_dict[name_key].coords()
        if None not in moves[delay_index]:
            actor_dict[delay_id].update(moves[delay_index])

async def attack(attacker_key=None, defender_key=None, blood=True, spatter_num=3):
    attacker_strength = actor_dict[attacker_key].strength
    target_x, target_y = actor_dict[defender_key].coords()
    if blood:
        await sow_texture(root_x=target_x, root_y=target_y, radius=3, paint=True,
                          seeds=randint(1, spatter_num), description="Blood.")
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
    #seek_location = actor_dict[seek_key].coords()
    within_fov = check_point_within_arc(checked_point=actor_location, arc_width=120)
    distance_to_player = distance_to_actor(actor_a=name_key, actor_b='player')
    if distance_to_player >= 15:
        movement_choice = await wander(name_key=name_key)
    elif within_fov and distance_to_player < 10:
        with term.location(60, 6):
            print("Flee!   ")
        movement_choice = await seek_actor(name_key=name_key, seek_key=seek_key, repel=True)
    else:
        with term.location(60, 6):
            print("Attack!   ")
        movement_choice = await seek_actor(name_key=name_key, seek_key=seek_key, repel=False)
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

#TODO: an invisible attribute for actors
def fuzzy_forget(name_key=None, radius=3, forget_count=5):
    actor_location = actor_dict[name_key].coords()
    for _ in range(forget_count):
        rand_point = point_within_circle(radius=radius, center=actor_location)
        map_dict[rand_point].seen = False

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

def facing_dir_to_num(direction="n"):
    dir_to_num = {'n':0, 'e':1, 's':2, 'w':3}
    return dir_to_num[direction]

def num_to_facing_dir(direction_number=1):
    direction_number %= 4
    num_to_offset = {0:'n', 1:'e', 2:'s', 3:'w'}
    return num_to_offset[direction_number]

async def run_every_n(sec_interval=3, repeating_function=None, kwargs={}):
    while True:
        await asyncio.sleep(sec_interval)
        x, y = actor_dict['player'].coords()
        asyncio.ensure_future(repeating_function(**kwargs))

#Actor creation and controllers----------------------------------------------
async def tentacled_mass(start_coord=(-5, -5), speed=1, tentacle_length_range=(3, 8),
                         tentacle_rate=.1, tentacle_colors="456"):
    """
    creates a (currently) stationary mass of random length and color tentacles
    move away while distance is far, move slowly towards when distance is near, radius = 20?
    """
    tentacled_mass_id = generate_id(base_name='tentacled_mass')
    actor_dict[tentacled_mass_id] = Actor(name=tentacled_mass_id, moveable=False, tile='*',
                                          is_animated=True, animation=Animation(preset='mouth'))
    actor_dict[tentacled_mass_id].update(coord=start_coord)
    current_coord = start_coord
    while True:
        await asyncio.sleep(tentacle_rate)
        current_coord = await choose_core_move(core_name_key=tentacled_mass_id,
                                               tentacles=False)
        if current_coord:
            actor_dict[tentacled_mass_id].update(coord=current_coord)
        #tentacle_color = int(choice(tentacle_colors))
        #asyncio.ensure_future(vine_grow(start_x=current_coord[0], 
                #start_y=current_coord[1], actor_key="tentacle", 
                #rate=random(), vine_length=randint(*tentacle_length_range), rounded=True,
                #behavior="retract", speed=.01, damage=10, color_num=tentacle_color,
                #extend_wait=.025, retract_wait=.25 ))
        actor_dict[tentacled_mass_id].update(coord=current_coord)
    
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
    #initialize all shroud tiles to starting coordinates:
    core_location = (start_x, start_y)
    actor_dict[core_name_key] = Actor(name=core_name_key, moveable=False, tile=' ')
    actor_dict[core_name_key].update(coord=core_location)
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
                actor_dict[shroud_name_key].update(coord=new_coord)
        core_location = actor_dict[core_name_key].coords()
        if wait > 0:
            wait -= 1
            pass 
        else:
            new_core_location = await choose_core_move(core_name_key=core_name_key)
        if new_core_location:
            actor_dict[core_name_key].update(coord=new_core_location)

async def choose_core_move(core_name_key='', tentacles=True):
    """
    breaks out random movement of core into separate function
    """
    core_behavior_val = random()
    core_location = actor_dict[core_name_key].coords()
    if core_behavior_val < .05 and tentacles:
        new_core_location = actor_dict[core_name_key].coords()
        #TODO: replace with follower_vine
        #asyncio.ensure_future(vine_grow(start_x=core_location[0], start_y=core_location[1])),
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
        movement_function_kwargs={}, description='A featureless blob'):
    """
    actors can:
    move from square to square using a movement function
    hold items
    attack or interact with the player
    die
    exist for a set number of turns
    """
    actor_dict[(name_key)] = Actor(name=name_key, x_coord=start_x, y_coord=start_y, 
                                   speed=speed, tile=tile, hurtful=hurtful, 
                                   leaves_body=True, strength=strength, 
                                   is_animated=is_animated, animation=animation,
                                   holding_items=holding_items, description=description)
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
            actor_dict[name_key].update(coord=next_coords)

def distance_to_actor(actor_a=None, actor_b='player'):
    if actor_a is None:
        return 0
    a_coord = actor_dict[actor_a].coords()
    b_coord = actor_dict[actor_b].coords()
    return point_to_point_distance(point_a=a_coord, point_b=b_coord)

async def actor_turret(track_to_actor=None, fire_rate=.05, reach=15):
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
        for entry in mte_dict[parent_name].member_data.values():
            if name_key in entry.values():
                segment_key = entry['offset']
                #print(f'segment_key: {segment_key}')
        #delete MTE segment then try to split remaining segments:
        del mte_dict[parent_name].member_data[segment_key]
        mte_dict[parent_name].split_along_subregions()
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
    coord_choices = [point for point in get_circle(center=base_coord, radius=radius)
                            if map_dict[point].passable]
    for item in items:
        item_coord = choice(coord_choices)
        spawn_item_at_coords(coord=item_coord, instance_of=item)

async def follower_vine(spawn_coord=None, num_segments=10, base_name='mte_vine',
                        root_node_key=None, facing_dir='e', update_period=.1,
                        color_choice=None):
    """
    listens for changes in a list of turn instructions and reconfigures a
    vine-like multi-unit-entity to match those turn instructions.

    Modifications to turn instructions are not changed here, they are modified
    elsewhere. They are initialized here though.

    An option to have multiple MTE vines listen to one instruction string?

    instructions are given as either 'L', 'M' or 'R'.
    encoding the state as a series of turn instructions makes it easily transformed.
    
    Given a starting direction of East with a root represented as R, the
    following configurations of a seven-unit mte vine would be represented as

     3232323   1222321   2221144
    'RLRLRLR'|'LRMMRLL'|'MMLMLMM'  
             |         |               ^    
      R┐     |  ┌──┐   |   ──┐         1    
       └┐    | R┘  └┘  |     │     < 4 . 2 >
        └┐   |         |  R──┘         3    
         └┐  |         |               v    
 
    Multiple segments of the same MTE vine can occupy the same location

    """
    if root_node_key is not None:
        current_coord = actor_dict[root_node_key].coords()
    elif spawn_coord is not None:
        current_coord = spawn_coord
    vine_name = await spawn_mte(base_name=base_name, spawn_coord=current_coord, preset='empty',)
    vine_id = generate_id(base_name='')
    for number in range(num_segments):
        mte_dict[vine_name].add_segment(
                 segment_tile='x',
                 write_coord=current_coord,
                 offset=(0, 0),
                 segment_name=f'{vine_id}_segment_{number}')
    mte_dict[vine_name].vine_instructions = "M" * num_segments
    mte_dict[vine_name].vine_facing_dir = facing_dir
    dir_increment = {'L':-1, 'M':0, 'R':1}
    direction_offsets = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
    inverse_direction_offsets = {'n':(0, 1), 'e':(-1, 0), 's':(0, -1), 'w':(1, 0),}
    if color_choice is None:
        color_choice = choice((1, 2, 3, 4, 5, 6, 7))
    while True:
        await asyncio.sleep(update_period)
        mte_dict[vine_name].vine_instructions = mte_vine_animation_step(mte_dict[vine_name].vine_instructions)
        write_dir = mte_dict[vine_name].vine_facing_dir
        if root_node_key is None:
            current_coord = add_coords(inverse_direction_offsets[write_dir], 
                    actor_dict[mte_dict[vine_name].member_names[0]].coords())
        else:
            current_coord = add_coords(inverse_direction_offsets[write_dir], 
                    actor_dict[root_node_key].coords())
        write_list = [] #clear out write_list
        next_offset = direction_offsets[write_dir]
        write_coord = add_coords(next_offset, current_coord)
        instructions = mte_dict[vine_name].vine_instructions
        for turn_instruction in instructions:
            prev_dir = write_dir
            write_dir = num_to_facing_dir(facing_dir_to_num(write_dir) + 
                                          dir_increment[turn_instruction])
            next_offset = direction_offsets[write_dir]
            segment_tile = choose_vine_tile(prev_dir, write_dir)
            write_list.append((write_coord, segment_tile)) #add to the end of write_list
            write_coord = add_coords(next_offset, write_coord) #set a NEW write_coord here
        member_names = mte_dict[vine_name].member_names
        for segment_name, (write_coord, segment_tile) in zip(member_names, write_list):
            actor_dict[segment_name].update(coord=write_coord)
            actor_dict[segment_name].tile = segment_tile
            actor_dict[segment_name].tile_color = color_choice

def rand_swap_on_pattern(input_string='LRLRLRLR', pattern='LRL', 
                         replacements=('LLL', 'MMM', 'RRR'), debug=False):
    """
    Finds and replaces a randomly chosen matching substring of an instruction
    list ('L', 'M' or 'R') and swaps it for a randomly chosen replacement.
    """
    match_indexes = [match.span() for match in re.finditer(pattern, input_string)]
    if not match_indexes:
        return False
    start_index, end_index = choice(match_indexes)
    if type(replacements) == str:
        replacement = replacements
    else:
        replacement = choice(replacements)
    head, tail = input_string[:start_index], input_string[end_index:]
    output_string = ''.join((head, replacement, tail))
    if debug:
        with term.location(0, 0):
            print(f' input: {input_string}')
        with term.location(0, 1):
            print(f'output: {output_string}')
    return output_string

def mte_vine_animation_step(instructions, debug=False):
    """
    randomly chooses substrings of L, M and R instruction strings to be swapped
    out to change the configuration of an existing mte_vine.
    """
    swaps = {'LRM':('MLR',),
             'RLM':('MRL',),
             'LRRL':('MMMM', 'RLLR', 'LLLL'),
             'RLLR':('LRRL', 'MMMM', 'RRRR'),
             'LLLL':('LRRL'), #loop to bend
             'MMMM':('RLLR', 'LRRL'),
             'RRRR':('RLLR'), #loop to bend
             'LR':('MM', 'LR'),
             'RL':('MM', 'RL'),
             'MM':('LR', 'RL'),
             'RLR':('MRM'),
             'MRM':('RLR'),
             'LRL':('MLM'),
             'MLM':('LRL'),}
    swap_choices = [pattern for pattern in swaps.keys() if pattern in instructions]
    if type(swap_choices) == str:
        swap_choice = swap_choices
    else:
        swap_choice = choice(swap_choices)
    new_instructions = rand_swap_on_pattern(input_string=instructions, 
                                            pattern=swap_choice,
                                            replacements=swaps[swap_choice], 
                                            debug=debug)
    return new_instructions

def choose_vine_tile(prev_dir=1, next_dir=2, rounded=True, color_num=8):
    if prev_dir in 'nesw':
        prev_dir = facing_dir_to_num(prev_dir)
    if next_dir in 'nesw':
        next_dir = facing_dir_to_num(next_dir)
    straight_vine_picks = {(0, 1):'┌', (3, 2):'┌', (1, 2):'┐', (0, 3):'┐', (0, 0):'│', (2, 2):'│', 
                (2, 3):'┘', (1, 0):'┘', (2, 1):'└', (3, 0):'└', (1, 1):'─', (3, 3):'─', }
    rounded_vine_picks = {(0, 1):'╭', (3, 2):'╭', (1, 2):'╮', (0, 3):'╮', (0, 0):'│', (2, 2):'│', 
                (2, 3):'╯', (1, 0):'╯', (2, 1):'╰', (3, 0):'╰', (1, 1):'─', (3, 3):'─', }
    if rounded:
        tile_choice = rounded_vine_picks[(prev_dir, next_dir)]
    else:
        tile_choice = straight_vine_picks[(prev_dir, next_dir)]
    return tile_choice

async def health_potion(item_id=None, actor_key='player', total_restored=25, 
                        duration=2, sub_second_step=.1):
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
    bubble_id = generate_id(base_name='')
    bubble_pieces = {}
    player_coords = actor_dict['player'].coords()
    every_five = [i * 5 for i in range(72)]
    points_at_distance = {point_at_distance_and_angle(radius=radius, central_point=player_coords, angle_from_twelve=angle) for angle in every_five}
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
        point = point_at_distance_and_angle(radius=radius, 
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
    actor_dict[turret_id].update(coord=spawn_coord)
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
    actor_dict[turret_id].update(coord=spawn_coord)
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
        actor_dict[particle_id].update(coord=point)
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
        point = point_at_distance_and_angle(angle_from_twelve=rand_angle, 
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
        if occupied(new_position) and not drag_through_solid:
            if not map_dict[actor_coords].passable:
                map_dict[actor_coords].passable = True
            actor_dict[actor_key].update(coord=new_position)
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
        point_coord = point_at_distance_and_angle(radius=radius, central_point=on_center, angle_from_twelve=angle)
        if point_coord != last_location:
            actor_dict[particle_id].update(coord=point_coord)
            last_location = actor_dict[particle_id].coords()
        map_dict[last_location].actors[particle_id] = True
        angle = (angle + degrees_per_step) % 360

async def death_check():
    player_health = actor_dict["player"].health
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    death_message = "You have died."
    while True:
        await asyncio.sleep(0.1)
        player_health = actor_dict["player"].health
        if player_health <= 0:
            asyncio.ensure_future(filter_print(pause_stay_on=99, output_text=death_message))
            #state_dict['halt_input'] = True
            await asyncio.sleep(3)
            state_dict['killall'] = True

async def environment_check(rate=.1):
    """
    checks actors that share a space with the player and applies status effects
    and/or damage over time for obstacle-type actors such as tentacles from 
    vine_grow().
    """
    while actor_dict['player'].health >= 0:
        await asyncio.sleep(rate)
        player_coords = actor_dict['player'].coords()
        with term.location(40, 0):
            print(" " * 10)
        with term.location(40, 0):
            print(len([i for i in map_dict[player_coords].actors.items()]))

async def spawn_preset_actor(coords=(0, 0), preset='blob', speed=1, holding_items=[]):
    """
    spawns an entity with various presets based on preset given.
    *** does not need to be set at top level. Can be nested in map and character
    placement.
    """
    loop = asyncio.get_event_loop()
    actor_id = generate_id(base_name=preset)
    name = "{}_{}".format(preset, actor_id)
    start_coord = coords
    if preset == 'blob':
        item_drops = ['red potion']
        description = 'A gibbering mass of green slime that pulses and writhes before your eyes.'
        loop.create_task(basic_actor(*coords, speed=.3, movement_function=waver, 
                                     tile='ö', name_key=name, hurtful=True, strength=0,
                                     is_animated=True, animation=Animation(preset="blob"),
                                     holding_items=item_drops, description=description))
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
    loop.create_task(view_tile_init(loop))
    loop.create_task(minimap_init(loop))
    loop.create_task(ui_setup()) #UI_SETUP 
    loop.create_task(printing_testing())
    loop.create_task(async_map_init())
    #loop.create_task(shrouded_horror(start_x=-8, start_y=-8))
    loop.create_task(death_check())
    loop.create_task(quitter_daemon())
    loop.create_task(under_passage())
    loop.create_task(under_passage(start=(-13, 20), end=(-26, 20), direction='ew'))
    loop.create_task(under_passage(start=(-1023, -981), end=(-1016, -979), width=2))
    loop.create_task(display_current_tile()) #debug for map generation
    loop.create_task(bay_door(hinge_coord=(-3, 0), orientation='e', patch_to_key='test', preset='secret')) #debug for map generation
    loop.create_task(bay_door(hinge_coord=(8, 0), orientation='w', patch_to_key='test', preset='secret')) #debug for map generation
    loop.create_task(bay_door_pair((-7, 3), (-2, 3), patch_to_key='bay_door_pair_1',
        preset='thin', pressure_plate_coord=(-5, 0), message_preset='ksh')) #debug for map generation
    loop.create_task(bay_door_pair((2, -15), (6, -15), patch_to_key='bay_door_pair_2',
        preset='thick', pressure_plate_coord=(4, -13), message_preset='ksh')) #debug for map generation
    loop.create_task(pressure_plate(spawn_coord=(-3, 3), patch_to_key='test'))
    for i in range(1):
        rand_coord = (randint(-5, -5), randint(-5, 5))
        loop.create_task(spawn_preset_actor(coords=rand_coord, preset='blob'))
    asyncio.set_event_loop(loop)
    result = loop.run_forever()

with term.hidden_cursor():
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        main()
    finally: 
        clear()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings) 
