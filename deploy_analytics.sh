#!/bin/bash
# Скрипт для деплоя расширенной аналитики на Railway

echo "🚀 Подготовка к деплою расширенной аналитики..."

# Удаляем тестовые файлы
rm -f test_dialogs.json generate_test_data.py

# Добавляем изменения
git add templates/
git add web_app.py
git add ANALYTICS_GUIDE.md

# Удаляем старые HTML из корня (они теперь в templates/)
git rm analytics.html manager.html setup.html 2>/dev/null || true

# Коммит
git commit -m "feat: расширенная аналитика с 4 подвкладками и 8 фильтрами

- Добавлено 4 подвкладки: Общая / По менеджерам / Временная / AI Insights
- 8 фильтров: дата, качество, менеджер, представление, решение, риск, сортировка
- 3 графика (Chart.js): распределение по часам, время ответа, качество по дням
- Экспорт в CSV
- Исправлена структура данных в JavaScript
- HTML файлы перемещены в templates/
- Добавлено руководство ANALYTICS_GUIDE.md"

# Пуш на Railway
git push origin main

echo "✅ Деплой завершен! Ждите обновления на Railway (~2-3 минуты)"
