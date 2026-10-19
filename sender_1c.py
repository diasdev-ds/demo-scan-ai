"""
Модуль отправки распознанных документов в 1С через OData.

ВАЖНО: этот код одинаков и для мока, и для боевой 1С.
Чтобы переключиться на реальную 1С — поменяй ODATA_URL и добавь логин/пароль.
"""
import os
import requests
from requests.auth import HTTPBasicAuth

# Локальный мок. Для боевой 1С будет вида:
# http://server/base/odata/standard.odata
ODATA_URL = os.environ.get("ODATA_URL", "http://127.0.0.1:8000/odata/standard.odata")
ODATA_USER = os.environ.get("ODATA_USER", "")
ODATA_PASS = os.environ.get("ODATA_PASS", "")

# Имя документа в 1С (в реальной базе зависит от конфигурации).
# Для Бухгалтерии: Document_ПоступлениеТоваровУслуг
DOC_NAME = os.environ.get("ODATA_DOC", "ПоступлениеТоваровУслуг")


def _date_iso(date_str: str) -> str:
    """'12.06.2026' -> '2026-06-12T00:00:00' (формат 1С). Терпим к мусору."""
    try:
        d, m, y = date_str.strip().split(".")
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}T00:00:00"
    except (ValueError, AttributeError):
        return date_str


def build_payload(data: dict) -> dict:
    """Распознанный JSON -> тело документа для 1С OData."""
    тип = data.get("тип", "накладная")
    if тип == "авр":
        контрагент = data.get("исполнитель", {}).get("название", "")
        бин = data.get("исполнитель", {}).get("ИИН_БИН", "")
        позиции = data.get("работы", [])
    else:
        контрагент = data.get("поставщик", {}).get("название", "")
        бин = data.get("поставщик", {}).get("ИИН_БИН", "")
        позиции = data.get("товары", [])

    товары = [{
        "Номенклатура": p.get("название") or p.get("описание", ""),
        "Количество": p.get("количество", ""),
        "Цена": p.get("цена", ""),
        "Сумма": p.get("сумма", ""),
    } for p in позиции]

    return {
        "Number": data.get("номер", ""),
        "Date": _date_iso(data.get("дата", "")),
        "Контрагент": контрагент,
        "БИН": бин,
        "СуммаДокумента": data.get("итого_с_НДС") or data.get("итого", ""),
        "НДС": data.get("НДС", ""),
        "Комментарий": f"Создано AI / {тип}",
        "Товары": товары,
    }


def send_to_1c(data: dict) -> dict:
    """Отправляет документ в 1С. Возвращает ответ 1С (Ref_Key, Number, статус)."""
    payload = build_payload(data)
    тип = data.get("тип", "накладная")
    # Имя документа: накладная и АВР в реальной Бухгалтерии — это разные документы.
    doc_name = DOC_NAME if тип == "накладная" else "АктВыполненныхРабот"
    url = f"{ODATA_URL}/Document_{doc_name}?$format=json"

    auth = HTTPBasicAuth(ODATA_USER, ODATA_PASS) if ODATA_USER else None
    resp = requests.post(url, json=payload, auth=auth, timeout=30)
    resp.raise_for_status()
    return resp.json()
