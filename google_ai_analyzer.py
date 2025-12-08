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
        self.endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"

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
        
        prompt = f"""Проанализируй диалог между менеджером и клиентом. Ответь в формате JSON:

Диалог:
{conversation}

Необходимо определить:
1. Представился ли менеджер по имени? (true/false)
2. Какое имя менеджера? (или null)
3. Качество приветствия: "отличное", "хорошее", "слабое", "отсутствует"
4. Тон ответа менеджера: "дружелюбный", "нейтральный", "формальный", "холодный"
5. Оценка профессионализма от 1 до 10
6. Список рекомендаций для улучшения
7. Ключевые проблемы в диалоге

Формат ответа (только JSON, без дополнительного текста):
{{
  "manager_introduced": true/false,
  "manager_name": "имя или null",
  "greeting_quality": "отличное/хорошее/слабое/отсутствует",
  "response_tone": "дружелюбный/нейтральный/формальный/холодный",
  "professionalism_score": 1-10,
  "suggestions": ["совет 1", "совет 2"],
  "key_issues": ["проблема 1", "проблема 2"]
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
        
        return {
            'manager_introduced': introduction['introduced'],
            'manager_name': introduction['manager_name'],
            'greeting_quality': 'хорошее' if has_greeting else 'отсутствует',
            'response_tone': 'нейтральный',
            'professionalism_score': 7 if introduction['introduced'] else 5,
            'suggestions': ['Использовать более персонализированный подход'],
            'key_issues': []
        }


google_ai_analyzer = GoogleAIAnalyzer()
