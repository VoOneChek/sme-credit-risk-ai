from sqlalchemy.orm import Session
from app.models.models import KnowledgeRule
from typing import List, Optional

class KnowledgeBaseService:
    
    def get_all_rules(self, db: Session) -> List[KnowledgeRule]:
        """Получить все активные правила"""
        return db.query(KnowledgeRule).all()

    def add_rule(self, db: Session, rule_data: dict) -> KnowledgeRule:
        """Добавить новое правило"""
        # Преобразуем словарь в модель
        new_rule = KnowledgeRule(
            risk_type=rule_data.get("risk_type"),
            rule_name=rule_data.get("rule_name"),
            condition_json=rule_data.get("condition_json"),
            severity=rule_data.get("severity"),
            recommendation=rule_data.get("recommendation")
        )
        db.add(new_rule)
        db.commit()
        db.refresh(new_rule)
        return new_rule
    
    def update_rule(self, db: Session, rule_id: int, rule_data: dict):
        """Обновление существующего правила"""
        rule = db.query(KnowledgeRule).filter(KnowledgeRule.id == rule_id).first()
        if rule:
            rule.risk_type = rule_data.get("risk_type", rule.risk_type)
            rule.rule_name = rule_data.get("rule_name", rule.rule_name)
            rule.condition_json = rule_data.get("condition_json", rule.condition_json)
            rule.severity = rule_data.get("severity", rule.severity)
            rule.recommendation = rule_data.get("recommendation", rule.recommendation)
            db.commit()
            db.refresh(rule)
        return rule

    def delete_rule(self, db: Session, rule_id: int):
        """Удалить правило"""
        rule = db.query(KnowledgeRule).filter(KnowledgeRule.id == rule_id).first()
        if rule:
            db.delete(rule)
            db.commit()
        return rule
    
    def evaluate_rule_severity(self, rule: KnowledgeRule, current_val: float, threshold: float, op: str) -> dict:
        """
        Оценивает правила на основе величины отклонения от порога.
        Возвращает словарь с severity и explanation для конкретного срабатывания.
        """

        if threshold == 0:
            deviation = abs(current_val) * 10
        else:
            if op == "<":
                deviation = (threshold - current_val) / threshold
            elif op == ">":
                deviation = (current_val - threshold) / threshold
            else:
                deviation = 0.1  # для строк
        
        deviation = min(1.0, max(0, deviation))
        
        # Определяем severity на основе отклонения
        if deviation > 0.5: 
            actual_severity = "критический"
            max_penalty = 40
        elif deviation > 0.2:
            actual_severity = "средний"
            max_penalty = 20
        else:
            actual_severity = "низкий"
            max_penalty = 10
        
        calculated_penalty = min(max_penalty, max_penalty * deviation * 2)
        
        return {
            "severity": actual_severity,
            "deviation": deviation,
            "penalty": calculated_penalty,
            "base_rule_severity": rule.severity, 
            "explanation": f"Отклонение от нормы на {deviation*100:.1f}%"
        }

kb_service = KnowledgeBaseService()