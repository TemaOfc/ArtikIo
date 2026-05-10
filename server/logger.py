import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Создаем директорию для логов
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# Создаем уникальное имя файла для каждой сессии
session_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_filename = os.path.join(LOGS_DIR, f'game_session_{session_timestamp}.log')

# Настраиваем логгер
logger = logging.getLogger('ArtikIo')
logger.setLevel(logging.DEBUG)

# Форматтер для логов
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Обработчик для файла (с ротацией, максимум 10MB на файл)
file_handler = RotatingFileHandler(
    log_filename,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# Обработчик для консоли
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Добавляем обработчики
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Функции для удобного логирования
def log_info(message, **kwargs):
    """Логирование информационных сообщений"""
    if kwargs:
        message = f"{message} | {kwargs}"
    logger.info(message)

def log_debug(message, **kwargs):
    """Логирование отладочных сообщений"""
    if kwargs:
        message = f"{message} | {kwargs}"
    logger.debug(message)

def log_warning(message, **kwargs):
    """Логирование предупреждений"""
    if kwargs:
        message = f"{message} | {kwargs}"
    logger.warning(message)

def log_error(message, exc_info=None, **kwargs):
    """Логирование ошибок"""
    if kwargs:
        message = f"{message} | {kwargs}"
    logger.error(message, exc_info=exc_info)

def log_critical(message, exc_info=None, **kwargs):
    """Логирование критических ошибок"""
    if kwargs:
        message = f"{message} | {kwargs}"
    logger.critical(message, exc_info=exc_info)

# Логируем начало сессии
log_info("=" * 80)
log_info(f"Новая игровая сессия начата: {session_timestamp}")
log_info(f"Файл логов: {log_filename}")
log_info("=" * 80)
