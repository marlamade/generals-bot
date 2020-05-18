"""
    @ Harris Christiansen (code@HarrisChristiansen.com)
    Generals.io Automated Client - https://github.com/harrischristiansen/generals-bot
    Generals.io Bot Commands
"""

import random
import threading
import time

from .constants import *
from . import generals_api


class BotCommands(object):
    def __init__(self, bot):
        self._bot = bot
        self._permitted_username = ""
        self._map = None

    def set_map(self, game_map):
        self._map = game_map

    # ======================== Bot Commands ======================== #

    def _get_command(self, msg, is_from_chat, username):
        msg_lower = msg.lower()
        command = msg.split(' ')
        command_len = len(command)
        if command_len == 1:
            command = command[0].split(':')  # Handle : delimiters
        base_command = command[0].lower()
        arg_command = " ".join(command[1:])

        # Handle directed commands (ex: myssix pause)
        if command_len > 1 and "_map" in dir(self) and "usernames" in dir(self._map):
            if base_command == self._map.usernames[self._map.player_index].lower():
                command = command[1:]
                command_len = len(command)
                base_command = command[0].lower()
                arg_command = " ".join(command[1:])

        return msg, msg_lower, command, command_len, base_command, arg_command, is_from_chat, username

    def handle_command(self, msg, is_from_chat=False, username=""):
        command_list = self._get_command(msg, is_from_chat, username)

        if self._handle_start_command(command_list):
            return True

        if self._handle_chat_command(command_list):
            return True

        if self._handle_unrestricted_command(command_list):
            return True

        if self._handle_restricted_command(command_list):
            return True

        return False

    def _handle_start_command(self, command_list):
        (msg, msg_lower, command, command_len, base_command, arg_command, is_from_chat, username) = command_list

        if len(msg) < 12 and any(k in msg_lower for k in START_KEYWORDS):
            self._bot.send_forcestart(delay=0)
            self._bot.is_paused = False
            return True
        if len(msg) < 2:
            return True

        return False

    def _handle_chat_command(self, command_list):
        (msg, msg_lower, command, command_len, base_command, arg_command, is_from_chat, username) = command_list

        if self._handle_player_command(msg, username):
            return True
        if base_command.startswith(tuple(HELP_KEYWORDS)):
            self._print_command_help(is_from_chat)
            return True
        if base_command.startswith(tuple(HELLO_KEYWORDS)):
            self._print_command_hello()
            return True

        return False

    def _handle_unrestricted_command(self, command_list):
        (msg, msg_lower, command, command_len, base_command, arg_command, is_from_chat, username) = command_list

        if "setup" in base_command:
            self._bot.set_game_speed(4)
            self._set_game_map()
            self._bot.set_game_public()
            return True
        if "speed" in base_command and command_len >= 2 and command[1][0].isdigit():
            self._bot.set_game_speed(command[1][0])
            return True
        if "public" in base_command:
            self._bot.set_game_public()
            return True

        return False

    def _handle_restricted_command(self, command_list):
        (msg, msg_lower, command, command_len, base_command, arg_command, is_from_chat, username) = command_list

        if self._permitted_username != "" and self._permitted_username != username:  # Only allow permitted user
            return False

        if self._handle_setup_command(command_list):
            return True

        if self._handle_game_command(command_list):
            return True

        return False

    def _handle_setup_command(self, command_list):
        (msg, msg_lower, command, command_len, base_command, arg_command, is_from_chat, username) = command_list

        if "map" in base_command:
            if command_len >= 2:
                self._set_game_map(arg_command)
            else:
                self._set_game_map()
            return True
        elif "normal" in base_command:
            self._set_normal_map()
            return True
        elif "maxsize" in base_command:
            self._bot.set_normal_map(width=1.0, height=1.0)
            return True
        elif "mincity" in base_command:
            self._bot.set_normal_map(city=0.0)
            return True
        elif "maxcity" in base_command:
            self._bot.set_normal_map(city=1.0)
            return True
        elif "minmountain" in base_command:
            self._bot.set_normal_map(mountain=0.0)
            return True
        elif "maxmountain" in base_command:
            self._bot.set_normal_map(mountain=1.0)
            return True
        elif "maxswamp" in base_command:
            self._bot.set_normal_map(swamp=1.0)
            return True
        elif "maxall" in base_command:
            self._bot.set_normal_map(1.0, 1.0, 1.0, 1.0, 1.0)
            return True
        elif "width" in base_command:
            if command_len == 2:
                try:
                    self._bot.set_normal_map(width=float(arg_command))
                    return True
                except ValueError:
                    pass
            self._bot.set_normal_map(width=1.0)
            return True
        elif "height" in base_command:
            if command_len == 2:
                try:
                    self._bot.set_normal_map(height=float(arg_command))
                    return True
                except ValueError:
                    pass
            self._bot.set_normal_map(height=1.0)
            return True
        elif "city" in base_command:
            if command_len == 2:
                try:
                    self._bot.set_normal_map(city=float(arg_command))
                    return True
                except ValueError:
                    pass
            self._bot.set_normal_map(city=1.0)
            return True
        elif "mountain" in base_command:
            if command_len == 2:
                try:
                    self._bot.set_normal_map(mountain=float(arg_command))
                    return True
                except ValueError:
                    pass
            self._bot.set_normal_map(mountain=1.0)
            return True
        elif "swamp" in base_command:
            if command_len == 2:
                try:
                    self._set_swamp_map(float(arg_command))
                    return True
                except ValueError:
                    pass
            self._set_swamp_map()
            return True
        elif is_from_chat and len(msg) < 12 and "map" in msg_lower:
            self._set_game_map()
            return True

        return False

    def _handle_game_command(self, command_list):
        (msg, msg_lower, command, command_len, base_command, arg_command, is_from_chat, username) = command_list

        if "take" in base_command and username != "":
            self._permitted_username = username
        elif "team" in base_command:
            if command_len >= 2:
                if len(command[1]) == 1:
                    self._bot.set_game_team(command[1])
                else:
                    return self._add_teammate(arg_command)
            elif base_command in ["unteamall"]:
                self._remove_all_teammates()
            elif base_command in ["unteam", "cancelteam"]:
                self._remove_teammate(username)
            elif base_command in ["noteam"]:
                _spawn(self._start_avoiding_team)
            else:
                return self._add_teammate(username)
            return True
        elif "bye!" in base_command:
            if "_map" in dir(self):
                # self._map.exit_on_game_over = False # Wait 2 minutes before exiting
                self._bot.send_surrender()
            return True

        elif "unpause" in base_command:
            self._bot.is_paused = False
            return True
        elif "pause" in base_command:
            self._bot.is_paused = True
            return True

        return False

    # ======================== Sending Messages ======================== #

    def _print_command_help(self, is_from_chat=False):
        if is_from_chat:
            self._bot.sent_hello = True
            for txt in GAME_HELP_TEXT if "_map" in dir(self) else PRE_HELP_TEXT:
                self._bot.send_chat(txt)
                time.sleep(0.34)
        else:
            print("\n".join(GAME_HELP_TEXT if "_map" in dir(self) else PRE_HELP_TEXT))

    def _print_command_hello(self):
        if "sent_hello" in dir(self._bot):
            return True
        self._bot.sent_hello = True

        for txt in GAME_HELLO_TEXT if "_map" in dir(self) else HELLO_TEXT:
            self._bot.send_chat(txt)
            time.sleep(0.34)

    # ======================== Teammates ======================== #

    def _add_teammate(self, username):
        if "_map" in dir(self) and "usernames" in dir(self._map):
            if username != "" and username != self._map.usernames[self._map.player_index] and \
                    username in self._map.usernames:
                self._map.do_not_attack_players.append(self._map.usernames.index(username))
                return True
        return False

    def _remove_teammate(self, username):
        if "_map" in dir(self) and "usernames" in dir(self._map):
            if username != "" and username != self._map.usernames[self._map.player_index]:
                if self._map.usernames.index(username) in self._map.do_not_attack_players:
                    self._map.do_not_attack_players.remove(self._map.usernames.index(username))
                    return True
        return False

    def _remove_all_teammates(self):
        self._map.do_not_attack_players = []
        return True

    def _start_avoiding_team(self):
        while True:
            if "teams" not in dir(self._bot):
                time.sleep(0.1)
                continue
            for i, members in self._bot.teams.items():
                if self._bot.username in members:
                    if len(members) > 1:  # More than 1 person on bots team
                        for team in range(1, MAX_NUM_TEAMS + 1):
                            if team not in self._bot.teams:
                                self._bot.set_game_team(team)
                                break

            time.sleep(0.1)

    # ======================== Set Custom Gamemap ======================== #

    def _set_game_map(self, map_name=""):
        if len(map_name) > 1:
            map_lower = map_name.lower()
            if map_lower in ["win", "good"]:
                self._bot.set_game_map(random.choice(GENERALS_MAPS))
            elif map_lower == "top":
                self._bot.set_game_map(random.choice(generals_api.list_top()))
            elif map_lower == "hot":
                self._bot.set_game_map(random.choice(generals_api.list_hot()))
            else:
                maps = generals_api.list_search(map_name)
                if map_name in maps:
                    self._bot.set_game_map(map_name)
                elif len(maps) >= 1:
                    self._bot.set_game_map(maps[0])
                    self._bot.send_chat("I could not find " + map_name + ", so I set the map to " + maps[
                        0] + " (Note: names are case sensitive)")
                else:
                    self._bot.send_chat("Could not find map named " + map_name + " (Note: names are case sensitive)")
        else:
            self._bot.set_game_map(random.choice(generals_api.list_both()))

    def _set_normal_map(self):
        width = round(random.uniform(0, 1), 2)
        height = round(random.uniform(0, 1), 2)
        city = round(random.uniform(0, 1), 2)
        mountain = round(random.uniform(0, 1), 2)
        self._bot.set_normal_map(width, height, city, mountain)

    def _set_swamp_map(self, swamp=-1):
        if swamp == -1:
            swamp = round(random.uniform(0, 1), 2)
        if 0 <= swamp <= 1:
            self._bot.set_normal_map(swamp=swamp)

    # ======================== Player Requested Commands ======================== #

    def _handle_player_command(self, msg, username):
        if "boomer" in username.lower():
            self._bot.send_chat("Okay Boomer <3")
            return True

        return False


def _spawn(f):
    t = threading.Thread(target=f)
    t.daemon = True
    t.start()
