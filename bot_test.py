"""
    @ Harris Christiansen (code@HarrisChristiansen.com)
    Generals.io Automated Client - https://github.com/harrischristiansen/generals-bot
    bot_test: Used for testing various move methods
"""

import logging
import time
from base import bot_moves
import startup

PRINT_TIMING = False
PRINT_MOVES = False
# Show all logging
logging.basicConfig(level=logging.DEBUG)

# ======================== Move Making ======================== #

_bot = None
_map = None


def make_move(currentBot, currentMap):
    global _bot, _map
    _bot = currentBot
    _map = currentMap

    if _map.turn < 24 and currentBot._gameType != "private":
        return

    start_time = time.time()

    if not move_priority():
        if _map.turn < 42 or not move_outward():
            move_toward()

    if PRINT_TIMING:
        move_time = time.time() - start_time
        logging.info("Move (%d) took: %1.7fs" % move_time)


def place_move(source, dest):
    if PRINT_MOVES:
        logging.info("Move: %s -> %s" % (source, dest))
    _bot.place_move(source, dest)


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
        place_move(move_from, move_to)
        return True
    return False


# ======================== Main ======================== #

# Start Game

if __name__ == '__main__':
    startup.startup(make_move, botName="PurdueBot-T")
