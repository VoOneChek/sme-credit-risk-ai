from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.database import get_db
from app.models.models import CreditApplication, FoundRisk, User, KnowledgeRule
from app.services.learning_service import learning_service
from app.services.kb_service import kb_service
from app.core.deps import logger, require_admin
from fastapi.templating import Jinja2Templates
from pathlib import Path
import joblib
import os

router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, user = Depends(require_admin), db: Session = Depends(get_db)):
    users_list = db.query(User).all()
    rules_list = db.query(KnowledgeRule).all()
    return templates.TemplateResponse("admin/admin.html", {"request": request, "user": user, "users": users_list, "rules": rules_list})

@router.post("/admin/delete_user/{user_id}")
async def delete_user(user_id: int, user = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if target and target.role != "admin":
        logger.info(f"Удален юзер: {target.username}")
        db.delete(target)
        db.commit()
    return RedirectResponse(url="/admin", status_code=302)

@router.get("/admin/download_log")
async def download_log(user = Depends(require_admin)):
    log_path = Path("app.log")
    return FileResponse(path=log_path, filename="logs.txt", media_type='text/plain')

@router.post("/admin/retrain")
async def retrain_model(user = Depends(require_admin)):
    """Запуск переобучения модели"""
    result = learning_service.retrain_ml_model()
    if result.get("status") == "success":
        return JSONResponse(content={
            "status": "success", 
            "message": "Модель успешно переобучена! Новые данные учтены."
        })
    else:
        return JSONResponse(content={
            "status": "error", 
            "message": result.get("message", "Ошибка при обучении")
        }, status_code=500)

@router.get("/admin/stats", response_class=HTMLResponse)
async def admin_stats(request: Request, user = Depends(require_admin), db: Session = Depends(get_db)):
    """Страница аналитики."""
    
    # 1. Общая статистика
    total_apps = db.query(CreditApplication).count()
    avg_rating = db.query(func.avg(CreditApplication.rating)).scalar() or 0
    
    # 2. Топ-5 частых рисков
    # Группируем риски по названию источника и считаем
    top_risks = db.query(
        FoundRisk.source, 
        func.count(FoundRisk.id).label('count')
    ).group_by(FoundRisk.source).order_by(func.count(FoundRisk.id).desc()).limit(5).all()
    
    # 3. Распределение по отраслям
    industries = db.query(
        CreditApplication.industry,
        func.count(CreditApplication.id).label('count')
    ).group_by(CreditApplication.industry).all()

    return templates.TemplateResponse("admin/stats.html", {
        "request": request,
        "user": user,
        "total_apps": total_apps,
        "avg_rating": round(avg_rating, 2),
        "top_risks": top_risks,
        "industries": industries
    })

@router.post("/admin/add_rule")
async def add_rule(
    request: Request,
    risk_type: str = Form(...),
    rule_name: str = Form(...),
    field: str = Form(...),
    op: str = Form(...),
    val: str = Form(...),
    severity: str = Form(...),
    recommendation: str = Form(...),
    user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Собираем JSON условия
    condition = {"field": field, "op": op, "val": val}
    # Преобразуем val в число если можно
    try:
        condition["val"] = float(val)
    except:
        pass

    new_rule = {
        "risk_type": risk_type,
        "rule_name": rule_name,
        "condition_json": condition,
        "severity": severity,
        "recommendation": recommendation
    }
    
    kb_service.add_rule(db, new_rule)
    logger.info(f"Админ {user.username} добавил правило: {rule_name}")
    
    return RedirectResponse(url="/admin", status_code=302)

@router.post("/admin/edit_rule/{rule_id}")
async def edit_rule(
    rule_id: int,
    risk_type: str = Form(...),
    rule_name: str = Form(...),
    field: str = Form(...),
    op: str = Form(...),
    val: str = Form(...),
    severity: str = Form(...),
    recommendation: str = Form(...),
    user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    condition = {"field": field, "op": op, "val": val}
    try:
        condition["val"] = float(val)
    except:
        pass

    update_data = {
        "risk_type": risk_type,
        "rule_name": rule_name,
        "condition_json": condition,
        "severity": severity,
        "recommendation": recommendation
    }
    
    kb_service.update_rule(db, rule_id, update_data)
    return RedirectResponse(url="/admin", status_code=302)

@router.post("/admin/delete_rule/{rule_id}")
async def delete_rule(rule_id: int, user = Depends(require_admin), db: Session = Depends(get_db)):
    kb_service.delete_rule(db, rule_id)
    logger.info(f"Админ {user.username} удалил правило ID {rule_id}")
    return RedirectResponse(url="/admin", status_code=302)