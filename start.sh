#!/bin/bash
# Простой скрипт запуска Telegram Alerts

cd "$(dirname "$0")"

echo "🚀 Запуск Telegram Alerts..."
echo ""

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не найден!"
    echo "Установите: brew install python"
    exit 1
fi

# Проверка .env
if [ ! -f ".env" ]; then
    echo "⚠️  Файл .env не найден!"
    echo "Создайте .env из .env.example и заполните данные"
    exit 1
fi

# Запуск
echo "✅ Запуск сервера..."
echo "📱 Откройте в браузере: http://localhost:5000"
echo "Для остановки нажмите Ctrl+C"
echo ""

python3 web_app.py
