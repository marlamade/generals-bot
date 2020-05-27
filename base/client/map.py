"""
    @ Harris Christiansen (code@HarrisChristiansen.com)
    Generals.io Automated Client - https://github.com/harrischristiansen/generals-bot
    Map: Objects for representing Generals IO Map
"""

import logging
from collections import deque
import time
from typing import List

from .constants import *
from .tile import Tile
from .TargetTracker import TargetTracker


class Map(object):
    def __init__(self, start_data, data):
        # Start Data
        self._start_data = start_data
        self.player_index = start_data['playerIndex']  # Integer Player Index
        self.usernames = start_data['usernames']  # List of String Usernames
        self.my_team = self._get_my_team(start_data['teams'])
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
        self.exploration_targets = TargetTracker()

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

    def find_largest_tile(
            self,
            of_type: int = None,
            tiles_to_exclude: List[Tile] = None,
            include_general=False
    ):
        """

        :param of_type: the player who's tiles are under consideration
        :param tiles_to_exclude:
        :param include_general: if 0, don't include the general. if 1, include the general.
            If between 0 and 1, multiply the general's army by this number and then include it.
            If greater than 1, include the general only if all other armies are less than this number.
        :return: The tile belonging to player of_type with the most armies
        """
        # ofType = Integer, notInPath = [Tile], includeGeneral = False|True|Int Acceptable Largest|0.1->0.9 Ratio
        if tiles_to_exclude is None:
            tiles_to_exclude = []
        if of_type is None:
            of_type = self.player_index
        general = self.generals[of_type]
        if general is None:
            logging.error("ERROR: find_largest_tile encountered general=None for player %d with list %s" % (
                of_type, self.generals))

        largest = None
        for tile in self.tiles[of_type]:  # Check each ofType tile
            if largest is None or largest.army < tile.army:  # New largest
                if not tile.is_general and tile not in tiles_to_exclude:  # Exclude general and path
                    largest = tile

        if include_general > 0 and general is not None and general not in tiles_to_exclude:  # Handle includeGeneral
            if include_general < 1:
                include_general = general.army * include_general
                if include_general < 6:
                    include_general = 6
            if largest is None:
                largest = general
            elif include_general == 1 and largest.army < general.army:
                largest = general
            elif include_general > 1 and largest.army < general.army and largest.army <= include_general:
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

    def find_exploration_targets(self):
        print("find exploration start: time %s, turn %s" % (time.time(), self.turn))
        obstacles = []
        fog = []
        bfs_queue: deque[Tile] = deque(self.tiles[self.player_index])
        processed = set()

        while bfs_queue:
            current = bfs_queue.popleft()
            if current in processed:
                continue
            if current.tile == TILE_OBSTACLE and not current.is_city and not current.is_mountain:
                obstacles.append(current)
            elif current.tile == TILE_FOG and not current.is_general and not current.is_basic:
                fog.append(current)
            processed.add(current)
            for neighbor in current.neighbors(True, True, True):
                if not neighbor.is_mountain:
                    bfs_queue.append(neighbor)

        print(obstacles)
        obstacles.reverse()
        fog.reverse()
        self.exploration_targets.update_list(obstacles, self.turn)
        print("find exploration end: time %s, turn %s" % (time.time(), self.turn))

    def get_exploration_target(self):
        target = self.exploration_targets.get_target(self.turn)
        if target is None:
            self.find_exploration_targets()
            target = self.exploration_targets.get_target(self.turn)
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
        print_cities = data['turn'] % 30 == 0
        if '_map_private' not in dir(self):
            self._map_private = []
            self._cities_private = []
        # if print_cities:
        #     print("Turn", data['turn'])
        #     print(self._cities_private)
        #     print(data['cities_diff'])
        _apply_diff(self._map_private, data['map_diff'])
        _apply_diff(self._cities_private, data['cities_diff'])
        # if print_cities:
        #     print(self._cities_private)
        #     print("\n")

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

    def _get_my_team(self, team_list):
        return [
            player_id
            for player_id, team in enumerate(team_list)
            if team == team_list[self.player_index]
        ]

def _apply_diff(cache, diff):
    """
    Input from generals.io assumes you are storing all data in arrays: one array
    describing most of the board state, and a second array just listing the cities.
    Updates from generals.io comes in the form of a diff array which has the following format:
    [u0, n0, x00, x01, ..., x0{n0-1}, u1, n1, x10, x11, x12, ..., x1{n1-1}, ... uk, ..., xk{nk-1}, u{k+1}?]
    Where u0 is the number of initial entries that do not need to change, n0 is the length of the first
    section that needs to change, [x00, ..., x0{n0-1}] are the new values for those entries, u1 is the
    number of entries after that that do not need to change, etc. If there is stuff at the end that does
    not need to change, the array will end with a u{k+1}
    :param cache: a "passed by reference" array that we are going to modify with this diff
    :param diff: the diff from the file.
    :return:
    """
    i = 0  # the current index of the diff array
    a = 0  # the current index of the cache array
    while i < len(diff) - 1:
        # diff[i] = the number of entries that do not need to change (u)
        # diff[i+1] =  the number of entries that do need to change (n)
        # diff[i+2:i+2+n] = the new values (x)
        a += diff[i]
        n = diff[i + 1]

        cache[a:a + n] = diff[i + 2:i + 2 + n]
        a += n
        i += n + 2

    if i == len(diff) - 1:
        # if there is a u{k+1} at the end, we go u{k+1} entries more and then truncate the rest of
        # the array. This statement should never have any affect.
        cache[:] = cache[:a + diff[i]]
        i += 1

    assert i == len(diff)


def _shuffle(seq):
    shuffled = list(seq)
    random.shuffle(shuffled)
    return iter(shuffled)
