"""
    @ Harris Christiansen (code@HarrisChristiansen.com)
    Generals.io Automated Client - https://github.com/harrischristiansen/generals-bot
    Tile: Objects for representing Generals IO Tiles
"""

from queue import Queue
import time
import logging

from .constants import *


class Tile(object):
    def __init__(self, game_map, x, y):
        # Public Properties
        self.x = x  # Integer X Coordinate
        self.y = y  # Integer Y Coordinate
        self.tile = TILE_FOG  # Integer Tile Type (TILE_OBSTACLE, TILE_FOG, TILE_MOUNTAIN, TILE_EMPTY, or player_ID)
        self.turn_captured = 0  # Integer Turn Tile Last Captured
        self.turn_held = 0  # Integer Last Turn Held
        self.army = 0  # Integer Army Count
        self.is_city = False  # Boolean isCity
        self.is_swamp = False  # Boolean isSwamp
        self.is_general = False  # Boolean isGeneral

        # Private Properties
        self._map = game_map  # Pointer to Map Object
        self._general_index = -1  # Player Index if tile is a general
        self._dirty_update_time = 0  # Last time Tile was updated by bot, not server

    def __repr__(self):
        return "(%2d,%2d)[%2d,%3d]" % (self.x, self.y, self.tile, self.army)

    """def __eq__(self, other):
            return (other is not None and self.x==other.x and self.y==other.y)"""

    def __lt__(self, other):
        return self.army < other.army

    def set_neighbors(self, game_map):
        self._map = game_map
        self._set_neighbors()

    def set_is_swamp(self, is_swamp):
        self.is_swamp = is_swamp

    def update(self, game_map, tile, army, is_city=False, is_general=False, is_dirty=False):
        self._map = game_map

        if is_dirty:
            self._dirty_update_time = time.time()

        if self.tile < 0 or tile >= TILE_MOUNTAIN or (tile < TILE_MOUNTAIN and self.is_self()):
            # Tile should be updated
            if (tile >= 0 or self.tile >= 0) and self.tile != tile:  # Remember Discovered Tiles
                self.turn_captured = game_map.turn
                if self.tile >= 0:
                    game_map.tiles[self.tile].remove(self)
                if tile >= 0:
                    game_map.tiles[tile].append(self)
            if tile == game_map.player_index:
                self.turn_held = game_map.turn
            self.tile = tile
        if self.army == 0 or army > 0 or tile >= TILE_MOUNTAIN or self.is_swamp:  # Remember Discovered Armies
            self.army = army

        if is_city:
            self.is_city = True
            self.is_general = False
            if self not in game_map.cities:
                game_map.cities.append(self)
            if self._general_index != -1 and self._general_index < 8:
                game_map.generals[self._general_index] = None
                self._general_index = -1
        elif is_general:
            self.is_general = True
            game_map.generals[tile] = self
            self._general_index = self.tile

    # ======================== Tile Properties ======================== #

    def is_dirty(self):
        return (time.time() - self._dirty_update_time) < 0.6

    def distance_to(self, dest):
        if dest is not None:
            return abs(self.x - dest.x) + abs(self.y - dest.y)
        return 0

    def neighbors(self, include_swamps=False, include_cities=True):
        neighbors = []
        for tile in self._neighbors:
            if (tile.tile != TILE_OBSTACLE or tile.is_city or tile.is_general) and tile.tile != TILE_MOUNTAIN and (
                    include_swamps or not tile.is_swamp) and (include_cities or not tile.is_city):
                neighbors.append(tile)
        return neighbors

    def is_valid_target(self):  # Check tile to verify reachability
        if self.tile < TILE_EMPTY:
            return False
        for tile in self.neighbors(include_swamps=True):
            if tile.turn_held > 0:
                return True
        return False

    def is_empty(self):
        return self.tile == TILE_EMPTY

    def is_self(self):
        return self.tile == self._map.player_index

    def is_on_team(self):
        if self.is_self():
            return True
        return False

    def should_not_attack(self):  # DEPRECATED: Use Tile.shouldAttack
        return not self.should_attack()

    def should_attack(self):
        if not self.is_valid_target():
            return False
        if self.is_on_team():
            return False
        if self.tile in self._map.do_not_attack_players:
            return False
        if self.is_dirty():
            return False
        return True

    # ======================== Select Neighboring Tile ======================== #

    def neighbor_to_attack(self, path=None):
        if path is None:
            path = []
        if not self.is_self():
            return None

        target = None
        for neighbor in self.neighbors(include_swamps=True):
            # Move into caputurable target Tiles
            if (neighbor.should_attack() and self.army > neighbor.army + 1) or neighbor in path:
                if not neighbor.is_swamp:
                    if target is None:
                        target = neighbor
                    elif neighbor.is_city and (not target.is_city or target.army > neighbor.army):
                        target = neighbor
                    # Special case, prioritize opponents with 1 army over empty tiles
                    elif not neighbor.is_empty and neighbor.army <= 1 and target.is_empty:
                        target = neighbor
                    elif target.army > neighbor.army and not target.is_city:
                        if neighbor.is_empty:
                            if target.army > 1:
                                target = neighbor
                        else:
                            target = neighbor
                elif neighbor.turn_held == 0:  # Move into swamps that we have never held before
                    target = neighbor

        return target

    # ======================== Select Distant Tile ======================== #

    def nearest_tile_in_path(self, path):
        dest = None
        dest_distance = 9999
        for tile in path:
            distance = self.distance_to(tile)
            if distance < tile_distance:
                dest = tile
                dest_distance = distance

        return dest

    def nearest_target_tile(self):
        if not self.is_self():
            return None

        max_target_army = self.army * 4 + 14

        dest = None
        dest_distance = 9999
        for x in range(self._map.cols):  # Check Each Square
            for y in range(self._map.rows):
                tile = self._map.grid[y][x]
                # Non Target Tiles
                if not tile.is_valid_target() or tile.should_not_attack() or tile.army > max_target_army:
                    continue

                distance = self.distance_to(tile)
                if tile.is_general:  # Generals appear closer
                    distance = distance * 0.09
                elif tile.is_city:  # Cities vary distance based on size, but appear closer
                    distance = distance * sorted((0.17, (tile.army / (3.2 * self.army)), 20))[1]

                if tile.tile == TILE_EMPTY:  # Empties appear further away
                    if tile.is_city:
                        distance = distance * 1.6
                    else:
                        distance = distance * 4.3

                if tile.army > self.army:  # Larger targets appear further away
                    distance = distance * (1.6 * tile.army / self.army)

                if tile.is_swamp:  # Swamps appear further away
                    distance = distance * 10
                    if tile.turn_held > 0:  # Swamps which have been held appear even further away
                        distance = distance * 3

                if distance < dest_distance:  # ----- Set nearest target -----
                    dest = tile
                    dest_distance = distance

        return dest

    # ======================== Pathfinding ======================== #

    def path_to(self, dest, include_cities=False):
        if dest is None:
            return []

        frontier = Queue()
        frontier.put(self)
        came_from = {self: None}
        army_count = {self: self.army}
        processed = set()

        while not frontier.empty():
            current = frontier.get()

            if current == dest:  # Found Destination
                break

            for next in current.neighbors(include_swamps=True, include_cities=include_cities):
                if next not in processed and (next.is_on_team() or next == dest or next.army < army_count[current]):
                    # priority = self.distance(next, dest)
                    if next not in came_from:
                        frontier.put(next)
                    if next.is_on_team():
                        next_army_count = army_count[current] + (next.army - 1)
                    else:
                        next_army_count = army_count[current] - (next.army + 1)
                    if next not in army_count or next_army_count > army_count[next]:
                        army_count[next] = next_army_count
                        came_from[next] = current

            processed.add(current)

        if dest not in came_from:  # Did not find dest
            if include_cities:
                return []
            else:
                return self.path_to(dest, include_cities=True)

        # Create Path List
        path = _path_reconstruct(came_from, dest)

        return path

    # ======================== PRIVATE FUNCTIONS ======================== #

    def _set_neighbors(self):
        x = self.x
        y = self.y

        neighbors = []
        for dy, dx in DIRECTIONS:
            if self._map.is_valid_position(x + dx, y + dy):
                tile = self._map.grid[y + dy][x + dx]
                neighbors.append(tile)

        self._neighbors = neighbors
        return neighbors


def _path_reconstruct(came_from, dest):
    current = dest
    path = [current]
    try:
        while came_from[current] is not None:
            current = came_from[current]
            path.append(current)
    except KeyError:
        pass
    path.reverse()

    return path
