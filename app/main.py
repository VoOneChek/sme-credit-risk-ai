# main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.models.database import engine, Base, get_db
from app.models.models import User, KnowledgeRule
from passlib.context import CryptContext

# Импорт роутеров
from app.api import auth, views, admin

# Импорт сервисов
from app.services.kb_service import KnowledgeBaseService
from app.services.learning_service import LearningService

kb_service = KnowledgeBaseService()
learning_service = LearningService(kb_service)

# Инициализация БД
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    # Создаем админа
    if not db.query(User).filter(User.username == "admin").first():
        admin = User(username="admin", hashed_password=pwd_context.hash("admin"), role="admin")
        db.add(admin)
        db.commit()
    
    # Создаем правила
    if not kb_service.get_all_rules(db):
        print("БЗ пуста, инициализация стандартных правил...")
        
        default_rules = [
            {
                "risk_type": "финансовый", "rule_name": "Низкая ликвидность", 
                "condition_json": {"field": "current_ratio", "op": "<", "val": 1.5}, 
                "severity": "критический", "recommendation": "Требуется обеспечение залогом."
            },
            {
                "risk_type": "финансовый", "rule_name": "Высокая долговая нагрузка", 
                "condition_json": {"field": "debt_to_equity", "op": ">", "val": 2.0}, 
                "severity": "средний", "recommendation": "Ограничить сумму кредита."
            },
            {
                "risk_type": "финансовый", "rule_name": "Убыточная деятельность", 
                "condition_json": {"field": "net_profit_margin", "op": "<", "val": 0.0}, 
                "severity": "критический", "recommendation": "Отказ в кредитовании."
            },
            {
                "risk_type": "операционный", "rule_name": "Малый срок деятельности", 
                "condition_json": {"field": "company_age", "op": "<", "val": 1}, 
                "severity": "средний", "recommendation": "Запросить поручительство."
            }
        ]
        
        for rule_data in default_rules:
            kb_service.add_rule(db, rule_data)
            
    db.close()
    yield

app = FastAPI(lifespan=lifespan)

# Подключение роутеров
app.include_router(auth.router)
app.include_router(views.router)
app.include_router(admin.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)