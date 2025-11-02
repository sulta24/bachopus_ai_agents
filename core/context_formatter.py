import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ContextFormatter:
    """
    Форматирует сообщения чата в контекст для AI агентов
    """
    
    def __init__(self, max_context_length: int = 4000, max_messages: int = 20):
        """
        Args:
            max_context_length: Максимальная длина контекста в символах
            max_messages: Максимальное количество сообщений для включения в контекст
        """
        self.max_context_length = max_context_length
        self.max_messages = max_messages
        self.logger = logging.getLogger(__name__)
    
    def format_chat_context(self, chat_data: Dict[str, Any], new_prompt: str) -> str:
        """
        Форматирует историю чата и новый промпт в единый контекст
        
        Args:
            chat_data: Данные чата от бекенда
            new_prompt: Новый промпт пользователя
            
        Returns:
            Отформатированный контекст для агентов
        """
        messages = chat_data.get('messages', [])
        
        if not messages:
            self.logger.info("История чата пуста, используется только новый промпт")
            return f"User: {new_prompt}"
        
        # Сортируем сообщения по времени (старые -> новые)
        sorted_messages = self._sort_messages_by_time(messages)
        
        # Ограничиваем количество сообщений
        if len(sorted_messages) > self.max_messages:
            sorted_messages = sorted_messages[-self.max_messages:]
            self.logger.info(f"Ограничено до {self.max_messages} последних сообщений")
        
        # Форматируем историю
        context_parts = []
        context_parts.append("=== История чата ===")
        
        for message in sorted_messages:
            formatted_message = self._format_single_message(message)
            context_parts.append(formatted_message)
        
        # Добавляем новый промпт
        context_parts.append("=== Новый запрос ===")
        context_parts.append(f"User: {new_prompt}")
        
        # Объединяем и проверяем длину
        full_context = "\n\n".join(context_parts)
        
        if len(full_context) > self.max_context_length:
            full_context = self._truncate_context(context_parts, new_prompt)
        
        self.logger.info(f"Сформирован контекст длиной {len(full_context)} символов")
        return full_context
    
    def _sort_messages_by_time(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Сортирует сообщения по времени
        
        Args:
            messages: Список сообщений
            
        Returns:
            Отсортированный список сообщений
        """
        try:
            return sorted(messages, key=lambda x: self._parse_timestamp(x.get('timestamp', '')))
        except Exception as e:
            self.logger.warning(f"Ошибка сортировки по времени: {e}, используется исходный порядок")
            return messages
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """
        Парсит timestamp в формате ISO
        
        Args:
            timestamp_str: Строка с timestamp
            
        Returns:
            datetime объект
        """
        try:
            # Поддерживаем формат "2025-11-01T04:11:02.838Z"
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            return datetime.fromisoformat(timestamp_str)
        except Exception:
            # Если не удается распарсить, возвращаем текущее время
            return datetime.now()
    
    def _format_single_message(self, message: Dict[str, Any]) -> str:
        """
        Форматирует одно сообщение
        
        Args:
            message: Данные сообщения
            
        Returns:
            Отформатированное сообщение
        """
        prompt = message.get('prompt', '').strip()
        answer = message.get('answer', '').strip()
        timestamp = message.get('timestamp', '')
        
        # Форматируем время для читаемости
        formatted_time = self._format_timestamp(timestamp)
        
        parts = []
        if formatted_time:
            parts.append(f"[{formatted_time}]")
        
        if prompt:
            parts.append(f"User: {prompt}")
        
        if answer:
            parts.append(f"Assistant: {answer}")
        
        return "\n".join(parts)
    
    def _format_timestamp(self, timestamp_str: str) -> str:
        """
        Форматирует timestamp для отображения
        
        Args:
            timestamp_str: Строка с timestamp
            
        Returns:
            Отформатированное время
        """
        try:
            dt = self._parse_timestamp(timestamp_str)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return ""
    
    def _truncate_context(self, context_parts: List[str], new_prompt: str) -> str:
        """
        Обрезает контекст до максимальной длины, сохраняя новый промпт
        
        Args:
            context_parts: Части контекста
            new_prompt: Новый промпт (должен быть сохранен)
            
        Returns:
            Обрезанный контекст
        """
        # Всегда сохраняем новый промпт и заголовки
        essential_parts = [
            "=== Новый запрос ===",
            f"User: {new_prompt}"
        ]
        essential_length = len("\n\n".join(essential_parts))
        
        # Оставляем место для истории
        available_length = self.max_context_length - essential_length - 100  # буфер
        
        if available_length <= 0:
            self.logger.warning("Новый промпт слишком длинный, используется только он")
            return "\n\n".join(essential_parts)
        
        # Берем историю с конца, пока помещается
        history_parts = ["=== История чата (сокращено) ==="]
        current_length = len(history_parts[0])
        
        # Идем с конца истории (исключая заголовки нового запроса)
        for part in reversed(context_parts[1:-2]):  # пропускаем заголовки
            part_length = len(part) + 2  # +2 для \n\n
            if current_length + part_length <= available_length:
                history_parts.insert(1, part)  # вставляем в начало после заголовка
                current_length += part_length
            else:
                break
        
        # Объединяем все части
        result_parts = history_parts + essential_parts
        result = "\n\n".join(result_parts)
        
        self.logger.info(f"Контекст обрезан до {len(result)} символов")
        return result
    
    def get_context_stats(self, chat_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Возвращает статистику по контексту
        
        Args:
            chat_data: Данные чата
            
        Returns:
            Словарь со статистикой
        """
        messages = chat_data.get('messages', [])
        
        total_messages = len(messages)
        total_chars = sum(len(msg.get('prompt', '') + msg.get('answer', '')) for msg in messages)
        
        return {
            'total_messages': total_messages,
            'total_characters': total_chars,
            'will_be_truncated': total_messages > self.max_messages or total_chars > self.max_context_length,
            'session_id': chat_data.get('sessionId'),
            'service_id': chat_data.get('serviceId')
        }
    
    def format_context(self, raw_data: Dict[str, Any], analysis_results: Dict[str, Any]) -> str:
        """Форматирует контекст для LLM на основе сырых данных и результатов анализа"""
        try:
            formatted_sections = []
            
            # Форматирование сырых данных
            if raw_data:
                formatted_sections.append("=== ДАННЫЕ СИСТЕМЫ ===")
                for data_type, data_content in raw_data.items():
                    section = self._format_data_section(data_type, data_content)
                    if section:
                        formatted_sections.append(section)
            
            # Форматирование результатов анализа
            if analysis_results:
                formatted_sections.append("\n=== РЕЗУЛЬТАТЫ АНАЛИЗА ===")
                analysis_section = self._format_analysis_section(analysis_results)
                if analysis_section:
                    formatted_sections.append(analysis_section)
            
            return "\n".join(formatted_sections)
            
        except Exception as e:
            print(f"❌ Ошибка форматирования контекста: {str(e)}")
            return "Ошибка при форматировании данных для анализа"

    def _format_data_section(self, data_type: str, data_content: Any) -> str:
        """Форматирует секцию данных определенного типа"""
        try:
            if not data_content:
                return f"{data_type.upper()}: Данные недоступны"
            
            if data_type == "logs":
                return self._format_logs(data_content)
            elif data_type == "metrics":
                return self._format_metrics(data_content)
            elif data_type == "critical_errors":
                return self._format_critical_errors(data_content)
            elif data_type == "service_summary":
                return self._format_service_summary(data_content)
            else:
                return f"{data_type.upper()}: {str(data_content)[:200]}..."
                
        except Exception as e:
            print(f"❌ Ошибка форматирования секции {data_type}: {str(e)}")
            return f"{data_type.upper()}: Ошибка форматирования"