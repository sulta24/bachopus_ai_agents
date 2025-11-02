"""
DatadogClient - клиент для работы с Datadog API
Обеспечивает получение метрик и данных временных рядов из Datadog
"""

import httpx
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import asyncio
from .datadog_utils import (
    safe_iterate_dict,
    parse_datadog_timeseries_response,
    parse_datadog_metrics_list,
    validate_datadog_response,
    log_datadog_response_structure
)


class DatadogConnectionError(Exception):
    """Исключение для ошибок подключения к Datadog API"""
    pass


class DatadogAuthenticationError(Exception):
    """Исключение для ошибок аутентификации в Datadog API"""
    pass


class DatadogAPIError(Exception):
    """Общее исключение для ошибок Datadog API"""
    pass


class DatadogClient:
    """Клиент для работы с Datadog API"""
    
    def __init__(self, api_key: str, app_key: str):
        """
        Инициализация клиента Datadog
        
        Args:
            api_key: API ключ Datadog
            app_key: Application ключ Datadog
        """
        if not api_key or not app_key:
            raise DatadogAuthenticationError("API key и Application key обязательны для работы с Datadog")
            
        self.api_key = api_key
        self.app_key = app_key
        self.base_url = "https://api.datadoghq.com"
        self.eu_base_url = "https://api.datadoghq.eu"
        
        # Заголовки для аутентификации
        self.headers = {
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key,
            "Content-Type": "application/json"
        }
    
    def _handle_response_error(self, response: httpx.Response, operation: str):
        """Обработка ошибок HTTP ответов"""
        if response.status_code == 401:
            raise DatadogAuthenticationError(f"Неверные ключи Datadog API для операции: {operation}")
        elif response.status_code == 403:
            raise DatadogAuthenticationError(f"Недостаточно прав для операции: {operation}")
        elif response.status_code == 429:
            raise DatadogAPIError(f"Превышен лимит запросов к Datadog API для операции: {operation}")
        elif response.status_code >= 500:
            raise DatadogConnectionError(f"Ошибка сервера Datadog для операции: {operation}")
        else:
            raise DatadogAPIError(f"Ошибка Datadog API ({response.status_code}) для операции: {operation}")
    
    async def get_available_metrics(self) -> List[Dict[str, Any]]:
        """
        Получение списка доступных метрик из Datadog с использованием безопасного парсинга
        
        Returns:
            List[Dict[str, Any]]: Список доступных метрик в нормализованном формате
            
        Raises:
            DatadogConnectionError: При ошибках подключения
            DatadogAuthenticationError: При ошибках аутентификации
            DatadogAPIError: При других ошибках API
        """
        try:
            async with httpx.AsyncClient() as client:
                # Используем EU endpoint и v1 API для лучшей совместимости
                response = await client.get(
                    f"{self.eu_base_url}/api/v1/metrics",
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    self._handle_response_error(response, "получение списка метрик")
                
                raw_data = response.json()
                
                # Логируем структуру для отладки
                log_datadog_response_structure(raw_data, "available metrics")
                
                # Используем безопасный парсинг
                metrics_list = parse_datadog_metrics_list(raw_data)
                
                print(f"Получено {len(metrics_list)} доступных метрик")
                return metrics_list
                    
        except httpx.TimeoutException:
            raise DatadogConnectionError("Таймаут при получении списка метрик")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise DatadogAuthenticationError("Неверные учетные данные API")
            elif e.response.status_code == 403:
                raise DatadogAuthenticationError("Недостаточно прав доступа")
            else:
                raise DatadogAPIError(f"HTTP ошибка {e.response.status_code}: {e.response.text}")
        except Exception as e:
            # Обрабатываем случаи, когда API возвращает ошибки из-за неверных ключей
            error_str = str(e).lower()
            if "invalid" in error_str or "unauthorized" in error_str or "forbidden" in error_str:
                print(f"Ошибка аутентификации API: {str(e)}")
                return []  # Возвращаем пустой список вместо исключения
            raise DatadogAPIError(f"Ошибка при получении списка метрик: {str(e)}")
    
    async def get_metric_timeseries(
        self, 
        metric_name: str, 
        start_timestamp: int, 
        end_timestamp: int,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Получение данных временных рядов для конкретной метрики с использованием безопасного парсинга
        
        Args:
            metric_name: Имя метрики
            start_timestamp: Начальный Unix timestamp
            end_timestamp: Конечный Unix timestamp
            tags: Опциональные теги для фильтрации
            
        Returns:
            Dict[str, Any]: Данные временных рядов метрики в нормализованном формате
        """
        try:
            # Формируем query в правильном формате для v1 API
            query = f"avg:{metric_name}"
            if tags:
                # Добавляем теги в формате {tag1:value1,tag2:value2}
                tag_string = ",".join(tags)
                query += f"{{{tag_string}}}"
            else:
                query += "{*}"
            
            # Формируем параметры запроса для v1 API
            params = {
                "from": start_timestamp,
                "to": end_timestamp,
                "query": query
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.eu_base_url}/api/v1/query",
                    headers=self.headers,
                    params=params,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    raw_data = response.json()
                    
                    # Логируем структуру для отладки
                    log_datadog_response_structure(raw_data, f"timeseries {metric_name}")
                    
                    # Используем безопасный парсинг
                    parsed_data = parse_datadog_timeseries_response(raw_data)
                    
                    if parsed_data.get("error"):
                        print(f"Ошибка в данных временных рядов: {parsed_data['error']}")
                        return {"error": parsed_data["error"], "series": []}
                    
                    # Добавляем метаданные запроса
                    parsed_data.update({
                        "metric_name": metric_name,
                        "start_timestamp": start_timestamp,
                        "end_timestamp": end_timestamp,
                        "query": query
                    })
                    
                    print(f"Получено {len(parsed_data.get('series', []))} серий для метрики {metric_name}")
                    return parsed_data
                else:
                    self._handle_response_error(response, f"получение данных метрики {metric_name}")
                    
        except httpx.TimeoutException:
            raise DatadogConnectionError(f"Таймаут при получении данных метрики {metric_name}")
        except Exception as e:
            raise DatadogAPIError(f"Ошибка при получении данных метрики {metric_name}: {str(e)}")
    
    async def get_system_metrics(self, hours_back: int = 1) -> List[Dict[str, Any]]:
        """
        Получение основных системных метрик за указанный период с использованием безопасной итерации
        Использует полный список системных метрик, организованных по категориям
        
        Args:
            hours_back: Количество часов назад для получения данных
            
        Returns:
            List[Dict[str, Any]]: Список системных метрик с категориями в нормализованном формате
        """
        try:
            # Вычисляем временные рамки
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours_back)
            
            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())
            
            # Полный список системных метрик, организованных по категориям
            metrics_config = {
                "cpu": [
                    "system.cpu.user",
                    "system.cpu.system", 
                    "system.cpu.idle",
                    "system.load.1"
                ],
                "memory": [
                    "system.mem.used",
                    "system.mem.free",
                    "system.swap.used"
                ],
                "disk": [
                    "system.disk.used",
                    "system.disk.free", 
                    "system.disk.in_use"
                ],
                "network": [
                    "system.net.bytes_sent",
                    "system.net.bytes_rcvd"
                ],
                "docker": [
                    "docker.cpu.usage",
                    "docker.mem.rss",
                    "docker.io.read_bytes",
                    "docker.io.write_bytes"
                ]
            }
            
            # Используем безопасную итерацию
            safe_config = safe_iterate_dict(metrics_config, "system metrics config")
            
            print(f"Получаем данные для системных метрик по категориям: {list(safe_config.keys())}")
            
            metrics_data = []
            
            # Получаем данные для каждой категории метрик
            for category, metric_names in safe_config.items():
                if not isinstance(metric_names, list):
                    print(f"Метрики для категории {category} не являются списком: {type(metric_names)}")
                    continue
                    
                category_data = {
                    "category": category,
                    "metrics": []
                }
                
                for metric_name in metric_names:
                    if not isinstance(metric_name, str):
                        print(f"Название метрики не является строкой: {type(metric_name)}")
                        continue
                        
                    try:
                        metric_data = await self.get_metric_timeseries(
                            metric_name, 
                            start_timestamp, 
                            end_timestamp
                        )
                        
                        # Добавляем метаданные категории
                        metric_data["category"] = category
                        metric_data["metric_name"] = metric_name
                        
                        category_data["metrics"].append(metric_data)
                    except Exception as e:
                        # Логируем ошибку, но продолжаем получать другие метрики
                        error_msg = f"Не удалось получить метрику {metric_name} из категории {category}: {str(e)}"
                        print(error_msg)
                        
                        # Добавляем информацию об ошибке в результат
                        error_data = {
                            "metric_name": metric_name,
                            "category": category,
                            "error": error_msg,
                            "series": []
                        }
                        category_data["metrics"].append(error_data)
                        continue
                
                # Добавляем категорию с метаданными
                category_data["metrics_count"] = len(category_data["metrics"])
                category_data["timestamp"] = end_time.isoformat()
                metrics_data.append(category_data)
            
            # Добавляем общие метаданные
            result_metadata = {
                "total_categories": len(metrics_data),
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "hours_back": hours_back
                },
                "timestamp": datetime.now().isoformat()
            }
            
            print(f"Обработано {len(metrics_data)} категорий системных метрик")
            
            # Возвращаем данные с метаданными
            return [
                {"_metadata": result_metadata},
                *metrics_data
            ]
            
        except Exception as e:
            error_msg = f"Критическая ошибка при получении системных метрик: {str(e)}"
            print(error_msg)
            return [{
                "error": error_msg,
                "_metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "status": "failed"
                }
            }]
    
    async def test_connection(self) -> bool:
        """
        Тестирование подключения к Datadog API
        
        Returns:
            bool: True если подключение успешно, False иначе
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.eu_base_url}/api/v1/validate",
                    headers=self.headers,
                    timeout=10.0
                )
                
                return response.status_code == 200
                
        except Exception:
            return False

    def send_metric(self, metric_name: str, value: float, tags: List[str] = None):
        """Отправляет метрику в Datadog"""
        if not self.enabled:
            return
            
        try:
            api.Metric.send(
                metric=metric_name,
                points=[(time.time(), value)],
                tags=tags or []
            )
        except Exception as e:
            print(f"❌ Ошибка отправки метрики в Datadog: {str(e)}")

    def send_event(self, title: str, text: str, alert_type: str = "info", tags: List[str] = None):
        """Отправляет событие в Datadog"""
        if not self.enabled:
            return
            
        try:
            api.Event.create(
                title=title,
                text=text,
                alert_type=alert_type,
                tags=tags or []
            )
        except Exception as e:
            print(f"❌ Ошибка отправки события в Datadog: {str(e)}")