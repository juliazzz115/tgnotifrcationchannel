"""
Анализатор настроения и качества диалогов
"""
import re
from typing import Dict, List, Optional


class SentimentAnalyzer:
    """Анализ настроения и проверка качества диалогов"""

    # Ключевые слова для определения настроения
    NEGATIVE_KEYWORDS = [
        'долго', 'медленно', 'плохо', 'ужасно', 'кошмар', 'отвратительно',
        'не отвечаете', 'игнорируете', 'не реагируете', 'безобразие',
        'разочарован', 'возмущен', 'недоволен', 'жалоба', 'претензия',
        'верните деньги', 'обман', 'мошенники', 'ужас', 'кошмар',
        'ненавижу', 'отстой', 'бред', 'фигня', 'не работает',
        'сломалось', 'бракованный', 'дефект', 'проблема', 'ошибка'
    ]

    VERY_NEGATIVE_KEYWORDS = [
        'позор', 'идиоты', 'дураки', 'тупые', 'дебилы',
        'прокуратура', 'суд', 'иск', 'роспотребнадзор'
    ]

    POSITIVE_KEYWORDS = [
        'спасибо', 'благодарю', 'отлично', 'супер', 'замечательно',
        'прекрасно', 'хорошо', 'классно', 'круто', 'здорово',
        'рад', 'доволен', 'понравилось', 'восторге', 'молодцы',
        'респект', 'браво', 'отличная работа', 'профессионально'
    ]

    URGENCY_KEYWORDS = [
        'срочно', 'быстрее', 'немедленно', 'сейчас', 'прямо сейчас',
        'как можно скорее', 'уже', 'когда', 'долго жду'
    ]

    # Имена менеджеров
    MANAGER_NAMES = {
        'владислав': ['владислав', 'влад', 'vladislav'],
        'егор': ['егор', 'egor'],
        'юлия': ['юлия', 'юля', 'julia', 'yuliya']
    }

    def analyze_sentiment(self, messages: List[Dict]) -> Dict:
        """
        Анализирует настроение диалога

        Args:
            messages: список сообщений с полями text, from_me

        Returns:
            {
                'sentiment': 'positive' | 'neutral' | 'negative' | 'very_negative',
                'sentiment_score': 0-10,
                'client_emotion': str,
                'urgency': 'low' | 'medium' | 'high',
                'issues': List[str]
            }
        """
        # Берем только сообщения от клиента
        client_messages = [msg for msg in messages if not msg.get('from_me', False)]

        if not client_messages:
            return self._default_result()

        # Объединяем весь текст от клиента
        client_text = ' '.join([msg['text'].lower() for msg in client_messages])

        # Подсчет негативных и позитивных слов
        negative_count = sum(1 for word in self.NEGATIVE_KEYWORDS if word in client_text)
        very_negative_count = sum(1 for word in self.VERY_NEGATIVE_KEYWORDS if word in client_text)
        positive_count = sum(1 for word in self.POSITIVE_KEYWORDS if word in client_text)
        urgency_count = sum(1 for word in self.URGENCY_KEYWORDS if word in client_text)

        # Определяем настроение
        if very_negative_count > 0:
            sentiment = 'very_negative'
            sentiment_score = 1
            emotion = '😡 Очень злой'
        elif negative_count >= 3:
            sentiment = 'very_negative'
            sentiment_score = 2
            emotion = '😠 Злой'
        elif negative_count >= 1:
            sentiment = 'negative'
            sentiment_score = 4
            emotion = '😞 Недовольный'
        elif positive_count >= 2:
            sentiment = 'positive'
            sentiment_score = 9
            emotion = '😊 Довольный'
        elif positive_count >= 1:
            sentiment = 'positive'
            sentiment_score = 8
            emotion = '🙂 Спокойный'
        else:
            sentiment = 'neutral'
            sentiment_score = 6
            emotion = '😐 Нейтральный'

        # Уровень срочности
        if urgency_count >= 2 or very_negative_count > 0:
            urgency = 'high'
        elif urgency_count >= 1 or negative_count >= 2:
            urgency = 'medium'
        else:
            urgency = 'low'

        # Найденные проблемы
        issues = []
        if 'долго' in client_text or 'медленно' in client_text:
            issues.append('Долгое ожидание')
        if 'не отвечаете' in client_text or 'игнорируете' in client_text:
            issues.append('Нет ответа')
        if 'не работает' in client_text or 'сломал' in client_text:
            issues.append('Технические проблемы')
        if 'деньги' in client_text and 'верн' in client_text:
            issues.append('Возврат средств')

        return {
            'sentiment': sentiment,
            'sentiment_score': sentiment_score,
            'client_emotion': emotion,
            'urgency': urgency,
            'issues': issues
        }

    def check_manager_introduction(self, messages: List[Dict]) -> Dict:
        """
        Проверяет, представился ли менеджер

        Args:
            messages: список сообщений с полями text, from_me

        Returns:
            {
                'introduced': bool,
                'manager_name': str | None,
                'greeting': bool
            }
        """
        # Берем только сообщения от менеджера
        manager_messages = [msg for msg in messages if msg.get('from_me', False)]

        if not manager_messages:
            return {'introduced': False, 'manager_name': None, 'greeting': False}

        # Объединяем текст от менеджера
        manager_text = ' '.join([msg['text'].lower() for msg in manager_messages])

        # Проверяем наличие имени
        found_name = None
        for full_name, variations in self.MANAGER_NAMES.items():
            for variant in variations:
                if variant in manager_text:
                    found_name = full_name.capitalize()
                    break
            if found_name:
                break

        # Проверяем приветствие
        greeting_words = ['здравствуйте', 'добрый день', 'добрый вечер', 'привет', 'hello']
        has_greeting = any(word in manager_text for word in greeting_words)

        return {
            'introduced': found_name is not None,
            'manager_name': found_name,
            'greeting': has_greeting
        }

    def analyze_dialog(self, messages: List[Dict], hours_waiting: float) -> Dict:
        """
        Полный анализ диалога

        Args:
            messages: список сообщений
            hours_waiting: часов ожидания ответа

        Returns:
            Полный анализ с рекомендациями
        """
        sentiment_data = self.analyze_sentiment(messages)
        introduction_data = self.check_manager_introduction(messages)

        # Определяем критичность
        is_critical = False
        warnings = []

        if sentiment_data['sentiment'] in ['negative', 'very_negative']:
            warnings.append('⚠️ Негативное настроение клиента')
            is_critical = True

        if not introduction_data['introduced']:
            warnings.append('⚠️ Менеджер не представился')

        if hours_waiting > 2:
            warnings.append(f'⚠️ Клиент ждет {hours_waiting:.1f}ч')
            is_critical = True

        if sentiment_data['urgency'] == 'high':
            warnings.append('🚨 Высокая срочность')
            is_critical = True

        # Рекомендации
        recommendations = []
        if not introduction_data['introduced']:
            recommendations.append('Представиться по имени')
        if not introduction_data['greeting']:
            recommendations.append('Начать с приветствия')
        if sentiment_data['sentiment'] in ['negative', 'very_negative']:
            recommendations.append('Принести извинения')
            recommendations.append('Предложить решение проблемы')
        if sentiment_data['urgency'] == 'high':
            recommendations.append('Ответить максимально быстро')

        return {
            **sentiment_data,
            **introduction_data,
            'is_critical': is_critical,
            'warnings': warnings,
            'recommendations': recommendations,
            'hours_waiting': hours_waiting
        }

    def _default_result(self) -> Dict:
        """Результат по умолчанию"""
        return {
            'sentiment': 'neutral',
            'sentiment_score': 6,
            'client_emotion': '😐 Нейтральный',
            'urgency': 'low',
            'issues': []
        }


# Глобальный экземпляр
analyzer = SentimentAnalyzer()
