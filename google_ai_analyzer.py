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
        self.endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"

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
Клиент уже является клиентом компании MIA CONSULT GROUP (бухгалтерское обслуживание, регистрация бизнеса, легализация в Польше).
Задачи менеджеров: отвечать на вопросы, решать проблемы, давать статус по заявкам, удерживать клиента, предотвращать отток.

ВХОДНЫЕ ДАННЫЕ:
{input_data}

ВАЖНО: ВСЕ ЗНАЧЕНИЯ В JSON ДОЛЖНЫ БЫТЬ НА РУССКОМ ЯЗЫКЕ (кроме ключей). Используй русские слова: "низкий", "средний", "высокий", "решён", "дружелюбный" и т.д.

ПРОВЕДИ ДЕТАЛЬНЫЙ МНОГОУРОВНЕВЫЙ АНАЛИЗ:

1. НАСТРОЕНИЕ И ЭМОЦИИ КЛИЕНТА:
   - overall_sentiment: positive/neutral/negative/mixed
   - sentiment_score: от -1.0 (очень негативное) до +1.0 (очень позитивное)
   - client_state: calm/worried/angry/frustrated/confused/in_a_hurry/satisfied/disappointed/unknown
   - emotion_dynamics: как менялись эмоции в течение диалога (например: "started_worried_became_calm", "consistently_positive", "escalating_frustration")

2. ТИП И ТЕМА ЗАПРОСА:
   - request_type: information_question / status_update / technical_issue / service_complaint / billing_issue / cancellation_or_risk / document_request / deadline_pressure / other
   - main_topic: конкретная тема (например: "статус регистрации компании", "вопрос по счету", "проблема с документами")
   - urgency_level: low/medium/high/critical
   - client_expectations: что ожидает клиент (быстрый ответ, конкретные действия, объяснение)

3. ПРЕДСТАВЛЕНИЕ И ПЕРВОЕ ВПЕЧАТЛЕНИЕ:
   - manager_introduced: true/false (назвал ли имя из списка managers)
   - manager_name: имя или null
   - greeting_quality: excellent/good/basic/poor/none
   - first_impression: как менеджер начал диалог (профессионально, формально, тепло, холодно)

4. ДЕТАЛЬНАЯ ОЦЕНКА КАЧЕСТВА РАБОТЫ МЕНЕДЖЕРА (каждый параметр 1-10):
   - politeness_score: вежливость, уважение, тон, использование приветствий и благодарностей
   - clarity_score: ясность и понятность ответов, структурированность информации
   - proactivity_score: инициатива, предложение решений, предвосхищение вопросов
   - responsiveness_score: скорость реакции, готовность помочь
   - empathy_score: эмпатия, понимание ситуации клиента, эмоциональный интеллект
   - professionalism_score: общий профессионализм, компетентность

ОБЪЕКТИВНЫЕ КРИТЕРИИ ОЦЕНКИ:
- Ответ <15 минут + вежливое обращение = минимум 7-8 баллов
- Ответ через 30-60 минут = 5-6 баллов (если качественный)
- Ответ >1 часа или игнорирование вопросов = максимум 3-4 балла
- Грубость, формализм, отписки = снижение на 2-3 балла
- Нет представления = -1 балл к professionalism_score, но не критично
- Решение проблемы клиента = +1-2 балла ко всем показателям

5. КОММУНИКАЦИЯ И СТИЛЬ:
   - communication_style: friendly/professional/formal/cold/warm/casual
   - used_personalization: использовал ли персонализацию (обращение по имени клиента)
   - tone_consistency: последовательность тона на протяжении диалога
   - language_quality: грамотность, отсутствие ошибок

6. АНАЛИЗ РЕШЕНИЯ ПРОБЛЕМЫ:
   - resolution_status: resolved/partially_resolved/in_progress/waiting_for_client/waiting_for_manager/long_term_process/not_resolvable_in_chat/ignored/unknown
   - solution_provided: предложено ли конкретное решение (true/false)
   - next_steps_clear: понятны ли следующие шаги клиенту (true/false)
   - timeline_given: указаны ли сроки выполнения (true/false)
   - follow_up_planned: запланирован ли follow-up (true/false)

7. РИСКИ И ПРЕДУПРЕЖДЕНИЯ:
   - risk_level: low/medium/high/critical (риск проблем с клиентом)
   - churn_risk_level: low/medium/high/critical (риск ухода клиента)
   - need_urgent_attention: требуется ли срочное внимание руководителя (true/false)
   - escalation_needed: нужна ли эскалация вопроса (true/false)
   - risks: массив конкретных рисков (например: ["клиент ждет ответ >24 часа", "недовольство качеством", "угроза расторжения"])

8. КЛЮЧЕВЫЕ МОМЕНТЫ ДИАЛОГА:
   - key_moments: важные моменты диалога (например: ["клиент выразил недовольство задержкой", "менеджер пообещал решить до конца дня"])
   - critical_phrases: критические фразы клиента или менеджера
   - turning_points: переломные моменты (положительные или отрицательные)

9. СИЛЬНЫЕ СТОРОНЫ:
   - strengths: массив сильных сторон работы менеджера (минимум 2-3 пункта, даже если есть проблемы)

10. ПРОБЛЕМЫ И НЕДОЧЕТЫ:
   - key_issues: массив конкретных проблем (например: ["нет представления", "слишком формальный тон", "не указаны сроки"])
   - missed_opportunities: упущенные возможности улучшить сервис

11. ДЕТАЛЬНЫЕ РЕКОМЕНДАЦИИ:
   - suggestions: массив конкретных, практических рекомендаций (минимум 3-5 пунктов)
   - priority_actions: приоритетные действия (что сделать в первую очередь)
   - training_needs: какое обучение может потребоваться менеджеру

12. ОБЩАЯ ОЦЕНКА И ВЫВОДЫ:
   - overall_quality: excellent/good/satisfactory/poor/critical
   - client_satisfaction_estimate: оценка удовлетворенности клиента (1-10)
   - summary: краткое резюме диалога (1-2 предложения)

Верни ТОЛЬКО JSON (без комментариев, без markdown). ВСЕ ЗНАЧЕНИЯ НА РУССКОМ:
{{
  "overall_sentiment": "позитивное",
  "sentiment_score": 0.7,
  "client_state": "спокоен",
  "emotion_dynamics": "стабильно позитивное",
  "request_type": "запрос статуса",
  "main_topic": "статус регистрации компании",
  "urgency_level": "средняя",
  "client_expectations": "получить конкретные сроки",
  "manager_introduced": true,
  "manager_name": "Владислав",
  "greeting_quality": "хорошее",
  "first_impression": "профессионально и тепло",
  "politeness_score": 8,
  "clarity_score": 7,
  "proactivity_score": 6,
  "responsiveness_score": 8,
  "empathy_score": 7,
  "professionalism_score": 7,
  "communication_style": "дружелюбный",
  "used_personalization": true,
  "tone_consistency": "последовательный",
  "language_quality": "отличное",
  "resolution_status": "решён",
  "solution_provided": true,
  "next_steps_clear": true,
  "timeline_given": true,
  "follow_up_planned": false,
  "risk_level": "низкий",
  "churn_risk_level": "низкий",
  "need_urgent_attention": false,
  "escalation_needed": false,
  "risks": [],
  "key_moments": ["менеджер оперативно дал статус", "клиент поблагодарил за информацию"],
  "critical_phrases": [],
  "turning_points": [],
  "strengths": ["быстрый ответ", "четкая информация", "вежливое обращение"],
  "key_issues": [],
  "missed_opportunities": ["можно было предложить дополнительную консультацию"],
  "suggestions": ["продолжать в том же духе", "можно добавить больше эмпатии", "предлагать дополнительную помощь проактивно"],
  "priority_actions": [],
  "training_needs": [],
  "overall_quality": "хорошее",
  "client_satisfaction_estimate": 8,
  "summary": "Качественный диалог с быстрым решением вопроса клиента"
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
                        "maxOutputTokens": 2048
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
                
                # Очистка summary от подчёркиваний и других артефактов
                if 'summary' in result and result['summary']:
                    result['summary'] = result['summary'].replace('_', ' ')
                
                logger.info(f"✅ Google AI анализ выполнен успешно")
                return result
            else:
                error_msg = f"Google AI API error: {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f" - {error_data.get('error', {}).get('message', 'Unknown error')}"
                except:
                    pass
                logger.error(error_msg)
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
            # Основные поля
            'manager_introduced': introduction['introduced'],
            'manager_name': introduction['manager_name'],
            'greeting_quality': 'good' if has_greeting else 'none',
            'response_tone': 'neutral',
            'professionalism_score': score,
            'suggestions': suggestions,
            'key_issues': key_issues,
            'strengths': strengths,
            # Расширенные поля для совместимости
            'overall_sentiment': 'neutral',
            'sentiment_score': 0.0,
            'client_state': 'unknown',
            'emotion_dynamics': 'unknown',
            'request_type': 'other',
            'main_topic': 'не определено',
            'urgency_level': 'medium',
            'client_expectations': 'не определено',
            'first_impression': 'нейтральное',
            'politeness_score': score,
            'clarity_score': score,
            'proactivity_score': score,
            'responsiveness_score': score,
            'empathy_score': score,
            'communication_style': 'professional',
            'used_personalization': False,
            'tone_consistency': 'последовательный',
            'language_quality': 'нормальное',
            'resolution_status': 'unknown',
            'solution_provided': False,
            'next_steps_clear': False,
            'timeline_given': False,
            'follow_up_planned': False,
            'risk_level': 'medium',
            'churn_risk_level': 'low',
            'need_urgent_attention': False,
            'escalation_needed': False,
            'risks': [],
            'key_moments': [],
            'critical_phrases': [],
            'turning_points': [],
            'missed_opportunities': [],
            'priority_actions': [],
            'training_needs': [],
            'overall_quality': 'satisfactory',
            'client_satisfaction_estimate': score,
            'summary': 'Базовый анализ (Google AI недоступен)'
        }


google_ai_analyzer = GoogleAIAnalyzer()
