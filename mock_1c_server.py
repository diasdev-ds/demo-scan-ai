"""
МОК-СЕРВЕР 1С — имитирует 1С:Предприятие с интерфейсом OData.

Зачем: разрабатывать и тестировать интеграцию на Mac, не имея настоящей 1С.
Код, который сюда отправляет документы, потом без изменений работает с реальной 1С —
меняется только адрес сервера.

Запуск:  python3 mock_1c_server.py
Журнал:  http://127.0.0.1:8000
"""
import json
import os
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

DB_FILE = os.path.join(os.path.dirname(__file__), "mock_1c_db.json")


def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"documents": []}


def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


# ============ OData endpoint (как у настоящей 1С) ============
# Реальная 1С: POST http://server/base/odata/standard.odata/Document_ПоступлениеТоваровУслуг
@app.route("/odata/standard.odata/Document_<doc_type>", methods=["POST"])
def create_document(doc_type):
    payload = request.get_json(force=True)
    db = load_db()

    ref_key = str(uuid.uuid4())
    number = payload.get("Number") or f"{len(db['documents']) + 1:08d}"

    doc = {
        "Ref_Key": ref_key,
        "Тип": doc_type,
        "Number": number,
        "Date": payload.get("Date", datetime.now().strftime("%Y-%m-%dT%H:%M:%S")),
        "Контрагент": payload.get("Контрагент", ""),
        "БИН": payload.get("БИН", ""),
        "СуммаДокумента": payload.get("СуммаДокумента", ""),
        "НДС": payload.get("НДС", ""),
        "Posted": False,  # создаётся как ЧЕРНОВИК — бухгалтер потом проводит
        "Комментарий": payload.get("Комментарий", ""),
        "Товары": payload.get("Товары", []),
        "_получен": datetime.now().strftime("%H:%M:%S"),
    }
    db["documents"].insert(0, doc)
    save_db(db)

    # 1С на создание документа отвечает объектом с Ref_Key — повторяем поведение
    return jsonify({
        "Ref_Key": ref_key,
        "Number": number,
        "Posted": False,
        "_status": "Документ создан в 1С (черновик)"
    }), 201


@app.route("/odata/standard.odata/Document_<doc_type>/clear", methods=["POST"])
def clear(doc_type):
    save_db({"documents": []})
    return jsonify({"ok": True})


# ============ Визуальный журнал (имитация интерфейса 1С) ============
JOURNAL_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="3">
<title>1С:Предприятие — Журнал документов</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, sans-serif; }
  body { background: #e8eef3; padding: 0; }
  .top { background: #c5d4e0; padding: 8px 16px; border-bottom: 1px solid #9bb0c2;
         display: flex; align-items: center; gap: 12px; }
  .logo { background: #d4a017; color: #fff; font-weight: 700; padding: 4px 10px;
          border-radius: 3px; font-size: 14px; letter-spacing: 1px; }
  .top h1 { font-size: 15px; color: #2c3e50; font-weight: 600; }
  .path { background: #f4f7fa; padding: 6px 16px; font-size: 12px; color: #5a6b7a;
          border-bottom: 1px solid #d5dfe8; }
  .toolbar { padding: 8px 16px; background: #f0f4f7; border-bottom: 1px solid #d5dfe8;
             display:flex; gap:8px; }
  .btn { background:#fff; border:1px solid #b0c0cc; padding:5px 12px; border-radius:3px;
         font-size:12px; color:#2c3e50; cursor:pointer; }
  table { width: 100%; border-collapse: collapse; background: #fff; }
  th { background: #dde7ee; padding: 8px 10px; text-align: left; font-size: 12px;
       color: #3c4f5e; border: 1px solid #c5d2dc; font-weight: 600; }
  td { padding: 7px 10px; font-size: 13px; border: 1px solid #e1e8ed; color: #2c3e50; }
  tr:hover td { background: #eef6ff; }
  .status { display:inline-block; width:14px; height:14px; border-radius:2px;
            vertical-align:middle; margin-right:6px; }
  .draft { border:2px solid #b0b0b0; background:#fff; }
  .posted { background:#2ecc71; }
  .label-ai { background:#e8f4fd; color:#2980b9; font-size:10px; padding:1px 6px;
              border-radius:8px; border:1px solid #aed6f1; }
  .sum { text-align:right; font-variant-numeric: tabular-nums; font-weight:500; }
  .empty { padding:40px; text-align:center; color:#90a4b0; font-size:14px; }
  .counter { margin-left:auto; font-size:12px; color:#5a6b7a; }
  .live { color:#27ae60; font-size:11px; }
</style>
</head>
<body>
  <div class="top">
    <span class="logo">1С</span>
    <h1>Поступление (акты, накладные, УПД)</h1>
    <span class="counter live">● обновляется автоматически</span>
  </div>
  <div class="path">Покупки › Поступление (акты, накладные, УПД)</div>
  <div class="toolbar">
    <span class="btn">＋ Создать</span>
    <span class="btn">✓ Провести</span>
    <span class="btn">🔍 Найти</span>
    <span class="counter">Всего документов: {{ docs|length }}</span>
  </div>
  <table>
    <tr>
      <th style="width:30px"></th>
      <th style="width:90px">Номер</th>
      <th style="width:110px">Дата</th>
      <th>Контрагент</th>
      <th style="width:130px">БИН</th>
      <th style="width:130px" class="sum">Сумма</th>
      <th style="width:110px">Комментарий</th>
      <th style="width:70px">Получен</th>
    </tr>
    {% for d in docs %}
    <tr>
      <td><span class="status {{ 'posted' if d.Posted else 'draft' }}"></span></td>
      <td>{{ d.Number }}</td>
      <td>{{ d.Date_fmt }}</td>
      <td>{{ d.Контрагент }}</td>
      <td>{{ d.БИН }}</td>
      <td class="sum">{{ d.СуммаДокумента }}</td>
      <td>{% if 'AI' in d.Комментарий %}<span class="label-ai">Создано AI</span>{% else %}{{ d.Комментарий }}{% endif %}</td>
      <td style="color:#90a4b0">{{ d._получен }}</td>
    </tr>
    {% endfor %}
  </table>
  {% if not docs %}
  <div class="empty">Документов пока нет.<br>Отправьте скан в Telegram-бот — документ появится здесь автоматически.</div>
  {% endif %}
</body>
</html>
"""


@app.route("/")
def journal():
    db = load_db()
    docs = db["documents"]
    for d in docs:
        raw = d.get("Date", "")
        try:
            d["Date_fmt"] = datetime.fromisoformat(raw).strftime("%d.%m.%Y")
        except (ValueError, TypeError):
            d["Date_fmt"] = raw
    return render_template_string(JOURNAL_HTML, docs=docs)


if __name__ == "__main__":
    print("=" * 55)
    print("  МОК-СЕРВЕР 1С запущен")
    print("  Журнал документов:  http://127.0.0.1:8000")
    print("  OData endpoint:      http://127.0.0.1:8000/odata/...")
    print("=" * 55)
    app.run(host="127.0.0.1", port=8000, debug=False)
