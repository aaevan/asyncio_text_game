import asyncio
import re
import os
import sys
import select 
import tty 
import termios
import textwrap
from numpy import linspace
from blessed import Terminal
from copy import copy
from collections import defaultdict
from datetime import datetime
from inspect import iscoroutinefunction
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
    def __init__(
        self, 
        passable=True,                      #actors can step through
        tile='𝄛',                           #old tile representation
        brightness_mod=0,                   #amount to shift tile brightness
        blocking=True,                      #line of sight is occluded
        description='A rough stone wall.',  #description when examined
        announcing=False,                   #used by announcement_at_coord
        seen=False,                         #True: displays in grey outside FOV
        announcement='',                    #a one-time message tied to a tile
        distance_trigger=None,              #distance at which annoucement runs
        is_animated=False,                  #decides whether a tile is animated
        animation='',                       #which animation preset that runs
        actors=None,                        #a dict of the actors present 
        items=None,                         #a dict of the items present
        magic=False,                        #used by magic_door
        magic_destination=False,            #the destination of any magic door
        mutable=True,                       #whether the tile can be changed
        override_view=False,                #show up when hidden or not in FOV
        color_num=8,                        #color to display character
        is_door=False,                      #if true, can be toggled
        locked=False,                       #lock state of door
        door_type='',                       #matches key required for entry
        prevent_pushing=False,              #prevent pushing onto this square
        use_action_func=None,               #function that runs on use action
        use_action_kwargs=None,             #kwards of use_action function
        toggle_states=None,                 #used for elements with multiple states
                #example: toggle_states = (('▯', False, False), ('▮', True, True))
                #the first element of each sub-tuple is the tile, '▯'
                #the second is the blocking state: False
                #the third element is the passable state: False
                #('▮', True, True) --> a door that is solid and opaque when closed
        toggle_state_index=None,            #keeps track of the current tile state
        run_on_entry=None,
        run_on_entry_kwargs=None,
    ):
        """ 
        Create a new Map_tile, map_dict holds tiles.
        A Map_tile is accessed from map_dict via a tuple key, ex. (0, 0).
        The tile representation of Map_tile at coordinate (0, 0) is accessed
        with map_dict[(0, 0)].tile.
        actors is a dictionary of actor names with value == True if 
        occupied by that actor, otherwise the key is deleted.
        """
        if len(tile) > 1:
            self.tile = choice(tile)
        else:
            self.tile = tile
        self.brightness_mod = brightness_mod
        #self.tile = tile
        self.passable = passable
        self.blocking = blocking
        self.description = description
        self.announcing = announcing
        self.seen = seen
        self.announcement = announcement
        self.distance_trigger = distance_trigger
        if not actors:
            self.actors = defaultdict(lambda:None)
        #allows for new map_tiles to be initialized with an existing actor list
        else:
            self.actors = actors
        self.items = defaultdict(lambda:None)
        self.is_animated = is_animated
        self.animation = animation
        self.magic = magic
        self.magic_destination = magic_destination
        self.mutable = mutable
        self.override_view = override_view
        self.color_num = color_num
        self.is_door = is_door
        self.locked = locked
        self.door_type = door_type
        self.prevent_pushing = prevent_pushing
        self.use_action_func = use_action_func
        self.use_action_kwargs = use_action_kwargs
        self.toggle_states = toggle_states
        self.toggle_state_index = toggle_state_index
        self.run_on_entry = run_on_entry
        self.run_on_entry_kwargs = run_on_entry_kwargs

class Actor:
    """ the representation of a single actor that lives on the map. """
    def __init__(
        self,
        name='',
        base_name='base name',
        coord=(0, 0),
        speed=.2, 
        tile="?", 
        base_attack=1,
        health=50,
        hurtful=True,
        moveable=True,
        is_animated=False,
        animation="",
        holding_items={},
        leaves_body=False,
        breakable=False,
        multi_tile_parent=None, 
        blocking=False,
        tile_color=8,
        description="A featureless gray blob",
        y_hide_coord=None,
        solid=True
    ):
        self.name = name
        self.base_name = base_name
        self.coord = coord
        self.speed = speed
        self.tile = tile
        self.tile_color = tile_color
        self.base_attack = base_attack
        self.health = health
        self.hurtful = hurtful
        #max health is set to starting value
        self.max_health = self.health 
        self.alive = True
        self.moveable = moveable
        self.is_animated = is_animated
        self.animation = animation
        self.leaves_body = leaves_body
        self.holding_items = holding_items
        self.breakable = breakable
        self.last_location = coord
        self.multi_tile_parent = multi_tile_parent
        self.blocking = blocking
        self.description = description
        self.y_hide_coord = y_hide_coord
        self.solid=solid

    def update(self, coord=(0, 0), make_passable=True):
        self.last_location = self.coord
        #make previous space passable:
        if make_passable:
            map_dict[self.last_location].passable = True 
        if self.name in map_dict[self.coords()].actors:
            del map_dict[self.coords()].actors[self.name]
        self.coord = coord
        map_dict[self.coords()].actors[self.name] = True
        run_on_entry = map_dict[self.coords()].run_on_entry
        run_on_entry_kwargs = map_dict[self.coords()].run_on_entry_kwargs
        if run_on_entry is not None:
            if iscoroutinefunction(run_on_entry):
                asyncio.ensure_future(
                    run_on_entry(**run_on_entry_kwargs)
                )
            else:
                run_on_entry(**run_on_entry_kwargs)

    def coords(self):
        return self.coord

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

class Room:
    """
    A representation of a room to map_dict.
    """
    def __init__(
        self, 
        center_coord=(-30, -30),
        dimensions=(10, 10),
        floor_preset='floor',
        inner_radius=None
    ):
        self.center_coord = center_coord
        self.dimensions = dimensions
        self.floor_preset = floor_preset
        self.inner_radius = inner_radius

    def draw_room(self):
        """
        draws a circle if given a number
        draws a rectangle if given a 2-tuple
        if given an inner_radius value, the circle will be drawn as a ring.
        """
        if type(self.dimensions) == int:
            draw_circle(
                center_coord=self.center_coord,
                radius=self.dimensions, 
                preset=self.floor_preset,
                annulus_radius=self.inner_radius
            )
        elif type(self.dimensions) == tuple and len(self.dimensions) == 2:
            draw_centered_box(
                middle_coord=self.center_coord, 
                x_size=self.dimensions[0],
                y_size=self.dimensions[1], 
                preset=self.floor_preset
            )
    def connect_to_room(
            self, 
            room_coord=(100, 100), 
            passage_width=2, 
            fade_to_preset=None, 
            style=None
        ):
        #connects on center with another coord
        if room_coord is not None:
            if style is None:
                n_wide_passage(
                    coord_a=self.center_coord,
                    coord_b=room_coord, 
                    width=passage_width,
                    fade_to_preset=fade_to_preset
                )
            if style is 'jagged':
                carve_jagged_passage(
                    start_point=self.center_coord,
                    end_point=room_coord,
                    num_points=5, 
                    jitter=5, 
                    width=passage_width, 
                    preset=fade_to_preset
                )
        else:
            print("No room provided!")

class Animation:
    def __init__(
        self,
        animation=None,
        base_tile='o',
        behavior=None,
        color_choices=None,
        preset="none",
        background=None,
    ):
        presets = {
            'bars':{
                'animation':(' ▁▂▃▄▅▆▇█'), 
                'behavior':'walk both', 
                'color_choices':'2'
            },
            'blob':{
                'animation':('ööööÖ'),
                'behavior':'loop tile',
                'color_choices':('2')
            },
            'bullet':{
                'animation':('◦◦◦○'),
                'behavior':'random',
                'color_choices':'446'
            },
            'blank':{
                'animation':' ', 
                'behavior':'random', 
                'color_choices':'0'
            },
            'chasm':{
                'animation':(' ' * 10 + '.'), 
                'behavior':'random', 'color_choices':'8'
            },
            'door':{
                'animation':('▯'), 
                'behavior':'random', 
                'color_choices':'78888'
            },
            'energy block':{
                'animation':'▤▥▦▧▨▩', 
                'behavior':'random', 
                'color_choices':'456'
            },
            'explosion':{
                'animation':('█▓▒'), 
                'behavior':'random', 
                'color_choices':'111333',
                'background':'0111333'
            },
            'fire':{
                'animation':'^∧', 
                'behavior':'random', 
                'color_choices':'3331'
            },
            'pulse':{
                'animation':(base_tile), 
                'behavior':'loop both',
                'color_choices':
                    [i for i in list(range(0xe8, 0xff, 2)) + list(range(0xff, 0xe8, -2))],
            },
            'goo':{
                'animation':('▒'), 
                'behavior':'random',
                'color_choices':(0x35, 0x36, 0x37, 0x38, 0x39),
            },
            'grass':{
                'animation':('▒'), 
                'behavior':'random',
                'color_choices':(0x4c, 0x4c, 0x4c, 0x70),
            },
            'terminal':{
                'animation':('▤▥▦▧▨▩'), 
                'behavior':'random',
                #'color_choices':(0x1c, 0x2e, 0x2e, 0x2e),
                'color_choices':(0x4c, 0x4c, 0x4c, 0x70),
            },
            'loop test':{
                'animation':('0123456789abcdefghi'), 
                'behavior':'loop both', 
                'color_choices':'33333344444'
            },
            'mouth':{
                'animation':('✳✳✳✳✳✸✸'),
                'behavior':'loop tile',
                'color_choices':('456')
            },
            'nightmare':{
                'animation':('      ▒▓▒ ▒▓▒'), 
                'behavior':'random',
                'color_choices':(0x34, 0x58),
            },
            'noise':{
                'animation':('      ▒▓▒ ▒▓▒'), 
                'behavior':'loop tile', 
                'color_choices':(0xe9, 0xea),
            },
            'sparse noise':{
                'animation':(' ' * 100 + '█▓▒'), 
                'behavior':'random', 
                'color_choices':'1' * 5 + '7'
            },
            'shimmer':{
                'animation':(base_tile), 
                'behavior':'random', 
                'color_choices':'1234567'
            },
            'spikes':{
                'animation':('∧∧∧∧‸‸‸     '), 
                'behavior':'loop both', 
                'color_choices':'7'
            },
            'water':{
                'animation':'███████▒▓▒', 
                'behavior':'random',
                'color_choices':([0x11 for i in range(50)] + list(range(0x11, 0x15)))
            },
            'writhe':{
                'animation':('╭╮╯╰╭╮╯╰'),
                'behavior':'random',
                'color_choices':'456'
            }
        }
        if preset:
            preset_kwargs = presets[preset]
            #calls init again using kwargs, but with preset set to None
            #to avoid infinite recursion.
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
        behavior_lookup = {
            'random':{'color':'random', 'tile':'random'},
            'loop color':{'color':'loop', 'tile':'random'},
            'loop tile':{'color':'random', 'tile':'loop'},
            'loop both':{'color':'loop', 'tile':'loop'},
            'walk color':{'color':'walk', 'tile':'random'},
            'walk frame':{'color':'random', 'tile':'walk'},
            'walk both':{'color':'walk', 'tile':'walk'},
        }

        current_behavior = behavior_lookup[self.behavior]
        #color behavior------------------------------------
        if current_behavior['color'] == 'random':
            color_choice = int(choice(self.color_choices))
        elif current_behavior['color'] == 'loop':
            color_choice = int(list(self.color_choices)[self.color_frame_number])
            self.color_frame_number = (self.color_frame_number + 1) % len(self.color_choices)
        elif current_behavior['color'] == 'walk':
            self.color_frame_number = (
                self.color_frame_number + randint(-1, 1)) % len(self.color_choices
            )
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
            background_choice = 0xe8 #background color.
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
    def __init__(
        self,
        name='generic_item',
        item_id=None,
        spawn_coord=(0, 0),
        uses=None,
        tile='?',
        current_location=None,
        usable_power=None,
        power_kwargs={}, 
        broken=False,
        use_message='You use the item.',
        broken_text=" is broken.",
        mutable=True,
        breakable=True,
        accepts_charges=False,
    ):
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
        self.breakable = breakable
        self.accepts_charges = accepts_charges

    async def use(self):
        if self.uses is not None and not self.broken:
            if self.use_message is not None:
                asyncio.ensure_future(append_to_log(message=self.use_message))
            asyncio.ensure_future(self.usable_power(**self.power_kwargs))
            if self.uses is not None and self.uses != -1:
                self.uses -= 1
            if self.uses <= 0 and self.breakable and self.uses != -1:
                self.broken = True
        elif self.broken:
            await append_to_log(
                message="The {}{}".format(self.name, self.broken_text)
            )
        else:
            await append_to_log(
                message="The {}{}".format(self.name, " is unbreakable!")
            )

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
    def __init__(
        self,
        name='mte',
        anchor_coord=(0, 0),
        preset='fireball', 
        blocking=False,
        fill_color=3,
        offset=(-1, -1),
        description="generic multi tile actor",
    ):
        self.name = name
        self.fill_color = fill_color
        self.member_data = {}
        self.member_names = []
        tiles = self.mte_presets(preset)
        preset_description = self.description_presets(preset)
        if preset_description is not None:
            description = preset_description
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
                self.add_segment(
                    segment_tile=segment_tile,
                    write_coord=write_coord,
                    offset=(x, y),
                    segment_name=segment_name,
                    blocking=blocking,
                    fill_color=fill_color,
                    description=description,
                )

    def mte_presets(self, preset):
        #Note: ' ' entries are ignored but keep the shape of the preset
        presets = {
            '2x2':(
                ('┏', '┓'),
                ('┗', '┛'),
            ),
            'empty':((' ')),
            'bold_2x2':(
                ('▛', '▜'),
                ('▙', '▟'),
            ),
            '2x2_block':(
                ('╔', '╗'),
                ('╚', '╝'),
            ),
            '2x2_block_thick':(
                ('▛', '▜'),
                ('▙', '▟'),
            ),
            '3x3_block':(
                ('╔', '╦', '╗'),
                ('╠', '╬', '╣'),
                ('╚', '╩', '╝'),
            ),
            '3x3':(
                ('┏', '━', '┓'),
                ('┃', ' ', '┃'),
                ('┗', ' ', '┛'),
            ),
            '3x3 fire':(
                ('┏', '━', '┓'),
                ('┃', 'E', '┃'),
                ('┗', '━', '┛'),
            ),
            'writheball':(
                (' ', 'W', 'W', ' '),
                ('W', 'W', 'W', 'W'),
                ('W', 'W', 'W', 'W'),
                (' ', 'W', 'W', ' '),
            ),
            'test_block':(
                ('X', 'X', 'X', 'X', 'X'),
                ('X', 'W', 'X', 'W', 'X'),
                ('X', 'X', 'X', 'X', 'X'),
                ('X', 'W', 'X', 'W', 'X'),
                ('X', 'X', 'X', 'X', 'X'),
            ),
            'fireball':(
                (' ', 'E', 'E', ' '),
                ('E', 'E', 'E', 'E'),
                ('E', 'E', 'E', 'E'),
                (' ', 'E', 'E', ' '),
            ),
            '4x4 tester':(
                ('1', '1', ' ', '3'),
                ('1', ' ', '3', '3'),
                (' ', '2', ' ', ' '),
                (' ', '2', ' ', '4'),
            ),
            '5x5 tester':(
                ('1', '1', ' ', '1', ' '),
                ('1', ' ', '1', '1', ' '),
                (' ', '1', ' ', ' ', '1'),
                ('1', ' ', '1', ' ', '1'),
                (' ', ' ', '1', '1', ' '),
            ),
           'ns_couch':(
                ('▛'),
                ('▌'),
                ('▙'),
            ),
           'ew_bookcase':(('▛'), ('▀'), ('▀'), ('▜'),),
           'add_sign':(
                (' ', '╻', ' '),
                ('╺', '╋', '╸'),
                (' ', '╹', ' '),
            ),
        }
        return presets[preset]

    def description_presets(self, preset):
        presets = {
            '2x2':'???',
            'empty':'Nothing\'s here!',
            'bold_2x2':'???',
            '2x2_block':'A large wooden crate. It looks fragile.',
            '2x2_block_thick':'A large crate heavily banded in metal.',
            '3x3_block':'???',
            '3x3':'???',
            '3x3 fire':'???',
            'writheball':'???',
            'test_block':'???',
            'fireball':'???',
            '4x4 tester':'???',
            '5x5 tester':'???',
            'ns_couch':'???',
            'ew_bookcase':'???',
            'add_sign':'???',
        }
        if preset not in presets:
            return None
        return presets[preset]

    def add_segment(
        self,
        segment_tile='?',
        write_coord=(0, 0),
        offset=(0, 0), 
        segment_name='test',
        literal_name=True,
        animation_preset=None,
        blocking=False,
        fill_color=8,
        moveable=True,
        breakable=True,
        description='mte_segment'
    ):
        animation_key = {'E':'explosion', 'W':'writhe'}
        self.member_data[offset] = {
            'tile':segment_tile, 
            'write_coord':write_coord,
            'offset':offset,
            'name':segment_name,
            'blocking':blocking
        }
        if segment_tile in animation_key:
            animation_preset=animation_key[segment_tile]
        else:
            animation_preset=None
        written_tile = term.color(fill_color)(segment_tile)
        member_name = spawn_static_actor(
            base_name=segment_name, 
            tile=written_tile,
            spawn_coord=write_coord, 
            animation_preset=animation_preset,
            multi_tile_parent=self.name,
            blocking=blocking,
            moveable=moveable,
            literal_name=True,
            breakable=breakable,
            description=description
        )
        self.member_names.append(segment_name)
        return segment_name

    def check_collision(self, move_by=(0, 0)):
        """
        Checks whether all of the member actors can fit into a new configuration
        """
        coord_to_dir = {(0, -1):'n', (1, 0):'e', (0, 1):'s', (-1, 0):'w'}
        check_position = {}
        for member_name in self.member_names:
            if not actor_dict[member_name].moveable:
                return False
            current_coord = actor_dict[member_name].coords()
            check_coord = add_coords(current_coord, move_by)
            if 'player' in map_dict[check_coord].actors:
                return True
            elif len(map_dict[check_coord].items) != 0:
                return False
            elif not map_dict[check_coord].passable:
                return False
            for actor in map_dict[check_coord].actors:
                if actor not in self.member_names:
                    return False
        return True

    def move(self, move_by=(3, 3)):
        for member_name in self.member_names:
            current_coord = actor_dict[member_name].coords()
            next_coord = add_coords(current_coord, move_by)
            actor_dict[member_name].update(coord=next_coord)

    def find_connected(
        self, root_node=None, traveled=None, depth=0, exclusions=set()
    ):
        """
        does a recursive search through the parts of an mte, starting at a
        given root node and returning the connected (adjacent without gaps)
        cells.

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
        segment_keys = {
            key for key in self.member_data if key not in traveled
        }
        if exclusions is not set():
            segment_keys -= exclusions
        if segment_keys == set():
            return set()
        if root_node is None:
            root_node = next(iter(segment_keys))
        traveled.add(root_node)
        possible_paths = {
            add_coords(neighbor_dir, root_node)
            for neighbor_dir in neighbor_dirs
        }
        walkable = set(segment_keys) & set(possible_paths) #intersection
        traveled |= walkable #union
        if walkable == set(): #is empty set
            return {root_node} #i.e. {(0, 0)}
        for direction in walkable:
            child_path = self.find_connected(
                root_node=direction, traveled=traveled, depth=depth + 1
            )
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
        if debug:
            for number, region in enumerate(regions):
                for cell in region:
                    actor_name = self.member_data[cell]['name']
                    if hasattr(actor_dict[actor_name], 'tile'):
                        tile_repr = term.color(number + 1)(str(number + 1))
                        actor_dict[actor_name].tile = tile_repr
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
            mte_dict[new_mte_name] = Multi_tile_entity(
                name=new_mte_name, preset='empty'
            )
            for segment in region:
                segment_data = self.member_data[segment]
                if debug:
                    color_string = term.color(number)(str(number))
                    new_tile = term.on_color(number + 3 % 8)(color_string)
                else:
                    new_tile = segment_data['tile']
                current_location = actor_dict[segment_data['name']].coords()
                mte_dict[new_mte_name].add_segment(
                    segment_tile=new_tile,
                    write_coord=current_location,
                    offset=segment_data['offset'],
                    segment_name='{}_{}'.format(segment_data['name'], number),
                    blocking=segment_data['blocking'],
                    literal_name=True, animation_preset=None
                )
        for member_name in self.member_names:
            del map_dict[actor_dict[member_name].coords()].actors[member_name]
        del mte_dict[self.name]
        return

async def spawn_mte(
    base_name='mte', 
    spawn_coord=(0, 0), 
    preset='3x3_block',
    blocking=True,
    fill_color=3,
):
    mte_id = generate_id(base_name=base_name)
    mte_dict[mte_id] = Multi_tile_entity(
        name=mte_id,
        anchor_coord=spawn_coord,
        preset=preset,
        blocking=blocking,
        fill_color=fill_color,
    )
    return mte_id

def multi_push(push_dir='e', pushed_actor=None, mte_parent=None):
    """
    pushes a multi_tile entity.
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
    start_point = actor_dict[actor_name].coords(),
    end_point = add_coords(
        start_point,
        point_given_angle_and_radius(angle=rand_angle, radius=rand_radius)
    )
    if map_dict[end_point].passable:
        actor_dict[actor_name].update(coord=end_point)

async def drag_actor_along_line(
    actor_name='player', line=None, linger_time=.02
):
    """
    Takes a list of coordinates as input.

    Moves an actor along the given points pausing along each step for
    linger_time seconds.
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

def brightness_test(print_coord=(110, 32)):
    """
    prints out a test pattern of possible colors
    """
    term_width, term_height = term.width, term.height
    print_coord = (term.width - 3 * 17) + 2, (term.height - 18)
    output = []
    for i in range(16 * 17):
        output.append(term.color(i)('{0:0{1}X}█'.format(i, 2)))
        if i % 16 == 0 and i != 0:
            offset_coord = add_coords(print_coord, (0, i // 16))
            with term.location(*offset_coord):
                print(''.join(output))
            output = []

#Global state setup-------------------------------------------------------------
term = Terminal()
brightness_vals = [(i, '█') for i in range(0xe8, 0xff)][::-1]
map_dict = defaultdict(lambda: Map_tile(passable=False, blocking=True))
mte_dict = {}
room_centers = set()
actor_dict = defaultdict(lambda: [None])
state_dict = defaultdict(lambda: None)
item_dict = defaultdict(lambda: None)
actor_dict['player'] = Actor(
    coord=(2, 2), name='player', tile='@', tile_color=6, health=100,
)
actor_dict['player'].update((23, 0))

#Drawing functions--------------------------------------------------------------
def tile_preset(preset='floor'):
    presets = {
        'floor':Map_tile(
            tile='░', 
            blocking=False,
            passable=True,
            description='A smooth patch of stone floor.',
            magic=True,
            is_animated=False,
            animation=None
        ),
        'wall':Map_tile(
            tile='𝄛',
            blocking=False,
            passable=True,
            description='A rough stone wall.',
            magic=True,
            is_animated=False,
            animation=None
        )
    }
    return presets[preset]

def paint_preset(tile_coords=(0, 0), preset='floor'):
    """
    Applies a preset to an existing map tile.

    Each attribute is individually set so that actors and items are preserved.
    """
    presets = {
        'floor':Map_tile(
            tile='░',
            blocking=False,
            passable=True,
            description='A smooth patch of stone floor.',
            magic=False,
            is_animated=False,
            animation=None,
        ),
        'rough floor':Map_tile(
            tile='░',
            blocking=False,
            passable=True,
            description='A roughly hewn stone floor.',
            magic=False,
            is_animated=False,
            animation=None,
            brightness_mod=(-1, 1)
        ),
        'wall':Map_tile(
            tile='𝄛',
            blocking=False,
            passable=True,
            description='A rough stone wall.',
            magic=False,
            is_animated=False,
            animation=None
        ),
        'noise':Map_tile(
            tile='.',
            blocking=False,
            passable=True,
            description='A shimmering insubstantial surface.',
            magic=False,
            is_animated=True, 
            animation=Animation(preset='noise')
        ),
        'chasm':Map_tile(
            tile=' ',
            blocking=False,
            passable=False,
            description='A gaping void',
            magic=False,
            is_animated=False
        ),
        'tiles':Map_tile(
            tile='▞',
            blocking=False,
            passable=True,
            color_num=7,
            description='Shiny linoleum floor in a checkerboard pattern.',
            magic=False,
            is_animated=False
        ),
        'nightmare':Map_tile(
            tile=' ',
            blocking=False,
            passable=True,
            color_num=0x34,
            description='It hurts your eyes to focus on.',
            magic=False,
            is_animated=True,
            animation=Animation(preset='nightmare')
        ),
        'pulse':Map_tile(
            tile='0',
            blocking=False,
            passable=True,
            description='',
            magic=False,
            is_animated=True,
            animation=Animation(preset='pulse')
        ),
        'goo':Map_tile(
            tile='.',
            blocking=False,
            passable=True,
            #color_num=0x39,
            description='A shimmering and roiling purple goo.',
            magic=False,
            is_animated=True,
            animation=Animation(preset='goo')
        ),
        'grass':Map_tile(
            tile='▒',
            blocking=False,
            passable=True,
            description='Soft knee-high grass. It nods gently in the breeze.',
            magic=False,
            is_animated=True, 
            animation=Animation(preset='grass')
        ),
        'water':Map_tile(
            tile='█',
            blocking=False,
            passable=True,
            description='A pool of water.',
            magic=False,
            is_animated=True, 
            animation=Animation(preset='water'),
            prevent_pushing=True,
        ),
        'error':Map_tile(
            tile='?',
            blocking=False,
            passable=True,
            description='ERROR',
            magic=False,
            is_animated=False
        ),
        'terminal':Map_tile(
            tile='▤',
            blocking=True,
            passable=False,
            description='A flickering monitor.',
            magic=False,
            is_animated=True,
            animation=Animation(preset='terminal')
        ),
    }
    map_dict[tile_coords].passable = presets[preset].passable
    map_dict[tile_coords].tile = presets[preset].tile
    map_dict[tile_coords].blocking = presets[preset].blocking 
    map_dict[tile_coords].description = presets[preset].description
    if presets[preset].brightness_mod:
        rand_offset = rand_float(*presets[preset].brightness_mod)
        map_dict[tile_coords].brightness_mod += rand_offset
    if presets[preset].is_animated:
        map_dict[tile_coords].is_animated = presets[preset].is_animated
        map_dict[tile_coords].animation = Animation(preset=preset)
    else:
        map_dict[tile_coords].is_animated = False

def rand_float(min_val, max_val, round_places=2):
    return round((random() * (max_val - min_val)) + min_val, round_places)

def draw_box(
    top_left=(0, 0),
    x_size=1,
    y_size=1,
    filled=True,
    tile='.',
    passable=True,
    preset='floor',
):
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

def draw_centered_box(
    middle_coord=(0, 0),
    x_size=10,
    y_size=10, 
    filled=True,
    preset="floor",
    passable=True
):
    top_left = (middle_coord[0] - x_size//2, middle_coord[1] - y_size//2)
    draw_box(
        top_left=top_left,
        x_size=x_size,
        y_size=y_size,
        filled=filled, 
        preset=preset
    )

def draw_line(
    coord_a=(0, 0),
    coord_b=(5, 5),
    preset='floor',
):
    """
    draws a line to the map_dict connecting coord_a to coord_b
    composed of the given preset.
    """
    points = get_line(coord_a, coord_b)
    for point in points:
        paint_preset(tile_coords=point, preset=preset)
        #map_dict[point].passable = passable
        #map_dict[point].blocking = blocking

def draw_secret_passage(
    coord_a=(-28, -14),
    coord_b=(-23, -14),
    preset='floor'
):
    points = get_line(coord_a, coord_b)
    for point in points[1:-1]:
        paint_preset(tile_coords=point, preset=preset)
    for point in (points[0], points[-1]):
        secret_door(door_coord=point)

def halfway_point(point_a=(0, 0), point_b=(10, 10)):
    """
    returns the point halfway between two points.
    """
    x_diff = point_b[0] - point_a[0]
    y_diff = point_b[1] - point_a[1]
    return add_coords(point_a, (x_diff//2, y_diff//2))

def find_centroid(points=((0, 0), (2, 2), (-1, -1)), rounded=True):
    """
    finds the centroid of any given number of points provided, rounded to the
    nearest whole x and y valued tile.
    """
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
        distance_from_center = abs(
            point_to_point_distance(point, center)
        )
        if distance_from_center <= radius:
            break
    return point

def check_point_within_arc(
    checked_point=(-5, 5), facing_angle=None, arc_width=90, center=None
):
    """
    checks whether a point falls within an arc sighted from another point.
    """
    if facing_angle is None:
        facing_angle = dir_to_angle(state_dict['facing'], mirror_ns=True)
        center = actor_dict['player'].coords()
    elif center is None:
        center = (0, 0)
    half_arc = arc_width / 2
    twelve_reference = (center[0], center[1] - 5)
    arc_range = (
        (facing_angle - half_arc) % 360,
        (facing_angle + half_arc) % 360
    )
    found_angle = round(
        find_angle(p0=twelve_reference, p1=center, p2=checked_point)
    )
    if checked_point[0] < center[0]:
        found_angle = 360 - found_angle
    result = angle_in_arc(
        given_angle=found_angle,
        arc_begin=arc_range[0], 
        arc_end=arc_range[1]
    )
    return result

def angle_in_arc(given_angle, arc_begin=45, arc_end=135):
    if arc_end < arc_begin and given_angle < arc_begin:
        arc_end += 360
        given_angle += 360
    elif arc_end < arc_begin and given_angle > arc_begin:
        arc_end += 360
    result = arc_begin < given_angle < arc_end
    return result

def points_around_point(
    radius=5,
    radius_spread=2,
    middle_point=(0, 0),
    in_cone=(0, 90),
    num_points=5
):
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
        points.append(
            point_given_angle_and_radius(
                angle=rand_angle, radius=rand_radius
            )
        )
    return points

def get_points_along_line(
    start_point=(0, 0), end_point=(10, 10), num_points=5
):
    """
    Writes a jagged passage between two points of a variable number of segments
    to map_dict.

    Uses np.linspace, np.astype and .tolist()
    """
    x_value_range = (start_point[0], end_point[0])
    y_value_range = (start_point[1], end_point[1])
    x_values = linspace(*x_value_range, num=num_points).astype(int)
    y_values = linspace(*y_value_range, num=num_points).astype(int)
    points = list(zip(x_values.tolist(), y_values.tolist()))
    return points

def carve_jagged_passage(
    start_point=(0, 0), 
    end_point=(10, 10), 
    num_points=5, 
    jitter=5, 
    width=3,
    preset='floor'
):
    points = get_points_along_line(
        num_points=num_points,
        start_point=start_point,
        end_point=end_point,
    )
    points = add_jitter_to_middle(points=points, jitter=jitter)
    multi_segment_passage(points, width=3, preset=preset)

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

def multi_segment_passage(
    points=None, 
    preset='floor', 
    width=3, 
    passable=True, 
    blocking=False
):
    coord_pairs = chained_pairs(pairs=points)
    for coord_pair in coord_pairs:
        n_wide_passage(
            coord_a=coord_pair[0],
            coord_b=coord_pair[1],
            width=width,
            passable=passable,
            blocking=blocking,
            preset=preset
        )

def n_wide_passage(
    coord_a=(0, 0),
    coord_b=(5, 5),
    preset='floor',
    passable=True,
    blocking=False,
    width=3,
    fade_to_preset=None,
    fade_bracket=(.25, .75)
):
    total_distance = point_to_point_distance(coord_a, coord_b)
    origin = (0, 0)
    if width == 0:
        return
    offsets = (
        (x, y)
        for x in range(-width, width + 1) 
        for y in range(-width, width + 1)
    )
    trimmed_offsets = {
        offset
        for offset in offsets
        if point_to_point_distance(offset, origin) <= width / 2
    }
    points_to_write = set()
    for offset in trimmed_offsets:
        offset_coord_a = add_coords(coord_a, offset)
        offset_coord_b = add_coords(coord_b, offset)
        line_points = get_line(offset_coord_a, offset_coord_b)
        for point in line_points:
            points_to_write.add(point)
    for point in points_to_write:
        if fade_to_preset is not None:
            if prob_fade_point_to_point(
                start_point=coord_a, 
                end_point=coord_b, 
                active_point=point, 
                fade_bracket=fade_bracket
            ):
                write_preset = preset
            else:
                write_preset = fade_to_preset
            paint_preset(tile_coords=point, preset=write_preset)
        else:
            paint_preset(tile_coords=point, preset=preset)

def prob_fade_point_to_point(
    start_point=(0, 0), 
    end_point=(10, 10), 
    active_point=(5, 5),
    fade_bracket=(.25, .75)
):
    """
    start_point is the beginning of the random gradient

    end_point is the end

    active_point is the point being currently generated

    fade_bracket is the ratio through the distance between start_point and 
    end_point between which the starting preset tile is faded into the ending
    preset

    based on a fade_bracket of (.25, .75),
    0% to 25% of the way through the total line will be guaranteed to be True
    75% to 100% of the way through the total line will be guaranteed to be False
    the 25% to 75% window will become progressively more likely to False
    """
    fade_slope = 1 / (fade_bracket[1] - fade_bracket[0])
    fade_intercept = fade_slope * -fade_bracket[0]
    total_distance = point_to_point_distance(start_point, end_point)
    point_distance = point_to_point_distance(start_point, active_point)
    if total_distance == 0:
        return False
    fade_threshold = (
        ((point_distance / total_distance) * fade_slope) + fade_intercept
    )
    if fade_threshold < 0:
        return True
    elif fade_threshold > 1:
        return False
    if fade_threshold > random():
        return False
    else:
        return True

def arc_of_points(
    start_coords=(0, 0),
    starting_angle=0,
    segment_length=4,
    fixed_angle_increment=5,
    segments=10,
    random_shift=True,
    shift_choices=(-10, 10)
):
    last_point, last_angle = start_coords, starting_angle
    output_points = [start_coords]
    for _ in range(segment_length):
        coord_shift = point_given_angle_and_radius(
            angle=last_angle, 
            radius=segment_length
        )
        next_point = add_coords(last_point, coord_shift)
        output_points.append(next_point)
        last_point = next_point
        if random_shift:
            last_angle += choice(shift_choices)
        else:
            last_angle += fixed_angle_increment
    return output_points, last_angle

def chain_of_arcs(
    start_coords=(0, 0),
    num_arcs=20,
    starting_angle=90, 
    width=(2, 20),
    draw_mode='even',
    preset='floor'
):
    """
    chain of arcs creates a chain of curved passages of optionally variable width.

    if width is given as a single number, width is fixed.
    if width is given as a 2-length tuple, width is a random number

    draw_mode controls the width of the passage
    """
    arc_start = start_coords
    if draw_mode == 'even': #same passage length throughout
        segment_widths = [width[0]] * num_arcs
    elif draw_mode == 'random': #passage width is random
        segment_widths = [randint(*width) for _ in range(num_arcs)]
    elif draw_mode == 'taper': #passage starts at width[0], ends at width[1]
        segment_widths = linspace(*width, num=num_arcs).astype(int)
    for segment_width in segment_widths:
        rand_segment_angle = choice((-20, -10, 10, 20))
        points, starting_angle = arc_of_points(
            starting_angle=starting_angle, 
            fixed_angle_increment=rand_segment_angle,
            start_coords=arc_start,
            random_shift=False
        )
        for point in points:
            map_dict[point].tile = term.red('X')
        arc_start = points[-1] #set the start point of the next passage.
        multi_segment_passage(points=points, width=segment_width, preset=preset)

def cave_room(
    trim_radius=40,
    width=100,
    height=100, 
    iterations=20,
    debug=False, 
    kernel=True,
    kernel_offset=(0, 0),
    kernel_radius=3
):
    """
    Generates a smooth cave-like series of rooms within a given radius
    and around a given starting point.
    """
    neighbors = [
        (x, y)
        for x in (-1, 0, 1)
        for y in (-1, 0, 1)
    ]
    #get kernel cells:
    #the kernel is a round open space in the middle of the room.
    if kernel:
        middle_coord = (width // 2, height // 2)
        kernel_base_coord = add_coords(kernel_offset, middle_coord)
        kernel_cells = {
            coord:'#' for coord in 
            get_circle(
                center=kernel_base_coord, 
                radius=kernel_radius
            )
        }
    #initialize the room:
    input_space = {
        (x, y):choice(['#', ' ']) 
        for x in range(width) 
        for y in range(height)
    }
    if trim_radius:
        input_space = trim_outside_circle(
            input_dict=input_space,
            width=width,
            height=height,
            trim_radius=trim_radius
        )
    adjacency = {(x, y):0 for x in range(width) for y in range(height)}
    check_coords = [(x, y) for x in range(width) for y in range(height)]
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

def trim_outside_circle(
    input_dict={}, width=20, height=20, trim_radius=8, outside_radius_char=' ',
):
    center_coord = width // 2, height // 2
    for coord in input_dict:
        distance_from_center = point_to_point_distance(coord, center_coord)
        if distance_from_center >= trim_radius:
            input_dict[coord] = outside_radius_char
    return input_dict

def write_room_to_map(
    room={}, top_left_coord=(0, 0), space_char=' ', hash_char='#'
):
    """
    Writes a dictionary representation of a region of space into the map_dict.
    """
    for coord, value in room.items():
        #print(coord, '" "'.format(value))
        write_coord = add_coords(coord, top_left_coord)
        if value == space_char:
            continue
        if value == hash_char:
            map_dict[write_coord].passable = True
            map_dict[write_coord].blocking = False
            map_dict[write_coord].tile = '░'

def draw_circle(
    center_coord=(0, 0),
    radius=5,
    animation=None,
    preset='floor',
    border_thickness=0,
    border_preset='chasm',
    annulus_radius=None,
    chance_skip=0,
):
    """
    draws a filled circle onto map_dict.
    """
    x_bounds = center_coord[0] - radius, center_coord[0] + radius
    y_bounds = center_coord[1] - radius, center_coord[1] + radius
    points = get_circle(center=center_coord, radius=radius)
    if annulus_radius:
        annulus_points = get_circle(center=center_coord, radius=annulus_radius)
        points = list(set(points) - set(annulus_points))
    for point in points:
        if not map_dict[point].mutable:
            continue
        if random() < chance_skip:
            continue
        distance_to_center = point_to_point_distance(center_coord, point)
        if distance_to_center <= radius:
            paint_preset(tile_coords=point, preset=preset)
    if border_thickness > 0:
        radius = radius + border_thickness
        boundary_circle = get_circle( radius=radius, center=center_coord)
        for point in set(boundary_circle) - set(points):
            if random() < chance_skip:
                continue
            paint_preset(tile_coords=point, preset=border_preset)

#Actions------------------------------------------------------------------------
async def toggle_scanner_state(batt_use=1):
    if state_dict['scanner_state'] == True:
        state_dict['scanner_state'] = False
        await append_to_log(message='You turn off the scanner.')
    else:
        state_dict['scanner_state'] = True
        await append_to_log(message='You turn on the scanner.')
    while (state_dict['scanner_state'] == True):
        await asyncio.sleep(1)

async def timed_scanner_use(duration=5):
    await append_to_log(message="The scanner flickers on.")
    state_dict['scanner_state'] = True
    await asyncio.sleep(5)
    state_dict['scanner_state'] = False
    await append_to_log(message="The scanner fades to black.")

async def throw_item(
    thrown_item_id=False,
    source_actor='player', 
    direction=None, 
    throw_distance=13, 
    rand_drift=2
):
    """
    Moves item from player's inventory to another tile at distance 
    throw_distance
    """
    if direction is None:
        direction = state_dict['facing']
    direction_tuple = dir_to_offset(state_dict['facing'])
    if not thrown_item_id:
        thrown_item_id = await choose_item()
    if thrown_item_id == None:
        await append_to_log(message='Nothing to throw!')
        return False
    del actor_dict['player'].holding_items[thrown_item_id]
    starting_point = actor_dict[source_actor].coords()
    throw_vector = scaled_dir_offset(
        dir_string=direction, scale_by=throw_distance
    )
    destination = add_coords(starting_point, throw_vector)
    if rand_drift:
        drift = randint(0, rand_drift), randint(0, rand_drift)
        destination = add_coords(destination, drift)
    if not hasattr(item_dict[thrown_item_id], 'tile'):
        return False
    line_of_sight_result = await check_line_of_sight(starting_point, destination)
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
    throw_text = 'throwing {}.'.format(item_dict[thrown_item_id].name)
    await append_to_log(message=throw_text)
    await travel_along_line(
        name='thrown_item_id',
        start_coords=starting_point, 
        end_coords=destination,
        speed=.05,
        tile=item_tile, 
        animation=None,
        debris=None
    )
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

async def explosion_effect(
    center_coord=(0, 0),
    radius=6,
    damage=75,
    particle_count=25,
    destroys_terrain=True
):
    await radial_fountain(
        tile_anchor=center,
        anchor_actor='player', 
        frequency=.001,
        radius=(radius, radius + 3),
        speed=(1, 2), 
        collapse=False,
        debris='`.,\'',
        deathclock=particle_count,
        animation=Animation(preset='explosion')
    )
    if destroys_terrain:
        #TODO: fix so this doesn't "destroy" voids and things that don't make sense
        area_of_effect = get_circle(center=center, radius=radius)
        draw_circle(center_coord=center, radius=radius)
    if damage:
        #TODO: change damage based on distance from center?
        await damage_within_circle(center=center, radius=radius, damage=damage)

async def thrown_action(
    thrown_item_id=None,
    source_actor='player', 
    direction=None,
    throw_distance=13,
    rand_drift=2, 
    fuse_length=3, #set to -1 for no fuse
    single_use_item=True,
    action_preset='dynamite',
    radius=6,
    damage=75,
    particle_count=25,
):
    await throw_item(
        thrown_item_id=thrown_item_id,
        source_actor=source_actor,
        direction=direction,
        throw_distance=throw_distance, 
        rand_drift=rand_drift
    )
    presets={
        'dynamite':{
            'called_function':'explosion_effect',
            'kwargs':{
                'radius':6,
                'damage':75,
                'particle_count':25,
            }
        }
    }
    called_function = presets[action_preset]['called_function']
    function_kwargs = presets[action_preset]['kwargs']
    item_location = item_dict[thrown_item_id].current_location
    if fuse_length > 0:
        await display_fuse(fuse_length=fuse_length, item_id=thrown_item_id)
    if single_use_item and thrown_item_id in map_dict[item_location].items:
        del map_dict[item_location].items[thrown_item_id]
        del item_dict[thrown_item_id]
    await called_function(
        center_coord=item_location,
        **function_kwargs,
    )

async def damage_all_actors_at_coord(
    coord=(0, 0), damage=10, source_actor=None, quiet=True
):
    actor_list = [actor for actor in map_dict[coord].actors.items()]
    for actor in actor_list:
        if actor[0] == 'player' and source_actor is not None:
            if not quiet:
                damage_message = "{} damage from {}!".format(damage, source_actor)
                asyncio.ensure_future(
                    append_to_log(message=damage_message)
                )
            asyncio.ensure_future(
                directional_alert(source_actor=source_actor)
            )
        await damage_actor(actor=actor[0], damage=damage, display_above=False)

async def damage_within_circle(
    center=(0, 0), 
    radius=6, 
    damage=75,
    inverse_square_damage=False,
):
    area_of_effect = get_circle(center=center, radius=radius)
    for coord in area_of_effect:
        dist_from_center = point_to_point_distance(center, coord)
        if inverse_square_damage: 
            damage = round(1 / (dist_from_center ** 2))
        await damage_all_actors_at_coord(coord=coord, damage=damage)

async def damage_actor(
    actor=None,
    damage=10,
    display_above=True,
    leaves_body=False,
    blood=False,
    material='wood'
):
    debris_dict = {'wood':('SMASH!', ',.\''),
                   'stone':('SMASH!', '..:o')}
    if actor_dict[actor].breakable == False:
        return
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
        root_coord = actor_dict[actor].coords()
        asyncio.ensure_future(
            sow_texture(
                root_coord,
                palette=palette,
                radius=3,
                seeds=6, 
                passable=True,
                stamp=True,
                paint=False,
                color_num=8,
                description='Broken {}.'.format(material),
                pause_between=.06
            )
        )
        await kill_actor(name_key=actor, blood=blood, leaves_body=leaves_body)

async def damage_numbers(actor=None, damage=10, squares_above=5):
    if not hasattr(actor_dict[actor], 'coords'):
        return
    actor_coords = actor_dict[actor].coords()
    digit_to_superscript = {
        '1':'¹', '2':'²', '3':'³', '4':'⁴', '5':'⁵',
        '6':'⁶', '7':'⁷', '8':'⁸', '9':'⁹', '0':'⁰',
        '-':'⁻', '+':'⁺'
    }
    if damage >= 0:
        damage = '-' + str(damage)
    else:
        damage = '+' + str(damage)[1:]
    for x_pos, digit in enumerate(damage):
        start_coords = actor_coords[0] + (x_pos - 1), actor_coords[1] - 1
        end_coords = start_coords[0], start_coords[1] - squares_above
        if damage[0] == '-':
            tile = term.red(digit_to_superscript[digit])
        else:
            tile = term.green(digit_to_superscript[digit])
        asyncio.ensure_future(
            travel_along_line(
                tile=tile,
                speed=.12,
                start_coords=start_coords, 
                end_coords=end_coords,
                debris=False,
                animation=False
            )
        )

async def unlock_door(actor_key='player', opens='red'):
    directions = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
    check_dir = state_dict['facing']
    actor_coord = actor_dict[actor_key].coords()
    door_coord = add_coords(actor_coord, directions[check_dir])
    door_type = map_dict[door_coord].door_type
    if opens in map_dict[door_coord].door_type and map_dict[door_coord].is_door:
        if map_dict[door_coord].locked:
            output_text = 'You unlock the {} door.'.format(opens)
            map_dict[door_coord].locked = False
        elif not map_dict[door_coord].locked:
            output_text = 'You lock the {} door.'.format(opens)
            map_dict[door_coord].locked = True
    elif not map_dict[door_coord].is_door:
        output_text = "That isn't a door."
    else:
        output_text = "Your {} key doesn't fit the {} door.".format(opens, door_type)
    await append_to_log(message=output_text)

def is_passable(checked_coords=(0, 0)):
    """
        returns True if the square is passable and there are no actors in it.
    """
    has_no_actors = True
    for actor_name in map_dict[checked_coords].actors:
        if actor_dict[actor_name].solid:
            has_no_actors = False
            break
    if has_no_actors and map_dict[checked_coords].passable:
        return True
    else:
        return False

def push(direction='n', pusher='player', base_coord=None):
    """
    objects do not clip into other objects or other actors.

    returns True if object is pushed.
    """
    dir_coords = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0)}
    chosen_dir = dir_coords[direction]
    if base_coord is None:
        pusher_coords = actor_dict[pusher].coords()
    else:
        pusher_coords = base_coord
    destination_coords = add_coords(pusher_coords, chosen_dir)
    has_actors = bool(map_dict[destination_coords].actors)
    not_viable_space = bool(map_dict[destination_coords].prevent_pushing)
    if not has_actors or not_viable_space:
        return False
    pushed_name = next(iter(map_dict[destination_coords].actors))
    mte_parent = actor_dict[pushed_name].multi_tile_parent
    if mte_parent is not None:
        multi_push(push_dir=direction, mte_parent=mte_parent)
        return True
    elif not actor_dict[pushed_name].moveable:
        return False
    else:
        pushed_coord = actor_dict[pushed_name].coords()
        pushed_destination = add_coords(pushed_coord, chosen_dir)
        if is_passable(pushed_destination):
            if len(map_dict[pushed_coord].items) > 0:
                return False
            actor_dict[pushed_name].update(coord=pushed_destination)
            return True
        else:
            return False

async def bay_door(
    hinge_coord=(3, 3),
    patch_to_key='bay_door_0', 
    orientation='n',
    segments=5,
    blocking=True, 
    color_num=6,
    preset='thin',
    debug=False,
    message_preset=None
):
    """
    Instantiates an MTE that moves to one side when a pressure plate 
    (or other trigger) is activated.
    hinge_coord is the location of the "doorframe", where the door 
    disappears into.
    orientation is the direction that the door will propagate from hinge_coord
    A bay_door with 'n' orientation and segments 5, hinging on (0, 0) will have
    door segments at coords, (0, -1), (0, -2), (0, -3), (0, -4) and (0, -5)

    [ ]TODO: account for crushing damage if the actor can be destroyed,
    [ ]TODO: stop closing of door (i.e. jammed with a crate or tentacle) 
          if actor cannot be crushed (destroyed?)
    """
    if type(state_dict[patch_to_key]) != dict:
        state_dict[patch_to_key] = {}
    if orientation in ('n', 's'):
        style_dir = 'ns'
    elif orientation in ('e', 'w'):
        style_dir = 'ew'
    door_style = {
        'secret':{'ns':'𝄛', 'ew':'𝄛'},
        'thick':{'ns':'┃', 'ew':'━'},
        'thin':{'ns':'│', 'ew':'─'},
        'test_a':{'ns':'n', 'ew':'e'},
        'test_b':{'ns':'s', 'ew':'w'},
    }
    message_presets = { 'ksh':['*kssshhhhh*'] * 2 }
    door_description_presets = {
            'secret':'A rough stone wall',
            'thick':'A thick steel door',
            'thin':'A door of stainless steel.',
            'test_a':'THIS IS A TEST (a)',
            'test_b':'THIS IS A TEST (b)',
    }
    door_segment_tile = door_style[preset][style_dir]
    if debug:
        print(preset, style_dir, door_segment_tile)
    door = await spawn_mte(
        base_name=patch_to_key, spawn_coord=hinge_coord, preset='empty'
    )
    segment_names = []
    door_id = generate_id(base_name=patch_to_key)
    for segment_num in range(segments):
        offset = scaled_dir_offset(
            dir_string=orientation, scale_by=(1 + segment_num)
        )
        spawn_coord = add_coords(hinge_coord, offset)
        segment_name = '{}_{}'.format(door_id, segment_num)
        segment_names.append((segment_name, spawn_coord))
        mte_dict[door].add_segment(
            write_coord=spawn_coord,
            segment_tile=door_segment_tile,
            offset=offset,
            segment_name=segment_name,
            moveable=False,
            blocking=blocking, 
            breakable=False,
            description=door_description_presets[preset]
        )
    last_spawn_coord = spawn_coord
    door_message = None
    if message_preset is not None and message_preset in message_presets: 
        door_message = message_presets[message_preset]
    door_state = None
    while True:
        player_coords = actor_dict['player'].coords()
        dist_from_player = point_to_point_distance(hinge_coord, player_coords)
        #go into standby mode if too distant:
        if dist_from_player > 30:
            await asyncio.sleep(1)
            continue
        await asyncio.sleep(.1)
        for segment in segment_names:
            if segment_name[0] not in actor_dict:
                continue
        if await any_true(trigger_key=patch_to_key):
            if door_state is not 'open':
                door_state = 'open'
                if door_message is not None:
                    asyncio.ensure_future(
                        sound_message(
                            output_text=door_message[0], 
                            sound_origin_coord=last_spawn_coord,
                            source_actor=None,
                            point_radius=18,
                            fade_duration=1,
                        )
                    )
                    await append_to_log(message=door_message[0])
            for segment in reversed(segment_names):
                await asyncio.sleep(.1)
                actor_dict[segment[0]].update((9999, 9999)) #move to nowhere
        else:
            if door_state is not 'close':
                door_state = 'close'
                if door_message is not None:
                    asyncio.ensure_future(
                        sound_message(
                            output_text=door_message[0], 
                            sound_origin_coord=last_spawn_coord,
                            source_actor=None,
                            point_radius=18,
                            fade_duration=1,
                        )
                    )
                    await append_to_log(message=door_message[1])
            for segment in segment_names:
                await asyncio.sleep(.1)
                #if there's an actor in the square we're about to update, push
                #if it's not pushable, jam here, enter check for not jammed loop
                #if it's pushable and the pushed-to space is either a wall or another bay door,
                #deal a whole bunch of damage to the jammed actor
                check_space = segment[1]
                check_push_space = add_coords(dir_to_offset(orientation), segment[1])
                segment_name = segment[0]
                push_return = push(direction=orientation, base_coord=segment[1])
                passable = is_passable(checked_coords=check_space)
                if not passable:
                    break
                else:
                    actor_dict[segment[0]].update(segment[1])

async def bay_door_pair(
    hinge_a_coord,
    hinge_b_coord,
    patch_to_key='bay_door_pair_1',
    preset='thin',
    pressure_plate_coord=None,
    message_preset=None
):
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
            span = hinge_a_coord[1] - hinge_b_coord[1] - 1
            a_segments = span // 2
            b_segments = span - a_segments
        else:
            hinge_a_dir, hinge_b_dir = 's', 'n'
            span = hinge_b_coord[1] - hinge_a_coord[1] - 1
            a_segments = span // 2
            b_segments = span - a_segments
    else:
        return
    if type(state_dict[patch_to_key]) != dict:
        state_dict[patch_to_key] = {}
    if pressure_plate_coord is not None:
        if type(pressure_plate_coord[0]) == tuple:
            for pair in pressure_plate_coord:
                asyncio.ensure_future(
                    pressure_plate(
                        spawn_coord=pair, 
                        patch_to_key=patch_to_key,
                    )
                )
        else:
            asyncio.ensure_future(
                pressure_plate(
                    spawn_coord=pressure_plate_coord,
                    patch_to_key=patch_to_key,
                )
            )
    asyncio.ensure_future(
        bay_door(
            hinge_coord=hinge_a_coord,
            patch_to_key=patch_to_key,
            orientation=hinge_a_dir,
            segments=a_segments,
            preset=preset,
            message_preset=message_preset
        )
    ) 
    asyncio.ensure_future(
        bay_door(
            hinge_coord=hinge_b_coord,
            patch_to_key=patch_to_key,
            orientation=hinge_b_dir,
            segments=b_segments,
            preset=preset,
            message_preset=None #one door is silent to prevent message repeats
        )
    )

async def follower_actor(
    name='follower',
    refresh_speed=.01,
    parent_actor='player', 
    offset=(-1, -1),
    alive=True,
    tile=' '
):
    await asyncio.sleep(refresh_speed)
    follower_id = generate_id(base_name=name)
    actor_dict[follower_id] = Actor(name=follower_id, tile=tile)
    while alive:
        await asyncio.sleep(refresh_speed)
        parent_coords = actor_dict[parent_actor].coords()
        follow_x, follow_y = (
            parent_coords[0] + offset[0], parent_coords[1] + offset[1]
        )
        actor_dict[follower_id].update(coord=(follow_x, follow_y))

async def circle_of_darkness(
    start_coords=(0, 0), name='darkness', circle_size=4
):
    actor_id = generate_id(base_name=name)
    loop = asyncio.get_event_loop()
    loop.create_task(
        basic_actor(
            coord=start_coords,
            speed=.5,
            movement_function=seek_actor, 
            tile=' ',
            name_key=actor_id,
            hurtful=True,
            is_animated=True,
            animation=Animation(preset='none')
        )
    )
    range_tuple = (-circle_size, circle_size + 1)
    for x in range(*range_tuple):
        for y in range(*range_tuple):
            distance_to_center = point_to_point_distance((0, 0), (x, y))
            if distance_to_center <= circle_size:
                loop.create_task(
                    follower_actor(
                        parent_actor=actor_id, 
                        offset=(x, y)
                    )
                )
                #shadow in nightmare space
                loop.create_task(
                    follower_actor(
                        tile=term.on_white(' '), 
                        parent_actor=actor_id, 
                        offset=(1000 + x, 1000 + y)
                    )
                )
            else:
                pass
    loop.create_task(
        radial_fountain(
            anchor_actor=actor_id,
            animation=Animation(preset='sparse noise')
        )
    )

async def multi_spike_trap(
    base_name='multitrap',
    base_coord=(10, 10), 
    nodes=[(i, -5, 's') for i in range(-5, 6)],
    damage=75,
    length=7,
    rate=.25,
    speed=.1,
    retract_speed=.1,
    patch_to_key='switch_1',
    mid_trap_delay_time=.1
):
    """
    pressure plate is centered, nodes are arrayed in offsets around
    the pressure plate. all nodes trigger at once when pressure plate is
    activated.
    """
    loop = asyncio.get_event_loop()
    state_dict[patch_to_key] = {}
    loop.create_task(
        pressure_plate(
            spawn_coord=base_coord,
            patch_to_key=patch_to_key
        )
    )
    node_data = []
    for number, node in enumerate(nodes):
        node_coord = add_coords(node, base_coord)
        node_name = '{}_{}'.format(base_name, str(number))
        node_data.append((node_name, node[2]))
        actor_dict[node_name] = Actor(
            name=node_name, 
            moveable=False, 
            tile='◘', 
            tile_color=0,
            description="You notice a hole in this section of wall."
        )
        actor_dict[node_name].update(coord=node_coord)
        map_dict[node_coord].tile = '◘'
    while True:
        await asyncio.sleep(rate)
        if await any_true(trigger_key=patch_to_key):
            for node in node_data:
                if random() < .1:
                    asyncio.ensure_future(
                        sound_message(
                            output_text=choice(('*tic*', '*ssshk*', '*ckrkrr*', '*shnng*')),
                            sound_origin_coord=actor_dict[node[0]].coords(),
                            source_actor=None,
                            point_radius=18,
                            fade_duration=1,
                        )
                    )
                asyncio.ensure_future(
                    start_delay_wrapper(
                        start_delay=random(), 
                        delay_func=sword, 
                        direction=node[1], 
                        actor=node[0], 
                        length=length, 
                        damage=damage, 
                        sword_color=7, 
                        speed=speed, 
                        retract_speed=retract_speed, 
                        player_sword_track=False
                    )
                )

async def spike_trap(
    base_name='spike_trap',
    coord=(10, 10), 
    direction='n',
    damage=20,
    reach=5,
    rate=.25, 
    speed=.1,
    patch_to_key='switch_1',
    trap_type='sword',
):
    """
    Generate a stationary, actor that periodically puts out spikes in each
    direction given at rate spike_rate.
    """
    trap_origin_id = generate_id(base_name=base_name)
    actor_dict[trap_origin_id] = Actor(
        name=trap_origin_id, moveable=False, tile='◘', tile_color='grey'
    )
    actor_dict[trap_origin_id].update(coord=coord)
    while True:
        await asyncio.sleep(rate)
        if await any_true(trigger_key=patch_to_key):
            if trap_type == sword:
                asyncio.ensure_future(
                    sword(
                        direction=direction,
                        actor=trap_origin_id,
                        length=reach, 
                        damage=damage,
                        sword_color=7,
                        speed=speed,
                        player_sword_track=False
                    )
                )
            elif trap_type == 'flame':
                asyncio.ensure_future(
                    flame_jet(
                        origin=(-27, 17),
                        duration=2, 
                        facing='e',
                        reach=reach
                    )
                )

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
    filename = '{}.txt'.format('exported_map')
    if os.path.exists(filename): 
        os.remove(filename)
    player_location = actor_dict['player'].coords()
    x_spread = (
        -width // 2 + player_location[0], width // 2 + player_location[0]
    )
    y_spread = (
        -height // 2 + player_location[1], height // 2 + player_location[1]
    )
    with open(filename, 'a') as map_file:
        for y_pos, y in enumerate(range(*y_spread)):
            with term.location(60, y_pos):
                row_output = ''.join(
                    [map_dict[i, y].tile for i in range(*x_spread)]
                )
                line_output = '{}\n'.format(row_output)
                map_file.write(line_output)
    with term.location(80, 0):
        await append_to_log(message='Wrote nearby map to {}.'.format(filename))
    #return the tile to its original state:
    map_dict[actor_dict['player'].coords()].tile = temp_tile

async def display_current_tile(x_offset=105, y_offset=5):
    while True:
        await asyncio.sleep(.01)
        current_coords = add_coords((-1, 0), actor_dict['player'].coords())
        current_tile = map_dict[current_coords].tile
        with term.location(x_offset, y_offset):
            print('view_tile_count: {}'.format(state_dict['view_tile_count']))
        state_dict['view_tile_count'] = 0
        with term.location(x_offset, y_offset + 1):
            print('current tile: {}'.format(current_tile))
        tile_color = map_dict[current_coords].color_num
        with term.location(x_offset, y_offset + 2):
            print('tile_color: {}'.format(tile_color))
        with term.location(x_offset, y_offset + 3):
            print(
                'tile w/ color: {}'.format(
                    term.color(tile_color)(current_tile)
                )
            )
        with term.location(x_offset, y_offset + 4):
            print('repr() of tile:')
        with term.location(x_offset, y_offset + 5):
            print('{}        '.format(repr(current_tile)))
        actors = [key for key in map_dict[current_coords].actors.keys()]
        with term.location(x_offset, y_offset + 6):
            print('actors here: {}        #'.format(actors))
        actors_len = len(map_dict[current_coords].actors.keys())
        with term.location(x_offset, y_offset + 7):
            print('actors_len: {}'.format(actors_len))
        if len(actors) > 1:
            await asyncio.sleep(1)

#TODO: proximity_trigger: trigger when actors are within say, 5 tiles
#TODO: line_trigger: test all the tiles in a straight line 
    #(triggers any time the line is crossed)
    #have the option of a semi-visible laser
#TODO: an item to emit a cloud, lasers only show up in clouds
#TODO: clouds limit distance of view?
#TODO: an actor that only shows up 1% of the time its tile is polled

async def proximity_trigger(
    coord_a=(0, 0),
    coord_b=(0, 5),
    patch_to_key="proximity_1",
    test_rate=.1,
    visible=False,
):
    if type(state_dict[patch_to_key]) != dict:
        state_dict[patch_to_key] = {}
    points = get_line(coord_a, coord_b)[1:-1] #trim off the head and the tail
    for point in points:
        asyncio.ensure_future(
            pressure_plate(
                tile='░',
                spawn_coord=point,
                patch_to_key=patch_to_key,
                off_delay=0, 
                test_rate=.1,
                positives=('player'),
                sound_choice=None,
                brightness_mod=(0, 0),
            )
        )

async def computer_terminal(
    tile='▣',
    spawn_coord=(0, 0),
    patch_to_key='term_1',
    message=('Door is now', ('locked', 'unlocked'))
):
    """
    a terminal that toggles the state of a state_dict value
    "green keycard required"
    """
    paint_preset(tile_coords=spawn_coord, preset='terminal')
    append_description(
        coord=spawn_coord, 
        added_message='The monitor reads:\"OPEN POD DOOR?\"',
        separator='||',
    )
    neighbors = adjacent_tiles(coord=spawn_coord)
    toggle_id = bool_toggle(patch_to_key=patch_to_key)
    map_dict[spawn_coord].use_action_func = toggle_bool_toggle
    map_dict[spawn_coord].use_action_kwargs = {
        'patch_to_key':patch_to_key, 
        'toggle_id':toggle_id,
        'message':message,
    }
    while True:
        await asyncio.sleep(.1 + random() / 5)
        rand_offset = randint(-5, 0)
        for tile in neighbors:
            map_dict[tile].brightness_mod = rand_offset

async def teleport_if_open(
    tile_coords=(0, 0), 
    destination_coords=(20, 20),
    open_index=0,
    player_facing_end='s',
    use_message="You climb down the ladder",
    use_offset=(1000, 1000, -1),
    bypass_state=False
):
    if map_dict[tile_coords].toggle_state_index == open_index or bypass_state:
        actor_list = list(map_dict[tile_coords].actors)
        for actor in actor_list:
            if not actor_dict[actor].moveable:
                continue
            actor_name = actor_dict[actor].name
            actor_dict[actor].update(destination_coords)
            if actor_name == "player":
                state_dict['facing'] = player_facing_end
                asyncio.ensure_future(append_to_log(message=use_message))
                if use_offset:
                    state_dict["display_offset"] = use_offset

async def hatch_pair(
    origin=(15, -1),
    destination=None, #origin is copied if no destination is given
    origin_z=0,       #where the hatch is spawned
    destination_z=-1, #where the ladder is spawned
    #offset to an empty square next to the hatch
    origin_landing_offset=(0, 1), 
    #offset to an empty square next to the bottom of the ladder:
    destination_landing_offset=(0, 1), 
    origin_display_offset=(0, 0), #change if going from a non standard floor
    tile_shift_offset=(1000, 1000),
    start_end_dir='s', #the direction faced when teleported to the origin
    dest_end_dir='s', #the direction faced when teleported to the destination
):
    if destination is None:
        destination = origin
    hatch_coords = origin
    ladder_coords = add_coords(destination, tile_shift_offset)
    hatch_landing_coords = add_coords(origin, origin_landing_offset)
    ladder_landing_coords = add_coords(ladder_coords, destination_landing_offset)
    hatch_use_offset = (*invert_coords(tile_shift_offset), destination_z)
    ladder_use_offset = (*invert_coords(origin_display_offset), origin_z)
    #hatch:
    asyncio.ensure_future(
        teleporting_hatch(
            hatch_coords=hatch_coords,
            destination_coords=ladder_landing_coords,
            use_offset=hatch_use_offset,
            ladder=False,
            player_facing_end=start_end_dir,
        )
    )
    #ladder:
    asyncio.ensure_future(
        teleporting_hatch(
            hatch_coords=ladder_coords,
            destination_coords=hatch_landing_coords,
            use_offset=ladder_use_offset,
            ladder=True,
            player_facing_end=dest_end_dir,
        )
    )

async def teleporting_hatch(
    hatch_coords=(27, 1),
    destination_coords=(19, 0),
    use_offset=(0, 0, 0),
    ladder=False,
    player_facing_end='s',
):
    if ladder:
        spawn_column(
            spawn_coord=(hatch_coords), tile='╪', solid_base=False, name='ladder',
        )
        use_message="You climb up the ladder"
        bypass_state=True
    else:
        draw_door(door_coord=hatch_coords, preset='hatch')
        use_message="You climb down the ladder"
        bypass_state=False
    map_dict[hatch_coords].run_on_entry = teleport_if_open
    map_dict[hatch_coords].run_on_entry_kwargs = {
        'tile_coords':hatch_coords,
        'destination_coords':destination_coords,
        'use_message':use_message,
        'use_offset':use_offset,
        'bypass_state':bypass_state,
        'player_facing_end':player_facing_end,
    }

async def teleporter(
    tile='X',
    spawn_coord=(1, 1),
    destination_coords=(1, -9),
    description="What happens if you step on it?"
):
    paint_preset(tile_coords=spawn_coord, preset='pulse')
    map_dict[spawn_coord].description = description
    map_dict[spawn_coord].run_on_entry = teleport
    map_dict[spawn_coord].run_on_entry_kwargs = {
        'origin':spawn_coord,
        'destination':destination_coords,
        'delay':0,
    }

async def indicator_lamp(
    tiles=('◉','◉'), #○
    tile_colors=(0x01, 0x22),
    spawn_coord=(0, 0), 
    patch_to_key='indicator_lamp', 
    refresh_rate=.1
):
    false_tile = term.color(tile_colors[0])(tiles[0])
    true_tile = term.color(tile_colors[1])(tiles[1])
    map_dict[spawn_coord].tile = term.color(tile_colors[0])(tiles[0])
    current_tile = tiles[0]
    while True:
        await asyncio.sleep(refresh_rate)
        if await any_true(trigger_key=patch_to_key):
            set_tile = true_tile
        else:
            set_tile = false_tile
        if set_tile != current_tile:
            map_dict[spawn_coord].tile = set_tile
            current_tile = set_tile

async def alarm_bell(
    tiles=('○','◉'),
    tile_colors=(0x00, 0x01),
    spawn_coord=(0, 0), 
    patch_to_key='alarm_bell', 
    refresh_rate=.1,
    time_between_alarms=2,
    fade_duration=1,
    message="ALERT!|INTRUDER!", #split on pipe character
    tile_descriptions=(
        "An inert alarm module.", 
        "The alarm emits a deafening siren."
    ),
    silent=False,
):
    if type(state_dict[patch_to_key]) is not dict:
        state_dict[patch_to_key] = {}
    map_dict[spawn_coord].tile = term.color(tile_colors[0])(tiles[0])
    map_dict[spawn_coord].description = tile_descriptions[0]
    tile_index = 0
    alarm_timing_index = 0
    alarm_trigger_num = round(time_between_alarms / refresh_rate)
    alert_index = 0
    latch = False
    message_words = message.split("|")
    while True:
        await asyncio.sleep(refresh_rate)
        alarm_timing_index = (alarm_timing_index + 1) % alarm_trigger_num
        alarm_on = alarm_timing_index % alarm_trigger_num
        alarm_triggered = await any_true(trigger_key=patch_to_key)
        if alarm_triggered and alarm_on:
            if latch == False and not silent:
                asyncio.ensure_future(append_to_log(message="You trigger an alarm!"))
            latch = True
            map_dict[spawn_coord].description = tile_descriptions[1]
            await sound_message(
                output_text="{}".format(message_words[alert_index]),
                sound_origin_coord=spawn_coord,
                point_radius=18,
                fade_duration=fade_duration,
            )
            alert_index = (alert_index + 1) % len(message_words)
            tile_index = (tile_index + 1) % (len(tiles))
            map_dict[spawn_coord].tile = term.color(tile_colors[tile_index])(tiles[tile_index])
        else:
            latch = False
            alert_index = 0
            map_dict[spawn_coord].tile = term.color(tile_colors[0])(tiles[0])
            map_dict[spawn_coord].description = tile_descriptions[0]

async def toggle_bool_toggle(
    patch_to_key,
    toggle_id,
    message=('toggled_object is now', ('falsey', 'truthy')),
    delay=1,
):
    toggle_state = state_dict[patch_to_key][toggle_id]
    false_text = "{} {}.".format(message[0], message[1][0])
    true_text =  "{} {}.".format(message[0], message[1][1])
    if toggle_state == True:
        state_dict[patch_to_key][toggle_id] = False
        output_text = false_text
    else:
        state_dict[patch_to_key][toggle_id] = True
        output_text = true_text
    asyncio.ensure_future(append_to_log(message=output_text))
    await asyncio.sleep(delay)

def bool_toggle(
    patch_to_key='door_1', 
    toggle_id_base_name='toggle', 
    toggle_message="Door {}",
    starting_state=False,
):
    """
    Sets up a new passive toggle at state_dict[patch_to_key][toggle_id]

    Returns toggle_id for use in whatever it's used by.
    """
    toggle_id = generate_id(base_name=toggle_id_base_name)
    if type(state_dict[patch_to_key]) is not dict:
        state_dict[patch_to_key] = {}
    state_dict[patch_to_key][toggle_id] = starting_state
    return toggle_id

async def pressure_plate(
    tile='░',
    spawn_coord=(4, 0), 
    patch_to_key='switch_1',
    off_delay=.5, 
    test_rate=.1,
    positives=None,
    sound_choice='default',
    brightness_mod=(3, -5),
):
    """
    creates a pressure plate on the map at specified spawn_coord.

    If positives is a list (instead of None), it will only accept things
    with names containing one of the specified colors/attributes. 
    Otherwise, it will be a list of generic objects that tend to trigger
    pressure plates.
    """
    map_dict[spawn_coord].tile = tile
    plate_id = generate_id(base_name='pressure_plate')
    state_dict[patch_to_key][plate_id] = False
    exclusions = ('sword', 'particle')
    sound_effects = {'default':'*click*'}
    if positives is None:
        positives = ('player', 'box', 'weight', 'crate', 'static')
    triggered = False
    while True:
        await asyncio.sleep(test_rate)
        positive_result = await check_actors_on_tile(
            coords=spawn_coord, positives=positives
        )
        if positive_result:
            if not triggered and sound_choice is not None:
                await append_to_log(message=sound_effects[sound_choice])
            triggered = True
            map_dict[spawn_coord].brightness_mod = brightness_mod[1]
            state_dict[patch_to_key][plate_id] = True
            if off_delay:
                await asyncio.sleep(off_delay)
        else:
            triggered = False
            state_dict[patch_to_key][plate_id] = False
            map_dict[spawn_coord].brightness_mod = brightness_mod[0]

async def puzzle_pair(
    block_coord=(-10, -10),
    plate_coord=(-10, -7),
    puzzle_name='puzzle_0', 
    block_description='A heavy block.|||A thin outline of a star is inscribed into the top face.',
    plate_description='The floor here is carved with a star.|||It sits slightly above the nearby tiles.',
    color_num=3,
    block_char='☐'
):
    """
    creates a paired pressure plate and uniquely keyed block.
    pressure plate triggers only with the paired block
    """
    state_dict[puzzle_name] = {}
    block_tile = term.color(color_num)(block_char)
    asyncio.ensure_future(
        spawn_weight(
            base_name=puzzle_name, 
            spawn_coord=block_coord, 
            tile=block_tile,
            description=block_description,
        )
    )
    map_dict[plate_coord].description = plate_description
    asyncio.ensure_future(
        pressure_plate(
            tile='▣',
            spawn_coord=plate_coord, 
            positives=(puzzle_name, 'null'), #positives needs to be a tuple
            patch_to_key=puzzle_name
        )
    )
    return puzzle_name
            
async def any_true(trigger_key):
    return any(i for i in state_dict[trigger_key].values())

async def state_toggle(
    sequence=(0, 1), time_between_triggers=1, trigger_key='test', channel=1
):
    looping_values = cycle(sequence)
    state_dict[trigger_key] = {channel:1}
    while True:
        state_dict[trigger_key][channel] = next(looping_values)
        map_dict[9, 9].tile = str(state_dict[trigger_key][channel])[0]
        await asyncio.sleep(time_between_triggers)

async def trigger_door(
    patch_to_key='switch_1',
    door_coord=(0, 0),
    default_state='closed',
    invert=False,
    open_index=0,
    closed_index=1,
):
    draw_door(door_coord=door_coord, preset='iron', locked=True)
    if default_state == 'closed':
        set_state = closed_index
    while True:
        await asyncio.sleep(.25)
        trigger_state = await any_true(trigger_key=patch_to_key)
        if invert:
            trigger_state = not trigger_state
        if trigger_state:
            set_state = open_index
        else:
            set_state = closed_index
        set_tile_toggle_state(door_coord, set_state)

async def start_delay_wrapper(start_delay=1, delay_func=None, **kwargs):
    await asyncio.sleep(start_delay)
    asyncio.ensure_future(delay_func(**kwargs))

async def swing(
    swing_direction='n', 
    base_coord=(0, 0), 
    base_actor=None, 
    set_facing=True, 
    base_name='swing',
    rand_direction=False,
    swing_color=0xf9,
    damage=50,
):
    #TODO: fix swing entities so they don't invisibly cut tiles
    if base_actor:
        base_coord = actor_dict[base_actor].coords()
    if set_facing:
        swing_direction = state_dict['facing']
    num_to_dir = {
        1:'n',
        2:'ne',
        3:'e',
        4:'se',
        5:'s',
        6:'sw',
        7:'w',
        8:'nw',
    }
    swing_chars = {
        'n': (['╲', '|', '╱'], ['nw', 'n', 'ne']),
        'e': (['╱', '─', '╲'], ['ne', 'e', 'se']),
        's': (['╲', '|', '╱'], ['se', 's', 'sw']),
        'w': (['╱', '─', '╲'], ['sw', 'w', 'nw']),
    }
    chars, dirs = swing_chars[swing_direction]
    #choose at random the direction the arc starts:
    if rand_direction: 
        if random() > .5:
            chars.reverse()
            dirs.reverse()
    #add swing actor to starting tile
    swing_id = generate_id(base_name=base_name)
    actor_dict[swing_id] = Actor(
        name=swing_id,
        moveable=False,
        tile=chars[0],
        tile_color=swing_color
    )
    for swing_char, print_direction in zip(chars, dirs):
        offset = dir_to_offset(print_direction)
        print_coord = add_coords(base_coord, offset)
        actor_dict[swing_id].tile = term.on_color(0xea)(swing_char)
        actor_dict[swing_id].update(print_coord)
        await damage_all_actors_at_coord(
            coord=print_coord, damage=damage, source_actor='player'
        )
        await asyncio.sleep(.15)
    #remove sword from map_dict:
    del map_dict[print_coord].actors[swing_id]
    del actor_dict[swing_id]

async def sword(
    direction='n',
    actor='player',
    length=5,
    name='sword', 
    speed=.1,
    retract_speed=.1,
    damage=100,
    sword_color=1,
    player_sword_track=True,
    mode='retract',
    delay_out=0,
    thick=False,
):
    """
    extends and retracts a line of characters

    mode controls the behavior of the cleanup:
    retract: 
        creates: 1, 2, 3, 4, 5 
        then ...
        removes 5, 4, 3, 2, 1

    spear: (used by 'blaster' item)
        creates: 1, 2, 3, 4, 5, ..., n
        then ...
        removes: 1, 2, 3, 4, 5, ..., n
    """
    if thick:
        ns_tile = '┃'
        ew_tile = '━'
    else:
        ns_tile = '│'
        ew_tile = '─'
    dir_coords = {
        'n':(0, -1, ns_tile),
        'e':(1, 0, ew_tile),
        's':(0, 1, ns_tile),
        'w':(-1, 0, ew_tile)
    }
    if player_sword_track:
        if 'player_busy' in state_dict and state_dict['player_busy'] == True:
            return False
        state_dict['player_busy'] = True
    starting_coords = actor_dict[actor].coords()
    chosen_dir = dir_coords[direction]
    sword_id = generate_id(base_name=name)
    sword_segment_names = [
        '{}_{}_{}'.format(name, sword_id, segment) for segment in range(1, length)
    ]
    segment_coords = [
        (
            starting_coords[0] + chosen_dir[0] * i,
            starting_coords[1] + chosen_dir[1] * i
        ) 
        for i in range(1, length)
    ]
    temp_output = []
    for coord in segment_coords:
        if map_dict[coord].blocking:
            #trim everything past the first blocking tile:
            segment_coords = segment_coords[:segment_coords.index(coord) + 1]
            break
    to_damage_names = []
    player_coords = actor_dict['player'].coords()
    #zip works here because it only zips up to the end of the shorter iterable:
    for segment_coord, segment_name in zip(segment_coords, sword_segment_names):
        actor_dict[segment_name] = Actor(
            name=segment_name,
            moveable=False,
            tile=chosen_dir[2],
            tile_color=sword_color
        )
        map_dict[segment_coord].actors[segment_name] = True
        await damage_all_actors_at_coord(
            coord=segment_coord, damage=damage, source_actor='player'
        )
        await asyncio.sleep(speed)
    await asyncio.sleep(delay_out)
    if mode == 'retract':
        #zip isn't reversible, weird nonsense is needed:
        retract_order = reversed(list(zip(segment_coords, sword_segment_names)))
    elif mode == 'spear':
        retract_order = zip(segment_coords, sword_segment_names)
    else:
        retract_speed = 0
        retract_order = zip(segment_coords, sword_segment_names)
    for segment_coord, segment_name in retract_order:
        if segment_name in map_dict[segment_coord].actors: 
            del map_dict[segment_coord].actors[segment_name]
        del actor_dict[segment_name]
        await asyncio.sleep(retract_speed)
    if player_sword_track:
        state_dict['player_busy'] = False

async def sword_item_ability(
    length=3,
    speed=.05,
    retract_speed=.05,
    damage=20,
    sword_color=1,
    mode='retract',
    player_sword_track=True,
    delay_out=0,
    thick=False,
):
    facing_dir = state_dict['facing']
    asyncio.ensure_future(
        sword(
            direction=facing_dir, 
            length=length, 
            speed=speed, 
            retract_speed=retract_speed,
            damage=damage, 
            sword_color=sword_color,
            mode=mode,
            player_sword_track=player_sword_track,
            delay_out=delay_out,
            thick=thick,
        )
    )

async def dash_ability(dash_length=20, direction=None, time_between_steps=.03):
    if direction is None:
        direction = state_dict['facing']
    asyncio.ensure_future(
        dash_along_direction(
            distance=dash_length, direction=direction, 
            time_between_steps=time_between_steps
        )
    )

async def teleport_in_direction(direction=None, distance=15, flashy=True):
    if direction is None:
        direction = state_dict['facing']
    directions_to_offsets = {
        'n':(0, -distance), 'e':(distance, 0), 
        's':(0, distance), 'w':(-distance, 0),
    }
    player_coords = actor_dict['player'].coords()
    destination_offset = directions_to_offsets[direction]
    destination = add_coords(player_coords, destination_offset)
    if flashy:
        await teleport(destination=destination)

async def teleport(
    origin=(0, 0),
    destination=(0, 0),
    #actor='player',
    actor=None,
    delay=.25,
    x_offset=1000,
    y_offset=1000,
    start_message="You feel slightly disoriented.",
    flashy=False
):
    """
    does a flash animation of drawing in particles then teleports the player
        to a given location.
    uses radial_fountain in collapse mode for the effect
    upon arrival, a random nova of particles is released (also using 
        radial_fountain but in reverse
    """
    await asyncio.sleep(delay)
    if map_dict[destination].passable:
        asyncio.ensure_future(append_to_log(message=start_message))
        if flashy:
            asyncio.ensure_future(
                pass_between(x_offset, y_offset, plane_name='nightmare')
            )
            await asyncio.sleep(3)
            dest_coords = add_coords(destination, (x_offset, y_offset))
            await pass_between(*dest_coords, plane_name='nightmare')
        if actor is None:
            actor = next(iter(map_dict[origin].actors))
        actor_dict[actor].update(coord=(destination))
    else:
        await append_to_log(message='Something is in the way.')
    
async def random_blink(actor='player', radius=20):
    current_location = actor_dict[actor].coords()
    await asyncio.sleep(.2)
    while True:
        await asyncio.sleep(.01)
        rand_x = randint(-radius, radius) + current_location[0]
        rand_y = randint(-radius, radius) + current_location[1]
        blink_to = (rand_x, rand_y)
        distance = point_to_point_distance(blink_to, current_location)
        if distance > radius:
            continue
        line_of_sight_result = await check_line_of_sight(current_location, blink_to)
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

async def temporary_block(
    duration=30,
    animation_preset='energy block',
    vanish_message=None,
):
    directions = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
    facing_dir_offset = directions[state_dict['facing']]
    actor_coords = actor_dict['player'].coords()
    spawn_coord = add_coords(actor_coords, facing_dir_offset)
    block_id = generate_id(base_name='weight')
    asyncio.ensure_future(
        timed_actor(
            death_clock=duration,
            name=block_id,
            coords=spawn_coord,
            rand_delay=0,
            solid=False,
            moveable=True, 
            animation_preset=animation_preset,
            vanish_message=vanish_message,
        )
    )

async def temp_view_circle(
    duration=10, 
    radius=15, 
    center_coord=(0, 0), 
    on_actor=None, 
    instant=True,
    wipe_after=True,
):
    """
    carves out a temporary zone of the map that can be viewed regardless
    of whether it's through a wall or behind the player's fov arc.
    """
    if on_actor is not None:
        center_coord = player_coords = actor_dict[on_actor].coords()
    temp_circle = get_circle(center=center_coord, radius=radius)
    shuffle(temp_circle)
    state_dict['lock view'] = True
    for coord in temp_circle:
        if not instant:
            await asyncio.sleep(.01)
        map_dict[coord].override_view = True
    await asyncio.sleep(duration)
    shuffle(temp_circle)
    for coord in temp_circle:
        if not instant:
            await asyncio.sleep(.01)
        map_dict[coord].override_view = False
        if wipe_after:
            map_dict[coord].seen = False
    state_dict['lock view'] = False

#Item interaction---------------------------------------------------------------

#TODO: create a weight that can be picked up and stored in one's inventory.
#TODO: an item that when thrown, temporarily creates a circle of overridden_view == True
#TODO: fix override_view to display a noisy (with brightness offsets) view instead of uniform single tone
#TODO: items that are used immediately upon pickup

def spawn_item_at_coords(coord=(2, 3), instance_of='block wand', on_actor_id=False):
    wand_broken_text = ' is out of charges.'
    possible_items = (
        'wand', 'nut', 'fused charge', 'shield wand', 'red potion',
        'shiny stone', 'shift amulet', 'red sword', 'vine wand',
        'eye trinket', 'dynamite', 'red key', 'green key', 
        'rusty key', 'looking glass'
    )
    block_wand_text = 'A shimmering block appears!'
    if instance_of == 'random':
        instance_of = choice(possible_items)
    item_id = generate_id(base_name=instance_of)
    item_catalog = {
        'block wand':{
            'uses':10,
            'tile':term.blue('/'),
            'usable_power':temporary_block,
            'power_kwargs':{'duration':30, 'vanish_message':'*POP!*'},
            'use_message':block_wand_text,
            'broken_text':' is out of charges',
        },
        #TODO: add stackable items in inventory
        'battery':{
            'uses':-1,
            'tile':term.green('◈'), 
            'power_kwargs':{
                'item_id':item_id,
                'num_charges':3,
            },
            'usable_power':battery_item,
            'use_message':None,
        },
        #TODO: add a cooldown bar next to item display.
        'blaster':{
            'uses':6,
            'tile':term.red('τ'),
            'usable_power':sword_item_ability,
            'use_message':None,
            'broken_text':' is out of charges',
            'accepts_charges':True,
            'power_kwargs':{
                'speed':0,
                'retract_speed':0,
                'mode':'spear', 
                'damage':100,
                'length':20,
                'mode':'spear',
                'player_sword_track':False,
                'delay_out':.5,
                'thick':True,
            }
        },
        'nut':{
            'uses':-1,
            'tile':term.red('⏣'),
            'usable_power':throw_item, 
            'power_kwargs':{'thrown_item_id':item_id}
        },
        'scanner':{
            'uses':5,
            'tile':term.green('𝄮'), 
            'usable_power':timed_scanner_use,
            'accepts_charges':True,
            'use_message':None,
            'breakable':False,
            'power_kwargs':{'duration':5}
        },
        'fused charge':{
            'uses':-1,
            'tile':term.green('⏣'),
            'usable_power':thrown_action, 
            'power_kwargs':{'thrown_item_id':item_id, 'radius':6}
        },
        'dynamite':{
            'uses':-1,
            'tile':term.red('\\'),
            'usable_power':thrown_action, 
            'power_kwargs':{
                'thrown_item_id':item_id,
                'throw_distance':1, 
                'radius':5,
                'damage':150,
                'fuse_length':9,
                'particle_count':30,
                'rand_drift':0
            }
        },
        'shield wand':{
            'uses':17,
            'tile':term.blue('/'),
            'power_kwargs':{'radius':6},
            'usable_power':spawn_bubble,
            'broken_text':wand_broken_text
        },
        'red potion':{
            'uses':1,
            'tile':term.red('◉'), 
            'power_kwargs':{
                'item_id':item_id,
                'total_restored':50,
            },
            'usable_power':health_potion,
            'broken_text':wand_broken_text,
            'use_message':"You drink the red potion.|||You feel healthy! (25 life restored)",
        },
        'shiny stone':{
            'uses':-1,
            'tile':term.blue('o'), 
            'power_kwargs':{'radius':5, 'track_actor':'player'}, 
            'usable_power':orbit,
            'broken_text':wand_broken_text
        },
        'shift amulet':{
            'uses':19,
            'tile':term.blue('O̧'),
            'power_kwargs':{
                'x_offset':1000,
                'y_offset':1000,
                'plane_name':'nightmare'
            },
            'usable_power':pass_between,
            'broken_text':'Something went wrong.'
        },
        'red sword':{
            'uses':-1,
            'tile':term.red('ļ'),
            'power_kwargs':{'length':9, 'speed':.1},
            'usable_power':sword_item_ability,
            'broken_text':'Something went wrong.',
            'use_message':None
        },
        'green sword':{
            'uses':-1,
            'tile':term.green('ļ'),
            'power_kwargs':{
                'length':9,
                'speed':.05,
                'damage':100,
                'sword_color':2,
                'player_sword_track':True,
            },
            'usable_power':sword_item_ability,
            'broken_text':'Something went wrong.',
            'use_message':None
        },
        'dash trinket':{
            'uses':19,
            'tile':term.blue('⥌'),
            'usable_power':dash_ability, 
            'power_kwargs':{'dash_length':20},
            'broken_text':wand_broken_text},
        'red key':{
            'uses':-1,
            'tile':term.red('⚷'),
            'usable_power':unlock_door, 
            'power_kwargs':{'opens':'red'},
            'broken_text':wand_broken_text,
            'use_message':''
        },
        'green key':{
            'uses':-1,
            'tile':term.green('⚷'),
            'usable_power':unlock_door, 
            'power_kwargs':{'opens':'green'},
            'broken_text':wand_broken_text,
            'use_message':None
        },
        'rusty key':{
            'uses':3,
            'tile':term.color(3)('⚷'),
            'usable_power':unlock_door, 
            'power_kwargs':{'opens':'rusty'},
            'broken_text':'the key breaks off in the lock',
            'use_message':None
        },
        'eye trinket':{
            'uses':-1,
            'tile':term.blue('⚭'),
            'usable_power':random_blink, 
            'power_kwargs':{'radius':50},
            'broken_text':wand_broken_text
        },
        'hop amulet':{
            'uses':-1,
            'tile':term.red('O̧'),
            'usable_power':teleport_in_direction, 
            'power_kwargs':{'distance':10},
            'broken_text':wand_broken_text
        },
        #TODO: passwall item: makes a section of wall shimmer like temporary
        #      blocks and passable for a short period of time. 
        #      kill all actors left when time expires.
        'looking glass':{
            'uses':-1,
            'use_message':"You see yourself outside of yourself.",
            'tile':term.color(0x06)('ϙ'),
            'usable_power':temp_view_circle, 
            'power_kwargs':{'on_actor':'player', 'radius':10, 'duration':3},
            'broken_text':wand_broken_text
        }
    }
    #item generation:
    if instance_of in item_catalog:
        item_dict[item_id] = Item(
            name=instance_of,
            item_id=item_id,
            spawn_coord=coord,
            **item_catalog[instance_of]
        )
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

def adjacent_passable_tiles(base_coord=(0, 0)):
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

async def display_items_at_coord(
    coord=actor_dict['player'].coords(),
    x_pos=2,
    y_pos=12
):
    item_list = ' '
    current_list_hash = 0
    last_list_hash = 0
    while True:
        await asyncio.sleep(.1)
        player_coords = actor_dict['player'].coords()
        
        item_list = [item for item in map_dict[player_coords].items]
        current_list_hash = hash(str(item_list))
        if current_list_hash != last_list_hash:
            clear_screen_region(
                x_size=20, y_size=10, screen_coord=(x_pos, y_pos + 1)
            )
        if current_list_hash != last_list_hash:
            if len(item_list) > 0:
                filter_text = 'Items here:'
            else:
                filter_text = '           '
            asyncio.ensure_future(
                filter_print(
                    output_text=filter_text, 
                    absolute_coord=(x_pos, y_pos),
                    wipe=False,
                )
            )
        if len(item_list) > 0:
            for number, item_id in enumerate(item_list):
                name_location = (x_pos + 2, (y_pos + 1) + number)
                icon_location = (x_pos, (y_pos + 1) + number)
                item_icon = item_dict[item_id].tile
                item_name = item_dict[item_id].name
                if current_list_hash != last_list_hash:
                    asyncio.ensure_future(
                        filter_print(
                            output_text = item_name,
                            absolute_coord = name_location,
                            wipe=False,
                        )
                    )
                with term.location(*icon_location):
                    print(item_icon)
        else:
            current_list_hash = 0
            with term.location(x_pos, y_pos):
                print('           ')
        last_list_hash = current_list_hash

async def display_items_on_actor(actor_key='player', x_pos=2, y_pos=24):
    item_list = ' '
    while True:
        await asyncio.sleep(.1)
        with term.location(x_pos, y_pos):
            print('Inventory:')
        clear_screen_region(x_size=19, y_size=10, screen_coord=(x_pos, y_pos+1))
        item_list = [item for item in actor_dict[actor_key].holding_items]
        for number, item_id in enumerate(item_list):
            if item_dict[item_id].uses >= 0:
                uses_text = '({})'.format(item_dict[item_id].uses)
            else:
                uses_text = ''
            with term.location(x_pos, (y_pos + 1) + number):
                print('{} {} {}'.format(item_dict[item_id].tile, item_dict[item_id].name, uses_text))

async def filter_print(
    output_text='filter_print default text',
    x_offset=0,
    y_offset=-8, 
    pause_fade_in=.01,
    pause_fade_out=.01,
    pause_stay_on=1, 
    delay=0,
    blocking=False,
    hold_for_lock=True,
    absolute_coord=None,
    wipe=True,
):
    if hold_for_lock:
        while True:
            if state_dict['printing'] == True:
                await asyncio.sleep(.1)
            else:
                break
    if x_offset == 0:
        x_offset = -int(len(output_text) / 2)
    middle_x, middle_y = (
        int(term.width / 2 - 2), int(term.height / 2 - 2),
    )
    if absolute_coord is None:
        y_location = term.height + y_offset
        x_location = middle_x + x_offset
    else:
        x_location, y_location = absolute_coord
    numbered_chars = [(place, char) for place, char in enumerate(output_text)]
    shuffle(numbered_chars)
    for char in numbered_chars:
        with term.location(char[0] + x_location, y_location):
            print(char[1])
        if not blocking:
            await asyncio.sleep(pause_fade_in)
    shuffle(numbered_chars)
    if wipe == False:
        return
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

async def filter_fill(
    top_left_coord=(30, 10),
    x_size=10,
    y_size=10, 
    pause_between_prints=.005,
    pause_stay_on=3, 
    fill_char=term.red('X'),
    random_order=True
):
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

def fill_screen_with_colors():
    for row in range(0, 48):
        for i in range(255):
            with term.location(i, row):
                print(term.on_color_rgb(
                    randint(0, 255), randint(0, 255), randint(0, 255)
                )(" "))

def print_debug_grid():
    """
    prints an overlay for finding positions of text
    """
    for y in range(term.height // 5):
        for x in range(term.width // 5):
            with term.location(x * 5, y * 5):
                print('┼')
            with term.location(x * 5, y * 5 + 1):
                print(' {0: >2}'.format(x * 5))
            with term.location(x * 5, y * 5 + 2):
                print(' {0: >2}'.format(y * 5))

def describe_region(top_left=(0, 0), x_size=5, y_size=5, text='testing...'):
    x_tuple = (top_left[0], top_left[0] + x_size)
    y_tuple = (top_left[1], top_left[1] + y_size)
    for x in range(*x_tuple):
        for y in range(*y_tuple):
            map_dict[(x, y)].description = text

def append_description(coord, added_message, separator="||"):
    map_dict[coord].description = "{}{}{}".format(
        map_dict[coord].description, 
        separator,
        added_message,
    )

def connect_with_passage(x1, y1, x2, y2, segments=2, tile='░'):
    """
    fills a straight path first then fills the shorter leg, 
    starting from the first coordinate
    """
    if segments == 2:
        if abs(x2-x1) > abs(y2-y1):
            for x_coord in range(x1, x2+1):
                paint_preset((x_coord, y1), preset=tile,)
            for y_coord in range(y1, y2+1):
                paint_preset((x2, y_coord), preset=tile,)
        else:
            for y_coord in range(y1, y2+1):
                paint_preset((x1, y_coord), preset=tile,)
            for x_coord in range(x1, x2+1):
                paint_preset((x_coord, y2), preset=tile,)

async def sow_texture(
    root_coord,
    palette=",.'\"`",
    radius=5,
    seeds=20, 
    passable=False,
    stamp=True,
    paint=True,
    color_num=1,
    description='',
    pause_between=.02,
    only_passable=True,
    append_description=True
):
    """ given a root node, picks random points within a radius length and writes
    characters from the given palette to their corresponding map_dict cell.
    """
    for i in range(seeds):
        await asyncio.sleep(pause_between)
        throw_dist = radius + 1
        while throw_dist >= radius:
            x_toss, y_toss = (
                randint(-radius, radius), randint(-radius, radius),
            )
            throw_dist = sqrt(x_toss**2 + y_toss**2) #distance
        toss_coord = add_coords(root_coord, (x_toss, y_toss))
        if only_passable and not map_dict[toss_coord].passable:
            continue
        if map_dict[toss_coord].mutable == False:
            continue
        if map_dict[toss_coord].magic == True:
            continue
        if paint:
            if map_dict[toss_coord].tile not in "▮▯": #ignore doors
                map_dict[toss_coord].color_num = 1
        else:
            random_tile = choice(palette)
            map_dict[toss_coord].color_num = color_num
        if not stamp:
            map_dict[toss_coord].passable = passable
        if description:
            current_description = map_dict[toss_coord].description
            if append_description and (description not in current_description):
                appended_description = '{} {}'.format(
                    current_description, description
                )
                map_dict[toss_coord].description = appended_description
            else:
                map_dict[toss_coord].description = description

def clear():
    """
    clears the screen.
    """
    # check and make call for specific operating system
    _ = call('clear' if os.name =='posix' else 'cls')

def secret_door(
    door_coord=(0, 0), 
    tile_description="The wall looks a little different here."
):
    draw_door(
        door_coord=door_coord,
        locked=False,
        preset='secret',
    )
    map_dict[door_coord].description = tile_description
    map_dict[door_coord].brightness_mod = 2

def secret_room(wall_coord=(0, 0), room_offset=(10, 0), square=True, size=5):
    room_center = add_coords(wall_coord, room_offset)
    n_wide_passage(coord_a=wall_coord, coord_b=room_center, width=1)
    secret_door(door_coord=wall_coord)
    announcement_at_coord("You found a secret room!", coord=room_center, )
    if square:
        draw_centered_box(
            middle_coord=room_center, x_size=size, y_size=size, preset="floor"
        )
    else:
        draw_circle(center_coord=room_center, radius=size)

def draw_door(
    door_coord=(0, 0),
    closed=True,
    locked=False,
    starting_toggle_index=1,
    #description='wooden',
    is_door=True,
    preset='wooden'
):
    """
    creates a door at the specified map_dict coordinate and sets the relevant
    attributes.
    """
    door_presets = {
        #((tile, blocking, passable), (tile, blocking, passable))
        'wooden':(('▯', False, True), ('▮', True, False)),
        'secret':(('▯', False, True), ('𝄛', True, False)),
        'hatch':(('◍', False, True), ('●', False, True)),
        'iron':(('▯', False, True), ('▮', True, False)),
    }
    door_colors = {
        'red':1, 'green':2, 'orange':3, 'wooden':3, 'rusty':3, 
        'blue':4, 'purple':5, 'cyan':6, 'grey':7, 'white':8,
        'iron':7, 'hatch':0xee,
    }
    map_dict[door_coord].toggle_states = door_presets[preset]
    map_dict[door_coord].toggle_state_index = starting_toggle_index
    tile, blocking, passable = door_presets[preset][starting_toggle_index]
    if preset != 'secret':
        door_tile = term.color(door_colors[preset])(tile)
    else:
        door_tile = tile
    map_dict[door_coord].tile = door_tile
    map_dict[door_coord].passable = passable
    map_dict[door_coord].blocking = blocking
    map_dict[door_coord].is_door = True
    map_dict[door_coord].locked = locked
    map_dict[door_coord].door_type = preset
    if closed:
        close_state = 'A closed'
    else:
        close_state = 'An open'
    door_description = "{} {}.".format(close_state, preset)
    map_dict[door_coord].description = door_description
    map_dict[door_coord].mutable = False

async def fake_stairs(
    coord_a=(8, 0),
    coord_b=(-10, 0), 
    hallway_offset=(-1000, -1000),
    hallway_length=15
):
    #draw hallway
    draw_box(
        top_left=hallway_offset, x_size=hallway_length, y_size=1, tile="░"
    )
    coord_a_hallway = add_coords(coord_a, hallway_offset)
    coord_b_hallway = add_coords(coord_a_hallway, (hallway_length, 0))
    #create magic doors:
    await create_magic_door_pair(
        door_a_coords=coord_a, door_b_coords=coord_a_hallway, silent=True
    )
    await create_magic_door_pair(
        door_a_coords=coord_b, door_b_coords=coord_b_hallway, silent=True
    )

async def under_passage(
    start=(-20, 27),
    end=(-20, 13),
    offset=(-1000, -1000), 
    width=1,
    direction='ns',
    length=10
):
    """
    Assumes parallel starting and ending directions.
    """
    under_start = add_coords(start, offset)
    end_offsets = {'ns':(0, length), 'ew':(length, 0)}
    under_end = add_coords(under_start, end_offsets[direction])
    n_wide_passage(coord_a=under_start, coord_b=under_end, width=width)
    await create_magic_door_pair(
        door_a_coords=start, door_b_coords=under_start, silent=True
    )
    await create_magic_door_pair(
        door_a_coords=end, door_b_coords=under_end, silent=True
    )

#TODO: create a mirror

async def magic_door(
    start_coords=(5, 5),
    end_coords=(-22, 18), 
    silent=False,
    destination_plane='normal',
    description = "The air shimmers slightly between you and the space beyond.",
    door_tile = "▯",
):
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
    animation = Animation(base_tile='▮', preset='door')
    map_dict[start_coords] = Map_tile(
        tile=" ",
        blocking=False,
        passable=True,
        magic=True,
        magic_destination=end_coords,
        is_animated=True,
        animation=animation
    )
    map_dict[start_coords].description = description
    map_dict[start_coords].tile = door_tile
    while(True):
        await asyncio.sleep(.1)
        player_coords = actor_dict['player'].coords()
        just_teleported = state_dict['just teleported']
        #TODO: add an option for non-player actors to go through.
        if player_coords == start_coords and not just_teleported:
            last_location = state_dict['last_location']
            difference_from_door_coords = (
                start_coords[0] - last_location[0], 
                start_coords[1] - last_location[1]
            )
            destination = add_coords(end_coords, difference_from_door_coords)
            if map_dict[destination].passable:
                if not silent:
                    await append_to_log(message="You are teleported.")
                map_dict[player_coords].passable=True
                actor_dict['player'].update(coord=destination)
                state_dict['just teleported'] = True
                state_dict['plane'] = destination_plane

async def create_magic_door_pair(
    door_a_coords=(5, 5),
    door_b_coords=(-25, -25),
    silent=False,
    source_plane='normal',
    destination_plane='normal'
):
    loop = asyncio.get_event_loop()
    loop.create_task(
        magic_door(
            start_coords=(door_a_coords),
            end_coords=(door_b_coords),
            silent=silent, 
            destination_plane=destination_plane
        ),
    )
    loop.create_task(
        magic_door(
            start_coords=(door_b_coords),
            end_coords=(door_a_coords),
            silent=silent,
            destination_plane=source_plane
        )
    )

async def spawn_container(
    base_name='box',
    spawn_coord=(5, 5),
    tile='☒',
    breakable=True,
    moveable=True,
    preset='random',
    description='A wooden box.'
):
    box_choices = ['', 'nut', 'dynamite', 'red potion', 'fused charge']
    if preset == 'random':
        contents = [choice(box_choices)]
    container_id = spawn_static_actor(
        base_name=base_name,
        spawn_coord=spawn_coord,
        tile=tile,
        moveable=moveable,
        breakable=breakable,
        description=description
    )
    actor_dict[container_id].holding_items = contents
    #add holding_items after container is spawned.

async def spawn_weight(
    base_name='weight',
    spawn_coord=(-2, -2),
    tile='█',
    description="This is a weighted block"
):
    """
    spawns a pushable box to trigger pressure plates or other puzzle elements.
    """
    weight_id = spawn_static_actor(
        base_name=base_name, 
        spawn_coord=spawn_coord,
        tile=tile,
        breakable=False, 
        moveable=True,
        description=description,
    )

def spawn_static_actor(
    base_name='static',
    spawn_coord=(5, 5),
    tile='☐',
    animation_preset=None,
    breakable=True,
    moveable=False,
    multi_tile_parent=None,
    blocking=False,
    literal_name=False,
    y_hide_coord=None,
    solid=True,
    description='STATIC ACTOR',
):
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
    actor_dict[actor_id] = Actor(
        name=actor_id,
        tile=tile,
        is_animated=is_animated,
        animation=animation,
        coord=spawn_coord,
        breakable=breakable,
        moveable=moveable,
        multi_tile_parent=multi_tile_parent,
        blocking=blocking,
        description=description,
        y_hide_coord=y_hide_coord,
        solid=solid,
    )
    map_dict[spawn_coord].actors[actor_id] = True
    return actor_id

def map_init():
    clear()
    rooms = {
        'a': Room((0, 0), 10, 'rough floor'),
        'b': Room((5, -20), 5),
        'c': Room((28, -28), 7),
        'd': Room((9, -39), 8),
        'e': Room((-20, 20), (12, 12)),
        'f': Room((-35, 20), (5, 5)),
        'g': Room((28, -34), 6, 'chasm'),
        'h': Room((-30, -20), (7, 7)),
        'i': Room((-30, 0)),
        'j': Room((-20, -45), (12, 6), 'goo'),
        'k': Room((9, -47), (1, 1), 'grass'),
        'l': Room((0, 0), 100, 'grass', inner_radius=70),
        'm': Room((9, -69), 5,),
        'n': Room((0, -20), 1,),
        'o': Room((-10, -20), (3, 3)),
        'p': Room((30, 0), (3, 3)),
        'q': Room((21, 0), (3, 3)),
        'r': Room((21, 18), (7, 7)),
        's': Room((7, 18), (17, 5)),
        't': Room((35, 18), (17, 5)),
        'u': Room((-1, 18), (1, 1)),
        'v': Room((-17, 18), (-16, 18)),
        'basement': Room((1000, 1000), (10, 10)),
        'entry_righthand': Room((28, -15), (10, 5)),
        'nw_off_main': Room((-4, -7), (4)),
        'nw_room_off_main': Room((-18, -14), (5)),
        'pool_a': Room((0, 6), 3, 'water'),
        'pool_b': Room((5, 8), 4, 'water'),
        'pool_c': Room((2, 8), 2, 'water'),
    }
    passage_tuples = [
        ('a', 'b', 2, None, None), 
        ('a', 'i', 2, None, None), 
        ('b', 'c', 2, None, None),
        ('d', 'c', 2, None, None),
        ('b', 'd', 2, None, None),
        ('a', 'e', 2, None, None),
        ('e', 'f', 1, None, None),
        ('d', 'j', 2, 'goo', None),
        ('k', 'm', 2, 'grass', 'jagged'),
        ('n', 'o', 1, None, None),
        ('a', 'p', 2, None, None),
        ('q', 'r', 1, None, None),
        ('r', 's', 1, None, None),
        ('r', 't', 1, None, None),
        ('u', 'v', 1, None, None),
        ('h', 'i', 2, None, None),
        ('nw_off_main', 'nw_room_off_main', 2, None, None),
    ]
    for passage in passage_tuples:
        source, destination, width, fade_to_preset, style = passage
        destination_coords = (rooms[destination].center_coord)
        rooms[source].connect_to_room(
            room_coord=destination_coords,
            passage_width=width,
            fade_to_preset=fade_to_preset,
            style=style
        )
    for room in rooms.values():
        room.draw_room()
    #secret_room(wall_coord=(-27, 20), room_offset=(-10, 0))
    secret_room(wall_coord=(35, -31))
    secret_room(wall_coord=(-40, 22), room_offset=(-3, 0), size=3)
    secret_room(wall_coord=(-40, 18), room_offset=(-3, 0), size=3)
    secret_room(wall_coord=(31, -2), room_offset=(0, -3), size=3)
    secret_room(wall_coord=(31, 2), room_offset=(0, 4), size=3)
    secret_door(door_coord=(-13, 18))
    secret_door(door_coord=(21, 2))
    draw_secret_passage(),
    draw_secret_passage(coord_a=(31, -7), coord_b=(31, -12))
    draw_secret_passage(coord_a=(31, 15), coord_b=(31, 8))
    draw_secret_passage(coord_a=(30, -18), coord_b=(30, -21))
    spawn_column(spawn_coord=(30, -5), tile='╪', name='ladder')
    for coord in ((-21, -16), (-18, -15), (-15, -14)):
        spawn_column(spawn_coord=coord)
def spawn_column(
    spawn_coord=(0, 0), 
    tile='┃', 
    height=4, 
    name='column', 
    cast_shadow=True, 
    shadow_length=4, 
    shadow_mod=5,
    solid_base=True,
):
    #TODO: in 'x' description, do not describe if it has a y_hide_coord
    """
    note: base of column is not blocking because it obscures higher elements
    """
    spawn_static_actor(
        base_name='y_hide_test', 
        spawn_coord=spawn_coord, 
        tile=tile, 
        y_hide_coord=None, 
        solid=solid_base,
        breakable=False,
        moveable=False,
        description="A {} rises into the ceiling.".format(name),
    )
    for y_value in range(height):
        column_segment_spawn_coord = add_coords(spawn_coord, (0, -y_value))
        spawn_static_actor(
            base_name='y_hide_test', 
            spawn_coord=column_segment_spawn_coord, 
            tile=tile, y_hide_coord=spawn_coord, 
            solid=False,
            breakable=False,
            moveable=False,
        )
        if cast_shadow and y_value <= shadow_length:
            map_dict[column_segment_spawn_coord].brightness_mod = shadow_mod

def announcement_at_coord(
    announcement, 
    coord=(0, 0),
    distance_trigger=3, 
    tile=None, 
    describe_tile=False
):
    """
    creates a one-time announcement at coord.
    split announcement up into separate sequential pieces with pipes
    pipes are parsed in view_tile
    """
    map_dict[coord].announcement = announcement
    map_dict[coord].announcing = True
    map_dict[coord].distance_trigger = distance_trigger
    if tile is not None:
        map_dict[coord].tile = tile
    if describe_tile:
        #strip repeated pipes:
        announcement = re.sub('\|+', '|', announcement)
        map_dict[coord].description = ' '.join(announcement.split('|'))

def is_data(): 
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

def is_number(number="0"):
    try:
        float(number)
        return True
    except ValueError:
        return False

#Top level input----------------------------------------------------------------
async def get_key(map_dict, help_wait_count=100): 
    """handles raw keyboard data, passes to handle_input if its interesting.
    Also, displays help tooltip if no input for a time."""
    debug_text = "key is: {}, same_count is: {}           "
    #TODO: fix help menu message to poll from consolidated messages (w/ repeats)
    help_text = 'Press ? for help menu.'
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        key = None
        state_dict['same_count'] = 0
        old_key = None
        while True:
            await asyncio.sleep(0.03)
            if is_data():
                key = sys.stdin.read(1)
                if key == '\x7f':  # x1b is ESC
                    state_dict['exiting'] = True
                if key is not None:
                    player_health = actor_dict["player"].health
                    if player_health > 0:
                        await handle_input(map_dict, key)
            if old_key == key:
                state_dict['same_count'] += 1
            else:
                state_dict['same_count'] = 0
            old_key = key
            if (
                state_dict['same_count'] >= help_wait_count and 
                state_dict['same_count'] % help_wait_count == 0
            ):
                if not any(
                    #line[0] is the text of the message, line[1] is the hash
                    help_text in line[0] for line in state_dict['messages'][-10:]
                ):
                    await append_to_log(message=help_text)
    finally: 
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings) 

async def handle_movement(map_dict, key):
    pass

async def handle_exit(key):
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    quit_question_text = 'Really quit? (y/n)'
    term_location = (
        middle_x - int(len(quit_question_text)/2), middle_y - 20
    )
    with term.location(*term_location):
        print(quit_question_text)
    if key in 'yY':
        state_dict['killall'] = True #trigger shutdown condition
    elif key in 'nN': #exit menus
        with term.location(*term_location):
            print(' ' * len(quit_question_text))
        state_dict['exiting'] = False

def key_to_compass(key):
    key_to_compass_char = {
        'w':'n', 'a':'w', 's':'s', 'd':'e', 
        'W':'n', 'A':'w', 'S':'s', 'D':'e', 
        'i':'n', 'j':'w', 'k':'s', 'l':'e',
        'I':'n', 'J':'w', 'K':'s', 'L':'e',
        'u':'nw', 'o':'ne', 'm':'sw', '.':'se',
        'U':'nw', 'O':'ne', 'M':'sw', '>':'se',
        ',':'s', '>':'s',
    }
    return key_to_compass_char[key]

async def menu_keypress(key):
    if key in '0123456789abcdef':
        if int("0x" + key, 16) in state_dict['menu_choices']:
            state_dict['menu_choice'] = key
    else:
        state_dict['menu_choice'] = False
        state_dict['in_menu'] = False

async def action_keypress(key):
    x_shift, y_shift = 0, 0 
    x, y = actor_dict['player'].coords()
    directions = {'a':(-1, 0), 'd':(1, 0), 'w':(0, -1), 's':(0, 1),}
    player_coords = actor_dict['player'].coords()
    if key in "wasd":
        if key in 'wasd':
            if state_dict['player_busy'] == True:
                return
            push(pusher='player', direction=key_to_compass(key))
            walk_destination = add_coords(player_coords, directions[key])
            if is_passable(walk_destination):
                x_shift, y_shift = directions[key]
        state_dict['just teleported'] = False #used by magic_doors
    elif key in 'WASD': 
        #TODO: hold shift and away from an object to pull?
        asyncio.ensure_future(dash_ability(
            dash_length=randint(2, 3),
            direction=key_to_compass(key),
            time_between_steps=.04
        ))
    elif key in "ijklIJKLuom.UOM>,<": #change viewing direction
        state_dict['facing'] = key_to_compass(key)
    elif key in '?':
            await display_help() 
    elif key in 'Xx': #examine
        asyncio.ensure_future(examine_facing())
    elif key in ' ': #toggle doors
        asyncio.ensure_future(use_action())
        await toggle_doors()
    elif key in 'g': #pick up an item from the ground
        asyncio.ensure_future(item_choices(coords=(x, y)))
    elif key in 'Q': #equip an item to slot q
        asyncio.ensure_future(equip_item(slot='q'))
    elif key in 'E': #equip an item to slot e
        asyncio.ensure_future(equip_item(slot='e'))
    elif key in 't': #throw a chosen item
        asyncio.ensure_future(throw_item())
    elif key in 'q': #use item in slot q
        asyncio.ensure_future(use_item_in_slot(slot='q'))
    elif key in 'e': #use item in slot e
        asyncio.ensure_future(use_item_in_slot(slot='e'))
    elif key in 'h': #debug health restore
        asyncio.ensure_future(health_potion())
    elif key in 'u':
        asyncio.ensure_future(use_chosen_item())
    #ITEM TEST COMMANDS----------------------------------------------------
    elif key in 'f': #use sword in facing direction
        await sword_item_ability(length=3)
    elif key in 'F': #use sword in facing direction
        await swing(base_actor='player')
    elif key in 'Y': #looking glass power
        asyncio.ensure_future(temp_view_circle(on_actor='player'))
    elif key in '3': #shift amulet power
        asyncio.ensure_future(pass_between(
            x_offset=1000, y_offset=1000, plane_name='nightmare'
        ))
    #DEBUG COMMANDS--------------------------------------------------------
    elif key in '8': #export map
        asyncio.ensure_future(export_map())
    elif key in '$':
        print_debug_grid() 
    elif key in '#':
        brightness_test()
    elif key in 'C':
        asyncio.ensure_future( add_uses_to_chosen_item())
    elif key in 'F': #fill screen with random colors
        fill_screen_with_colors()
    elif key in 'Z': #test out points_around_point and write result to map_dict
        points = points_around_point()
        for point in points:
            map_dict[add_coords(point, player_coords)].tile = '$'
    elif key in '(':
        spawn_coord = player_coords
        vine_name = "testing"
        asyncio.ensure_future(follower_vine(spawn_coord=spawn_coord))
    elif key in '%':
        asyncio.ensure_future(distanced_fade_print())
    #MAP COMMANDS----------------------------------------------------------
    elif key in '7':
        draw_circle(center_coord=actor_dict['player'].coords(), preset='floor')
    elif key in '9': #creates a passage in a random direction from the player
        facing_angle = dir_to_angle(state_dict['facing'])
        chain_of_arcs(starting_angle=facing_angle, start_coords=player_coords, num_arcs=5)
    elif key in 'b': #
        asyncio.ensure_future(rand_blink())
    elif key in 'M': #spawn an mte near the player
        spawn_coords = add_coords(player_coords, (2, 2))
        mte_id = asyncio.ensure_future(
            spawn_mte(
                spawn_coord=spawn_coords, preset='2x2_block'
            )
        )
    elif key in 'R': #generate a random cave room around the player
        player_coords = add_coords(
            actor_dict['player'].coords(), (-50, -50)
        )
        test_room = cave_room()
        write_room_to_map(room=test_room, top_left_coord=player_coords)
    elif key in 'y': #teleport to debug location
        #destination = (31, -5)
        destination = (82, 4) #outside in grassy area (good for view testing)
        actor_dict['player'].update(coord=destination)
        state_dict['facing'] = 'n'
        return
    elif key in 'T': #place a temporary pushable block
        asyncio.ensure_future(temporary_block())
    shifted_coord = add_coords((x, y), (x_shift, y_shift))
    if (
        map_dict[shifted_coord].passable and 
        shifted_coord != (0, 0)
    ):
        state_dict['last_location'] = (x, y)
        map_dict[(x, y)].passable = True #make previous space passable
        actor_dict['player'].update(coord=shifted_coord)
        x, y = actor_dict['player'].coords()
        map_dict[(x, y)].passable = False #make current space impassable

async def handle_input(map_dict, key):
    """
    interpret keycodes and do various actions.
    controls:
    wasd to move/push
    ijkl to look in different directions
    x to examine
    spacebar to open doors
    esc to open inventory
    """
    if state_dict['in_menu'] == True:
        await menu_keypress(key)
    elif state_dict['exiting'] == True:
        await handle_exit(key)
    else:
        await action_keypress(key)

def get_facing_coord():
    direction = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
    player_coords = actor_dict['player'].coords()
    facing_offset = direction[state_dict['facing']]
    facing_coord = add_coords(player_coords, facing_offset)
    return facing_coord

async def examine_facing():
    examined_coord = get_facing_coord()
    #add descriptions for actors
    is_secret = False
    has_visible_actor = False
    for actor in map_dict[examined_coord].actors:
        if actor_dict[actor].y_hide_coord is None:
            has_visible_actor = True
            actor_description = actor_dict[actor].description
    if map_dict[examined_coord].door_type != '':
        is_secret = 'secret' in map_dict[examined_coord].door_type
    #if map_dict[examined_coord].actors:
    if has_visible_actor:
        #actor_name = list(map_dict[examined_coord].actors)[0]#"There's an actor there!"
        #description_text = actor_dict[actor_name].description
        description_text = actor_description
    elif map_dict[examined_coord].items:
        description_text = "There's an item here!"
    elif map_dict[examined_coord].is_door and not is_secret:
        is_open = map_dict[examined_coord].toggle_state_index == 0
        door_type = map_dict[examined_coord].door_type
        if is_open:
            description_text = "An open {} door.".format(door_type)
        else:
            description_text = "A closed {} door.".format(door_type)
    else:
        description_text = map_dict[examined_coord].description
    if description_text is not None:
        await append_to_log(message=description_text)

async def toggle_door(door_coord):
    """
    a door is an actor that cannot be pushed and maybe is breakable
    a "steel" door cannot be broken
    a cage door can be seen through but not passed through
    when space is pressed, the door's tile is changed and it is set to passable
    """
    #TODO: generalize toggle_door to toggle_tile (for puzzles that have toggleable elements, switches)
    if map_dict[door_coord].toggle_states is None:
        return
    toggle_states = map_dict[door_coord].toggle_states
    toggle_state_index = map_dict[door_coord].toggle_state_index
    current_tile_state = term.strip_seqs(map_dict[door_coord].tile)
    if map_dict[door_coord].locked:
        description = map_dict[door_coord].door_type
        output_text="The {} door is locked.".format(description)
    else:
        new_toggle_state_index = (toggle_state_index + 1) % len(toggle_states)
        door_state = set_tile_toggle_state(
            tile_coord=door_coord, 
            toggle_state_index=new_toggle_state_index,
        )
        door_type = map_dict[door_coord].door_type
        if door_state == False:
            output_text = "You open the {} door".format(door_type)
        else:
            output_text = "You close the {} door".format(door_type)
    await append_to_log(message=output_text)

def set_tile_toggle_state(tile_coord, toggle_state_index):
    toggle_states = map_dict[tile_coord].toggle_states
    new_tile, block_state, passable_state = toggle_states[toggle_state_index]
    map_dict[tile_coord].tile = new_tile
    map_dict[tile_coord].blocking = block_state #blocking: see through tile
    map_dict[tile_coord].passable = passable_state #passable: walk through tile
    map_dict[tile_coord].toggle_state_index = toggle_state_index
    return block_state #whether the door is open or not

async def toggle_doors():
    x, y = actor_dict['player'].coords()
    player_coords = actor_dict['player'].coords()
    facing = state_dict['facing']
    directions = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
    door_coords = add_coords(player_coords, directions[facing])
    await toggle_door(door_coords)

async def use_action(tile_coords=None, is_async=True):
    """
    for the given coordinate, if the Map_tile (or actor) has a use_action_func
    (with use_action_kwargs), run that function, else, pass
    """
    if tile_coords is None:
        tile_coords = get_facing_coord()
    if map_dict[tile_coords] is not None:
        tile_use_action = map_dict[tile_coords].use_action_func
        tile_use_action_kwargs = map_dict[tile_coords].use_action_kwargs
    else:
        return
    if tile_use_action is None:
        return
    elif tile_use_action_kwargs is not None:
        if is_async:
            await tile_use_action(**tile_use_action_kwargs)
        else:
            tile_use_action(**tile_use_action_kwargs)
    else:
        if is_async:
            await tile_use_action() #case for no arguments provided
        else:
            tile_use_action()


#Item Interaction---------------------------------------------------------------
async def print_icon(x_coord=0, y_coord=20, icon_name='block wand'):
    """
    prints an item's 3x3 icon representation. tiles are stored within this 
    function.
    """
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    icons = {
        'battery':(
            '┌───┐',
            '│┌─┐│',
            '││{}││'.format(term.green('+')),
            '│└─┘│',
            '└───┘',
        ),
        'blaster':(
            '┌───┐',
            '│   │'.format(term.red('╱')),
            '│╒╤═│',
            '│║  │'.format(term.bold(term.red('╳'))),
            '└───┘',
        ),
        'block wand':(
            '┌───┐',
            '│  *│', 
            '│ ╱ │',
            '│╱  │',
            '└───┘',
        ),
        'red sword':(
            '┌───┐',
            '│  {}│'.format(term.red('╱')),
            '│ {} │'.format(term.red('╱')),
            '│{}  │'.format(term.bold(term.red('╳'))),
            '└───┘',
        ),
        'green sword':(
            '┌───┐',
            '│  {}│'.format(term.green('╱')),
            '│ {} │'.format(term.green('╱')),
            '│{}  │'.format(term.bold(term.green('╳'))),
            '└───┘',
        ),
        'nut':(
            '┌───┐',
            '│/ \│', 
            '│\_/│',
            '│\_/│',
            '└───┘',
        ),
        'dash trinket':(
            '┌───┐',
            '│ ║╲│', 
            '│ ║ │',
            '│╲║ │',
            '└───┘',
        ),
       'red potion':(
           '┌───┐',
           '│┌O┐│', 
           '│|{}|│'.format(term.red('█')),
           '│└─┘│',
           '└───┘',
        ),
        'fused charge':(
            '┌───┐',
            '│/*\│', 
            '│\_/│',
            '│\_/│',
            '└───┘',
        ),
        'scanner':(
            '┌───┐',
            '│┌─┦│', 
            '│|{}|│'.format(term.green('█')),
            '│└o┘│',
            '└───┘',
        ),
        'dynamite':(
            '┌───┐',
            '│ ╭ │', 
            '│ {} │'.format(term.red('█')),
            '│ {} │'.format(term.red('█')),
            '└───┘',
        ),
        'shift amulet':(
            '┌───┐',
            '│╭─╮│', 
            '││ ││',
            '│╰{}╯│'.format(term.blue('ʘ')),
            '└───┘',
        ),
        'hop amulet':(
            '┌───┐',
            '│╭─╮│', 
            '││ ││',
            '│╰{}╯│'.format(term.red('ʘ')),
            '└───┘',
        ),
        'looking glass':( 
            '┌───┐',
            '│ ⴰ〫 〬│',
            '│   ⃝│',
            '│ ⧸ │',
            '└───┘',
        ),
        'eye trinket':(
            '┌───┐',
            '│   │', 
            '│<ʘ>│',
            '│   │',
            '└───┘',
        ),
        'red key':(
            '┌───┐',
            '│ {} │'.format(term.red('╒')),
            '│ {} │'.format(term.red('│')),
            '│ {} │'.format(term.red('O')),
            '└───┘',
        ),
        'green key':(
            '┌───┐',
            '│ {} │'.format(term.green('╒')),
            '│ {} │'.format(term.green('│')),
            '│ {} │'.format(term.green('O')),
            '└───┘',
        ),
        'rusty key':(
            '┌───┐',
            '│ {} │'.format(term.color(3)('╒')),
            '│ {} │'.format(term.color(3)('│')),
            '│ {} │'.format(term.color(3)('O')),
            '└───┘',),
        'shiny stone':(
            '┌───┐',   #effect while equipped: orbit
            '│ _ │', 
            '│(_)│',
            '│   │',
            '└───┘',
        ),
        'empty':(
            '┌───┐',
            '│   │', 
            '│   │',
            '│   │',
            '└───┘',
        ),
    }
    for (num, line) in enumerate(icons[icon_name]):
        with term.location(*add_coords((x_coord, y_coord), (0, num))):
            print(line)

async def choose_item(
    item_id_choices=None, item_id=None, x_pos=0, y_pos=25
):
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
    for (number, item) in enumerate(item_id_choices):
        with term.location(x_pos, y_pos + number):
            print("{}:".format(str(hex(number))[-1]))
    menu_choices = [str(hex(i))[-1] for i in range(16)]
    return_val = None
    while state_dict['in_menu']:
        await asyncio.sleep(.1)
        menu_choice = state_dict['menu_choice']
        if type(menu_choice) == str and menu_choice not in menu_choices:
            menu_choice = int(menu_choice)
            break
        if menu_choice in menu_choices:
            state_dict['in_menu'] = False
            state_dict['menu_choice'] = -1 # not in range as 1 evaluates as True.
            return_val = item_id_choices[int(menu_choice, 16)]
    clear_screen_region( #clear number choices along left edge
        x_size=2, y_size=len(item_id_choices), screen_coord=(x_pos, y_pos)
    )
    return return_val

async def console_box(
    width=40, height=10, x_margin=1, y_margin=1, refresh_rate=.05
    #width=40, height=10, x_margin=1, y_margin=10, refresh_rate=.05 #for debugging
):
    state_dict['messages'] = [('', 0)] * height
    asyncio.ensure_future(
        ui_box_draw(
            box_height=height, 
            box_width=width, 
            x_margin=x_margin - 1,
            y_margin=y_margin - 1
        )
    )
    while True:
        grouped_messages = [['', hash(''), 1]]
        last_message_hash = ''
        message_index = len(state_dict['messages']) - 1
        while len(grouped_messages) <= height:
            message, message_hash = state_dict['messages'][message_index]
            if message_hash != last_message_hash and last_message_hash != 0: 
                grouped_messages.append([message, message_hash, 1])
            else:
                grouped_messages[-1][2] += 1
            last_message_hash = message_hash
            message_index -= 1
            if message_index <= 0:
                break
        for index, (message, hash_val, count) in enumerate(grouped_messages[1:]):
            if count > 1 and message != '':
                suffix = "x{}".format(count)
            else:
                suffix = ""
            line_text = "{}{}".format(message, suffix)
            line_y = index + y_margin
            with term.location(x_margin, line_y):
                print(line_text.ljust(width, ' '))
        await asyncio.sleep(refresh_rate)

async def append_to_log(
    message="This is a test", 
    wipe=False, 
    wipe_time=5, 
    wipe_char_time=.1,
):
    if '|' in message:
        messages = message.split('|')
        for split_message in messages:  
            if split_message == '':
                await asyncio.sleep(1)
            else:
                await append_to_log(
                    message=split_message,
                    wipe=wipe,
                    wipe_time=wipe_time,
                    wipe_char_time=wipe_char_time,
                )
        return
    message_lines = textwrap.wrap(message, 40)
    padded_lines = ["{:<37}".format(line) for line in message_lines]
    if wipe:
        wipe_text = ' ' * len(message)
    for index_offset, line in enumerate(reversed(padded_lines)):
        line_index = len(state_dict['messages'])
        state_dict['messages'].append(('', hash(message)))
        asyncio.ensure_future(
            filter_into_log(
                message=line, line_index=line_index
            )
        )
    if wipe:
        for index_offset, line in enumerate(reversed(padded_lines)):
            await asyncio.sleep(wipe_time)
            asyncio.ensure_future(
                filter_into_log(
                    starting_text=line,
                    message=wipe_text,
                    line_index=line_index,
                    time_between_chars=.02
                )
            )

async def filter_into_log(
    message="This is a test",
    line_index=0,
    time_between_chars=.02,
    starting_text=''
):
    if starting_text == '':
        written_string = [' '] * len(message)
    else:
        written_string = list(starting_text)
    indexes = [index for index in range(len(message))]
    shuffle(indexes)
    for index in indexes:
        await asyncio.sleep(time_between_chars)
        written_string[index] = message[index]
        state_dict['messages'][line_index] = (
            ''.join(written_string), hash(message)
        )

async def key_slot_checker(
    slot='q', frequency=.1, centered=True, print_location=(0, 0)
):
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


async def battery_item(
    item_id=None,
    num_charges=6,
):
    return_val = await add_uses_to_chosen_item(num_charges=num_charges)
    if item_id and return_val:
        del item_dict[item_id]
        del actor_dict['player'].holding_items[item_id]

async def add_uses_to_chosen_item(num_charges=10):
    asyncio.ensure_future(
        append_to_log("Charge which item?")
    )
    item_id_choice = await choose_item()
    if item_id_choice != None:
        item_name = item_dict[item_id_choice].name
        accepts_charges = item_dict[item_id_choice].accepts_charges
        if accepts_charges:
            item_dict[item_id_choice].uses += num_charges
            await append_to_log("Added {} charges to {}".format(num_charges, item_name))
            if item_dict[item_id_choice].broken:
                item_dict[item_id_choice].broken = False
            return True
        else:
            await append_to_log("{} cannot be charged.".format(item_name.capitalize()))
            return False
    
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

async def item_choices(coords=None, x_pos=0, y_pos=13):
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
        id_choice = await choose_item(
            item_id_choices=item_list, x_pos=x_pos, y_pos=y_pos
        )
        if id_choice:
            await get_item(coords=coords, item_id=id_choice)

async def get_item(coords=(0, 0), item_id=None, source='ground'):
    """
    Transfers an item from a map tile to the holding_items dict of an actor.
    """
    if len(actor_dict['player'].holding_items) >= 16:
        await append_to_log("You can't carry any more!")
        return False
    template_text = "You take the {} from the {}."
    pickup_text = template_text.format(item_dict[item_id].name, source)
    del map_dict[coords].items[item_id]
    actor_dict['player'].holding_items[item_id] = True
    await append_to_log(message=pickup_text)
    return True

#Announcement/message handling--------------------------------------------------
async def parse_announcement(tile_coord_key, delay=1):
    """
    parses an announcement, with a new line printed after each pipe 
    """
    announcement_sequence = map_dict[tile_coord_key].announcement.split("|")
    for line in announcement_sequence:
        if line != '':
            await append_to_log(message=line)
        await asyncio.sleep(delay)

async def trigger_announcement(tile_coord_key, player_coords=(0, 0)):
    is_announcing = map_dict[tile_coord_key].announcing
    yet_seen = map_dict[tile_coord_key].seen
    if is_announcing and not yet_seen:
        if map_dict[tile_coord_key].distance_trigger:
            distance = point_to_point_distance(tile_coord_key, player_coords)
            if distance <= map_dict[tile_coord_key].distance_trigger:
                map_dict[tile_coord_key].seen = True
                await parse_announcement(tile_coord_key)
        else:
            map_dict[tile_coord_key].seen = True
            await parse_announcement(tile_coord_key)
    else:
        map_dict[tile_coord_key].seen = True

#Geometry functions-------------------------------------------------------------
def point_to_point_distance(point_a, point_b):
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

def point_at_distance_and_angle(
    angle_from_twelve=30,
    central_point=(0, 0), 
    reference_point=(0, 5),
    radius=10,
    rounded=True,
):
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

def dir_to_angle(facing_dir, offset=0, mirror_ns=False):
    if mirror_ns:
        dirs_to_angle = {
            #'n':180, 'e':90, 's':360, 'w':270, #swap n with s
            'n':360, 'e':90, 's':180, 'w':270,
            #'ne':135, 'se':45, 'sw':315, 'nw':225 # swap ne w/ se, sw w/ nw
            'ne':45, 'se':135, 'sw':225, 'nw':315,
        }
    else:
        dirs_to_angle = {
            'n':180, 'e':90, 's':360, 'w':270,
            'ne':135, 'se':45, 'sw':315, 'nw':225
        }
    #dirs_to_angle['n'] = 360
    #dirs_to_angle['s'] = 180
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

async def crosshairs(
    radius=18,
    crosshair_chars=('.', '*', '.'),
    fov=30, 
    refresh_delay=.05
):
    middle_x, middle_y = (
        int(term.width / 2 - 2), 
        int(term.height / 2 - 2),
    )
    central_point = (middle_x, middle_y)
    last_angle = None
    old_points = None #used for clearing out print location
    while True:
        current_angle = state_dict['current_angle']
        #clear last known location of crosshairs:
        if last_angle != current_angle:
            angles = (current_angle + fov, current_angle, current_angle - fov)
            points = [
                point_at_distance_and_angle(
                    radius=radius,
                    central_point=central_point,
                    angle_from_twelve=angle
                )
                for angle in angles
            ]
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
    x_offset, y_offset = offset_of_center(x_offset=-15, y_offset=-5)
    help_text = (
        " wasd: move/push          ",
        " WASD: run (no pushing)   ",
        "space: open/close/interact",
        " ijkl: look in direction  ",
        "    g: get item from tile,",
        "       0-f to choose item ",
        "  Q/E: equip item to slot,",
        "       0-f to choose item ",
        "  q/e: use equipped item  ",
        "    t: throw chosen item  ",
        "    u: use selected item  ",
        "    x: examine faced tile ",
        "bkspc: quit dialog (y/n)  ",
        "    ?: open this message  ",
    )
    for line_number, line in enumerate(help_text):
        x_print_coord, y_print_coord = 0, 0
        asyncio.ensure_future(
            filter_print(
                output_text=line, pause_stay_on=7,
                pause_fade_in=.015, pause_fade_out=.015,
                x_offset=-55, y_offset=-33 + line_number,
                hold_for_lock=False
            )
        )

async def tile_debug_info(offset_coord=(50, 0), offset_from_center=False):
    middle_coord = get_term_middle()
    dummy_text = []
    while True:
        directions = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
        check_dir = state_dict['facing']
        check_coord = add_coords(
            actor_dict['player'].coords(),
            directions[check_dir]
        )
        output_text = [
            f'tile_debug_info:',
            f'facing: {check_dir}',
            f' coord: {check_coord}',
            f'actors: {map_dict[check_coord].actors.keys()}',
            f'numact: {len(map_dict[check_coord].actors.keys())}',
            f'  tile: {map_dict[check_coord].tile}',
        ]
        blank_space = [' ' * len(line) for line in output_text]
        for text_written in (blank_space, output_text):
            for y_offset, line in enumerate(text_written):
                output_location = add_coords(offset_coord, (0, y_offset))
                with term.location(*output_location):
                    print(line)
        await asyncio.sleep(.2)

async def check_line_of_sight(coord_a, coord_b):
    """
    intended to be used for occlusion.
    show the tile that the first collision happened at but not the following tile

    first checks if the checked tile is a wall, if so, we ask if there's a 
    neighbor to that tile that has a clear line of sight to coord_a. if so,
    display the tile
    """
    points = get_line(coord_a, coord_b)
    has_magic = any([map_dict[point].magic for point in points])
    #since walls and thin corridors are special cases,
    #if the last coord is blocking, just change coord_b to check the new non-wall tile
    if map_dict[coord_b].blocking:
        neighbors = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
        neighbor_coords = [
            add_coords(coord_b, neighbor) for neighbor in neighbors.values()
        ]
        non_walls = []
        for coord in neighbor_coords:
            not_blocking = not map_dict[coord].blocking
            explored = map_dict[coord].seen
            if not_blocking and explored:
                non_walls.append(coord)
        if len(non_walls) == 0 and not has_magic: #we're in the middle of a wall
            return False #this is causing problems for magic doors.
        elif len(non_walls) == 1:
            coord_b = non_walls[0]
        else:
            dists = {coord:point_to_point_distance(coord_a, coord) for coord in neighbor_coords}
            min_value = min(dists.values())
            result = [(key, value) for key, value in dists.items() if value == min_value]
            coord_b = result[0][0]
    points = get_line(coord_a, coord_b) #recompute after changed endpoint
    walls = 0
    blocking_actor_index = None
    inside_mte = False 
    for index, point in enumerate(points[:-1]):
        if map_dict[point].actors:
            for key in map_dict[point].actors:
                if 'mte' in key:
                    #TODO: allow for transparent MTEs
                    if inside_mte:
                        return False
                    else:
                        inside_mte = True
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
    if blocking_actor_index is not None:
        if blocking_actor_index < len(points) - 1:
            return False
        else:
            return True
    #if there's only open space among the checked points, display it.
    elif walls == 0:
        return True
    else:
        return False

async def handle_magic_door(point=(0, 0), last_point=(5, 5)):
    difference_from_last = diff_coords(last_point, point)
    destination = map_dict[point].magic_destination
    if difference_from_last is not (0, 0):
        coord_through_door = (
            destination[0] + difference_from_last[0], 
            destination[1] + difference_from_last[1]
        )
        door_points = get_line(destination, coord_through_door)
        if len(door_points) >= 2:
            LOS_result = await check_line_of_sight(
                door_points[1], coord_through_door
            )
        else:
            LOS_result = True
        if LOS_result not in (False, None):
            return coord_through_door
        else:
            return LOS_result

#TODO: an enemy that carves a path through explored map tiles and causes it to be forgotten.
#      [ ]the tile displayed by gradient_tile_pairs is modified by the light level of the tile
#      [ ]actors have a chance to not display based on the light level of the tile they are sitting on.
#      [ ]actors which stay in darkness until lit up or a condition is met and then they change behavior
#             seek or flee
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

def get_term_middle():
    middle_x, middle_y = (int(term.width / 2 - 2), int(term.height / 2 - 2))
    return (middle_x, middle_y)

async def view_tile(map_dict, x_offset=1, y_offset=1, threshold=15, fov=140):
    """ handles displaying data from map_dict """
    #distance from offsets to center of field of view
    distance = sqrt(abs(x_offset)**2 + abs(y_offset)**2) 
    await asyncio.sleep(random()/5 * distance) #stagger starting_time
    middle_x, middle_y = (int(term.width / 2 - 2), int(term.height / 2 - 2))
    previous_tile = None
    print_location = add_coords((middle_x, middle_y), (x_offset, y_offset))
    angle_from_twelve = find_angle(p0=(0, 5), p2=(x_offset, y_offset))
    last_print_choice = ' '
    if x_offset <= 0:
        angle_from_twelve = 360 - angle_from_twelve
    display = False
    player_coords = actor_dict['player'].coords()
    while True:
        state_dict["view_tile_count"] += 1
        await asyncio.sleep(distance * .0075 + .05 + random() * .1) #update speed
        if not state_dict['lock view']:
            player_coords = actor_dict['player'].coords()
        x_display_coord, y_display_coord = (
            add_coords(player_coords, (x_offset, y_offset))
        )
        tile_coord_key = (x_display_coord, y_display_coord)
        #check whether the current tile is within the current field of view
        current_angle = state_dict['current_angle']
        l_angle, r_angle = (
            (current_angle - fov // 2) % 360, 
            (current_angle + fov // 2) % 360
        )
        display = angle_in_arc(
            angle_from_twelve,
            arc_begin=l_angle,
            arc_end=r_angle
        )
        if (x_offset, y_offset) == (0, 0):
            display=True
        if map_dict[x_display_coord, y_display_coord].override_view:
            print_choice = await check_contents_of_tile((x_display_coord, y_display_coord))
            map_dict[tile_coord_key].seen = True
        elif display:
            random_distance = abs(gauss(distance, 1))
            if random_distance < threshold: 
                line_of_sight_result = await check_line_of_sight(
                    player_coords,
                    tile_coord_key
                )
                if type(line_of_sight_result) is tuple:
                    print_choice = await check_contents_of_tile(line_of_sight_result)
                elif line_of_sight_result == True:
                    await trigger_announcement(
                        tile_coord_key,
                        player_coords=player_coords
                    )
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
                color_choice = 0xea
            remembered_tile = map_dict[x_display_coord, y_display_coord].tile
            if map_dict[x_display_coord, y_display_coord].actors:
                for key in map_dict[x_display_coord, y_display_coord].actors.keys():
                    if 'mte' in key:
                        raw_tile = term.strip_seqs(actor_dict[str(key)].tile)
                        remembered_tile = term.color(color_choice)(raw_tile)
                        break
            if map_dict[x_display_coord, y_display_coord].items:
                for item_id in map_dict[x_display_coord, y_display_coord].items:
                    raw_tile = term.strip(item_dict[item_id].tile)
                    remembered_tile = term.color(color_choice)(raw_tile)
                    break
            print_choice = term.color(color_choice)(str(remembered_tile))
        else:
            #catches tiles that are not within current FOV
            print_choice = ' '
        # only print something if it has changed:
        if last_print_choice != print_choice:
            tile_color = map_dict[tile_coord_key].color_num
            brightness_mod = map_dict[tile_coord_key].brightness_mod
            tile_brightness = get_brightness(distance, brightness_mod)
            if not state_dict['lock view']:
                color_tuple = brightness_vals[int(tile_brightness)]
            else:
                #if view locked, display a slightly fuzzy but uniform view:
                color_tuple = brightness_vals[9 + randint(-2, 2)]
            if print_choice in ('░', '▞', '𝄛', '■', '▣'):
                print_choice = term.color(color_tuple[0])(print_choice)
            else:
                print_choice = term.color(tile_color)(print_choice)
        with term.location(*print_location):
            print(print_choice)
        last_print_choice = print_choice

def get_brightness(distance, brightness_mod, lower_limit=0xe8, upper_limit=0x100):
    """
    brighness falls off according to the below equation

    the random element makes it so the returned value sometimes rounds up or
    down to a nearby value.

    The greyscale values lie between 0xe8 (near-black) and 0x100 (white)
    """
    brightness_val = int(round(
        -(30 / (.5 * ((distance/2) + 3))) + 27 + brightness_mod + random() * .75, 1
    ))
    if brightness_val <= 0:
        return 0
    elif brightness_val >= len(brightness_vals) - 1:
        return len(brightness_vals) - 1
    return brightness_val

async def check_contents_of_tile(coord):
    if map_dict[coord].actors:
        actor_choice = None
        for actor_name in map_dict[coord].actors:
            #y_hide_coord acts roughly like a z_index: higher values in front
            y_hide_coord = actor_dict[actor_name].y_hide_coord
            if y_hide_coord is not None:
                player_coords = actor_dict['player'].coords()
                if player_coords[1] >= y_hide_coord[1]:
                    actor_choice = actor_name
                else:
                    continue
            else:
                actor_choice = actor_name
        if actor_choice is not None:
            return actor_dict[actor_choice].get_view()
    if map_dict[coord].items:
        item_name = next(iter(map_dict[coord].items))
        return item_dict[item_name].tile
    elif map_dict[coord].is_animated:
        return next(map_dict[coord].animation)
    else:
        if map_dict[coord].color_num not in (7, 8):
            tile_color = map_dict[coord].color_num
            return term.color(tile_color)(map_dict[coord].tile)
        else:
            return map_dict[coord].tile

def offset_of_center(x_offset=0, y_offset=0):
    window_width, window_height = term.width, term.height
    middle_x, middle_y = (
        int(window_width / 2 - 2), 
        int(window_height / 2 - 2),
    )
    x_print, y_print = middle_x + x_offset, middle_y + y_offset
    return x_print, y_print

def clear_screen_region(
    x_size=10, 
    y_size=10,
    screen_coord=(0, 0),
    debug=False
):
    if debug:
        marker = str(randint(0, 9))
    else:
        marker = ' '
    for y in range(screen_coord[1], screen_coord[1] + y_size):
        with term.location(screen_coord[0], y):
            print(marker * x_size)

async def ui_box_draw(
    position="top left",
    box_height=1,
    box_width=9,
    x_margin=30,
    y_margin=4,
    one_time=False,
):
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
        middle_x, middle_y = (
            int(window_width / 2 - 2), 
            int(window_height / 2 - 2),
        )
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

async def status_bar_draw(
    state_dict_key="health",
    position="top left",
    bar_height=1,
    bar_width=10,
    x_margin=5,
    y_margin=4
):
    asyncio.ensure_future(
        ui_box_draw(
            position=position,
            bar_height=box_height,
            bar_width=box_width,
            x_margin=x_margin,
            y_margin=y_margin
        )
    )

async def random_angle(centered_on_angle=0, total_cone_angle=60):
    rand_shift = round(randint(0, total_cone_angle) - (total_cone_angle / 2))
    return (centered_on_angle + rand_shift) % 360

async def directional_alert(
    particle_count=40,
    source_angle=None, 
    source_actor=None,
    source_direction=None,
    radius=17,
    radius_spread=3,
    warning_color=1,
    palette='?',
    persist_delay=1,
    angle_spread=60,
    preset='damage'
):
    """
    generates a spray of red tiles beyond the normal sight radius in the
    direction of a damage source.
    """
    presets = {
        'damage':{
            'particle_count':40,
            'radius':15, 
            'radius_spread':3, 
            'angle_spread': 60,
            'warning_color':1,
            'palette':"█",
            'persist_delay':0,
        },
        'heal':{
            'particle_count':5,
            'radius':15, 
            'radius_spread':3, 
            'angle_spread': 360,
            'warning_color':0x1c,
            'palette':"█",
            'persist_delay':.075,
        },
        'sound':{
            'particle_count':10,
            'radius':12,
            'radius_spread':1,
            'angle_spread': 30,
            'warning_color':2,
            'palette':"◌",
            'persist_delay':1,
        },
        'footfall':{
            'particle_count':1,
            'radius':18,
            'radius_spread':1,
            'angle_spread': 30,
            'warning_color':0x08,
            'palette':"◌",
            'persist_delay':1,
        },
    }
    if preset is not None and preset in presets:
        preset_kwargs = presets[preset]
        await directional_alert(
            **preset_kwargs,
            source_actor=source_actor,
            preset=None
        )
        return
    if source_actor:
        if source_actor not in actor_dict:
            return
        source_angle = angle_point_to_point(
            actor_a='player',
            actor_b=source_actor
        )
    elif source_direction is not None:
        if source_direction in source_directions:
            source_angle = dir_to_angle(source_direction)
    elif source_angle is None:
        return
    source_angle = 180 - source_angle
    middle_x, middle_y = (
        int(term.width / 2 - 2), 
        int(term.height / 2 - 2),
    )
    ui_points = []
    for _ in range(particle_count):
        point_radius = radius + randint(0, radius_spread)
        central_point = (middle_x, middle_y)
        angle = await random_angle(
            centered_on_angle=source_angle, 
            total_cone_angle=angle_spread
        )
        point = point_at_distance_and_angle(
            radius=point_radius,
            central_point=central_point,
            angle_from_twelve=angle,
        )
        ui_points.append(point)
    for tile_palette in [palette, ' ']:
        shuffle(ui_points)
        for point in ui_points:
            tile_choice = term.color(warning_color)(choice(tile_palette))
            await asyncio.sleep(random()/70)
            with term.location(*point):
                print(tile_choice)
        await asyncio.sleep(persist_delay)

async def fade_print(
    output_text="This is a test", 
    print_coord=(55, 0),
    fade_step=1, 
    fade_range=(0xe8, 0xff),
    fade_delay=.5, #how long to wait before starting to fade text
    step_delay=.05, #how long between each step through the range
    reverse_range=True,
):
    color_steps = [color_number for color_number in range(*fade_range)]
    if reverse_range:
        color_steps.reverse()
    for index, color_num in enumerate(color_steps):
        with term.location(*print_coord):
            print(term.color(color_num)(output_text))
        if index == 0:
            await asyncio.sleep(fade_delay)
        else:
            await asyncio.sleep(step_delay)

async def distanced_fade_print(
    output_text="DRIP",
    fade_duration=1,
    origin=(0, 0),
    print_coord=(100, 5),
    fade_range=(0xe8, 0xff),
):
    distance = point_to_point_distance(origin, actor_dict['player'].coords())
    cutoff = 0
    if distance > 18:
        cutoff = distance - 18
    lower, upper = fade_range[0], fade_range[1] - cutoff
    if lower >= upper:
        return
    fade_delay = round(fade_duration / (upper - lower), 3)
    await fade_print(
        output_text=output_text,
        print_coord=print_coord,
        fade_range=(lower, upper),
        fade_delay=fade_delay,
        step_delay=fade_delay,
    )

async def repeated_sound_message(
    output_text="drip", 
    interval=1,
    sound_origin_coord=(0, 0),
    source_actor=None,
    point_radius=18,
    rand_delay=True,
    fade_duration=1,
):
    """
    Assumes the player is the center and creates a fading message at the
    appropriate source angle to simulate a sound being heard from that
    direction.
    """
    if rand_delay:
        await asyncio.sleep(random())
    while True:
        if rand_delay:
            await asyncio.sleep(1 + random())
        else:
            await asyncio.sleep(1)
        await sound_message(
            output_text=output_text,
            sound_origin_coord=sound_origin_coord,
            source_actor=source_actor,
            point_radius=point_radius,
            fade_duration=fade_duration
        )

async def sound_message(
    output_text="drip", 
    sound_origin_coord=(0, 0),
    source_actor=None,
    point_radius=18,
    fade_duration=1,
):
    if source_actor:
        sound_origin_coord = actor_dict[source_actor].coords()
    source_angle = angle_point_to_point(coord_b=sound_origin_coord, actor_a='player')
    x_middle, y_middle = (int(term.width / 2 - 2), int(term.height / 2 - 2))
    central_point = (x_middle, y_middle)
    print_coord = point_at_distance_and_angle(
        radius=point_radius,
        central_point=central_point,
        angle_from_twelve=(-source_angle % 360) + 180,
    )
    if print_coord[0] < x_middle:
        print_coord = ((print_coord[0] - len(output_text)), print_coord[1])
    elif print_coord[0] == x_middle:
        print_coord = ((print_coord[0] - (len(output_text) // 2)), print_coord[1])
    await distanced_fade_print(
        output_text=output_text, 
        origin=sound_origin_coord,
        print_coord=print_coord,
        fade_duration=fade_duration,
    )

def timer_text(minutes, seconds):
    output_text = "⌛ {0: }:{}".format(
        str(time_minutes).zfill(2),
        str(time_seconds).zfill(2)
    )
    return output_text

async def timer(
    x_pos=0,
    y_pos=10,
    time_minutes=0,
    time_seconds=5,
    resolution=1,
):
    timer_text = timer_text(time_minutes, time_seconds)
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
        timer_text = timer_text(time_minutes, time_seconds)
    return

async def view_tile_init(
    loop,
    term_x_radius=40,
    term_y_radius=20,
    max_view_radius=17,
    debug=False
):
    view_tile_count = 0
    for x in range(-term_x_radius, term_x_radius + 1):
       for y in range(-term_y_radius, term_y_radius + 1):
           view_tile_count += 1
           distance = sqrt(x**2 + y**2)
           #cull view_tile instances that are beyond a certain radius
           if distance < max_view_radius:
               loop.create_task(view_tile(map_dict, x_offset=x, y_offset=y))
    if debug:
        with term.location(50, 0):
            print("view_tile_count: {}".format(view_tile_count))

async def minimap_init(loop, box_width=21, box_height=21):
    width_span = range(-20, 21, 2)
    height_span = range(-20, 21, 2)
    width, height = (term.width, term.height)
    x_offset, y_offset = (width - (box_width // 2) - 2), 1 + (box_height // 2)
    if width % 2 == 0:
        box_x_offset, box_y_offset = (width // 2) - box_width, -box_height - 1
    else:
        box_x_offset, box_y_offset = (width // 2) - box_width + 1, -box_height - 1
    asyncio.ensure_future(
        ui_box_draw(
            position='centered',
            x_margin=box_x_offset,
            y_margin=box_y_offset, 
            box_width=box_width,
            box_height=box_height
        )
    )
    for x in width_span:
        for y in height_span:
            half_scale = x // 2, y // 2
            loop.create_task(
                minimap_tile(
                    player_position_offset=(x, y),
                    display_coord=(
                        add_coords((x_offset, y_offset), half_scale)
                    )
                )
            )

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
    loop = asyncio.get_event_loop()
    #map drawing-------------------------------------------
    announcement_at_coord(
        "There's a body here.|||Looks like you get their stuff.",
        coord=(8, 6), 
        describe_tile=True, 
        tile="g"
    )
    announcement_at_coord(
        "The dooway shimmers slightly as you look through it.",
        coord=(-20, 24),
        describe_tile=True,
        distance_trigger=2
    )
    announcement_at_coord(
        "You feel momentarily nauseous.",
        coord=(-1020, -969),
        describe_tile=False, 
        distance_trigger=3
    )
    announcement_at_coord(
        "A loose pebble tumbles off the edge. |||You don't hear it land.", 
        coord=(31, -28), 
        describe_tile=False, 
        distance_trigger=0
    )
    announcement_at_coord(
        "The darkness is moving here.|||It's taken an interest in you.||Running might be a good idea.", 
        coord=(25, -27), 
        describe_tile=False, 
        distance_trigger=0
    )
    announcement_at_coord(
        "Every surface is covered in a pulsating slime.|||You feel a little nauseous.",
        coord=(-17, -44),
        describe_tile=False,
        distance_trigger=0
    )
    announcement_at_coord(
        "It's pretty but there's nothing much going on out here.||It's hard to see much in this darkness.",
        coord=(10, -68), 
        describe_tile=False,
        distance_trigger=0
    )
    #spawn multi-tile entities-----------------------------
    mte_spawns = (
        ((17, 1), '2x2_block'),
        ((11, 0), '2x2_block'),
        ((-32, 3), '2x2_block'),
        ((-28, 1), '2x2_block'),
        ((9, 3), '2x2_block'),
        ((7, 0), '2x2_block'),
        ((27, 0), '2x2_block'),
        ((29, 1), '2x2_block'),
        ((5, 0), '2x2_block'),
        ((7, 3), '2x2_block'),
        #room to north of scanner spawn location
        ((24, -16), '2x2_block'),
        ((30, -13), '2x2_block'),
        ((31, -16), '2x2_block'),
        ((28, -13), '2x2_block'),
        ((29, -15), '2x2_block'),
        ((13, 17), '2x2_block'),
        ((11, 17), '2x2_block'),
        ((9, 17), '2x2_block'),
        ((15, 20), '2x2_block'),
        ((13, 20), '2x2_block'),
        ((11, 20), '2x2_block'),
    )
    for (coord, preset) in mte_spawns:
        asyncio.ensure_future(
            spawn_mte(
                spawn_coord=coord, preset=preset
            )
        )
    #features drawing--------------------------------------
    containers = [
        (3, -2),
        (3, -3),
        (-44, 21), 
        (-36, 18),
        (-36, 22),
        (4, -24)
    ]
    for coord in containers:
        loop.create_task(spawn_container(spawn_coord=coord))
    #item creation-----------------------------------------
    items = (
        ((-3, 0), 'block wand'), 
        ((-3, -3), 'red key'), 
        ((8, 4), 'red potion'), 
        ((47, -31), 'red sword'), 
        ((-21, -18), 'blaster'), 
        ((-18, -19), 'battery'), 
        ((23, -13), 'battery'), 
        ((30, 7), 'battery'), #small s. room s. of spawn
        ((-1, -5), 'green sword'), 
        ((32, -5), 'green sword'), #debug
        ((25, -1), 'dash trinket'), #debug
        ((-11, -20), 'hop amulet'), 
        ((-15, 0), 'looking glass'), 
        ((31, -6), 'scanner'),
        ((31, -1), 'red potion'),
        ((20, 1), 'green key'),
    )
    for coord, item_name in items:
        spawn_item_at_coords(
            coord=coord, instance_of=item_name, on_actor_id=False
        )
    #actor creation----------------------------------------
    tasks = [
        spawn_container(spawn_coord=(3, -4)),
        trap_init(),
        #beam_spire(spawn_coord=(26, -25)),
        repeated_sound_message(output_text="*drip*", sound_origin_coord=(0, 0)),
        repeated_sound_message(output_text="*drip*", sound_origin_coord=(21, 19)),
        repeated_sound_message(output_text="*drip*", sound_origin_coord=(2, -24)),
        puzzle_pair(
            block_coord=(3, -5),
            plate_coord=(3, -11),
            puzzle_name='puzzle_0',
            color_num=3,
            block_char='☐'
        ),
        bay_door_pair(
            (2, -15),
            (6, -15),
            patch_to_key='puzzle_0',
            preset='thick',
            pressure_plate_coord=((4, -17)),
            message_preset='ksh'
        ),
    ]
    monster_spawns = (
       ((25, -13), 'blob'),
       ((-4, -9), 'blob'),
       ((-20, 16), 'blob'),
    )
    #for coord, name in monster_spawns:
        #tasks.append(spawn_preset_actor(coords=coord, preset=name))
    for task in tasks:
        loop.create_task(task)


async def trap_init():
    loop = asyncio.get_event_loop()
    node_offsets = ((-6, 's'), (6, 'n'))
    nodes = [(i, *offset) for i in range(-5, 6) for offset in node_offsets]
    base_coord = (9, -41)
    draw_centered_box(middle_coord=base_coord, x_size=11, y_size=11, preset='floor')
    rand_coords = {
        (
            randint(-5, 5) + base_coord[0], 
            randint(-5, 5) + base_coord[1]
        ) 
        for _ in range(20)
    }
    state_dict['switch_1'] = {}
    for coord in rand_coords:
        loop.create_task(
            pressure_plate(
                spawn_coord=coord, patch_to_key='switch_1'
            )
        )
    loop.create_task(
        multi_spike_trap(
            nodes=nodes, base_coord=base_coord, patch_to_key='switch_1'
        )
    )
    state_dict['switch_2'] = {}
    loop.create_task(
        pressure_plate(
            spawn_coord=(6, -20), patch_to_key='switch_2'
        )
    )
    loop.create_task(
        trigger_door(
            door_coord=(-1, -20), patch_to_key='switch_2'
        )
    )
    loop.create_task(
        trigger_door(
            door_coord=(-8, -20), patch_to_key='switch_2', invert=True
        )
    )

async def pass_between(x_offset, y_offset, plane_name='nightmare'):
    """
    shift from default area to alternate area and vice versa.
    """
    player_coords = actor_dict['player'].coords()
    if state_dict['plane'] == 'normal':
        offset_coords = add_coords(player_coords, (x_offset, y_offset))
        destination, plane = offset_coords, plane_name
        draw_circle(
            center_coord=offset_coords,
            radius=12,
            annulus_radius=12,
            border_thickness=18,
            border_preset='chasm',
            chance_skip=0,
        )
        draw_circle(
            center_coord=offset_coords,
            radius=12,
            annulus_radius=12,
            border_thickness=1,
            border_preset='nightmare',
            chance_skip=.5,
        )
        draw_circle(
            center_coord=offset_coords,
            radius=10,
            animation=None,
            preset='nightmare',
            annulus_radius=None
        )
        asyncio.ensure_future(append_to_log(
            message="You're not alone in this place.||||Something moves at the edge of your vision."
        ))
    elif state_dict['plane'] == plane_name:
        destination = add_coords(player_coords, (-x_offset, -y_offset))
        plane = 'normal'
    else:
        return False
    if map_dict[destination].passable:
        map_dict[player_coords].passable = True
        actor_dict['player'].update(coord=destination)
        state_dict['plane'] = plane
        if plane != 'normal':
            state_dict['known location'] = False
        else:
            state_dict['known location'] = True
    else:
        asyncio.ensure_future(
            filter_print(
                output_text="Something is in the way."
            )
        )

def get_relative_ui_coord(x_offset, y_offset):
    width, height = term.width, term.height
    x_return, y_return = 0, 0
    if x_offset < 0:
        x_return = width + x_offset
    else:
        x_return = x_offset
    if y_offset < 0:
        y_return = height + y_offset
    else:
        y_return = y_offset
    return x_return, y_return

async def printing_testing(distance=0, x_offset=-45, y_offset=1):
    x_coord, y_coord = get_relative_ui_coord(x_offset, y_offset)
    for number in range(10):
        with term.location(number + x_coord, 2 + y_coord):
            print(term.color(number)(str(number)))
        with term.location(number + x_coord, 3 + y_coord):
            print(term.on_color(number)(str(number)))

async def status_bar(
    actor_name='player',
    attribute='health',
    x_offset=0,
    y_offset=0,
    centered=True, 
    bar_length=20,
    title=None,
    refresh_time=.1,
    max_value=100,
    bar_color=1
):
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

async def player_coord_readout(
    x_offset=0, y_offset=0, refresh_time=.1, centered=True
):
    if centered:
        middle_x, middle_y = (int(term.width / 2), int(term.height / 2))
        print_coord = (middle_x - x_offset, middle_y + y_offset)
    state_dict['display_offset'] = [0, 0, 0]
    while True:
        await asyncio.sleep(refresh_time)
        player_coords = actor_dict['player'].coords()
        if state_dict['plane'] == 'normal':
            x_offset, y_offset, z_offset = state_dict['display_offset']
            display_x, display_y = add_coords((x_offset, y_offset), player_coords)
            display_z = state_dict['display_offset'][2]
            printed_coords = (display_x, display_y, display_z)
        else:
            noise = "1234567890ABCDEF       ░░░░░░░░░░░ " 
            printed_coords = [''.join([choice(noise) for _ in range(2)]) for _ in range(3)]
        with term.location(*add_coords(print_coord, (0, 1))):
            print("x:{} y:{} z:{}     ".format(*printed_coords))

async def ui_setup():
    """
    lays out UI elements to the screen at the start of the program.
    """
    loop = asyncio.get_event_loop()
    loop.create_task(angle_swing())
    loop.create_task(crosshairs())
    loop.create_task(console_box())
    loop.create_task(display_items_at_coord())
    loop.create_task(display_items_on_actor())
    loop.create_task(key_slot_checker(slot='q', print_location=(46, 5)))
    loop.create_task(key_slot_checker(slot='e', print_location=(52, 5)))
    #loop.create_task(tile_debug_info())
    health_title = "{} ".format(term.color(1)("♥"))
    loop.create_task(
        status_bar(
            y_offset=18,
            actor_name='player',
            attribute='health',
            title=health_title,
            bar_color=1
        )
    )
    loop.create_task(player_coord_readout(x_offset=10, y_offset=18))

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
    if is_passable(next_position):
        return next_position
    else:
        return x_current, y_current

async def delay_follow(
    name_key='player', window_length=20, speed=.05, delay_offset=10
):
    """
    Creates a static actor that follows the path of the specified actor.

    In its default state, it makes a dark space that follows you a little 
    too slowly.
    """
    moves = [[None, None]] * window_length
    grab_index = 0
    delay_index = delay_offset
    current_coords = actor_dict[name_key].coords()
    delay_id = spawn_static_actor(
        base_name='static',
        spawn_coord=current_coords, 
        tile=' ',
        breakable=False,
        moveable=False,
        multi_tile_parent=None, 
        blocking=False, 
        literal_name=False,
        description='Your shadow.'
    )
    while True:
        await asyncio.sleep(speed)
        grab_index = (grab_index + 1) % window_length
        delay_index = (delay_index + 1) % window_length
        moves[grab_index] = actor_dict[name_key].coords()
        if None not in moves[delay_index]:
            actor_dict[delay_id].update(moves[delay_index])

async def attack(
    attacker_key=None, defender_key=None, blood=True, spatter_range=(1, 3)
):
    attacker_strength = actor_dict[attacker_key].base_attack
    target_coord = actor_dict[defender_key].coords()
    if blood:
        await sow_texture(
            root_coord=target_coord,
            radius=3,
            paint=True,
            seeds=randint(*spatter_range),
            description="Blood.", 
            append_description=True
        )
    if defender_key == 'player':
        asyncio.ensure_future(
            append_to_log(
                "The {} hits you for {} damage!".format(
                    actor_dict[attacker_key].base_name,
                    attacker_strength,
                )
            )
        )
    actor_dict[defender_key].health -= attacker_strength
    if actor_dict[defender_key].health <= 0:
        actor_dict[defender_key].health = 0
    asyncio.ensure_future(directional_alert(source_actor=attacker_key))

async def seek_actor(name_key=None, seek_key='player', repel=False):
    current_coord = actor_dict[name_key].coords()
    target_coord = actor_dict[seek_key].coords()
    is_hurtful = actor_dict[name_key].hurtful
    current_distance = point_to_point_distance(current_coord, target_coord)
    if is_hurtful and current_distance <= 1:
        await attack(attacker_key=name_key, defender_key=seek_key)
    eight_offsets = [
        dir_to_offset(offset) for offset in (
            'n', 'e', 's', 'w', 'ne', 'se', 'sw', 'nw'
        )
    ]
    eight_adjacencies = [
        add_coords(current_coord, offset) for offset in eight_offsets
    ]
    open_spaces = list(filter(
        lambda coord: is_passable(coord) == True,
        eight_adjacencies
    ))
    distances = [
        point_to_point_distance(coord, target_coord) for coord in open_spaces
    ]
    if distances == []:
        return current_coord
    if repel:
        output_index = distances.index(max(distances))
    else:
        output_index = distances.index(min(distances))
    return open_spaces[output_index]

def offset_to_dir(offset):
    dir_of_travel = {
        (0, -1): 'n',
        (1, 0): 'e',
        (0, 1): 's',
        (-1, 0): 'w',
        (1, -1): 'ne',
        (1, 1): 'se',
        (-1, 1): 'sw',
        (-1, -1): 'nw',
    }
    return dir_of_travel[offset]

def adjacent_tiles(coord=(0, 0)):
    surrounding_coords = [
        add_coords(coord, dir_to_offset(offset)) for offset in (
            'n', 'e', 's', 'w', 'ne', 'se', 'sw', 'nw'
        )
    ]
    return surrounding_coords

def opposite_dir(dir_string='n'):
    """
    Returns the opposite cardinal direction.
    """
    opposites = {
        'n' :'s',
        'e' :'w',
        's' :'n',
        'w' :'e',
        'ne':'sw',
        'se':'nw',
        'sw':'ne',
        'nw':'se',
    }
    return opposites[dir_string]

def dir_to_offset(dir_string='n', inverse=False):
    if inverse:
        dir_string = opposite_dir(dir_string)
    dirs_to_offsets = {
        'n' :(0, -1),
        'e' :(1, 0),
        's':(0, 1),
        'w':(-1, 0),
        'ne':(1, -1),
        'se':(1, 1),
        'sw':(-1, 1),
        'nw':(-1, -1),
    }
    return dirs_to_offsets[dir_string]

def scaled_dir_offset(dir_string='n', scale_by=5):
    dir_offset = dir_to_offset(dir_string)
    return (dir_offset[0] * scale_by, dir_offset[1] * scale_by)

async def wait(name_key=None, **kwargs):
    """
    Takes no action. Stays in place.
    """
    actor_location = actor_dict[name_key].coords()
    return actor_location

async def waver(name_key=None, seek_key='player', **kwargs):
    """
    Modifies the behavior of a terminal

    Seeks player if out of sight, flees if within fov of player
    """
    actor_location = actor_dict[name_key].coords()
    within_fov = check_point_within_arc(
        checked_point=actor_location, arc_width=120
    )
    distance_to_player = distance_to_actor(actor_a=name_key, actor_b='player')
    if distance_to_player >= 15:
        movement_choice = await wander(name_key=name_key)
    elif within_fov and distance_to_player < 10:
        movement_choice = await seek_actor(
            name_key=name_key, seek_key=seek_key, repel=True
        )
    else:
        movement_choice = await seek_actor(
            name_key=name_key, seek_key=seek_key, repel=False
        )
    return movement_choice

async def angel_seek(name_key=None, seek_key='player'):
    """
    Seeks only when the player isn't looking.
    """
    actor_location = actor_dict[name_key].coords()
    within_fov = check_point_within_arc(
        checked_point=actor_location, arc_width=120
    )
    if within_fov:
        movement_choice = actor_location
    else:
        movement_choice = await seek_actor(
            name_key=name_key, seek_key=seek_key, repel=False
        )
    return movement_choice

def fuzzy_forget(name_key=None, radius=3, forget_count=5):
    """
    The actor leaves a trail of tiles that are forgotten from the player's 
    memory.
    """
    actor_location = actor_dict[name_key].coords()
    for _ in range(forget_count):
        rand_point = point_within_circle(radius=radius, center=actor_location)
        map_dict[rand_point].seen = False

#misc utility functions---------------------------------------------------------
def add_coords(coord_a=(0, 0), coord_b=(10, 10)):
    output = (coord_a[0] + coord_b[0],
              coord_a[1] + coord_b[1])
    return output

def diff_coords(coord_a=(0, 0), coord_b=(10, 10)):
    output = (coord_a[0] - coord_b[0],
              coord_a[1] - coord_b[1])
    return output

def invert_coords(coord):
    return(-coord[0], -coord[1])

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
async def tentacled_mass(
    start_coords=(-5, -5),
    speed=1,
    tentacle_length_range=(3, 8),
    tentacle_rate=.1,
    tentacle_colors="456"
):
    """
    creates a (currently) stationary mass of random length and color tentacles
    move away while distance is far, move slowly towards when distance is near, radius = 20?
    """
    tentacled_mass_id = generate_id(base_name='tentacled_mass')
    actor_dict[tentacled_mass_id] = Actor(
        name=tentacled_mass_id,
        moveable=False,
        tile='*',
        is_animated=True,
        animation=Animation(preset='mouth'),
    )
    actor_dict[tentacled_mass_id].update(coord=start_coords)
    current_coord = start_coords
    while True:
        await asyncio.sleep(tentacle_rate)
        current_coord = await choose_core_move(
            core_name_key=tentacled_mass_id, tentacles=False
        )
        if current_coord:
            actor_dict[tentacled_mass_id].update(coord=current_coord)
        actor_dict[tentacled_mass_id].update(coord=current_coord)
    
async def shrouded_horror(
    start_coords=(0, 0),
    speed=.1,
    shroud_pieces=50,
    core_name_key="shrouded_horror"
):
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
    core_location = start_coords
    actor_dict[core_name_key] = Actor(
        name=core_name_key, moveable=False, tile=' '
    )
    actor_dict[core_name_key].update(coord=core_location)
    shroud_locations = [start_coords] * shroud_pieces
    #initialize segment actors:
    shroud_piece_names = []
    for number, shroud_coord in enumerate(shroud_locations):
        shroud_piece_names.append("{}_piece_{}".format(core_name_key, number))
    for number, name in enumerate(shroud_piece_names):
        actor_dict[name] = Actor(
            name=name,
            moveable=True,
            coord=start_coords,
            tile=' '
        )
    wait = 0
    while True:
        await asyncio.sleep(speed)
        for offset, shroud_name_key in enumerate(shroud_piece_names):
            #deleting instance of the shroud pieces from the map_dict's actor list:
            new_coord = await choose_shroud_move(
                shroud_name_key=shroud_name_key, core_name_key=core_name_key
            )
            if new_coord:
                actor_dict[shroud_name_key].update(coord=new_coord)
        core_location = actor_dict[core_name_key].coords()
        if wait > 0:
            wait -= 1
        else:
            new_core_location = await choose_core_move(
                core_name_key=core_name_key
            )
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
        asyncio.ensure_future(
            follower_vine(
                root_node_key=core_name_key,
                color_choice=2
            )
        )
    elif core_behavior_val > .4:
        new_core_location = await wander(name_key=core_name_key)
    else:
        new_core_location = await seek_actor(
            name_key=core_name_key, seek_key="player"
        )
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
        new_shroud_location = await seek_actor(
            name_key=shroud_name_key, seek_key=core_name_key
        )
    return new_shroud_location

async def basic_actor(
    coord=(0, 0),
    speed=1,
    tile="*", 
    movement_function=wander,
    name_key="test",
    base_name="test",
    hurtful=False,
    base_attack=5,
    is_animated=False,
    animation=" ",
    holding_items=[],
    movement_function_kwargs={},
    description='A featureless blob'
):
    """
    actors can:
    move from square to square using a movement function
    hold items
    attack or interact with the player
    die
    exist for a set number of turns
    """
    actor_dict[(name_key)] = Actor(
        name=name_key,
        base_name=base_name,
        coord=coord,
        speed=speed,
        tile=tile,
        hurtful=hurtful, 
        leaves_body=True,
        base_attack=base_attack, 
        is_animated=is_animated,
        animation=animation,
        holding_items=holding_items,
        description=description
    )
    coords = actor_dict[name_key].coords()
    while True:
        if actor_dict[name_key].health <= 0:
            await kill_actor(name_key=name_key)
            return
        await asyncio.sleep(speed)
        next_coords = await movement_function(
            name_key=name_key, **movement_function_kwargs
        )
        #checked again here because actors can be pushed around
        current_coords = actor_dict[name_key].coords()
        if current_coords != next_coords:
            dist_to_player = distance_to_actor(name_key, 'player')
            noise_level = (1 / dist_to_player ** 2) * 10
            if random() <= noise_level:
                asyncio.ensure_future(
                    directional_alert(source_actor=name_key, preset='footfall')
                )
            if name_key in map_dict[current_coords].actors:
                del map_dict[current_coords].actors[name_key]
            map_dict[next_coords].actors[name_key] = True
            actor_dict[name_key].update(coord=next_coords)

def distance_to_actor(actor_a=None, actor_b='player'):
    if actor_a is None:
        return 0
    a_coord = actor_dict[actor_a].coords()
    b_coord = actor_dict[actor_b].coords()
    return point_to_point_distance(a_coord, b_coord)

async def kill_actor(name_key=None, leaves_body=True, blood=True):
    actor_coords = actor_dict[name_key].coords()
    holding_items = actor_dict[name_key].holding_items
    if leaves_body:
        body_tile = term.red(actor_dict[name_key].tile)
        name_temp = actor_dict[name_key].base_name
    if actor_dict[name_key].multi_tile_parent is not None:
        parent_name = actor_dict[name_key].multi_tile_parent
        actor_index = mte_dict[parent_name].member_names.index(name_key)
        del mte_dict[parent_name].member_names[actor_index]
        for entry in mte_dict[parent_name].member_data.values():
            if name_key in entry.values():
                segment_key = entry['offset']
        #delete MTE segment then try to split remaining segments:
        del mte_dict[parent_name].member_data[segment_key]
        mte_dict[parent_name].split_along_subregions()
    del map_dict[actor_coords].actors[name_key]
    del actor_dict[name_key]
    if blood:
        await sow_texture(
            root_coord=actor_coords,
            radius=3,
            paint=True,
            seeds=5,
            description="Blood."
        )
    if leaves_body:
        map_dict[actor_coords].tile = body_tile
        map_dict[actor_coords].description = "A dead {}.".format(name_temp)
    spawn_item_spray(base_coord=actor_coords, items=holding_items)
    return

def spawn_item_spray(base_coord=(0, 0), items=[], random=False, radius=1):
    if items is None:
        return
    loop = asyncio.get_event_loop()
    circle_points = get_circle(center=base_coord, radius=radius)
    coord_choices = [
        point for point in circle_points if map_dict[point].passable
    ]
    for item in items:
        item_coord = choice(coord_choices)
        spawn_item_at_coords(coord=item_coord, instance_of=item)

async def follower_vine(
    spawn_coord=None,
    num_segments=10,
    base_name='mte_vine',
    root_node_key=None,
    facing_dir='e',
    update_period=.2,
    color_choice=None
):
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
    vine_name = await spawn_mte(
        base_name=base_name, spawn_coord=current_coord, preset='empty',
    )
    vine_id = generate_id(base_name='')
    for number in range(num_segments):
        mte_dict[vine_name].add_segment(
            segment_tile='x',
            write_coord=current_coord,
            offset=(0, 0),
            segment_name=f'{vine_id}_segment_{number}'
        )
    mte_dict[vine_name].vine_instructions = "M" * num_segments
    mte_dict[vine_name].vine_facing_dir = facing_dir
    #TODO: remove next six lines
    #direction_offsets = {
        #'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),
    ##}
    #inverse_direction_offsets = {
        #'n':(0, 1), 'e':(-1, 0), 's':(0, -1), 'w':(1, 0),
    #}
    if color_choice is None:
        color_choice = choice((1, 2, 3, 4, 5, 6, 7))
    while True:
        await asyncio.sleep(update_period)
        mte_dict[vine_name].vine_instructions = mte_vine_animation_step(
            mte_dict[vine_name].vine_instructions
        )
        write_dir = mte_dict[vine_name].vine_facing_dir
        if root_node_key is None:
            current_coord = add_coords(
                dir_to_offset(write_dir, inverse=True), 
                actor_dict[mte_dict[vine_name].member_names[0]].coords()
            )
        else:
            current_coord = add_coords(
                dir_to_offset(write_dir, inverse=True), 
                actor_dict[root_node_key].coords()
            )
        write_list = [] #clear out write_list
        next_offset = dir_to_offset(write_dir)
        write_coord = add_coords(next_offset, current_coord)
        instructions = mte_dict[vine_name].vine_instructions
        dir_increment = {'L':-1, 'M':0, 'R':1}
        for turn_instruction in instructions:
            prev_dir = write_dir
            write_dir = num_to_facing_dir(
                facing_dir_to_num(write_dir) + dir_increment[turn_instruction]
            )
            next_offset = dir_to_offset(write_dir)
            segment_tile = choose_vine_tile(prev_dir, write_dir)
            write_list.append((write_coord, segment_tile)) #add to the end of write_list
            write_coord = add_coords(next_offset, write_coord) #set a NEW write_coord here
        member_names = mte_dict[vine_name].member_names
        for segment_name, (write_coord, segment_tile) in zip(member_names, write_list):
            actor_dict[segment_name].update(coord=write_coord, make_passable=False)
            actor_dict[segment_name].tile = segment_tile
            actor_dict[segment_name].tile_color = color_choice

def rand_swap_on_pattern(
    input_string='LRLRLRLR',
    pattern='LRL',
    replacements=('LLL', 'MMM', 'RRR'),
    debug=False
):
    """
    Finds and replaces a randomly chosen matching substring of an instruction
    list ('L', 'M' or 'R') and swaps it for a randomly chosen replacement.
    """
    match_indexes = [
        match.span() for match in re.finditer(pattern, input_string)
    ]
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
    swaps = {
        'LRM':('MLR',),
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
        'MLM':('LRL'),
    }
    swap_choices = [
        pattern for pattern in swaps.keys() if pattern in instructions
    ]
    if type(swap_choices) == str:
        swap_choice = swap_choices
    else:
        swap_choice = choice(swap_choices)
    new_instructions = rand_swap_on_pattern(
        input_string=instructions, 
        pattern=swap_choice,
        replacements=swaps[swap_choice], 
        debug=debug
    )
    return new_instructions

def choose_vine_tile(prev_dir=1, next_dir=2, rounded=True, color_num=8):
    if prev_dir in 'nesw':
        prev_dir = facing_dir_to_num(prev_dir)
    if next_dir in 'nesw':
        next_dir = facing_dir_to_num(next_dir)
    straight_vine_picks = {
        (0, 1):'┌', (3, 2):'┌', (1, 2):'┐', (0, 3):'┐', (0, 0):'│', (2, 2):'│',
        (2, 3):'┘', (1, 0):'┘', (2, 1):'└', (3, 0):'└', (1, 1):'─', (3, 3):'─',
    }
    rounded_vine_picks = {
        (0, 1):'╭', (3, 2):'╭', (1, 2):'╮', (0, 3):'╮', (0, 0):'│', (2, 2):'│',
        (2, 3):'╯', (1, 0):'╯', (2, 1):'╰', (3, 0):'╰', (1, 1):'─', (3, 3):'─',
    }
    if rounded:
        tile_choice = rounded_vine_picks[(prev_dir, next_dir)]
    else:
        tile_choice = straight_vine_picks[(prev_dir, next_dir)]
    return tile_choice

async def health_potion(
    item_id=None,
    actor_key='player',
    total_restored=25,
    duration=2,
    sub_second_step=.1
):
    if item_id:
        del item_dict[item_id]
        del actor_dict['player'].holding_items[item_id]
    num_steps = duration / sub_second_step
    health_per_step = total_restored / num_steps
    asyncio.ensure_future(
        damage_numbers(
            actor='player', damage=-total_restored
        )
    )
    for i in range(int(num_steps)):
        await asyncio.sleep(sub_second_step)
        asyncio.ensure_future(
            directional_alert(source_actor='player', preset='heal')
        )
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
    points_at_distance = {
        point_at_distance_and_angle(
            radius=radius, central_point=player_coords, angle_from_twelve=angle
        ) for angle in every_five
    }
    state_dict['bubble_cooldown'] = True
    for num, point in enumerate(points_at_distance):
        actor_name = 'bubble_{}_{}'.format(bubble_id, num)
        asyncio.ensure_future(
            timed_actor(
                name=actor_name,
                coords=(point),
                rand_delay=.3,
                death_clock=duration
            )
        )
    await asyncio.sleep(duration)
    state_dict['bubble_cooldown'] = False
    return True

async def points_at_distance(radius=5, central_point=(0, 0)):
    every_five = [i * 5 for i in range(72)]
    points = []
    for angle in every_five:
        point = point_at_distance_and_angle(
            radius=radius, 
            central_point=player_coords, 
            angle_from_twelve=angle
        )
        points.append(point)
    return set(points)

async def timed_actor(
    death_clock=10,
    name='timed_actor',
    coords=(0, 0),
    rand_delay=0,
    solid=True,
    moveable=False, 
    animation_preset='shimmer',
    vanish_message=None,
):
    """
    spawns an actor at given coords that disappears after a number of turns.
    """
    if name == 'timed_actor':
        name = name + generate_id(base_name='')
    if rand_delay:
        await asyncio.sleep(random() * rand_delay)
    actor_dict[name] = Actor(
        name=name,
        moveable=moveable,
        coord=coords,
        tile=str(death_clock),
        is_animated=True,
        animation=Animation(preset=animation_preset)
    )
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
    if vanish_message is not None:
        await append_to_log(message=vanish_message)

async def beam_spire(spawn_coord=(0, 0)):
    """
    spawns a rotating flame source
    """
    closed_tile = term.on_color(7)(term.color(0)('◫'))
    open_tile = term.on_color(7)(term.color(0)('◼'))
    turret_id = generate_id(base_name='turret')
    actor_dict[turret_id] = Actor(
        name=turret_id, moveable=False, tile=closed_tile
    )
    actor_dict[turret_id].update(coord=spawn_coord)
    while True:
        for angle in [i * 5 for i in range(72)]:
            player_distance = distance_to_actor(actor_a=turret_id, actor_b='player')
            if player_distance < 40:
                for i in range(10):
                    asyncio.ensure_future(
                        fire_projectile(
                            actor_key=turret_id, firing_angle=angle
                        )
                    )
                    if random() <= .005:
                        rand_coord = add_coords(spawn_coord, (randint(-10, 10), randint(-10, 10)))
                        asyncio.ensure_future(
                            sound_message(
                                output_text=choice(("*FOOOM*", "*WHOOSH*", "*FSSST*", "*KRK*")),
                                sound_origin_coord=spawn_coord,
                                source_actor=None,
                                point_radius=18,
                                fade_duration=1,
                            )
                        )
            await asyncio.sleep(.1)

async def flame_jet(
    origin=(-9, 3),
    facing='e',
    duration=1,
    reach=10,
    rate=.1,
    spread=10,
):
    particle_count = round(duration / rate)
    base_angle = dir_to_angle(facing)
    for i in range(particle_count):
        rand_angle = randint(-spread, spread) + base_angle
        asyncio.ensure_future(
            fire_projectile(
                start_coords=origin, firing_angle=rand_angle
            )
        )
        await asyncio.sleep(rate)

async def fire_projectile(
    start_coords=(0, 0),
    actor_key=None,
    firing_angle=45,
    radius=10, 
    radius_spread=(10, 14),
    degree_spread=(-30, 30),
    damage=5,
    animation_preset='explosion'
):
    rand_radius = randint(*radius_spread) + radius
    rand_angle = randint(*degree_spread) + firing_angle
    if actor_key is not None:
        start_coords = actor_dict[actor_key].coords()
    x_shift, y_shift = point_given_angle_and_radius(
        angle=rand_angle, radius=rand_radius
    )
    end_coords = add_coords(start_coords, (x_shift, y_shift))
    await travel_along_line(
        name='particle', 
        start_coords=start_coords, 
        end_coords=end_coords, 
        damage=damage, 
        animation=Animation(preset=animation_preset), 
        ignore_head=True,
        source_actor=actor_key
    )

def point_given_angle_and_radius(angle=0, radius=10):
    x = round(cos(radians(angle)) * radius)
    y = round(sin(radians(angle)) * radius)
    return x, y

def angle_point_to_point(
    coord_a=(0, 0), coord_b=(3, 3), actor_a=None, actor_b=None
):
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
    if actor_a:
        coord_a = actor_dict[actor_a].coords()
    if actor_b:
        coord_b = actor_dict[actor_b].coords()
    x_run, y_run = (
        coord_a[0] - coord_b[0],
        coord_a[1] - coord_b[1]
    )
    hypotenuse = sqrt(x_run ** 2 + y_run ** 2)
    if hypotenuse == 0:
        return 0
    a_angle = degrees(acos(y_run/hypotenuse))
    if x_run > 0:
        a_angle = 360 - a_angle
    return a_angle

async def travel_along_line(
    name='particle',
    start_coords=(0, 0),
    end_coords=(10, 10),
    speed=.05,
    tile="X",
    animation=Animation(preset='explosion'),
    debris=None,
    damage=None,
    ignore_head=False,
    no_clip=True,
    source_actor=None
):
    points = get_line(start_coords, end_coords)
    if no_clip:
        for index, point in enumerate(points):
            not_passable = not map_dict[point].passable
            no_actors = len(map_dict[point].actors) == 0
            if not_passable and no_actors:
                points = points[:index] #trim points past first wall found
                break
        if len(points) < 1:
            return
    particle_id = generate_id(base_name=name)
    if animation:
        is_animated = True
    else:
        is_animated = False
    actor_dict[particle_id] = Actor(
        name=particle_id,
        coord=start_coords,
        tile=tile,
        moveable=False,
        is_animated=is_animated,
        animation=animation
    )
    map_dict[start_coords].actors[particle_id] = True
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
            await damage_all_actors_at_coord(
                coord=point, damage=damage, source_actor=source_actor
            )
        last_location = actor_dict[particle_id].coords()
    if debris:
        if random() > .8:
            map_dict[last_location].tile = choice(debris)
            map_dict[last_location].description = "Debris."
    del map_dict[last_location].actors[particle_id]
    del actor_dict[particle_id]

async def radial_fountain(
    anchor_actor='player',
    tile_anchor=None,
    angle_range=(0, 360),
    frequency=.1,
    radius=(3, 30),
    speed=(1, 7),
    collapse=True,
    debris=None,
    deathclock=None,
    animation=Animation(preset='water')
):
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
        point = point_at_distance_and_angle(
            angle_from_twelve=rand_angle, 
            central_point=origin_coord,
            reference_point=reference, 
            radius=rand_radius
        )
        if collapse:
            start_coords, end_coords = point, origin_coord
        else:
            start_coords, end_coords = origin_coord, point
        asyncio.ensure_future(
            travel_along_line(
                start_coords=start_coords, 
                end_coords=end_coords,
                debris=debris,
                animation=animation
            )
        )
        if deathclock:
            deathclock -= 1
            if deathclock <= 0:
                break

async def dash_along_direction(
    actor_key='player', direction='n', distance=10, time_between_steps=.03
):
    current_coord = actor_dict[actor_key].coords()
    direction_step = dir_to_offset(direction)
    scaled_offset = scaled_dir_offset(dir_string=direction, scale_by=distance)
    destination = add_coords(current_coord, scaled_offset)
    coord_list = get_line(current_coord, destination)
    await move_through_coords(
        actor_key=actor_key,
        coord_list=coord_list,
        time_between_steps=time_between_steps
    )

async def move_through_coords(
    actor_key=None, coord_list=[(i, i) for i in range(10)],
    drag_through_solid=False,
    time_between_steps=.1
):
    """
    Takes a list of coords and moves the actor along them.
    if apply_offset is True, the path starts at actor's current location.
    drag_through solid toggles whether solid obstacles stop the motion.
    """
    steps = await path_into_steps(coord_list)
    for step in steps:
        actor_coords = actor_dict[actor_key].coords()
        new_position = add_coords(actor_coords, step)
        if is_passable(new_position) and not drag_through_solid:
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

async def orbit(
    name='particle',
    radius=5,
    degrees_per_step=1,
    on_center=(0, 0), 
    rand_speed=False,
    track_actor=None, 
    sin_radius=False,
    sin_radius_amplitude=3
):
    """
    generates an actor that orbits about a point
    TODO: particles that follow an arbitrary path
    """
    angle = randint(0, 360)
    particle_id = generate_id(base_name=name)
    actor_dict[particle_id] = Actor(
        name=particle_id,
        coord=on_center,
        moveable=False,
        is_animated=True,
        animation=Animation(base_tile='◉', preset='shimmer')
    )
    map_dict[on_center].actors[particle_id] = True
    point_coord = actor_dict[particle_id].coords()
    original_radius = radius
    if sin_radius:
        # a cyclical generator expression for each value in 360.
        sin_cycle = (
            (sin(radians(i)) * sin_radius_amplitude) + original_radius 
            for i in cycle(range(360))
        )
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
        point_coord = point_at_distance_and_angle(
            radius=radius, central_point=on_center, angle_from_twelve=angle
        )
        if point_coord != last_location:
            actor_dict[particle_id].update(coord=point_coord)
            last_location = actor_dict[particle_id].coords()
        map_dict[last_location].actors[particle_id] = True
        angle = (angle + degrees_per_step) % 360

async def death_check():
    player_health = actor_dict["player"].health
    middle_x, middle_y = (
        int(term.width / 2 - 2), int(term.height / 2 - 2),
    )
    death_message = "You have died."
    while True:
        await asyncio.sleep(0.1)
        player_health = actor_dict["player"].health
        if player_health <= 0:
            asyncio.ensure_future(
                filter_print(
                    pause_stay_on=99, output_text=death_message
                )
            )
            await asyncio.sleep(3)
            state_dict['killall'] = True

async def spawn_preset_actor(
    coords=(0, 0), preset='blob', speed=1, holding_items=[]
):
    """
    spawns an entity with various presets based on preset given.
    """
    loop = asyncio.get_event_loop()
    actor_id = generate_id(base_name=preset)
    name = "{}_{}".format(preset, actor_id)
    start_coords = coords
    if preset == 'blob':
        item_drops = ['red potion']
        description = 'A gibbering mass of green slime that pulses and writhes before your eyes.'
        loop.create_task(
            basic_actor(
                coord=coords,
                speed=.3,
                movement_function=waver, 
                tile='ö',
                name_key=name,
                base_name=preset,
                hurtful=True,
                base_attack=5,
                is_animated=True,
                animation=Animation(preset="blob"),
                holding_items=item_drops,
                description=description
            )
        )
    elif preset == 'angel':
        item_drops = ['dash trinket']
        loop.create_task(
            basic_actor(
                coord=coords,
                speed=.15,
                movement_function=angel_seek, 
                tile='A',
                name_key=name,
                hurtful=True,
                base_attack=20,
                is_animated=None,
                holding_items=item_drops,
            )
        )
    elif preset == 'test':
        item_drops = ['nut']
        loop.create_task(
            basic_actor(
                coord=coords,
                speed=.75,
                movement_function=seek_actor, 
                tile='?',
                name_key=name,
                hurtful=True,
                base_attack=10,
                is_animated=True,
                animation=Animation(preset="mouth"),
                holding_items=item_drops
            )
        )
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
    await asyncio.sleep(random()) #stagger starting update times
    if player_position_offset == (0, 0):
        blink_switch = cycle((0, 1))
    else:
        blink_switch = repeat(1)
    while True:
        await asyncio.sleep(random()/2)
        if state_dict['scanner_state'] == False:
            with term.location(*display_coord):
                print(' ')
            continue
        player_coord = actor_dict['player'].coords()
        bin_string = ''.join([
            one_for_passable(add_coords(player_coord, coord)) 
            for coord in listen_coords
        ])
        actor_presence = any(
            map_dict[add_coords(player_coord, coord)].actors
            for coord in listen_coords
        )
        state_index = int(bin_string, 2)
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

async def door_init(loop):
    door_pairs = (
        bay_door_pair(
            (-10, -2),
            (-10, 2),
            #patch_to_key='bay_door_pair_1',
            patch_to_key='computer_test',
            preset='thick',
            pressure_plate_coord=((-7, 0), (-13, 0)),
            message_preset='ksh'
        ),
        bay_door_pair(
            (-27, 21),
            (-14, 21),
            patch_to_key='bay_door_pair_3',
            preset='thick',
            pressure_plate_coord=(-20, 18),
            message_preset='ksh'
        ),
        bay_door_pair(
            (4, -25),
            (8, -25),
            patch_to_key='bay_door_pair_4',
            preset='thick',
            pressure_plate_coord=((6, -23), (6, -27)),
            message_preset='ksh'
        )
    )
    #loop through the above coroutines:
    for door_pair in door_pairs:
        loop.create_task(door_pair)

def state_setup():
    state_dict['just teleported'] = False
    state_dict["player_health"] = 100
    state_dict['facing'] = 'w'
    state_dict['menu_choices'] = []
    state_dict['plane'] = 'normal'
    state_dict['printing'] = False
    state_dict['known location'] = True
    state_dict['teleporting'] = False
    state_dict['view_tile_count'] = 0
    state_dict['scanner_state'] = False
    state_dict['lock view'] = False

def main():
    state_setup()
    map_init()
    old_settings = termios.tcgetattr(sys.stdin) 
    loop = asyncio.new_event_loop()
    tasks = (
        get_key(map_dict),
        view_tile_init(loop),
        quitter_daemon(),
        minimap_init(loop),
        ui_setup(),
        #printing_testing(),
        #TODO: fix follower vine to disappear after a set time:
        #shrouded_horror(start_coords=(29, -25)),
        death_check(),
        under_passage(),
        #display_current_tile(), #debug for map generation
        door_init(loop),
        async_map_init(),
        computer_terminal(spawn_coord=(-4, -5), patch_to_key='computer_test'),
        teleporter(),
        hatch_pair(),
        teleporting_hatch(
            destination_coords=(1000, 1001),
            use_offset=(-1000, -1000, -1),
            player_facing_end='s',
        ),
        teleporting_hatch(
            hatch_coords=(1000, 1000), 
            use_offset=(0, 0, 0), 
            destination_coords=(26, 1), 
            player_facing_end='w',
            ladder=True,
        ),
        indicator_lamp(spawn_coord=(-10, -3), patch_to_key='computer_test'),
        proximity_trigger(coord_a=(13, -2), coord_b=(13, 2), patch_to_key='line_test'),
        indicator_lamp(spawn_coord=(9, 1), patch_to_key='line_test'),
        alarm_bell(spawn_coord=(12, -1), patch_to_key='line_test', silent=True),
    )
    for task in tasks:
        loop.create_task(task)
    asyncio.set_event_loop(loop)
    result = loop.run_forever()

with term.hidden_cursor():
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        main()
    finally: 
        clear()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings) 
