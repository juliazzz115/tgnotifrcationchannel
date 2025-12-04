#!/bin/bash
# Автоматический установщик Telegram Desktop Alerts для macOS

set -e  # Остановка при ошибке

echo "🚀 Установка Telegram Desktop Alerts..."
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Получаем абсолютный путь к папке проекта
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "📁 Папка проекта: $PROJECT_DIR"
echo ""

# Проверка наличия Python 3
echo "🔍 Проверка Python 3..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 не найден!${NC}"
    echo "Установите Python 3:"
    echo "  brew install python"
    exit 1
fi
PYTHON_PATH=$(which python3)
echo -e "${GREEN}✅ Python 3 найден: $PYTHON_PATH${NC}"
echo ""

# Проверка наличия pip3
echo "🔍 Проверка pip3..."
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ pip3 не найден!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ pip3 найден${NC}"
echo ""

# Установка зависимостей
echo "📦 Установка зависимостей Python..."
cd "$PROJECT_DIR"
pip3 install -r requirements.txt
echo -e "${GREEN}✅ Зависимости установлены${NC}"
echo ""

# Проверка файла .env
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}⚠️  Файл .env не найден!${NC}"
    echo "Создаю .env из .env.example..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo ""
    echo -e "${RED}❗ ВАЖНО: Отредактируйте файл .env перед запуском!${NC}"
    echo "   Откройте: $PROJECT_DIR/.env"
    echo "   Заполните: API_ID, API_HASH, CHANNEL_ID"
    echo ""

    # Открываем .env в текстовом редакторе
    if command -v open &> /dev/null; then
        echo "Открываю .env в редакторе..."
        open -e "$PROJECT_DIR/.env"
    fi
else
    echo -e "${GREEN}✅ Файл .env найден${NC}"
    echo ""
fi

# Создаем LaunchAgent для автозапуска
PLIST_NAME="com.telegram.monitor.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$PLIST_NAME"

echo "🔧 Настройка автозапуска при включении компьютера..."

# Создаем папку LaunchAgents если её нет
mkdir -p "$LAUNCH_AGENTS_DIR"

# Создаем plist файл
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.telegram.monitor</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_PATH</string>
        <string>$PROJECT_DIR/telegram_monitor.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/telegram_monitor_stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/telegram_monitor_stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

echo -e "${GREEN}✅ Файл автозапуска создан: $PLIST_PATH${NC}"
echo ""

# Загружаем LaunchAgent
echo "🚀 Активация автозапуска..."
launchctl unload "$PLIST_PATH" 2>/dev/null || true  # Выгружаем если уже загружен
launchctl load "$PLIST_PATH"
echo -e "${GREEN}✅ Автозапуск активирован!${NC}"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ УСТАНОВКА ЗАВЕРШЕНА!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Что дальше:"
echo ""
echo "1. Убедитесь, что файл .env заполнен правильно:"
echo "   Откройте: $PROJECT_DIR/.env"
echo "   Должны быть указаны: API_ID, API_HASH, CHANNEL_ID"
echo ""
echo "2. Программа УЖЕ ЗАПУЩЕНА и работает в фоне!"
echo "   Теперь она будет запускаться автоматически при каждом включении Mac."
echo ""
echo "3. Проверить статус:"
echo "   $PROJECT_DIR/check_status.sh"
echo ""
echo "4. Остановить:"
echo "   $PROJECT_DIR/stop.sh"
echo ""
echo "5. Перезапустить:"
echo "   $PROJECT_DIR/restart.sh"
echo ""
echo "📝 Логи находятся в:"
echo "   $PROJECT_DIR/telegram_monitor.log"
echo "   $PROJECT_DIR/telegram_monitor_stdout.log"
echo "   $PROJECT_DIR/telegram_monitor_stderr.log"
echo ""
echo -e "${YELLOW}⚠️  При первом запуске Telegram попросит авторизацию!${NC}"
echo "   Проверьте лог: tail -f $PROJECT_DIR/telegram_monitor_stderr.log"
echo ""
