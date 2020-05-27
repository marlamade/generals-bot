"""
    @ Harris Christiansen (code@HarrisChristiansen.com)
    Generals.io Automated Client - https://github.com/harrischristiansen/generals-bot
    Generals Bot: Common Move Logic
"""
import logging
import random
from pprint import pprint

from base import bot_base
from .client.constants import *

# ======================== Move Priority Capture ======================== #
from .client.map import Map


def move_priority(game_map):
    priority_move = (False, False)
    generals = [t for t in game_map.generals if t is not None]
    generals_and_cities = generals + game_map.cities

    for tile in generals_and_cities:
        # if it doesn't belong to my teammates and isn't dirty
        if tile.should_attack():
            for neighbor in tile.neighbors():
                # if I can capture this tile
                if neighbor.is_self() and neighbor.army > max(1, tile.army + 1):
                    # if I haven't already found a priority move OR I have, but it uses a weaker army
                    if not priority_move[0] or priority_move[0].army < neighbor.army:
                        priority_move = (neighbor, tile)
                    # if the tile is a general, capture it
                    if tile in generals:
                        priority_move = (neighbor, tile)
            # if priority_move[0]:
            #     # TODO: Note, priority moves are repeatedly sent, indicating move making is sending repeated moves
            #     # logging.info("Priority Move from %s -> %s" % (priority_move[0], priority_move[1]))
            #     break
    return priority_move


# ======================== Move Outward ======================== #

def move_outward(game_map, path=None):
    """
    Move from one of my tiles to any adjacent tile, preferably not a swamp
    :param game_map:
    :param path:
    :return:
    """
    if path is None:
        path = []
    swamp_moves = []
    # move_swamp = (False, False)

    for source in game_map.tiles[game_map.player_index]:  # Check Each Owned Tile
        if source.army >= 2 and source not in path:  # Find One With Armies
            target = source.neighbor_to_attack(path)
            if target:
                if not target.is_swamp:
                    return source, target
                swamp_moves.append((source, target))

    for source, swamp in swamp_moves:
        swamp_paths = swamp.get_swamp_paths(source.army)
        if swamp_paths:
            return source, swamp

    return (False, False)


# ======================== Move Path Forward ======================== #

def move_path(path):
    if len(path) < 2:
        return False, False

    source = path[0]
    target = path[-1]

    if target.tile == source.tile:
        return _move_path_largest(path)

    move_capture = _move_path_capture(path)

    if not target.is_general and move_capture[1] != target:
        return _move_path_largest(path)

    return move_capture


def _move_path_largest(path):
    largest = path[0]
    largest_index = 0
    for i, tile in enumerate(path):
        if tile == path[-1]:
            break
        if tile.tile == path[0].tile and tile > largest:
            largest = tile
            largest_index = i

    dest = path[largest_index + 1]
    return largest, dest


def _move_path_capture(path):
    source = path[0]
    capture_army = 0
    for i, tile in reversed(list(enumerate(path))):
        if tile.tile == source.tile:
            capture_army += (tile.army - 1)
        else:
            capture_army -= tile.army

        if capture_army > 0 and i + 1 < len(path) and path[i].army > 1:
            return path[i], path[i + 1]

    return _move_path_largest(path)


# ======================== Move Path Forward ======================== #

def should_move_half(game_map, source, dest=None):
    if dest is not None and dest.is_city and \
            (not source.is_city or source.army / 4 < dest.army):
        return False

    if game_map.turn > 250:
        if source.is_general:
            return random.choice([True, True, True, False])
        elif source.is_city:
            ## if game_map.turn - source.turn_captured < 16:
            enemy_neighbors = sum(
                1 for neighbor in source.neighbors(include_cities=True, include_swamps=True)
                if neighbor.is_enemy()
            )
            enemy_neighbors -= dest.is_enemy()  # if one of the surrounding enemy tiles is the dest, then it doesn't count.
            if enemy_neighbors > 0:  # If we don't own all the surrounding land except the destination, move half
                return True
            else:
                return False
            return random.choice([False, False, False, True])
    return False


# ======================== Proximity Targeting - Path-finding ======================== #

# noinspection SpellCheckingInspection
def path_proximity_target(game_map):
    # Find path from largest tile to closest targetbasic_config

    # find the tile I own with the most armies. Include generals at .5 of their actual armies
    source = game_map.find_largest_tile(include_general=0.5)
    # find the best enemy target to attack. If all enemy tiles have more that 4x+14 army, where x
    # is the size of my largest army, then return none.
    target = source.nearest_target_tile()
    path = source.path_to(target, include_cities=True)
    # logging.info("Proximity %s -> %s via %s" % (source, target, path))

    if not game_map.can_step_path(path):
        path = path_gather(game_map)
        # logging.info("Proximity FAILED, using path %s" % path)
    return path


# noinspection SpellCheckingInspection,SpellCheckingInspection
def path_gather(game_map, elso_do=None):
    if elso_do is None:
        elso_do = []
    target = game_map.find_largest_tile()
    source = game_map.find_largest_tile(tiles_to_exclude=[target], include_general=0.5)
    if source and target and source != target:
        return source.path_to(target)
    return elso_do


# ======================== Moves added by Marla ======================== #

def leave_swamp(game_map: Map):
    for tile in game_map.tiles[game_map.player_index]:
        if tile.is_swamp:
            best_swamp_path = tile.get_best_swamp_path()
            if best_swamp_path and len(best_swamp_path) >= 2:
                return best_swamp_path[0], best_swamp_path[1]
    return (False, False)


def move_explore(game_map: Map):
    # source = game_map.find_largest_tile(include_general=0.5)
    target = game_map.get_exploration_target()
    if target is None:
        return False, False

    source, dest = target.step_toward_me()
    print("Exploration targeting %s. First step: %s -> %s" %(target, source, dest))

    return source, dest


    #
    # path = source.path_to(target, include_obstacles=True, include_cities=True)
    # # logging.info("Explore %s -> %s via %s" % (source, target, path))
    #
    # if len(path) >= 2:
    #     return path[0], path[1]
    # else:
    #     return False, False

# ======================== Helpers ======================== #

def _shuffle(seq):
    shuffled = list(seq)
    random.shuffle(shuffled)
    return iter(shuffled)
