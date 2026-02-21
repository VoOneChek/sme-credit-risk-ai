from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Float, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.models.database import Base
import datetime
import enum

class RoleEnum(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    user = "user"

class RiskTypeEnum(str, enum.Enum):
    FINANCIAL = "финансовый"
    OPERATIONAL = "операционный"
    INDUSTRY = "отраслевой"
    PREDICTIVE = "прогнозный"

class SeverityEnum(str, enum.Enum):
    CRITICAL = "критический"
    MEDIUM = "средний"
    LOW = "низкий"

# --- Пользователи ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String) # В реальном проекте храним хэш!
    role = Column(String, default="user") # admin, operator, user
    applications = relationship("CreditApplication", back_populates="user", cascade="all, delete-orphan")

# --- Заявки на кредит (История) ---
class CreditApplication(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String)
    industry = Column(String)
    financial_data = Column(JSON) # Храним JSON с коэффицентами
    business_description = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    rating = Column(Integer, default=0)
    status = Column(String, default="Обработан") # или "Отклонен"
    created_at = Column(DateTime, default=datetime.datetime.now)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    user = relationship("User", back_populates="applications")
    risks = relationship("FoundRisk", back_populates="application", cascade="all, delete-orphan")

# --- База Знаний (Правила) ---
class KnowledgeRule(Base):
    __tablename__ = "knowledge_rules"
    id = Column(Integer, primary_key=True, index=True)
    risk_type = Column(String) # финансовый, отраслевой...
    rule_name = Column(String) # Название правила
    condition_json = Column(JSON) # {"field": "current_ratio", "op": "<", "val": 1.5}
    severity = Column(String)
    recommendation = Column(String)

# --- Найденные риски (для отчетов) ---
class FoundRisk(Base):
    __tablename__ = "found_risks"
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"))
    risk_type = Column(String)
    source = Column(String)
    severity = Column(String)
    recommendation = Column(String)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"))
    application = relationship("CreditApplication", back_populates="risks")

class RiskReport(BaseModel):
    risk_type: RiskTypeEnum
    source: str  # локализация риска
    severity: SeverityEnum
    recommendation: Optional[str] = None

class AnalysisResult(BaseModel):
    summary: str  # "Риски не обнаружены..." или список
    risks: List[RiskReport]
    statistics: dict
    rating: int  # Итоговый рейтинг кредитоспособности

class ApplicationData(BaseModel):
    company_name: str
    financial_data: dict  # JSON с коэффициентами (ликвидность, рентабельность и т.д.)
    business_description: str  # Текстовое описание (для NLP)
    industry: str