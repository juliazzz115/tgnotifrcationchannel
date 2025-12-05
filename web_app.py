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
        self.alert_delay = int(os.getenv('ALERT_DELAY', '5'))  # Временно 5 секунд для отладки

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

            # ВАЖНО: Подписываемся на канал если ещё не подписаны
            try:
                from telethon.tl.functions.channels import JoinChannelRequest
                await self.client(JoinChannelRequest(channel))
                logger.info("✅ Подписан на канал")
            except Exception as e:
                logger.info(f"Подписка на канал (возможно уже подписан): {e}")

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
        # Создаем event loop ПЕРЕД созданием TelegramMonitor
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        monitor = TelegramMonitor(socketio)
        telegram_client = monitor.client
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


@app.route('/status')
def status_page():
    """Страница проверки статуса"""
    is_connected = telegram_client is not None and telegram_client.is_connected()

    status_html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Статус подключения</title>
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
            .warning {{
                background: #fef3c7;
                padding: 15px;
                border-radius: 8px;
                margin: 15px 0;
                color: #92400e;
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
            // Автообновление каждые 5 секунд
            setTimeout(() => location.reload(), 5000);
        </script>
    </head>
    <body>
        <div class="container">
            <h1>📊 Статус подключения</h1>

            <div class="status {'connected' if is_connected else 'disconnected'}">
                {'✅ Telegram подключен' if is_connected else '❌ Telegram НЕ подключен'}
            </div>

            <div class="info">
                <strong>Канал для мониторинга:</strong><br>
                {os.getenv('CHANNEL_ID', 'не указан')}
            </div>

            <div class="info">
                <strong>Задержка уведомлений:</strong><br>
                {os.getenv('ALERT_DELAY', '60')} секунд
            </div>

            {'<div class="info"><strong>✅ Всё работает!</strong><br>Сервер мониторит канал. Когда придет сообщение - появится уведомление.</div>' if is_connected else '<div class="warning"><strong>⚠️ Telegram не подключен!</strong><br><br>Возможные причины:<br>• Не указаны API_ID и API_HASH<br>• Неправильный CHANNEL_ID<br>• Требуется авторизация (номер телефона и код)<br>• Проверьте логи сервера</div>'}

            <div style="margin-top: 30px; text-align: center;">
                <a href="/" class="button">Главная</a>
                <a href="/test" class="button">Тест уведомления</a>
            </div>

            <div class="info" style="margin-top: 20px; font-size: 14px; color: #666;">
                Страница обновляется каждые 5 секунд
            </div>
        </div>
    </body>
    </html>
    """
    return status_html


@app.route('/test')
def send_test_alert():
    """Отправить тестовое уведомление - просто откройте этот URL!"""
    test_message = """📋 *Чаты без ответа MCG1 (сегодня):*

– KIRYL ILYENKOU (15:32)
  💬 понял, спасибо

– Yelyzaveta Bachiieva (15:02)
  💬 Будут скорее эти и еще какие-то ,я отпишу сегодня - завтра

– Volodymyr SMIRNOV JDG L (13:29)
  💬 Да, буду пробовать на следующей неделе!

– Polina VITARO SPÓŁKA (13:18)
  💬 Здравствуйте
К сожалению нет
В понедельник займусь и этим и договором

– Павел (13:09)
  💬 Уточните и я им отпишу 🙏"""

    from datetime import datetime

    # Отправляем тестовое уведомление всем подключенным клиентам
    socketio.emit('new_alert', {
        'message_id': 99999,
        'message_text': test_message,
        'channel_name': '🧪 ТЕСТОВЫЙ КАНАЛ',
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'date': datetime.now().strftime('%d.%m.%Y')
    }, namespace='/')

    logger.info("Отправлено тестовое уведомление")

    return """
    <html>
    <head>
        <meta charset="utf-8">
        <title>Тест отправлен!</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                margin: 0;
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
                max-width: 500px;
            }
            h1 { color: #10b981; }
            p { color: #666; line-height: 1.6; }
            a {
                display: inline-block;
                margin-top: 20px;
                padding: 12px 24px;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 8px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>✅ Тестовое уведомление отправлено!</h1>
            <p>Посмотрите на вкладку с главной страницей - должно появиться большое красное окно!</p>
            <p>Если вкладка не открыта, <a href="/">откройте её сначала</a></p>
            <a href="/test">Отправить ещё раз</a>
        </div>
    </body>
    </html>
    """


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
