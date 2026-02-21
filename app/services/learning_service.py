from sqlalchemy.orm import Session
import logging
import os
import joblib
import numpy as np

from app.services import kb_service

logger = logging.getLogger(__name__)

class LearningService:
    def __init__(self, kb_service):
        self.kb = kb_service

    def retrain_ml_model(self):
        """ Запускает процесс обучения ML-модели. """

        logger.info("Запуск процедуры дообучения модели...")
        try:
            import train_model
            train_model.train_credit_model()
            
            from app.services import analysis_service
            model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "credit_model.pkl")
            if os.path.exists(model_path):
                analysis_service.model = joblib.load(model_path)
                logger.info("Модель успешно перезагружена в памяти.")
            
            return {"status": "success", "message": "Модель переобучена."}
        except Exception as e:
            logger.error(f"Ошибка при обучении: {e}")
            return {"status": "error", "message": str(e)}

learning_service = LearningService(kb_service)