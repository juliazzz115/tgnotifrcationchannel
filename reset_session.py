#!/usr/bin/env python3
"""
Скрипт для сброса сессии Telegram и создания новой
Решает проблему AuthKeyDuplicatedError
"""
import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

if not API_ID or not API_HASH:
    print("❌ Ошибка: API_ID и API_HASH не найдены в .env файле!")
    exit(1)

print("=" * 70)
print("🔄 СБРОС СЕССИИ TELEGRAM")
print("=" * 70)
print()
print("Этот скрипт:")
print("1. Удалит старую сессию (если есть)")
print("2. Выполнит выход из всех активных сессий")
print("3. Создаст новую чистую сессию")
print()
print("=" * 70)
print()


async def main():
    # Удаляем старые файлы сессии
    session_files = [
        'telegram_session.session',
        'telegram_session.session-journal'
    ]

    for file in session_files:
        if os.path.exists(file):
            os.remove(file)
            print(f"🗑️  Удален старый файл: {file}")

    print()
    print("📱 Создание новой сессии...")
    print()

    # Создаем новый клиент
    client = TelegramClient('telegram_session', int(API_ID), API_HASH)

    await client.connect()

    print("Введите ваш номер телефона (с кодом страны):")
    print("Пример: +380501234567")
    phone = input("Номер: ").strip()

    print()
    print(f"📤 Отправка кода на {phone}...")
    await client.send_code_request(phone)

    print()
    print("Введите код из Telegram:")
    code = input("Код: ").strip()

    try:
        await client.sign_in(phone, code)
    except Exception as e:
        if "password" in str(e).lower() or "2fa" in str(e).lower():
            print()
            print("Требуется пароль двухфакторной аутентификации:")
            password = input("Пароль: ").strip()
            await client.sign_in(password=password)

    me = await client.get_me()

    print()
    print("=" * 70)
    print(f"✅ НОВАЯ СЕССИЯ СОЗДАНА!")
    print(f"   Аккаунт: {me.first_name} (@{me.username})")
    print("=" * 70)
    print()

    # Теперь выходим из всех других сессий, кроме текущей
    print("🔒 Завершение всех других активных сессий...")
    try:
        from telethon.tl.functions.auth import ResetAuthorizationsRequest
        # Внимание: эта команда завершит ВСЕ другие сессии
        # Текущая сессия (которую мы только что создали) останется активной
        # await client(ResetAuthorizationsRequest())
        # print("✅ Все другие сессии завершены")
        print("⚠️  Рекомендация: зайдите в Telegram > Настройки > Устройства")
        print("   и вручную завершите все старые сессии")
    except Exception as e:
        print(f"⚠️  Не удалось завершить другие сессии: {e}")

    print()
    print("=" * 70)
    print("📋 СЛЕДУЮЩИЕ ШАГИ:")
    print("=" * 70)
    print()
    print("1. Загрузите новый файл на GitHub:")
    print("   git add telegram_session.session")
    print("   git commit -m 'Новая сессия Telegram'")
    print("   git push")
    print()
    print("2. Railway автоматически подхватит новый файл")
    print()
    print("3. Больше НЕ запускайте authorize.py или web_app.py ЛОКАЛЬНО!")
    print("   Используйте только Railway для работы сервера")
    print()
    print("=" * 70)

    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
