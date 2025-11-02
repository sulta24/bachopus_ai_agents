import json
import os
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import asyncio

# Импортируем DatadogClient
from core.datadog_client import DatadogClient, DatadogConnectionError, DatadogAuthenticationError, DatadogAPIError

class DataAgent:
    def __init__(self, dd_api_key: Optional[str] = None, dd_app_key: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        
        # Инициализация встроенного форматировщика
        self.formatter = self.DataFormatter()
        
        # Инициализация без зависимости от mock данных
        self.data = None  # Будет загружен при первом обращении
        
        # Настройки Datadog API
        self.DD_API_KEY = dd_api_key or "3cb244343cf0b67a853fab8dd26adace"
        self.DD_APP_KEY = dd_app_key or "1879f3e74ab7e870e5fb9e1558f4427633cb1bcc"
        self.DATADOG_SITE = "datadoghq.eu"
        self.API_BASE = f"https://api.{self.DATADOG_SITE}"
        self.HEADERS = {
            "DD-API-KEY": self.DD_API_KEY,
            "DD-APPLICATION-KEY": self.DD_APP_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        # Инициализируем статистику
        self.collection_stats = {
            "total_collections": 0,
            "last_collection_time": None,
            "data_sources": {
                "datadog_api": 0,
                "fallback": 0
            }
        }
        
        # Инициализация DatadogClient
        try:
            self.datadog_client = DatadogClient(api_key=self.DD_API_KEY, app_key=self.DD_APP_KEY)
            print(f"[DataAgent] Инициализирован с Datadog API: {self.API_BASE}")
        except Exception as e:
            self.logger.error(f"Ошибка инициализации DatadogClient: {e}")
            self.datadog_client = None
            print(f"[DataAgent] Ошибка инициализации DatadogClient: {e}")
    
    def _epoch_seconds(self, dt: datetime) -> int:
        """Конвертирует datetime в epoch секунды"""
        return int(dt.timestamp())
    
    class DataFormatter:
        """Встроенный форматировщик для интеллектуальной обработки данных"""
        
        def smart_format(self, data: Dict[str, Any], context: str = "analysis", max_tokens: int = 2000) -> str:
            """Упрощенное форматирование данных - только ключевые показатели"""
            
            # Простой краткий формат для всех случаев
            output = ["=== МОНИТОРИНГ СИСТЕМЫ ===\n"]
            
            # Обработка новой структуры метрик с series
            series = data.get("series", [])
            if series:
                output.append("📊 КЛЮЧЕВЫЕ МЕТРИКИ:")
                for metric_data in series[:3]:  # Максимум 3 метрики
                    metric_name = metric_data.get("metric", "unknown")
                    pointlist = metric_data.get("pointlist", [])
                    unit = metric_data.get("unit", [{}])
                    
                    # Берем последнее значение из pointlist
                    if pointlist:
                        latest_value = pointlist[-1][1] if len(pointlist[-1]) > 1 else 0
                    else:
                        latest_value = 0
                    
                    # Получаем единицу измерения
                    unit_name = unit[0].get("name", "") if unit else ""
                    
                    # Форматируем значения по типу метрики
                    if "cpu" in metric_name.lower():
                        output.append(f"  • CPU: {latest_value:.1f}%")
                    elif "mem" in metric_name.lower():
                        output.append(f"  • Memory: {latest_value:.1f}%") 
                    elif "error" in metric_name.lower():
                        output.append(f"  • Errors: {int(latest_value)}")
                    else:
                        output.append(f"  • {metric_name}: {latest_value} {unit_name}")
            else:
                output.append("📊 Метрики недоступны")
            
            # Логи (максимум 3) - обновлено для API v2
            logs_data = data.get("logs", {})
            logs = logs_data.get("data", []) if isinstance(logs_data, dict) else logs_data
            if logs:
                output.append(f"\n🚨 ЛОГИ ({len(logs)}):")
                for log in logs[:3]:
                    # Обрабатываем новую структуру API v2 с attributes
                    if isinstance(log, dict) and "attributes" in log:
                        attrs = log["attributes"]
                        status = attrs.get("status", "unknown")
                        service = attrs.get("service", "unknown")
                        message = attrs.get("message", "")[:50]  # Обрезаем до 50 символов
                    else:
                        # Обратная совместимость со старой структурой
                        status = log.get("status", "unknown")
                        service = log.get("service", "unknown")
                        message = log.get("message", "")[:50]
                    
                    # Определяем иконку по статусу
                    if status.upper() in ["ERROR", "CRITICAL"]:
                        icon = "🔴"
                    elif status.upper() == "WARN":
                        icon = "🟡"
                    else:
                        icon = "ℹ️"
                    
                    output.append(f"  {icon} {service}: {message}...")
            else:
                output.append("\n✅ Логи отсутствуют")
            
            # Общий статус - обновлено для API v2
            logs_data = data.get("logs", {})
            logs = logs_data.get("data", []) if isinstance(logs_data, dict) else logs_data
            error_count = 0
            
            for log in logs:
                if isinstance(log, dict) and "attributes" in log:
                    status = log["attributes"].get("status", "").upper()
                else:
                    status = log.get("status", "").upper()
                
                if status in ["ERROR", "CRITICAL"]:
                    error_count += 1
            
            if error_count > 0:
                output.append(f"\n⚠️ СТАТУС: Требует внимания ({error_count} ошибок)")
            else:
                output.append("\n✅ СТАТУС: Система работает нормально")
            
            return "\n".join(output)
        
        def _format_for_error_analysis(self, data: Dict[str, Any], max_tokens: int) -> str:
            """Форматирование для анализа ошибок - приоритет критическим ошибкам"""
            output = ["=== АНАЛИЗ ОШИБОК ===\n"]
            
            logs = data.get("logs", [])
            if logs:
                # Сортируем по критичности и времени
                critical_logs = [log for log in logs if log.get("level") == "CRITICAL"]
                error_logs = [log for log in logs if log.get("level") == "ERROR"]
                
                # Добавляем критические ошибки в приоритете
                if critical_logs:
                    output.append("🔴 КРИТИЧЕСКИЕ ОШИБКИ:")
                    for log in critical_logs[:3]:  # Топ-3 критических
                        output.append(f"• {log.get('timestamp', 'N/A')} | {log.get('service', 'N/A')}")
                        output.append(f"  Код: {log.get('error_code', 'N/A')} | {log.get('message', 'N/A')[:100]}...")
                
                if error_logs:
                    output.append("\n🟡 ОШИБКИ:")
                    for log in error_logs[:5]:  # Топ-5 ошибок
                        output.append(f"• {log.get('timestamp', 'N/A')} | {log.get('service', 'N/A')}")
                        output.append(f"  {log.get('error_code', 'N/A')}: {log.get('message', 'N/A')[:80]}...")
            
            # Добавляем метрики если есть место
            metrics = data.get("metrics", [])
            if metrics and len("\n".join(output)) < max_tokens * 0.7:
                output.append("\n📊 СВЯЗАННЫЕ МЕТРИКИ:")
                latest_metric = metrics[-1] if metrics else None
                if latest_metric and "metrics" in latest_metric:
                    m = latest_metric["metrics"]
                    output.append(f"CPU: {m.get('cpu_usage', 'N/A')}% | RAM: {m.get('memory_usage', 'N/A')}% | Ошибки: {m.get('error_rate', 'N/A')}%")
            
            return "\n".join(output)
        
        def _format_for_performance_analysis(self, data: Dict[str, Any], max_tokens: int) -> str:
            """Форматирование для анализа производительности"""
            output = ["=== АНАЛИЗ ПРОИЗВОДИТЕЛЬНОСТИ ===\n"]
            
            metrics = data.get("metrics", [])
            if metrics:
                output.append("📈 КЛЮЧЕВЫЕ МЕТРИКИ:")
                for metric in metrics[-5:]:  # Последние 5 метрик
                    if "metrics" in metric:
                        m = metric["metrics"]
                        service = metric.get("service", "N/A")
                        timestamp = metric.get("timestamp", "N/A")
                        
                        output.append(f"\n🔹 {service} ({timestamp})")
                        output.append(f"  CPU: {m.get('cpu_usage', 'N/A')}% | RAM: {m.get('memory_usage', 'N/A')}%")
                        output.append(f"  Отклик: {m.get('response_time_avg', 'N/A')}ms | Ошибки: {m.get('error_rate', 'N/A')}%")
            
            # Добавляем критические ошибки если есть
            logs = data.get("logs", [])
            critical_logs = [log for log in logs if log.get("level") in ["CRITICAL", "ERROR"]]
            if critical_logs and len("\n".join(output)) < max_tokens * 0.8:
                output.append(f"\n⚠️ СВЯЗАННЫЕ ПРОБЛЕМЫ ({len(critical_logs)}):")
                for log in critical_logs[:3]:
                    output.append(f"• {log.get('service', 'N/A')}: {log.get('message', 'N/A')[:60]}...")
            
            return "\n".join(output)
        
        def _format_for_service_summary(self, data: Dict[str, Any], max_tokens: int) -> str:
            """Форматирование для сводки по сервису"""
            output = ["=== СВОДКА ПО СЕРВИСУ ===\n"]
            
            # Группируем данные по сервисам
            services_data = {}
            
            # Обрабатываем логи
            for log in data.get("logs", []):
                service = log.get("service", "unknown")
                if service not in services_data:
                    services_data[service] = {"errors": [], "metrics": []}
                services_data[service]["errors"].append(log)
            
            # Обрабатываем метрики
            for metric in data.get("metrics", []):
                service = metric.get("service", "unknown")
                if service not in services_data:
                    services_data[service] = {"errors": [], "metrics": []}
                services_data[service]["metrics"].append(metric)
            
            # Форматируем по сервисам
            for service, sdata in services_data.items():
                output.append(f"🔧 {service.upper()}:")
                
                # Статистика ошибок
                errors = sdata["errors"]
                if errors:
                    error_levels = {}
                    for error in errors:
                        level = error.get("level", "UNKNOWN")
                        error_levels[level] = error_levels.get(level, 0) + 1
                    
                    error_summary = ", ".join([f"{level}: {count}" for level, count in error_levels.items()])
                    output.append(f"  Ошибки: {error_summary}")
                
                # Последние метрики
                metrics = sdata["metrics"]
                if metrics:
                    latest = metrics[-1]
                    if "metrics" in latest:
                        m = latest["metrics"]
                        output.append(f"  Состояние: CPU {m.get('cpu_usage', 'N/A')}%, RAM {m.get('memory_usage', 'N/A')}%, Отклик {m.get('response_time_avg', 'N/A')}ms")
                
                output.append("")
            
            return "\n".join(output)
        
        def _format_default(self, data: Dict[str, Any], max_tokens: int) -> str:
            """Базовое форматирование с приоритизацией"""
            output = ["=== ДАННЫЕ ДЛЯ АНАЛИЗА ===\n"]
            
            # Приоритет: критические ошибки -> метрики -> остальные ошибки
            logs = data.get("logs", [])
            metrics = data.get("metrics", [])
            
            # Критические проблемы в начало
            critical_logs = [log for log in logs if log.get("level") == "CRITICAL"]
            if critical_logs:
                output.append("🚨 КРИТИЧЕСКИЕ ПРОБЛЕМЫ:")
                for log in critical_logs[:3]:
                    output.append(f"• {log.get('service', 'N/A')}: {log.get('message', 'N/A')[:100]}...")
                output.append("")
            
            # Ключевые метрики
            if metrics:
                output.append("📊 ТЕКУЩИЕ МЕТРИКИ:")
                latest_metrics = metrics[-3:] if len(metrics) > 3 else metrics
                for metric in latest_metrics:
                    if "metrics" in metric:
                        m = metric["metrics"]
                        service = metric.get("service", "N/A")
                        output.append(f"• {service}: CPU {m.get('cpu_usage', 'N/A')}%, RAM {m.get('memory_usage', 'N/A')}%")
                output.append("")
            
            # Остальные ошибки
            other_logs = [log for log in logs if log.get("level") != "CRITICAL"]
            if other_logs and len("\n".join(output)) < max_tokens * 0.7:
                output.append("⚠️ ДРУГИЕ ПРОБЛЕМЫ:")
                for log in other_logs[:5]:
                    output.append(f"• {log.get('service', 'N/A')}: {log.get('error_code', 'N/A')} - {log.get('message', 'N/A')[:80]}...")
            
            return "\n".join(output)

    def _get_metrics(self, from_timestamp: int, to_timestamp: int) -> Dict[str, Any]:
        """Получает только ключевые поля метрик из Datadog API - максимально упрощенно"""
        try:
            # Только 3 самые важные метрики
            essential_metrics = [
                "avg:system.cpu.user{*}",      # CPU usage
                "avg:system.mem.used{*}",      # Memory usage  
                "sum:trace.servlet.request.errors{*}"  # Error count
            ]
            
            results = {"series": []}
            
            for metric_query in essential_metrics:
                url = f"{self.API_BASE}/api/v1/query"
                params = {
                    "from": from_timestamp,
                    "to": to_timestamp,
                    "query": metric_query,
                }
                
                response = requests.get(url, headers=self.HEADERS, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Извлекаем только ключевые поля согласно структуре JSON
                    if data.get("series"):
                        series_data = data["series"][0]
                        
                        # Упрощенная структура - только нужные поля
                        simplified_metric = {
                            "query": data.get("query", metric_query),           # Запрос
                            "from_date": data.get("from_date"),                 # Начальная дата
                            "to_date": data.get("to_date"),                     # Конечная дата
                            "metric": series_data.get("metric"),               # Имя метрики
                            "pointlist": series_data.get("pointlist", []),     # Массив точек [timestamp, value]
                            "unit": series_data.get("unit", [{"family": "general", "name": "unit"}])  # Единица измерения
                        }
                        
                        results["series"].append(simplified_metric)
                        
                else:
                    self.logger.warning(f"Не удалось получить метрику {metric_query}: {response.status_code}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении метрик: {e}")
            return {"series": []}
    
    def _get_logs(self, from_timestamp: int, to_timestamp: int) -> Dict[str, Any]:
        """Получает логи из Datadog API v2 с фильтром service:auarai AND env:prod за последние 100 часов"""
        try:
            url = f"{self.API_BASE}/api/v2/logs/events/search"
            
            # Используем фиксированный интервал - последние 100 часов
            body = {
                "filter": {
                    "query": "service:auarai AND env:prod",  # Конкретный фильтр как в curl
                    "from": "now-100h",                      # Последние 100 часов
                    "to": "now"                              # До текущего момента
                },
                "page": {"limit": 10},                       # Лимит 10 записей как в curl
                "sort": "timestamp"                          # Сортировка по timestamp как в curl
            }
            
            response = requests.post(url, headers=self.HEADERS, json=body, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Извлекаем только ключевые поля из JSON ответа API v2
                simplified_logs = {
                    "data": [],
                    "meta": data.get("meta", {}),
                    "links": data.get("links", {})
                }
                
                # Обрабатываем каждый лог-событие
                for log_event in data.get("data", []):
                    # Извлекаем только необходимые поля
                    simplified_log = {
                        "id": log_event.get("id"),                                    # ID события
                        "type": log_event.get("type"),                                # Тип события
                        "attributes": {
                            "timestamp": log_event.get("attributes", {}).get("timestamp"),     # Временная метка
                            "message": log_event.get("attributes", {}).get("message"),         # Сообщение лога
                            "status": log_event.get("attributes", {}).get("status"),           # Статус (INFO, ERROR, etc.)
                            "service": log_event.get("attributes", {}).get("service"),         # Сервис
                            "host": log_event.get("attributes", {}).get("host"),               # Хост
                            "tags": log_event.get("attributes", {}).get("tags", [])            # Теги
                        }
                    }
                    
                    simplified_logs["data"].append(simplified_log)
                
                return simplified_logs
                
            else:
                self.logger.warning(f"Не удалось получить логи: {response.status_code}")
                return {"data": [], "meta": {}, "links": {}}
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении логов: {e}")
            return {"data": [], "meta": {}, "links": {}}
    
    def _save_data(self, collected_data: Dict[str, Any]) -> bool:
        """
        Сохранить собранные данные в файл
        Теперь работает только с реальными данными из Datadog API
        """
        try:
            # Создаем структуру данных для сохранения
            data_to_save = {
                "server_logs": collected_data.get("logs", []),
                "server_metrics": collected_data.get("metrics", []),
                "collection_metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "total_logs": len(collected_data.get("logs", [])),
                    "total_metrics": len(collected_data.get("metrics", [])),
                    "data_source": "datadog_api" if self.datadog_client else "no_data",
                    "collection_stats": self.collection_stats
                }
            }
            
            # Добавляем дополнительные данные если есть
            if "additional_data" in collected_data:
                data_to_save.update(collected_data["additional_data"])
            
            # Определяем путь для сохранения (теперь в папке data вместо mock_data)
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
            os.makedirs(data_dir, exist_ok=True)
            
            save_path = os.path.join(data_dir, 'collected_data.json')
            
            # Сохраняем данные
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            
            print(f"[DataAgent] Данные сохранены в {save_path}")
            print(f"[DataAgent] Сохранено логов: {len(collected_data.get('logs', []))}, метрик: {len(collected_data.get('metrics', []))}")
            
            return True
            
        except Exception as e:
            print(f"[DataAgent] Ошибка сохранения данных: {str(e)}")
            return False
    
    def extract_error_logs(self, 
                          service: Optional[str] = None, 
                          error_level: Optional[str] = None,
                          error_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Extract error logs from Datadog API (no mock data)
        Returns empty list if Datadog is not available
        """
        if not self.datadog_client:
            print("[DataAgent] Datadog клиент недоступен для получения логов")
            return []
        
        try:
            # Используем синхронную обертку для асинхронного метода
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Получаем логи за последний час
            logs_data = loop.run_until_complete(
                self.datadog_client.get_logs(hours_back=1, limit=100)
            )
            
            filtered_logs = []
            logs = logs_data.get("data", [])
            
            for log in logs:
                # Применяем фильтры
                if service and log.get("attributes", {}).get("service") != service:
                    continue
                if error_level and log.get("attributes", {}).get("status") != error_level:
                    continue
                if error_code and str(error_code) not in str(log.get("attributes", {}).get("message", "")):
                    continue
                
                # Преобразуем в стандартный формат
                formatted_log = {
                    "timestamp": log.get("attributes", {}).get("timestamp"),
                    "service": log.get("attributes", {}).get("service", "unknown"),
                    "level": log.get("attributes", {}).get("status", "INFO"),
                    "message": log.get("attributes", {}).get("message", ""),
                    "source": "datadog_api"
                }
                
                if error_code:
                    formatted_log["error_code"] = error_code
                
                filtered_logs.append(formatted_log)
            
            loop.close()
            return filtered_logs
            
        except Exception as e:
            print(f"[DataAgent] Ошибка получения логов из Datadog: {str(e)}")
            return []
    
    def extract_metrics(self, 
                       service: Optional[str] = None,
                       metric_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Extract server metrics from Datadog API (no mock data)
        Returns empty list if Datadog is not available
        """
        if not self.datadog_client:
            print("[DataAgent] Datadog клиент недоступен для получения метрик")
            return []
        
        try:
            # Используем синхронную обертку для асинхронного метода
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Получаем системные метрики за последний час
            metrics_data = loop.run_until_complete(
                self.datadog_client.get_system_metrics(hours_back=1)
            )
            
            filtered_metrics = []
            
            for metric in metrics_data:
                # Применяем фильтры
                metric_name = metric.get("metric_name", "")
                
                if service and service not in metric_name:
                    continue
                
                if metric_type and metric_type.lower() not in metric_name.lower():
                    continue
                
                # Преобразуем в стандартный формат
                formatted_metric = {
                    "timestamp": metric.get("timestamp"),
                    "service": service or "system",
                    "metric_name": metric_name,
                    "value": metric.get("value"),
                    "unit": metric.get("unit", ""),
                    "source": "datadog_api"
                }
                
                if metric_type:
                    formatted_metric["metric_type"] = metric_type
                
                filtered_metrics.append(formatted_metric)
            
            loop.close()
            return filtered_metrics
            
        except Exception as e:
            print(f"[DataAgent] Ошибка получения метрик из Datadog: {str(e)}")
            return []
    
    def get_critical_errors(self) -> List[Dict[str, Any]]:
        """Get all critical and error level logs"""
        return self.extract_error_logs(error_level="CRITICAL") + \
               self.extract_error_logs(error_level="ERROR")
    
    async def get_available_metrics_list(self) -> List[str]:
        """Получение списка доступных метрик из Datadog"""
        if self.datadog_client:
            try:
                metrics_data = await self.datadog_client.get_available_metrics()
                # Извлекаем только имена метрик
                metric_names = []
                for metric in metrics_data:
                    if isinstance(metric, dict) and 'id' in metric:
                        metric_names.append(metric['id'])
                    elif isinstance(metric, dict) and 'attributes' in metric:
                        # Альтернативная структура ответа
                        name = metric.get('attributes', {}).get('name')
                        if name:
                            metric_names.append(name)
                
                return metric_names[:50]  # Ограничиваем количество для тестирования
                
            except Exception as e:
                print(f"Ошибка при получении списка метрик: {str(e)}")
                return []
        else:
            return []

    async def get_metrics(self, service: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Получение метрик системы через Datadog или моковые данные"""
        if self.datadog_client:
            try:
                # Получаем системные метрики из Datadog
                metrics = await self.datadog_client.get_system_metrics(hours_back=1)
                
                # Фильтруем по сервису если указан
                if service:
                    metrics = [m for m in metrics if service.lower() in m.get('service', '').lower()]
                
                # Ограничиваем количество
                return metrics[:limit]
                
            except DatadogAuthenticationError as e:
                raise Exception(f"Ошибка аутентификации Datadog: {str(e)}")
            except DatadogConnectionError as e:
                raise Exception(f"Ошибка подключения к Datadog: {str(e)}")
            except DatadogAPIError as e:
                raise Exception(f"Ошибка Datadog API: {str(e)}")
            except Exception as e:
                raise Exception(f"Неожиданная ошибка при получении метрик из Datadog: {str(e)}")
        else:
            # Используем моковые данные если Datadog недоступен
            return self.extract_metrics(service=service)[:limit]
    
    async def get_service_summary(self, service: str) -> Dict[str, Any]:
        """Get comprehensive summary for a specific service"""
        service_logs = self.extract_error_logs(service=service)
        
        # Получаем метрики через обновленный метод get_metrics
        try:
            service_metrics = await self.get_metrics(service=service, limit=5)
        except Exception as e:
            # Если ошибка с Datadog, re-raise для передачи пользователю
            raise e
        
        # Count errors by type
        error_counts = {}
        for log in service_logs:
            error_code = log.get("error_code", "UNKNOWN")
            error_counts[error_code] = error_counts.get(error_code, 0) + 1
        
        # Get latest metrics
        latest_metrics = service_metrics[-1] if service_metrics else None
        
        return {
            "service": service,
            "total_errors": len(service_logs),
            "error_breakdown": error_counts,
            "recent_errors": service_logs[-3:] if service_logs else [],
            "latest_metrics": latest_metrics,
            "timestamp": datetime.now().isoformat()
        }
    
    def format_data_for_analysis(self, 
                                logs: List[Dict[str, Any]], 
                                metrics: List[Dict[str, Any]], 
                                context: str = "analysis") -> str:
        """Format extracted data for LLM analysis using intelligent formatter"""
        data = {"logs": logs, "metrics": metrics}
        return self.formatter.smart_format(data, context)
    
    def get_error_logs(self, service: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get error logs for analysis - required method for orchestrator"""
        error_logs = self.extract_error_logs(service=service, error_level="ERROR")
        critical_logs = self.extract_error_logs(service=service, error_level="CRITICAL")
        
        # Combine and sort by timestamp (most recent first)
        all_error_logs = error_logs + critical_logs
        all_error_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return all_error_logs[:limit]

    def execute_query(self, query: str) -> Dict[str, Any]:
        """Выполняет упрощенный запрос к Datadog API за последний час - только ключевые метрики и критические логи"""
        try:
            # Определяем временной интервал - последний час
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=1)
            
            # Конвертируем в epoch секунды
            from_timestamp = self._epoch_seconds(start_time)
            to_timestamp = self._epoch_seconds(end_time)
            
            print(f"[DataAgent] Упрощенный запрос данных за период: {start_time.strftime('%H:%M:%S')} - {end_time.strftime('%H:%M:%S')}")
            
            # Всегда получаем только ключевые данные (3 метрики + 5 критических логов)
            metrics_data = self._get_metrics(from_timestamp, to_timestamp)
            logs_data = self._get_logs(from_timestamp, to_timestamp)
            
            raw_data = {
                "metrics": metrics_data,
                "logs": logs_data
            }
            
            # Проверяем, получены ли данные
            if not metrics_data and not logs_data:
                return {
                    "status": "no_data",
                    "message": f"За последний час не удалось получить ключевые данные",
                    "timestamp": datetime.now().isoformat(),
                    "query": query,
                    "period": f"{start_time.strftime('%H:%M:%S')} - {end_time.strftime('%H:%M:%S')}"
                }
            
            # Используем упрощенный форматтер
            formatted_data = self.formatter.smart_format(raw_data, "minimal")
            
            result = {
                "status": "success",
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "period": f"{start_time.strftime('%H:%M:%S')} - {end_time.strftime('%H:%M:%S')}",
                "data_type": "essential_only",
                "metrics_count": len(metrics_data.get("series", [])) if metrics_data else 0,
                "logs_count": len(logs_data.get("logs", [])) if logs_data else 0,
                "formatted_data": formatted_data
            }
            
            print(f"[DataAgent] Получено {result['metrics_count']} метрик и {result['logs_count']} критических логов")
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка при выполнении упрощенного запроса: {e}")
            return {
                "status": "error",
                "message": f"Ошибка при получении ключевых данных: {str(e)}",
                "query": query,
                "timestamp": datetime.now().isoformat()
            }

        def format_data(self, data: Dict[str, Any], data_type: str = "combined") -> str:
            """
            Форматирует данные из Datadog API для анализа
            """
            if data_type == "metrics":
                return self._format_datadog_metrics(data)
            elif data_type == "logs":
                return self._format_datadog_logs(data)
            elif data_type == "combined":
                return self._format_combined_datadog_data(data)
            else:
                return self._format_raw_data(data)
        
        def _format_datadog_metrics(self, metrics_data: Dict[str, Any]) -> str:
            """Форматирует метрики из Datadog"""
            output = ["=== МЕТРИКИ DATADOG ===\n"]
            
            if not metrics_data or "series" not in metrics_data:
                output.append("❌ Метрики не найдены за указанный период")
                return "\n".join(output)
            
            series = metrics_data.get("series", [])
            if not series:
                output.append("❌ Данные метрик отсутствуют")
                return "\n".join(output)
            
            output.append("📊 СИСТЕМНЫЕ МЕТРИКИ:")
            for serie in series[:5]:  # Ограничиваем количество серий
                metric_name = serie.get("metric", "unknown")
                points = serie.get("pointlist", [])
                
                if points:
                    # Берем последние значения
                    latest_points = points[-3:] if len(points) > 3 else points
                    output.append(f"\n🔹 {metric_name}:")
                    
                    for point in latest_points:
                        if len(point) >= 2:
                            timestamp = datetime.fromtimestamp(point[0] / 1000).strftime("%H:%M:%S")
                            value = round(point[1], 2) if isinstance(point[1], (int, float)) else point[1]
                            output.append(f"  {timestamp}: {value}")
            
            return "\n".join(output)
        
        def _format_datadog_logs(self, logs_data: Dict[str, Any]) -> str:
            """Форматирует логи из Datadog"""
            output = ["=== ЛОГИ DATADOG ===\n"]
            
            if not logs_data or "data" not in logs_data:
                output.append("❌ Логи не найдены за указанный период")
                return "\n".join(output)
            
            logs = logs_data.get("data", [])
            if not logs:
                output.append("❌ Данные логов отсутствуют")
                return "\n".join(output)
            
            output.append(f"📝 НАЙДЕНО ЛОГОВ: {len(logs)}")
            
            # Группируем по уровням
            levels_count = {}
            for log in logs:
                attributes = log.get("attributes", {})
                level = attributes.get("status", "unknown")
                levels_count[level] = levels_count.get(level, 0) + 1
            
            if levels_count:
                output.append("\n📊 РАСПРЕДЕЛЕНИЕ ПО УРОВНЯМ:")
                for level, count in sorted(levels_count.items()):
                    output.append(f"  {level}: {count}")
            
            # Показываем последние логи
            output.append("\n📋 ПОСЛЕДНИЕ ЗАПИСИ:")
            for log in logs[:10]:  # Показываем первые 10
                attributes = log.get("attributes", {})
                timestamp = attributes.get("timestamp", "N/A")
                if timestamp != "N/A":
                    try:
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        timestamp = dt.strftime("%H:%M:%S")
                    except:
                        pass
                
                service = attributes.get("service", "unknown")
                status = attributes.get("status", "unknown")
                message = attributes.get("message", "")[:100]
                
                output.append(f"• {timestamp} | {service} | {status}")
                if message:
                    output.append(f"  {message}...")
            
            return "\n".join(output)
        
        def _format_combined_datadog_data(self, data: Dict[str, Any]) -> str:
            """Форматирует комбинированные данные из Datadog"""
            output = ["=== СВОДКА DATADOG ===\n"]
            
            metrics_data = data.get("metrics", {})
            logs_data = data.get("logs", {})
            
            # Краткая сводка по метрикам
            if metrics_data and "series" in metrics_data:
                series = metrics_data.get("series", [])
                output.append(f"📊 МЕТРИКИ: {len(series)} серий данных")
                
                if series:
                    latest_serie = series[0]
                    points = latest_serie.get("pointlist", [])
                    if points:
                        latest_point = points[-1]
                        if len(latest_point) >= 2:
                            timestamp = datetime.fromtimestamp(latest_point[0] / 1000).strftime("%H:%M:%S")
                            value = round(latest_point[1], 2) if isinstance(latest_point[1], (int, float)) else latest_point[1]
                            metric_name = latest_serie.get("metric", "unknown")
                            output.append(f"  Последнее значение {metric_name}: {value} ({timestamp})")
            else:
                output.append("📊 МЕТРИКИ: Данные отсутствуют")
            
            # Краткая сводка по логам
            if logs_data and "data" in logs_data:
                logs = logs_data.get("data", [])
                output.append(f"\n📝 ЛОГИ: {len(logs)} записей")
                
                if logs:
                    # Подсчет по статусам
                    status_count = {}
                    for log in logs:
                        status = log.get("attributes", {}).get("status", "unknown")
                        status_count[status] = status_count.get(status, 0) + 1
                    
                    status_summary = ", ".join([f"{status}: {count}" for status, count in status_count.items()])
                    output.append(f"  Распределение: {status_summary}")
            else:
                output.append("\n📝 ЛОГИ: Данные отсутствуют")
            
            return "\n".join(output)
        
        def _format_raw_data(self, data: Dict[str, Any]) -> str:
            """Базовое форматирование для неизвестных типов данных"""
            output = ["=== НЕОБРАБОТАННЫЕ ДАННЫЕ ===\n"]
            
            if isinstance(data, dict):
                for key, value in data.items():
                    output.append(f"{key}: {type(value).__name__}")
                    if isinstance(value, (list, dict)):
                        output.append(f"  Размер: {len(value) if hasattr(value, '__len__') else 'N/A'}")
            else:
                output.append(f"Тип данных: {type(data).__name__}")
            
            return "\n".join(output)

    async def collect_selective_data(self, data_requirements: list, target_services: list = None) -> dict:
        """
        Селективный сбор данных на основе требований из фазы планирования
        
        Args:
            data_requirements: список типов данных для сбора
            target_services: список целевых сервисов (опционально)
            
        Returns:
            dict: собранные данные по типам
        """
        collected_data = {}
        collection_errors = []
        successful_collections = []
        
        # Логирование начала селективного сбора
        print(f"[DataAgent] Начинаю селективный сбор данных: {data_requirements}")
        if target_services:
            print(f"[DataAgent] Целевые сервисы: {target_services}")
        
        # Проверяем доступность Datadog клиента
        datadog_available = self.datadog_client is not None
        print(f"[DataAgent] Datadog клиент доступен: {datadog_available}")
        
        # Сбор логов с ошибками
        if "error_logs" in data_requirements:
            try:
                print("[DataAgent] Собираю логи с ошибками...")
                error_logs = self.get_error_logs()
                collected_data["error_logs"] = error_logs
                print(f"[DataAgent] ✓ Собрано {len(error_logs)} записей логов с ошибками")
                successful_collections.append("error_logs")
            except Exception as e:
                error_msg = f"Не удалось собрать логи с ошибками: {str(e)}"
                print(f"[DataAgent] ✗ {error_msg}")
                collection_errors.append({"type": "error_logs", "error": error_msg})
                
        # Сбор метрик производительности
        if "performance_logs" in data_requirements:
            try:
                print("[DataAgent] Собираю логи производительности...")
                # Используем синхронную версию для совместимости
                metrics = self.extract_metrics()
                collected_data["performance_logs"] = metrics
                print(f"[DataAgent] ✓ Собрано {len(metrics)} записей логов производительности")
                successful_collections.append("performance_logs")
            except Exception as e:
                error_msg = f"Не удалось собрать логи производительности: {str(e)}"
                print(f"[DataAgent] ✗ {error_msg}")
                collection_errors.append({"type": "performance_logs", "error": error_msg})
                
        # Сбор CPU метрик
        if "cpu_metrics" in data_requirements:
            try:
                print("[DataAgent] Собираю CPU метрики...")
                if datadog_available:
                    # Попытка получить данные из Datadog
                    try:
                        cpu_metrics = await self.datadog_client.get_system_metrics(hours_back=1)
                        # Фильтруем только CPU метрики
                        cpu_only = [m for m in cpu_metrics if 'cpu' in m.get('metric_name', '').lower()]
                        collected_data["cpu_metrics"] = cpu_only
                        print(f"[DataAgent] ✓ Собрано {len(cpu_only)} CPU метрик из Datadog")
                        successful_collections.append("cpu_metrics")
                    except Exception as dd_error:
                        print(f"[DataAgent] Ошибка Datadog для CPU метрик: {str(dd_error)}")
                        # Fallback к mock данным
                        cpu_metrics = [m for m in self.extract_metrics() if 'cpu' in m.get('metric_name', '').lower()]
                        collected_data["cpu_metrics"] = cpu_metrics
                        print(f"[DataAgent] ✓ Fallback: собрано {len(cpu_metrics)} CPU метрик из mock данных")
                        successful_collections.append("cpu_metrics")
                else:
                    # Используем mock данные
                    cpu_metrics = [m for m in self.extract_metrics() if 'cpu' in m.get('metric_name', '').lower()]
                    collected_data["cpu_metrics"] = cpu_metrics
                    print(f"[DataAgent] ✓ Собрано {len(cpu_metrics)} CPU метрик из mock данных")
                    successful_collections.append("cpu_metrics")
            except Exception as e:
                error_msg = f"Не удалось собрать CPU метрики: {str(e)}"
                print(f"[DataAgent] ✗ {error_msg}")
                collection_errors.append({"type": "cpu_metrics", "error": error_msg})
                
        # Сбор Memory метрик
        if "memory_metrics" in data_requirements:
            try:
                print("[DataAgent] Собираю Memory метрики...")
                if datadog_available:
                    # Попытка получить данные из Datadog
                    try:
                        memory_metrics = await self.datadog_client.get_system_metrics(hours_back=1)
                        # Фильтруем только Memory метрики
                        memory_only = [m for m in memory_metrics if 'memory' in m.get('metric_name', '').lower() or 'mem' in m.get('metric_name', '').lower()]
                        collected_data["memory_metrics"] = memory_only
                        print(f"[DataAgent] ✓ Собрано {len(memory_only)} Memory метрик из Datadog")
                        successful_collections.append("memory_metrics")
                    except Exception as dd_error:
                        print(f"[DataAgent] Ошибка Datadog для Memory метрик: {str(dd_error)}")
                        # Fallback к mock данным
                        memory_metrics = [m for m in self.extract_metrics() if 'memory' in m.get('metric_name', '').lower() or 'mem' in m.get('metric_name', '').lower()]
                        collected_data["memory_metrics"] = memory_metrics
                        print(f"[DataAgent] ✓ Fallback: собрано {len(memory_metrics)} Memory метрик из mock данных")
                        successful_collections.append("memory_metrics")
                else:
                    # Используем mock данные
                    memory_metrics = [m for m in self.extract_metrics() if 'memory' in m.get('metric_name', '').lower() or 'mem' in m.get('metric_name', '').lower()]
                    collected_data["memory_metrics"] = memory_metrics
                    print(f"[DataAgent] ✓ Собрано {len(memory_metrics)} Memory метрик из mock данных")
                    successful_collections.append("memory_metrics")
            except Exception as e:
                error_msg = f"Не удалось собрать Memory метрики: {str(e)}"
                print(f"[DataAgent] ✗ {error_msg}")
                collection_errors.append({"type": "memory_metrics", "error": error_msg})
                
        # Сбор Disk метрик
        if "disk_metrics" in data_requirements:
            try:
                print("[DataAgent] Собираю Disk метрики...")
                if datadog_available:
                    # Попытка получить данные из Datadog
                    try:
                        disk_metrics = await self.datadog_client.get_system_metrics(hours_back=1)
                        # Фильтруем только Disk метрики
                        disk_only = [m for m in disk_metrics if 'disk' in m.get('metric_name', '').lower() or 'io' in m.get('metric_name', '').lower()]
                        collected_data["disk_metrics"] = disk_only
                        print(f"[DataAgent] ✓ Собрано {len(disk_only)} Disk метрик из Datadog")
                        successful_collections.append("disk_metrics")
                    except Exception as dd_error:
                        print(f"[DataAgent] Ошибка Datadog для Disk метрик: {str(dd_error)}")
                        # Fallback к mock данным
                        disk_metrics = [m for m in self.extract_metrics() if 'disk' in m.get('metric_name', '').lower() or 'io' in m.get('metric_name', '').lower()]
                        collected_data["disk_metrics"] = disk_metrics
                        print(f"[DataAgent] ✓ Fallback: собрано {len(disk_metrics)} Disk метрик из mock данных")
                        successful_collections.append("disk_metrics")
                else:
                    # Используем mock данные
                    disk_metrics = [m for m in self.extract_metrics() if 'disk' in m.get('metric_name', '').lower() or 'io' in m.get('metric_name', '').lower()]
                    collected_data["disk_metrics"] = disk_metrics
                    print(f"[DataAgent] ✓ Собрано {len(disk_metrics)} Disk метрик из mock данных")
                    successful_collections.append("disk_metrics")
            except Exception as e:
                error_msg = f"Не удалось собрать Disk метрики: {str(e)}"
                print(f"[DataAgent] ✗ {error_msg}")
                collection_errors.append({"type": "disk_metrics", "error": error_msg})
                
        # Сбор метрик производительности (старый код для совместимости)
        if "metrics" in data_requirements:
            try:
                print("[DataAgent] Собираю метрики производительности...")
                # Используем синхронную версию для совместимости
                metrics = self.extract_metrics()
                collected_data["metrics"] = metrics
                print(f"[DataAgent] ✓ Собрано {len(metrics)} записей метрик")
                successful_collections.append("metrics")
            except Exception as e:
                error_msg = f"Не удалось собрать метрики: {str(e)}"
                print(f"[DataAgent] ✗ {error_msg}")
                collection_errors.append({"type": "metrics", "error": error_msg})
                
        # Сбор критических ошибок
        if "critical_errors" in data_requirements:
            try:
                print("[DataAgent] Собираю критические ошибки...")
                critical_errors = self.get_critical_errors()
                collected_data["critical_errors"] = critical_errors
                print(f"[DataAgent] ✓ Собрано {len(critical_errors)} критических ошибок")
                successful_collections.append("critical_errors")
            except Exception as e:
                error_msg = f"Не удалось собрать критические ошибки: {str(e)}"
                print(f"[DataAgent] ✗ {error_msg}")
                collection_errors.append({"type": "critical_errors", "error": error_msg})
                
        # Сбор сводки по сервисам
        if "service_summary" in data_requirements:
            try:
                print("[DataAgent] Собираю сводку по сервисам...")
                if target_services:
                    # Собираем данные для каждого целевого сервиса
                    service_summaries = {}
                    for service in target_services:
                        try:
                            # Используем синхронную версию для совместимости
                            summary = {
                                "service": service,
                                "error_logs": self.extract_error_logs(service=service),
                                "metrics": self.extract_metrics(service=service),
                                "timestamp": datetime.now().isoformat()
                            }
                            service_summaries[service] = summary
                            print(f"[DataAgent] ✓ Собрана сводка для сервиса {service}")
                        except Exception as e:
                            error_msg = f"Ошибка сбора данных для сервиса {service}: {str(e)}"
                            print(f"[DataAgent] ✗ {error_msg}")
                            collection_errors.append({"type": f"service_summary_{service}", "error": error_msg})
                    collected_data["service_summary"] = service_summaries
                else:
                    # Используем сервис по умолчанию
                    default_summary = {
                        "service": "api",
                        "error_logs": self.extract_error_logs(service="api"),
                        "metrics": self.extract_metrics(service="api"),
                        "timestamp": datetime.now().isoformat()
                    }
                    collected_data["service_summary"] = default_summary
                    print(f"[DataAgent] ✓ Собрана сводка для сервиса по умолчанию (api)")
                successful_collections.append("service_summary")
            except Exception as e:
                error_msg = f"Не удалось собрать сводку по сервисам: {str(e)}"
                print(f"[DataAgent] ✗ {error_msg}")
                collection_errors.append({"type": "service_summary", "error": error_msg})
        
        # Возвращаем результат с детальной статистикой
        result = {
            "data": collected_data,
            "collection_stats": {
                "requested_types": data_requirements,
                "successful_collections": successful_collections,
                "failed_collections": [err["type"] for err in collection_errors],
                "collection_errors": collection_errors,
                "has_errors": len(collection_errors) > 0,
                "success_rate": round((len(successful_collections) / len(data_requirements)) * 100, 1) if data_requirements else 100.0,
                "total_requested": len(data_requirements),
                "total_successful": len(successful_collections),
                "total_failed": len(collection_errors)
            }
        }
        
        # Сохраняем собранные данные в файл
        if collected_data:  # Сохраняем только если есть данные
            save_success = self._save_data(collected_data)
            result["collection_stats"]["data_saved"] = save_success
        else:
            result["collection_stats"]["data_saved"] = False
            print("[DataAgent] Нет данных для сохранения")
        
        print(f"[DataAgent] Селективный сбор завершен. Успешно: {len(successful_collections)}/{len(data_requirements)}")
        return result

    def get_data_type_info(self) -> dict:
        """
        Возвращает информацию о доступных типах данных
        
        Returns:
            dict: описание доступных типов данных
        """
        return {
            "available_data_types": {
                "error_logs": {
                    "description": "Логи с ошибками и критическими событиями",
                    "typical_size": "средний",
                    "collection_time": "быстро"
                },
                "metrics": {
                    "description": "Метрики производительности системы",
                    "typical_size": "большой",
                    "collection_time": "средне"
                },
                "critical_errors": {
                    "description": "Только критические ошибки",
                    "typical_size": "малый",
                    "collection_time": "быстро"
                },
                "service_summary": {
                    "description": "Сводная информация по конкретному сервису",
                    "typical_size": "малый",
                    "collection_time": "быстро"
                }
            },
            "supported_services": ["api", "database", "cache", "auth", "notification"],
            "collection_strategies": {
                "performance_analysis": ["metrics", "service_summary"],
                "error_investigation": ["error_logs", "critical_errors"],
                "service_health_check": ["service_summary", "error_logs"],
                "full_system_analysis": ["error_logs", "metrics", "critical_errors", "service_summary"]
            }
        }