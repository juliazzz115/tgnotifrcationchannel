"""
Расширенный анализатор для детальной аналитики
"""
from typing import Dict, List
from datetime import datetime


class DetailedAnalyzer:
    """Детальный анализ диалогов с метриками времени ответа"""

    def analyze_response_times(self, messages: List[Dict]) -> Dict:
        """
        Анализ времени ответа менеджера на первое сообщение клиента
        
        Args:
            messages: список сообщений с timestamp
            
        Returns:
            {
                'first_client_message_time': datetime,
                'first_manager_response_time': datetime,
                'response_delay_minutes': float,
                'response_quality': 'отлично' | 'хорошо' | 'приемлемо' | 'долго' | 'очень_долго',
                'is_overtime': bool (более 1.5 часов)
            }
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
                'response_quality': 'нет_ответа',
                'is_overtime': True
            }

        client_time = first_client_msg.get('timestamp')
        manager_time = first_manager_response.get('timestamp')

        if not client_time or not manager_time:
            return self._default_response_time()

        delay_seconds = manager_time - client_time
        delay_minutes = delay_seconds / 60
        delay_hours = delay_minutes / 60

        if delay_minutes <= 15:
            quality = 'отлично'
        elif delay_minutes <= 30:
            quality = 'хорошо'
        elif delay_minutes <= 60:
            quality = 'приемлемо'
        elif delay_hours <= 1.5:
            quality = 'долго'
        else:
            quality = 'очень_долго'

        is_overtime = delay_hours > 1.5

        return {
            'first_client_message_time': datetime.fromtimestamp(client_time),
            'first_manager_response_time': datetime.fromtimestamp(manager_time),
            'response_delay_minutes': round(delay_minutes, 1),
            'response_delay_hours': round(delay_hours, 2),
            'response_quality': quality,
            'is_overtime': is_overtime
        }

    def analyze_manager_behavior(self, messages: List[Dict]) -> Dict:
        """
        Анализ поведения менеджера в диалоге
        
        Returns:
            {
                'introduced': bool,
                'manager_name': str,
                'used_greeting': bool,
                'message_count': int,
                'avg_message_length': int,
                'used_emojis': bool,
                'politeness_markers': List[str]
            }
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
        
        Returns:
            {
                'total_dialogs': int,
                'avg_response_time_minutes': float,
                'overtime_count': int (>1.5ч),
                'introduced_percentage': float,
                'greeting_percentage': float,
                'quality_distribution': Dict
            }
        """
        if not all_dialogs:
            return {
                'total_dialogs': 0,
                'avg_response_time_minutes': 0,
                'overtime_count': 0,
                'introduced_percentage': 0,
                'greeting_percentage': 0,
                'quality_distribution': {}
            }

        total = len(all_dialogs)
        response_times = []
        overtime_count = 0
        introduced_count = 0
        greeting_count = 0
        quality_counts = {}

        for dialog in all_dialogs:
            if dialog.get('response_delay_minutes'):
                response_times.append(dialog['response_delay_minutes'])
            
            if dialog.get('is_overtime'):
                overtime_count += 1
            
            if dialog.get('introduced'):
                introduced_count += 1
            
            if dialog.get('greeting'):
                greeting_count += 1
            
            quality = dialog.get('response_quality', 'неизвестно')
            quality_counts[quality] = quality_counts.get(quality, 0) + 1

        avg_response = sum(response_times) / len(response_times) if response_times else 0

        return {
            'total_dialogs': total,
            'avg_response_time_minutes': round(avg_response, 1),
            'avg_response_time_hours': round(avg_response / 60, 2),
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
            'response_quality': 'неизвестно',
            'is_overtime': False
        }


detailed_analyzer = DetailedAnalyzer()
