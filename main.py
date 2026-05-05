from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import re

app = FastAPI()
templates = Jinja2Templates(directory="templates")


# ------------------------
# Простая защита
# ------------------------

def contains_private_data_request(text: str) -> bool:
    text = text.lower()
    bad_words = [
        "чужой телефон",
        "чужой адрес",
        "чужие данные",
        "данные другого человека",
        "пароль другого",
        "карта другого",
    ]
    return any(word in text for word in bad_words)


def redact_pii(text: str) -> str:
    patterns = [
        (r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[EMAIL]'),
        (r'\+?\d[\d\s\-\(\)]{7,}\d', '[PHONE]'),
    ]
    result = text
    for pattern, repl in patterns:
        result = re.sub(pattern, repl, result)
    return result


def assistant_answer(user_text: str) -> str:
    if contains_private_data_request(user_text):
        return "Извините, я не могу помогать с персональными данными других людей."

    safe_text = redact_pii(user_text)

    # Здесь потом можно подключить локальную AI-модель
    return f"Я получил ваш безопасный запрос: {safe_text}"


# ------------------------
# Страницы
# ------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()
    user_text = data.get("message", "")
    answer = assistant_answer(user_text)
    return JSONResponse({"answer": answer})