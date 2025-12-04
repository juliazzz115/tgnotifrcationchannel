#!/bin/bash
# Перезапуск Telegram Desktop Alerts

PLIST_PATH="$HOME/Library/LaunchAgents/com.telegram.monitor.plist"

echo "🔄 Перезапуск Telegram Monitor..."

if [ -f "$PLIST_PATH" ]; then
    # Останавливаем
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    sleep 1

    # Запускаем
    launchctl load "$PLIST_PATH"

    echo "✅ Программа перезапущена"
    echo ""
    echo "Проверить статус:"
    echo "  ./check_status.sh"
else
    echo "❌ Файл автозапуска не найден: $PLIST_PATH"
    echo "Запустите установку:"
    echo "  ./install.sh"
fi
