from flask_socketio import emit, join_room, leave_room
from flask import request
from server.app import socketio
from server.game_logic import game_manager
from server.word_checker import check_guess
from shared.config import WORD_CHOICE_TIME, ROUND_TIME
from server.logger import log_info, log_debug, log_warning, log_error
import threading

@socketio.on('get_lobby_list')
def handle_get_lobby_list():
    """Отправить список всех лобби"""
    lobbies = game_manager.get_all_lobbies()
    emit('lobby_list', lobbies)

@socketio.on('create_lobby')
def handle_create_lobby(data):
    """Создать новое лобби с настройками"""
    room_id = data['room_id']
    settings = {
        'password': data.get('password'),
        'max_players': data.get('max_players', 8),
        'round_time': data.get('round_time', 60),
        'word_choice_time': data.get('word_choice_time', 15),
        'points_to_win': data.get('points_to_win', 1000),
        'themes': data.get('themes', ['general'])
    }

    log_info("Creating lobby with settings", room_id=room_id, settings=settings)
    room = game_manager.create_room(room_id, settings)
    emit('lobby_created', {'room_id': room_id})

@socketio.on('join_game')
def handle_join_game(data):
    room_id = data['room_id']
    player_name = data['player_name']
    password = data.get('password')
    create_lobby = data.get('create_lobby', False)
    lobby_settings = data.get('lobby_settings')
    sid = request.sid

    log_info("Player joining game", room_id=room_id, player_name=player_name, sid=sid, create_lobby=create_lobby)

    # Если нужно создать лобби
    if create_lobby and lobby_settings:
        room = game_manager.create_room(room_id, lobby_settings)
        log_info("Lobby created", room_id=room_id, settings=lobby_settings)
        # Создатель лобби автоматически проходит проверку пароля
    else:
        room = game_manager.get_room(room_id)
        if not room:
            room = game_manager.create_room(room_id)
            log_info("Auto-created room with default settings", room_id=room_id)
        else:
            # Проверка пароля только если комната уже существует и не создается сейчас
            if room.password and not room.verify_password(password):
                log_warning("Wrong password", room_id=room_id, player_name=player_name)
                emit('error', {'message': 'Неверный пароль'})
                return

    if not room.add_player(sid, player_name):
        log_warning("Room is full", room_id=room_id, player_name=player_name)
        emit('error', {'message': 'Комната полна'})
        return

    join_room(room_id)
    log_info("Player joined successfully", room_id=room_id, player_name=player_name)

    emit('player_joined', {
        'player_name': player_name,
        'scoreboard': room.get_scoreboard()
    }, room=room_id)

    if room.round_active:
        log_debug("Syncing active round state to new player", room_id=room_id, sid=sid)
        emit('sync_game_state', {
            'round_active': True,
            'drawer': room.current_drawer,
            'drawer_name': room.players[room.current_drawer].name,
            'word_hint': get_word_hint(room.current_word),
            'time_left': room.get_time_left(),
            'canvas_data': room.get_canvas_data(),
            'scoreboard': room.get_scoreboard()
        })
    elif room.choosing_word and room.current_drawer == sid:
        log_debug("Sending word choice to reconnected drawer", room_id=room_id, sid=sid)
        emit('choose_word', {
            'choices': room.word_choices
        })

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid

    log_debug("Player disconnecting", sid=sid)

    for room_id, room in list(game_manager.rooms.items()):
        if sid in room.players:
            player_name = room.players[sid].name
            room.remove_player(sid)

            log_info("Player left room", room_id=room_id, player_name=player_name, sid=sid)

            emit('player_left', {
                'player_name': player_name,
                'scoreboard': room.get_scoreboard()
            }, room=room_id)

            if len(room.players) == 0:
                log_info("Room is empty, deleting", room_id=room_id)
                game_manager.delete_room(room_id)

            break

@socketio.on('start_round')
def handle_start_round(data):
    room_id = data['room_id']
    room = game_manager.get_room(room_id)

    if not room or len(room.players) < 2:
        emit('error', {'message': 'Недостаточно игроков'})
        return

    if room.round_active or room.choosing_word:
        return

    word_choice_data = room.start_word_choice()

    if not word_choice_data:
        return

    emit('choose_word', {
        'choices': word_choice_data['choices']
    }, room=word_choice_data['drawer'])

    emit('waiting_for_word', {
        'drawer_name': word_choice_data['drawer_name']
    }, room=room_id, skip_sid=word_choice_data['drawer'])

    # Запускаем таймер для автовыбора слова
    socketio.start_background_task(force_word_choice_task, room_id, room.word_choice_time)

def force_word_choice(room_id):
    room = game_manager.get_room(room_id)

    # Проверяем, что комната существует и все еще в режиме выбора слова
    if not room:
        log_warning("force_word_choice: room not found", room_id=room_id)
        return

    if not room.choosing_word:
        log_debug("force_word_choice: player already chose word, skipping auto-choice", room_id=room_id)
        return

    import random
    word = random.choice(room.word_choices)
    room.choose_word(word)

    log_info("force_word_choice: auto-selected word", room_id=room_id, word=word)

    socketio.emit('round_start', {
        'drawer': room.current_drawer,
        'drawer_name': room.players[room.current_drawer].name,
        'word_hint': get_word_hint(room.current_word),
        'time_left': room.round_time
    }, to=room_id, namespace='/')

    socketio.emit('reveal_word', {
        'word': room.current_word
    }, to=room.current_drawer, namespace='/')

    # Запускаем таймер раунда
    socketio.start_background_task(end_round_timer_task, room_id, room.round_time)

@socketio.on('word_chosen')
def handle_word_chosen(data):
    room_id = data['room_id']
    word = data['word']
    sid = request.sid

    log_debug("Player choosing word", room_id=room_id, word=word, sid=sid)

    room = game_manager.get_room(room_id)

    if not room or room.current_drawer != sid:
        log_warning("Invalid word choice attempt", room_id=room_id, sid=sid, is_drawer=(room.current_drawer == sid if room else False))
        return

    # Проверяем, что игрок все еще выбирает слово
    if not room.choosing_word:
        log_warning("Player trying to choose word but choosing_word=False", room_id=room_id, sid=sid)
        return

    if not room.choose_word(word):
        log_error("Failed to choose word", room_id=room_id, word=word, sid=sid)
        return

    log_info("Player chose word, starting round", room_id=room_id, word=word, sid=sid)

    emit('round_start', {
        'drawer': room.current_drawer,
        'drawer_name': room.players[room.current_drawer].name,
        'word_hint': get_word_hint(room.current_word),
        'time_left': room.round_time
    }, room=room_id)

    emit('reveal_word', {
        'word': room.current_word
    }, room=sid)

    # Запускаем таймер как фоновую задачу
    socketio.start_background_task(end_round_timer_task, room_id, room.round_time)

@socketio.on('chat_message')
def handle_chat_message(data):
    room_id = data['room_id']
    message = data['message']
    sid = request.sid

    room = game_manager.get_room(room_id)

    if not room or sid not in room.players:
        return

    player = room.players[sid]

    if not room.round_active or sid == room.current_drawer or player.guessed:
        emit('chat_message', {
            'player_name': player.name,
            'message': message
        }, room=room_id)
        return

    result = check_guess(message, room.current_word)

    if result == "correct":
        guess_result = room.make_guess(sid, result)

        if guess_result:
            emit('player_guessed', {
                'player_name': player.name,
                'guesser_points': guess_result['guesser_points'],
                'drawer_points': guess_result['drawer_points'],
                'scoreboard': room.get_scoreboard()
            }, room=room_id)

            winner = room.check_winner()
            if winner:
                log_info("Game over - winner found", room_id=room_id, winner=winner.name, score=winner.score)
                emit('game_over', {
                    'winner_name': winner.name,
                    'scoreboard': room.get_scoreboard()
                }, room=room_id)
                room.end_round()
            elif guess_result['all_guessed']:
                log_info("All players guessed the word", room_id=room_id, word=room.current_word)
                emit('round_end', {
                    'word': room.current_word,
                    'reason': 'all_guessed',
                    'scoreboard': room.get_scoreboard()
                }, room=room_id)
                room.end_round()

                # Автоматически начать следующий раунд через 3 секунды
                log_debug("Starting timer for next round after all guessed", room_id=room_id)
                socketio.start_background_task(auto_start_next_round_task, room_id, 3)

    elif result == "close":
        emit('close_guess', {
            'message': 'Очень близко!'
        }, room=sid)

        emit('chat_message', {
            'player_name': player.name,
            'message': '***'
        }, room=room_id, skip_sid=sid)

    else:
        emit('chat_message', {
            'player_name': player.name,
            'message': message
        }, room=room_id)

@socketio.on('draw_action')
def handle_draw_action(data):
    room_id = data['room_id']
    action = data['action']
    sid = request.sid

    room = game_manager.get_room(room_id)

    if not room or room.current_drawer != sid:
        return

    room.add_canvas_action(action)

    emit('draw_action', {
        'action': action
    }, room=room_id, skip_sid=sid)

@socketio.on('canvas_snapshot')
def handle_canvas_snapshot(data):
    room_id = data['room_id']
    snapshot = data['snapshot']
    sid = request.sid

    room = game_manager.get_room(room_id)

    if not room or room.current_drawer != sid:
        return

    room.set_canvas_snapshot(snapshot)

    # Отправить снимок всем остальным игрокам
    emit('sync_canvas', {
        'snapshot': snapshot
    }, room=room_id, skip_sid=sid)

@socketio.on('request_canvas_sync')
def handle_request_canvas_sync(data):
    room_id = data['room_id']
    sid = request.sid

    room = game_manager.get_room(room_id)

    if not room:
        return

    snapshot = room.get_canvas_snapshot()
    if snapshot:
        emit('sync_canvas', {
            'snapshot': snapshot
        }, room=sid)

@socketio.on('clear_canvas')
def handle_clear_canvas(data):
    room_id = data['room_id']
    sid = request.sid

    room = game_manager.get_room(room_id)

    if not room or room.current_drawer != sid:
        return

    room.canvas_data = []

    emit('clear_canvas', {}, room=room_id)

def end_round_timer_task(room_id, delay):
    """Фоновая задача для таймера раунда"""
    # Отправляем обновления времени каждую секунду
    for remaining in range(delay, 0, -1):
        socketio.sleep(1)
        room = game_manager.get_room(room_id)

        # Проверяем, что раунд все еще активен
        if not room or not room.round_active:
            log_debug("end_round_timer_task: round already ended, stopping timer", room_id=room_id)
            return

        socketio.emit('time_update', {
            'time_left': remaining - 1
        }, to=room_id, namespace='/')

    # Финальная проверка перед завершением раунда
    room = game_manager.get_room(room_id)
    if room and room.round_active:
        end_round_timer(room_id)

def auto_start_next_round_task(room_id, delay):
    """Фоновая задача для автостарта следующего раунда"""
    socketio.sleep(delay)
    auto_start_next_round(room_id)

def force_word_choice_task(room_id, delay):
    """Фоновая задача для автовыбора слова"""
    log_debug("force_word_choice_task: waiting", room_id=room_id, delay=delay)
    socketio.sleep(delay)
    log_debug("force_word_choice_task: delay completed, calling force_word_choice", room_id=room_id)
    force_word_choice(room_id)

def end_round_timer(room_id):
    room = game_manager.get_room(room_id)

    if room and room.round_active:
        log_info("Round timer expired, ending round", room_id=room_id, word=room.current_word)
        socketio.emit('round_end', {
            'word': room.current_word,
            'reason': 'time_up',
            'scoreboard': room.get_scoreboard()
        }, to=room_id, namespace='/')

        room.end_round()

        # Автоматически начать следующий раунд через 3 секунды
        log_debug("Starting timer for next round auto-start", room_id=room_id)
        socketio.start_background_task(auto_start_next_round_task, room_id, 3)

def auto_start_next_round(room_id):
    room = game_manager.get_room(room_id)

    log_debug("auto_start_next_round called", room_id=room_id)

    if not room:
        log_warning("auto_start_next_round: room not found", room_id=room_id)
        return

    if len(room.players) < 2:
        log_warning("auto_start_next_round: not enough players", room_id=room_id, player_count=len(room.players))
        return

    if room.round_active or room.choosing_word:
        log_debug("auto_start_next_round: round already active or choosing word", room_id=room_id)
        return

    word_choice_data = room.start_word_choice()

    if not word_choice_data:
        log_error("auto_start_next_round: failed to start word choice", room_id=room_id)
        return

    drawer_sid = word_choice_data['drawer']

    # Проверяем, что игрок все еще в комнате
    if drawer_sid not in room.players:
        log_warning("auto_start_next_round: drawer disconnected, skipping", room_id=room_id, drawer_sid=drawer_sid)
        return

    log_info("Sending word choice to drawer", room_id=room_id, drawer_name=word_choice_data['drawer_name'], drawer_sid=drawer_sid)

    # Отправляем всем в комнате, клиент сам решит показывать ли модалку
    socketio.emit('choose_word', {
        'choices': word_choice_data['choices'],
        'drawer_sid': drawer_sid
    }, to=room_id, namespace='/')

    socketio.emit('waiting_for_word', {
        'drawer_name': word_choice_data['drawer_name']
    }, to=room_id, namespace='/')

    # Запускаем таймер для автовыбора слова
    socketio.start_background_task(force_word_choice_task, room_id, room.word_choice_time)

def get_word_hint(word):
    return '_' * len(word)
