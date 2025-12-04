#!/bin/bash
# Проверка статуса Telegram Desktop Alerts

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_NAME="com.telegram.monitor"

echo "🔍 Проверка статуса Telegram Monitor..."
echo ""

# Проверяем, запущен ли процесс
if launchctl list | grep -q "$PLIST_NAME"; then
    echo "✅ Программа ЗАПУЩЕНА и работает"
    echo ""

    # Показываем PID
    PID=$(launchctl list | grep "$PLIST_NAME" | awk '{print $1}')
    if [ "$PID" != "-" ]; then
        echo "📊 Process ID: $PID"
    fi
else
    echo "❌ Программа НЕ ЗАПУЩЕНА"
    echo ""
    echo "Запустить:"
    echo "  ./restart.sh"
fi

echo ""
echo "📝 Последние строки из лога:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "$PROJECT_DIR/telegram_monitor.log" ]; then
    tail -n 10 "$PROJECT_DIR/telegram_monitor.log"
else
    echo "Лог-файл пока не создан"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📁 Лог-файлы:"
echo "   $PROJECT_DIR/telegram_monitor.log"
echo "   $PROJECT_DIR/telegram_monitor_stdout.log"
echo "   $PROJECT_DIR/telegram_monitor_stderr.log"
echo ""
echo "Смотреть лог в реальном времени:"
echo "  tail -f $PROJECT_DIR/telegram_monitor.log"
