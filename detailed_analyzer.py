"""
Расширенный анализатор для детальной аналитики с учетом рабочего времени
"""
from typing import Dict, List
from datetime import datetime, time
import pytz


class DetailedAnalyzer:
    """Детальный анализ диалогов с метриками времени ответа"""

    def __init__(self):
        self.work_start = time(8, 0)
        self.work_end = time(16, 0)
        self.timezone = pytz.timezone('Europe/Warsaw')

    def _calculate_working_hours_delay(self, start_timestamp: float, end_timestamp: float) -> float:
        """
        Рассчитать задержку только в рабочее время (8:00-16:00)
        
        Returns:
            Задержка в минутах (только рабочее время)
        """
        from datetime import datetime, timedelta
        
        start_dt = datetime.fromtimestamp(start_timestamp, tz=self.timezone)
        end_dt = datetime.fromtimestamp(end_timestamp, tz=self.timezone)
        
        total_minutes = 0
        current_dt = start_dt
        
        while current_dt < end_dt:
            current_time = current_dt.time()
            
            # Если текущее время в рабочем диапазоне
            if self.work_start <= current_time < self.work_end:
                total_minutes += 1
            
            # Переходим к следующей минуте
            current_dt += timedelta(minutes=1)
        
        return total_minutes

    def analyze_response_times(self, messages: List[Dict]) -> Dict:
        """
        Анализ времени ответа менеджера на первое сообщение клиента
        Учитывает только рабочее время 8:00-16:00
        """
        if not messages:
            return self._default_response_time()

        first_client_msg = None
        first_manager_response = None

        for msg in messages:
            if not msg.get('from_me') and not first_client_msg:
                first_client_msg = msg
            elif msg.get('from_me') and first_client_msg and not first_manager_response:
                first_manager_response = msg
                break

        if not first_client_msg or not first_manager_response:
            return {
                'first_client_message_time': None,
                'first_manager_response_time': None,
                'response_delay_minutes': None,
                'response_delay_working_minutes': None,
                'response_quality': 'нет_ответа',
                'is_overtime': True,
                'waiting_first_response_minutes': None
            }

        client_time = first_client_msg.get('timestamp')
        manager_time = first_manager_response.get('timestamp')

        if not client_time or not manager_time:
            return self._default_response_time()

        delay_working_minutes = self._calculate_working_hours_delay(client_time, manager_time)
        delay_minutes = (manager_time - client_time) / 60
        delay_hours = delay_working_minutes / 60

        if delay_working_minutes <= 15:
            quality = 'отлично'
        elif delay_working_minutes <= 30:
            quality = 'хорошо'
        elif delay_working_minutes <= 60:
            quality = 'приемлемо'
        elif delay_hours <= 1.5:
            quality = 'долго'
        else:
            quality = 'очень_долго'

        is_overtime = delay_hours > 1.5

        return {
            'first_client_message_time': datetime.fromtimestamp(client_time, tz=self.timezone),
            'first_manager_response_time': datetime.fromtimestamp(manager_time, tz=self.timezone),
            'response_delay_minutes': round(delay_minutes, 1),
            'response_delay_working_minutes': round(delay_working_minutes, 1),
            'response_delay_hours': round(delay_hours, 2),
            'response_quality': quality,
            'is_overtime': is_overtime,
            'waiting_first_response_minutes': round(delay_working_minutes, 1)
        }

    def analyze_all_response_times(self, messages: List[Dict]) -> Dict:
        """
        Анализ среднего времени ответа на ВСЕ сообщения клиента в диалоге
        Считает только в рабочее время 8:00-16:00
        """
        if not messages:
            return {
                'avg_response_time_minutes': None,
                'total_client_messages': 0,
                'total_responses': 0
            }

        response_times = []
        
        for i, msg in enumerate(messages):
            if msg.get('from_me'):
                continue
            
            for j in range(i + 1, len(messages)):
                if messages[j].get('from_me'):
                    client_timestamp = msg.get('timestamp')
                    manager_timestamp = messages[j].get('timestamp')
                    
                    if client_timestamp and manager_timestamp:
                        delay = self._calculate_working_hours_delay(client_timestamp, manager_timestamp)
                        response_times.append(delay)
                    break

        if not response_times:
            return {
                'avg_response_time_minutes': None,
                'total_client_messages': len([m for m in messages if not m.get('from_me')]),
                'total_responses': 0
            }

        avg_time = sum(response_times) / len(response_times)

        return {
            'avg_response_time_minutes': round(avg_time, 1),
            'total_client_messages': len([m for m in messages if not m.get('from_me')]),
            'total_responses': len(response_times)
        }

    def analyze_manager_behavior(self, messages: List[Dict]) -> Dict:
        """
        Анализ поведения менеджера в диалоге
        """
        manager_messages = [m for m in messages if m.get('from_me')]
        
        if not manager_messages:
            return {
                'introduced': False,
                'manager_name': None,
                'used_greeting': False,
                'message_count': 0,
                'avg_message_length': 0,
                'used_emojis': False,
                'politeness_markers': []
            }

        all_text = ' '.join([m['text'].lower() for m in manager_messages])
        
        manager_names = {
            'владислав': ['владислав', 'влад', 'vladislav'],
            'егор': ['егор', 'egor'],
            'юлия': ['юлия', 'юля', 'julia']
        }
        
        found_name = None
        for full_name, variations in manager_names.items():
            if any(var in all_text for var in variations):
                found_name = full_name.capitalize()
                break

        greeting_words = ['здравствуйте', 'добрый день', 'добрый вечер', 'привет', 'hello', 'hi']
        used_greeting = any(word in all_text for word in greeting_words)

        avg_length = sum(len(m['text']) for m in manager_messages) / len(manager_messages)

        has_emojis = any(
            char in m['text'] 
            for m in manager_messages 
            for char in '😊🙂😀👍✅💪❤️🎉'
        )

        politeness = []
        if 'спасибо' in all_text or 'благодарю' in all_text:
            politeness.append('благодарность')
        if 'пожалуйста' in all_text:
            politeness.append('вежливость')
        if 'извините' in all_text or 'приносим извинения' in all_text:
            politeness.append('извинения')

        return {
            'introduced': found_name is not None,
            'manager_name': found_name,
            'used_greeting': used_greeting,
            'message_count': len(manager_messages),
            'avg_message_length': round(avg_length),
            'used_emojis': has_emojis,
            'politeness_markers': politeness
        }

    def calculate_daily_stats(self, all_dialogs: List[Dict]) -> Dict:
        """
        Статистика за день
        """
        if not all_dialogs:
            return {
                'total_dialogs': 0,
                'avg_response_time_minutes': 0,
                'avg_first_response_minutes': 0,
                'avg_all_responses_minutes': 0,
                'overtime_count': 0,
                'introduced_percentage': 0,
                'greeting_percentage': 0,
                'quality_distribution': {}
            }

        total = len(all_dialogs)
        first_response_times = []
        all_response_times = []
        overtime_count = 0
        introduced_count = 0
        greeting_count = 0
        quality_counts = {}

        for dialog in all_dialogs:
            if dialog.get('response_delay_working_minutes'):
                first_response_times.append(dialog['response_delay_working_minutes'])
            
            if dialog.get('avg_response_time_minutes'):
                all_response_times.append(dialog['avg_response_time_minutes'])
            
            if dialog.get('is_overtime'):
                overtime_count += 1
            
            if dialog.get('introduced'):
                introduced_count += 1
            
            if dialog.get('greeting'):
                greeting_count += 1
            
            quality = dialog.get('response_quality', 'неизвестно')
            quality_counts[quality] = quality_counts.get(quality, 0) + 1

        avg_first = sum(first_response_times) / len(first_response_times) if first_response_times else 0
        avg_all = sum(all_response_times) / len(all_response_times) if all_response_times else 0

        return {
            'total_dialogs': total,
            'avg_response_time_minutes': round(avg_first, 1),
            'avg_response_time_hours': round(avg_first / 60, 2),
            'avg_first_response_minutes': round(avg_first, 1),
            'avg_all_responses_minutes': round(avg_all, 1),
            'overtime_count': overtime_count,
            'overtime_percentage': round(overtime_count / total * 100, 1) if total > 0 else 0,
            'introduced_percentage': round(introduced_count / total * 100, 1) if total > 0 else 0,
            'greeting_percentage': round(greeting_count / total * 100, 1) if total > 0 else 0,
            'quality_distribution': quality_counts
        }

    def _default_response_time(self):
        return {
            'first_client_message_time': None,
            'first_manager_response_time': None,
            'response_delay_minutes': None,
            'response_delay_working_minutes': None,
            'response_quality': 'неизвестно',
            'is_overtime': False,
            'waiting_first_response_minutes': None
        }


detailed_analyzer = DetailedAnalyzer()
