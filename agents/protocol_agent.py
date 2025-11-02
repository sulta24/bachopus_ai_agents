import json
import os
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
from core.datadog_utils import safe_iterate_dict

logger = logging.getLogger(__name__)

class ProtocolAgent:
    def __init__(self, rules_path: Optional[str] = None):
        """
        Инициализация ProtocolAgent без зависимости от mock данных
        """
        # Удаляем зависимость от mock данных
        # self.rules_path = rules_path or "mock_data/protocols.json"
        
        # Определяем базовые правила и пороговые значения
        self.default_rules = {
            "error_thresholds": {
                "critical_error_count": 10,
                "error_rate_per_minute": 5,
                "response_time_ms": 5000
            },
            "performance_thresholds": {
                "cpu_usage_percent": 80,
                "memory_usage_percent": 85,
                "disk_usage_percent": 90,
                "network_latency_ms": 1000
            },
            "alert_rules": {
                "consecutive_errors": 3,
                "service_downtime_minutes": 5,
                "anomaly_detection": True
            },
            "escalation_protocols": {
                "level_1": {"threshold": 3, "notify": ["team_lead"]},
                "level_2": {"threshold": 5, "notify": ["manager", "team_lead"]},
                "level_3": {"threshold": 10, "notify": ["director", "manager", "team_lead"]}
            }
        }
        
        # Загружаем правила из файла если путь указан
        if rules_path and os.path.exists(rules_path):
            try:
                with open(rules_path, 'r', encoding='utf-8') as f:
                    custom_rules = json.load(f)
                    # Объединяем с базовыми правилами
                    self.rules = {**self.default_rules, **custom_rules}
            except Exception as e:
                print(f"[ProtocolAgent] Ошибка загрузки правил из {rules_path}: {e}")
                self.rules = self.default_rules
        else:
            self.rules = self.default_rules
        
        print(f"[ProtocolAgent] Инициализирован с правилами: {len(self.rules)} категорий")
    
    def analyze_error_log(self, error_log: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single error log and provide recommendations"""
        error_code = error_log.get("error_code", "UNKNOWN")
        service = error_log.get("service", "unknown")
        level = error_log.get("level", "INFO")
        
        # Get rules for this error type from default rules
        error_rules = self.rules.get("error_thresholds", {})
        
        analysis = {
            "error_code": error_code,
            "service": service,
            "level": level,
            "timestamp": error_log.get("timestamp"),
            "message": error_log.get("message"),
            "severity": self._determine_severity(level, error_code),
            "category": self._categorize_error(error_code),
            "recommendations": self._generate_generic_recommendations(error_log),
            "immediate_actions": self._get_immediate_actions(level),
            "analysis_timestamp": datetime.now().isoformat()
        }
        
        return analysis
    
    def analyze_logs(self, logs_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze a list of error logs and provide comprehensive analysis"""
        if not logs_data:
            return {
                "total_logs": 0,
                "analyzed_logs": [],
                "summary": {
                    "critical_count": 0,
                    "error_count": 0,
                    "warning_count": 0,
                    "total_issues": 0
                },
                "recommendations": [],
                "action_plan": [],
                "analysis_timestamp": datetime.now().isoformat()
            }
        
        analyzed_logs = []
        critical_count = 0
        error_count = 0
        warning_count = 0
        all_recommendations = []
        all_actions = []
        
        # Анализируем каждый лог
        for log in logs_data:
            log_analysis = self.analyze_error_log(log)
            analyzed_logs.append(log_analysis)
            
            # Подсчитываем по уровням
            level = log.get("level", "").upper()
            if level == "CRITICAL":
                critical_count += 1
            elif level == "ERROR":
                error_count += 1
            elif level == "WARNING":
                warning_count += 1
            
            # Собираем рекомендации и действия
            if log_analysis.get("recommendations"):
                all_recommendations.extend(log_analysis["recommendations"])
            if log_analysis.get("immediate_actions"):
                all_actions.extend(log_analysis["immediate_actions"])
        
        # Удаляем дубликаты
        unique_recommendations = list(set(all_recommendations))
        unique_actions = list(set(all_actions))
        
        return {
            "total_logs": len(logs_data),
            "analyzed_logs": analyzed_logs,
            "summary": {
                "critical_count": critical_count,
                "error_count": error_count,
                "warning_count": warning_count,
                "total_issues": critical_count + error_count + warning_count
            },
            "recommendations": unique_recommendations[:10],  # Ограничиваем до 10
            "action_plan": unique_actions[:10],  # Ограничиваем до 10
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    def analyze_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze server metrics and identify issues"""
        service = metrics.get("service", "unknown")
        metric_values = metrics.get("metrics", {})
        
        # Проверяем тип metric_values перед использованием .items()
        if not isinstance(metric_values, dict):
            logger.warning(f"metric_values не является словарем: {type(metric_values)}, значение: {metric_values}")
            metric_values = {}
        
        # Get threshold rules
        thresholds = self.rules.get("protocol_rules", {}).get("metric_thresholds", {})
        service_rules = self.rules.get("protocol_rules", {}).get("service_specific_rules", {}).get(service, {})
        
        issues = []
        recommendations = []
        
        # Check each metric against thresholds
        for metric_name, value in metric_values.items():
            if metric_name in thresholds:
                threshold_rule = thresholds[metric_name]
                warning_threshold = threshold_rule.get("warning", float('inf'))
                critical_threshold = threshold_rule.get("critical", float('inf'))
                
                if value >= critical_threshold:
                    issues.append({
                        "metric": metric_name,
                        "value": value,
                        "threshold": critical_threshold,
                        "severity": "critical",
                        "message": f"{metric_name} is critically high: {value}"
                    })
                    recommendations.extend(threshold_rule.get("recommendations", []))
                elif value >= warning_threshold:
                    issues.append({
                        "metric": metric_name,
                        "value": value,
                        "threshold": warning_threshold,
                        "severity": "warning",
                        "message": f"{metric_name} is above warning threshold: {value}"
                    })
                    recommendations.extend(threshold_rule.get("recommendations", []))
        
        # Check service-specific rules
        if service_rules:
            rps = metric_values.get("requests_per_second", 0)
            response_time = metric_values.get("response_time_avg", 0)
            
            max_rps = service_rules.get("max_requests_per_second", float('inf'))
            max_response_time = service_rules.get("max_response_time", float('inf'))
            
            if rps > max_rps:
                issues.append({
                    "metric": "requests_per_second",
                    "value": rps,
                    "threshold": max_rps,
                    "severity": "warning",
                    "message": f"Request rate exceeds service limit: {rps} > {max_rps}"
                })
            
            if response_time > max_response_time:
                issues.append({
                    "metric": "response_time_avg",
                    "value": response_time,
                    "threshold": max_response_time,
                    "severity": "warning",
                    "message": f"Response time exceeds service limit: {response_time}ms > {max_response_time}ms"
                })
        
        return {
            "service": service,
            "timestamp": metrics.get("timestamp"),
            "total_issues": len(issues),
            "issues": issues,
            "recommendations": list(set(recommendations)),  # Remove duplicates
            "status": "critical" if any(issue["severity"] == "critical" for issue in issues) else 
                     "warning" if issues else "healthy",
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    def analyze_data_batch(self, data_result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a batch of data from DataAgent"""
        result_type = data_result.get("result_type", "unknown")
        data = data_result.get("data", {})
        
        analysis_results = {
            "query": data_result.get("query", ""),
            "result_type": result_type,
            "analysis_timestamp": datetime.now().isoformat(),
            "summary": {},
            "detailed_analysis": []
        }
        
        if result_type == "error_logs":
            # Analyze each error log
            logs = data if isinstance(data, list) else []
            for log in logs:
                log_analysis = self.analyze_error_log(log)
                analysis_results["detailed_analysis"].append(log_analysis)
            
            # Create summary
            total_errors = len(logs)
            critical_errors = len([a for a in analysis_results["detailed_analysis"] if a["severity"] == "critical"])
            high_errors = len([a for a in analysis_results["detailed_analysis"] if a["severity"] == "high"])
            
            analysis_results["summary"] = {
                "total_errors": total_errors,
                "critical_errors": critical_errors,
                "high_priority_errors": high_errors,
                "overall_status": "critical" if critical_errors > 0 else "warning" if high_errors > 0 else "stable"
            }
        
        elif result_type == "metrics":
            # Analyze each metric set
            metrics_list = data if isinstance(data, list) else []
            for metrics in metrics_list:
                metrics_analysis = self.analyze_metrics(metrics)
                analysis_results["detailed_analysis"].append(metrics_analysis)
            
            # Create summary
            total_issues = sum(a["total_issues"] for a in analysis_results["detailed_analysis"])
            critical_services = len([a for a in analysis_results["detailed_analysis"] if a["status"] == "critical"])
            
            analysis_results["summary"] = {
                "total_issues": total_issues,
                "critical_services": critical_services,
                "services_analyzed": len(metrics_list),
                "overall_status": "critical" if critical_services > 0 else "warning" if total_issues > 0 else "healthy"
            }
        
        elif result_type == "service_summary":
            # Analyze service summary
            service_data = data
            service_name = service_data.get("service", "unknown")
            
            # Analyze recent errors
            recent_errors = service_data.get("recent_errors", [])
            error_analyses = []
            for error in recent_errors:
                error_analyses.append(self.analyze_error_log(error))
            
            # Analyze latest metrics
            latest_metrics = service_data.get("latest_metrics")
            metrics_analysis = None
            if latest_metrics:
                metrics_analysis = self.analyze_metrics(latest_metrics)
            
            analysis_results["detailed_analysis"] = {
                "service": service_name,
                "error_analyses": error_analyses,
                "metrics_analysis": metrics_analysis,
                "error_breakdown": service_data.get("error_breakdown", {}),
                "total_errors": service_data.get("total_errors", 0)
            }
            
            # Create summary
            critical_errors = len([a for a in error_analyses if a["severity"] == "critical"])
            metrics_status = metrics_analysis["status"] if metrics_analysis else "unknown"
            
            analysis_results["summary"] = {
                "service": service_name,
                "total_errors": service_data.get("total_errors", 0),
                "critical_errors": critical_errors,
                "metrics_status": metrics_status,
                "overall_status": "critical" if critical_errors > 0 or metrics_status == "critical" else "warning"
            }
        
        return analysis_results
    
    def _generate_generic_recommendations(self, error_log: Dict[str, Any]) -> List[str]:
        """Generate generic recommendations for unknown error types"""
        level = error_log.get("level", "INFO")
        service = error_log.get("service", "unknown")
        
        recommendations = [
            f"Review {service} service logs for additional context",
            "Check service health and resource utilization",
            "Verify service configuration and dependencies"
        ]
        
        if level in ["CRITICAL", "ERROR"]:
            recommendations.extend([
                "Consider implementing retry mechanisms",
                "Set up monitoring and alerting for this error type",
                "Review error handling in the application code"
            ])
        
        return recommendations
    
    def get_action_plan(self, metrics: Any, thresholds: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Создание плана действий на основе метрик с безопасной обработкой данных
        
        Args:
            metrics: Метрики (может быть словарем или списком)
            thresholds: Пороговые значения
            
        Returns:
            Dict[str, Any]: План действий
        """
        try:
            # Безопасная обработка входных метрик
            safe_metrics = safe_iterate_dict(metrics, "protocol agent metrics")
            safe_thresholds = safe_iterate_dict(thresholds or {}, "protocol agent thresholds")
            
            actions = []
            alerts = []
            
            # Проверяем метрики на превышение порогов
            for metric_name, metric_data in safe_metrics.items():
                if not isinstance(metric_data, dict):
                    logger.warning(f"Данные метрики {metric_name} не являются словарем: {type(metric_data)}")
                    continue
                
                # Извлекаем значение метрики
                metric_value = None
                if isinstance(metric_data, dict):
                    if "value" in metric_data:
                        metric_value = metric_data["value"]
                    elif "latest_value" in metric_data:
                        metric_value = metric_data["latest_value"]
                    elif "series" in metric_data and isinstance(metric_data["series"], list):
                        # Пытаемся извлечь последнее значение из серий
                        for series in metric_data["series"]:
                            if isinstance(series, dict) and "points" in series:
                                points = series["points"]
                                if isinstance(points, list) and points:
                                    last_point = points[-1]
                                    if isinstance(last_point, list) and len(last_point) >= 2:
                                        metric_value = last_point[1]
                                        break
                
                if metric_value is None:
                    logger.warning(f"Не удалось извлечь значение для метрики {metric_name}")
                    continue
                
                # Проверяем пороговые значения
                threshold = safe_thresholds.get(metric_name)
                if threshold is not None and isinstance(threshold, (int, float)):
                    try:
                        if float(metric_value) > float(threshold):
                            alert = {
                                "metric": metric_name,
                                "value": metric_value,
                                "threshold": threshold,
                                "severity": "high" if float(metric_value) > float(threshold) * 1.5 else "medium",
                                "timestamp": datetime.now().isoformat()
                            }
                            alerts.append(alert)
                            
                            # Создаем действие для критических метрик
                            if alert["severity"] == "high":
                                actions.append({
                                    "type": "scale_up",
                                    "target": metric_name,
                                    "reason": f"Метрика {metric_name} превысила критический порог",
                                    "priority": "high"
                                })
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Ошибка при сравнении значений для метрики {metric_name}: {e}")
                        continue
            
            # Создаем общий план действий
            action_plan = {
                "timestamp": datetime.now().isoformat(),
                "metrics_processed": len(safe_metrics),
                "alerts": alerts,
                "actions": actions,
                "status": "critical" if any(a["severity"] == "high" for a in alerts) else "normal",
                "summary": {
                    "total_alerts": len(alerts),
                    "critical_alerts": len([a for a in alerts if a["severity"] == "high"]),
                    "recommended_actions": len(actions)
                }
            }
            
            logger.info(f"Создан план действий: {len(alerts)} предупреждений, {len(actions)} действий")
            return action_plan
            
        except Exception as e:
            error_msg = f"Ошибка при создании плана действий: {str(e)}"
            logger.error(error_msg)
            return {
                "error": error_msg,
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "alerts": [],
                "actions": []
            }
    
    def analyze_selective_data(self, selective_data: Dict[str, Any], collection_stats: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze selective data collected based on data_requirements"""
        analysis_results = {
            "data_types_analyzed": list(selective_data.keys()),
            "analysis_timestamp": datetime.now().isoformat(),
            "combined_analysis": {},
            "overall_summary": {},
            "action_plan": {},
            "data_collection_status": {}
        }
        
        # Add collection statistics to analysis
        if collection_stats:
            analysis_results["data_collection_status"] = {
                "successful_collections": collection_stats.get("successful_collections", []),
                "failed_collections": collection_stats.get("failed_collections", []),
                "has_errors": collection_stats.get("has_errors", False),
                "collection_errors": collection_stats.get("collection_errors", [])
            }
        
        # Analyze each data type that was collected
        combined_issues = []
        combined_recommendations = []
        combined_actions = []
        overall_status = "healthy"
        
        # Check if data collection had failures
        if collection_stats and collection_stats.get("has_errors", False):
            failed_types = collection_stats.get("failed_collections", [])
            collection_errors = collection_stats.get("collection_errors", [])
            
            # Add collection failures to issues
            for error_info in collection_errors:
                combined_issues.append(f"Не удалось получить данные типа '{error_info['type']}': {error_info['error']}")
            
            # Adjust status based on failed collections
            if len(failed_types) == len(collection_stats.get("requested_types", [])):
                # All collections failed
                overall_status = "critical"
                combined_issues.append("Все попытки сбора данных завершились неудачей")
                combined_recommendations.append("Проверить подключение к источникам данных")
                combined_recommendations.append("Проверить конфигурацию системы мониторинга")
            elif len(failed_types) > 0:
                # Partial failure
                if overall_status == "healthy":
                    overall_status = "warning"
                combined_recommendations.append("Проверить доступность источников данных")
        
        # Analyze error logs if present
        if "error_logs" in selective_data:
            logs_analysis = self.analyze_logs(selective_data["error_logs"])
            analysis_results["combined_analysis"]["error_logs"] = logs_analysis
            
            # Extract issues and recommendations
            if logs_analysis.get("summary", {}).get("total_issues", 0) > 0:
                combined_issues.append(f"Найдено {logs_analysis['summary']['total_issues']} проблем в логах")
                if logs_analysis["summary"].get("critical_count", 0) > 0:
                    overall_status = "critical"
                elif overall_status != "critical" and logs_analysis["summary"].get("error_count", 0) > 0:
                    overall_status = "warning"
            
            combined_recommendations.extend(logs_analysis.get("recommendations", []))
            combined_actions.extend(logs_analysis.get("action_plan", []))
        
        # Analyze metrics if present
        if "metrics" in selective_data:
            metrics_analysis = []
            critical_services = 0
            total_issues = 0
            
            for metric in selective_data["metrics"]:
                if isinstance(metric, dict):
                    metric_analysis = self.analyze_metrics(metric)
                    metrics_analysis.append(metric_analysis)
                    
                    total_issues += metric_analysis.get("total_issues", 0)
                    if metric_analysis.get("status") == "critical":
                        critical_services += 1
                        overall_status = "critical"
                    elif metric_analysis.get("status") == "warning" and overall_status != "critical":
                        overall_status = "warning"
                    
                    combined_recommendations.extend(metric_analysis.get("recommendations", []))
            
            analysis_results["combined_analysis"]["metrics"] = {
                "services_analyzed": len(metrics_analysis),
                "total_issues": total_issues,
                "critical_services": critical_services,
                "detailed_analysis": metrics_analysis
            }
            
            if total_issues > 0:
                combined_issues.append(f"Найдено {total_issues} проблем в метриках {len(metrics_analysis)} сервисов")
        
        # Analyze service summary if present
        if "service_summary" in selective_data:
            service_data = selective_data["service_summary"]
            service_name = service_data.get("service", "unknown")
            
            # Analyze recent errors
            recent_errors = service_data.get("recent_errors", [])
            error_analyses = []
            critical_errors = 0
            
            for error in recent_errors:
                error_analysis = self.analyze_error_log(error)
                error_analyses.append(error_analysis)
                if error_analysis.get("severity") == "critical":
                    critical_errors += 1
                    overall_status = "critical"
                elif error_analysis.get("severity") in ["high", "warning"] and overall_status != "critical":
                    overall_status = "warning"
                
                combined_recommendations.extend(error_analysis.get("recommendations", []))
                combined_actions.extend(error_analysis.get("immediate_actions", []))
            
            # Analyze latest metrics
            metrics_analysis = None
            if service_data.get("latest_metrics"):
                metrics_analysis = self.analyze_metrics(service_data["latest_metrics"])
                if metrics_analysis.get("status") == "critical":
                    overall_status = "critical"
                elif metrics_analysis.get("status") == "warning" and overall_status != "critical":
                    overall_status = "warning"
                combined_recommendations.extend(metrics_analysis.get("recommendations", []))
            
            analysis_results["combined_analysis"]["service_summary"] = {
                "service": service_name,
                "total_errors": service_data.get("total_errors", 0),
                "critical_errors": critical_errors,
                "error_analyses": error_analyses,
                "metrics_analysis": metrics_analysis
            }
            
            if service_data.get("total_errors", 0) > 0:
                combined_issues.append(f"Сервис {service_name}: {service_data['total_errors']} ошибок, {critical_errors} критических")
        
        # Analyze critical errors if present
        if "critical_errors" in selective_data:
            critical_analysis = []
            for error in selective_data["critical_errors"]:
                error_analysis = self.analyze_error_log(error)
                critical_analysis.append(error_analysis)
                combined_recommendations.extend(error_analysis.get("recommendations", []))
                combined_actions.extend(error_analysis.get("immediate_actions", []))
            
            analysis_results["combined_analysis"]["critical_errors"] = {
                "count": len(selective_data["critical_errors"]),
                "analyses": critical_analysis
            }
            
            if len(selective_data["critical_errors"]) > 0:
                overall_status = "critical"
                combined_issues.append(f"Обнаружено {len(selective_data['critical_errors'])} критических ошибок")
        
        # Create overall summary with data collection awareness
        analysis_results["overall_summary"] = {
            "status": overall_status,
            "data_types_collected": len(selective_data),
            "data_types_requested": len(collection_stats.get("requested_types", [])) if collection_stats else len(selective_data),
            "collection_success_rate": self._calculate_collection_success_rate(collection_stats) if collection_stats else 100.0,
            "total_issues": len(combined_issues),
            "issues_summary": combined_issues,
            "requires_immediate_attention": overall_status == "critical",
            "data_availability": "partial" if collection_stats and collection_stats.get("has_errors") else "complete"
        }
        
        # Generate action plan with data collection considerations
        unique_recommendations = list(set(combined_recommendations))
        unique_actions = list(set(combined_actions))
        
        # Add data collection specific recommendations if needed
        if collection_stats and collection_stats.get("has_errors"):
            unique_recommendations.insert(0, "Восстановить доступ к недоступным источникам данных")
            unique_actions.insert(0, "Проверить статус системы мониторинга")
        
        analysis_results["action_plan"] = {
            "priority": "high" if overall_status == "critical" else "medium" if overall_status == "warning" else "low",
            "immediate_actions": unique_actions[:5],
            "recommendations": unique_recommendations[:10],
            "estimated_resolution_time": self._estimate_resolution_time(overall_status),
            "requires_escalation": overall_status == "critical"
        }
        
        return analysis_results
    
    def _calculate_collection_success_rate(self, collection_stats: Dict[str, Any]) -> float:
        """Calculate the success rate of data collection"""
        if not collection_stats:
            return 100.0
        
        requested_types = collection_stats.get("requested_types", [])
        successful_collections = collection_stats.get("successful_collections", [])
        
        if not requested_types:
            return 100.0
        
        success_rate = (len(successful_collections) / len(requested_types)) * 100
        return round(success_rate, 1)

    def _estimate_resolution_time(self, status: str) -> str:
        """Estimate resolution time based on status"""
        time_estimates = {
            "critical": "Immediate (0-30 minutes)",
            "warning": "Short-term (1-4 hours)",
            "healthy": "Routine maintenance (1-7 days)",
            "unknown": "Assessment needed (30 minutes - 2 hours)"
        }
        return time_estimates.get(status, "Assessment needed")
    
    def generate_recommendations(self, analysis_data: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis data - required method for orchestrator"""
        recommendations = []
        
        # Extract recommendations from different analysis types
        if "recommendations" in analysis_data:
            if isinstance(analysis_data["recommendations"], list):
                recommendations.extend(analysis_data["recommendations"])
            elif isinstance(analysis_data["recommendations"], str):
                recommendations.append(analysis_data["recommendations"])
        
        # If no specific recommendations, generate generic ones based on status
        if not recommendations:
            status = analysis_data.get("status", "unknown")
            if status == "critical":
                recommendations.extend([
                    "Immediate investigation required",
                    "Check system resources and logs",
                    "Consider scaling or failover procedures",
                    "Alert operations team"
                ])
            elif status == "warning":
                recommendations.extend([
                    "Monitor system closely",
                    "Review recent changes",
                    "Check resource utilization trends",
                    "Plan preventive maintenance"
                ])
            else:
                recommendations.extend([
                    "Continue regular monitoring",
                    "Review system performance metrics",
                    "Update documentation if needed"
                ])
        
        return recommendations[:10]  # Limit to top 10 recommendations

    def _determine_severity(self, level: str, error_code: str) -> str:
        """Определяет серьезность ошибки на основе уровня и кода"""
        if level.upper() in ['CRITICAL', 'FATAL', 'ERROR']:
            return 'high'
        elif level.upper() in ['WARNING', 'WARN']:
            return 'medium'
        else:
            return 'low'
    
    def _categorize_error(self, error_code: str) -> str:
        """Категоризирует ошибку по коду"""
        if 'AUTH' in error_code.upper():
            return 'authentication'
        elif 'CONN' in error_code.upper() or 'NETWORK' in error_code.upper():
            return 'connectivity'
        elif 'DB' in error_code.upper() or 'DATABASE' in error_code.upper():
            return 'database'
        elif 'API' in error_code.upper():
            return 'api'
        else:
            return 'general'
    
    def _get_immediate_actions(self, level: str) -> List[str]:
        """Возвращает немедленные действия на основе уровня ошибки"""
        if level.upper() in ['CRITICAL', 'FATAL']:
            return [
                "Немедленно уведомить команду",
                "Проверить состояние сервиса",
                "Подготовить план восстановления"
            ]
        elif level.upper() == 'ERROR':
            return [
                "Проанализировать детали ошибки",
                "Проверить логи сервиса",
                "Мониторить повторения"
            ]
        else:
            return [
                "Зафиксировать в системе мониторинга",
                "Проверить тренды"
            ]