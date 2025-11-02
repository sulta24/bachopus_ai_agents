import uuid
import time
import os
from typing import Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from core.reasoning_state import ReasoningState, ReasoningStep, ReasoningPhase
from core.reasoning_trace import tracer
from agents.data_agent import DataAgent
from agents.protocol_agent import ProtocolAgent


class AIOrchestrator:
    """
    AI Оркестратор с тремя циклами рассуждения:
    1. Planning - планирование анализа
    2. Execution - выполнение анализа
    3. Feedback - обратная связь и рекомендации
    """
    
    def __init__(self, dd_api_key: Optional[str] = None, dd_app_key: Optional[str] = None):
        # Инициализация LLM
        self.llm = ChatOpenAI(
            model="gpt-4o",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.3
        )
        
        # Инициализация агентов с ключами Datadog
        self.data_agent = DataAgent(dd_api_key=dd_api_key, dd_app_key=dd_app_key)
        self.protocol_agent = ProtocolAgent()
        
        # Adaptive system prompts for each phase - respond to user intent
        self.system_prompts = {
            ReasoningPhase.PLANNING: """You are an intelligent AI assistant that analyzes user requests and creates data collection plans.

CRITICAL: You MUST respond ONLY with valid JSON format. No additional text, explanations, or formatting.

Your task:
1. Analyze the user's request to understand their intent
2. Determine what data types are needed to answer their question
3. Respond with the exact JSON structure specified

Required JSON format (respond with this exact structure):
{
    "user_intent": "monitoring/question/analysis/other",
    "analysis_plan": "brief description of what analysis will be performed",
    "data_requirements": ["list", "of", "required", "data", "types"],
    "target_services": ["list", "of", "target", "services"],
    "priority": "high/medium/low"
}

Available data types: cpu_metrics, memory_metrics, disk_metrics, network_metrics, error_logs, performance_logs

IMPORTANT: Respond ONLY with the JSON structure above. No other text.""",
            ReasoningPhase.EXECUTION: """You are an intelligent AI assistant focused on providing helpful, accurate responses based on the user's actual needs.

IMPORTANT: Your response should directly address what the user asked for, not force system monitoring analysis.

Guidelines:
1. If user wants system monitoring - analyze the collected data thoroughly
2. If user has other questions - provide direct, helpful answers
3. Always be relevant and useful to the user's specific request
4. Use available data only when it serves the user's purpose

Respond in JSON format:
{
    "response_type": "monitoring/answer/analysis/explanation",
    "main_response": "direct answer to user's question",
    "system_status": "critical/warning/ok" (only if monitoring requested),
    "identified_issues": ["list_of_issues"] (only if relevant),
    "analysis_results": "detailed analysis relevant to user request",
    "confidence": 0.0-1.0
}""",
            
            ReasoningPhase.FEEDBACK: """You are an intelligent AI assistant providing final recommendations and conclusions based on the user's original request.

IMPORTANT: Your feedback should be directly useful to what the user actually wanted to know or accomplish.

Guidelines:
1. Summarize findings relevant to the user's request
2. Provide actionable recommendations if appropriate
3. If monitoring was requested - include system recommendations
4. If other help was requested - provide relevant guidance
5. Always be practical and user-focused

Respond in JSON format:
{
    "summary": "concise summary addressing user's request",
    "recommendations": ["list_of_actionable_recommendations"],
    "action_plan": ["specific_steps"] (if applicable),
    "additional_help": "offer of further assistance",
    "priority": "high/medium/low"
}"""
        }
        
    def _determine_data_requirements_fallback(self, user_query: str, llm_response: str = "") -> dict:
        """Fallback method to determine data requirements based on keywords in user query"""
        query_lower = user_query.lower()
        requirements = []
        
        # CPU related keywords
        if any(keyword in query_lower for keyword in ['cpu', 'процессор', 'load', 'нагрузка', 'загружен', 'загрузка']):
            requirements.append('cpu_metrics')
            
        # Memory related keywords  
        if any(keyword in query_lower for keyword in ['memory', 'память', 'ram', 'swap']):
            requirements.append('memory_metrics')
            
        # Disk related keywords
        if any(keyword in query_lower for keyword in ['disk', 'диск', 'storage', 'хранилище', 'io']):
            requirements.append('disk_metrics')
            
        # Network related keywords
        if any(keyword in query_lower for keyword in ['network', 'сеть', 'traffic', 'трафик', 'connection']):
            requirements.append('network_metrics')
            
        # Error/log related keywords
        if any(keyword in query_lower for keyword in ['error', 'ошибка', 'log', 'лог', 'exception']):
            requirements.append('error_logs')
            
        # Performance related keywords
        if any(keyword in query_lower for keyword in ['performance', 'производительность', 'slow', 'медленно']):
            requirements.append('performance_logs')
            if 'cpu_metrics' not in requirements:
                requirements.append('cpu_metrics')
            if 'memory_metrics' not in requirements:
                requirements.append('memory_metrics')
        
        # Server load keywords (for "насколько мой сервер загружен?")
        if any(keyword in query_lower for keyword in ['сервер', 'server', 'загружен', 'loaded']):
            if 'cpu_metrics' not in requirements:
                requirements.append('cpu_metrics')
            if 'memory_metrics' not in requirements:
                requirements.append('memory_metrics')
            if 'disk_metrics' not in requirements:
                requirements.append('disk_metrics')
            if 'network_metrics' not in requirements:
                requirements.append('network_metrics')
        
        # If no specific requirements found, default to basic monitoring
        if not requirements:
            requirements = ['cpu_metrics', 'memory_metrics']
        
        # Return structured data matching expected format
        return {
            "user_intent": "Запрос информации о состоянии системы",
            "analysis_plan": {
                "data_requirements": requirements,
                "target_services": ["system"],
                "priority": "high"
            },
            "data_requirements": requirements,
            "target_services": ["system"],
            "priority": "high"
        }

    def _determine_request_type(self, user_query: str) -> str:
        """Determine the type of user request to provide appropriate response"""
        query_lower = user_query.lower()
        
        # Keywords that indicate monitoring/system analysis requests
        monitoring_keywords = [
            'error', 'errors', 'bug', 'bugs', 'issue', 'issues', 'problem', 'problems',
            'crash', 'crashes', 'fail', 'failure', 'down', 'outage', 'slow', 'performance',
            'monitor', 'monitoring', 'status', 'health', 'check', 'analyze', 'analysis',
            'log', 'logs', 'metric', 'metrics', 'alert', 'alerts', 'warning', 'warnings',
            'critical', 'service', 'server', 'system', 'api', 'database', 'db'
        ]
        
        # Keywords that indicate general questions
        question_keywords = [
            'what', 'how', 'why', 'when', 'where', 'who', 'which', 'explain', 'tell me',
            'help', 'guide', 'tutorial', 'example', 'show', 'demonstrate'
        ]
        
        # Count monitoring vs question indicators
        monitoring_score = sum(1 for keyword in monitoring_keywords if keyword in query_lower)
        question_score = sum(1 for keyword in question_keywords if keyword in query_lower)
        
        # Determine request type based on scores and patterns
        if monitoring_score > question_score and monitoring_score > 0:
            return "monitoring"
        elif "?" in user_query or question_score > 0:
            return "question"
        elif any(word in query_lower for word in ['analyze', 'analysis', 'check', 'review']):
            return "analysis"
        else:
            return "other"
    
    async def process_query(self, user_query: str) -> ReasoningState:
        """
        Основной метод обработки запроса пользователя с трехфазным рассуждением
        """
        session_id = str(uuid.uuid4())
        
        # Создание состояния рассуждения
        state = ReasoningState(
            session_id=session_id,
            user_query=user_query,
            timestamp=datetime.now()
        )
        
        try:
            # Фаза 1: Планирование
            await self._planning_phase(state)
            
            # Фаза 2: Выполнение
            await self._execution_phase(state)
            
            # Фаза 3: Обратная связь
            await self._feedback_phase(state)
            
            return state
            
        except Exception as e:
            error_msg = f"Критическая ошибка в процессе рассуждения: {str(e)}"
            print(f"❌ {error_msg}")
            
            # Добавляем ошибку в состояние
            state.add_error(error_msg)
            return state

    async def _planning_phase(self, state: ReasoningState) -> None:
        """Фаза планирования анализа"""
        
        planning_start = time.time()
        
        try:
            # Создание промпта для планирования
            planning_prompt = f"""
            Пользователь спрашивает: "{state.user_query}"
            
            Проанализируй запрос и определи план анализа.
            """
            
            # Вызов LLM для планирования
            messages = [
                SystemMessage(content=self.system_prompts[ReasoningPhase.PLANNING]),
                HumanMessage(content=planning_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Парсинг ответа LLM
            try:
                response_content = response.content.strip()
                
                # Clean up JSON formatting
                if response_content.startswith("```json"):
                    response_content = response_content.replace("```json", "").replace("```", "").strip()
                elif response_content.startswith("```"):
                    response_content = response_content.replace("```", "").strip()
                
                planning_data = json.loads(response_content)
                
                # Validate required fields
                required_fields = ["user_intent", "analysis_plan", "data_requirements", "target_services", "priority"]
                for field in required_fields:
                    if field not in planning_data:
                        raise ValueError(f"Missing required field: {field}")
                
            except (json.JSONDecodeError, ValueError) as e:
                # Enhanced fallback logic
                planning_data = self._determine_data_requirements_fallback(state.user_query, response.content)
            
            except Exception as e:
                planning_data = self._determine_data_requirements_fallback(state.user_query, "")
            
            planning_execution_time = time.time() - planning_start
            
            # Создание шага рассуждения
            step = ReasoningStep(
                phase=ReasoningPhase.PLANNING,
                timestamp=datetime.now(),
                agent_name="PlanningAgent",
                input_data={"user_query": state.user_query},
                output_data=planning_data,
                reasoning=f"Analyzed user request and determined data requirements: {planning_data.get('data_requirements', [])}",
                confidence=0.8,
                execution_time=planning_execution_time
            )
            
            state.add_reasoning_step(step)
            state.planning_results = planning_data  # Store planning results in state
            
            # Сохранение плана в состоянии
            state.processed_data["planning"] = planning_data
            
        except Exception as e:
            error_msg = f"Ошибка в фазе планирования: {str(e)}"
            print(f"❌ {error_msg}")
            state.add_error(error_msg)

    async def _execution_phase(self, state: ReasoningState) -> None:
        """Фаза выполнения анализа"""
        
        try:
            # Получение плана из предыдущей фазы
            planning_results = state.planning_results
            
            if not isinstance(planning_results, dict):
                planning_results = self._determine_data_requirements_fallback(state.user_query, "")
            
            # Извлечение плана анализа
            analysis_plan = planning_results.get("analysis_plan", "Общий анализ системы")
            
            # Определение требований к данным
            data_requirements = planning_results.get("data_requirements", ["cpu_metrics", "memory_metrics"])
            target_services = planning_results.get("target_services", ["system"])
            
            # Сбор данных
            data_start_time = time.time()
            raw_data = {}
            successful_types = []
            failed_types = []
            
            for data_type in data_requirements:
                try:
                    if data_type in ["cpu_metrics", "memory_metrics", "disk_metrics", "network_metrics"]:
                        data = await self.data_agent.collect_system_metrics(data_type)
                        raw_data[data_type] = data
                        successful_types.append(data_type)
                    elif data_type in ["error_logs", "performance_logs"]:
                        data = await self.data_agent.collect_logs(data_type)
                        raw_data[data_type] = data
                        successful_types.append(data_type)
                except Exception as e:
                    failed_types.append(data_type)
            
            data_execution_time = time.time() - data_start_time
            
            if failed_types:
                print(f"⚠️ Сбор данных завершен частично: успешно {len(successful_types)}, ошибок {len(failed_types)}")
            
            # Создание шага сбора данных
            data_step = ReasoningStep(
                phase=ReasoningPhase.EXECUTION,
                timestamp=datetime.now(),
                agent_name="DataAgent",
                input_data={"data_requirements": data_requirements},
                output_data=raw_data,
                reasoning=f"Collected {len(successful_types)} data types successfully",
                confidence=0.9 if not failed_types else 0.7,
                execution_time=data_execution_time
            )
            
            state.add_reasoning_step(data_step)
            
            # Анализ протоколов
            protocol_start_time = time.time()
            protocol_analysis = await self.protocol_agent.analyze_protocols(raw_data, analysis_plan)
            protocol_execution_time = time.time() - protocol_start_time
            
            protocol_step = ReasoningStep(
                phase=ReasoningPhase.EXECUTION,
                timestamp=datetime.now(),
                agent_name="ProtocolAgent",
                input_data={"raw_data": raw_data, "analysis_plan": analysis_plan},
                output_data=protocol_analysis,
                reasoning="Analyzed data according to protocols and identified patterns",
                confidence=0.8,
                execution_time=protocol_execution_time
            )
            
            state.add_reasoning_step(protocol_step)
            
            # LLM анализ
            llm_start_time = time.time()
            
            # Подготовка контекста для LLM
            context = f"""
            Пользователь спрашивает: "{state.user_query}"
            
            План анализа: {analysis_plan}
            
            Собранные данные:
            {self._format_data_for_llm(raw_data)}
            
            Анализ протоколов:
            {protocol_analysis}
            """
            
            messages = [
                SystemMessage(content=self.system_prompts[ReasoningPhase.EXECUTION]),
                HumanMessage(content=context)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Парсинг ответа LLM
            try:
                response_content = response.content.strip()
                if response_content.startswith("```json"):
                    response_content = response_content.replace("```json", "").replace("```", "").strip()
                elif response_content.startswith("```"):
                    response_content = response_content.replace("```", "").strip()
                
                llm_analysis = json.loads(response_content)
            except (json.JSONDecodeError, ValueError):
                # Fallback для некорректного JSON
                llm_analysis = {
                    "response_type": "analysis",
                    "main_response": response.content,
                    "system_status": "unknown",
                    "identified_issues": [],
                    "analysis_results": response.content,
                    "confidence": 0.5
                }
            
            llm_execution_time = time.time() - llm_start_time
            
            llm_step = ReasoningStep(
                phase=ReasoningPhase.EXECUTION,
                timestamp=datetime.now(),
                agent_name="LLMAnalyst",
                input_data={"context": context},
                output_data=llm_analysis,
                reasoning="Performed comprehensive analysis using LLM",
                confidence=llm_analysis.get("confidence", 0.7),
                execution_time=llm_execution_time
            )
            
            state.add_reasoning_step(llm_step)
            
            # Сохранение результатов выполнения
            state.processed_data["execution"] = {
                "raw_data": raw_data,
                "protocol_analysis": protocol_analysis,
                "llm_analysis": llm_analysis
            }
            
            # Извлечение проблем из анализа
            identified_issues = llm_analysis.get("identified_issues", [])
            if identified_issues:
                state.identified_issues.extend(identified_issues)
            
        except Exception as e:
            error_msg = f"Ошибка в фазе выполнения: {str(e)}"
            print(f"❌ {error_msg}")
            state.add_error(error_msg)

    async def _feedback_phase(self, state: ReasoningState) -> None:
        """Фаза обратной связи и рекомендаций"""
        
        try:
            # Получение результатов выполнения
            execution_results = state.processed_data.get("execution", {})
            
            # Анализ протоколов для рекомендаций
            protocol_start_time = time.time()
            recommendations = await self.protocol_agent.generate_recommendations(
                execution_results.get("raw_data", {}),
                state.identified_issues
            )
            protocol_execution_time = time.time() - protocol_start_time
            
            protocol_step = ReasoningStep(
                phase=ReasoningPhase.FEEDBACK,
                timestamp=datetime.now(),
                agent_name="ProtocolAgent",
                input_data={"execution_results": execution_results, "issues": state.identified_issues},
                output_data=recommendations,
                reasoning="Generated recommendations based on identified issues",
                confidence=0.8,
                execution_time=protocol_execution_time
            )
            
            state.add_reasoning_step(protocol_step)
            
            # LLM для финальной обратной связи
            feedback_start_time = time.time()
            
            # Подготовка контекста для финальной обратной связи
            context = f"""
            Пользователь спрашивает: "{state.user_query}"
            
            Результаты анализа:
            {json.dumps(execution_results.get("llm_analysis", {}), indent=2, ensure_ascii=False)}
            
            Выявленные проблемы:
            {json.dumps(state.identified_issues, indent=2, ensure_ascii=False)}
            
            Рекомендации протоколов:
            {json.dumps(recommendations, indent=2, ensure_ascii=False)}
            """
            
            messages = [
                SystemMessage(content=self.system_prompts[ReasoningPhase.FEEDBACK]),
                HumanMessage(content=context)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Парсинг ответа LLM
            try:
                response_content = response.content.strip()
                if response_content.startswith("```json"):
                    response_content = response_content.replace("```json", "").replace("```", "").strip()
                elif response_content.startswith("```"):
                    response_content = response_content.replace("```", "").strip()
                
                feedback_data = json.loads(response_content)
            except (json.JSONDecodeError, ValueError):
                # Fallback для некорректного JSON
                feedback_data = {
                    "summary": response.content,
                    "recommendations": [],
                    "action_plan": [],
                    "additional_help": "Обратитесь за дополнительной помощью",
                    "priority": "medium"
                }
            
            feedback_execution_time = time.time() - feedback_start_time
            
            feedback_step = ReasoningStep(
                phase=ReasoningPhase.FEEDBACK,
                timestamp=datetime.now(),
                agent_name="FeedbackAgent",
                input_data={"context": context},
                output_data=feedback_data,
                reasoning="Generated final feedback and recommendations",
                confidence=0.8,
                execution_time=feedback_execution_time
            )
            
            state.add_reasoning_step(feedback_step)
            
            # Сохранение финальной обратной связи
            state.processed_data["final_feedback"] = feedback_data
            
            # Нормализация рекомендаций
            normalized_recommendations = []
            if isinstance(feedback_data.get("recommendations"), list):
                normalized_recommendations = feedback_data["recommendations"]
            
            # Нормализация плана действий
            normalized_action_plan = []
            if isinstance(feedback_data.get("action_plan"), list):
                normalized_action_plan = feedback_data["action_plan"]
            
        except Exception as e:
            error_msg = f"Ошибка в фазе обратной связи: {str(e)}"
            print(f"❌ {error_msg}")
            state.add_error(error_msg)

    def get_session_summary(self, state: ReasoningState) -> Dict[str, Any]:
        """Получить сводку сессии"""
        return {
            "session_id": state.session_id,
            "user_query": state.user_query,
            "execution_summary": state.get_execution_summary(),
            "identified_issues": state.identified_issues,
            "recommendations": state.recommendations,
            "action_plan": state.action_plan,
            "reasoning_trace": [step.to_dict() for step in state.reasoning_steps]
        }