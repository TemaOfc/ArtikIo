from flask_socketio import emit, join_room, leave_room
from flask import request
from server.app import socketio
from server.game_logic import game_manager
from server.word_checker import check_guess
from shared.config import WORD_CHOICE_TIME, ROUND_TIME
import threading

@socketio.on('join_game')
def handle_join_game(data):
    room_id = data['room_id']
    player_name = data['player_name']
    sid = request.sid

    room = game_manager.create_room(room_id)

    if not room.add_player(sid, player_name):
        emit('error', {'message': 'Комната полна'})
        return

    join_room(room_id)

    emit('player_joined', {
        'player_name': player_name,
        'scoreboard': room.get_scoreboard()
    }, room=room_id)

    if room.round_active:
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
        emit('choose_word', {
            'choices': room.word_choices
        })

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid

    for room_id, room in list(game_manager.rooms.items()):
        if sid in room.players:
            player_name = room.players[sid].name
            room.remove_player(sid)

            emit('player_left', {
                'player_name': player_name,
                'scoreboard': room.get_scoreboard()
            }, room=room_id)

            if len(room.players) == 0:
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
    socketio.start_background_task(force_word_choice_task, room_id, WORD_CHOICE_TIME)

def force_word_choice(room_id):
    room = game_manager.get_room(room_id)

    # Проверяем, что комната существует и все еще в режиме выбора слова
    if not room:
        print(f"[DEBUG] force_word_choice: комната {room_id} не найдена")
        return

    if not room.choosing_word:
        print(f"[DEBUG] force_word_choice: игрок уже выбрал слово, пропускаем автовыбор")
        return

    import random
    word = random.choice(room.word_choices)
    room.choose_word(word)

    print(f"[DEBUG] force_word_choice: автоматически выбрано слово '{word}' для комнаты {room_id}")

    socketio.emit('round_start', {
        'drawer': room.current_drawer,
        'drawer_name': room.players[room.current_drawer].name,
        'word_hint': get_word_hint(room.current_word),
        'time_left': ROUND_TIME
    }, to=room_id, namespace='/')

    socketio.emit('reveal_word', {
        'word': room.current_word
    }, to=room.current_drawer, namespace='/')

    # Запускаем таймер раунда
    socketio.start_background_task(end_round_timer_task, room_id, ROUND_TIME)

@socketio.on('word_chosen')
def handle_word_chosen(data):
    room_id = data['room_id']
    word = data['word']
    sid = request.sid

    room = game_manager.get_room(room_id)

    if not room or room.current_drawer != sid:
        return

    # Проверяем, что игрок все еще выбирает слово
    if not room.choosing_word:
        print(f"[DEBUG] Игрок пытается выбрать слово, но choosing_word=False")
        return

    if not room.choose_word(word):
        return

    print(f"[DEBUG] Игрок выбрал слово '{word}', начинаем раунд в комнате {room_id}")

    emit('round_start', {
        'drawer': room.current_drawer,
        'drawer_name': room.players[room.current_drawer].name,
        'word_hint': get_word_hint(room.current_word),
        'time_left': ROUND_TIME
    }, room=room_id)

    emit('reveal_word', {
        'word': room.current_word
    }, room=sid)

    # Запускаем таймер как фоновую задачу
    socketio.start_background_task(end_round_timer_task, room_id, ROUND_TIME)

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
                emit('game_over', {
                    'winner_name': winner.name,
                    'scoreboard': room.get_scoreboard()
                }, room=room_id)
                room.end_round()
            elif guess_result['all_guessed']:
                print(f"[DEBUG] Все игроки угадали слово в комнате {room_id}")
                emit('round_end', {
                    'word': room.current_word,
                    'reason': 'all_guessed',
                    'scoreboard': room.get_scoreboard()
                }, room=room_id)
                room.end_round()

                # Автоматически начать следующий раунд через 3 секунды
                print(f"[DEBUG] Запускаем таймер для автостарта после угадывания всеми")
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
            print(f"[DEBUG] end_round_timer_task: раунд уже завершен, останавливаем таймер")
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
    print(f"[DEBUG] force_word_choice_task: ждем {delay} секунд для комнаты {room_id}")
    socketio.sleep(delay)
    print(f"[DEBUG] force_word_choice_task: задержка завершена, вызываем force_word_choice")
    force_word_choice(room_id)

def end_round_timer(room_id):
    room = game_manager.get_room(room_id)

    if room and room.round_active:
        print(f"[DEBUG] Таймер истек для комнаты {room_id}, завершаем раунд")
        socketio.emit('round_end', {
            'word': room.current_word,
            'reason': 'time_up',
            'scoreboard': room.get_scoreboard()
        }, to=room_id, namespace='/')

        room.end_round()

        # Автоматически начать следующий раунд через 3 секунды
        print(f"[DEBUG] Запускаем таймер для автостарта следующего раунда")
        socketio.start_background_task(auto_start_next_round_task, room_id, 3)

def auto_start_next_round(room_id):
    room = game_manager.get_room(room_id)

    print(f"[DEBUG] auto_start_next_round вызван для комнаты {room_id}")

    if not room:
        print(f"[DEBUG] Комната {room_id} не найдена")
        return

    if len(room.players) < 2:
        print(f"[DEBUG] Недостаточно игроков в комнате {room_id}")
        return

    if room.round_active or room.choosing_word:
        print(f"[DEBUG] Раунд уже активен или идет выбор слова")
        return

    word_choice_data = room.start_word_choice()

    if not word_choice_data:
        print(f"[DEBUG] Не удалось начать выбор слова")
        return

    drawer_sid = word_choice_data['drawer']

    # Проверяем, что игрок все еще в комнате
    if drawer_sid not in room.players:
        print(f"[DEBUG] Рисующий игрок отключился, пропускаем")
        return

    print(f"[DEBUG] Отправляем выбор слова игроку {word_choice_data['drawer_name']} (sid: {drawer_sid})")

    # Отправляем всем в комнате, клиент сам решит показывать ли модалку
    socketio.emit('choose_word', {
        'choices': word_choice_data['choices'],
        'drawer_sid': drawer_sid
    }, to=room_id, namespace='/')

    socketio.emit('waiting_for_word', {
        'drawer_name': word_choice_data['drawer_name']
    }, to=room_id, namespace='/')

    # Запускаем таймер для автовыбора слова
    socketio.start_background_task(force_word_choice_task, room_id, WORD_CHOICE_TIME)

def get_word_hint(word):
    return '_' * len(word)
