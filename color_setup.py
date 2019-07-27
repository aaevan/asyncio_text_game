from blessings import Terminal
import os
from subprocess import call
from itertools import product

term = Terminal()

def clear():
    """
    clears the screen.
    """
    # check and make call for specific operating system
    _ = call('clear' if os.name =='posix' else 'cls')

def shades_pick():
    shades = ('░', '▒', '▓', '█')
    numbers = (0, 8, 7)
    output_pairs = list(product(numbers, shades))
    #print(output_pairs)
    str_output = []
    for pair in output_pairs:
        print(pair)
    for pair in output_pairs:
        str_output.append(term.color(pair[0])(pair[1]))
    print(''.join(str_output))
    for number in numbers:
        for index, shade in enumerate(shades):
            tile = term.color(number)(shade)
            print(number, index, shade, tile * 4)
    print()
    print(term.color(0)(shades[0]) * 4, 0, 0)
    print(term.color(8)(shades[0]) * 4, 8, 0)
    print(term.color(0)(shades[1]) * 4, 0, 1)
    print(term.color(0)(shades[2]) * 4, 0, 2)
    print(term.color(8)(shades[1]) * 4, 8, 1)
    print(term.color(7)(shades[0]) * 4, 7, 0)
    print(term.color(0)(shades[3]) * 4, 0, 3)
    print(term.color(8)(shades[2]) * 4, 8, 2)
    print(term.color(8)(shades[3]) * 4, 8, 3)
    print(term.color(7)(shades[1]) * 4, 7, 1)
    print(term.color(7)(shades[2]) * 4, 7, 2)
    print(term.color(7)(shades[3]) * 4, 7, 3)

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
    x_coord, y_coord = 0, 0
    gradient_output_1 = []
    gradient_output_2 = []
    for number, tile in enumerate(bw_gradient):
        gradient_output_1.append(term.bold(str(hex(number))[-1]))
    for number, tile in enumerate(reversed(bw_gradient)):
        gradient_output_2.append(tile)
    print(''.join(gradient_output_1))
    print(''.join(gradient_output_2))
    output_1 = []
    output_2 = []
    for number in range(10):
        output_1.append(term.color(number)(str(number)))
        output_2.append(term.on_color(number)(str(number)))
    print(''.join(output_1))
    print(''.join(output_2))
    shades_pick()

main()

