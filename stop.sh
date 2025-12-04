#!/bin/bash
# Остановка Telegram Desktop Alerts

PLIST_PATH="$HOME/Library/LaunchAgents/com.telegram.monitor.plist"

echo "🛑 Остановка Telegram Monitor..."

if [ -f "$PLIST_PATH" ]; then
    launchctl unload "$PLIST_PATH"
    echo "✅ Программа остановлена"
    echo ""
    echo "Чтобы снова запустить, выполните:"
    echo "  ./restart.sh"
else
    echo "❌ Файл автозапуска не найден: $PLIST_PATH"
    echo "Возможно, программа не была установлена."
fi
