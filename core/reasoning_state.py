from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class ReasoningPhase(Enum):
    """Фазы рассуждения оркестратора"""
    PLANNING = "planning"
    EXECUTION = "execution"
    FEEDBACK = "feedback"


@dataclass
class ReasoningStep:
    """Отдельный шаг рассуждения"""
    phase: ReasoningPhase
    timestamp: datetime
    agent_name: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    reasoning: str
    confidence: float
    execution_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для логирования"""
        return {
            "phase": self.phase.value,
            "timestamp": self.timestamp.isoformat(),
            "agent_name": self.agent_name,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "execution_time": self.execution_time
        }


@dataclass
class ReasoningState:
    """Состояние рассуждения, передаваемое между циклами"""
    
    # Основные данные
    session_id: str
    user_query: str
    current_phase: ReasoningPhase = ReasoningPhase.PLANNING
    request_type: str = "other"  # Type of user request: monitoring/question/analysis/other
    
    # История шагов рассуждения
    reasoning_steps: List[ReasoningStep] = field(default_factory=list)
    
    # Контекст данных
    context: Dict[str, Any] = field(default_factory=dict)  # Add context field
    raw_data: Dict[str, Any] = field(default_factory=dict)
    processed_data: Dict[str, Any] = field(default_factory=dict)
    collected_data: Dict[str, Any] = field(default_factory=dict)  # Add collected_data field
    planning_results: Dict[str, Any] = field(default_factory=dict)  # Add planning_results field
    
    # Результаты анализа
    identified_issues: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    action_plan: List[Dict[str, Any]] = field(default_factory=list)
    
    # Метаданные
    start_time: datetime = field(default_factory=datetime.now)
    last_update: datetime = field(default_factory=datetime.now)
    total_confidence: float = 0.0
    
    # Флаги состояния
    is_complete: bool = False
    has_errors: bool = False
    error_messages: List[str] = field(default_factory=list)
    
    def add_reasoning_step(self, step: ReasoningStep):
        """Добавить шаг рассуждения"""
        self.reasoning_steps.append(step)
        self.last_update = datetime.now()
        
        # Обновить общую уверенность
        if self.reasoning_steps:
            self.total_confidence = sum(s.confidence for s in self.reasoning_steps) / len(self.reasoning_steps)
    
    def set_phase(self, phase: ReasoningPhase):
        """Установить текущую фазу"""
        self.current_phase = phase
        self.last_update = datetime.now()
    
    def add_error(self, error_message: str):
        """Добавить ошибку"""
        self.has_errors = True
        self.error_messages.append(error_message)
        self.last_update = datetime.now()
    
    def get_phase_steps(self, phase: ReasoningPhase) -> List[ReasoningStep]:
        """Получить шаги определенной фазы"""
        return [step for step in self.reasoning_steps if step.phase == phase]
    
    def get_latest_step(self) -> Optional[ReasoningStep]:
        """Получить последний шаг рассуждения"""
        return self.reasoning_steps[-1] if self.reasoning_steps else None
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Получить сводку выполнения"""
        total_time = (self.last_update - self.start_time).total_seconds()
        
        phase_stats = {}
        for phase in ReasoningPhase:
            phase_steps = self.get_phase_steps(phase)
            phase_stats[phase.value] = {
                "steps_count": len(phase_steps),
                "avg_confidence": sum(s.confidence for s in phase_steps) / len(phase_steps) if phase_steps else 0,
                "total_time": sum(s.execution_time for s in phase_steps)
            }
        
        return {
            "session_id": self.session_id,
            "total_execution_time": total_time,
            "total_steps": len(self.reasoning_steps),
            "current_phase": self.current_phase.value,
            "overall_confidence": self.total_confidence,
            "is_complete": self.is_complete,
            "has_errors": self.has_errors,
            "error_count": len(self.error_messages),
            "phase_statistics": phase_stats,
            "issues_found": len(self.identified_issues),
            "recommendations_generated": len(self.recommendations),
            "action_items": len(self.action_plan)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для сериализации"""
        return {
            "session_id": self.session_id,
            "user_query": self.user_query,
            "current_phase": self.current_phase.value,
            "reasoning_steps": [step.to_dict() for step in self.reasoning_steps],
            "raw_data": self.raw_data,
            "processed_data": self.processed_data,
            "identified_issues": self.identified_issues,
            "recommendations": self.recommendations,
            "action_plan": self.action_plan,
            "start_time": self.start_time.isoformat(),
            "last_update": self.last_update.isoformat(),
            "total_confidence": self.total_confidence,
            "is_complete": self.is_complete,
            "has_errors": self.has_errors,
            "error_messages": self.error_messages,
            "execution_summary": self.get_execution_summary()
        }