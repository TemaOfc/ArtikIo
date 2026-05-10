class GameSocket {
    constructor(roomId, playerName, createLobby, lobbySettings) {
        this.socket = io();
        this.roomId = roomId;
        this.playerName = playerName;
        this.createLobby = createLobby;
        this.lobbySettings = lobbySettings;
        this.setupSocketListeners();
    }

    setupSocketListeners() {
        this.socket.on('connect', () => {
            console.log('Connected to server');

            const urlParams = new URLSearchParams(window.location.search);
            let password = urlParams.get('password');

            // Если создаем лобби и есть настройки с паролем, используем его
            if (this.createLobby && this.lobbySettings && this.lobbySettings.password) {
                password = this.lobbySettings.password;
            }

            this.socket.emit('join_game', {
                room_id: this.roomId,
                player_name: this.playerName,
                password: password,
                create_lobby: this.createLobby,
                lobby_settings: this.lobbySettings
            });

            // Запросить синхронизацию холста через 500мс после подключения
            setTimeout(() => {
                this.requestCanvasSync();
            }, 500);
        });

        this.socket.on('player_joined', (data) => {
            if (window.chatManager) {
                window.chatManager.addSystemMessage(`${data.player_name} присоединился к игре`);
            }
            if (window.updateScoreboard) {
                window.updateScoreboard(data.scoreboard);
            }

            if (window.innerWidth <= 768) {
                showToast(`${data.player_name} присоединился`, 'info', 1500);
            }
        });

        this.socket.on('player_left', (data) => {
            if (window.chatManager) {
                window.chatManager.addSystemMessage(`${data.player_name} покинул игру`);
            }
            if (window.updateScoreboard) {
                window.updateScoreboard(data.scoreboard);
            }
        });

        this.socket.on('choose_word', (data) => {
            console.log('[DEBUG] choose_word received:', data);
            console.log('[DEBUG] my socket.id:', this.socket.id);
            console.log('[DEBUG] drawer_sid:', data.drawer_sid);

            // Проверяем, является ли текущий игрок рисующим
            if (data.drawer_sid) {
                // Если передан drawer_sid, показываем модалку только ему
                // Сравниваем через socket.id
                if (this.socket.id === data.drawer_sid) {
                    console.log('[DEBUG] Showing word choice to drawer');
                    window.showWordChoice(data.choices, data.weights);
                } else {
                    console.log('[DEBUG] Not showing word choice - not the drawer');
                }
            } else {
                // Старый формат - показываем всем (для совместимости)
                console.log('[DEBUG] Showing word choice (old format)');
                window.showWordChoice(data.choices, data.weights);
            }
        });

        this.socket.on('waiting_for_word', (data) => {
            window.chatManager.addSystemMessage(`${data.drawer_name} выбирает слово...`);
        });

        this.socket.on('round_start', (data) => {
            window.startRound(data);
        });

        this.socket.on('reveal_word', (data) => {
            window.revealWord(data.word, data.weight);
        });

        this.socket.on('chat_message', (data) => {
            if (window.chatManager) {
                window.chatManager.addMessage(data.player_name, data.message);
            }
        });

        this.socket.on('close_guess', (data) => {
            if (window.chatManager) {
                window.chatManager.addMessage('', data.message, 'close');
            }
        });

        this.socket.on('player_guessed', (data) => {
            if (window.chatManager) {
                window.chatManager.addMessage(data.player_name, '', 'correct');
            }
            if (window.updateScoreboard) {
                window.updateScoreboard(data.scoreboard);
            }

            const hintsText = data.hints_used > 0 ? ` (использовано подсказок: ${data.hints_used})` : '';

            if (window.innerWidth <= 768) {
                showToast(`${data.player_name} угадал! +${data.guesser_points} очков${hintsText}`, 'success', 2000);
            } else {
                // Для десктопа показываем сложность в чате
                if (window.chatManager) {
                    window.chatManager.addSystemMessage(`${data.player_name} угадал слово! +${data.guesser_points} очков (сложность: ${data.word_weight})${hintsText}`);
                }
            }
        });

        this.socket.on('partial_guess', (data) => {
            // Обновляем подсказку с отгаданной частью
            if (typeof renderWordLetters === 'function') {
                renderWordLetters(data.word_hint, true);
            }

            if (window.innerWidth <= 768) {
                showToast(`${data.player_name} угадал часть слова!`, 'info', 1500);
            } else {
                if (window.chatManager) {
                    window.chatManager.addSystemMessage(`${data.player_name} угадал часть слова!`);
                }
            }
        });

        this.socket.on('round_end', (data) => {
            window.endRound(data);
        });

        this.socket.on('game_over', (data) => {
            window.showGameOver(data);
        });

        this.socket.on('draw_action', (data) => {
            if (window.drawingCanvas) {
                window.drawingCanvas.applyAction(data.action);
            }
        });

        this.socket.on('sync_canvas', (data) => {
            if (window.drawingCanvas) {
                window.drawingCanvas.loadSnapshot(data.snapshot);
            }
        });

        this.socket.on('clear_canvas', () => {
            if (window.drawingCanvas) {
                window.drawingCanvas.clearCanvas();
            }
        });

        this.socket.on('sync_game_state', (data) => {
            if (window.syncGameState) {
                window.syncGameState(data);
            }
        });

        this.socket.on('hint_available', (data) => {
            if (window.showHintAvailable) {
                window.showHintAvailable(data);
            }
        });

        this.socket.on('letter_revealed', (data) => {
            if (window.revealLetterAtIndex) {
                window.revealLetterAtIndex(data);
            }
        });

        this.socket.on('time_update', (data) => {
            // Обновляем таймер с сервера
            const timerElement = document.getElementById('timer');
            if (timerElement) {
                timerElement.textContent = data.time_left;
                if (data.time_left <= 10) {
                    timerElement.classList.add('warning');
                } else {
                    timerElement.classList.remove('warning');
                }
            }
        });

        this.socket.on('error', (data) => {
            alert(data.message);
            // Перенаправляем обратно к списку лобби при ошибке
            window.location.href = '/lobby_list';
        });
    }

    sendChatMessage(message) {
        this.socket.emit('chat_message', {
            room_id: this.roomId,
            message: message
        });
    }

    startRound() {
        this.socket.emit('start_round', {
            room_id: this.roomId
        });
    }

    chooseWord(word) {
        this.socket.emit('word_chosen', {
            room_id: this.roomId,
            word: word
        });
    }

    emitDrawAction(action) {
        this.socket.emit('draw_action', {
            room_id: this.roomId,
            action: action
        });
    }

    sendCanvasSnapshot(snapshot) {
        this.socket.emit('canvas_snapshot', {
            room_id: this.roomId,
            snapshot: snapshot
        });
    }

    requestCanvasSync() {
        this.socket.emit('request_canvas_sync', {
            room_id: this.roomId
        });
    }

    clearCanvas() {
        this.socket.emit('clear_canvas', {
            room_id: this.roomId
        });
    }
}

let drawingCanvas;
let chatManager;
let gameSocket;
let timerInterval;
let choiceTimerInterval;

// Отслеживание клавиатуры на мобильных устройствах с visualViewport API
let initialViewportHeight = window.innerHeight;

function handleViewportResize() {
    // Используем visualViewport API если доступен
    const visualViewport = window.visualViewport;

    if (visualViewport) {
        const currentHeight = visualViewport.height;
        const heightDiff = initialViewportHeight - currentHeight;

        console.log('[VIEWPORT] Initial height:', initialViewportHeight);
        console.log('[VIEWPORT] Visual viewport height:', currentHeight);
        console.log('[VIEWPORT] Height diff:', heightDiff);
        console.log('[VIEWPORT] Window width:', window.innerWidth);
        console.log('[VIEWPORT] Visual viewport scale:', visualViewport.scale);

        // Если высота уменьшилась более чем на 150px, считаем что клавиатура открыта
        if (heightDiff > 150 && window.innerWidth <= 768) {
            console.log('[VIEWPORT] Keyboard OPEN - adding class');
            document.body.classList.add('keyboard-open');

            // Устанавливаем CSS переменную с высотой viewport
            document.documentElement.style.setProperty('--viewport-height', `${currentHeight}px`);
        } else {
            console.log('[VIEWPORT] Keyboard CLOSED - removing class');
            document.body.classList.remove('keyboard-open');
            document.documentElement.style.setProperty('--viewport-height', `${initialViewportHeight}px`);
        }
    } else {
        // Fallback для старых браузеров
        const currentHeight = window.innerHeight;
        const heightDiff = initialViewportHeight - currentHeight;

        console.log('[VIEWPORT] Fallback - Initial height:', initialViewportHeight);
        console.log('[VIEWPORT] Fallback - Current height:', currentHeight);
        console.log('[VIEWPORT] Fallback - Height diff:', heightDiff);

        if (heightDiff > 150 && window.innerWidth <= 768) {
            document.body.classList.add('keyboard-open');
            document.documentElement.style.setProperty('--viewport-height', `${currentHeight}px`);
        } else {
            document.body.classList.remove('keyboard-open');
            document.documentElement.style.setProperty('--viewport-height', `${initialViewportHeight}px`);
        }
    }
}

// Слушаем изменения visualViewport
if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', handleViewportResize);
    window.visualViewport.addEventListener('scroll', handleViewportResize);
}

window.addEventListener('resize', handleViewportResize);
window.addEventListener('orientationchange', () => {
    console.log('[VIEWPORT] Orientation changed');
    setTimeout(() => {
        initialViewportHeight = window.innerHeight;
        handleViewportResize();
    }, 100);
});

// Логируем при фокусе на input
document.addEventListener('DOMContentLoaded', () => {
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.addEventListener('focus', () => {
            console.log('[INPUT] Chat input focused');
            setTimeout(() => {
                console.log('[INPUT] After focus - viewport height:', window.innerHeight);
                if (window.visualViewport) {
                    console.log('[INPUT] After focus - visual viewport height:', window.visualViewport.height);
                }
                handleViewportResize();
            }, 300);
        });
        chatInput.addEventListener('blur', () => {
            console.log('[INPUT] Chat input blurred');
            setTimeout(() => {
                console.log('[INPUT] After blur - viewport height:', window.innerHeight);
                if (window.visualViewport) {
                    console.log('[INPUT] After blur - visual viewport height:', window.visualViewport.height);
                }
                handleViewportResize();
            }, 300);
        });
    }
});

function showToast(message, type = 'info', duration = 2000) {
    const toast = document.getElementById('toastNotification');
    toast.textContent = message;
    toast.className = `toast-notification ${type}`;

    setTimeout(() => toast.classList.add('show'), 10);

    setTimeout(() => {
        toast.classList.remove('show');
    }, duration);
}

function init() {
    const urlParams = new URLSearchParams(window.location.search);
    const playerName = urlParams.get('name');
    const roomId = window.location.pathname.split('/').pop();
    const createLobby = urlParams.get('create') === 'true';

    if (!playerName) {
        window.location.href = '/';
        return;
    }

    document.getElementById('roomId').textContent = roomId;

    // Получаем настройки лобби из localStorage если создаем новое
    let lobbySettings = null;
    if (createLobby) {
        const savedSettings = localStorage.getItem('lobbySettings');
        if (savedSettings) {
            lobbySettings = JSON.parse(savedSettings);
            localStorage.removeItem('lobbySettings'); // Удаляем после использования
        }
    }

    drawingCanvas = new DrawingCanvas('gameCanvas');
    chatManager = new ChatManager('chatMessages', 'chatInput', 'sendBtn');
    gameSocket = new GameSocket(roomId, playerName, createLobby, lobbySettings);

    // Инициализируем пустой контейнер для букв
    const wordLettersContainer = document.getElementById('wordLetters');
    if (wordLettersContainer) {
        wordLettersContainer.innerHTML = '';
    }

    window.drawingCanvas = drawingCanvas;
    window.chatManager = chatManager;
    window.gameSocket = gameSocket;

    setupToolbar();
    setupGameControls();

    // Скрываем панель инструментов при загрузке
    document.getElementById('toolbar').classList.add('hidden');
}

function setupToolbar() {
    const toolButtons = document.querySelectorAll('.tool-btn[data-tool]');
    toolButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            toolButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            drawingCanvas.setTool(btn.dataset.tool);
        });
    });

    const colorSwatches = document.querySelectorAll('.color-swatch');
    colorSwatches.forEach(swatch => {
        swatch.addEventListener('click', () => {
            colorSwatches.forEach(s => s.classList.remove('active'));
            swatch.classList.add('active');
            drawingCanvas.setColor(swatch.dataset.color);
            document.getElementById('colorPicker').value = swatch.dataset.color;
        });
    });

    const colorPicker = document.getElementById('colorPicker');
    colorPicker.addEventListener('change', (e) => {
        colorSwatches.forEach(s => s.classList.remove('active'));
        drawingCanvas.setColor(e.target.value);
    });

    const brushSize = document.getElementById('brushSize');
    const sizeValue = document.getElementById('sizeValue');
    brushSize.addEventListener('input', (e) => {
        const size = e.target.value;
        sizeValue.textContent = size;
        drawingCanvas.setBrushSize(parseInt(size));
    });

    document.getElementById('clearBtn').addEventListener('click', () => {
        if (confirm('Очистить холст?')) {
            drawingCanvas.clearCanvas();
            gameSocket.clearCanvas();
        }
    });

    document.getElementById('undoBtn').addEventListener('click', () => {
        drawingCanvas.undo();
    });
}

function setupGameControls() {
    const startRoundBtn = document.getElementById('startRoundBtn');
    startRoundBtn.addEventListener('click', () => {
        gameSocket.startRound();
        startRoundBtn.disabled = true;
    });

    document.getElementById('newGameBtn').addEventListener('click', () => {
        window.location.reload();
    });
}

function updateScoreboard(scoreboard) {
    const scoreboardList = document.getElementById('scoreboardList');
    scoreboardList.innerHTML = '';

    scoreboard.forEach(player => {
        const playerDiv = document.createElement('div');
        playerDiv.className = 'player-item';

        if (player.guessed) {
            playerDiv.classList.add('guessed');
        }

        playerDiv.innerHTML = `
            <span class="player-name">${player.name}</span>
            <span class="player-score">${player.score}</span>
        `;

        scoreboardList.appendChild(playerDiv);
    });
}

function showWordChoice(choices, weights) {
    const modal = document.getElementById('wordChoiceModal');
    const choicesContainer = document.getElementById('wordChoices');
    choicesContainer.innerHTML = '';

    choices.forEach((word, index) => {
        const btn = document.createElement('button');
        btn.className = 'word-choice-btn';

        const weight = weights ? weights[index] : 3;
        const difficultyText = getDifficultyText(weight);

        btn.innerHTML = `
            <span class="word-text">${word}</span>
            <span class="word-difficulty" style="color: ${getDifficultyColor(weight)}">★${weight} ${difficultyText}</span>
        `;

        btn.addEventListener('click', () => {
            gameSocket.chooseWord(word);
            modal.classList.remove('active');
            clearInterval(choiceTimerInterval);
        });
        choicesContainer.appendChild(btn);
    });

    modal.classList.add('active');

    let timeLeft = 15;
    document.getElementById('choiceTimer').textContent = timeLeft;

    choiceTimerInterval = setInterval(() => {
        timeLeft--;
        document.getElementById('choiceTimer').textContent = timeLeft;
        if (timeLeft <= 0) {
            clearInterval(choiceTimerInterval);
        }
    }, 1000);
}

function getDifficultyText(weight) {
    if (weight <= 2) return 'легко';
    if (weight === 3) return 'средне';
    return 'сложно';
}

function getDifficultyColor(weight) {
    if (weight <= 2) return '#4CAF50';
    if (weight === 3) return '#FFC107';
    return '#F44336';
}

function startRound(data) {
    document.getElementById('wordChoiceModal').classList.remove('active');
    clearInterval(choiceTimerInterval);

    drawingCanvas.clearCanvas();

    // Проверяем, является ли текущий игрок рисующим
    const isDrawer = (data.drawer === gameSocket.socket.id);

    if (isDrawer) {
        drawingCanvas.setEnabled(true);
        document.getElementById('toolbar').classList.remove('hidden');
    } else {
        drawingCanvas.setEnabled(false);
        document.getElementById('toolbar').classList.add('hidden');
    }

    document.getElementById('currentDrawer').textContent = `Рисует: ${data.drawer_name}`;

    // Создаем кнопки для букв
    renderWordLetters(data.word_hint, !isDrawer);

    document.getElementById('startRoundBtn').style.display = 'none';

    startTimer(data.time_left);
}

function renderWordLetters(word, clickable) {
    const wordLettersContainer = document.getElementById('wordLetters');
    wordLettersContainer.innerHTML = '';

    for (let i = 0; i < word.length; i++) {
        const char = word[i];
        const btn = document.createElement('button');
        btn.className = 'letter-btn';

        if (char === ' ') {
            btn.className += ' space';
            btn.textContent = ' ';
            btn.disabled = true;
        } else if (char === '_') {
            btn.className += ' hidden';
            btn.textContent = '_';
            btn.dataset.index = i;

            if (clickable) {
                btn.onclick = () => handleLetterClick(i);
            } else {
                btn.disabled = true;
            }
        } else {
            btn.textContent = char;
            btn.disabled = true;
        }

        wordLettersContainer.appendChild(btn);
    }

    // Обновляем размер шрифта
    updateWordHintSize(word);
}

function handleLetterClick(index) {
    if (!gameSocket || !gameSocket.socket) {
        console.error('GameSocket not initialized');
        return;
    }
    gameSocket.socket.emit('reveal_letter', {
        room_id: gameSocket.roomId,
        letter_index: index
    });
}

function revealWord(word, weight) {
    renderWordLetters(word, false);
    drawingCanvas.setEnabled(true);

    const toolbar = document.getElementById('toolbar');
    toolbar.classList.remove('hidden');
    toolbar.querySelectorAll('button, input').forEach(el => el.disabled = false);

    const difficultyText = getDifficultyText(weight || 3);
    chatManager.addSystemMessage(`Ваше слово: ${word} (сложность: ${weight || 3} - ${difficultyText})`);
}

function startTimer(seconds) {
    clearInterval(timerInterval);

    let timeLeft = seconds;
    const timerElement = document.getElementById('timer');
    timerElement.textContent = timeLeft;
    timerElement.classList.remove('warning');

    timerInterval = setInterval(() => {
        timeLeft--;
        timerElement.textContent = timeLeft;

        if (timeLeft <= 10) {
            timerElement.classList.add('warning');
        }

        if (timeLeft <= 0) {
            clearInterval(timerInterval);
        }
    }, 1000);
}

function endRound(data) {
    clearInterval(timerInterval);

    drawingCanvas.setEnabled(false);

    const toolbar = document.getElementById('toolbar');
    toolbar.classList.add('hidden');
    toolbar.querySelectorAll('button, input').forEach(el => el.disabled = true);

    const weight = data.word_weight || 3;
    const difficultyText = getDifficultyText(weight);

    if (data.reason === 'time_up') {
        chatManager.addSystemMessage(`Время вышло! Слово было: ${data.word} (сложность: ${weight} - ${difficultyText})`);
        if (window.innerWidth <= 768) {
            showToast(`Время вышло! Слово: ${data.word} (★${weight})`, 'info', 3000);
        }
    } else if (data.reason === 'all_guessed') {
        chatManager.addSystemMessage(`Все угадали! Слово было: ${data.word} (сложность: ${weight} - ${difficultyText})`);
        if (window.innerWidth <= 768) {
            showToast(`Все угадали! Слово: ${data.word} (★${weight})`, 'success', 3000);
        }
    }

    renderWordLetters(data.word, false);
    document.getElementById('currentDrawer').textContent = '';

    updateScoreboard(data.scoreboard);

    // Не показываем кнопку - раунд начнется автоматически
    document.getElementById('startRoundBtn').style.display = 'none';
}

function showGameOver(data) {
    clearInterval(timerInterval);

    const modal = document.getElementById('gameOverModal');
    document.getElementById('winnerName').textContent = data.winner_name;

    const finalScoreboard = document.getElementById('finalScoreboard');
    finalScoreboard.innerHTML = '<h3>Финальные результаты:</h3>';

    data.scoreboard.forEach((player, index) => {
        const playerDiv = document.createElement('div');
        playerDiv.className = 'player-item';
        playerDiv.innerHTML = `
            <span>${index + 1}. ${player.name}</span>
            <span class="player-score">${player.score}</span>
        `;
        finalScoreboard.appendChild(playerDiv);
    });

    modal.classList.add('active');
}

function syncGameState(data) {
    if (data.round_active) {
        document.getElementById('currentDrawer').textContent = `Рисует: ${data.drawer_name}`;

        // Проверяем, является ли текущий игрок рисующим
        const isDrawer = (data.drawer === gameSocket.socket.id);

        renderWordLetters(data.word_hint, !isDrawer);
        document.getElementById('startRoundBtn').style.display = 'none';

        drawingCanvas.clearCanvas();
        data.canvas_data.forEach(action => {
            drawingCanvas.applyAction(action);
        });

        if (isDrawer) {
            drawingCanvas.setEnabled(true);
            document.getElementById('toolbar').classList.remove('hidden');
        } else {
            drawingCanvas.setEnabled(false);
            document.getElementById('toolbar').classList.add('hidden');
        }

        startTimer(data.time_left);
        updateScoreboard(data.scoreboard);
    } else {
        // Раунд не активен - скрываем панель инструментов
        document.getElementById('toolbar').classList.add('hidden');
    }
}

function updateWordHintSize(text) {
    const wordLettersContainer = document.getElementById('wordLetters');
    if (!wordLettersContainer) return;

    const length = text.length;
    let fontSize;

    // Масштабируем размер шрифта в зависимости от длины
    if (length <= 10) {
        fontSize = '48px';
    } else if (length <= 20) {
        fontSize = '36px';
    } else if (length <= 30) {
        fontSize = '28px';
    } else if (length <= 40) {
        fontSize = '24px';
    } else if (length <= 50) {
        fontSize = '20px';
    } else {
        fontSize = '16px';
    }

    wordLettersContainer.style.fontSize = fontSize;
}

function showHintAvailable(data) {
    if (window.innerWidth <= 768) {
        showToast(`Доступна подсказка ${data.hint_number}/${data.total_hints}! Нажмите на букву чтобы открыть`, 'info', 3000);
    } else {
        window.chatManager.addSystemMessage(`Доступна подсказка ${data.hint_number}/${data.total_hints}! Нажмите на букву в слове чтобы открыть её`);
    }
}

function revealLetterAtIndex(data) {
    // Находим кнопку с нужным индексом и заменяем её содержимое
    const buttons = document.querySelectorAll('.letter-btn');
    buttons.forEach(btn => {
        if (btn.dataset.index == data.letter_index) {
            btn.textContent = data.letter;
            btn.classList.remove('hidden');
            btn.disabled = true;
            btn.onclick = null;
        }
    });

    if (window.innerWidth <= 768) {
        showToast(`Буква открыта! Использовано подсказок: ${data.hints_used}`, 'success', 2000);
    } else {
        window.chatManager.addSystemMessage(`Вы открыли букву "${data.letter}". Использовано подсказок: ${data.hints_used}`);
    }
}

window.updateScoreboard = updateScoreboard;
window.showWordChoice = showWordChoice;
window.startRound = startRound;
window.revealWord = revealWord;
window.endRound = endRound;
window.showGameOver = showGameOver;
window.syncGameState = syncGameState;
window.showHintAvailable = showHintAvailable;
window.revealLetterAtIndex = revealLetterAtIndex;

document.addEventListener('DOMContentLoaded', init);
