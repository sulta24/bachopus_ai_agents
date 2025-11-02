"""
Утилиты для безопасной работы с API Datadog
Основаны на реальной структуре ответов API
"""

from typing import Dict, List, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)

def safe_iterate_dict(data: Any, operation_name: str = "неизвестная операция") -> Dict[str, Any]:
    """
    Безопасная итерация по словарю с проверкой типов
    
    Args:
        data: Данные для итерации
        operation_name: Название операции для логирования
        
    Returns:
        Dict[str, Any]: Словарь для безопасной итерации или пустой словарь
    """
    # Детальное логирование типов данных для отладки
    logger.debug(f"safe_iterate_dict вызвана для операции '{operation_name}': тип данных = {type(data)}, значение = {str(data)[:200]}...")
    
    if isinstance(data, dict):
        logger.debug(f"Операция '{operation_name}': корректный словарь с {len(data)} элементами")
        return data
    elif isinstance(data, list):
        logger.warning(f"Получен список вместо словаря для операции '{operation_name}': {type(data)}, длина = {len(data)}")
        logger.debug(f"Содержимое списка: {str(data)[:500]}...")
        return {}
    elif data is None:
        logger.warning(f"Получен None для операции '{operation_name}'")
        return {}
    else:
        logger.warning(f"Неожиданный тип данных для операции '{operation_name}': {type(data)}")
        logger.debug(f"Значение неожиданного типа: {str(data)[:200]}...")
        return {}

def parse_datadog_timeseries_response(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Парсинг ответа временных рядов от Datadog API v1
    
    Args:
        response_data: Сырой ответ от API
        
    Returns:
        Dict[str, Any]: Нормализованные данные
    """
    try:
        # Проверяем базовую структуру ответа
        if not isinstance(response_data, dict):
            logger.error(f"Ответ API не является словарем: {type(response_data)}")
            return {"series": [], "error": "Некорректный формат ответа"}
        
        # Извлекаем основные поля
        status = response_data.get("status", "unknown")
        res_type = response_data.get("res_type", "unknown")
        query = response_data.get("query", "")
        
        # Логируем структуру для отладки
        logger.info(f"Datadog API ответ: status={status}, res_type={res_type}, query={query}")
        
        # Проверяем статус
        if status != "ok":
            error_msg = response_data.get("message", "Неизвестная ошибка API")
            logger.error(f"API вернул ошибку: {error_msg}")
            return {"series": [], "error": error_msg}
        
        # Извлекаем серии данных
        series_list = response_data.get("series", [])
        if not isinstance(series_list, list):
            logger.error(f"Поле 'series' не является списком: {type(series_list)}")
            return {"series": [], "error": "Некорректный формат серий данных"}
        
        formatted_series = []
        for series in series_list:
            if not isinstance(series, dict):
                logger.warning(f"Серия не является словарем: {type(series)}")
                continue
                
            formatted_series.append(parse_single_series(series))
        
        return {
            "status": status,
            "query": query,
            "from_date": response_data.get("from_date"),
            "to_date": response_data.get("to_date"),
            "series": formatted_series,
            "error": None
        }
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге ответа Datadog: {str(e)}")
        return {"series": [], "error": f"Ошибка парсинга: {str(e)}"}

def parse_single_series(series_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Парсинг одной серии данных из ответа Datadog
    
    Args:
        series_data: Данные одной серии
        
    Returns:
        Dict[str, Any]: Нормализованная серия
    """
    try:
        # Извлекаем основные поля
        metric_name = series_data.get("metric", "unknown")
        display_name = series_data.get("display_name", metric_name)
        scope = series_data.get("scope", "*")
        
        # Обрабатываем единицы измерения
        unit_info = extract_unit_info(series_data.get("unit", []))
        
        # Обрабатываем точки данных
        pointlist = series_data.get("pointlist", [])
        formatted_points = []
        
        if isinstance(pointlist, list):
            for point in pointlist:
                if isinstance(point, list) and len(point) >= 2:
                    timestamp, value = point[0], point[1]
                    if timestamp is not None and value is not None:
                        try:
                            formatted_points.append([
                                int(float(timestamp)),  # Конвертируем в int timestamp
                                float(value)            # Конвертируем в float value
                            ])
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Некорректная точка данных: {point}, ошибка: {e}")
                            continue
        
        return {
            "metric": metric_name,
            "display_name": display_name,
            "scope": scope,
            "points": formatted_points,
            "unit": unit_info,
            "interval": series_data.get("interval", 0),
            "length": len(formatted_points),
            "start": series_data.get("start"),
            "end": series_data.get("end"),
            "aggr": series_data.get("aggr", "unknown")
        }
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге серии: {str(e)}")
        return {
            "metric": "error",
            "display_name": "Ошибка парсинга",
            "scope": "*",
            "points": [],
            "unit": {"name": "unknown", "symbol": ""},
            "error": str(e)
        }

def extract_unit_info(unit_data: List[Any]) -> Dict[str, str]:
    """
    Извлечение информации о единицах измерения
    
    Args:
        unit_data: Данные о единицах из API
        
    Returns:
        Dict[str, str]: Информация о единицах
    """
    try:
        if isinstance(unit_data, list) and len(unit_data) > 0:
            unit_obj = unit_data[0]
            if isinstance(unit_obj, dict):
                return {
                    "name": unit_obj.get("name", "unknown"),
                    "symbol": unit_obj.get("short_name", ""),
                    "family": unit_obj.get("family", "unknown"),
                    "scale_factor": unit_obj.get("scale_factor", 1.0)
                }
        
        return {"name": "unknown", "symbol": "", "family": "unknown", "scale_factor": 1.0}
        
    except Exception as e:
        logger.warning(f"Ошибка при извлечении единиц измерения: {e}")
        return {"name": "unknown", "symbol": "", "family": "unknown", "scale_factor": 1.0}

def parse_datadog_metrics_list(response_data: Union[Dict[str, Any], List[str]]) -> List[Dict[str, str]]:
    """
    Парсинг списка доступных метрик от Datadog API
    
    Args:
        response_data: Ответ от API со списком метрик
        
    Returns:
        List[Dict[str, str]]: Список метрик в нормализованном формате
    """
    try:
        # Случай 1: Ответ в виде словаря с ключом 'metrics'
        if isinstance(response_data, dict):
            if "metrics" in response_data:
                metrics_list = response_data["metrics"]
                if isinstance(metrics_list, list):
                    return [{"id": metric, "name": metric} for metric in metrics_list if isinstance(metric, str)]
            
            # Случай 2: Словарь с другой структурой
            logger.warning(f"Неожиданная структура ответа метрик: {list(response_data.keys())}")
            return []
        
        # Случай 3: Прямой список метрик
        elif isinstance(response_data, list):
            return [{"id": metric, "name": metric} for metric in response_data if isinstance(metric, str)]
        
        # Случай 4: Неожиданный тип данных
        else:
            logger.error(f"Неожиданный тип ответа метрик: {type(response_data)}")
            return []
            
    except Exception as e:
        logger.error(f"Ошибка при парсинге списка метрик: {str(e)}")
        return []

def validate_datadog_response(response_data: Any, expected_fields: List[str] = None) -> bool:
    """
    Валидация ответа от Datadog API
    
    Args:
        response_data: Данные для валидации
        expected_fields: Ожидаемые поля (опционально)
        
    Returns:
        bool: True если данные валидны
    """
    try:
        if not isinstance(response_data, dict):
            logger.error(f"Ответ не является словарем: {type(response_data)}")
            return False
        
        # Проверяем базовые поля
        if expected_fields:
            missing_fields = [field for field in expected_fields if field not in response_data]
            if missing_fields:
                logger.warning(f"Отсутствуют ожидаемые поля: {missing_fields}")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при валидации ответа: {str(e)}")
        return False

def log_datadog_response_structure(data: Any, context: str = "response"):
    """Логирует структуру ответа Datadog для отладки"""
    # Убираем детальное логирование для продакшена
    pass

def safe_iterate_dict(data: Dict[str, Any], context: str = "data") -> Dict[str, Any]:
    """Безопасная итерация по словарю с обработкой ошибок"""
    try:
        if not isinstance(data, dict):
            print(f"❌ Ошибка: {context} не является словарем: {type(data)}")
            return {}
        return data
    except Exception as e:
        print(f"❌ Ошибка итерации по {context}: {str(e)}")
        return {}

def parse_datadog_metrics_list(raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Парсит список метрик из ответа Datadog API"""
    try:
        if not isinstance(raw_data, dict):
            return []
        
        metrics = raw_data.get('metrics', [])
        if not isinstance(metrics, list):
            return []
        
        return [{"name": metric} for metric in metrics if isinstance(metric, str)]
    except Exception as e:
        print(f"❌ Ошибка парсинга списка метрик: {str(e)}")
        return []

def parse_datadog_timeseries_response(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Парсит ответ временных рядов от Datadog API"""
    try:
        if not isinstance(raw_data, dict):
            return {"error": "Неверный формат данных", "series": []}
        
        series = raw_data.get('series', [])
        if not isinstance(series, list):
            return {"error": "Отсутствуют данные серий", "series": []}
        
        return {"series": series, "status": "ok"}
    except Exception as e:
        print(f"❌ Ошибка парсинга временных рядов: {str(e)}")
        return {"error": str(e), "series": []}

def validate_datadog_response(data: Any, expected_keys: List[str] = None) -> bool:
    """Валидирует ответ от Datadog API"""
    try:
        if not isinstance(data, dict):
            return False
        
        if expected_keys:
            return all(key in data for key in expected_keys)
        
        return True
    except Exception as e:
        print(f"❌ Ошибка валидации ответа Datadog: {str(e)}")
        return False