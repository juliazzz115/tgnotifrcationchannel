"""
Веб-сервер для Telegram Desktop Alerts
ПРОСТОЕ И НАДЕЖНОЕ СКАНИРОВАНИЕ КАНАЛА
"""
import os
import asyncio
import logging
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from dotenv import load_dotenv
from telethon import TelegramClient
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
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)

# Глобальные переменные
telegram_client = None
last_message_id = None  # ID последнего просмотренного сообщения
confirmed_messages = set()  # ID подтвержденных сообщений


class TelegramScanner:
    """Класс для СКАНИРОВАНИЯ Telegram канала (не ждем события, а проверяем сами!)"""

    def __init__(self, socketio_instance):
        self.socketio = socketio_instance
        self.api_id = os.getenv('API_ID')
        self.api_hash = os.getenv('API_HASH')
        self.channel_id = os.getenv('CHANNEL_ID')
        self.scan_interval = 3  # Сканируем каждые 3 секунды

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
        self.running = True

        logger.info(f"TelegramScanner инициализирован")
        logger.info(f"Канал: {self.channel_entity}, Интервал сканирования: {self.scan_interval} сек")

    async def get_recent_messages(self, limit=20):
        """Получить последние сообщения из канала"""
        try:
            messages = []
            async for message in self.client.iter_messages(self.channel_entity, limit=limit):
                if message.text:  # Только текстовые сообщения
                    messages.append({
                        'id': message.id,
                        'text': message.text,
                        'date': message.date.strftime('%d.%m.%Y'),
                        'time': message.date.strftime('%H:%M:%S')
                    })
            return messages
        except Exception as e:
            logger.error(f"Ошибка получения сообщений: {e}")
            return []

    async def scan_loop(self):
        """Бесконечный цикл сканирования канала"""
        global last_message_id

        logger.info("=" * 80)
        logger.info("🚀 ЗАПУСК СКАНЕРА КАНАЛА")
        logger.info("=" * 80)

        await self.client.start()
        me = await self.client.get_me()
        logger.info(f"✅ Авторизован: {me.first_name} (@{me.username})")

        channel = await self.client.get_entity(self.channel_entity)
        logger.info(f"✅ Подключен к каналу: {channel.title} (ID: {channel.id})")

        # Подписываемся на канал если ещё не подписаны
        try:
            from telethon.tl.functions.channels import JoinChannelRequest
            await self.client(JoinChannelRequest(channel))
            logger.info("✅ Подписан на канал")
        except Exception as e:
            logger.info(f"Подписка: {e}")

        logger.info("=" * 80)
        logger.info("🔍 НАЧИНАЮ СКАНИРОВАНИЕ КАНАЛА КАЖДЫЕ 3 СЕКУНДЫ")
        logger.info("=" * 80)

        while self.running:
            try:
                # Получаем последние сообщения
                messages = await self.get_recent_messages(limit=20)

                if messages:
                    # Отправляем все сообщения клиентам
                    self.socketio.emit('messages_update', {
                        'messages': messages,
                        'channel_name': channel.title
                    }, namespace='/')

                    # Проверяем есть ли НОВЫЕ сообщения
                    newest_message_id = messages[0]['id']

                    if last_message_id is None:
                        # Первый запуск - запоминаем последнее сообщение
                        last_message_id = newest_message_id
                        logger.info(f"📌 Инициализация: последнее сообщение ID {last_message_id}")
                    elif newest_message_id > last_message_id:
                        # Есть НОВЫЕ сообщения!
                        new_messages = [m for m in messages if m['id'] > last_message_id]

                        logger.info("=" * 80)
                        logger.info(f"🔔 ОБНАРУЖЕНО {len(new_messages)} НОВЫХ СООБЩЕНИЙ!")
                        logger.info("=" * 80)

                        for msg in reversed(new_messages):  # От старых к новым
                            if msg['id'] not in confirmed_messages:
                                logger.info(f"📢 НОВОЕ: ID {msg['id']}")
                                logger.info(f"💬 Текст: {msg['text'][:100]}...")
                                logger.info(f"⏰ Время: {msg['time']}")

                                # Отправляем уведомление о НОВОМ сообщении
                                self.socketio.emit('new_message_alert', {
                                    'message': msg,
                                    'channel_name': channel.title
                                }, namespace='/')

                        last_message_id = newest_message_id

                # Ждем перед следующим сканированием
                await asyncio.sleep(self.scan_interval)

            except Exception as e:
                logger.error(f"❌ Ошибка сканирования: {e}", exc_info=True)
                await asyncio.sleep(self.scan_interval)

    async def start(self):
        """Запуск сканера"""
        try:
            await self.scan_loop()
        except Exception as e:
            logger.error(f"Критическая ошибка сканера: {e}", exc_info=True)
            raise


def run_telegram_scanner():
    """Запуск сканера в отдельном потоке"""
    global telegram_client
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        scanner = TelegramScanner(socketio)
        telegram_client = scanner.client
        loop.run_until_complete(scanner.start())
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@app.route('/')
def index():
    """Главная страница"""
    return render_template('messages.html')


@app.route('/api/status')
def status():
    """Статус сервера"""
    return {
        'status': 'running',
        'telegram_connected': telegram_client is not None and telegram_client.is_connected(),
        'last_message_id': last_message_id,
        'confirmed_count': len(confirmed_messages)
    }


@app.route('/status')
def status_page():
    """Страница проверки статуса"""
    is_connected = telegram_client is not None and telegram_client.is_connected()

    status_html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Статус сканера</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 600px;
                width: 100%;
            }}
            h1 {{
                color: #333;
                margin-bottom: 20px;
            }}
            .status {{
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                font-size: 18px;
                font-weight: bold;
            }}
            .connected {{
                background: #d1fae5;
                color: #065f46;
            }}
            .disconnected {{
                background: #fee2e2;
                color: #991b1b;
            }}
            .info {{
                background: #f3f4f6;
                padding: 15px;
                border-radius: 8px;
                margin: 15px 0;
                line-height: 1.6;
            }}
            a {{
                color: #667eea;
                text-decoration: none;
                font-weight: bold;
            }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                margin: 10px 5px;
            }}
        </style>
        <script>
            setTimeout(() => location.reload(), 5000);
        </script>
    </head>
    <body>
        <div class="container">
            <h1>🔍 Статус сканера</h1>

            <div class="status {'connected' if is_connected else 'disconnected'}">
                {'✅ Telegram подключен - СКАНИРУЮ КАНАЛ' if is_connected else '❌ Telegram НЕ подключен'}
            </div>

            <div class="info">
                <strong>Канал:</strong><br>
                {os.getenv('CHANNEL_ID', 'не указан')}
            </div>

            <div class="info">
                <strong>Режим работы:</strong><br>
                Сканирование каждые 3 секунды
            </div>

            {'<div class="info"><strong>✅ Работает!</strong><br>Сканер проверяет канал каждые 3 секунды и сразу покажет новые сообщения!</div>' if is_connected else '<div class="info" style="background: #fee2e2; color: #991b1b;"><strong>⚠️ Не подключен!</strong><br>Проверьте логи</div>'}

            <div style="margin-top: 30px; text-align: center;">
                <a href="/" class="button">Главная</a>
            </div>

            <div class="info" style="margin-top: 20px; font-size: 14px; color: #666;">
                Обновление каждые 5 секунд
            </div>
        </div>
    </body>
    </html>
    """
    return status_html


@socketio.on('connect')
def handle_connect():
    """Подключение клиента"""
    logger.info(f"✅ Клиент подключен: {request.sid}")
    emit('connected', {'status': 'ok'})


@socketio.on('disconnect')
def handle_disconnect():
    """Отключение клиента"""
    logger.info(f"❌ Клиент отключен: {request.sid}")


@socketio.on('confirm_message')
def handle_confirm(data):
    """Подтверждение просмотра сообщения"""
    global confirmed_messages
    message_id = data.get('message_id')
    user_name = data.get('user_name')

    confirmed_messages.add(message_id)
    logger.info(f"✅ Сообщение {message_id} подтверждено пользователем: {user_name}")
    logger.info(f"📊 Всего подтверждено: {len(confirmed_messages)}")

    emit('confirmation_received', {'message_id': message_id})


if __name__ == '__main__':
    # Запуск Telegram сканера
    scanner_thread = Thread(target=run_telegram_scanner, daemon=True)
    scanner_thread.start()

    port = int(os.getenv('PORT', '5000'))
    host = os.getenv('HOST', '0.0.0.0')

    logger.info("=" * 80)
    logger.info(f"🚀 Сервер запущен: http://localhost:{port}")
    logger.info(f"📱 Откройте эту ссылку в браузере!")
    logger.info("=" * 80)

    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
