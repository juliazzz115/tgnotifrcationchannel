#!/bin/bash
# Удаление Telegram Desktop Alerts

PLIST_PATH="$HOME/Library/LaunchAgents/com.telegram.monitor.plist"
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "🗑️  Удаление Telegram Monitor..."
echo ""

# Останавливаем и удаляем из автозапуска
if [ -f "$PLIST_PATH" ]; then
    echo "Остановка программы..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true

    echo "Удаление из автозапуска..."
    rm "$PLIST_PATH"

    echo "✅ Автозапуск отключен и удален"
else
    echo "ℹ️  Автозапуск уже был удален"
fi

echo ""
echo "📁 Файлы проекта остались в папке:"
echo "   $PROJECT_DIR"
echo ""
echo "Если хотите полностью удалить проект:"
echo "  rm -rf $PROJECT_DIR"
echo ""
echo "✅ Удаление завершено"
