"""
TELEGRAM ALERTS - МАКСИМАЛЬНО ПРОСТАЯ И НАДЕЖНАЯ ВЕРСИЯ
Сканирование канала каждые 5 секунд
"""
import os
import asyncio
import logging
from datetime import datetime
from threading import Thread
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

# ЛОГИРОВАНИЕ - максимально подробное
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Flask приложение
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
CORS(app)

# SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Глобальные переменные
telegram_client = None
all_messages = []  # Все сообщения из канала
last_check_id = None  # ID последнего проверенного сообщения


class SimpleScanner:
    """Простейший сканер канала"""

    def __init__(self):
        logger.info("=" * 80)
        logger.info("ИНИЦИАЛИЗАЦИЯ СКАНЕРА")
        logger.info("=" * 80)

        self.api_id = os.getenv('API_ID')
        self.api_hash = os.getenv('API_HASH')
        self.channel_id = os.getenv('CHANNEL_ID', '@utraci')

        logger.info(f"API_ID: {self.api_id}")
        logger.info(f"API_HASH: {self.api_hash[:10]}..." if self.api_hash else "API_HASH: НЕ УСТАНОВЛЕН")
        logger.info(f"CHANNEL_ID: {self.channel_id}")

        if not self.api_id or not self.api_hash:
            raise ValueError("НЕ УКАЗАНЫ API_ID или API_HASH!")

        self.client = TelegramClient('telegram_session', int(self.api_id), self.api_hash)
        logger.info("✅ TelegramClient создан")

    async def scan_forever(self):
        """Бесконечное сканирование"""
        global telegram_client, all_messages, last_check_id

        try:
            logger.info("=" * 80)
            logger.info("ПОДКЛЮЧЕНИЕ К TELEGRAM")
            logger.info("=" * 80)

            await self.client.start()
            telegram_client = self.client

            me = await self.client.get_me()
            logger.info(f"✅ АВТОРИЗОВАН: {me.first_name} (@{me.username})")

            logger.info(f"Получаю информацию о канале: {self.channel_id}")
            channel = await self.client.get_entity(self.channel_id)
            logger.info(f"✅ КАНАЛ НАЙДЕН: {channel.title} (ID: {channel.id})")

            logger.info("=" * 80)
            logger.info("НАЧИНАЮ СКАНИРОВАНИЕ КАЖДЫЕ 5 СЕКУНД")
            logger.info("=" * 80)

            scan_count = 0

            while True:
                scan_count += 1
                logger.info(f"\n{'='*80}")
                logger.info(f"СКАНИРОВАНИЕ #{scan_count} - {datetime.now().strftime('%H:%M:%S')}")
                logger.info(f"{'='*80}")

                try:
                    # Получаем последние 10 сообщений
                    logger.info("Получаю последние 10 сообщений из канала...")
                    messages = []

                    async for message in self.client.iter_messages(self.channel_id, limit=10):
                        if message.text:
                            msg_data = {
                                'id': message.id,
                                'text': message.text,
                                'date': message.date.strftime('%d.%m.%Y'),
                                'time': message.date.strftime('%H:%M:%S')
                            }
                            messages.append(msg_data)
                            logger.info(f"  📬 Сообщение #{message.id}: {message.text[:50]}...")

                    logger.info(f"✅ Получено {len(messages)} сообщений")

                    # Обновляем глобальный список
                    all_messages = messages

                    # Отправляем всем клиентам
                    logger.info("Отправляю обновление всем подключенным клиентам...")
                    socketio.emit('messages_update', {'messages': messages})

                    # Проверяем на новые
                    if messages:
                        newest_id = messages[0]['id']

                        if last_check_id is None:
                            logger.info(f"📌 ПЕРВАЯ ПРОВЕРКА: запоминаю ID {newest_id}")
                            last_check_id = newest_id
                        elif newest_id > last_check_id:
                            new_count = 0
                            for msg in messages:
                                if msg['id'] > last_check_id:
                                    new_count += 1

                            logger.info("!" * 80)
                            logger.info(f"🔔 ОБНАРУЖЕНО {new_count} НОВЫХ СООБЩЕНИЙ!")
                            logger.info("!" * 80)

                            # Отправляем алерт
                            for msg in messages:
                                if msg['id'] > last_check_id:
                                    logger.info(f"📢 НОВОЕ СООБЩЕНИЕ #{msg['id']}: {msg['text'][:100]}")
                                    socketio.emit('new_alert', {'message': msg})

                            last_check_id = newest_id
                        else:
                            logger.info(f"ℹ️  Новых сообщений нет (последний ID: {newest_id})")

                except Exception as e:
                    logger.error(f"❌ ОШИБКА ПРИ СКАНИРОВАНИИ: {e}", exc_info=True)

                logger.info(f"⏳ Жду 5 секунд до следующего сканирования...")
                await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
            raise


def run_scanner():
    """Запуск сканера в потоке"""
    logger.info("🚀 ЗАПУСК ПОТОКА СКАНЕРА")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        scanner = SimpleScanner()
        loop.run_until_complete(scanner.scan_forever())
    except Exception as e:
        logger.error(f"❌ Ошибка в потоке сканера: {e}", exc_info=True)


@app.route('/')
def index():
    logger.info("📄 Запрос главной страницы")
    return render_template('simple.html')


@app.route('/api/status')
def status():
    is_connected = telegram_client and telegram_client.is_connected()
    logger.info(f"📊 Запрос статуса: connected={is_connected}, messages={len(all_messages)}")
    return {
        'connected': is_connected,
        'messages_count': len(all_messages),
        'last_id': last_check_id
    }


@socketio.on('connect')
def handle_connect():
    logger.info(f"✅ Клиент подключен")
    emit('connected', {'status': 'ok'})

    # Отправляем текущие сообщения
    if all_messages:
        logger.info(f"Отправляю {len(all_messages)} сообщений новому клиенту")
        emit('messages_update', {'messages': all_messages})


@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"❌ Клиент отключен")


@socketio.on('confirm')
def handle_confirm(data):
    msg_id = data.get('message_id')
    name = data.get('name')
    logger.info(f"✅ Подтверждение сообщения #{msg_id} от {name}")


if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("ЗАПУСК СЕРВЕРА")
    logger.info("=" * 80)

    # Запускаем сканер
    scanner_thread = Thread(target=run_scanner, daemon=True)
    scanner_thread.start()
    logger.info("✅ Поток сканера запущен")

    port = int(os.getenv('PORT', '5000'))
    logger.info(f"🌐 Запуск веб-сервера на порту {port}")
    logger.info("=" * 80)

    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
