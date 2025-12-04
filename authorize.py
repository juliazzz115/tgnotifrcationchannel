#!/usr/bin/env python3
"""
Простой скрипт для авторизации в Telegram
Создает файл telegram_session.session который потом загружается на Railway
"""
import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient

# Загружаем переменные
load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

if not API_ID or not API_HASH:
    print("❌ Ошибка: API_ID и API_HASH не найдены в .env файле!")
    print("Создайте файл .env и заполните его:")
    print("API_ID=ваш_api_id")
    print("API_HASH=ваш_api_hash")
    exit(1)

print("=" * 60)
print("🔐 АВТОРИЗАЦИЯ В TELEGRAM")
print("=" * 60)
print()
print("Этот скрипт создаст файл telegram_session.session")
print("После авторизации загрузите его на GitHub:")
print("  git add telegram_session.session")
print("  git commit -m 'Session file'")
print("  git push")
print()
print("=" * 60)
print()


async def main():
    # Создаем клиент
    client = TelegramClient('telegram_session', int(API_ID), API_HASH)

    print("📱 Подключение к Telegram...")
    await client.connect()

    # Проверяем авторизацию
    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"✅ Вы уже авторизованы как: {me.first_name} (@{me.username})")
        print(f"✅ Файл telegram_session.session уже существует!")
        print()
        print("Загрузите его на GitHub:")
        print("  git add telegram_session.session")
        print("  git commit -m 'Session file'")
        print("  git push")
    else:
        print()
        print("Введите ваш номер телефона (с кодом страны):")
        print("Пример: +380501234567")
        phone = input("Номер: ").strip()

        print()
        print(f"📤 Отправка кода на {phone}...")
        await client.send_code_request(phone)

        print()
        print("Введите код, который пришел в Telegram:")
        code = input("Код: ").strip()

        try:
            await client.sign_in(phone, code)
            me = await client.get_me()

            print()
            print("=" * 60)
            print(f"✅ УСПЕХ! Авторизован как: {me.first_name} (@{me.username})")
            print("=" * 60)
            print()
            print("Файл telegram_session.session создан!")
            print()
            print("Загрузите его на GitHub:")
            print("  git add telegram_session.session")
            print("  git commit -m 'Telegram session'")
            print("  git push")
            print()
            print("Railway автоматически подхватит файл!")

        except Exception as e:
            print(f"❌ Ошибка авторизации: {e}")
            if "password" in str(e).lower() or "2fa" in str(e).lower():
                print()
                print("У вас включена двухфакторная аутентификация.")
                print("Введите пароль:")
                password = input("Пароль: ").strip()
                await client.sign_in(password=password)
                me = await client.get_me()
                print(f"✅ Авторизован: {me.first_name} (@{me.username})")

    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
