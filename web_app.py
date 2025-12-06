"""
TELEGRAM ALERTS - ПРОСТАЯ ВЕРСИЯ
С автоматическим переходом на страницу настройки если нет сессии
"""
import os
import asyncio
import logging
from datetime import datetime
from threading import Thread
from flask import Flask, render_template, request, jsonify, redirect
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

load_dotenv()

# ЛОГИРОВАНИЕ
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
all_messages = []
last_check_id = None
session_exists = os.path.exists('telegram_session.session')

# Переменные для setup
temp_client = None
phone_number = None
phone_code_hash = None

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
CHANNEL_ID = os.getenv('CHANNEL_ID', '@utraci')


class SimpleScanner:
    """Простейший сканер канала"""

    def __init__(self):
        logger.info("=" * 80)
        logger.info("ИНИЦИАЛИЗАЦИЯ СКАНЕРА")
        logger.info("=" * 80)

        logger.info(f"API_ID: {API_ID}")
        logger.info(f"API_HASH: {API_HASH[:10]}..." if API_HASH else "API_HASH: НЕ УСТАНОВЛЕН")
        logger.info(f"CHANNEL_ID: {CHANNEL_ID}")

        if not API_ID or not API_HASH:
            raise ValueError("НЕ УКАЗАНЫ API_ID или API_HASH!")

        self.client = TelegramClient('telegram_session', int(API_ID), API_HASH)
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

            logger.info(f"Получаю информацию о канале: {CHANNEL_ID}")
            channel = await self.client.get_entity(CHANNEL_ID)
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
                    logger.info("Получаю последние 10 сообщений из канала...")
                    messages = []

                    async for message in self.client.iter_messages(CHANNEL_ID, limit=10):
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

                    all_messages = messages
                    logger.info("Отправляю обновление всем подключенным клиентам...")
                    socketio.emit('messages_update', {'messages': messages})

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
    if not session_exists:
        logger.info("⚠️  Нет session файла - сканер НЕ запускается")
        return

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
    """Главная страница - перенаправляет на setup если нет сессии"""
    if not session_exists:
        logger.info("📄 Нет сессии - перенаправление на /setup")
        return redirect('/setup')

    logger.info("📄 Запрос главной страницы")
    return render_template('simple.html')


@app.route('/setup')
def setup():
    """Страница настройки сессии"""
    return render_template('setup.html')


@app.route('/api/send_code', methods=['POST'])
def send_code():
    """Отправить код на телефон"""
    global temp_client, phone_number, phone_code_hash

    data = request.json
    phone_number = data.get('phone')

    if not phone_number:
        return jsonify({'error': 'Укажите номер телефона'}), 400

    try:
        # ВАЖНО: создаем event loop ПЕРЕД созданием TelegramClient!
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Теперь создаем клиент - у потока уже есть event loop
        temp_client = TelegramClient('telegram_session_NEW', int(API_ID), API_HASH)

        async def send():
            await temp_client.connect()
            result = await temp_client.send_code_request(phone_number)
            return result.phone_code_hash

        phone_code_hash = loop.run_until_complete(send())

        return jsonify({
            'success': True,
            'message': f'Код отправлен на номер {phone_number}'
        })

    except Exception as e:
        logger.error(f"Ошибка send_code: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/verify_code', methods=['POST'])
def verify_code():
    """Проверить код и создать сессию"""
    global temp_client, phone_number, phone_code_hash, session_exists

    data = request.json
    code = data.get('code')

    if not code or not temp_client:
        return jsonify({'error': 'Сначала отправьте код на телефон'}), 400

    try:
        # Получаем или создаем event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def sign_in():
            try:
                await temp_client.sign_in(phone_number, code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                return {'error': 'У вас включена двухфакторная аутентификация. Этот интерфейс пока не поддерживает 2FA.'}

            me = await temp_client.get_me()
            await temp_client.disconnect()
            return me

        me = loop.run_until_complete(sign_in())

        if isinstance(me, dict) and 'error' in me:
            return jsonify(me), 400

        # Удаляем старую сессию
        if os.path.exists('telegram_session.session'):
            os.remove('telegram_session.session')

        # Переименовываем новую сессию
        if os.path.exists('telegram_session_NEW.session'):
            os.rename('telegram_session_NEW.session', 'telegram_session.session')
            session_exists = True

        return jsonify({
            'success': True,
            'message': f'✅ Авторизация успешна! Привет, {me.first_name}! Теперь перезапустите приложение в Railway.',
            'user': {
                'first_name': me.first_name,
                'username': me.username
            }
        })

    except Exception as e:
        logger.error(f"Ошибка verify_code: {e}", exc_info=True)
        return jsonify({'error': f'Ошибка: {str(e)}'}), 500


@app.route('/api/status')
def status():
    is_connected = telegram_client and telegram_client.is_connected()
    return {
        'connected': is_connected,
        'messages_count': len(all_messages),
        'last_id': last_check_id,
        'session_exists': session_exists
    }


@socketio.on('connect')
def handle_connect():
    logger.info(f"✅ Клиент подключен")
    emit('connected', {'status': 'ok'})

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
    logger.info(f"Session файл существует: {session_exists}")

    if session_exists:
        # Запускаем сканер только если есть сессия
        scanner_thread = Thread(target=run_scanner, daemon=True)
        scanner_thread.start()
        logger.info("✅ Поток сканера запущен")
    else:
        logger.info("⚠️  НЕТ SESSION ФАЙЛА - откройте главную страницу для настройки")

    port = int(os.getenv('PORT', '5000'))
    logger.info(f"🌐 Запуск веб-сервера на порту {port}")
    logger.info("=" * 80)

    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
