import asyncio
import sys
import select 
import tty 
import termios
from blessings import Terminal
import os
from collections import defaultdict
from random import randint

term = Terminal()

map_dict = defaultdict(lambda: [' '])

#testing out writing to the map_dict
for x in range(-5, 6):
    for y in range(-5, 6):
        #the lowest level scenery on the tile is index 0.
        map_dict[(x, y)][0] = '-' 

def show_key(key):
    txt.set_text(repr(key))

def isData(): ##
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []) ##

async def handle_input(key, x, y):
    """
    interpret keycodes and do various actions.
    """
    await asyncio.sleep(0)  
    if key == 'a':   
        x += 1
    if key == 'd':  
        x -= 1
    if key == 'w': 
        y += 1
    if key == 's':
        y -= 1
    return x, y

async def get_key(): ##
    """
    the closest thing I could get to non-blocking input
    currently contains messy map display code
    """
    old_settings = termios.tcgetattr(sys.stdin)
    #TODO: figure out resizing and auto-centering of @ in terminal
    #rows, columns = os.popen('stty size', 'r').read().split()
    #middle_x = int(int(rows)/2)
    #middle_y = int(int(columns)/2)
    middle_x = 30 
    middle_y = 10
    try:
        tty.setcbreak(sys.stdin.fileno())
        x = 0
        y = 0
        while 1:
            await asyncio.sleep(0)  
            if isData():
                key = sys.stdin.read(1)
                if key == 'x1b':  # x1b is ESC
                    break
                x, y = await handle_input(key, x, y)
            else:
                await asyncio.sleep(0)
            for x_shift in range(-10, 11):
                for y_shift in range(-10, 11):
                    x_coord = middle_x + x_shift
                    y_coord = middle_y + y_shift
                    with term.location(x_coord, y_coord):
                        print(map_dict[(x + x_shift, y + y_shift)][-1])
            with term.location(middle_x, middle_y):
                print("@")
            with term.location(0, 0):
                print(x_coord, y_coord)
    
                #await asyncio.sleep(0)
    finally: ##
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings) ##

async def wanderer(start_x, start_y, speed):
    """
    a coroutine that creates a randomly wandering '*'
    TODO: figure out how to not leave a trail and/or poll from a list of actors 
    instead of writing to the map dicitionary
    """
    old_value = map_dict[(start_x, start_y)][-1]
    map_dict[(start_x, start_y)][-1] = '&'
    x = start_x
    y = start_y
    while 1:
        await asyncio.sleep(speed)
        map_dict[(x, y)][-1] = old_value
        x += randint(-1,1)
        y += randint(-1,1)
        map_dict[(x, y)][-1] = '*'

def main():
    old_settings = termios.tcgetattr(sys.stdin) ##
    
    loop = asyncio.new_event_loop()

    loop.create_task(get_key())
    loop.create_task(wanderer(5, 5, .2))
    loop.create_task(wanderer(0, 5, .2))
    loop.create_task(wanderer(5, 0, .2))
    loop.create_task(wanderer(10, 10, .2))

    asyncio.set_event_loop(loop)
    result = loop.run_forever()

    
main()
