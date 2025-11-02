import httpx
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from colorama import Fore, Style

logger = logging.getLogger(__name__)

class BackendClientError(Exception):
    """Базовое исключение для ошибок клиента бекенда"""
    pass

class ServiceNotFoundError(BackendClientError):
    """Исключение когда сервис не найден"""
    pass

class SessionNotFoundError(BackendClientError):
    """Исключение когда сессия не найдена"""
    pass

class BackendClient:
    """
    HTTP клиент для работы с бекендом AI Orchestrator
    Обеспечивает получение данных сервисов и сообщений чата
    """
    
    def __init__(self, base_url: str = "http://45.133.74.188:8080", timeout: int = 30, bearer_token: str = None):
        """
        Инициализация клиента бекенда
        
        Args:
            base_url: Базовый URL бекенда
            timeout: Таймаут запросов в секундах
            bearer_token: Bearer токен для аутентификации
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.bearer_token = bearer_token
        self.logger = logging.getLogger(__name__)
        
        # Настройка заголовков по умолчанию
        self.default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Добавляем Authorization заголовок если токен предоставлен
        if self.bearer_token:
            self.default_headers["Authorization"] = f"Bearer {self.bearer_token}"
        
    async def get_service_info(self, service_id: str) -> Dict[str, Any]:
        """
        Получает информацию о сервисе
        
        Args:
            service_id: ID сервиса
            
        Returns:
            Dict с информацией о сервисе
            
        Raises:
            ServiceNotFoundError: Если сервис не найден
            BackendClientError: При других ошибках API
        """
        url = f"{self.base_url}/api/services/{service_id}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.default_headers)
                
                if response.status_code == 404:
                    self.logger.error(f"Сервис {service_id} не найден")
                    raise ServiceNotFoundError(f"Сервис {service_id} не найден")
                elif response.status_code != 200:
                    self.logger.error(f"Ошибка API {response.status_code} при получении сервиса {service_id}")
                    raise BackendClientError(f"Ошибка API: {response.status_code} - {response.text}")
                
                result = response.json()
                
                # Валидация данных
                if not self.validate_service_data(result):
                    self.logger.error(f"Некорректные данные сервиса {service_id}")
                    raise BackendClientError(f"Некорректные данные сервиса {service_id}")
                
                return result
                
        except httpx.RequestError as e:
            self.logger.error(f"Ошибка сети при получении сервиса {service_id}: {e}")
            raise BackendClientError(f"Ошибка сети: {e}")
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при получении сервиса {service_id}: {e}")
            raise BackendClientError(f"Неожиданная ошибка: {e}")
    
    async def get_chat_messages(self, session_id: str) -> Dict[str, Any]:
        """
        Получает сообщения чата для указанной сессии
        
        Args:
            session_id: ID сессии чата
            
        Returns:
            Dict с сообщениями: messages, sessionId, serviceId
            
        Raises:
            SessionNotFoundError: Если сессия не найдена
            BackendClientError: При других ошибках API
        """
        url = f"{self.base_url}/api/sessions/{session_id}/get_messages"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.default_headers)
                
                if response.status_code == 404:
                    self.logger.error(f"Сессия {session_id} не найдена")
                    raise SessionNotFoundError(f"Сессия {session_id} не найдена")
                elif response.status_code != 200:
                    self.logger.error(f"Ошибка API {response.status_code} для сессии {session_id}")
                    raise BackendClientError(f"Ошибка API: {response.status_code} - {response.text}")
                
                chat_data = response.json()
                
                # Валидация структуры ответа
                if 'messages' not in chat_data:
                    self.logger.error(f"Отсутствует поле 'messages' в ответе")
                    raise BackendClientError("Отсутствует поле 'messages' в ответе API")
                
                return chat_data
                
        except httpx.TimeoutException:
            self.logger.error(f"Таймаут при запросе сообщений сессии {session_id}")
            raise BackendClientError(f"Таймаут при запросе сообщений сессии {session_id}")
        except httpx.RequestError as e:
            self.logger.error(f"Ошибка сети при запросе сессии {session_id}: {e}")
            raise BackendClientError(f"Ошибка сети при запросе сессии {session_id}: {str(e)}")
    
    async def get_service_and_messages(self, service_id: str, session_id: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Получает данные сервиса и сообщения чата одновременно
        
        Args:
            service_id: ID сервиса
            session_id: ID сессии
            
        Returns:
            Tuple (service_data, chat_data)
            
        Raises:
            ServiceNotFoundError, SessionNotFoundError, BackendClientError
        """
        try:
            # Выполняем запросы параллельно для ускорения
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                service_task = self.get_service_info(service_id)
                messages_task = self.get_chat_messages(session_id)
                
                service_data, chat_data = await asyncio.gather(service_task, messages_task)
                
                return service_data, chat_data
                
        except Exception as e:
            self.logger.error(f"Ошибка при получении данных сервиса {service_id} и сессии {session_id}: {str(e)}")
            raise
    
    async def add_message(self, session_id: str, prompt: str, answer: str) -> Dict[str, Any]:
        """
        Добавляет сообщение в чат сессии
        
        Args:
            session_id: ID сессии чата
            prompt: Исходный запрос пользователя
            answer: Ответ ассистента
            
        Returns:
            Dict с результатом добавления сообщения
            
        Raises:
            SessionNotFoundError: Если сессия не найдена
            BackendClientError: При других ошибках API
        """
        url = f"{self.base_url}/api/sessions/{session_id}/add_message"
        
        payload = {
            "prompt": prompt,
            "answer": answer
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=self.default_headers)
                
                if response.status_code == 404:
                    self.logger.error(f"Сессия {session_id} не найдена")
                    raise SessionNotFoundError(f"Сессия {session_id} не найдена")
                elif response.status_code not in [200, 201]:
                    self.logger.error(f"Ошибка API {response.status_code} при добавлении сообщения")
                    raise BackendClientError(f"Ошибка API: {response.status_code} - {response.text}")
                
                return response.json()
                
        except httpx.RequestError as e:
            self.logger.error(f"Ошибка сети при добавлении сообщения: {e}")
            raise BackendClientError(f"Ошибка сети: {e}")
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при добавлении сообщения: {e}")
            raise BackendClientError(f"Неожиданная ошибка: {e}")

    def validate_service_data(self, service_data: Dict[str, Any]) -> bool:
        """
        Валидирует данные сервиса
        
        Args:
            service_data: Данные сервиса
            
        Returns:
            True если данные валидны
        """
        required_fields = ['id', 'name', 'apiKey', 'appKey']
        return all(service_data.get(field) for field in required_fields)
    
    def validate_chat_data(self, chat_data: Dict[str, Any]) -> bool:
        """
        Валидирует данные чата
        
        Args:
            chat_data: Данные чата
            
        Returns:
            True если данные валидны
        """
        if 'messages' not in chat_data:
            return False
            
        messages = chat_data['messages']
        if not isinstance(messages, list):
            return False
            
        # Проверяем структуру каждого сообщения
        for message in messages:
            required_fields = ['id', 'timestamp', 'prompt', 'answer']
            if not all(field in message for field in required_fields):
                return False
                
        return True