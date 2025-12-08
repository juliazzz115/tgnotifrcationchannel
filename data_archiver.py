"""
Модуль архивации данных по дням
Сохраняет аналитику в JSON и Excel для скачивания
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path
import pytz

logger = logging.getLogger(__name__)

LOCAL_TZ = pytz.timezone('Europe/Warsaw')
ARCHIVE_DIR = Path('archives')


class DataArchiver:
    """Архивация данных аналитики по дням"""
    
    def __init__(self):
        # Создать папку archives если не существует
        ARCHIVE_DIR.mkdir(exist_ok=True)
        logger.info(f"📁 Архивная папка: {ARCHIVE_DIR.absolute()}")
    
    def archive_today_data(self, dialogs_data: list) -> dict:
        """
        Сохранить данные за сегодня в архив
        
        Args:
            dialogs_data: список диалогов с аналитикой
            
        Returns:
            {'success': bool, 'json_path': str, 'csv_path': str, 'date': str}
        """
        try:
            now = datetime.now(LOCAL_TZ)
            date_str = now.strftime('%Y-%m-%d')
            time_str = now.strftime('%H-%M-%S')
            
            # JSON файл
            json_filename = f'analytics_{date_str}_{time_str}.json'
            json_path = ARCHIVE_DIR / json_filename
            
            archive_data = {
                'date': date_str,
                'archived_at': now.isoformat(),
                'total_dialogs': len(dialogs_data),
                'dialogs': dialogs_data
            }
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(archive_data, f, ensure_ascii=False, indent=2)
            
            # CSV файл (упрощенная версия для Excel)
            csv_filename = f'analytics_{date_str}_{time_str}.csv'
            csv_path = ARCHIVE_DIR / csv_filename
            
            self._save_csv(dialogs_data, csv_path)
            
            logger.info(f"✅ Данные за {date_str} сохранены в архив")
            logger.info(f"   JSON: {json_filename}")
            logger.info(f"   CSV: {csv_filename}")
            
            return {
                'success': True,
                'json_path': str(json_path),
                'csv_path': str(csv_path),
                'json_filename': json_filename,
                'csv_filename': csv_filename,
                'date': date_str,
                'dialogs_count': len(dialogs_data)
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка архивации: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def _save_csv(self, dialogs_data: list, csv_path: Path):
        """Сохранить данные в CSV"""
        import csv
        
        if not dialogs_data:
            return
        
        # Заголовки для CSV
        headers = [
            'Имя клиента',
            'Время',
            'Дата',
            'Представился',
            'Имя менеджера',
            'Приветствие',
            'Время ответа (мин)',
            'Профессионализм (1-10)',
            'Вежливость (1-10)',
            'Ясность (1-10)',
            'Проактивность (1-10)',
            'Скорость (1-10)',
            'Эмпатия (1-10)',
            'Тема запроса',
            'Срочность',
            'Настроение клиента',
            'Статус решения',
            'Уровень риска',
            'Риск ухода',
            'Резюме'
        ]
        
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            for d in dialogs_data:
                writer.writerow({
                    'Имя клиента': d.get('name', ''),
                    'Время': d.get('time', ''),
                    'Дата': d.get('date', ''),
                    'Представился': 'Да' if d.get('introduced') else 'Нет',
                    'Имя менеджера': d.get('manager_name', ''),
                    'Приветствие': 'Да' if d.get('greeting') else 'Нет',
                    'Время ответа (мин)': d.get('avg_response_time_minutes', ''),
                    'Профессионализм (1-10)': d.get('professionalism_score', ''),
                    'Вежливость (1-10)': d.get('politeness_score', ''),
                    'Ясность (1-10)': d.get('clarity_score', ''),
                    'Проактивность (1-10)': d.get('proactivity_score', ''),
                    'Скорость (1-10)': d.get('responsiveness_score', ''),
                    'Эмпатия (1-10)': d.get('empathy_score', ''),
                    'Тема запроса': d.get('main_topic', ''),
                    'Срочность': d.get('urgency_level', ''),
                    'Настроение клиента': d.get('overall_sentiment', ''),
                    'Статус решения': d.get('resolution_status', ''),
                    'Уровень риска': d.get('risk_level', ''),
                    'Риск ухода': d.get('churn_risk_level', ''),
                    'Резюме': d.get('summary', '')
                })
    
    def get_archives_list(self) -> list:
        """Получить список всех архивов"""
        try:
            archives = []
            
            # Группируем файлы по датам
            json_files = sorted(ARCHIVE_DIR.glob('analytics_*.json'), reverse=True)
            
            for json_file in json_files:
                # Извлекаем дату из имени файла
                parts = json_file.stem.split('_')
                if len(parts) >= 2:
                    date_str = parts[1]  # YYYY-MM-DD
                    
                    # Ищем соответствующий CSV
                    csv_file = json_file.with_suffix('.csv')
                    
                    # Читаем количество диалогов из JSON
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            dialogs_count = data.get('total_dialogs', 0)
                    except:
                        dialogs_count = 0
                    
                    archives.append({
                        'date': date_str,
                        'json_file': json_file.name,
                        'csv_file': csv_file.name if csv_file.exists() else None,
                        'json_path': str(json_file),
                        'csv_path': str(csv_file) if csv_file.exists() else None,
                        'json_size': self._format_file_size(json_file.stat().st_size),
                        'csv_size': self._format_file_size(csv_file.stat().st_size) if csv_file.exists() else '',
                        'dialogs_count': dialogs_count
                    })
            
            return archives
            
        except Exception as e:
            logger.error(f"Ошибка получения списка архивов: {e}")
            return []
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Форматировать размер файла"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    
    def cleanup_old_archives(self, keep_days: int = 30):
        """Удалить архивы старше N дней"""
        try:
            from datetime import timedelta
            
            cutoff_date = datetime.now(LOCAL_TZ) - timedelta(days=keep_days)
            deleted_count = 0
            
            for file in ARCHIVE_DIR.glob('analytics_*.*'):
                # Извлекаем дату из имени файла
                parts = file.stem.split('_')
                if len(parts) >= 2:
                    try:
                        file_date = datetime.strptime(parts[1], '%Y-%m-%d')
                        file_date = LOCAL_TZ.localize(file_date)
                        
                        if file_date < cutoff_date:
                            file.unlink()
                            deleted_count += 1
                            logger.info(f"🗑️  Удален старый архив: {file.name}")
                    except:
                        pass
            
            if deleted_count > 0:
                logger.info(f"✅ Удалено старых архивов: {deleted_count}")
            
        except Exception as e:
            logger.error(f"Ошибка очистки архивов: {e}")


# Singleton
data_archiver = DataArchiver()
