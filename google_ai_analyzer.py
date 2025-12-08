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
        self.endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    def analyze_dialog_with_ai(self, messages: List[Dict]) -> Dict:
        """
        Глубокий анализ диалога с помощью Google AI
        
        Args:
            messages: список сообщений с полями text, from_me, sender_name, timestamp
            
        Returns:
            Детальный анализ качества сопровождения клиента
        """
        if not self.api_key:
            logger.warning("Google AI API key не установлен")
            return self._fallback_analysis(messages)

        # Подготовка диалога
        dialog_json = []
        for msg in messages:
            dialog_json.append({
                "role": "manager" if msg.get('from_me') else "client",
                "sender": msg.get('sender_name', 'unknown'),
                "time": msg.get('time', ''),
                "text": msg.get('text', '')
            })
        
        # Вычисляем время с последнего сообщения клиента
        hours_since = 0
        for msg in reversed(messages):
            if not msg.get('from_me'):
                if msg.get('timestamp'):
                    import time
                    hours_since = (time.time() - msg['timestamp']) / 3600
                break
        
        input_data = {
            "dialog": dialog_json,
            "hours_since_last_client_message": round(hours_since, 1),
            "managers": ["Владислав", "Егор", "Юлия"],
            "company_name": "MIA CONSULT GROUP"
        }
        
        prompt = f"""Ты — эксперт по аналитике работы менеджеров по сопровождению ДЕЙСТВУЮЩИХ клиентов и контролю качества сервиса.

КОНТЕКСТ:
Клиент уже является клиентом компании (бухгалтерское обслуживание, регистрация, легализация).
Задачи менеджеров: отвечать на вопросы, решать проблемы, давать статус, удерживать клиента.

ВХОДНЫЕ ДАННЫЕ:
{input_data}

ОЦЕНИ:
1. НАСТРОЕНИЕ КЛИЕНТА:
   - overall_sentiment: positive/neutral/negative/mixed
   - sentiment_score: от -1 до 1
   - client_state: calm/worried/angry/confused/in_a_hurry/unknown

2. ТИП ЗАПРОСА:
   - request_type: information_question / status_update / technical_issue / service_complaint / billing_issue / cancellation_or_risk / other

3. ПРЕДСТАВЛЕНИЕ МЕНЕДЖЕРА:
   - Назвал ли имя из списка managers
   - Качество: none/poor/normal/good

4. КАЧЕСТВО РАБОТЫ (1-10):
   - politeness_score: вежливость, приветствие, уважение
   - clarity_score: ясность, понятность ответов
   - proactivity_score: инициатива, предложение решений
   - professionalism_score: общий уровень

ВАЖНО: 
- Если ответ быстрый (<15 мин) + вежливый = минимум 7 баллов
- Если ответ >1 часа или игнор вопросов = максимум 4 балла
- Нет представления - снижает на 1-2 балла, но не делает автоматически плохим

5. РИСКИ:
   - risk_level: low/medium/high/critical (риск проблем с клиентом)
   - churn_risk_level: low/medium/high/critical (риск ухода)
   - need_urgent_attention: true/false

6. СТАТУС РЕШЕНИЯ:
   - resolution_status: resolved/partially_resolved/waiting_for_client/waiting_for_manager/long_term_process/not_resolvable_in_chat/unknown

Верни ТОЛЬКО JSON (без комментариев):
{{
  "overall_sentiment": "positive",
  "sentiment_score": 0.5,
  "client_state": "calm",
  "request_type": "information_question",
  "manager_introduced": true,
  "manager_name": "Владислав",
  "greeting_quality": "good",
  "politeness_score": 8,
  "clarity_score": 7,
  "proactivity_score": 6,
  "professionalism_score": 7,
  "resolution_status": "resolved",
  "risk_level": "low",
  "churn_risk_level": "low",
  "need_urgent_attention": false,
  "risks": ["риск 1", "риск 2"],
  "suggestions": ["совет 1", "совет 2", "совет 3"],
  "strengths": ["сильная сторона 1", "сильная сторона 2"],
  "key_issues": ["проблема 1"]
}}"""

        try:
            response = requests.post(
                self.endpoint,
                headers={
                    'Content-Type': 'application/json',
                    'X-goog-api-key': self.api_key
                },
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
