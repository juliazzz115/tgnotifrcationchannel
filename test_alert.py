"""
Тестовый скрипт для проверки окна уведомлений
Запустите когда веб-сервер работает и страница открыта в браузере
"""
import socketio
import time

# Создаем клиент для подключения к серверу
sio = socketio.Client()

# Тестовое сообщение
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

try:
    # Определяем порт (можно передать как аргумент)
    import sys
    import os
    from dotenv import load_dotenv

    load_dotenv()
    port = int(os.getenv('PORT', '5000'))

    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    server_url = f'http://localhost:{port}'

    print(f"🔍 Подключение к серверу {server_url}...")
    sio.connect(server_url)

    print("✅ Подключено!")
    print("⏰ Через 3 секунды отправлю тестовое уведомление...")
    print(f"   (откройте браузер на {server_url})")

    time.sleep(3)

    # Отправляем тестовое уведомление
    print("📤 Отправка тестового уведомления...")

    sio.emit('new_alert', {
        'message_id': 99999,
        'message_text': test_message,
        'channel_name': 'ТЕСТОВЫЙ КАНАЛ',
        'timestamp': time.strftime('%H:%M:%S'),
        'date': time.strftime('%d.%m.%Y')
    })

    print("✅ Уведомление отправлено!")
    print("💡 Теперь посмотрите на браузер - должно появиться БОЛЬШОЕ КРАСНОЕ ОКНО!")

    time.sleep(2)
    sio.disconnect()

except Exception as e:
    print(f"❌ Ошибка: {e}")
    print("\nПроверьте:")
    print("1. Запущен ли веб-сервер? (python3 web_app.py)")
    print("2. Порт правильный? (по умолчанию 5000)")
