#! /usr/bin/env python3
import sys
import yaml
import string
import random
import logging
from pathlib import Path
from datetime import datetime
from duckling.lib.udp import MaexchenUdpClient, MaexchenConnectionError

class Move():
    def __init__(self):
        self._truth = None
        self._announced = None
        self._accused = False
        self._player = None

    def set_truth(self, truth):
        self._truth = truth

    def set_announced(self, announced):
        self._announced = announced

    def set_accused(self, accused):
        self._accused = accused

    def set_player(self, players):
        self._player = players

    def get_truth(self):
        return self._truth

    def get_announced(self):
        return self._announced

    def get_accused(self):
        return self._accused

    def get_player(self):
        return self._player

    def get_lied(self):
        if self.get_truth() is not None and self.get_announced() is not None:
            return self.get_truth() != self.get_announced()

    def serialize(self):
        return {
            "truth": self.get_truth(),
            "announced": self.get_announced(),
            "lied": self.get_lied(),
            "accused": self.get_accused(),
            "player": self.get_player(),
        }


class Round():
    def __init__(self, idx, players):
        self._idx = idx
        self._time = datetime.now()
        self._players = players
        self._moves = []

    def add_move(self, move):
        self._moves.append(move)

    def get_idx(self):
        return self._idx

    def get_time(self):
        return self._time

    def get_players(self):
        return self._players

    def get_moves(self):
        return self._moves

    def serialize(self):
        moves = [move.serialize() for move in self.get_moves()]
        return {
            "round_number": self.get_idx(),
            "time": self.get_time(),
            "players": self.get_players(),
            "moves": moves,
        }


class GameLogger():
    def __init__(self, base_save_path, save_interval=100, spectator_name="spectator", rand_name_suffix=True, server_ip="35.159.50.117", server_port=9000, buffer_size=1024):
        """
        Creates a GameLogger.

        :param str base_save_path: Base path of where to save the logs
        :param int save_interval: Saving after each interval
        :param str spectator_name: The name of the spectator.
        :param bool rand_name_suffix: Add a random suffix to the name. This enables two multiple spectators.
        :param str server_ip: IP of the server.
        :param int server_port: Port of the server.
        :param int buffer_size: Size of the Buffer.
        """
        self._save_path = Path(base_save_path) / Path("mia_" + datetime.now().strftime("%d-%m-%Y_%H:%M:%S") + ".yaml")
        self._save_interval = save_interval

        # Placeholders
        self._rounds = []

        self._udp_client = MaexchenUdpClient()

        # Set or generate the bot name
        if rand_name_suffix:
            self._spectator_name = spectator_name + "x" + \
                ''.join(random.choice(string.ascii_lowercase) for i in range(3))
        else:
            self._spectator_name = spectator_name

        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(logging.DEBUG)

        self.start()

    def start(self):
        """ 
        Start the game for your spectator (non blocking).
        It joins the game on the next possibility.
        """
        print(f"LOGGING DATA to '{self._save_path}'...")
        self._udp_client.send_message(f"REGISTER_SPECTATOR;{self._spectator_name}")
        self._main_loop()

    def close(self):
        """
        Closes the Bots connection.
        """
        print("CLOSING CONNECTION...")
        self._udp_client.send_message("UNREGISTER")
        self._udp_client.close()
        print("CONNECTION CLOSED")
        self._save_data()
        print(f"LOG DATA saved to '{self._save_path}'")

    def _main_loop(self):
            """
            Runs the main loop which listens for messages from the server.
            """
            round_count = 0  # Used for save interval
            while True:
                try:
                    message = self._udp_client.await_commands(["ROUND STARTED"])  # Round started
                    idx = message.split(";")[1]
                    players = message.split(";")[2].split(",")
                    self._rounds.append(Round(idx, players))
                    self._current_player_counter = 0
                    self._listen_move()
                    if round_count % self._save_interval == 0:
                        self._save_data()
                    round_count += 1

                except KeyboardInterrupt:
                    self.close()
                    exit(0)

    def _listen_move(self):
        """
        Recursively listens to the game moves until round is finished.
        """
        message = self._udp_client.await_commands(["ANNOUNCED", "SCORE"])
        split = message.split(";")
        if split[0] == "SCORE":
            return
        move = Move()
        self._rounds[-1].add_move(move)
        players = self._rounds[-1].get_players()
        move.set_player(players[self._current_player_counter])
        move.set_announced(tuple([int(i) for i in split[2].split(",")]))
        self._current_player_counter = (self._current_player_counter + 1) % len(players)

        message = self._udp_client.await_commands(["ACTUAL DICE", "PLAYER ROLLS", "SCORE"])
        split = message.split(";")
        cmd = split[0]
        if cmd == "SCORE":
            return
        elif cmd == "ACTUAL DICE":
            move.set_accused(True)
            move.set_truth(tuple([int(i) for i in split[1].split(",")]))

        elif cmd == "PLAYER ROLLS":
            self._listen_move()

    def _save_data(self):
        print("Saving data...")
        data = [r.serialize() for r in self._rounds]
        with open(self._save_path, 'w') as save_file:
            yaml.dump(data, save_file)


if __name__ == "__main__":
    GameLogger(sys.argv[1], spectator_name="SpectatorTeam8")
