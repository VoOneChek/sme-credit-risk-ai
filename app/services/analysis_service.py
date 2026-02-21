import joblib
import os
import numpy as np
from sqlalchemy.orm import Session
from app.core.utils import get_label
from app.models.models import CreditApplication, FoundRisk, AnalysisResult, RiskReport, ApplicationData

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "credit_model.pkl")

class AnalysisService:
    def __init__(self, kb_service, data_service):
        self.kb = kb_service
        self.preproc = data_service
        # Загрузка модели (если есть)
        if os.path.exists(MODEL_PATH):
            self.model = joblib.load(MODEL_PATH)
        else:
            from sklearn.ensemble import RandomForestClassifier
            self.model = RandomForestClassifier(n_estimators=10, random_state=42)
            self.model.fit(np.array([[1, 1], [2, 2]]), [0, 1])

    def analyze_application(self, raw_data: ApplicationData, user_id: int, db: Session) -> AnalysisResult:
        processed_text = self.preproc.preprocess_text(raw_data.business_description)
        risks_data = []

        # --- 1. ML ---
        features = np.array([[
            raw_data.financial_data.get("current_ratio", 0),
            raw_data.financial_data.get("debt_to_equity", 0),
            raw_data.financial_data.get("net_profit_margin", 0),
            raw_data.financial_data.get("company_age", 0)
        ]])
        
        risk_probability = self.model.predict_proba(features)[0][1]
        rating = int(100 * (1 - risk_probability))

        if risk_probability > 0.5:
            risks_data.append({
                "risk_type": "прогнозный",
                "source": "Нейросетевая модель",
                "severity": "критический",
                "recommendation": "Высокая вероятность дефолта по статистической модели."
            })
        elif risk_probability > 0.3:
                risks_data.append({
                "risk_type": "прогнозный",
                "source": "Нейросетевая модель",
                "severity": "средний",
                "recommendation": "Статистические показатели ниже оптимальных."
            })

        # --- 2. NLP ---
        text_analysis = self.preproc.analyze_text_sentiment(raw_data.business_description)
        text_risk_score = text_analysis["score"]
        
        text_penalty = int(text_risk_score * 20)
        rating -= text_penalty

        if text_risk_score > 0.3:
            risks_data.append({
                "risk_type": "операционный",
                "source": "Анализ описания бизнеса (NLP)",
                "severity": "средний" if text_risk_score > 0.6 else "низкий",
                "recommendation": text_analysis.get("reason", "Обнаружены негативные маркеры в тексте.")
            })

        # --- 3. ПРАВИЛА  ---
        rules = self.kb.get_all_rules(db)
        
        # Словарь для отслеживания уже обработанных полей
        processed_fields = {}
        
        for rule in rules:
            cond = rule.condition_json
            field_name = cond.get("field")
            op = cond.get("op")
            threshold = cond.get("val")
            
            current_val = raw_data.financial_data.get(field_name)
            if current_val is None:
                current_val = getattr(raw_data, field_name, None)

            if current_val is None:
                continue
            
            match = False
            if op == "<" and isinstance(current_val, (int, float)):
                if current_val < threshold:
                    match = True
            elif op == ">" and isinstance(current_val, (int, float)):
                if current_val > threshold:
                    match = True
            elif op == "==":
                if isinstance(current_val, str):
                    if current_val.lower() == str(threshold).lower():
                        match = True
                elif isinstance(current_val, (int, float)):
                    # Для чисел используем погрешность
                    if abs(current_val - float(threshold)) < 0.0001:
                        match = True

            if not match:
                continue
            
            # Используем вынесенный метод
            severity_eval = self.kb.evaluate_rule_severity(rule, current_val, threshold, op)
            
            # Ключ для группировки (поле + оператор)
            field_key = f"{field_name}_{op}"
            
            # Если для этого поля уже есть правило, проверяем severity
            if field_key in processed_fields:
                existing = processed_fields[field_key]
                # Приоритет severity
                severity_priority = {"критический": 3, "средний": 2, "низкий": 1}
                if severity_priority.get(severity_eval["severity"], 0) <= severity_priority.get(existing["severity"], 0):
                    continue  # Пропускаем, если текущее правило не строже
            
            # Создаем запись о риске
            source = f"{get_label(field_name)} = {current_val} ({threshold} {op} нормы, отклонение: {severity_eval['deviation']*100:.1f}%)"
            
            risk_entry = {
                "risk_type": rule.risk_type,
                "source": source,
                "severity": severity_eval["severity"],
                "recommendation": rule.recommendation
            }
            
            processed_fields[field_key] = risk_entry
            rating -= severity_eval["penalty"]

        # Добавляем все уникальные риски
        risks_data.extend(processed_fields.values())

        # --- 4. СОХРАНЕНИЕ (без изменений) ---
        rating = max(0, min(100, rating))

        new_app = CreditApplication(
            company_name=raw_data.company_name,
            industry=raw_data.industry,
            financial_data=raw_data.financial_data,
            business_description=raw_data.business_description,
            user_id=user_id
        )
        db.add(new_app)
        db.commit()
        db.refresh(new_app)

        for r in risks_data:
            risk_entry = FoundRisk(application_id=new_app.id, **r)
            db.add(risk_entry)
        db.commit()

        new_app.rating = rating
        db.commit()

        stats = {
            "input_params": len(raw_data.financial_data) + 2,
            "risks_found": len(risks_data),
            "text_analyzed_words": processed_text.get("token_count", 0)
        }

        summary = "Рейтинг основан на статистической модели и анализе текста." if risks_data else "Профиль надежный."
        
        return AnalysisResult(
            summary=summary,
            risks=[RiskReport(**r) for r in risks_data],
            statistics=stats,
            rating=rating
        )