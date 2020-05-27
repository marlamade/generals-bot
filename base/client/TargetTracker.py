from typing import List

from .tile import Tile


class TargetTracker(list):
    """
    Track the targets that might be good to attack/explore
    """
    def __init__(self, *args, **kwargs):
        list.__init__(self, *args, **kwargs)
        self.turn_last_updated: int = 0

    def update_list(self, target_list: List[Tile], current_turn):
        self.extend(target_list)
        self.turn_last_updated = current_turn

    def get_target(self, turn):
        # print(self)
        if turn > 1.5 * self.turn_last_updated + 30:
            # if we haven't gotten an updated list since a third of the game ago,
            # it's too old and we should throw it away
            while self:
                self.pop()
        while self:
            target = self[-1]
            if target.is_city or target.is_mountain or target.is_basic or target.is_general:
                self.pop()
                continue
            return target
        return None

