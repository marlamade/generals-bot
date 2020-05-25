"""
    @ Harris Christiansen (code@HarrisChristiansen.com)
    Generals.io Automated Client - https://github.com/harrischristiansen/generals-bot
    Bot_blob: Creates a blob of troops.
"""

import logging
from base import bot_moves
import startup

# Show all logging
logging.basicConfig(level=logging.DEBUG)

# ======================== Move Making ======================== #

_bot = None
_map = None


def make_move(current_bot, current_map):
    global _bot, _map
    _bot = current_bot
    _map = current_map

    if leave_swamp():
        return

    if move_priority():  # Capture a city or general if I have an adjacent larger force
        return

    if _map.turn % 3 == 0:
        if move_outward():  # Capture a regular tile if it's adjacent - preferably not a swamp
            return
    if not move_toward():
        move_outward()    # We get here on turn 1. not sure if it happens any other time.
    return


def place_move(source, dest):
    _bot.place_move(source, dest, move_half=bot_moves.should_move_half(_map, source, dest))


# ======================== Move Priority ======================== #

def move_priority():
    (source, dest) = bot_moves.move_priority(_map)
    if source and dest:
        place_move(source, dest)
        return True
    return False


# ======================== Move Outward ======================== #

def move_outward():
    (source, dest) = bot_moves.move_outward(_map)
    if source and dest:
        place_move(source, dest)
        return True
    return False


# ======================== Move Toward ======================== #

def move_toward():
    _map.path = bot_moves.path_proximity_target(_map)
    (move_from, move_to) = bot_moves.move_path(_map.path)
    if move_from and move_to:
        print("move_toward:", move_from, move_to)
        place_move(move_from, move_to)
        return True
    return False


# ======================== Move Toward ======================== #

def leave_swamp():
    (source, dest) = bot_moves.leave_swamp(_map)
    if source and dest:
        place_move(source, dest)
        return True
    return False

# ======================== Main ======================== #

# Start Game

if __name__ == '__main__':
    startup.startup(make_move, bot_name="Brobot")
