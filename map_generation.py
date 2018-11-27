from random import choice
import os
from time import sleep
from math import sqrt

def add_coords(coord_a=(0, 0), coord_b=(10, 10)):
    output = (coord_a[0] + coord_b[0],
              coord_a[1] + coord_b[1])
    return output

def get_circle(center=(0, 0), radius=5):
    radius_range = [i for i in range(-radius, radius + 1)]
    result = []
    for x in radius_range:
       for y in radius_range:
           distance = sqrt(x**2 + y**2)
           if distance <= radius:
               result.append((center[0] + x, center[1] + y))
    return result

def point_to_point_distance(point_a=(0, 0), point_b=(5, 5)):
    """ finds 2d distance between two points """
    x_run, y_run = [abs(point_a[i] - point_b[i]) for i in (0, 1)]
    distance = round(sqrt(x_run ** 2 + y_run ** 2))
    return distance

def cave_room(input_space=None, trim_radius=20, width=50, height=50, iterations=20):
    #TODO: unfinished. 
    neighbors = [(x, y) for x in (-1, 0, 1)
                        for y in (-1, 0, 1)]
    #initialize the room
    input_space = {(x, y):choice(['#', ' ']) for x in range(width) for y in range(height)}
    if trim_radius:
        center_coord = width // 2, height // 2
        for coord in input_space:
            distance_from_center = point_to_point_distance(point_a=coord, point_b=center_coord)
            if distance_from_center > trim_radius:
                input_space[coord] = ' '
    adjacency = {(x, y):0 for x in range(width) for y in range(height)}
    check_coords = [(x, y) for x in range(width)
                           for y in range(height)]
    for iteration_number in range(iterations):
        for coord in check_coords:
            neighbor_count = 0
            for neighbor in neighbors:
                check_cell_coord = add_coords(coord_a=coord, coord_b=neighbor)
                if check_cell_coord not in input_space:
                    continue
                if input_space[check_cell_coord] == '#':
                    neighbor_count += 1
            adjacency[coord] = neighbor_count
        for y in range(height):
            for x in range(width):
                if adjacency[x, y] >= 5:
                    input_space[x, y] = '#'
                else:
                    input_space[x, y] = ' '
        for y in range(height):
            print(''.join([input_space[x, y] for x in range(width)]))
        print("iteration: {}".format(iteration_number))
        sleep(.05)
        os.system('clear')

def main():
    while(True):
        cave_room()

if __name__ == '__main__':
    main()

