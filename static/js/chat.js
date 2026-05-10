class ChatManager {
    constructor(messagesId, inputId, sendBtnId) {
        this.messagesContainer = document.getElementById(messagesId);
        this.input = document.getElementById(inputId);
        this.sendBtn = document.getElementById(sendBtnId);

        this.setupEventListeners();
    }

    setupEventListeners() {
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendMessage();
            }
        });

        // Предотвращаем скроллинг к полю ввода на мобильных устройствах
        if (window.innerWidth <= 768) {
            this.input.addEventListener('focus', (e) => {
                e.preventDefault();
                window.scrollTo(0, 0);
                document.body.scrollTop = 0;
            });

            this.input.addEventListener('blur', () => {
                window.scrollTo(0, 0);
                document.body.scrollTop = 0;
            });
        }
    }

    sendMessage() {
        const message = this.input.value.trim();
        if (!message) return;

        if (window.gameSocket) {
            window.gameSocket.sendChatMessage(message);
        }

        this.input.value = '';
    }

    addMessage(playerName, message, type = 'normal') {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${type}`;

        if (type === 'system') {
            messageDiv.textContent = message;
        } else if (type === 'correct') {
            messageDiv.innerHTML = `<strong>${playerName}</strong> угадал слово!`;
        } else if (type === 'close') {
            messageDiv.textContent = message;
        } else {
            messageDiv.innerHTML = `<strong>${playerName}:</strong> ${this.escapeHtml(message)}`;
        }

        this.messagesContainer.appendChild(messageDiv);
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    addSystemMessage(message) {
        this.addMessage('', message, 'system');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    clear() {
        this.messagesContainer.innerHTML = '';
    }
}
