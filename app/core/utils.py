FINANCIAL_LABELS = {
    "current_ratio": "Коэффициент текущей ликвидности",
    "debt_to_equity": "Коэффициент финансового левериджа",
    "net_profit_margin": "Рентабельность по чистой прибыли",
    "company_age": "Возраст компании",
    "industry": "Отрасль"
}

def get_label(key):
    return FINANCIAL_LABELS.get(key, key)