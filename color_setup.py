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

def color_pairing():
    """
    display a list of colors, pick the ones that are closest to the given color
    for both foreground and background

    return the results
    """
    colors = ("dark grey", "light grey", "white")
    stylings = ("foreground", "background")
    choice_offset = 0
    settings = []
    for styling in stylings:
        for color in colors:
            for i in range(10):
                if styling == "foreground":
                    with term.location(0, i + 2):
                        print(i, term.color(i)('test'))
                if styling == "background":
                    with term.location(0, i + 2):
                        print(i, term.on_color(i)('test'))
            input_string = None
            while input_string is None or input_string not in '0123456789':
                with term.location(0, 0):
                    print("Pick the closest {} color to a {}.".format(styling, color))
                with term.location(0, 2):
                    input_string = input("enter a number 0 to 9 and press enter:")
            if styling == "foreground":
                settings.append((int(input_string), 0))
            else:
                settings.append((0, int(input_string)))
            with term.location(10, 5 + choice_offset):
                if styling == "foreground":
                    print(term.color(int(input_string))("foreground {}".format(color)))
                else:
                    print(term.on_color(int(input_string))("background {}".format(color)))
            choice_offset += 1

def switcher_display(y_offset=3, x_offset=3):
    shades = (' ', '░', '▒', '▒', '▓', '█', '█')
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

def choose_yn(message="Yes or No? "):
    while True:
        user_input = input(message).lower()
        if user_input not in ('y', 'n', 'yes', 'no'):
            print("Must be a yes or no answer.")
            continue
        else:
            if user_input in ('n', 'no'):
                return False
            else:
                return True

def pick_matching_color():
    clear()
    color_map = {}
    for number in range(10):
        with term.location(number, 0):
            print(term.color(number)(str(number)))
        with term.location(number, 1):
            print(term.on_color(number)(str(number)))
    for color in ('red', 'white', 'black', 'gray', 'green', 'orange', 'blue', 'light blue'):
        with term.location(0, 2):
            color_choice = None
            print("Which color is closest to {}?          ".format(color))
            color_choice = input_number()
            color_map[color] = int(color_choice)
    print("Color map is: {}".format(color_map))
    return color_map

def main():
    clear()
    color_pairing()
    #ordering = switcher_display()
    #print("brightness_preset:")
    #print(ordering)
    #print(''.join([str(i) for _, i in ordering]))
    #with open('brightness_preset.txt', 'w+') as color_palette:
        #color_palette.write(repr(ordering))
        #for pair in ordering:
            #color_palette.write("{}, {}\n".format(*pair))
    """
    colors = ('red', 'white', 'black', 'gray', 'green', 'orange', 'blue', 'light blue')
    while True:
        color_preset = pick_matching_color()
        clear()
        for color_name in colors:
            print(color_name, term.color(color_preset[color_name])(color_name))
        confirm_preset = input("For all lines, does the font color match the color names?\n")
        print("confirm_preset: {}".format(confirm_preset))
        if confirm_preset.lower() not in ('yes', 'y'):
            continue
        else:
            break
    with open('color_palette.txt', 'w') as color_palette:
        for color in colors:
            print("writing {}, {}".format(color, color_preset[color]))
            color_palette.write("{}, {}\n".format(color, color_preset[color]))
    """

main()

