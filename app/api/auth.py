from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.models import User
from passlib.context import CryptContext
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.core.deps import logger

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request, "error": None})

@router.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        logger.warning(f"Неудачный вход: {username}")
        return templates.TemplateResponse("auth/login.html", {"request": request, "error": "Неверные данные"})
    
    response = RedirectResponse(url="/profile", status_code=302)
    response.set_cookie(key="user_id", value=str(user.id), httponly=True)
    logger.info(f"Вход пользователя: {username}")
    return response

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request, "error": None})

@router.post("/register", response_class=HTMLResponse)
async def register_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if db.query(User).filter(User.username == username).first():
        return templates.TemplateResponse("auth/register.html", {"request": request, "error": "Имя занято"})
    
    hashed_pw = pwd_context.hash(password)
    new_user = User(username=username, hashed_password=hashed_pw, role="user")
    db.add(new_user)
    db.commit()
    logger.info(f"Новый пользователь: {username}")
    
    response = RedirectResponse(url="/login", status_code=302)
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("user_id")
    return response