"""
    @ Harris Christiansen (code@HarrisChristiansen.com)
    Generals.io Automated Client - https://github.com/harrischristiansen/generals-bot
    Map: Objects for representing Generals IO Map
"""

import logging

from .constants import *
from .tile import Tile


class Map(object):
    def __init__(self, start_data, data):
        # Start Data
        self._start_data = start_data
        self.player_index = start_data['playerIndex']  # Integer Player Index
        self.usernames = start_data['usernames']  # List of String Usernames
        # TODO: Use Client Region
        self.replay_url = REPLAY_URLS["na"] + start_data['replay_id']  # String Replay URL

        # Map Properties
        self._apply_update_diff(data)
        self.rows = self.rows  # Integer Number Grid Rows
        self.cols = self.cols  # Integer Number Grid Cols
        self.grid = [[Tile(self, x, y) for x in range(self.cols)] for y in range(self.rows)]  # 2D List of Tile Objects
        self._set_neighbors()
        self.swamps = [(c // self.cols, c % self.cols) for c in start_data['swamps']]  # List [(y,x)] of swamps
        self._set_swamps()
        self.turn = data['turn']  # Integer Turn # (1 turn / 0.5 seconds)
        self.tiles = [[] for x in range(12)]  # List of 8 (+ extra) Players Tiles
        self.cities = []  # List of City Tiles
        self.generals = [None for x in range(12)]  # List of 8 (+ extra) Generals (None if not found)
        self._set_generals()
        self.stars = []  # List of Player Star Ratings
        self.scores = self._get_scores(data)  # List of Player Scores
        self.complete = False  # Boolean Game Complete
        self.result = False  # Boolean Game Result (True = Won)

        # Public/Shared Components
        self.path = []
        self.collect_path = []

        # Public Options
        self.exit_on_game_over = True  # Controls if bot exits after game over
        self.do_not_attack_players = []  # List of player IDs not to attack

    # ======================== Game Updates ======================== #

    def update(self, data):
        if self.complete:  # Game Over - Ignore Empty Board Updates
            return self

        self._apply_update_diff(data)
        self.scores = self._get_scores(data)
        self.turn = data['turn']

        for x in range(self.cols):  # Update Each Tile
            for y in range(self.rows):
                tile_type = self._tile_grid[y][x]
                army_count = self._army_grid[y][x]
                is_city = (y, x) in self._visible_cities
                is_general = (y, x) in self._visible_generals
                self.grid[y][x].update(self, tile_type, army_count, is_city, is_general)

        return self

    def update_result(self, result):
        self.complete = True
        self.result = result == "game_won"
        return self

    # ======================== Map Search/Selection ======================== #

    def find_city(self, of_type=None, not_of_type=None, not_in_path=None, find_largest=True, include_general=False):
        # ofType = Integer, notOfType = Integer, notInPath = [Tile], findLargest = Boolean
        if not_in_path is None:
            not_in_path = []
        if of_type is None and not_of_type is None:
            of_type = self.player_index

        found_city = None
        for city in self.cities:  # Check Each City
            if city.tile == of_type or (not_of_type is not None and city.tile != not_of_type):
                if city in not_in_path:
                    continue
                if found_city is None:
                    found_city = city
                elif (find_largest and found_city.army < city.army) or \
                        (not find_largest and city.army < found_city.army):
                    found_city = city

        if include_general:
            general = self.generals[of_type]
            if found_city is None:
                return general
            if general is not None and ((find_largest and general.army > found_city.army) or (
                    not find_largest and general.army < found_city.army)):
                return general

        return found_city

    def find_largest_tile(self, of_type=None, not_in_path=None,
                          include_general=False):
        # ofType = Integer, notInPath = [Tile], includeGeneral = False|True|Int Acceptable Largest|0.1->0.9 Ratio
        if not_in_path is None:
            not_in_path = []
        if of_type is None:
            of_type = self.player_index
        general = self.generals[of_type]
        if general is None:
            logging.error("ERROR: find_largest_tile encountered general=None for player %d with list %s" % (
                of_type, self.generals))

        largest = None
        for tile in self.tiles[of_type]:  # Check each ofType tile
            if largest is None or largest.army < tile.army:  # New largest
                if not tile.is_general and tile not in not_in_path:  # Exclude general and path
                    largest = tile

        if include_general > 0 and general is not None and general not in not_in_path:  # Handle includeGeneral
            if include_general < 1:
                include_general = general.army * include_general
                if include_general < 6:
                    include_general = 6
            if largest is None:
                largest = general
            elif include_general and largest.army < general.army:
                largest = general
            elif include_general > True and largest.army < general.army and largest.army <= include_general:
                largest = general

        return largest

    def find_primary_target(self, target=None):
        target_type = OPP_EMPTY - 1
        if target is not None and target.should_not_attack():  # Acquired Target
            target = None
        if target is not None:  # Determine Previous Target Type
            target_type = OPP_EMPTY
            if target.is_general:
                target_type = OPP_GENERAL
            elif target.is_city:
                target_type = OPP_CITY
            elif target.army > 0:
                target_type = OPP_ARMY

        # Determine Max Target Size
        largest = self.find_largest_tile(include_general=True)
        max_target_size = largest.army * 1.25

        for x in _shuffle(range(self.cols)):  # Check Each Tile
            for y in _shuffle(range(self.rows)):
                source = self.grid[y][x]
                if not source.is_valid_target() or source.tile == self.player_index:  # Don't target invalid tiles
                    continue

                if target_type <= OPP_GENERAL:  # Search for Generals
                    if source.tile >= 0 and source.is_general and source.army < max_target_size:
                        return source

                if target_type <= OPP_CITY:  # Search for Smallest Cities
                    if source.is_city and source.army < max_target_size:
                        if target_type < OPP_CITY or source.army < target.army:
                            target = source
                            target_type = OPP_CITY

                if target_type <= OPP_ARMY:  # Search for Largest Opponent Armies
                    if source.tile >= 0 and (target is None or source.army > target.army) and not source.is_city:
                        target = source
                        target_type = OPP_ARMY

                if target_type < OPP_EMPTY:  # Search for Empty Squares
                    if source.tile == TILE_EMPTY and source.army < largest.army:
                        target = source
                        target_type = OPP_EMPTY

        return target

    # ======================== Validators ======================== #

    def is_valid_position(self, x, y):
        return 0 <= y < self.rows and 0 <= x < self.cols and self._tile_grid[y][x] != TILE_MOUNTAIN

    def can_complete_path(self, path):
        if len(path) < 2:
            return False

        army_total = 0
        for tile in path:  # Verify can obtain every tile in path
            if tile.is_swamp:
                army_total -= 1

            if tile.tile == self.player_index:
                army_total += tile.army - 1
            elif tile.army + 1 > army_total:  # Cannot obtain tile
                return False
        return True

    def can_step_path(self, path):
        if len(path) < 2:
            return False

        army_total = 0
        for tile in path:  # Verify can obtain at least one tile in path
            if tile.is_swamp:
                army_total -= 1

            if tile.tile == self.player_index:
                army_total += tile.army - 1
            else:
                if tile.army + 1 > army_total:  # Cannot obtain tile
                    return False
                return True
        return True

    # ======================== PRIVATE FUNCTIONS ======================== #

    def _get_scores(self, data):
        scores = {s['i']: s for s in data['scores']}
        scores = [scores[i] for i in range(len(scores))]

        if 'stars' in data:
            self.stars[:] = data['stars']

        return scores

    def _apply_update_diff(self, data):
        if '_map_private' not in dir(self):
            self._map_private = []
            self._cities_private = []
        _apply_diff(self._map_private, data['map_diff'])
        _apply_diff(self._cities_private, data['cities_diff'])

        # Get Number Rows + Columns
        self.rows, self.cols = self._map_private[1], self._map_private[0]

        # Create Updated Tile Grid
        self._tile_grid = [[self._map_private[2 + self.cols * self.rows + y * self.cols + x] for x in range(self.cols)]
                           for y in range(self.rows)]
        # Create Updated Army Grid
        self._army_grid = [[self._map_private[2 + y * self.cols + x] for x in range(self.cols)] for y in
                           range(self.rows)]

        # Update Visible Cities
        self._visible_cities = [(c // self.cols, c % self.cols) for c in self._cities_private]  # returns [(y,x)]

        # Update Visible Generals
        self._visible_generals = [(-1, -1) if g == -1 else (g // self.cols, g % self.cols) for g in
                                  data['generals']]  # returns [(y,x)]

    def _set_neighbors(self):
        for x in range(self.cols):
            for y in range(self.rows):
                self.grid[y][x].set_neighbors(self)

    def _set_swamps(self):
        for (y, x) in self.swamps:
            self.grid[y][x].set_is_swamp(True)

    def _set_generals(self):
        for i, general in enumerate(self._visible_generals):
            if general[0] != -1:
                self.generals[i] = self.grid[general[0]][general[1]]


def _apply_diff(cache, diff):
    i = 0
    a = 0
    while i < len(diff) - 1:
        # offset and length
        a += diff[i]
        n = diff[i + 1]

        cache[a:a + n] = diff[i + 2:i + 2 + n]
        a += n
        i += n + 2

    if i == len(diff) - 1:
        cache[:] = cache[:a + diff[i]]
        i += 1

    assert i == len(diff)


def _shuffle(seq):
    shuffled = list(seq)
    random.shuffle(shuffled)
    return iter(shuffled)
