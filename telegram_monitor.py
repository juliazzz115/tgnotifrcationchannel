"""
Основной модуль для мониторинга Telegram канала
"""
import asyncio
import os
import logging
from datetime import datetime
from threading import Thread, Timer
from typing import Optional
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import Message
from alert_window import AlertWindow

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


class TelegramMonitor:
    """Класс для мониторинга Telegram канала и показа уведомлений"""

    def __init__(self):
        """Инициализация монитора"""
        # Получаем настройки из .env
        self.api_id = os.getenv('API_ID')
        self.api_hash = os.getenv('API_HASH')
        self.channel_id = os.getenv('CHANNEL_ID')
        self.alert_delay = int(os.getenv('ALERT_DELAY', '60'))

        # Проверка обязательных параметров
        if not self.api_id or not self.api_hash or not self.channel_id:
            raise ValueError(
                "Необходимо заполнить API_ID, API_HASH и CHANNEL_ID в файле .env"
            )

        # Преобразуем channel_id в правильный формат
        if self.channel_id.startswith('@'):
            # Если это username канала
            self.channel_entity = self.channel_id
        else:
            # Если это числовой ID
            try:
                self.channel_entity = int(self.channel_id)
            except ValueError:
                raise ValueError(
                    f"CHANNEL_ID должен быть числом или начинаться с @, получено: {self.channel_id}"
                )

        # Создаем клиент Telegram
        self.client = TelegramClient(
            'telegram_monitor_session',
            int(self.api_id),
            self.api_hash
        )

        # Хранилище для отложенных уведомлений
        self.pending_alerts: dict[int, Timer] = {}

        logger.info("TelegramMonitor инициализирован")
        logger.info(f"Канал для мониторинга: {self.channel_entity}")
        logger.info(f"Задержка уведомлений: {self.alert_delay} секунд")

    def _show_alert_window(self, message_text: str, channel_name: str):
        """
        Показать окно уведомления в отдельном потоке

        Args:
            message_text: Текст сообщения
            channel_name: Название канала
        """
        try:
            logger.info(f"Запуск окна уведомления для сообщения из {channel_name}")
            window = AlertWindow(message_text, channel_name)
            user_name, confirmed = window.show()

            if confirmed:
                logger.info(f"Уведомление подтверждено пользователем: {user_name}")
            else:
                logger.warning("Окно уведомления закрыто без подтверждения")

        except Exception as e:
            logger.error(f"Ошибка при показе окна уведомления: {e}", exc_info=True)

    def _schedule_alert(self, message: Message, channel_name: str):
        """
        Запланировать показ уведомления через заданное время

        Args:
            message: Объект сообщения Telegram
            channel_name: Название канала
        """
        message_id = message.id
        message_text = message.text or "[Без текста]"

        # Отменяем предыдущее уведомление для этого сообщения, если оно есть
        if message_id in self.pending_alerts:
            self.pending_alerts[message_id].cancel()
            logger.info(f"Отменено предыдущее уведомление для сообщения {message_id}")

        # Создаем таймер для отложенного показа уведомления
        def show_alert():
            # Удаляем из списка отложенных
            if message_id in self.pending_alerts:
                del self.pending_alerts[message_id]

            # Показываем окно в отдельном потоке
            alert_thread = Thread(
                target=self._show_alert_window,
                args=(message_text, channel_name),
                daemon=True
            )
            alert_thread.start()

        timer = Timer(self.alert_delay, show_alert)
        timer.start()
        self.pending_alerts[message_id] = timer

        logger.info(
            f"Запланировано уведомление для сообщения {message_id} "
            f"через {self.alert_delay} секунд"
        )

    async def _on_new_message(self, event: events.NewMessage.Event):
        """
        Обработчик новых сообщений

        Args:
            event: Событие нового сообщения
        """
        message: Message = event.message
        chat = await event.get_chat()
        channel_name = getattr(chat, 'title', str(self.channel_entity))

        logger.info(
            f"Получено новое сообщение в канале '{channel_name}' "
            f"(ID: {message.id}) в {datetime.now().strftime('%H:%M:%S')}"
        )

        # Планируем показ уведомления
        self._schedule_alert(message, channel_name)

    async def start(self):
        """Запустить мониторинг канала"""
        try:
            logger.info("Запуск Telegram клиента...")
            await self.client.start()

            # Получаем информацию о себе
            me = await self.client.get_me()
            logger.info(f"Авторизован как: {me.first_name} (@{me.username})")

            # Получаем информацию о канале
            try:
                channel = await self.client.get_entity(self.channel_entity)
                logger.info(f"Подключен к каналу: {channel.title} (ID: {channel.id})")
            except Exception as e:
                logger.error(f"Ошибка при получении информации о канале: {e}")
                raise

            # Регистрируем обработчик новых сообщений
            @self.client.on(events.NewMessage(chats=self.channel_entity))
            async def handler(event):
                await self._on_new_message(event)

            logger.info("✅ Мониторинг запущен! Ожидание новых сообщений...")
            logger.info(f"При получении сообщения окно появится через {self.alert_delay} секунд")

            # Запускаем бесконечный цикл обработки событий
            await self.client.run_until_disconnected()

        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки (Ctrl+C)")
        except Exception as e:
            logger.error(f"Ошибка при работе монитора: {e}", exc_info=True)
            raise
        finally:
            # Отменяем все отложенные уведомления
            for timer in self.pending_alerts.values():
                timer.cancel()
            logger.info("Все отложенные уведомления отменены")

    async def stop(self):
        """Остановить мониторинг"""
        logger.info("Остановка монитора...")
        await self.client.disconnect()
        logger.info("Монитор остановлен")


async def main():
    """Главная функция"""
    try:
        monitor = TelegramMonitor()
        await monitor.start()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Программа завершена пользователем")
        exit(0)
