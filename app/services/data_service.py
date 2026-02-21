import re
import io
import pandas as pd
import pdfplumber
import logging
import datetime
from fastapi import UploadFile

logger = logging.getLogger(__name__)

class DataProcessingService:
    def preprocess_text(self, text: str) -> dict:
        """Токенизация, нормализация"""
        if not text: return {"original_text": "", "tokens": [], "token_count": 0}
        text = text.lower()
        text = re.sub(r'[^a-zа-яё0-9\s]', '', text)
        tokens = text.split()
        return {
            "original_text": text,
            "tokens": tokens,
            "token_count": len(tokens)
        }

    def analyze_text_sentiment(self, text: str) -> dict:
        """ИИ-анализ текста: определяет тональность"""
        if not text: return {"score": 0, "reason": "Нет описания"}
        
        text = text.lower()
        risk_keywords = [
            "суд", "банкротство", "долг", "проверка", "убыток", "кризис",
            "просрочка", "ликвидация", "проблема", "спор", "задолженност",
            "нестабильность", "увольнение", "штраф", "санкции", "дефицит"
        ]
        positive_keywords = [
            "рост", "развитие", "прибыль", "контракт", "инвестиции",
            "стабильность", "надежность", "лидер", "расширение", "новый проект"
        ]

        risk_count = sum(1 for word in risk_keywords if word in text)
        positive_count = sum(1 for word in positive_keywords if word in text)
        total_words = len(text.split())
        
        if total_words == 0: return {"score": 0, "reason": "Пусто"}

        sentiment_score = (risk_count - positive_count * 0.5) / (total_words / 10)
        sentiment_score = max(0, min(1, sentiment_score))

        reason = None
        if sentiment_score > 0.5:
            reason = "Обнаружены негативные маркеры в описании бизнеса"
        
        return {
            "score": round(sentiment_score, 2),
            "reason": reason,
            "risk_words_found": risk_count
        }

    async def parse_financial_document(self, file: UploadFile) -> dict:
        """Улучшенный парсинг CSV и PDF"""
        contents = await file.read()
        filename = file.filename.lower()
        
        extracted_data = {
            "current_ratio": None,
            "debt_to_equity": None,
            "net_profit_margin": None,
            "company_age": None
        }

        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(contents))
                
                # Нормализуем названия колонок: убираем пробелы, приводим к нижнему регистру
                df.columns = [c.strip().lower().replace(' ', '_').replace('-', '_') for c in df.columns]
                
                # Словарь маппинга
                field_aliases = {
                    "current_ratio": ["current_ratio", "liquidity", "ликвидность", "current"],
                    "debt_to_equity": ["debt_to_equity", "leverage", "леверидж", "debt", "задолженност"],
                    "net_profit_margin": ["net_profit_margin", "profit", "рентабельность", "margin", "чистая_прибыль"],
                    "company_age": ["company_age", "age", "возраст", "лет", "years"]
                }

                if not df.empty:
                    last_row = df.iloc[-1]
                    
                    for field, aliases in field_aliases.items():
                        for col in df.columns:
                            if any(alias in col for alias in aliases):
                                try:
                                    val = float(last_row[col])
                                    extracted_data[field] = val
                                    logger.info(f"CSV: Найдено {field} = {val} в колонке '{col}'")
                                    break
                                except ValueError:
                                    pass
                
            elif filename.endswith('.pdf'):
                text = ""
                with pdfplumber.open(io.BytesIO(contents)) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                
                patterns = {
                    "current_ratio": r"(current\s*ratio|коэффициент\s*текущей\s*ликвидности|текущая\s*ликвидность)\s*[:\-]?\s*([\d\.]+)",
                    "debt_to_equity": r"(debt[\/\s]*to[\/\s]*equity|финансовый\s*леверидж|коэффициент\s*задолженности)\s*[:\-]?\s*([\d\.]+)",
                    "net_profit_margin": r"(net\s*profit\s*margin|рентабельность\s*по\s*чистой\s*прибыли|чистая\s*рентабельность)\s*[:\-]?\s*([\d\.\-]+)",
                }
                
                for key, pattern in patterns.items():
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        try:
                            extracted_data[key] = float(match.group(2))
                            logger.info(f"PDF: Найдено {key} = {match.group(2)}")
                        except (IndexError, ValueError):
                            pass
                
                year_match = re.search(r"(основан[а]?\s*в\s*|основание\s*:\s*|founded\s*:\s*)(\d{4})", text, re.IGNORECASE)
                if year_match:
                    founded_year = int(year_match.group(2))
                    current_year = datetime.datetime.now().year
                    extracted_data['company_age'] = current_year - founded_year

            else:
                raise ValueError("Формат файла не поддерживается")

        except Exception as e:
            logger.error(f"Ошибка парсинга файла {filename}: {e}")
        
        return {k: v for k, v in extracted_data.items() if v is not None}

data_service = DataProcessingService()