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
        self.guessed_parts = set()  # Отгаданные части многословной фразы
        self.hints_used = 0  # Количество использованных подсказок
        self.revealed_letters = set()  # Открытые буквы для этого игрока

class GameRoom:
    def __init__(self, room_id, settings=None):
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
        self.canvas_snapshot = None
        self.last_snapshot_time = 0
        self.word_choice_timer_id = 0  # ID текущего таймера выбора слова
        self.guessed_parts = set()  # Глобально отгаданные части слова
        self.hints_given = 0  # Количество выданных подсказок в текущем раунде
        self.hint_timers = []  # Таймеры для подсказок

        # Настройки лобби
        if settings:
            self.password = settings.get('password')
            self.max_players = settings.get('max_players', MAX_PLAYERS)
            self.round_time = settings.get('round_time', ROUND_TIME)
            self.word_choice_time = settings.get('word_choice_time', WORD_CHOICE_TIME)
            self.points_to_win = settings.get('points_to_win', POINTS_TO_WIN)
            self.hints_per_round = settings.get('hints_per_round', 0)
            self.themes = settings.get('themes', ['general'])
        else:
            self.password = None
            self.max_players = MAX_PLAYERS
            self.round_time = ROUND_TIME
            self.word_choice_time = WORD_CHOICE_TIME
            self.points_to_win = POINTS_TO_WIN
            self.hints_per_round = 0
            self.themes = ['general']

    def add_player(self, sid, name):
        if len(self.players) >= self.max_players:
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
                  current_drawer=self.players[self.current_drawer].name if self.current_drawer and self.current_drawer in self.players else None)

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

        from shared.words import get_random_word_pair
        from shared.word_weights import get_word_weight

        self.word_choices = get_random_word_pair(self.themes)
        self.choosing_word = True
        self.round_active = False

        # Увеличиваем ID таймера, чтобы старые таймеры стали невалидными
        self.word_choice_timer_id += 1

        # Получаем веса для каждого слова
        weights = [get_word_weight(word) for word in self.word_choices]

        return {
            'drawer': self.current_drawer,
            'drawer_name': self.players[self.current_drawer].name,
            'choices': self.word_choices,
            'weights': weights,
            'timer_id': self.word_choice_timer_id
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
        self.guessed_parts = set()  # Сбрасываем отгаданные части
        self.hints_given = 0  # Сбрасываем счетчик подсказок

        for player in self.players.values():
            player.guessed = False
            player.guess_time = None
            player.guess_order = None
            player.guessed_parts = set()  # Сбрасываем отгаданные части игрока
            player.hints_used = 0  # Сбрасываем использованные подсказки
            player.revealed_letters = set()  # Сбрасываем открытые буквы

        return True

    def make_guess(self, sid, result, guessed_word=None):
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

            guesser_points = self.calculate_guesser_points(player.guess_time, player.guess_order, player.hints_used)
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
                'all_guessed': all_guessed,
                'hints_used': player.hints_used
            }
        elif result == "partial":
            # Частичное отгадывание - добавляем отгаданную часть
            if guessed_word:
                player.guessed_parts.add(guessed_word)
                self.guessed_parts.add(guessed_word)

                # Проверяем, все ли части отгаданы
                word_parts = set(self.current_word.split())
                if player.guessed_parts == word_parts:
                    # Все части отгаданы - засчитываем полное слово
                    player.guessed = True
                    player.guess_time = time.time() - self.round_start_time
                    self.guess_order_counter += 1
                    player.guess_order = self.guess_order_counter

                    guesser_points = self.calculate_guesser_points(player.guess_time, player.guess_order, player.hints_used)
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
                        'all_guessed': all_guessed,
                        'partial_complete': True,
                        'hints_used': player.hints_used
                    }
                else:
                    # Частично отгадано, но не все
                    return {
                        'guesser': sid,
                        'guesser_name': player.name,
                        'partial': True,
                        'guessed_word': guessed_word
                    }

        return None

    def calculate_guesser_points(self, guess_time, guess_order, hints_used=0):
        from shared.word_weights import get_word_weight

        # Базовые факторы
        time_factor = max(0, 1 - (guess_time / self.round_time))
        order_factor = max(0.3, 1 - (guess_order - 1) * 0.15)

        # Фактор сложности слова (1-5 -> 0.8-1.6)
        # Легкие слова дают меньше очков, сложные - больше
        word_weight = get_word_weight(self.current_word)
        difficulty_factor = 0.6 + (word_weight * 0.2)  # 1->0.8, 3->1.2, 5->1.6

        # Фактор подсказок - чем больше подсказок использовано, тем меньше очков
        # Также учитываем длину слова
        word_length = len(self.current_word.replace(' ', ''))  # Длина без пробелов

        if hints_used > 0:
            # Базовый штраф за использование подсказок
            hint_penalty = 1 - (hints_used * 0.25)  # -25% за каждую подсказку

            # Дополнительный штраф для коротких слов
            if word_length <= 5:
                hint_penalty *= 0.6  # Еще -40% для очень коротких слов
            elif word_length <= 8:
                hint_penalty *= 0.8  # Еще -20% для коротких слов

            # Если открыто слишком много букв относительно длины слова
            reveal_ratio = hints_used / max(1, word_length)
            if reveal_ratio >= 0.5:  # Открыто 50% или больше букв
                hint_penalty *= 0.5  # Еще -50%

            hint_penalty = max(0, hint_penalty)  # Не меньше 0
        else:
            hint_penalty = 1.0

        points = int(BASE_POINTS_GUESSER * time_factor * order_factor * difficulty_factor * hint_penalty)
        return max(1, points)  # Минимум 1 очко, если отгадал

    def calculate_drawer_points(self, guesser_points):
        # Рисующий получает немного больше, чем отгадавший
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
        return max(0, self.round_time - int(elapsed))

    def check_winner(self):
        for player in self.players.values():
            if player.score >= self.points_to_win:
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

    def get_lobby_info(self):
        """Получить информацию о лобби для списка"""
        return {
            'room_id': self.room_id,
            'password': self.password is not None,
            'current_players': len(self.players),
            'max_players': self.max_players,
            'round_time': self.round_time,
            'word_choice_time': self.word_choice_time,
            'points_to_win': self.points_to_win,
            'themes': self.themes,
            'round_active': self.round_active
        }

    def verify_password(self, password):
        """Проверить пароль лобби"""
        if self.password is None:
            return True
        return self.password == password

    def reveal_letter_for_player(self, sid, letter_index):
        """Открыть букву для конкретного игрока"""
        if sid not in self.players or sid == self.current_drawer:
            return None

        player = self.players[sid]

        if player.guessed:
            return None

        # Проверяем, доступна ли подсказка
        if player.hints_used >= self.hints_given:
            return None

        # Проверяем, что индекс валидный
        if letter_index < 0 or letter_index >= len(self.current_word):
            return None

        # Проверяем, что это не пробел
        if self.current_word[letter_index] == ' ':
            return None

        # Добавляем индекс в открытые буквы
        player.revealed_letters.add(letter_index)
        player.hints_used += 1

        return {
            'letter_index': letter_index,
            'letter': self.current_word[letter_index],
            'hints_used': player.hints_used
        }

    def get_hint_availability(self):
        """Получить информацию о доступности подсказок"""
        if self.hints_per_round == 0:
            return None

        elapsed = time.time() - self.round_start_time
        hint_interval = self.round_time / (self.hints_per_round + 1)

        # Сколько подсказок должно быть доступно сейчас
        available_hints = int(elapsed / hint_interval)
        available_hints = min(available_hints, self.hints_per_round)

        return {
            'total_hints': self.hints_per_round,
            'available_hints': available_hints,
            'next_hint_in': hint_interval - (elapsed % hint_interval) if available_hints < self.hints_per_round else 0
        }

class GameManager:
    def __init__(self):
        self.rooms = {}

    def create_room(self, room_id, settings=None):
        if room_id not in self.rooms:
            self.rooms[room_id] = GameRoom(room_id, settings)
        return self.rooms[room_id]

    def get_room(self, room_id):
        return self.rooms.get(room_id)

    def delete_room(self, room_id):
        if room_id in self.rooms:
            del self.rooms[room_id]

    def get_all_lobbies(self):
        """Получить список всех лобби"""
        lobbies = []
        for room in self.rooms.values():
            lobbies.append(room.get_lobby_info())
        return lobbies

game_manager = GameManager()
