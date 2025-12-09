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
from pathlib import Path
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
from detailed_analyzer import detailed_analyzer
from google_ai_analyzer import google_ai_analyzer
from data_archiver import data_archiver

load_dotenv()

GOOGLE_AI_KEY = os.getenv('GOOGLE_AI_KEY', 'AIzaSyBoYgQMK5cydwDThxovjsRdyUEgcIIu2_g')
google_ai_analyzer.api_key = GOOGLE_AI_KEY

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
all_dialogs_for_analytics = []  # ВСЕ диалоги за день для аналитики

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

    async def get_unanswered_dialogs(self):
        """Получить список неотвеченных диалогов"""
        try:
            me = await self.client.get_me()
            dialogs = await self.client.get_dialogs(limit=300)

            unanswered = []

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

                # КЛЮЧЕВАЯ ЛОГИКА: unread_count == 0 (прочитали) и последнее от клиента
                if dialog.unread_count == 0 and sender and sender.id != me.id:
                    name = dialog.name or getattr(entity, 'username', 'Без имени')
                    local_time = last_msg.date.astimezone(LOCAL_TZ)

                    # ФИЛЬТР: Только сегодняшние сообщения (с 00:00 до текущего момента)
                    now = datetime.now(LOCAL_TZ)
                    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

                    if local_time < today_start:
                        continue  # Пропускаем старые диалоги (не за сегодня)

                    # Время без ответа
                    time_ago = now - local_time
                    hours_ago = time_ago.total_seconds() / 3600

                    # ФИЛЬТР: Показываем только если > 1 часа без ответа
                    if hours_ago < 1.0:
                        continue

                    # ОРИГИНАЛЬНАЯ ЛОГИКА: Получаем последние 3 сообщения для контекста
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

                    # Получаем ВСЕ сообщения за СЕГОДНЯ для расширенного анализа (с timestamp)
                    all_messages_for_analysis = []
                    try:
                        async for msg in self.client.iter_messages(entity, limit=None):
                            msg_local_time = msg.date.astimezone(LOCAL_TZ)
                            
                            # Фильтр: только сообщения за сегодня
                            if msg_local_time < today_start:
                                break
                            
                            msg_sender = await msg.get_sender()
                            is_from_me = msg_sender and msg_sender.id == me.id if msg_sender else False

                            all_messages_for_analysis.append({
                                'text': msg.message or '[нет текста]',
                                'time': msg_local_time.strftime('%H:%M'),
                                'from_me': is_from_me,
                                'sender_name': 'Вы' if is_from_me else name,
                                'timestamp': msg.date.timestamp()
                            })

                        all_messages_for_analysis.reverse()
                    except Exception as e:
                        logger.warning(f"Не удалось получить расширенную историю для {name}: {e}")
                        all_messages_for_analysis = recent_messages

                    # Формируем ссылку на чат
                    chat_link = ""
                    if hasattr(entity, 'username') and entity.username:
                        chat_link = f"https://t.me/{entity.username}"
                    else:
                        chat_link = f"tg://openmessage?user_id={entity.id}"

                    # 🤖 БАЗОВЫЙ AI АНАЛИЗ
                    analysis = sentiment_analyzer.analyze_dialog(recent_messages, hours_ago)
                    
                    # 📊 ДЕТАЛЬНЫЙ АНАЛИЗ ВРЕМЕНИ ОТВЕТА НА ПЕРВОЕ СООБЩЕНИЕ
                    response_analysis = detailed_analyzer.analyze_response_times(all_messages_for_analysis)
                    
                    # 📊 СРЕДНЕЕ ВРЕМЯ ОТВЕТА НА ВСЕ СООБЩЕНИЯ В ДИАЛОГЕ
                    all_responses_analysis = detailed_analyzer.analyze_all_response_times(all_messages_for_analysis)
                    
                    # 👤 АНАЛИЗ ПОВЕДЕНИЯ МЕНЕДЖЕРА
                    manager_analysis = detailed_analyzer.analyze_manager_behavior(all_messages_for_analysis)
                    
                    # 🤖 GOOGLE AI АНАЛИЗ (все сообщения за день)
                    ai_analysis = {}
                    try:
                        ai_analysis = google_ai_analyzer.analyze_dialog_with_ai(all_messages_for_analysis)
                    except Exception as e:
                        logger.warning(f"Google AI анализ не удался для {name}: {e}")

                    unanswered.append({
                        'id': entity.id,
                        'name': name,
                        'time': local_time.strftime('%H:%M'),
                        'date': local_time.strftime('%d.%m.%Y'),
                        'text': (last_msg.message or '[нет текста]').strip()[:200],
                        'messages': recent_messages,  # ОРИГИНАЛЬНЫЕ 3 сообщения БЕЗ timestamp
                        'hours_ago': round(hours_ago, 1),
                        'chat_link': chat_link,
                        'timestamp': last_msg.date.timestamp(),
                        # Базовый анализ
                        'sentiment': analysis['sentiment'],
                        'sentiment_score': analysis['sentiment_score'],
                        'client_emotion': analysis['client_emotion'],
                        'urgency': analysis['urgency'],
                        'issues': analysis['issues'],
                        'introduced': manager_analysis.get('introduced'),  # Из детального анализа (все сообщения за день)
                        'manager_name': manager_analysis.get('manager_name'),  # Из детального анализа
                        'greeting': manager_analysis.get('used_greeting'),  # Из детального анализа
                        'is_critical': analysis['is_critical'],
                        'warnings': analysis['warnings'],
                        'recommendations': analysis['recommendations'],
                        # Детальный анализ времени ПЕРВОГО ответа (рабочее время 8-16)
                        'response_delay_minutes': response_analysis.get('response_delay_minutes'),
                        'response_delay_working_minutes': response_analysis.get('response_delay_working_minutes'),
                        'response_delay_hours': response_analysis.get('response_delay_hours'),
                        'response_quality': response_analysis.get('response_quality'),
                        'is_overtime': response_analysis.get('is_overtime'),
                        'waiting_first_response_minutes': response_analysis.get('waiting_first_response_minutes'),
                        # Среднее время ответа на ВСЕ сообщения (рабочее время 8-16)
                        'avg_response_time_minutes': all_responses_analysis.get('avg_response_time_minutes'),
                        'total_client_messages': all_responses_analysis.get('total_client_messages'),
                        'total_responses': all_responses_analysis.get('total_responses'),
                        # Анализ менеджера
                        'message_count': manager_analysis.get('message_count'),
                        'politeness_markers': manager_analysis.get('politeness_markers'),
                        # Google AI анализ - расширенные метрики
                        'professionalism_score': ai_analysis.get('professionalism_score'),
                        'politeness_score': ai_analysis.get('politeness_score'),
                        'clarity_score': ai_analysis.get('clarity_score'),
                        'proactivity_score': ai_analysis.get('proactivity_score'),
                        'responsiveness_score': ai_analysis.get('responsiveness_score'),
                        'empathy_score': ai_analysis.get('empathy_score'),
                        # Детали запроса и эмоций
                        'main_topic': ai_analysis.get('main_topic'),
                        'urgency_level': ai_analysis.get('urgency_level'),
                        'emotion_dynamics': ai_analysis.get('emotion_dynamics'),
                        'client_expectations': ai_analysis.get('client_expectations'),
                        # Коммуникация
                        'communication_style': ai_analysis.get('communication_style'),
                        'used_personalization': ai_analysis.get('used_personalization'),
                        'first_impression': ai_analysis.get('first_impression'),
                        # Решение проблемы
                        'resolution_status': ai_analysis.get('resolution_status'),
                        'solution_provided': ai_analysis.get('solution_provided'),
                        'next_steps_clear': ai_analysis.get('next_steps_clear'),
                        'timeline_given': ai_analysis.get('timeline_given'),
                        # Риски
                        'risk_level': ai_analysis.get('risk_level'),
                        'churn_risk_level': ai_analysis.get('churn_risk_level'),
                        'need_urgent_attention': ai_analysis.get('need_urgent_attention'),
                        'escalation_needed': ai_analysis.get('escalation_needed'),
                        # Детальная информация
                        'key_moments': ai_analysis.get('key_moments', []),
                        'critical_phrases': ai_analysis.get('critical_phrases', []),
                        'missed_opportunities': ai_analysis.get('missed_opportunities', []),
                        'priority_actions': ai_analysis.get('priority_actions', []),
                        # Рекомендации и оценки
                        'ai_suggestions': ai_analysis.get('suggestions', []),
                        'ai_key_issues': ai_analysis.get('key_issues', []),
                        'ai_strengths': ai_analysis.get('strengths', []),
                        'overall_quality': ai_analysis.get('overall_quality'),
                        'client_satisfaction_estimate': ai_analysis.get('client_satisfaction_estimate'),
                        'summary': ai_analysis.get('summary'),
                        # Совместимость со старыми полями
                        'response_tone': ai_analysis.get('response_tone'),
                        'greeting_quality': ai_analysis.get('greeting_quality')
                    })

            logger.info(f"📊 Найдено неотвеченных диалогов: {len(unanswered)}")
            return unanswered

        except Exception as e:
            logger.error(f"❌ Ошибка сканирования: {e}", exc_info=True)
            return []

    async def scan_all_dialogs_for_analytics(self):
        """Получить прочитанные диалоги с 15:00 для аналитики"""
        try:
            me = await self.client.get_me()
            dialogs = await self.client.get_dialogs(limit=500)

            all_dialogs = []
            
            now = datetime.now(LOCAL_TZ)
            today_3pm = now.replace(hour=15, minute=0, second=0, microsecond=0)

            logger.info(f"📊 Сбор прочитанных диалогов с {today_3pm.strftime('%H:%M')}")

            for dialog in dialogs:
                if is_excluded(dialog):
                    continue

                entity = dialog.entity

                if getattr(entity, 'bot', False) or entity.id == me.id:
                    continue

                if hasattr(entity, 'broadcast') or hasattr(entity, 'megagroup'):
                    continue

                # ВСЕ диалоги (прочитанные и непрочитанные) для полной аналитики
                # Удален фильтр по unread_count - показываем ВСЕ диалоги за день

                name = dialog.name or getattr(entity, 'username', 'Без имени')

                # Получаем сообщения с 15:00
                all_messages_for_analysis = []
                try:
                    async for msg in self.client.iter_messages(entity, limit=None):
                        msg_local_time = msg.date.astimezone(LOCAL_TZ)
                        
                        # Фильтр: только сообщения с 15:00 сегодня
                        if msg_local_time < today_3pm:
                            break
                        
                        msg_sender = await msg.get_sender()
                        is_from_me = msg_sender and msg_sender.id == me.id if msg_sender else False

                        all_messages_for_analysis.append({
                            'text': msg.message or '[нет текста]',
                            'time': msg_local_time.strftime('%H:%M'),
                            'from_me': is_from_me,
                            'sender_name': 'Вы' if is_from_me else name,
                            'timestamp': msg.date.timestamp()
                        })

                    all_messages_for_analysis.reverse()
                except Exception as e:
                    logger.warning(f"Не удалось получить сообщения для {name}: {e}")
                    continue

                # Пропускаем диалоги без сообщений за период
                if not all_messages_for_analysis:
                    continue

                # Анализ времени ответа
                response_analysis = detailed_analyzer.analyze_response_times(all_messages_for_analysis)
                all_responses_analysis = detailed_analyzer.analyze_all_response_times(all_messages_for_analysis)
                manager_analysis = detailed_analyzer.analyze_manager_behavior(all_messages_for_analysis)
                
                # Google AI анализ
                ai_analysis = {}
                try:
                    ai_analysis = google_ai_analyzer.analyze_dialog_with_ai(all_messages_for_analysis)
                except Exception as e:
                    logger.warning(f"Google AI анализ не удался для {name}: {e}")

                # Формируем ссылку на чат
                chat_link = ""
                if hasattr(entity, 'username') and entity.username:
                    chat_link = f"https://t.me/{entity.username}"
                else:
                    chat_link = f"tg://openmessage?user_id={entity.id}"

                last_msg_time = all_messages_for_analysis[-1]['time'] if all_messages_for_analysis else ''
                last_msg_timestamp = all_messages_for_analysis[-1]['timestamp'] if all_messages_for_analysis else 0

                all_dialogs.append({
                    'id': entity.id,
                    'name': name,
                    'time': last_msg_time,
                    'date': now.strftime('%d.%m.%Y'),
                    'chat_link': chat_link,
                    'timestamp': last_msg_timestamp,
                    # Детальный анализ
                    'introduced': manager_analysis.get('introduced'),
                    'manager_name': manager_analysis.get('manager_name'),
                    'greeting': manager_analysis.get('used_greeting'),
                    'response_delay_minutes': response_analysis.get('response_delay_minutes'),
                    'response_delay_working_minutes': response_analysis.get('response_delay_working_minutes'),
                    'response_delay_hours': response_analysis.get('response_delay_hours'),
                    'response_quality': response_analysis.get('response_quality'),
                    'is_overtime': response_analysis.get('is_overtime'),
                    'waiting_first_response_minutes': response_analysis.get('waiting_first_response_minutes'),
                    'avg_response_time_minutes': all_responses_analysis.get('avg_response_time_minutes'),
                    'total_client_messages': all_responses_analysis.get('total_client_messages'),
                    'total_responses': all_responses_analysis.get('total_responses'),
                    'message_count': manager_analysis.get('message_count'),
                    'politeness_markers': manager_analysis.get('politeness_markers'),
                    # Google AI анализ - все расширенные поля
                    'professionalism_score': ai_analysis.get('professionalism_score'),
                    'politeness_score': ai_analysis.get('politeness_score'),
                    'clarity_score': ai_analysis.get('clarity_score'),
                    'proactivity_score': ai_analysis.get('proactivity_score'),
                    'responsiveness_score': ai_analysis.get('responsiveness_score'),
                    'empathy_score': ai_analysis.get('empathy_score'),
                    # Детали запроса и эмоций
                    'main_topic': ai_analysis.get('main_topic'),
                    'urgency_level': ai_analysis.get('urgency_level'),
                    'emotion_dynamics': ai_analysis.get('emotion_dynamics'),
                    'client_expectations': ai_analysis.get('client_expectations'),
                    # Коммуникация
                    'communication_style': ai_analysis.get('communication_style'),
                    'used_personalization': ai_analysis.get('used_personalization'),
                    'first_impression': ai_analysis.get('first_impression'),
                    # Решение проблемы
                    'resolution_status': ai_analysis.get('resolution_status'),
                    'solution_provided': ai_analysis.get('solution_provided'),
                    'next_steps_clear': ai_analysis.get('next_steps_clear'),
                    'timeline_given': ai_analysis.get('timeline_given'),
                    # Риски
                    'risk_level': ai_analysis.get('risk_level'),
                    'churn_risk_level': ai_analysis.get('churn_risk_level'),
                    'need_urgent_attention': ai_analysis.get('need_urgent_attention'),
                    'escalation_needed': ai_analysis.get('escalation_needed'),
                    # Детальная информация
                    'key_moments': ai_analysis.get('key_moments', []),
                    'critical_phrases': ai_analysis.get('critical_phrases', []),
                    'missed_opportunities': ai_analysis.get('missed_opportunities', []),
                    'priority_actions': ai_analysis.get('priority_actions', []),
                    # Рекомендации и оценки
                    'ai_suggestions': ai_analysis.get('suggestions', []),
                    'ai_key_issues': ai_analysis.get('key_issues', []),
                    'ai_strengths': ai_analysis.get('strengths', []),
                    'overall_quality': ai_analysis.get('overall_quality'),
                    'client_satisfaction_estimate': ai_analysis.get('client_satisfaction_estimate'),
                    'summary': ai_analysis.get('summary'),
                    # Совместимость со старыми полями
                    'response_tone': ai_analysis.get('response_tone'),
                    'greeting_quality': ai_analysis.get('greeting_quality'),
                    'overall_sentiment': ai_analysis.get('overall_sentiment'),
                    'client_state': ai_analysis.get('client_state'),
                    'client_emotion': '😐'
                })

            logger.info(f"📊 Собрано диалогов для аналитики: {len(all_dialogs)}")
            return all_dialogs

        except Exception as e:
            logger.error(f"❌ Ошибка сбора диалогов для аналитики: {e}", exc_info=True)
            return []

    async def scan_forever(self):
        """Бесконечное сканирование"""
        global telegram_client, unanswered_dialogs, all_dialogs_for_analytics

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

            while True:
                scan_count += 1
                logger.info(f"СКАНИРОВАНИЕ #{scan_count} - {datetime.now().strftime('%H:%M:%S')}")

                # Получаем неотвеченные диалоги
                dialogs = await self.get_unanswered_dialogs()

                # Загружаем статусы
                statuses = load_statuses()

                if dialogs:
                    # Обогащаем данные статусами
                    for dialog in dialogs:
                        dialog_id = str(dialog['id'])
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

                    # Проверяем новые диалоги для alert
                    for dialog in dialogs:
                        if dialog['status'] == 'new':
                            logger.info(f"🔔 НОВЫЙ НЕОТВЕЧЕННЫЙ: {dialog['name']}")
                            socketio.emit('new_unanswered', {'dialog': dialog})
                else:
                    # Если нет неотвеченных, очищаем список
                    unanswered_dialogs = []
                    socketio.emit('dialogs_update', {'dialogs': []})

                # АВТООЧИСТКА
                current_dialog_ids = set(str(d['id']) for d in dialogs)
                updated_statuses = {}
                cleaned_count = 0

                for dialog_id, status_data in statuses.items():
                    if dialog_id in current_dialog_ids or status_data.get('status') == 'task':
                        updated_statuses[dialog_id] = status_data
                    else:
                        cleaned_count += 1

                if cleaned_count > 0:
                    logger.info(f"🧹 Автоочистка: удалено {cleaned_count} статусов")
                    save_statuses(updated_statuses)

                # Собираем диалоги для аналитики (первый раз сразу, потом каждое 3-е сканирование)
                if scan_count == 1 or scan_count % 3 == 0:
                    logger.info("📊 Сбор диалогов для аналитики...")
                    all_dialogs = await self.scan_all_dialogs_for_analytics()
                    all_dialogs_for_analytics = all_dialogs

                # АРХИВАЦИЯ И ОЧИСТКА ДАННЫХ В 7:00 УТРА
                now = datetime.now(LOCAL_TZ)
                if now.hour == 7 and now.minute < 3:  # Окно 7:00-7:03
                    # Проверяем, архивировали ли уже сегодня
                    today_str = now.strftime('%Y-%m-%d')
                    archive_marker_file = f'.archived_{today_str}'
                    
                    if not os.path.exists(archive_marker_file):
                        logger.info("=" * 80)
                        logger.info("🕖 7:00 - АРХИВАЦИЯ И ОБНУЛЕНИЕ ДАННЫХ")
                        logger.info("=" * 80)
                        
                        # Архивируем данные за вчера
                        if all_dialogs_for_analytics:
                            archive_result = data_archiver.archive_today_data(all_dialogs_for_analytics)
                            if archive_result.get('success'):
                                logger.info(f"✅ Сохранено диалогов: {archive_result['dialogs_count']}")
                                logger.info(f"📄 JSON: {archive_result['json_filename']}")
                                logger.info(f"📊 CSV: {archive_result['csv_filename']}")
                        
                        # Очищаем данные
                        all_dialogs_for_analytics = []
                        unanswered_dialogs = []
                        
                        # Очищаем старые архивы (>30 дней)
                        data_archiver.cleanup_old_archives(keep_days=30)
                        
                        # Создаем маркер, что архивация выполнена
                        with open(archive_marker_file, 'w') as f:
                            f.write(now.isoformat())
                        
                        # Удаляем старые маркеры (вчерашние)
                        for old_marker in Path('.').glob('.archived_*'):
                            if old_marker.name != archive_marker_file:
                                old_marker.unlink()
                        
                        logger.info("🔄 Данные обнулены. Готово к новому рабочему дню!")
                        logger.info("=" * 80)

                logger.info(f"⏳ Следующее сканирование через 3 минуты...")
                await asyncio.sleep(180)

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
    """Главная страница - перенаправление на manager"""
    if not session_exists:
        return redirect('/setup')
    return redirect('/manager')


@app.route('/manager')
def manager():
    """Страница менеджера диалогов"""
    if not session_exists:
        return redirect('/setup')
    return render_template('manager.html', managers=MANAGERS)


@app.route('/analytics')
def analytics():
    """Страница аналитики"""
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
    """Получить список неотвеченных диалогов"""
    statuses = load_statuses()

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

    socketio.emit('status_changed', {
        'dialog_id': dialog_id,
        'status': status,
        'manager': manager,
        'note': note
    })

    return jsonify({'success': True})


@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Получить аналитику по диалогам"""
    # Используем данные из фонового сбора или неотвеченные диалоги как fallback
    dialogs_to_analyze = all_dialogs_for_analytics if all_dialogs_for_analytics else unanswered_dialogs
    
    daily_stats = detailed_analyzer.calculate_daily_stats(dialogs_to_analyze)

    return jsonify({
        'dialogs': dialogs_to_analyze,
        'daily_stats': daily_stats
    })


@app.route('/api/export_analytics_csv', methods=['GET'])
def export_analytics_csv():
    """Экспорт сводной аналитики в CSV для руководства"""
    dialogs_to_analyze = all_dialogs_for_analytics if all_dialogs_for_analytics else unanswered_dialogs
    daily_stats = detailed_analyzer.calculate_daily_stats(dialogs_to_analyze)
    
    # Сводная таблица
    summary = {
        'Дата отчета': datetime.now(LOCAL_TZ).strftime('%d.%m.%Y %H:%M'),
        'Всего диалогов за день': daily_stats['total_dialogs'],
        'Среднее время ответа (мин)': daily_stats['avg_response_time_minutes'],
        'Превышение SLA (>1.5ч)': f"{daily_stats['overtime_count']} ({daily_stats['overtime_percentage']}%)",
        'Менеджер представился': f"{daily_stats['introduced_percentage']}%",
        'Приветствие использовано': f"{daily_stats['greeting_percentage']}%"
    }
    
    # Детализация по диалогам
    rows = []
    for dialog in dialogs_to_analyze:
        rows.append({
            'Имя клиента': dialog.get('name', ''),
            'Время': dialog.get('time', ''),
            'Время ответа (мин)': dialog.get('response_delay_working_minutes', ''),
            'Качество': dialog.get('response_quality', ''),
            'Представился': 'Да' if dialog.get('introduced') else 'Нет',
            'Имя менеджера': dialog.get('manager_name', ''),
            'Приветствие': 'Да' if dialog.get('greeting') else 'Нет',
            'Оценка AI': dialog.get('professionalism_score', ''),
            'Тон общения': dialog.get('response_tone', ''),
            'Всего сообщений клиента': dialog.get('total_client_messages', ''),
            'Всего ответов менеджера': dialog.get('total_responses', '')
        })
    
    output = StringIO()
    
    # Записываем сводку
    output.write('СВОДКА ЗА ДЕНЬ\n')
    for key, value in summary.items():
        output.write(f'{key},{value}\n')
    output.write('\n\n')
    
    # Записываем детализацию
    if rows:
        output.write('ДЕТАЛИЗАЦИЯ ПО ДИАЛОГАМ\n')
        fieldnames = ['Имя клиента', 'Время', 'Время ответа (мин)', 'Качество', 'Представился', 
                      'Имя менеджера', 'Приветствие', 'Оценка AI', 'Тон общения', 
                      'Всего сообщений клиента', 'Всего ответов менеджера']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename=analytics_summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
    )


@app.route('/api/export_csv', methods=['GET'])
def export_csv():
    """Экспорт диалогов в CSV"""
    statuses = load_statuses()

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

    output = StringIO()
    if rows:
        fieldnames = ['Дата', 'Время', 'Имя', 'Часов без ответа', 'Сообщение', 'Статус', 'Ответственный', 'Заметка', 'Ссылка']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=dialogs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
    )


# ============================================================================
# SETUP API
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
# АРХИВЫ И СКАЧИВАНИЕ
# ============================================================================

@app.route('/archives')
def archives_page():
    """Страница со списком архивов"""
    return render_template('archives.html')


@app.route('/api/archives/list', methods=['GET'])
def api_archives_list():
    """Получить список всех архивов"""
    archives = data_archiver.get_archives_list()
    return jsonify({'archives': archives})


@app.route('/api/archives/download/<filename>')
def download_archive(filename):
    """Скачать архивный файл"""
    from flask import send_file
    
    # Проверка безопасности - только файлы из archives/
    if '..' in filename or '/' in filename:
        return jsonify({'error': 'Invalid filename'}), 400
    
    file_path = Path('archives') / filename
    
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename
    )


@app.route('/api/archives/create_now', methods=['POST'])
def create_archive_now():
    """Создать архив прямо сейчас (ручной экспорт)"""
    dialogs_data = all_dialogs_for_analytics if all_dialogs_for_analytics else unanswered_dialogs
    
    if not dialogs_data:
        return jsonify({'error': 'Нет данных для архивации'}), 400
    
    result = data_archiver.archive_today_data(dialogs_data)
    
    if result.get('success'):
        return jsonify({
            'success': True,
            'message': f"Архив создан: {result['dialogs_count']} диалогов",
            'json_filename': result['json_filename'],
            'csv_filename': result['csv_filename']
        })
    else:
        return jsonify({'error': result.get('error', 'Unknown error')}), 500


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
        scanner_thread = Thread(target=run_scanner, daemon=True)
        scanner_thread.start()
        logger.info("✅ Сканер запущен в фоновом потоке")
    else:
        logger.warning("⚠️  Сессия не найдена. Откройте /setup для настройки")

    port = int(os.getenv('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
