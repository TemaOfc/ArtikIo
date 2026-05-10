# -*- coding: utf-8 -*-
import sys
import time
from flask import Flask
from flask_socketio import SocketIO, emit
from server.app import app, socketio
from server.game_logic import game_manager

def test_emit_to_room():
    print("\n=== Test 1: Emit to room ===")

    with app.app_context():
        room_id = "test_room_1"
        room = game_manager.create_room(room_id)

        room.add_player("player1_sid", "Player1")
        room.add_player("player2_sid", "Player2")

        print(f"Players in room: {[p.name for p in room.players.values()]}")

        try:
            socketio.emit('test_event', {'message': 'test'}, to=room_id, namespace='/')
            print("[OK] Event sent to room successfully")
        except Exception as e:
            print(f"[FAIL] Error sending to room: {e}")

        try:
            socketio.emit('test_event', {'message': 'test'}, to="player1_sid", namespace='/')
            print("[OK] Event sent to player successfully")
        except Exception as e:
            print(f"[FAIL] Error sending to player: {e}")

def test_word_choice_flow():
    print("\n=== Test 2: Word choice flow ===")

    with app.app_context():
        room_id = "test_room_2"
        room = game_manager.create_room(room_id)

        room.add_player("player1_sid", "Player1")
        room.add_player("player2_sid", "Player2")

        print(f"Initial current_drawer: {room.current_drawer}")

        word_choice_data = room.start_word_choice()

        if word_choice_data:
            print(f"[OK] Word choice started")
            print(f"  Drawer: {word_choice_data['drawer_name']}")
            print(f"  SID: {word_choice_data['drawer']}")
            print(f"  Words: {word_choice_data['choices']}")
            print(f"  choosing_word: {room.choosing_word}")

            word = word_choice_data['choices'][0]
            success = room.choose_word(word)

            if success:
                print(f"[OK] Word '{word}' chosen")
                print(f"  round_active: {room.round_active}")
                print(f"  current_word: {room.current_word}")
            else:
                print(f"[FAIL] Failed to choose word")
        else:
            print("[FAIL] Failed to start word choice")

def test_next_drawer_logic():
    print("\n=== Test 3: Next drawer logic ===")

    with app.app_context():
        room_id = "test_room_3"
        room = game_manager.create_room(room_id)

        room.add_player("player1_sid", "Player1")
        room.add_player("player2_sid", "Player2")
        room.add_player("player3_sid", "Player3")

        player_names = [room.players[sid].name for sid in room.players.keys()]
        print(f"Players: {player_names}")

        sequence = []
        for i in range(6):
            word_choice_data = room.start_word_choice()
            if word_choice_data:
                drawer_name = word_choice_data['drawer_name']
                sequence.append(drawer_name)
                print(f"  Round {i+1}: {drawer_name}")

                room.choose_word(word_choice_data['choices'][0])
                room.end_round()
            else:
                print(f"[FAIL] Failed to start round {i+1}")
                break

        if len(sequence) == 6:
            if sequence[0] == sequence[3] and sequence[1] == sequence[4] and sequence[2] == sequence[5]:
                print("[OK] Sequence is cyclic")
            else:
                print(f"[FAIL] Sequence is not cyclic: {sequence}")
        else:
            print(f"[FAIL] Not all rounds completed")

def test_emit_with_namespace():
    print("\n=== Test 4: Emit with different parameters ===")

    with app.app_context():
        test_cases = [
            ("to='room_id', namespace='/'", {'to': 'test_room', 'namespace': '/'}),
            ("room='room_id', namespace='/'", {'room': 'test_room', 'namespace': '/'}),
            ("to='sid', namespace='/'", {'to': 'test_sid', 'namespace': '/'}),
            ("room='sid', namespace='/'", {'room': 'test_sid', 'namespace': '/'}),
        ]

        for desc, kwargs in test_cases:
            try:
                socketio.emit('test_event', {'data': 'test'}, **kwargs)
                print(f"[OK] {desc} - success")
            except Exception as e:
                print(f"[FAIL] {desc} - error: {e}")

if __name__ == '__main__':
    print("Running SocketIO tests...")
    print("=" * 50)

    test_emit_to_room()
    test_word_choice_flow()
    test_next_drawer_logic()
    test_emit_with_namespace()

    print("\n" + "=" * 50)
    print("Tests completed")
