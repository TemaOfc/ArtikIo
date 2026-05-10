import time
import random
from shared.config import *
from shared.words import get_random_word_pair
from server.logger import log_info, log_debug, log_warning, log_error

class Player:
    def __init__(self, sid, name):
        self.sid = sid
        self.name = name
        self.score = 0
        self.guessed = False
        self.guess_time = None
        self.guess_order = None

class GameRoom:
    def __init__(self, room_id):
        self.room_id = room_id
        self.players = {}
        self.current_drawer = None
        self.current_word = None
        self.word_choices = None
        self.round_start_time = None
        self.round_active = False
        self.choosing_word = False
        self.guess_order_counter = 0
        self.canvas_data = []
        self.canvas_snapshot = None  # Полное состояние холста в base64
        self.last_snapshot_time = 0

    def add_player(self, sid, name):
        if len(self.players) >= MAX_PLAYERS:
            return False
        self.players[sid] = Player(sid, name)
        return True

    def remove_player(self, sid):
        if sid in self.players:
            del self.players[sid]
            if sid == self.current_drawer:
                self.end_round()

    def get_next_drawer(self):
        if not self.players:
            return None

        player_list = list(self.players.keys())

        log_debug("get_next_drawer: player_list",
                  room_id=self.room_id,
                  players=[self.players[p].name for p in player_list])
        log_debug("get_next_drawer: current_drawer",
                  room_id=self.room_id,
                  current_drawer=self.players[self.current_drawer].name if self.current_drawer else None)

        if self.current_drawer is None:
            return player_list[0]

        try:
            current_index = player_list.index(self.current_drawer)
            next_index = (current_index + 1) % len(player_list)
            next_drawer = player_list[next_index]
            log_debug("get_next_drawer: next_drawer",
                      room_id=self.room_id,
                      next_drawer=self.players[next_drawer].name)
            return next_drawer
        except ValueError:
            return player_list[0]

    def start_word_choice(self):
        old_drawer = self.current_drawer
        log_debug("start_word_choice: current_drawer before",
                  room_id=self.room_id,
                  current_drawer=self.players[old_drawer].name if old_drawer and old_drawer in self.players else None)
        self.current_drawer = self.get_next_drawer()
        log_debug("start_word_choice: current_drawer after",
                  room_id=self.room_id,
                  current_drawer=self.players[self.current_drawer].name if self.current_drawer else None)
        if not self.current_drawer:
            return None

        self.word_choices = get_random_word_pair()
        self.choosing_word = True
        self.round_active = False

        return {
            'drawer': self.current_drawer,
            'drawer_name': self.players[self.current_drawer].name,
            'choices': self.word_choices
        }

    def choose_word(self, word):
        if word not in self.word_choices:
            return False

        # Нормализуем слово: убираем лишние пробелы и приводим к нижнему регистру
        self.current_word = ' '.join(word.strip().lower().split())
        self.choosing_word = False
        self.round_active = True
        self.round_start_time = time.time()
        self.guess_order_counter = 0
        self.canvas_data = []

        for player in self.players.values():
            player.guessed = False
            player.guess_time = None
            player.guess_order = None

        return True

    def make_guess(self, sid, result):
        if sid not in self.players or sid == self.current_drawer:
            return None

        player = self.players[sid]

        if player.guessed:
            return None

        if result == "correct":
            player.guessed = True
            player.guess_time = time.time() - self.round_start_time
            self.guess_order_counter += 1
            player.guess_order = self.guess_order_counter

            guesser_points = self.calculate_guesser_points(player.guess_time, player.guess_order)
            drawer_points = self.calculate_drawer_points(guesser_points)

            player.score += guesser_points

            drawer = self.players[self.current_drawer]
            drawer.score += drawer_points

            all_guessed = all(p.guessed for p in self.players.values() if p.sid != self.current_drawer)

            return {
                'guesser': sid,
                'guesser_name': player.name,
                'guesser_points': guesser_points,
                'drawer_points': drawer_points,
                'all_guessed': all_guessed
            }

        return None

    def calculate_guesser_points(self, guess_time, guess_order):
        time_factor = max(0, 1 - (guess_time / ROUND_TIME))
        order_factor = max(0.3, 1 - (guess_order - 1) * 0.15)

        points = int(BASE_POINTS_GUESSER * time_factor * order_factor)
        return max(5, points)

    def calculate_drawer_points(self, guesser_points):
        return guesser_points + 1

    def end_round(self):
        self.round_active = False
        self.choosing_word = False
        self.current_word = None
        self.word_choices = None
        self.canvas_data = []

    def get_time_left(self):
        if not self.round_active or not self.round_start_time:
            return 0

        elapsed = time.time() - self.round_start_time
        return max(0, ROUND_TIME - int(elapsed))

    def check_winner(self):
        for player in self.players.values():
            if player.score >= POINTS_TO_WIN:
                return player
        return None

    def get_scoreboard(self):
        return [
            {
                'sid': p.sid,
                'name': p.name,
                'score': p.score,
                'guessed': p.guessed
            }
            for p in sorted(self.players.values(), key=lambda x: x.score, reverse=True)
        ]

    def add_canvas_action(self, action):
        self.canvas_data.append(action)

    def get_canvas_data(self):
        return self.canvas_data

    def set_canvas_snapshot(self, snapshot):
        self.canvas_snapshot = snapshot
        self.last_snapshot_time = time.time()

    def get_canvas_snapshot(self):
        return self.canvas_snapshot

    def should_sync_snapshot(self):
        # Синхронизировать каждые 2 секунды
        return time.time() - self.last_snapshot_time > 2

class GameManager:
    def __init__(self):
        self.rooms = {}

    def create_room(self, room_id):
        if room_id not in self.rooms:
            self.rooms[room_id] = GameRoom(room_id)
        return self.rooms[room_id]

    def get_room(self, room_id):
        return self.rooms.get(room_id)

    def delete_room(self, room_id):
        if room_id in self.rooms:
            del self.rooms[room_id]

game_manager = GameManager()
