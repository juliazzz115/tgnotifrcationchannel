"""
Расширенный анализатор с использованием Google AI API
"""
import os
import requests
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class GoogleAIAnalyzer:
    """Анализатор диалогов с использованием Google AI"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('GOOGLE_AI_KEY')
        self.endpoint = "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent"

    def analyze_dialog_with_ai(self, messages: List[Dict]) -> Dict:
        """
        Глубокий анализ диалога с помощью Google AI
        
        Args:
            messages: список сообщений с полями text, from_me, sender_name
            
        Returns:
            {
                'manager_introduced': bool,
                'manager_name': str,
                'greeting_quality': str,
                'response_tone': str,
                'professionalism_score': int,
                'suggestions': List[str],
                'key_issues': List[str]
            }
        """
        if not self.api_key:
            logger.warning("Google AI API key не установлен")
            return self._fallback_analysis(messages)

        conversation = self._format_conversation(messages)
        
        prompt = f"""Ты опытный тренер по клиентскому сервису. Проанализируй диалог между менеджером и клиентом ОБЪЕКТИВНО.

Диалог:
{conversation}

КРИТЕРИИ ОЦЕНКИ ПРОФЕССИОНАЛИЗМА (1-10):

⭐ 9-10 баллов (Отлично):
- Менеджер представился по имени
- Есть теплое приветствие
- Быстрые и полные ответы на все вопросы
- Проявляет эмпатию и понимание
- Предлагает конкретные решения
- Грамотная речь

⭐ 7-8 баллов (Хорошо):
- Представился или есть приветствие
- Дает развернутые ответы
- Вежливый тон
- Отвечает на вопросы клиента

⭐ 5-6 баллов (Средне):
- Базовая вежливость
- Отвечает, но не всегда полно
- Нет представления или приветствия

⭐ 3-4 балла (Плохо):
- Короткие формальные ответы
- Нет приветствия и представления
- Игнорирует некоторые вопросы клиента

⭐ 1-2 балла (Очень плохо):
- Грубость или холодность
- Не отвечает на вопросы
- Отсутствие базовой вежливости

АНАЛИЗИРУЙ:
1. Представился ли менеджер? (true/false) Какое имя?
2. Качество приветствия: отличное/хорошее/слабое/отсутствует
3. Тон общения: дружелюбный/нейтральный/формальный/холодный
4. Оценка профессионализма (1-10) - СТРОГО по критериям выше
5. Конкретные рекомендации (3-5 штук) с примерами фраз
6. Ключевые проблемы диалога
7. Сильные стороны менеджера

ВАЖНО: Будь объективным! Если менеджер хорошо работает - ставь 8-10. Если плохо - 1-4.

Формат ответа (ТОЛЬКО JSON):
{{
  "manager_introduced": true/false,
  "manager_name": "имя или null",
  "greeting_quality": "отличное/хорошее/слабое/отсутствует",
  "response_tone": "дружелюбный/нейтральный/формальный/холодный",
  "professionalism_score": 1-10,
  "suggestions": [
    "Конкретная рекомендация 1 с примерами фраз",
    "Конкретная рекомендация 2 с примерами фраз",
    "Конкретная рекомендация 3 с примерами фраз"
  ],
  "key_issues": ["проблема 1", "проблема 2"],
  "strengths": ["сильная сторона 1", "сильная сторона 2"]
}}"""

        try:
            response = requests.post(
                f"{self.endpoint}?key={self.api_key}",
                json={
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 1024
                    }
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                text = data['candidates'][0]['content']['parts'][0]['text']
                
                import json
                text = text.strip()
                if text.startswith('```json'):
                    text = text[7:]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()
                
                result = json.loads(text)
                logger.info(f"✅ Google AI анализ выполнен успешно")
                return result
            else:
                logger.error(f"Google AI API error: {response.status_code}")
                return self._fallback_analysis(messages)

        except Exception as e:
            logger.error(f"Ошибка Google AI анализа: {e}")
            return self._fallback_analysis(messages)

    def _format_conversation(self, messages: List[Dict]) -> str:
        """Форматирование диалога для AI"""
        lines = []
        for msg in messages:
            sender = "Менеджер" if msg.get('from_me') else "Клиент"
            lines.append(f"{sender}: {msg['text']}")
        return "\n".join(lines)

    def _fallback_analysis(self, messages: List[Dict]) -> Dict:
        """Простой анализ если AI недоступен"""
        from sentiment_analyzer import analyzer
        
        introduction = analyzer.check_manager_introduction(messages)
        
        manager_messages = [m for m in messages if m.get('from_me')]
        has_greeting = any(
            word in m['text'].lower() 
            for m in manager_messages 
            for word in ['здравствуйте', 'добрый', 'привет', 'hello']
        )
        
        suggestions = []
        key_issues = []
        strengths = []
        
        score = 5
        
        if introduction['introduced']:
            score += 2
            strengths.append("Менеджер представился по имени")
        else:
            suggestions.append("Всегда представляйтесь клиенту по имени в начале диалога")
            key_issues.append("Менеджер не представился")
            score -= 1
        
        if has_greeting:
            score += 1
            strengths.append("Использовано приветствие")
        else:
            suggestions.append("Начинайте диалог с приветствия (Здравствуйте, Добрый день)")
            key_issues.append("Отсутствует приветствие")
            score -= 1
        
        if len(manager_messages) > 0:
            avg_length = sum(len(m['text']) for m in manager_messages) / len(manager_messages)
            if avg_length < 20:
                suggestions.append("Давайте более развернутые ответы клиенту (минимум 2-3 предложения)")
                key_issues.append("Слишком короткие ответы")
                score -= 1
            elif avg_length > 50:
                score += 1
                strengths.append("Развернутые ответы")
        
        if len(manager_messages) >= 2:
            score += 1
            strengths.append("Активное участие в диалоге")
        
        score = max(1, min(10, score))
        
        if not suggestions:
            suggestions.append("Продолжайте работать в том же духе")
        
        return {
            'manager_introduced': introduction['introduced'],
            'manager_name': introduction['manager_name'],
            'greeting_quality': 'хорошее' if has_greeting else 'отсутствует',
            'response_tone': 'нейтральный',
            'professionalism_score': score,
            'suggestions': suggestions,
            'key_issues': key_issues,
            'strengths': strengths
        }


google_ai_analyzer = GoogleAIAnalyzer()
