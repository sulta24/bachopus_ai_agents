from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
import os
import logging
from datetime import datetime
from colorama import Fore, Style, init

from core.orchestrator import AIOrchestrator
from core.reasoning_state import ReasoningState
from core.backend_client import BackendClient, BackendClientError, ServiceNotFoundError, SessionNotFoundError
from core.context_formatter import ContextFormatter

# Создаем экземпляр FastAPI приложения
app = FastAPI(
    title="AI Orchestrator",
    description="Система оркестрации AI агентов с трехфазным рассуждением",
    version="2.0.0",
    # Настройка схемы безопасности для Swagger UI
    openapi_tags=[
        {
            "name": "orchestration",
            "description": "Операции оркестрации AI агентов",
        },
        {
            "name": "system",
            "description": "Системные операции и мониторинг",
        }
    ]
)

# Добавляем схему безопасности в OpenAPI
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Введите Bearer токен для авторизации. Формат: Bearer <ваш_токен>"
        }
    }
    
    # Добавляем требования безопасности для защищенных эндпоинтов
    for path, path_item in openapi_schema["paths"].items():
        for method, operation in path_item.items():
            if method.lower() in ["get", "post", "put", "delete", "patch"]:
                # Добавляем безопасность только для эндпоинта /orchestrate
                if path == "/orchestrate":
                    operation["security"] = [{"BearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Схема безопасности для Bearer токена
security = HTTPBearer()

# Инициализация оркестратора (API ключ будет загружен из переменных окружения)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
# Инициализация оркестратора без ключей (они будут переданы в каждом запросе)
orchestrator = None

# Инициализация клиентов для работы с бекендом
backend_client = BackendClient()
context_formatter = ContextFormatter()

# Инициализация colorama для цветного вывода
init(autoreset=True)

# Настройка логирования
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("AI_Orchestrator")

# Модели данных
class AgentInfo(BaseModel):
    name: str
    description: str
    status: str

class ContextAnalysisRequest(BaseModel):
    service_id: str
    session_id: str
    prompt: str
    include_trace: bool = True

class ContextAnalysisResponse(BaseModel):
    session_id: str
    service_id: str
    prompt: str
    answer: str
    status: str
    execution_time: float

# Корневой эндпоинт
@app.get("/", tags=["system"], summary="Корневой эндпоинт")
async def root():
    return {
        "message": "Добро пожаловать в AI Orchestrator v2.0!",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "features": [
            "Трехфазное рассуждение (Planning, Execution, Feedback)",
            "Интеграция с Google Gemini AI",
            "Цветная трассировка в консоли",
            "Анализ логов и метрик системы"
        ],
        "endpoints": [
            "/health - проверка состояния сервера",
            "/agents - список доступных агентов", 
            "/analyze - новый эндпоинт для AI анализа",
            "/orchestrate - основной эндпоинт для оркестрации",
            "/mock-data - получение тестовых данных",
            "/docs - документация API"
        ]
    }

# Проверка состояния сервера
@app.get("/health", tags=["system"], summary="Проверка состояния сервиса")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "AI Orchestrator"
    }

# Получение списка доступных агентов
@app.get("/agents", response_model=List[AgentInfo], tags=["system"], summary="Получить список доступных агентов")
async def get_agents():
    agents = [
        AgentInfo(
            name="data_agent",
            description="Агент для работы с данными логов и метрик",
            status="available"
        ),
        AgentInfo(
            name="protocol_agent", 
            description="Агент для анализа по протоколам и генерации рекомендаций",
            status="available"
        ),
        AgentInfo(
            name="planning_agent",
            description="Агент планирования анализа (LLM)",
            status="available"
        ),
        AgentInfo(
            name="execution_agent",
            description="Агент выполнения анализа (LLM)",
            status="available"
        ),
        AgentInfo(
            name="feedback_agent",
            description="Агент обратной связи и рекомендаций (LLM)",
            status="available"
        )
    ]
    return agents

# Эндпоинт для оркестрации агентов с контекстом из бекенда
@app.post("/orchestrate", 
          response_model=ContextAnalysisResponse,
          tags=["orchestration"],
          summary="Оркестрация AI агентов",
          dependencies=[Depends(security)],
          responses={
              200: {"description": "Успешная обработка запроса"},
              401: {"description": "Неавторизованный доступ - неверный или отсутствующий Bearer токен"},
              404: {"description": "Сервис или сессия не найдены"},
              500: {"description": "Внутренняя ошибка сервера"}
          })
async def orchestrate(
    request: ContextAnalysisRequest, 
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Эндпоинт для оркестрации AI агентов с контекстом из бекенда
    
    ## Авторизация
    **Требует Bearer токен для аутентификации в заголовке Authorization.**
    
    Формат заголовка: `Authorization: Bearer <ваш_токен>`
    
    Токен используется для всех обратных вызовов к бекенду API и должен быть действительным
    для доступа к указанному сервису и сессии.
    
    ## Использование в Swagger UI
    1. Нажмите кнопку "Authorize" в правом верхнем углу
    2. Введите ваш Bearer токен в поле "Value"
    3. Нажмите "Authorize" для сохранения токена
    4. Токен будет автоматически добавляться ко всем запросам
    
    ## Пример curl запроса
    ```bash
    curl -X POST "http://localhost:8000/orchestrate" \\
         -H "Authorization: Bearer your_token_here" \\
         -H "Content-Type: application/json" \\
         -d '{
           "service_id": "your_service_id",
           "session_id": "your_session_id", 
           "prompt": "Ваш вопрос",
           "include_trace": true
         }'
    ```
    
    Args:
         request: Запрос с service_id, session_id и prompt
         credentials: Bearer токен для аутентификации
        
    Returns:
        ContextAnalysisResponse: Результат анализа с ответом AI агентов
        
    Raises:
        HTTPException 401: При недействительном или отсутствующем токене
        HTTPException 404: При отсутствии сервиса или сессии
        HTTPException 500: При внутренних ошибках сервера
    """
    start_time = datetime.now()
    
    # Извлекаем Bearer токен из заголовка
    bearer_token = credentials.credentials
    
    try:
        # Создаем BackendClient с токеном для аутентифицированных запросов
        authenticated_backend_client = BackendClient(bearer_token=bearer_token)
        
        # 1. Получаем информацию о сервисе (включая ключи Datadog)
        try:
            service_info = await authenticated_backend_client.get_service_info(request.service_id)
        except ServiceNotFoundError:
            logger.error(f"Сервис не найден: {request.service_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Сервис с ID {request.service_id} не найден"
            )
        except BackendClientError as e:
            # Проверяем, является ли ошибка связанной с аутентификацией
            if "401" in str(e) or "Unauthorized" in str(e):
                raise HTTPException(
                    status_code=401,
                    detail="Ошибка аутентификации: недействительный или отсутствующий Bearer токен"
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Ошибка при получении информации о сервисе: {str(e)}"
                )
        
        # 2. Получаем историю чата
        try:
            chat_messages = await authenticated_backend_client.get_chat_messages(request.session_id)
        except SessionNotFoundError:
            logger.error(f"Сессия не найдена: {request.session_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Сессия с ID {request.session_id} не найдена"
            )
        except BackendClientError as e:
            # Проверяем, является ли ошибка связанной с аутентификацией
            if "401" in str(e) or "Unauthorized" in str(e):
                raise HTTPException(
                    status_code=401,
                    detail="Ошибка аутентификации: недействительный или отсутствующий Bearer токен"
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Ошибка при получении истории чата: {str(e)}"
                )
        
        # 3. Форматируем контекст
        # Используем правильный метод format_chat_context, который уже включает новый промпт
        full_prompt = context_formatter.format_chat_context(
            chat_messages, 
            request.prompt
        )
        
        # 4. Инициализируем оркестратор с ключами из сервиса
        global orchestrator
        orchestrator = AIOrchestrator(
            dd_api_key=service_info['apiKey'],
            dd_app_key=service_info['appKey']
        )
        
        # 5. Выполняем анализ
        ai_start_time = datetime.now()
        
        result = await orchestrator.process_query(full_prompt)
        
        ai_end_time = datetime.now()
        ai_duration = (ai_end_time - ai_start_time).total_seconds()
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # 6. Извлекаем простой ответ из результата
        # result теперь является ReasoningState объектом
        final_feedback = result.processed_data.get("final_feedback", {})
        
        # Извлекаем ответ из различных возможных полей
        if isinstance(final_feedback, dict):
            answer = (
                final_feedback.get("main_response", "") or
                final_feedback.get("recommendations", "") or
                final_feedback.get("analysis_results", "") or
                str(final_feedback)
            )
        else:
            answer = str(final_feedback) if final_feedback else "Анализ завершен, но ответ не сформирован"
        
        # Если ответ все еще пустой, попробуем получить из последнего шага рассуждения
        if not answer or answer == "{}":
            latest_step = result.get_latest_step()
            if latest_step and latest_step.output_data:
                step_output = latest_step.output_data
                answer = (
                    step_output.get("main_response", "") or
                    step_output.get("recommendations", "") or
                    step_output.get("analysis_results", "") or
                    str(step_output)
                )
        
        # Финальная проверка
        if not answer or answer in ["{}", "[]", ""]:
            answer = f"Анализ завершен. Обработано {len(result.reasoning_steps)} шагов рассуждения."
        
        # 7. Сохраняем результат в чат
        try:
            await authenticated_backend_client.add_message(
                session_id=request.session_id,
                prompt=request.prompt,
                answer=answer
            )
        except BackendClientError as e:
            # Проверяем, является ли ошибка связанной с аутентификацией
            if "401" in str(e) or "Unauthorized" in str(e):
                logger.error(f"Ошибка аутентификации при сохранении: {e}")
                raise HTTPException(
                    status_code=401,
                    detail="Ошибка аутентификации: недействительный или отсутствующий Bearer токен"
                )
            else:
                logger.error(f"Не удалось сохранить результат: {e}")
                # Продолжаем выполнение, так как основная задача выполнена
        
        # 9. Формируем простой ответ
        response = ContextAnalysisResponse(
            session_id=request.session_id,
            service_id=request.service_id,
            prompt=request.prompt,
            answer=answer,
            status="completed",
            execution_time=execution_time
        )
        
        return response
        
    except HTTPException:
        # Перебрасываем HTTP исключения как есть
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Ошибка при выполнении анализа с контекстом: {str(e)}"
        )

# Получение статистики системы
@app.get("/system-stats", tags=["system"], summary="Получить системную статистику")
async def get_system_stats():
    """Получение статистики работы системы"""
    try:
        # Проверяем наличие сохраненных данных
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        data_path = os.path.join(data_dir, 'collected_data.json')
        
        result = {
            "system_status": "active",
            "data_collection": {
                "enabled": True,
                "last_collection": None,
                "data_available": os.path.exists(data_path)
            },
            "agents_status": {
                "data_agent": "ready",
                "protocol_agent": "ready", 
                "reasoning_agent": "ready"
            }
        }
        
        if os.path.exists(data_path):
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                result["data_collection"]["last_collection"] = data.get("metadata", {}).get("collection_timestamp")
                result["data_collection"]["records_count"] = len(data.get("logs", []))
                
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при загрузке mock данных: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)