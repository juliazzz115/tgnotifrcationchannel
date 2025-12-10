"""
Анализатор настроения и качества диалогов с улучшенным AI анализом
"""
import re
from typing import Dict, List, Optional
from datetime import datetime


class SentimentAnalyzer:
    """Анализ настроения и проверка качества диалогов"""

    # Ключевые слова для определения настроения
    NEGATIVE_KEYWORDS = [
        'долго', 'медленно', 'плохо', 'ужасно', 'кошмар', 'отвратительно',
        'не отвечаете', 'игнорируете', 'не реагируете', 'безобразие',
        'разочарован', 'возмущен', 'недоволен', 'жалоба', 'претензия',
        'верните деньги', 'обман', 'мошенники', 'ужас', 'кошмар',
        'ненавижу', 'отстой', 'бред', 'фигня', 'не работает',
        'сломалось', 'бракованный', 'дефект', 'проблема', 'ошибка',
        'устал', 'надоело', 'бесполезно', 'зачем', 'бесит'
    ]

    VERY_NEGATIVE_KEYWORDS = [
        'позор', 'идиоты', 'дураки', 'тупые', 'дебилы',
        'прокуратура', 'суд', 'иск', 'роспотребнадзор',
        'жалоба', 'юрист', 'прокурор', 'полиция'
    ]

    POSITIVE_KEYWORDS = [
        'спасибо', 'благодарю', 'отлично', 'супер', 'замечательно',
        'прекрасно', 'хорошо', 'классно', 'круто', 'здорово',
        'рад', 'доволен', 'понравилось', 'восторге', 'молодцы',
        'респект', 'браво', 'отличная работа', 'профессионально',
        'благодарность', 'восхищен', 'счастлив'
    ]

    URGENCY_KEYWORDS = [
        'срочно', 'быстрее', 'немедленно', 'сейчас', 'прямо сейчас',
        'как можно скорее', 'уже', 'когда', 'долго жду',
        'жду', 'давно', 'наконец', 'скорее', 'пора'
    ]

    # Категории проблем
    PROBLEM_CATEGORIES = {
        'response_time': ['долго', 'медленно', 'не отвечаете', 'игнорируете', 'жду', 'давно'],
        'quality': ['плохо', 'ужасно', 'не работает', 'сломалось', 'бракованный', 'дефект'],
        'service': ['безобразие', 'отвратительно', 'разочарован', 'недоволен'],
        'financial': ['деньги', 'верните', 'оплата', 'возврат', 'переплата'],
        'technical': ['ошибка', 'не работает', 'сломалось', 'баг', 'глюк'],
        'legal': ['прокуратура', 'суд', 'иск', 'роспотребнадзор', 'жалоба']
    }

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

    def detect_problem_categories(self, text: str) -> List[str]:
        """
        Определяет категории проблем в тексте

        Args:
            text: текст сообщения

        Returns:
            Список категорий проблем
        """
        text_lower = text.lower()
        found_categories = []

        category_names = {
            'response_time': '⏱️ Долгое ожидание',
            'quality': '🔧 Проблемы с качеством',
            'service': '😞 Недовольство сервисом',
            'financial': '💰 Финансовые вопросы',
            'technical': '⚙️ Технические проблемы',
            'legal': '⚖️ Правовые вопросы'
        }

        for category, keywords in self.PROBLEM_CATEGORIES.items():
            if any(keyword in text_lower for keyword in keywords):
                found_categories.append(category_names[category])

        return found_categories

    def calculate_quality_score(self, messages: List[Dict], hours_waiting: float,
                               sentiment_data: Dict, introduction_data: Dict) -> Dict:
        """
        Рассчитывает оценку качества обслуживания

        Args:
            messages: список сообщений
            hours_waiting: часов ожидания
            sentiment_data: данные анализа настроения
            introduction_data: данные о представлении менеджера

        Returns:
            Оценка качества и детали
        """
        score = 100  # Начальная оценка
        deductions = []

        # Штраф за время ожидания
        if hours_waiting > 4:
            score -= 30
            deductions.append('Очень долгое ожидание (-30)')
        elif hours_waiting > 2:
            score -= 20
            deductions.append('Долгое ожидание (-20)')
        elif hours_waiting > 1:
            score -= 10
            deductions.append('Ожидание больше часа (-10)')

        # Штраф за негативное настроение
        if sentiment_data['sentiment'] == 'very_negative':
            score -= 40
            deductions.append('Очень негативное настроение (-40)')
        elif sentiment_data['sentiment'] == 'negative':
            score -= 20
            deductions.append('Негативное настроение (-20)')

        # Штраф за отсутствие представления
        if not introduction_data['introduced']:
            score -= 15
            deductions.append('Менеджер не представился (-15)')

        # Штраф за отсутствие приветствия
        if not introduction_data['greeting']:
            score -= 10
            deductions.append('Нет приветствия (-10)')

        # Бонус за позитивное настроение
        if sentiment_data['sentiment'] == 'positive':
            score += 10
            deductions.append('Позитивное настроение (+10)')

        # Ограничиваем оценку в диапазоне 0-100
        score = max(0, min(100, score))

        # Определяем категорию качества
        if score >= 80:
            quality_level = '🟢 Отлично'
            quality_class = 'excellent'
        elif score >= 60:
            quality_level = '🟡 Хорошо'
            quality_class = 'good'
        elif score >= 40:
            quality_level = '🟠 Удовлетворительно'
            quality_class = 'fair'
        else:
            quality_level = '🔴 Критично'
            quality_class = 'critical'

        return {
            'score': score,
            'quality_level': quality_level,
            'quality_class': quality_class,
            'deductions': deductions
        }

    def analyze_dialog(self, messages: List[Dict], hours_waiting: float) -> Dict:
        """
        Полный анализ диалога с улучшенным AI

        Args:
            messages: список сообщений
            hours_waiting: часов ожидания ответа

        Returns:
            Полный анализ с рекомендациями и оценкой качества
        """
        sentiment_data = self.analyze_sentiment(messages)
        introduction_data = self.check_manager_introduction(messages)

        # Категории проблем
        client_messages = [msg for msg in messages if not msg.get('from_me', False)]
        client_text = ' '.join([msg['text'] for msg in client_messages])
        problem_categories = self.detect_problem_categories(client_text)

        # Оценка качества
        quality_data = self.calculate_quality_score(
            messages, hours_waiting, sentiment_data, introduction_data
        )

        # Определяем критичность
        is_critical = False
        warnings = []

        if sentiment_data['sentiment'] in ['negative', 'very_negative']:
            warnings.append('⚠️ Негативное настроение клиента')
            is_critical = True

        if not introduction_data['introduced']:
            warnings.append('⚠️ Менеджер не представился')

        if hours_waiting > 3:
            warnings.append(f'🚨 Клиент ждет {hours_waiting:.1f}ч')
            is_critical = True
        elif hours_waiting > 2:
            warnings.append(f'⚠️ Клиент ждет {hours_waiting:.1f}ч')

        if sentiment_data['urgency'] == 'high':
            warnings.append('🚨 Высокая срочность')
            is_critical = True

        if problem_categories:
            is_critical = True

        # Улучшенные рекомендации
        recommendations = []

        # Приоритет 1: Критичные действия
        if sentiment_data['sentiment'] == 'very_negative':
            recommendations.append('🚨 СРОЧНО: Принести искренние извинения')
            recommendations.append('🚨 СРОЧНО: Немедленно предложить решение')
            recommendations.append('🚨 Эскалировать вопрос руководству')
        elif sentiment_data['sentiment'] == 'negative':
            recommendations.append('⚠️ Принести извинения за неудобства')
            recommendations.append('⚠️ Предложить конкретное решение проблемы')

        # Приоритет 2: Улучшение коммуникации
        if not introduction_data['introduced']:
            recommendations.append('👤 Представиться по имени')
        if not introduction_data['greeting']:
            recommendations.append('👋 Начать с вежливого приветствия')

        # Приоритет 3: Время реагирования
        if hours_waiting > 3:
            recommendations.append('⚡ Ответить НЕМЕДЛЕННО')
        elif sentiment_data['urgency'] == 'high':
            recommendations.append('⚡ Ответить максимально быстро')

        # Приоритет 4: Решение конкретных проблем
        if problem_categories:
            recommendations.append(f'🔍 Уделить внимание: {", ".join(problem_categories[:2])}')

        # Приоритет 5: Поддержание качества
        if sentiment_data['sentiment'] == 'neutral':
            recommendations.append('💬 Поддержать дружелюбный тон')
        if sentiment_data['sentiment'] == 'positive':
            recommendations.append('😊 Поблагодарить клиента за позитивный отзыв')

        return {
            **sentiment_data,
            **introduction_data,
            **quality_data,
            'is_critical': is_critical,
            'warnings': warnings,
            'recommendations': recommendations,
            'problem_categories': problem_categories,
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
