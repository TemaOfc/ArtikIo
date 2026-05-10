from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import webbrowser
import threading

app = Flask(__name__,
            template_folder='../templates',
            static_folder='../static')
app.config['SECRET_KEY'] = 'artik-io-secret-key-2026'
socketio = SocketIO(app, cors_allowed_origins="*")

from server.socketio_events import *

def open_browser():
    webbrowser.open('http://127.0.0.1:5000')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/lobby_list')
def lobby_list():
    return render_template('lobby_list.html')

@app.route('/create_lobby')
def create_lobby():
    return render_template('create_lobby.html')

@app.route('/game/<room_id>')
def game(room_id):
    return render_template('game.html', room_id=room_id)

def run_server(host='127.0.0.1', port=5000, debug=False):
    if not debug:
        threading.Timer(1.5, open_browser).start()
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
