"""
TELEGRAM ALERTS - СИСТЕМА ДЛЯ МЕНЕДЖЕРОВ
Сканирование диалогов и отслеживание неотвеченных сообщений
"""
import os
import asyncio
import logging
import json
import pytz
from datetime import datetime, time, timezone
from threading import Thread
from flask import Flask, render_template, request, jsonify, Response, redirect
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import csv
from io import StringIO
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from sentiment_analyzer import analyzer as sentiment_analyzer
from google_ai_analyzer import GoogleAIAnalyzer
from detailed_analyzer import DetailedAnalyzer

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
unanswered_dialogs = []

# Файл для хранения статусов
STATUS_FILE = 'dialog_statuses.json'

# Менеджеры
MANAGERS = ['Влад', 'Егор']

# Проверяем наличие сессии
SESSION_STRING = os.getenv('SESSION_STRING')
session_exists = bool(SESSION_STRING) or os.path.exists('telegram_session.session')

# Переменные для setup
temp_client = None
temp_loop = None
phone_number = None
phone_code_hash = None

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

# Настройки из notifier.py
LOCAL_TZ = pytz.timezone('Europe/Warsaw')

# Чаты, которые нужно игнорировать
EXCLUDED_KEYWORDS = [
    "бизнес в польше", "законы", "спулки", "ип в польше",
    "mcg warszawa", "invoices", "kadry", "telegram", "utracone", "utraci"
]


def load_statuses():
    """Загрузить статусы из файла"""
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки статусов: {e}")
    return {}


def save_statuses(statuses):
    """Сохранить статусы в файл"""
    try:
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(statuses, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения статусов: {e}")


def is_excluded(dialog):
    """Проверка нужно ли исключить диалог"""
    title = (getattr(dialog, 'name', '') or getattr(dialog.entity, 'title', '') or '').lower()
    return any(keyword in title for keyword in EXCLUDED_KEYWORDS)


class DialogScanner:
    """Сканер диалогов для поиска неотвеченных сообщений"""

    def __init__(self):
        logger.info("=" * 80)
        logger.info("ИНИЦИАЛИЗАЦИЯ СКАНЕРА ДИАЛОГОВ")
        logger.info("=" * 80)

        logger.info(f"API_ID: {API_ID}")
        logger.info(f"API_HASH: {API_HASH[:10]}..." if API_HASH else "API_HASH: НЕ УСТАНОВЛЕН")

        if not API_ID or not API_HASH:
            raise ValueError("НЕ УКАЗАНЫ API_ID или API_HASH!")

        # Используем StringSession если есть
        if SESSION_STRING:
            logger.info("📝 Используется StringSession из переменной окружения")
            self.client = TelegramClient(StringSession(SESSION_STRING), int(API_ID), API_HASH)
        else:
            logger.info("📁 Используется файл telegram_session.session")
            self.client = TelegramClient('telegram_session', int(API_ID), API_HASH)

        logger.info("✅ TelegramClient создан")

    async def get_unanswered_dialogs(self, mode='dialogs'):
        """
        Получить список неотвеченных диалогов

        Args:
            mode: 'dialogs' или 'analytics'
                - dialogs: прочитано + последнее от клиента + нет ответа от НАС > 1ч
                - analytics: прочитано + нет ответа от ЛЮБОЙ стороны > 1ч (с 08:00 до 16:00)
        """
        try:
            me = await self.client.get_me()
            dialogs = await self.client.get_dialogs(limit=300)

            unanswered = []
            now = datetime.now(LOCAL_TZ)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            for dialog in dialogs:
                # Пропускаем исключенные чаты
                if is_excluded(dialog):
                    continue

                entity = dialog.entity

                # Пропускаем ботов и самого себя
                if getattr(entity, 'bot', False) or entity.id == me.id:
                    continue

                # Пропускаем группы и каналы - только личные чаты
                if hasattr(entity, 'broadcast') or hasattr(entity, 'megagroup'):
                    continue

                last_msg = dialog.message
                if not last_msg:
                    continue

                await last_msg.get_sender()
                sender = last_msg.sender

                # РЕЖИМ "ДИАЛОГИ": unread_count == 0 (прочитали) и последнее от клиента
                # РЕЖИМ "АНАЛИТИКА": unread_count == 0 (прочитали) независимо от отправителя

                if mode == 'dialogs':
                    # Диалоги: прочитано И последнее от клиента (нужен ответ от НАС)
                    should_include = (dialog.unread_count == 0 and sender and sender.id != me.id)
                else:  # analytics
                    # Аналитика: прочитано (неважно от кого последнее)
                    should_include = (dialog.unread_count == 0)

                if should_include:
                    name = dialog.name or getattr(entity, 'username', 'Без имени')
                    local_time = last_msg.date.astimezone(LOCAL_TZ)

                    # Для диалогов: только за сегодня (с 00:00)
                    # Для аналитики: показываем ВСЕ прочитанные (без временного ограничения)
                    if mode == 'dialogs':
                        if local_time < today_start:
                            continue

                    # Время без ответа
                    time_ago = now - local_time
                    hours_ago = time_ago.total_seconds() / 3600

                    # ФИЛЬТР: Показываем только если > 1 часа без ответа
                    if hours_ago < 1.0:
                        continue

                    # Получаем последние 3 сообщения для контекста
                    recent_messages = []
                    try:
                        async for msg in self.client.iter_messages(entity, limit=3):
                            msg_sender = await msg.get_sender()
                            is_from_me = msg_sender and msg_sender.id == me.id if msg_sender else False

                            recent_messages.append({
                                'text': msg.message or '[нет текста]',
                                'time': msg.date.astimezone(LOCAL_TZ).strftime('%H:%M'),
                                'from_me': is_from_me,
                                'sender_name': 'Вы' if is_from_me else name
                            })

                        # Разворачиваем чтобы старые были первыми
                        recent_messages.reverse()
                    except Exception as e:
                        logger.error(f"Ошибка получения истории для {name}: {e}")
                        recent_messages = [{
                            'text': last_msg.message or '[нет текста]',
                            'time': local_time.strftime('%H:%M'),
                            'from_me': False,
                            'sender_name': name
                        }]

                    # Формируем ссылку на чат
                    chat_link = ""
                    if hasattr(entity, 'username') and entity.username:
                        chat_link = f"https://t.me/{entity.username}"
                    else:
                        chat_link = f"tg://openmessage?user_id={entity.id}"

                    # 🤖 AI АНАЛИЗ ДИАЛОГА (улучшенный)
                    analysis = sentiment_analyzer.analyze_dialog(recent_messages, hours_ago)

                    unanswered.append({
                        'id': entity.id,
                        'name': name,
                        'time': local_time.strftime('%H:%M'),
                        'date': local_time.strftime('%d.%m.%Y'),
                        'text': (last_msg.message or '[нет текста]').strip()[:200],  # Последнее сообщение
                        'messages': recent_messages,  # История последних 3
                        'hours_ago': round(hours_ago, 1),
                        'chat_link': chat_link,
                        'timestamp': last_msg.date.timestamp(),
                        'mode': mode,  # Режим (dialogs/analytics)
                        # Данные AI анализа
                        'sentiment': analysis['sentiment'],
                        'sentiment_score': analysis['sentiment_score'],
                        'client_emotion': analysis['client_emotion'],
                        'urgency': analysis['urgency'],
                        'issues': analysis['issues'],
                        'introduced': analysis['introduced'],
                        'manager_name': analysis['manager_name'],
                        'greeting': analysis['greeting'],
                        'is_critical': analysis['is_critical'],
                        'warnings': analysis['warnings'],
                        'recommendations': analysis['recommendations'],
                        # Новые данные из улучшенного анализатора
                        'quality_score': analysis['score'],
                        'quality_level': analysis['quality_level'],
                        'quality_class': analysis['quality_class'],
                        'quality_deductions': analysis['deductions'],
                        'problem_categories': analysis['problem_categories']
                    })

            logger.info(f"📊 Найдено неотвеченных диалогов: {len(unanswered)}")
            return unanswered

        except Exception as e:
            logger.error(f"❌ Ошибка сканирования: {e}", exc_info=True)
            return []

    async def scan_forever(self):
        """Бесконечное сканирование"""
        global telegram_client, unanswered_dialogs

        try:
            logger.info("=" * 80)
            logger.info("ПОДКЛЮЧЕНИЕ К TELEGRAM")
            logger.info("=" * 80)

            await self.client.start()
            telegram_client = self.client

            me = await self.client.get_me()
            logger.info(f"✅ АВТОРИЗОВАН: {me.first_name} (@{me.username})")

            logger.info("=" * 80)
            logger.info("ЗАПУСК СКАНИРОВАНИЯ")
            logger.info("=" * 80)

            scan_count = 0
            previous_dialog_ids = set()  # Отслеживаем ID диалогов из предыдущего сканирования

            while True:
                scan_count += 1
                logger.info(f"СКАНИРОВАНИЕ #{scan_count} - {datetime.now().strftime('%H:%M:%S')}")

                # Получаем неотвеченные диалоги (только для раздела "Диалоги")
                dialogs = await self.get_unanswered_dialogs(mode='dialogs')

                # Загружаем статусы
                statuses = load_statuses()

                if dialogs:
                    # Обогащаем данные статусами
                    current_dialog_ids = set()
                    for dialog in dialogs:
                        dialog_id = str(dialog['id'])
                        current_dialog_ids.add(dialog_id)

                        if dialog_id in statuses:
                            dialog['status'] = statuses[dialog_id].get('status', 'new')
                            dialog['manager'] = statuses[dialog_id].get('manager', '')
                            dialog['note'] = statuses[dialog_id].get('note', '')
                        else:
                            dialog['status'] = 'new'
                            dialog['manager'] = ''
                            dialog['note'] = ''

                    unanswered_dialogs = dialogs

                    # Отправляем обновление всем клиентам
                    socketio.emit('dialogs_update', {'dialogs': dialogs})

                    # Проверяем ДЕЙСТВИТЕЛЬНО НОВЫЕ диалоги (которых не было в предыдущем сканировании)
                    # Отправляем уведомление только для них, НЕ для всех со статусом 'new'
                    new_dialog_ids = current_dialog_ids - previous_dialog_ids
                    if new_dialog_ids and scan_count > 1:  # Не отправляем уведомления при первом сканировании
                        for dialog in dialogs:
                            if str(dialog['id']) in new_dialog_ids:
                                logger.info(f"🔔 НОВЫЙ НЕОТВЕЧЕННЫЙ: {dialog['name']}")
                                socketio.emit('new_unanswered', {'dialog': dialog})

                    # Обновляем список предыдущих ID для следующего сканирования
                    previous_dialog_ids = current_dialog_ids
                else:
                    # Если нет неотвеченных, очищаем список
                    unanswered_dialogs = []
                    socketio.emit('dialogs_update', {'dialogs': []})
                    previous_dialog_ids = set()

                # АВТООЧИСТКА: Убираем из статусов диалоги которых больше нет в неотвеченных
                # (значит мы ответили или клиент написал новое сообщение)
                current_dialog_ids = set(str(d['id']) for d in dialogs)
                updated_statuses = {}
                cleaned_count = 0

                for dialog_id, status_data in statuses.items():
                    # Сохраняем только если диалог всё ещё неотвечен ИЛИ имеет важный статус
                    if dialog_id in current_dialog_ids or status_data.get('status') == 'task':
                        updated_statuses[dialog_id] = status_data
                    else:
                        cleaned_count += 1

                if cleaned_count > 0:
                    logger.info(f"🧹 Автоочистка: удалено {cleaned_count} статусов (диалоги отвечены)")
                    save_statuses(updated_statuses)

                # Ждем 3 минуты до следующего сканирования (частая проверка)
                logger.info(f"⏳ Следующее сканирование через 3 минуты...")
                await asyncio.sleep(180)  # 3 минуты

        except Exception as e:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)


def run_scanner():
    """Запуск сканера в отдельном потоке"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    scanner = DialogScanner()
    loop.run_until_complete(scanner.scan_forever())


# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    """Главная страница - перенаправление на диалоги"""
    if not session_exists:
        return redirect('/setup')
    return redirect('/dialogs')


@app.route('/dialogs')
def dialogs_page():
    """Страница диалогов"""
    if not session_exists:
        return redirect('/setup')
    return render_template('manager.html', managers=MANAGERS, mode='dialogs')


@app.route('/analytics')
def analytics_page():
    """Страница аналитики с Google AI"""
    if not session_exists:
        return redirect('/setup')
    return render_template('analytics.html')


@app.route('/setup')
def setup():
    """Страница настройки сессии"""
    return render_template('setup.html')


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/dialogs', methods=['GET'])
def get_dialogs():
    """Получить список неотвеченных диалогов (для раздела Диалоги)"""
    statuses = load_statuses()

    # Обогащаем диалоги статусами
    enriched_dialogs = []
    for dialog in unanswered_dialogs:
        dialog_id = str(dialog['id'])
        enriched = dialog.copy()
        if dialog_id in statuses:
            enriched.update(statuses[dialog_id])
        else:
            enriched['status'] = 'new'
            enriched['manager'] = ''
            enriched['note'] = ''
        enriched_dialogs.append(enriched)

    return jsonify({'dialogs': enriched_dialogs})


@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Получить аналитику диалогов (с 08:00 до 16:00 сегодня)"""
    try:
        # Создаем временный сканер для аналитики
        if telegram_client:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def fetch_analytics():
                scanner = DialogScanner()
                scanner.client = telegram_client
                analytics_dialogs = await scanner.get_unanswered_dialogs(mode='analytics')
                return analytics_dialogs

            analytics_dialogs = loop.run_until_complete(fetch_analytics())
            loop.close()

            # Обогащаем статусами
            statuses = load_statuses()
            enriched = []
            for dialog in analytics_dialogs:
                dialog_id = str(dialog['id'])
                enriched_dialog = dialog.copy()
                if dialog_id in statuses:
                    enriched_dialog.update(statuses[dialog_id])
                else:
                    enriched_dialog['status'] = 'new'
                    enriched_dialog['manager'] = ''
                    enriched_dialog['note'] = ''
                enriched.append(enriched_dialog)

            return jsonify({'dialogs': enriched})
        else:
            return jsonify({'dialogs': []})
    except Exception as e:
        logger.error(f"Ошибка получения аналитики: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/update_status', methods=['POST'])
def update_status():
    """Обновить статус диалога"""
    data = request.json
    dialog_id = str(data.get('dialog_id'))
    status = data.get('status')
    manager = data.get('manager', '')
    note = data.get('note', '')

    statuses = load_statuses()

    statuses[dialog_id] = {
        'status': status,
        'manager': manager,
        'note': note,
        'updated_at': datetime.now().isoformat()
    }

    save_statuses(statuses)

    # Уведомляем всех клиентов об изменении
    socketio.emit('status_changed', {
        'dialog_id': dialog_id,
        'status': status,
        'manager': manager,
        'note': note
    })

    return jsonify({'success': True})


@app.route('/api/export_csv', methods=['GET'])
def export_csv():
    """Экспорт диалогов в CSV"""
    statuses = load_statuses()

    # Собираем данные
    rows = []
    for dialog in unanswered_dialogs:
        dialog_id = str(dialog['id'])
        status_data = statuses.get(dialog_id, {})

        rows.append({
            'Дата': dialog['date'],
            'Время': dialog['time'],
            'Имя': dialog['name'],
            'Часов без ответа': dialog['hours_ago'],
            'Сообщение': dialog['text'],
            'Статус': status_data.get('status', 'new'),
            'Ответственный': status_data.get('manager', ''),
            'Заметка': status_data.get('note', ''),
            'Ссылка': dialog['chat_link']
        })

    # Создаем CSV
    output = StringIO()
    if rows:
        fieldnames = ['Дата', 'Время', 'Имя', 'Часов без ответа', 'Сообщение', 'Статус', 'Ответственный', 'Заметка', 'Ссылка']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Возвращаем как файл
    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=dialogs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
    )


# ============================================================================
# SETUP API (из старого web_app.py)
# ============================================================================

@app.route('/api/send_code', methods=['POST'])
def send_code():
    """Отправка кода"""
    global temp_client, phone_number, phone_code_hash, temp_loop

    data = request.json
    phone = data.get('phone')

    if not phone:
        return jsonify({'error': 'Не указан номер телефона'}), 400

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    temp_loop = loop

    async def send():
        global temp_client, phone_number, phone_code_hash

        temp_client = TelegramClient(StringSession(), int(API_ID), API_HASH)
        await temp_client.connect()

        result = await temp_client.send_code_request(phone)
        phone_number = phone
        phone_code_hash = result.phone_code_hash

        return {'success': True}

    result = loop.run_until_complete(send())
    return jsonify(result)


@app.route('/api/verify_code', methods=['POST'])
def verify_code():
    """Проверка кода"""
    global temp_client, phone_number, phone_code_hash

    data = request.json
    code = data.get('code')

    if not code:
        return jsonify({'error': 'Не указан код'}), 400

    asyncio.set_event_loop(temp_loop)

    async def verify():
        try:
            await temp_client.sign_in(phone_number, code, phone_code_hash=phone_code_hash)

            session_string = temp_client.session.save()

            await temp_client.disconnect()

            return {'success': True, 'session_string': session_string}

        except SessionPasswordNeededError:
            return {'error': '2FA включена. Введите пароль.'}
        except Exception as e:
            return {'error': str(e)}

    result = temp_loop.run_until_complete(verify())
    return jsonify(result)


# ============================================================================
# WEBSOCKET HANDLERS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Клиент подключился"""
    logger.info(f"✅ Клиент подключился: {request.sid}")
    emit('connected', {'status': 'ok'})


@socketio.on('disconnect')
def handle_disconnect():
    """Клиент отключился"""
    logger.info(f"❌ Клиент отключился: {request.sid}")


# ============================================================================
# ЗАПУСК
# ============================================================================

if __name__ == '__main__':
    logger.info("🚀 Запуск Telegram Alerts - Система для менеджеров")

    if session_exists:
        # Запускаем сканер в отдельном потоке
        scanner_thread = Thread(target=run_scanner, daemon=True)
        scanner_thread.start()
        logger.info("✅ Сканер запущен в фоновом потоке")
    else:
        logger.warning("⚠️  Сессия не найдена. Откройте /setup для настройки")

    # Запуск Flask
    port = int(os.getenv('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
