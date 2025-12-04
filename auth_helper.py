"""
Вспомогательный скрипт для авторизации в Telegram через веб-интерфейс
"""
import os
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

# Глобальные переменные для хранения состояния
auth_client = None
phone_code_hash = None


async def start_auth(api_id, api_hash):
    """Начать процесс авторизации"""
    global auth_client

    auth_client = TelegramClient('telegram_session', int(api_id), api_hash)
    await auth_client.connect()

    return auth_client.is_user_authorized()


async def send_code(phone_number):
    """Отправить код на телефон"""
    global auth_client, phone_code_hash

    if not auth_client:
        raise Exception("Клиент не инициализирован")

    result = await auth_client.send_code_request(phone_number)
    phone_code_hash = result.phone_code_hash

    return True


async def verify_code(phone_number, code):
    """Проверить код и завершить авторизацию"""
    global auth_client, phone_code_hash

    if not auth_client or not phone_code_hash:
        raise Exception("Сначала отправьте код")

    try:
        await auth_client.sign_in(phone_number, code, phone_code_hash=phone_code_hash)

        # Проверяем авторизацию
        if await auth_client.is_user_authorized():
            me = await auth_client.get_me()
            await auth_client.disconnect()
            return True, f"Успешно! Авторизован как: {me.first_name}"
        else:
            return False, "Не удалось авторизоваться"

    except Exception as e:
        return False, str(e)


async def check_auth(api_id, api_hash):
    """Проверить, есть ли уже авторизация"""
    client = TelegramClient('telegram_session', int(api_id), api_hash)
    await client.connect()

    is_auth = await client.is_user_authorized()

    if is_auth:
        me = await client.get_me()
        name = f"{me.first_name} (@{me.username})"
    else:
        name = None

    await client.disconnect()

    return is_auth, name
