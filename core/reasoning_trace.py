import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from colorama import Fore, Back, Style, init
from .reasoning_state import ReasoningState, ReasoningStep, ReasoningPhase

# Инициализация colorama для Windows
init(autoreset=True)


class ReasoningTracer:
    """Система трассировки рассуждений с цветным логированием в консоль"""
    
    def __init__(self, log_level: str = "INFO"):
        self.logger = logging.getLogger("ReasoningTracer")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Настройка консольного обработчика
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, log_level.upper()))
            
            # Настройка кодировки для Windows
            import sys
            if hasattr(console_handler.stream, 'reconfigure'):
                console_handler.stream.reconfigure(encoding='utf-8')
            elif sys.platform.startswith('win'):
                import codecs
                console_handler.stream = codecs.getwriter('utf-8')(console_handler.stream.buffer)
            
            # Кастомный форматтер без стандартного префикса
            formatter = logging.Formatter('%(message)s')
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(console_handler)
        
        # Цветовая схема для разных фаз
        self.phase_colors = {
            ReasoningPhase.PLANNING: Fore.CYAN,
            ReasoningPhase.EXECUTION: Fore.GREEN,
            ReasoningPhase.FEEDBACK: Fore.YELLOW
        }
        
        # Символы для разных типов сообщений
        self.symbols = {
            "start": "🚀",
            "step": "⚡",
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
            "thinking": "🤔",
            "data": "📊",
            "recommendation": "💡",
            "action": "🎯"
        }
    
    def _get_phase_color(self, phase: ReasoningPhase) -> str:
        """Получить цвет для фазы"""
        return self.phase_colors.get(phase, Fore.WHITE)
    
    def _format_timestamp(self) -> str:
        """Форматировать временную метку"""
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    def _print_separator(self, char: str = "─", length: int = 80, color: str = Fore.WHITE):
        """Печать разделителя"""
        self.logger.info(f"{color}{char * length}{Style.RESET_ALL}")
    
    def _print_box(self, title: str, content: str, color: str = Fore.WHITE):
        """Печать содержимого в рамке"""
        lines = content.split('\n')
        max_width = max(len(title), max(len(line) for line in lines)) + 4
        
        # Верхняя граница
        self.logger.info(f"{color}┌{'─' * (max_width - 2)}┐{Style.RESET_ALL}")
        
        # Заголовок
        title_padding = max_width - len(title) - 4
        self.logger.info(f"{color}│ {Style.BRIGHT}{title}{Style.NORMAL}{' ' * title_padding} │{Style.RESET_ALL}")
        
        # Разделитель
        self.logger.info(f"{color}├{'─' * (max_width - 2)}┤{Style.RESET_ALL}")
        
        # Содержимое
        for line in lines:
            line_padding = max_width - len(line) - 4
            self.logger.info(f"{color}│ {line}{' ' * line_padding} │{Style.RESET_ALL}")
        
        # Нижняя граница
        self.logger.info(f"{color}└{'─' * (max_width - 2)}┘{Style.RESET_ALL}")
    
    def trace_session_start(self, state: ReasoningState):
        """Трассировка начала сессии"""
        self._print_separator("═", color=Fore.MAGENTA)
        
        header = f"{self.symbols['start']} AI ORCHESTRATOR SESSION STARTED"
        session_info = f"""Session ID: {state.session_id}
Query: {state.user_query}
Start Time: {state.start_time.strftime('%Y-%m-%d %H:%M:%S')}
Initial Phase: {state.current_phase.value.upper()}"""
        
        self._print_box(header, session_info, Fore.MAGENTA)
        self._print_separator("═", color=Fore.MAGENTA)
    
    def trace_phase_start(self, phase: ReasoningPhase, context: Dict[str, Any] = None):
        """Трассировка начала фазы"""
        color = self._get_phase_color(phase)
        timestamp = self._format_timestamp()
        
        self.logger.info(f"\n{color}{Style.BRIGHT}[{timestamp}] 🔄 PHASE: {phase.value.upper()} STARTED{Style.RESET_ALL}")
        
        if context:
            context_str = json.dumps(context, indent=2, ensure_ascii=False)
            self._print_box("Phase Context", context_str, color)
    
    def trace_reasoning_step(self, step_name: str, input_data: Any, output_data: Any, 
                           execution_time: float = None, metadata: Dict[str, Any] = None):
        """Записывает шаг рассуждения"""
        try:
            step = ReasoningStep(
                step_name=step_name,
                input_data=input_data,
                output_data=output_data,
                execution_time=execution_time,
                metadata=metadata or {}
            )
            self.steps.append(step)
            
        except Exception as e:
            print(f"❌ Ошибка записи шага рассуждения: {str(e)}")

    def get_trace_summary(self) -> Dict[str, Any]:
        """Возвращает краткую сводку трассировки"""
        try:
            total_time = sum(step.execution_time for step in self.steps if step.execution_time)
            
            return {
                "total_steps": len(self.steps),
                "total_execution_time": total_time,
                "steps": [step.step_name for step in self.steps],
                "session_id": self.session_id,
                "created_at": self.created_at.isoformat()
            }
            
        except Exception as e:
            print(f"❌ Ошибка создания сводки трассировки: {str(e)}")
            return {"error": "Ошибка создания сводки"}
    
    def trace_issues_found(self, issues: list):
        """Трассировка найденных проблем"""
        if not issues:
            return
        
        self.logger.info(f"\n{Fore.RED}{Style.BRIGHT}{self.symbols['error']} ISSUES IDENTIFIED:{Style.RESET_ALL}")
        
        for i, issue in enumerate(issues, 1):
            severity = issue.get('severity', 'unknown').upper()
            severity_color = {
                'CRITICAL': Fore.RED,
                'HIGH': Fore.YELLOW,
                'MEDIUM': Fore.BLUE,
                'LOW': Fore.GREEN
            }.get(severity, Fore.WHITE)
            
            self.logger.info(f"  {severity_color}{i}. [{severity}] {issue.get('description', 'No description')}{Style.RESET_ALL}")
            
            if issue.get('details'):
                self.logger.info(f"     Details: {issue['details']}")
    
    def trace_recommendations(self, recommendations: list):
        """Трассировка рекомендаций"""
        if not recommendations:
            return
        
        self.logger.info(f"\n{Fore.CYAN}{Style.BRIGHT}{self.symbols['recommendation']} RECOMMENDATIONS:{Style.RESET_ALL}")
        
        for i, rec in enumerate(recommendations, 1):
            # Проверяем тип элемента списка
            if isinstance(rec, dict):
                priority = rec.get('priority', 'medium').upper()
                action = rec.get('action', 'No action specified')
                rationale = rec.get('rationale')
            elif isinstance(rec, str):
                priority = 'MEDIUM'
                action = rec
                rationale = None
            else:
                priority = 'MEDIUM'
                action = str(rec)
                rationale = None
            
            priority_color = {
                'HIGH': Fore.RED,
                'MEDIUM': Fore.YELLOW,
                'LOW': Fore.GREEN
            }.get(priority, Fore.WHITE)
            
            self.logger.info(f"  {priority_color}{i}. [{priority}] {action}{Style.RESET_ALL}")
            
            if rationale:
                self.logger.info(f"     Rationale: {rationale}")
    
    def trace_action_plan(self, action_plan: list):
        """Трассировка плана действий"""
        if not action_plan:
            return
        
        self.logger.info(f"\n{Fore.GREEN}{Style.BRIGHT}{self.symbols['action']} ACTION PLAN:{Style.RESET_ALL}")
        
        for i, action in enumerate(action_plan, 1):
            # Проверяем тип элемента списка
            if isinstance(action, dict):
                status = action.get('status', 'pending')
                description = action.get('description', 'No description')
                estimated_time = action.get('estimated_time')
            elif isinstance(action, str):
                status = 'pending'
                description = action
                estimated_time = None
            else:
                status = 'pending'
                description = str(action)
                estimated_time = None
            
            status_symbol = {
                'pending': '⏳',
                'in_progress': '🔄',
                'completed': '✅',
                'failed': '❌'
            }.get(status, '❓')
            
            self.logger.info(f"  {status_symbol} {i}. {description}")
            
            if estimated_time:
                self.logger.info(f"     ETA: {estimated_time}")
    
    def trace_session_complete(self, state: ReasoningState):
        """Трассировка завершения сессии"""
        summary = state.get_execution_summary()
        
        self._print_separator("═", color=Fore.MAGENTA)
        
        # Заголовок
        status_symbol = self.symbols['success'] if not state.has_errors else self.symbols['error']
        header = f"{status_symbol} SESSION COMPLETED"
        
        # Сводка
        summary_text = f"""Total Time: {summary['total_execution_time']:.2f}s
Total Steps: {summary['total_steps']}
Overall Confidence: {summary['overall_confidence']:.1%}
Issues Found: {summary['issues_found']}
Recommendations: {summary['recommendations_generated']}
Action Items: {summary['action_items']}
Errors: {summary['error_count']}"""
        
        color = Fore.GREEN if not state.has_errors else Fore.RED
        self._print_box(header, summary_text, color)
        
        # Статистика по фазам
        if summary.get('phase_statistics'):
            phase_stats = []
            phase_statistics = summary['phase_statistics']
            
            # Проверяем тип данных перед вызовом .items()
            if isinstance(phase_statistics, dict):
                for phase, stats in phase_statistics.items():
                    if isinstance(stats, dict) and 'steps_count' in stats and 'total_time' in stats:
                        phase_stats.append(f"{phase.upper()}: {stats['steps_count']} steps, {stats['total_time']:.2f}s")
            elif isinstance(phase_statistics, list):
                # Если это список, обрабатываем каждый элемент
                for i, stats in enumerate(phase_statistics):
                    if isinstance(stats, dict) and 'steps_count' in stats and 'total_time' in stats:
                        phase_name = stats.get('phase', f'Phase {i+1}')
                        phase_stats.append(f"{phase_name.upper()}: {stats['steps_count']} steps, {stats['total_time']:.2f}s")
            else:
                # Если тип данных неожиданный, логируем предупреждение
                self.logger.warning(f"Unexpected type for phase_statistics: {type(phase_statistics)}")
            
            if phase_stats:
                self._print_box("Phase Statistics", "\n".join(phase_stats), Fore.BLUE)
        
        self._print_separator("═", color=Fore.MAGENTA)
    
    def trace_error(self, error_message: str, context: Dict[str, Any] = None):
        """Трассировка ошибки"""
        timestamp = self._format_timestamp()
        
        self.logger.error(f"\n{Fore.RED}[{timestamp}] {self.symbols['error']} ERROR: {error_message}{Style.RESET_ALL}")
        
        if context:
            context_str = json.dumps(context, indent=2, ensure_ascii=False)
            self._print_box("Error Context", context_str, Fore.RED)
    
    def trace_warning(self, warning_message: str):
        """Трассировка предупреждения"""
        timestamp = self._format_timestamp()
        self.logger.warning(f"{Fore.YELLOW}[{timestamp}] {self.symbols['warning']} WARNING: {warning_message}{Style.RESET_ALL}")
    
    def trace_info(self, info_message: str):
        """Трассировка информационного сообщения"""
        timestamp = self._format_timestamp()
        self.logger.info(f"{Fore.BLUE}[{timestamp}] {self.symbols['info']} {info_message}{Style.RESET_ALL}")

    def trace_data_requirements(self, data_requirements: list, target_services: list = None):
        """Трассировка требований к данным для селективного сбора"""
        self.logger.info(f"\n{Fore.CYAN}{Style.BRIGHT}{self.symbols['data']} DATA REQUIREMENTS:{Style.RESET_ALL}")
        
        for i, req in enumerate(data_requirements, 1):
            self.logger.info(f"  {Fore.CYAN}{i}. {req}{Style.RESET_ALL}")
        
        if target_services:
            self.logger.info(f"{Fore.CYAN}{self.symbols['info']} Target Services: {', '.join(target_services)}{Style.RESET_ALL}")

    def trace_data_collection(self, collected_data: Dict[str, Any], execution_time: float):
        """Трассировка сбора данных"""
        color = Fore.BLUE
        
        # Подсчет собранных данных
        data_summary = []
        # Подсчет логов
        if "logs" in collected_data and collected_data["logs"]:
            logs_count = len(collected_data['logs']) if isinstance(collected_data['logs'], list) else 1
            data_summary.append(f"{logs_count} логов")
        
        # Подсчет метрик с учетом структуры Datadog
        if "metrics" in collected_data and collected_data["metrics"]:
            metrics_count = 0
            if isinstance(collected_data['metrics'], list):
                for item in collected_data['metrics']:
                    if isinstance(item, dict):
                        # Если это метаданные, пропускаем
                        if "_metadata" in item:
                            continue
                        # Если это категория метрик, считаем метрики внутри
                        if "metrics" in item and isinstance(item["metrics"], list):
                            metrics_count += len(item["metrics"])
                        else:
                            metrics_count += 1
                    else:
                        metrics_count += 1
            else:
                metrics_count = 1
            data_summary.append(f"{metrics_count} метрик")
        
        # Подсчет критических ошибок
        if "critical_errors" in collected_data and collected_data["critical_errors"]:
            errors_count = len(collected_data['critical_errors']) if isinstance(collected_data['critical_errors'], list) else 1
            data_summary.append(f"{errors_count} критических ошибок")
        
        # Сводка сервиса
        if "service_summary" in collected_data and collected_data["service_summary"]:
            if isinstance(collected_data['service_summary'], dict):
                service_name = collected_data['service_summary'].get('service', 'неизвестный')
                data_summary.append(f"сводка сервиса {service_name}")
            else:
                data_summary.append("сводка сервиса")
        
        summary_text = ", ".join(data_summary) if data_summary else "нет данных"
        
        self.logger.info(f"{color}{self.symbols['data']} Данные собраны: {summary_text}{Style.RESET_ALL}")
        self.logger.info(f"{color}⏱️  Время сбора: {execution_time:.2f}с{Style.RESET_ALL}")
        
        # Детальная информация о собранных данных
        for key, value in collected_data.items():
            if value:
                if isinstance(value, list):
                    self.logger.info(f"  📋 {key}: {len(value)} элементов")
                elif isinstance(value, dict):
                    self.logger.info(f"  📊 {key}: словарь с {len(value)} ключами")
                else:
                    self.logger.info(f"  📄 {key}: {type(value).__name__}")

    def _summarize_data(self, data: Dict[str, Any], max_length: int = 100) -> str:
        """Создать краткую сводку данных"""
        if isinstance(data, dict):
            keys = list(data.keys())
            if len(keys) <= 3:
                return f"{{keys: {keys}}}"
            else:
                return f"{{keys: {keys[:3]}... (+{len(keys)-3} more)}}"
        elif isinstance(data, list):
            return f"[{len(data)} items]"
        else:
            str_data = str(data)
            if len(str_data) > max_length:
                return str_data[:max_length] + "..."
            return str_data


# Глобальный экземпляр трассировщика
tracer = ReasoningTracer()