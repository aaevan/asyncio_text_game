from blessings import Terminal
import os
from subprocess import call
from itertools import product
from time import sleep

term = Terminal()

def clear():
    """
    clears the screen.
    """
    # check and make call for specific operating system
    _ = call('clear' if os.name =='posix' else 'cls')

def switcher_display(y_offset=3, x_offset=3):
    shades = (' ', '░', '▒', '▓', '█')
    numbers = (0, 8, 7)
    on_fill = (0, 8, 7)
    ordering = []
    for number in numbers:
        for index, shade in enumerate(shades):
            tile = (number, shade, term.color(number)(shade))
            ordering.append(tile)
    while True:
        clear()
        with term.location(0, 0):
            print("Arrange color values from brightest (top) to darkest (bottom).")
        with term.location(0, 1):
            print("Enter line indexes to swap, ex. '1, 2', 'good' to finish preset")
        for index, (number, shade, tile) in enumerate(ordering):
            with term.location(x_offset, y_offset + index):
                print(str(index).ljust(2) + ':', number, shade, (tile * 10))
        while True:
            with term.location(0, 2):
                print(' ' * 80)
            with term.location(0, 2):
                input_string = input("switch a and b? ")
            if type(input_string) == str:
                if input_string == 'good':
                    clear()
                    ordering = [(i, j) for i, j, _ in ordering]
                    return ordering
                input_string = input_string.split(',')
                if len(input_string) == 2:
                    if all (i.strip().isdigit() for i in input_string):
                        break
                with term.location(0, 0):
                    print(" " * 80)
                with term.location(0, 0):
                    print("input must be 'int, int' format.")
        input_command = [int(i.strip()) for i in input_string]
        a, b = input_command
        ordering[a], ordering[b] = ordering[b], ordering[a]
        print("input_command: {}".format(input_command))

def input_number(message="Choose a number: "):
    while True:
        try:
            user_input = int(input(message))
        except ValueError:
            print("That's not a whole number.")
            continue
        else:
            return user_input

def pick_matching_color():
    color_map = {}
    for color in ('red', 'white', 'black', 'gray', 'green', 'orange', 'blue', 'light blue'):
        with term.location(0, 0):
            color_choice = None
            print("Which color is closest to {}?".format(color))
            color_choice = input_number()
            color_map[color] = int(color_choice)
    return color

def main():
    clear()
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
    clear()
    output = switcher_display()
    print(output)
    with open('color_palette.txt', 'w') as color_palette:
        color_palette.write(str(output))

main()

