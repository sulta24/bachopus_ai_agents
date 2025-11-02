#!/usr/bin/env python3
"""
Простой тест для проверки подлинности и работоспособности OpenAI API ключа
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

def test_api_key():
    """
    Тестирует OpenAI API ключ на подлинность и работоспособность
    """
    print("🔑 Тестирование OpenAI API ключа...")
    
    # Загружаем переменные окружения
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("❌ ОШИБКА: API ключ не найден в .env файле")
        print("   Убедитесь, что в .env файле есть строка: OPENAI_API_KEY=ваш_ключ")
        return False
    
    print(f"📋 API ключ найден: {api_key[:10]}...{api_key[-10:]}")
    
    try:
        # Создаем клиент OpenAI
        client = OpenAI(api_key=api_key)
        
        # Получаем список доступных моделей
        print("📋 Получаем список доступных моделей...")
        models = client.models.list()
        available_models = [model.id for model in models.data if 'gpt' in model.id]
        
        if not available_models:
            print("❌ ОШИБКА: Нет доступных GPT моделей")
            return False
        
        # Используем модель gpt-4o
        model_name = "gpt-4o"
        print(f"🤖 Используем модель: {model_name}")
        
        # Отправляем простой тестовый запрос
        print("📡 Отправляем тестовый запрос...")
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": "Привет! Это тест API. Скажи сколько будет 2 + 2 * 3"}
            ],
            max_tokens=100
        )
        
        if response and response.choices and response.choices[0].message.content:
            print("✅ УСПЕХ: API ключ работает корректно!")
            print(f"📝 Ответ от OpenAI: {response.choices[0].message.content[:100]}...")
            return True
        else:
            print("❌ ОШИБКА: Получен пустой ответ от API")
            return False
            
    except Exception as e:
        print(f"❌ ОШИБКА: {str(e)}")
        
        # Анализируем тип ошибки
        error_str = str(e).lower()
        if "api key not valid" in error_str or "invalid" in error_str or "unauthorized" in error_str:
            print("💡 Решение: Проверьте правильность API ключа")
        elif "quota" in error_str or "limit" in error_str or "rate" in error_str:
            print("💡 Решение: Превышена квота API, попробуйте позже")
        elif "permission" in error_str:
            print("💡 Решение: Недостаточно прав доступа к API")
        else:
            print("💡 Решение: Проверьте подключение к интернету и настройки API")
        
        return False

def main():
    """Основная функция"""
    print("=" * 50)
    print("🧪 ТЕСТ OPENAI API КЛЮЧА")
    print("=" * 50)
    
    success = test_api_key()
    
    print("=" * 50)
    if success:
        print("🎉 РЕЗУЛЬТАТ: API ключ работает отлично!")
    else:
        print("💥 РЕЗУЛЬТАТ: Проблемы с API ключом")
    print("=" * 50)

if __name__ == "__main__":
    main()