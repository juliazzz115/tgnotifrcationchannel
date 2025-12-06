"""
Скрипт для создания новой Telegram сессии через веб-интерфейс
"""
import os
import asyncio
from flask import Flask, render_template, request, jsonify
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Глобальные переменные для процесса авторизации
temp_client = None
phone_number = None
phone_code_hash = None

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')


@app.route('/')
def index():
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
        # Создаем новый клиент
        temp_client = TelegramClient('telegram_session_NEW', int(API_ID), API_HASH)

        # Запускаем в новом event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

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
        return jsonify({'error': str(e)}), 500


@app.route('/api/verify_code', methods=['POST'])
def verify_code():
    """Проверить код и создать сессию"""
    global temp_client, phone_number, phone_code_hash

    data = request.json
    code = data.get('code')

    if not code or not temp_client:
        return jsonify({'error': 'Сначала отправьте код на телефон'}), 400

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def sign_in():
            await temp_client.sign_in(phone_number, code, phone_code_hash=phone_code_hash)
            me = await temp_client.get_me()
            await temp_client.disconnect()
            return me

        me = loop.run_until_complete(sign_in())

        # Удаляем старую сессию
        if os.path.exists('telegram_session.session'):
            os.remove('telegram_session.session')

        # Переименовываем новую сессию
        if os.path.exists('telegram_session_NEW.session'):
            os.rename('telegram_session_NEW.session', 'telegram_session.session')

        return jsonify({
            'success': True,
            'message': f'✅ Авторизация успешна! Привет, {me.first_name}!',
            'user': {
                'first_name': me.first_name,
                'username': me.username
            }
        })

    except Exception as e:
        return jsonify({'error': f'Ошибка: {str(e)}'}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
