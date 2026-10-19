"""
Модуль распознавания документов через Gemini Vision.
Используется и ботом, и пакетным скриптом.
"""
import os
import json
import io
import fitz  # PyMuPDF
from google import genai
from google.genai import types

MODEL = "gemini-2.5-flash"

PROMPT_NAKLADNAYA = """
Ты — система распознавания документов. Перед тобой скан накладной на русском или казахском языке.
Извлеки данные и верни ТОЛЬКО валидный JSON без пояснений:
{
  "тип": "накладная",
  "номер": "", "дата": "",
  "поставщик": { "название": "", "ИИН_БИН": "" },
  "получатель": { "название": "", "ИИН_БИН": "" },
  "товары": [ { "название": "", "количество": "", "единица": "", "цена": "", "сумма": "" } ],
  "итого": "", "НДС": "", "итого_с_НДС": ""
}
Если поле не найдено — пустая строка. Числа как строки, сохраняя формат документа.
"""

PROMPT_AVR = """
Ты — система распознавания документов. Перед тобой скан акта выполненных работ (АВР) на русском или казахском.
Извлеки данные и верни ТОЛЬКО валидный JSON без пояснений:
{
  "тип": "авр",
  "номер": "", "дата": "",
  "исполнитель": { "название": "", "ИИН_БИН": "" },
  "заказчик": { "название": "", "ИИН_БИН": "" },
  "работы": [ { "описание": "", "количество": "", "единица": "", "цена": "", "сумма": "" } ],
  "итого": "", "НДС": "", "итого_с_НДС": ""
}
Если поле не найдено — пустая строка. Числа как строки, сохраняя формат документа.
"""

PROMPT_AUTO = """
Ты — система распознавания первичных бухгалтерских документов Казахстана.
Сначала определи тип документа: "накладная" или "авр" (акт выполненных работ).
Затем извлеки данные и верни ТОЛЬКО валидный JSON.

Если накладная:
{
  "тип": "накладная", "номер": "", "дата": "",
  "поставщик": { "название": "", "ИИН_БИН": "" },
  "получатель": { "название": "", "ИИН_БИН": "" },
  "товары": [ { "название": "", "количество": "", "единица": "", "цена": "", "сумма": "" } ],
  "итого": "", "НДС": "", "итого_с_НДС": ""
}

Если акт выполненных работ:
{
  "тип": "авр", "номер": "", "дата": "",
  "исполнитель": { "название": "", "ИИН_БИН": "" },
  "заказчик": { "название": "", "ИИН_БИН": "" },
  "работы": [ { "описание": "", "количество": "", "единица": "", "цена": "", "сумма": "" } ],
  "итого": "", "НДС": "", "итого_с_НДС": ""
}
Если поле не найдено — пустая строка. Числа как строки, сохраняя формат документа.
"""


_cached_client = None


def _client():
    global _cached_client
    if _cached_client is None:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY не задан")
        _cached_client = genai.Client(api_key=api_key)
    return _cached_client


def file_to_images(data: bytes, filename: str) -> list[bytes]:
    """PDF → список PNG-страниц. Картинка → как есть."""
    name = filename.lower()
    if name.endswith(".pdf"):
        doc = fitz.open(stream=data, filetype="pdf")
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            images.append(pix.tobytes("png"))
        doc.close()
        return images
    return [data]  # уже изображение (jpg/png)


def extract(data: bytes, filename: str, doc_type: str = "auto") -> dict:
    """
    Распознаёт документ. doc_type: "накладная" | "авр" | "auto".
    Возвращает dict с распознанными полями.
    """
    images = file_to_images(data, filename)
    if doc_type == "накладная":
        prompt = PROMPT_NAKLADNAYA
    elif doc_type == "авр":
        prompt = PROMPT_AVR
    else:
        prompt = PROMPT_AUTO

    parts = [types.Part.from_text(text=prompt)]
    for img in images:
        parts.append(types.Part.from_bytes(data=img, mime_type="image/png"))

    response = _client().models.generate_content(
        model=MODEL,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    raw = response.text.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"ошибка": raw, "файл": filename}
