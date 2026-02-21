from fastapi import APIRouter, Depends, HTTPException, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.core.utils import FINANCIAL_LABELS
from app.models.database import get_db
from app.services.analysis_service import AnalysisService
from app.services.data_service import DataProcessingService
from app.services.kb_service import KnowledgeBaseService
from app.models.models import CreditApplication, FoundRisk, ApplicationData
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json
from app.core.deps import logger, require_user

router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

data_processor = DataProcessingService()
kb_service = KnowledgeBaseService()
analysis_service = AnalysisService(kb_service, data_processor)

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request, user = Depends(require_user)):
    """Главная страница. Доступна только авторизованным."""
    return templates.TemplateResponse("main/index.html", {"request": request, "user": user})

@router.post("/submit", response_class=HTMLResponse)
async def submit_application(
    request: Request,
    company_name: str = Form(...),
    industry: str = Form(...),
    description: str = Form(""),
    # Получаем числовые поля
    current_ratio: float = Form(None),
    debt_to_equity: float = Form(None),
    net_profit_margin: float = Form(None),
    company_age: int = Form(None),
    document: UploadFile = File(None),
    user = Depends(require_user),
    db: Session = Depends(get_db)
):
    user_id = user.id
    logger.info(f"Заявка от {user.username}: {company_name}")

    financials = {
        "current_ratio": current_ratio if current_ratio else 1.0,
        "debt_to_equity": debt_to_equity if debt_to_equity else 1.0,
        "net_profit_margin": net_profit_margin if net_profit_margin else 0.0,
        "company_age": company_age if company_age else 0
    }

    if document and document.filename:
        file_data = await data_processor.parse_financial_document(document)
        if file_data:
            financials.update(file_data) # Подставляем данные из файла

    input_data = ApplicationData(
        company_name=company_name,
        industry=industry,
        financial_data=financials,
        business_description=description
    )

    try:
        result = analysis_service.analyze_application(input_data, user_id=user_id, db=db)
    except Exception as e:
        logger.error(f"Ошибка анализа: {e}")
        return HTMLResponse(content=f"<h2>Ошибка: {e}</h2>", status_code=500)

    return templates.TemplateResponse("main/result.html", {"request": request, "result": result, "user": user})

@router.get("/profile", response_class=HTMLResponse)
async def profile(request: Request, user = Depends(require_user), db: Session = Depends(get_db)):
    """Личный кабинет. История заявок."""
    history = db.query(CreditApplication).filter(CreditApplication.user_id == user.id).order_by(CreditApplication.id.desc()).all()
    return templates.TemplateResponse("main/profile.html", {"request": request, "user": user, "history": history})

@router.get("/history/{app_id}", response_class=HTMLResponse)
async def application_details(
    request: Request, 
    app_id: int, 
    user = Depends(require_user), 
    db: Session = Depends(get_db)
):
    """Страница детального просмотра заявки."""
    # Находим заявку
    application = db.query(CreditApplication).filter(CreditApplication.id == app_id).first()
    
    # Проверка прав: админ видит всё, обычный юзер — только свои заявки
    if not application or (user.role != "admin" and application.user_id != user.id):
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    
    # Получаем риски, связанные с этой заявкой
    risks = db.query(FoundRisk).filter(FoundRisk.application_id == app_id).all()
    
    return templates.TemplateResponse("main/details.html", {
        "request": request, 
        "user": user, 
        "app": application, 
        "risks": risks,
        "labels": FINANCIAL_LABELS
    })