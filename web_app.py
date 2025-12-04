"""
Веб-сервер для Telegram Desktop Alerts
Показывает полноэкранные уведомления в браузере
"""
import os
import asyncio
import logging
from datetime import datetime
from threading import Thread, Timer
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import Message

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Создаем Flask приложение
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'telegram-alerts-secret-key')
CORS(app)

# Инициализация SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Глобальные переменные
telegram_client = None
pending_alerts = {}


class TelegramMonitor:
    """Класс для мониторинга Telegram канала"""

    def __init__(self, socketio_instance):
        self.socketio = socketio_instance
        self.api_id = os.getenv('API_ID')
        self.api_hash = os.getenv('API_HASH')
        self.channel_id = os.getenv('CHANNEL_ID')
        self.alert_delay = int(os.getenv('ALERT_DELAY', '60'))

        if not self.api_id or not self.api_hash or not self.channel_id:
            raise ValueError("Необходимо заполнить API_ID, API_HASH и CHANNEL_ID в файле .env")

        if self.channel_id.startswith('@'):
            self.channel_entity = self.channel_id
        else:
            try:
                self.channel_entity = int(self.channel_id)
            except ValueError:
                raise ValueError(f"CHANNEL_ID должен быть числом или начинаться с @")

        self.client = TelegramClient('telegram_session', int(self.api_id), self.api_hash)

        logger.info(f"TelegramMonitor инициализирован")
        logger.info(f"Канал: {self.channel_entity}, Задержка: {self.alert_delay} сек")

    def _send_alert(self, message_text: str, channel_name: str, message_id: int):
        """Отправить уведомление в браузер"""
        try:
            logger.info(f"Отправка уведомления в браузер (ID: {message_id})")

            alert_data = {
                'message_id': message_id,
                'message_text': message_text,
                'channel_name': channel_name,
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'date': datetime.now().strftime('%d.%m.%Y')
            }

            self.socketio.emit('new_alert', alert_data, namespace='/')
            logger.info("Уведомление отправлено")

        except Exception as e:
            logger.error(f"Ошибка отправки: {e}", exc_info=True)

    def _schedule_alert(self, message: Message, channel_name: str):
        """Запланировать уведомление через заданное время"""
        message_id = message.id
        message_text = message.text or "[Без текста]"

        if message_id in pending_alerts:
            pending_alerts[message_id].cancel()

        def send_alert():
            if message_id in pending_alerts:
                del pending_alerts[message_id]
            self._send_alert(message_text, channel_name, message_id)

        timer = Timer(self.alert_delay, send_alert)
        timer.start()
        pending_alerts[message_id] = timer

        logger.info(f"Уведомление запланировано через {self.alert_delay} сек")

    async def _on_new_message(self, event: events.NewMessage.Event):
        """Обработчик новых сообщений"""
        message = event.message
        chat = await event.get_chat()
        channel_name = getattr(chat, 'title', str(self.channel_entity))

        logger.info(f"Новое сообщение в '{channel_name}' (ID: {message.id})")
        self._schedule_alert(message, channel_name)

    async def start(self):
        """Запуск мониторинга"""
        try:
            logger.info("Запуск Telegram клиента...")
            await self.client.start()

            me = await self.client.get_me()
            logger.info(f"Авторизован: {me.first_name} (@{me.username})")

            channel = await self.client.get_entity(self.channel_entity)
            logger.info(f"Канал: {channel.title} (ID: {channel.id})")

            @self.client.on(events.NewMessage(chats=self.channel_entity))
            async def handler(event):
                await self._on_new_message(event)

            logger.info("✅ Мониторинг запущен!")
            await self.client.run_until_disconnected()

        except Exception as e:
            logger.error(f"Ошибка мониторинга: {e}", exc_info=True)
            raise


def run_telegram_monitor():
    """Запуск монитора в отдельном потоке"""
    global telegram_client
    try:
        monitor = TelegramMonitor(socketio)
        telegram_client = monitor.client
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(monitor.start())
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@app.route('/')
def index():
    """Главная страница"""
    return render_template('alert.html')


@app.route('/api/status')
def status():
    """Статус сервера"""
    return {
        'status': 'running',
        'telegram_connected': telegram_client is not None and telegram_client.is_connected(),
        'pending_alerts': len(pending_alerts)
    }


@socketio.on('connect')
def handle_connect():
    """Подключение клиента"""
    logger.info(f"Клиент подключен: {request.sid}")
    emit('connected', {'status': 'ok'})


@socketio.on('disconnect')
def handle_disconnect():
    """Отключение клиента"""
    logger.info(f"Клиент отключен: {request.sid}")


@socketio.on('alert_confirmed')
def handle_confirmed(data):
    """Подтверждение уведомления"""
    message_id = data.get('message_id')
    user_name = data.get('user_name')
    logger.info(f"Уведомление {message_id} подтверждено: {user_name}")
    emit('confirmation_received', {'message_id': message_id})


if __name__ == '__main__':
    # Запуск Telegram монитора
    telegram_thread = Thread(target=run_telegram_monitor, daemon=True)
    telegram_thread.start()

    port = int(os.getenv('PORT', '5000'))
    host = os.getenv('HOST', '0.0.0.0')

    logger.info(f"🚀 Сервер: http://localhost:{port}")
    logger.info(f"📱 Откройте эту ссылку в браузере!")

    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
