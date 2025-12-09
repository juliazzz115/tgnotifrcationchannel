"""
Генератор тестовых данных для аналитики
"""
import json
import random
from datetime import datetime, timedelta

# Списки для генерации данных
MANAGERS = ['Влад', 'Егор', 'Юлия']
CLIENTS = ['Анна Ковальская', 'Петр Новак', 'Мария Вишневская', 'Ян Ковальчик', 
           'Катажина Зелинская', 'Артур Войтович', 'Ольга Козловская', 'Михал Дуда',
           'Агнешка Левандовска']
TOPICS = ['статус регистрации компании', 'вопрос по счету', 'проблема с документами',
          'консультация по налогам', 'продление визы', 'открытие счета в банке',
          'изменение данных в ZUS', 'вопрос по PESEL']
SENTIMENTS = ['позитивное', 'нейтральное', 'слегка негативное', 'позитивное']
SUGGESTIONS = [
    'Продолжать в том же духе',
    'Можно добавить больше эмпатии',
    'Предлагать дополнительную помощь проактивно',
    'Использовать более понятный язык',
    'Сократить время ответа'
]

def generate_dialog(index):
    """Генерация одного диалога"""
    now = datetime.now()
    time_offset = timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59))
    dialog_time = now - time_offset
    
    manager = random.choice(MANAGERS)
    introduced = random.choice([True, True, True, False])  # 75% представляются
    
    # Качество зависит от нескольких факторов
    base_score = random.randint(5, 10)
    if not introduced:
        base_score -= 1
    
    response_time = random.randint(5, 180)  # 5-180 минут
    if response_time > 90:
        base_score -= 2
    
    score = max(1, min(10, base_score))
    
    # Риск оттока
    if score >= 8:
        risk = 'low'
    elif score >= 6:
        risk = 'medium'
    elif score >= 4:
        risk = 'high'
    else:
        risk = 'critical'
    
    return {
        'id': 1000000 + index,
        'name': random.choice(CLIENTS),
        'time': dialog_time.strftime('%d.%m.%Y %H:%M'),
        'date': dialog_time.strftime('%d.%m.%Y'),
        'timestamp': int(dialog_time.timestamp()),
        'manager_name': manager,
        'introduced': introduced,
        'greeting': introduced,  # обычно связано
        'professionalism_score': score,
        'politeness_score': score + random.randint(-1, 1),
        'clarity_score': score + random.randint(-1, 1),
        'proactivity_score': score + random.randint(-2, 1),
        'responsiveness_score': 10 - (response_time // 20),
        'empathy_score': score + random.randint(-1, 2),
        'response_delay_working_minutes': response_time,
        'avg_response_time_minutes': response_time + random.randint(-10, 10),
        'total_client_messages': random.randint(1, 5),
        'total_responses': random.randint(1, 4),
        'overall_sentiment': random.choice(SENTIMENTS),
        'response_tone': random.choice(['дружелюбный', 'профессиональный', 'нейтральный']),
        'main_topic': random.choice(TOPICS),
        'urgency_level': random.choice(['низкая', 'средняя', 'высокая']),
        'communication_style': random.choice(['дружелюбный', 'профессиональный', 'формальный']),
        'resolution_status': random.choice(['resolved', 'resolved', 'in_progress', 'waiting']),
        'solution_provided': random.choice([True, True, False]),
        'churn_risk_level': risk,
        'risk_level': risk,
        'summary': f"{'Отличный' if score >= 8 else 'Хороший' if score >= 6 else 'Удовлетворительный'} диалог. {manager} {'представился' if introduced else 'не представился'}. Время ответа: {response_time}м.",
        'suggestions': random.sample(SUGGESTIONS, k=random.randint(2, 4)),
        'response_quality': 'отлично' if score >= 9 else 'хорошо' if score >= 7 else 'приемлемо'
    }

def main():
    """Генерация тестовых данных"""
    print("🔧 Генерация тестовых данных...")
    
    # Генерируем 27 диалогов (как в оригинале)
    dialogs = [generate_dialog(i) for i in range(27)]
    
    # Сохраняем в файл
    with open('test_dialogs.json', 'w', encoding='utf-8') as f:
        json.dump(dialogs, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Создано {len(dialogs)} тестовых диалогов")
    print(f"📄 Файл: test_dialogs.json")
    
    # Статистика
    print("\n📊 Статистика:")
    print(f"   Менеджеры: {', '.join(set(d['manager_name'] for d in dialogs))}")
    print(f"   Представились: {sum(1 for d in dialogs if d['introduced'])}/{len(dialogs)}")
    print(f"   Средняя оценка: {sum(d['professionalism_score'] for d in dialogs) / len(dialogs):.1f}/10")
    print(f"   Высокий риск: {sum(1 for d in dialogs if d['churn_risk_level'] in ['high', 'critical'])}")

if __name__ == '__main__':
    main()
