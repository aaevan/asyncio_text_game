import asyncio
import sys
import select 
import tty 
import termios
from copy import copy, deepcopy
from blessings import Terminal
from collections import defaultdict
from datetime import datetime
from random import randint, choice, random, shuffle
from math import acos, cos, degrees, pi, radians, sin, sqrt
from itertools import cycle
from subprocess import call
import os

#Class definitions--------------------------------------------------------------


class Map_tile:
    """ holds the status and state of each tile. """
    def __init__(self, passable=True, tile="⣿", blocking=True, 
                 description='', announcing=False, seen=False, 
                 announcement="", distance_trigger=None, is_animated=False,
                 animation="", actors=None, items=None, 
                 magic=False, magic_destination=False, 
                 mutable=True, 
                 is_door=False, locked=False, key=''):
        """ create a new map tile, map_dict holds tiles.
        A Map_tile is accessed from map_dict via a tuple key, ex. (0, 0).
        The tile representation of Map_tile at coordinate (0, 0) is accesed 
        with map_dict[(0, 0)].tile.
        actors is a dictionary of actor names with value == True if 
                occupied by that actor, otherwise the key is deleted.
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
        self.mutable = mutable
        self.is_door = is_door
        self.locked = locked
        self.key = key

class Actor:
    """ the representation of a single actor that lives on the map. """
    def __init__(self, name='', x_coord=0, y_coord=0, speed=.2, tile="?", strength=1, 
                 health=50, hurtful=True, moveable=True, is_animated=False,
                 animation="", holding_items={}, leaves_body=False,
                 breakable=False):
        self.name = name
        self.x_coord, self.y_coord, = (x_coord, y_coord)
        self.speed, self.tile = (speed, tile)
        self.coord = (x_coord, y_coord)
        self.strength, self.health, self.hurtful = strength, health, hurtful
        self.max_health = self.health #max health is set to starting value
        self.alive = True
        self.moveable = moveable
        self.is_animated = is_animated
        self.animation = animation
        self.leaves_body = leaves_body
        self.holding_items = holding_items
        self.breakable = breakable

    def update(self, x, y):
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
                  'water':{'animation':'▒▓▓▓████', 
                           'behavior':'random',
                           'color_choices':('4'*10 + '6')},
                  'grass':{'animation':('▒' * 20 + '▓'), 
                           'behavior':'random',
                           'color_choices':('2'),},
                   'blob':{'animation':('ööööÖ'),
                           'behavior':'loop tile',
                           'color_choices':('2')},
                  'mouth':{'animation':('▲▸▼◀'),
                           'behavior':'loop tile',
                           'color_choices':('456')},
                  #'noise':{'animation':('            ▒▓█▓▒'), 
                  'noise':{'animation':('      ▒▓▒ ▒▓▒'), 
                           'behavior':'loop tile', 
                           'color_choices':'1'},
           'sparse noise':{'animation':(' ' * 100 + '█▓▒'), 
                           'behavior':'random', 
                           'color_choices':'1' * 5 + '7'},
                'shimmer':{'animation':(base_tile), 
                           'behavior':'random', 
                           'color_choices':'1234567'},
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
                           'behavior':'loop both', 
                           'color_choices':'2'},
                 'spikes':{'animation':('∧∧∧∧‸‸‸     '), 
                           'behavior':'loop both', 
                           'color_choices':'7'},
                   'none':{'animation':(' '), 
                           'behavior':'random', 
                           'color_choices':'1'}}
        #TODO: have color choices tied to a background/foreground color combination?
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
        #elif current_behavior['color'] == 'breathe':
            #TODO: implement forward and back looping
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
        await asyncio.sleep(0)
        if self.uses != None and not self.broken:
            await self.usable_power(**self.power_kwargs)
            if self.uses is not None:
                self.uses -= 1
            await filter_print(output_text=self.use_message)
            if self.uses <= 0:
                self.broken = True
        else:
            await filter_print(output_text="{}{}".format(self.name, self.broken_text))

#Global state setup-------------------------------------------------------------
term = Terminal()
map_dict = defaultdict(lambda: Map_tile(passable=False, blocking=True))
actor_dict = defaultdict(lambda: [None])
state_dict = defaultdict(lambda: None)
item_dict = defaultdict(lambda: None)
actor_dict['player'] = Actor(name='player', tile=term.red("@"), health=100)
actor_dict['player'].just_teleported = False
map_dict[actor_dict['player'].coords()].actors['player'] = True
state_dict['facing'] = 'n'
state_dict['menu_choices'] = []
state_dict['plane'] = 'normal'

bw_background_tile_pairs = ((0, ' '),       #dark
                            (7, "░"),
                            (8, "░"), 
                            (7, "▒"),
                            (8, "▒"), 
                            (7, "▓"), 
                            (7, "█"), 
                          *((8, "▓"),) * 2,
                          *((8, "█"),) * 6) #bright

bw_gradient = tuple([term.color(pair[0])(pair[1]) for pair in bw_background_tile_pairs])
#defined at top level as a dictionary for fastest lookup time
bright_to_dark = {num:val for num, val in enumerate(reversed(bw_gradient))}
 
#Drawing functions--------------------------------------------------------------
def draw_box(top_left=(0, 0), x_size=1, y_size=1, filled=True, 
             tile=".", passable=True):
    """ Draws a box to map_dict at the given coordinates."""
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

async def draw_circle(center_coord=(0, 0), radius=5, palette="░▒",
                passable=True, blocking=False, animation=None, delay=0):
    """
    draws a circle in real time. eats actors right now
    """
    await asyncio.sleep(0)
    for x in range(center_coord[0] - radius, center_coord[0] + radius):
        for y in range(center_coord[1] - radius, center_coord[1] + radius):
            await asyncio.sleep(delay)
            if not map_dict[(x, y)].mutable:
                continue
            distance_to_center = await point_to_point_distance(point_a=center_coord, point_b=(x, y))
            if animation:
                is_animated = True
            else:
                is_animated = False
            if distance_to_center <= radius:
                actors = map_dict[(x, y)].actors
                items = map_dict[(x, y)].items
                # a copy of the animation is made so each tile can have its own instance.
                map_dict[(x, y)] = Map_tile(passable=True, tile=choice(palette), blocking=False, 
                                            description=None, is_animated=is_animated,
                                            animation=copy(animation), actors=actors, items=items)


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
        points = await get_line(starting_point, destination)
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
                            end_coord=destination, speed=.05, tile=item_tile, 
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

async def damage_all_actors_at_coord(exclude=None, coord=(0, 0), damage=10):
    for actor in map_dict[coord].actors.items():
        if actor == exclude:
            continue
        await damage_actor(actor=actor[0], damage=damage, display_above=False)

async def damage_within_circle(center=(0, 0), radius=6, damage=75):
    area_of_effect = await get_circle(center=center, radius=radius)
    for coord in area_of_effect:
        await damage_all_actors_at_coord(coord=coord, damage=damage)

async def damage_actor(actor=None, damage=10, display_above=True):
    current_health = actor_dict[actor].health
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
    #TODO: implement dropping items for breakable actors.
    #TODO: create class for breakable/moveable scenery to 
    #      not overload Actor class?
    #if actor_dict[actor].health <= 0 and actor_dict[actor].breakable == True:
        #non-breakable actors are handled with basic_actor
        #await kill_actor(name_key=name_key)

async def damage_numbers(actor=None, damage=10, squares_above=5):
    actor_coords = actor_dict[actor].coords()
    digit_to_superscript = {'1':'¹', '2':'²', '3':'³', '4':'⁴', '5':'⁵',
                            '6':'⁶', '7':'⁷', '8':'⁸', '9':'⁹', '0':'⁰',
                            '-':'⁻', '+':'⁺'}
    #digit_to_subscript =   {'1':'₁', '2':'₂', '3':'₃', '4':'₄', '5':'₅', 
                            #'6':'₆', '7':'₇', '8':'₈', '9':'₉', '0':'₀',
                            #'-':'₋', '+':'₊'}
    if damage >= 0:
        damage = '-' + str(damage)
    else:
        damage = '+' + str(damage)[1:]
    for x_pos, digit in enumerate(damage):
        start_coord = actor_coords[0] + (x_pos - 1), actor_coords[1] - 1
        end_coord = start_coord[0], start_coord[1] - squares_above
        if damage[0] == '-':
            tile = term.red(digit_to_superscript[digit])
        else:
            tile = term.green(digit_to_superscript[digit])
        asyncio.ensure_future(travel_along_line(tile=tile,
                                                speed=.12,
                                                start_coord=start_coord, 
                                                end_coord=end_coord,
                                                debris=False,
                                                animation=False))

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

async def unlock_door(actor_key='player', opens='red'):
    directions = {'n':(0, -1), 'e':(1, 0), 's':(0, 1), 'w':(-1, 0),}
    check_dir = state_dict['facing']
    actor_coord = actor_dict[actor_key].coords()
    door_coord = (actor_coord[0] + directions[check_dir][0], 
                  actor_coord[1] + directions[check_dir][1])
    door_type = map_dict[door_coord].key
    if opens in map_dict[door_coord].key and map_dict[door_coord].is_door:
        if map_dict[door_coord].locked:
            output_text = "You unlock the {} door.".format(opens)
            map_dict[door_coord].locked = False
        elif not map_dict[door_coord].locked:
            output_text = "You lock the {} door.".format(opens)
            map_dict[door_coord].locked = True
    else:
        output_text = "Your {} key doesn't fit the {} door.".format(opens, door_type)
    asyncio.ensure_future(filter_print(output_text=output_text))

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
        return
    pushed_name = next(iter(map_dict[destination_coords].actors))
    if not actor_dict[pushed_name].moveable:
        return 0
    else:
        pushed_coords = actor_dict[pushed_name].coords()
        pushed_destination = (pushed_coords[0] + chosen_dir[0], 
                              pushed_coords[1] + chosen_dir[1])
        if not map_dict[pushed_destination].actors and map_dict[pushed_destination].passable:
            actor_dict[pushed_name].update(*pushed_destination)

async def follower_actor(name="follower", refresh_speed=.01, parent_actor='player', 
                         offset=(-1,-1), alive=True, tile=" "):
    await asyncio.sleep(refresh_speed)
    follower_id = await generate_id(base_name=name)
    actor_dict[follower_id] = Actor(name=follower_id, tile=tile)
    while alive:
        if state_dict['killall'] == True:
            break
        await asyncio.sleep(refresh_speed)
        parent_coords = actor_dict[parent_actor].coords()
        follow_x, follow_y = (parent_coords[0] + offset[0], 
                              parent_coords[1] + offset[1])
        actor_dict[follower_id].update(follow_x, follow_y)

async def circle_of_darkness(start_coord=(0, 0), name='darkness', circle_size=4):
    actor_id = await generate_id(base_name=name)
    loop = asyncio.get_event_loop()
    loop.create_task(basic_actor(*start_coord, speed=.5, movement_function=seek_actor, 
                                 tile=" ", name_key=actor_id, hurtful=True,
                                 is_animated=True, animation=Animation(preset="none")))
    await asyncio.sleep(0)
    range_tuple = (-circle_size, circle_size + 1)
    for x in range(*range_tuple):
        for y in range(*range_tuple):
            distance_to_center = await point_to_point_distance(point_a=(0, 0), 
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


async def sword(direction='n', actor='player', length=5, name='sword', 
                speed=.05, damage=100):
    """extends and retracts a line of characters
    TODO: end the range once it hits a wall
    """
    if 'sword_out' in state_dict and state_dict['sword_out'] == True:
        return False
    await asyncio.sleep(0)
    state_dict['sword_out'] = True
    dir_coords = {'n':(0, -1, '│'), 'e':(1, 0, '─'), 's':(0, 1, '│'), 'w':(-1, 0, '─')}
    starting_coords = actor_dict['player'].coords()
    chosen_dir = dir_coords[direction]
    sword_id = await generate_id(base_name='')
    sword_segment_names = ["{}_{}_{}".format(name, sword_id, segment) for segment in range(1, length)]
    segment_coords = [(starting_coords[0] + chosen_dir[0] * i, 
                       starting_coords[1] + chosen_dir[1] * i) for i in range(1, length)]
    for segment_coord, segment_name in zip(segment_coords, sword_segment_names):
        actor_dict[segment_name] = Actor(name=segment_name, tile=term.red(chosen_dir[2]))
        map_dict[segment_coord].actors[segment_name] = True
        for actor in map_dict[segment_coord].actors.items():
            await damage_actor(actor=actor[0], damage=damage)
        await asyncio.sleep(speed)
    for segment_coord, segment_name in zip(reversed(segment_coords), reversed(sword_segment_names)):
        if segment_name in map_dict[segment_coord].actors: 
            del map_dict[segment_coord].actors[segment_name]
        del actor_dict[segment_name]
        await asyncio.sleep(speed)
    state_dict['sword_out'] = False

async def sword_item_ability(length=3):
    facing_dir = state_dict['facing']
    asyncio.ensure_future(sword(facing_dir, length=length))

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
        if state_dict['killall'] == True:
            break
        await asyncio.sleep(.01)
        rand_x = randint(-radius, radius) + current_location[0]
        rand_y = randint(-radius, radius) + current_location[1]
        blink_to = (rand_x, rand_y)
        distance = await point_to_point_distance(point_a=blink_to, 
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


#Item interaction---------------------------------------------------------------
async def spawn_item_at_coords(coord=(2, 3), instance_of='wand', on_actor_id=False):
    #item text:
    wand_broken_text = " is out of charges."
    shift_amulet_kwargs = {'x_offset':1000, 'y_offset':1000, 'plane_name':'nightmare'}
    possible_items = ('wand', 'nut', 'fused charge', 'shield wand', 'red potion',
                      'shiny stone', 'shift amulet', 'red sword', 'vine wand',
                      'eye trinket', 'high explosives', 'red key', 'green key')
    if instance_of == 'random':
        instance_of = choice(possible_items)
    item_id = await generate_id(base_name=instance_of)
    item_catalog = {'wand':{'uses':10, 'tile':term.blue('/'), 'usable_power':None},
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
                 'red key':{'uses':9999, 'tile':term.red('⚷'), 'usable_power':unlock_door, 
                            'power_kwargs':{'opens':'red'}, 'broken_text':wand_broken_text,
                            'use_message':''},
               'green key':{'uses':9999, 'tile':term.green('⚷'), 'usable_power':unlock_door, 
                            'power_kwargs':{'opens':'green'}, 'broken_text':wand_broken_text,
                            'use_message':''},
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

async def display_items_at_coord(coord=actor_dict['player'].coords(), x_pos=2, y_pos=24):
    last_coord = None
    item_list = ' '
    with term.location(x_pos, y_pos):
        print("Items here:")
    while True:
        if state_dict['killall'] == True:
            break
        await asyncio.sleep(.1)
        player_coords = actor_dict['player'].coords()
        
        await clear_screen_region(x_size=20, y_size=10, screen_coord=(x_pos, y_pos + 1))
        item_list = [item for item in map_dict[player_coords].items]
        for number, item_id in enumerate(item_list):
            with term.location(x_pos, (y_pos + 1) + number):
                print("{} {}".format(item_dict[item_id].tile, item_dict[item_id].name))
        last_coord = player_coords

async def display_items_on_actor(actor_key='player', x_pos=2, y_pos=9):
    item_list = ' '
    while True:
        if state_dict['killall'] == True:
            break
        await asyncio.sleep(.1)
        with term.location(x_pos, y_pos):
            print("Inventory:")
        await clear_screen_region(x_size=15, y_size=10, screen_coord=(x_pos, y_pos+1))
        item_list = [item for item in actor_dict[actor_key].holding_items]
        for number, item_id in enumerate(item_list):
            with term.location(x_pos, (y_pos + 1) + number):
                print("{} {}".format(item_dict[item_id].tile, item_dict[item_id].name))

async def filter_print(output_text="You open the door.", x_offset=0, y_offset=-8, 
                       pause_fade_in=.01, pause_fade_out=.002, pause_stay_on=1, 
                       delay=0, blocking=False):
    #await asyncio.sleep(delay)
    while True:
        if state_dict['printing'] == True:
            with term.location(30, 0):
                print('waiting for lock...')
            await asyncio.sleep(.1)
        else:
            break
    #TODO: lock solves overlap of messages but causes delay. FIX.
    state_dict['printing'] = True #get lock on printing
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
    #await asyncio.sleep
    #if random_order:
        #shuffle(coord_list)


async def print_screen_grid():
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

def clear():
    """
    clears the screen.
    """
    # check and make call for specific operating system
    _ = call('clear' if os.name =='posix' else 'cls')

def draw_door(x, y, closed=True, locked=False, description='red', is_door=True):
    """
    creates a door at the specified map_dict coordinate and sets the relevant
    attributes.
    """
    states = [('▮', False, True), ('▯', True, False)]
    if closed:
        tile, passable, blocking = states[0]
    else:
        tile, passable, blocking = states[1]
    #if description == 'red':
        #map_dict[(x, y)].tile = term.red(tile)
    #elif description == 'green':
        #map_dict[(x, y)].tile = term.green(tile)
    map_dict[(x, y)].tile = tile
    map_dict[(x, y)].passable = passable
    map_dict[(x, y)].blocking = blocking
    map_dict[(x, y)].is_door = is_door
    map_dict[(x, y)].locked = locked
    map_dict[(x, y)].key = description

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
    animation = Animation(base_tile='▮', preset='shimmer')
                          #color_choices="1234567", preset=None)
    map_dict[start_coord] = Map_tile(tile=" ", blocking=False, passable=True,
                                     magic=True, magic_destination=end_coord,
                                     is_animated=True, animation=animation)
    while(True):
        if state_dict['killall'] == True:
            break
        await asyncio.sleep(.1)
        player_coords = actor_dict['player'].coords()
        just_teleported = actor_dict['player'].just_teleported
        if player_coords == start_coord and not just_teleported:
            asyncio.ensure_future(filter_print(output_text="You are teleported."))
            map_dict[player_coords].passable=True
            #del map_dict[player_coords].actors['player']
            actor_dict['player'].update(*end_coord)
            x, y = actor_dict['player'].coords()
            #map_dict[(x, y)].actors['player'] = True
            actor_dict['player'].just_teleported = True

async def create_magic_door_pair(door_a_coords=(5, 5), door_b_coords=(-25, -25)):
    loop = asyncio.get_event_loop()
    loop.create_task(magic_door(start_coord=(door_a_coords), end_coord=(door_b_coords)))
    loop.create_task(magic_door(start_coord=(door_b_coords), end_coord=(door_a_coords)))

def map_init():
    clear()
    draw_box(top_left=(-25, -25), x_size=50, y_size=50, tile="░") #large debug room
    draw_box(top_left=(-5, -5), x_size=10, y_size=10, tile="░")
    draw_centered_box(middle_coord=(-5, -5), x_size=10, y_size=10, tile="░")
    actor_dict['box'] = Actor(name='box', x_coord=7, y_coord=5, tile='☐',
                              holding_items=['red potion', 'nut'])
    map_dict[(7, 5)].actors['box'] = True
    draw_box(top_left=(15, 15), x_size=10, y_size=10, tile="░")
    draw_box(top_left=(30, 15), x_size=10, y_size=10, tile="░")
    draw_box(top_left=(42, 10), x_size=20, y_size=20, tile="░")
    passages = [(7, 7, 17, 17), (17, 17, 25, 10), (20, 20, 35, 20), 
                (0, 0, 17, 17), (39, 20, 41, 20), (-30, -30, 0, 0),
                (60, 20, 90, 20)]
    doors = [(7, 16), (0, 5), (14, 17), (25, 20), (29, 20), (41, 20)]
    for passage in passages:
        connect_with_passage(*passage)
    for door in doors:
        draw_door(*door, locked=True)
    draw_door(*(-5, -5), locked=True, description='green')
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
        key = None
        while True:
            if state_dict['killall'] == True:
                break
            await asyncio.sleep(0.01)
            if isData():
                key = sys.stdin.read(1)
                if key == '\x7f':  # x1b is ESC
                    state_dict['exiting'] = True
                if key is not None:
                    await handle_input(key)
            with term.location(0, 1):
                print("key is: {}".format(repr(key)))
            if state_dict['halt_input'] == True:
                break
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
    hops = {'A':(-15, 0), 'D':(15, 0), 'W':(0, -15), 'S':(0, 15),}
    key_to_compass = {'w':'n', 'a':'w', 's':'s', 'd':'e', 
                      'i':'n', 'j':'w', 'k':'s', 'l':'e'}
    compass_directions = ('n', 'e', 's', 'w')
    fov = 120
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
    elif state_dict['exiting'] == True:
        middle_x, middle_y = (int(term.width / 2 - 2), 
                              int(term.height / 2 - 2),)
        quit_question_text = 'Really quit? (y/n)'
        term_location = (middle_x - int(len(quit_question_text)/2), middle_y - 16)
        with term.location(*term_location):
            print(quit_question_text)
        if key in 'yY':
            state_dict['killall'] = True
        elif key in 'nN':
            with term.location(*term_location):
                #TODO: implement second half of filter print to blot out things with spaces.
                print(' ' * len(quit_question_text))
            state_dict['exiting'] = False

    else:
        if key in directions:
            x_shift, y_shift = directions[key]
            if key in 'wasd':
                await push(pusher='player', direction=key_to_compass[key])
            actor_dict['player'].just_teleported = False
        if key in hops:
            #TODO: break hops into separate function/ability
            player_coords = actor_dict['player'].coords()
            destination = (player_coords[0] + hops[key][0], 
                           player_coords[1] + hops[key][1])
            await flashy_teleport(destination=destination)
        shifted_x, shifted_y = x + x_shift, y + y_shift
        if key in '?':
            await display_help() 
        if key in '$':
            asyncio.ensure_future(filter_fill())
        if key in 'h':
            asyncio.ensure_future(unlock_door())
        if key in '3':
            asyncio.ensure_future(pass_between(x_offset=1000, y_offset=1000, plane_name='nightmare'))
        if key in 'Vv':
            asyncio.ensure_future(vine_grow(start_x=x, start_y=y)),
        if key in 'Xx':
            description = map_dict[(x, y)].description
            asyncio.ensure_future(filter_print(output_text=description)),
        if key in ' ':
            asyncio.ensure_future(toggle_doors()),
        if key in '@':
            #asyncio.ensure_future(spawn_item_at_coords(coord=(2, 3), instance_of='fused charge', on_actor_id='player'))
            player_coords = actor_dict['player'].coords()
            asyncio.ensure_future(spawn_item_spray(base_coord=player_coords, 
                                                   items=['nut', 'shield wand']))
        if key in 'g':
            asyncio.ensure_future(item_choices(coords=(x, y)))
        if key in 'Q':
            asyncio.ensure_future(equip_item(slot='q'))
        if key in 'E':
            asyncio.ensure_future(equip_item(slot='e'))
        if key in 't':
            asyncio.ensure_future(throw_item())
        if key in 'q':
            asyncio.ensure_future(use_item_in_slot(slot='q'))
        if key in 'e':
            asyncio.ensure_future(use_item_in_slot(slot='e'))
        if key in 'h':
            asyncio.ensure_future(health_potion())
        if key in 'u':
            loop = asyncio.get_event_loop()
            loop.create_task(use_chosen_item())
        if key in 'f':
            await sword_item_ability()
        if key in '7':
            asyncio.ensure_future(draw_circle(center_coord=actor_dict['player'].coords(), 
                                  animation=Animation(preset='bars')))
        if key in '8':
            asyncio.ensure_future(print_screen_grid())
        if key in 'o':
            asyncio.ensure_future(orbit(track_actor='player'))
        if key in '6':
            with term.location(5, 5):
                print("trying to blink...")
            await random_blink()
        if key in 'b':
            asyncio.ensure_future(spawn_bubble())
        if map_dict[(shifted_x, shifted_y)].passable and (shifted_x, shifted_y) is not (0, 0):
            map_dict[(x, y)].passable = True #make previous space passable
            actor_dict['player'].update(x + x_shift, y + y_shift)
            x, y = actor_dict['player'].coords()
            map_dict[(x, y)].passable = False #make current space impassable
        if key in "ijkl":
            state_dict['facing'] = key_to_compass[key]
            state_dict['view_angles'] = view_angles[key_to_compass[key]]
            state_dict['fuzzy_view_angles'] = fuzzy_view_angles[key_to_compass[key]]
    return x, y

async def toggle_doors():
    x, y = actor_dict['player'].coords()
    door_dirs = {(-1, 0), (1, 0), (0, -1), (0, 1)}
    for door in door_dirs:
        door_coord_tuple = (x + door[0], y + door[1])
        door_state = map_dict[door_coord_tuple].tile 
        if map_dict[door_coord_tuple].locked:
            description = map_dict[door_coord_tuple].key
            output_text="The {} door is locked.".format(description)
            asyncio.ensure_future(filter_print(output_text=output_text))
            continue
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

    defaults to items in player's inventory if item_id_choices is passed None
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
        if state_dict['killall'] == True:
            break
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
        if state_dict['killall'] == True:
            break
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
        await filter_print(output_text=equip_message)
    else:
        await filter_print(output_text="Nothing to equip!")

async def use_chosen_item():
    #await asyncio.sleep(0)
    item_id_choice = await choose_item()
    if item_id_choice != None:
        asyncio.ensure_future(item_dict[item_id_choice].use())
    
async def use_item_in_slot(slot='q'):
    await asyncio.sleep(0)
    item_id = state_dict['{}_slot'.format(slot)]
    if item_id is 'empty':
        pass
    else:
        if item_dict[item_id].power_kwargs:
            await item_dict[item_id].use()
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

#Geometry functions-------------------------------------------------------------
async def point_to_point_distance(point_a=(0, 0), point_b=(5, 5)):
    """ finds 2d distance between two points """
    await asyncio.sleep(0)
    x_run, y_run = [abs(point_a[i] - point_b[i]) for i in (0, 1)]
    distance = round(sqrt(x_run ** 2 + y_run ** 2))
    return distance

async def get_circle(center=(0, 0), radius=5):
    radius_range = [i for i in range(-radius, radius + 1)]
    result = []
    for x in radius_range:
       for y in radius_range:
           distance = sqrt(x**2 + y**2)
           if distance <= radius:
               result.append((center[0] + x, center[1] + y))
    return result

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

#TODO: add timer that displays tooltip for help menu if no keys are pressed for a while.

#UI/HUD functions---------------------------------------------------------------
async def display_help():
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
                              x_offset=-40, y_offset=-30 + line_number))

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
                coord_through_door = (destination[0] + difference_from_last[0], 
                                      destination[1] + difference_from_last[1])
                door_points = await get_line(destination, coord_through_door)
                if len(door_points) >= 2:
                    line_of_sight_result = await check_line_of_sight(door_points[1], coord_through_door)
                else:
                    line_of_sight_result = True
                if line_of_sight_result != False and line_of_sight_result != None:
                    #catches tiles beyond magic doors:
                    return coord_through_door
                else:
                    return line_of_sight_result
                #return await check_contents_of_tile(coord_through_door)
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
        #await asyncio.sleep(distance * .015)
        await asyncio.sleep(1 / 10)
        if state_dict['killall'] == True:
            break
        #pull up the most recent viewing angles based on recent inputs:
        fuzzy, display = await angle_checker(angle_from_twelve)
        if (x_offset, y_offset) == (0, 0):
            print_choice=term.red('@')
        #elif display or fuzzy:
        elif display:
            player_x, player_y = actor_dict['player'].coords()
            #add a line in here for different levels/dimensions:
            x_display_coord, y_display_coord = player_x + x_offset, player_y + y_offset
            tile_coord_key = (x_display_coord, y_display_coord)
            if randint(0, round(distance)) < threshold:
                line_of_sight_result = await check_line_of_sight((player_x, player_y), tile_coord_key)
                if type(line_of_sight_result) is tuple: #
                    print_choice = await check_contents_of_tile(line_of_sight_result) #
                elif line_of_sight_result == True:
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
                if print_choice == "░":
                    print_choice = bright_to_dark[int(distance)]
                print(print_choice)
                last_printed = print_choice
        #distant tiles update slower than near tiles:

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
        #return item_name
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
        if state_dict['killall'] == True:
            break
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

async def directional_damage_alert(direction='n'):
    with term.location(30, 0):
        print(direction)
    angle_pair_index = await facing_dir_to_num(direction)
    angle_pairs = [(360, 0), (90, 90), (180, 180), (270, 270)]
    arc_width = 90
    dir_arcs = [((int(i - arc_width/2), i), (j, int(j + arc_width/2))) for i, j in angle_pairs]
    middle_x, middle_y = (int(term.width / 2 - 2), 
                          int(term.height / 2 - 2),)
    angle_pair = dir_arcs[angle_pair_index]
    warning_ui_points = [await point_at_distance_and_angle(
                                 radius=17 + randint(0, 3), 
                                 central_point=(middle_x, middle_y), 
                                 angle_from_twelve=randint(*choice(angle_pair)))
                         for _ in range(40)]
    for tile in [term.red("█"), ' ']:
        shuffle(warning_ui_points)
        for point in warning_ui_points:
            await asyncio.sleep(random()/70)
            with term.location(*point):
                print(tile)

async def find_damage_direction(attacker_key):
    """
    TODO: fix to pull from an angle instead
    four possible outputs.
        N
       
    W       E

        S

    N: y value of attacker is less than player Y
    E: x value is greater than player x
    S: y value is greater than player y
    W: x value of attacker is less than player x
    """
    attacker_location = actor_dict[attacker_key].coords()
    player_location = actor_dict['player'].coords()
    if attacker_location[1] < player_location[1]: #N
        return 'n'
    elif attacker_location[0] > player_location[0]: #E
        return 'e'
    elif attacker_location[1] > player_location[1]: #S 
        return 's'
    elif attacker_location[0] < player_location[0]: #W
        return 'w'
    else:
        return 'n'

async def timer(x_pos=0, y_pos=10, time_minutes=0, time_seconds=5, resolution=1):
    await asyncio.sleep(0)
    timer_text = str(time_minutes).zfill(2) + ":" + str(time_seconds).zfill(2)
    while True:
        if state_dict['killall'] == True:
            break
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
    loop.create_task(create_magic_door_pair(door_a_coords=(-26, 3), door_b_coords=(-7, 3)))
    loop.create_task(create_magic_door_pair(door_a_coords=(-26, 4), door_b_coords=(-7, 4)))
    loop.create_task(create_magic_door_pair(door_a_coords=(-26, 5), door_b_coords=(-7, 5)))
    loop.create_task(create_magic_door_pair(door_a_coords=(-8, -8), door_b_coords=(1005, 1005)))

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
    map_dict[player_x, player_y].passable = True
    if map_dict[destination].passable:
        actor_dict['player'].update(*destination)
        state_dict['plane'] = plane
    else:
        await filter_print(output_text="Something is in the way.")

async def printing_testing(distance=0):
    await asyncio.sleep(0)

    bw_gradient = ((" "),                               #0
                   term.color(7)("░"),                  #1
                   term.color(8)("░"),                  #3
                   term.color(7)("▒"),                  #5
                   term.color(8)("▒"),                  #7
                   term.color(7)("▓"),                  #9
                   term.color(7)("█"),                  #10
                   term.color(8)("▓"),                  #11
                   term.color(8)("▓"),                  #11
                   term.color(8)("▓"),                  #11
                   term.color(8)("▓"),                  #11
                   term.color(8)("█"),                  #12
                   term.color(8)("█"),                  #13
                   term.color(8)("█"),                  #14
                   term.color(8)("█"),                  #15
                   )
    bright_to_dark = bw_gradient[::-1]
    for number, tile in enumerate(bw_gradient):
        with term.location(number, 4):
            print(term.bold(str(number)))
    for number, tile in enumerate(reversed(bw_gradient)):
        with term.location(number, 5):
            print(tile)
    for number in range(10):
        with term.location(number, 6):
            print(term.color(number)(str(number)))
        with term.location(number, 7):
            print(term.on_color(number)(str(number)))
    if distance <= len(bright_to_dark) -1: return bright_to_dark[int(distance)]
    else:
        return " "

async def readout(x_coord=50, y_coord=35, update_rate=.1, float_len=3, 
                  actor_name=None, attribute=None, title=None, bar=False, 
                  bar_length=20, is_actor=True, is_state=False):
    """Create a status bar for the health of the 'player' actor"""
    await asyncio.sleep(0)
    while True:
        if state_dict['killall'] == True:
            break
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

async def ui_setup():
    """
    lays out UI elements to the screen at the start of the program.
    """
    await asyncio.sleep(0)
    asyncio.ensure_future(ui_box_draw(x_margin=49, y_margin=35, box_width=23))
    loop = asyncio.get_event_loop()
    loop.create_task(key_slot_checker(slot='q', print_location=(-30, 10)))
    loop.create_task(key_slot_checker(slot='e', print_location=(30, 10)))
    loop.create_task(display_items_at_coord())
    loop.create_task(display_items_on_actor())
    loop.create_task(readout(is_actor=True, actor_name="player", attribute='coords', title="coords:"))
    loop.create_task(readout(bar=True, y_coord=36, actor_name='player', attribute='health', title="♥:"))

#Actor behavior functions-------------------------------------------------------
async def wander(x_current=0, y_current=0, name_key=None):
    """ 
    randomly increments or decrements x_current and y_current
    if square to be moved to is passable
    """
    await asyncio.sleep(0)
    x_move, y_move = randint(-1, 1), randint(-1, 1)
    next_position = (x_current + x_move, y_current + y_move)
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
    direction = await find_damage_direction(attacker_key)
    asyncio.ensure_future(directional_damage_alert(direction=direction))

async def seek_actor(name_key=None, seek_key='player'):
    """ Standardize format to pass movement function.  """
    await asyncio.sleep(0)
    x_current, y_current = actor_dict[name_key].coords()
    target_x, target_y = actor_dict[seek_key].coords()
    active_x, active_y = x_current, y_current
    next_x, next_y = x_current, y_current
    diff_x, diff_y = (active_x - target_x), (active_y - target_y)
    hurtful = actor_dict[name_key].hurtful
    player_x, player_y = actor_dict["player"].coords()
    player_x_diff, player_y_diff = (active_x - player_x), (active_y - player_y)
    if hurtful and abs(player_x_diff) <= 1 and abs(player_y_diff) <= 1:
        await attack(attacker_key=name_key, defender_key="player")
    if diff_x > 0:
        next_x = active_x - 1
    elif diff_x < 0:
        next_x = active_x + 1
    if diff_y > 0: 
        next_y = active_y - 1
    elif diff_y < 0:
        next_y = active_y + 1
    if map_dict[(next_x, next_y)].passable:
        return (next_x, next_y)
    else:
        return (x_current, y_current)

async def damage_door():
    """ allows actors to break down doors"""
    pass

#misc utility functions---------------------------------------------------------
async def generate_id(base_name="name"):
    return "{}_{}".format(base_name, str(datetime.time(datetime.now())))

async def facing_dir_to_num(direction="n"):
    dir_to_num = {'n':2, 'e':1, 's':0, 'w':3}
    return dir_to_num[direction]

async def run_every_n(sec_interval=3, repeating_function=None, kwargs={}):
    while True:
        if state_dict['killall'] == True:
            break
        await asyncio.sleep(sec_interval)
        x, y = actor_dict['player'].coords()
        asyncio.ensure_future(repeating_function(**kwargs))

async def track_actor_location(state_dict_key="player", actor_dict_key="player", update_speed=.1, length=10):
    await asyncio.sleep(0)
    actor_coords = None
    while True:
        if state_dict['killall'] == True:
            break
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
    tentacled_mass_id = await generate_id(base_name='tentacled_mass')
    actor_dict[tentacled_mass_id] = Actor(name=tentacled_mass_id, moveable=False, tile='*',
                                          is_animated=True, animation=Animation(preset='mouth'))
    actor_dict[tentacled_mass_id].update(*start_coord)
    current_coord = start_coord
    while True:
        if state_dict['killall'] == True:
            break
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
        if state_dict['killall'] == True:
            break
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
    await asyncio.sleep(0)
    core_behavior_val = random()
    core_location = actor_dict[core_name_key].coords()
    if core_behavior_val < .05 and tentacles:
        new_core_location = actor_dict[core_name_key].coords()
        asyncio.ensure_future(vine_grow(start_x=core_location[0], start_y=core_location[1])),
        wait = 20
    elif core_behavior_val > .4:
        new_core_location = await wander(x_current=core_location[0],
                                         y_current=core_location[1],
                                         name_key=core_name_key)
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
        new_shroud_location = await wander(*coord, shroud_name_key)
    else:
        new_shroud_location = await seek_actor(name_key=shroud_name_key, seek_key=core_name_key)
    return new_shroud_location

async def basic_actor(start_x=0, start_y=0, speed=1, tile="*", 
        movement_function=wander, name_key="test", hurtful=False,
        strength=5, is_animated=False, animation=" ", holding_items=[]):
    """ A coroutine that creates a randomly wandering '*' """
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
        if state_dict['killall'] == True:
            break
        if actor_dict[name_key].health <= 0:
            await kill_actor(name_key=name_key)
            return
        await asyncio.sleep(speed)
        next_coords = await movement_function(name_key=name_key)
        current_coords = actor_dict[name_key].coords() #checked again here because actors can be pushed around
        if current_coords != next_coords:
            if name_key in map_dict[current_coords].actors:
                del map_dict[current_coords].actors[name_key]
            map_dict[next_coords].actors[name_key] = True
            actor_dict[name_key].update(*next_coords)

async def kill_actor(name_key=None, leaves_body=True, blood=True):
    coords = actor_dict[name_key].coords()
    holding_items = actor_dict[name_key].holding_items
    if leaves_body:
        body_tile = term.red(actor_dict[name_key].tile)
    #if actor_dict[name_key].holding_items:
        #for number, item in enumerate(actor_dict[name_key].holding_items):
            #with term.location(30, 2 + number):
                #print(item)
    del actor_dict[name_key]
    del map_dict[coords].actors[name_key]
    if blood:
        await sow_texture(root_x=coords[0], root_y=coords[1], radius=3, paint=True, 
                          seeds=5, description="blood.")
        await spawn_item_spray(base_coord=coords, items=holding_items)
        map_dict[coords].tile = body_tile
        map_dict[coords].description = "A body."
    return

async def spawn_item_spray(base_coord=(0, 0), items=[], random=False, radius=2):
    if items is None:
        return
    loop = asyncio.get_event_loop()
    coord_choices = await get_circle(center=base_coord, radius=radius)
    for item in items:
        item_coord = choice(coord_choices)
        loop.create_task(spawn_item_at_coords(coord=item_coord, instance_of=item))

async def vine_grow(start_x=0, start_y=0, actor_key="vine", 
                    rate=.1, vine_length=20, rounded=True,
                    behavior="retract", speed=.01, damage=20,
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
    vine_id = await generate_id(base_name='')
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
        current_coord = (current_coord[0] + next_tuple[0], current_coord[1] + next_tuple[1])
        prev_dir = next_dir
        #next_dir is generated at the end of the for loop so it can be
        #initialized to a given direction.
        next_dir = randint(1, 4)
    for vine_name in vine_actor_names:
        await asyncio.sleep(extend_wait)
        map_tile = actor_dict[vine_name].tile
        coord = actor_dict[vine_name].coord
        with term.location(0, 3):
            print(coord)
        if behavior == "grow":
            map_dict[coord].tile = map_tile
        if behavior == "retract" or "bolt":
            map_dict[coord].actors[vine_name] = True
        if damage:
            await damage_all_actors_at_coord(exclude=vine_name, 
                                             coord=coord, 
                                             damage=damage)
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
    for i in range(int(num_steps)):
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
    bubble_id = await generate_id(base_name='')
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
                      rand_delay=0, solid=True):
    """
    spawns an actor at given coords that disappears after a number of turns.
    """
    if name == 'timed_actor':
        name = name + await generate_id(base_name='')
    if rand_delay:
        await asyncio.sleep(random() * rand_delay)
    actor_dict[name] = Actor(name=name, moveable=False, x_coord=coords[0], y_coord=coords[1], 
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

async def travel_along_line(name='particle', start_coord=(0, 0), end_coord=(10, 10),
                            speed=.05, tile="X", animation=Animation(preset='fire'),
                            debris=None):
    asyncio.sleep(0)
    points = await get_line(start_coord, end_coord)
    particle_id = await generate_id(base_name=name)
    if animation:
        is_animated = True
    else:
        is_animated = False
    actor_dict[particle_id] = Actor(name=particle_id, x_coord=start_coord[0], y_coord=start_coord[1], 
                                    tile=tile, moveable=False, is_animated=is_animated,
                                    animation=animation)
    map_dict[start_coord].actors[particle_id] = True
    last_location = points[0]
    for point in points:
        await asyncio.sleep(speed)
        if particle_id in map_dict[last_location].actors:
            del map_dict[last_location].actors[particle_id]
        map_dict[point].actors[particle_id] = True
        actor_dict[particle_id].update(*point)
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
        if state_dict['killall'] == True:
            break
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
            start_coord, end_coord = point, origin_coord
        else:
            start_coord, end_coord = origin_coord, point
        asyncio.ensure_future(travel_along_line(start_coord=start_coord, 
                                                end_coord=end_coord,
                                                debris=debris,
                                                animation=animation))
        if deathclock:
            deathclock -= 1
            if deathclock <= 0:
                break

async def orbit(name='particle', radius=5, degrees_per_step=1, on_center=(0, 0), 
                rand_speed=False, track_actor=None, 
                sin_radius=False, sin_radius_amplitude=3):
    """
    generates an actor that orbits about a point
    TODO: particles that follow an arbitrary path
    """
    await asyncio.sleep(0)
    angle = randint(0, 360)
    particle_id = await generate_id(base_name=name)
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
        if state_dict['killall'] == True:
            break
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
        if state_dict['killall'] == True:
            break
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
        if state_dict['killall'] == True:
            break
        await asyncio.sleep(rate)
        player_coords = actor_dict['player'].coords()
        with term.location(40, 0):
            print(" " * 10)
        with term.location(40, 0):
            print(len([i for i in map_dict[player_coords].actors.items()]))
#
async def kill_all_tasks():
    await asyncio.sleep(0)
    pending = asyncio.Task.all_tasks()
    for task in pending:
        task.cancel()
        # Now we should await task to execute it's cancellation.
        # Cancelled task raises asyncio.CancelledError that we can suppress:
        with suppress(asyncio.CancelledError):
            loop.run_until_complete(task)

async def spawn_preset_actor(coords=(0, 0), preset='blob', speed=1, holding_items=[]):
    """
    spawns an entity with various presets based on preset given.
    *** does not need to be set at top level. Can be nested in map and character
    placement.
    """
    asyncio.sleep(0)
    loop = asyncio.get_event_loop()
    actor_id = await generate_id(base_name=preset)
    name = "{}_{}".format(preset, actor_id)
    start_coord = coords
    if preset == 'blob':
        item_drops = ['red potion']
        loop.create_task(basic_actor(*coords, speed=.75, movement_function=seek_actor, 
                                     tile='ö', name_key=name, hurtful=True, strength=30,
                                     is_animated=True, animation=Animation(preset="blob"),
                                     holding_items=item_drops))
    #elif preset == 'crate':
        #item_drops = ['red potion', 'red potion']
    else:
        pass

async def spawn_breakable(coords=(0, 0), preset='crate', holding_items=['red potion'], health=10):
    pass
    #def __init__(self, name='', x_coord=0, y_coord=0, speed=.2, tile="?", strength=1, 
                 #health=health, hurtful=False, moveable=True, is_animated=False,
                 #animation="", holding_items={}, leaves_body=False):

async def quitter_daemon():
    while True:
        await asyncio.sleep(0.1)
        if state_dict['killall'] == True:
            loop = asyncio.get_event_loop()
            loop.stop()
            loop.close()

def main():
    map_init()
    state_dict["player_health"] = 100
    state_dict['view_angles'] = (315, 360, 0, 45)
    state_dict['fuzzy_view_angles'] = (315, 360, 0, 45)
    old_settings = termios.tcgetattr(sys.stdin) 
    loop = asyncio.new_event_loop()
    loop.create_task(get_key())
    loop.create_task(view_init(loop))
    loop.create_task(ui_setup())
    loop.create_task(printing_testing())
    loop.create_task(track_actor_location())
    loop.create_task(async_map_init())
    loop.create_task(spawn_item_at_coords(coord=(-3, -3), instance_of='red key', on_actor_id=False))
    loop.create_task(spawn_item_at_coords(coord=(-2, -2), instance_of='green key', on_actor_id=False))
    #loop.create_task(shrouded_horror(start_x=-8, start_y=-8))
    item_spawns = []
    loop.create_task(death_check())
    loop.create_task(environment_check())
    loop.create_task(quitter_daemon())
    #loop.create_task(circle_of_darkness())
    for i in range(3):
        rand_coord = (randint(-25, 25), randint(-25, 25))
        loop.create_task(spawn_preset_actor(coords=rand_coord, preset='blob'))
    #loop.create_task(travel_along_line())
    asyncio.set_event_loop(loop)
    result = loop.run_forever()

with term.hidden_cursor():
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        main()
    finally: 
        clear()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings) 
