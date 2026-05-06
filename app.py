from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
import re

app = FastAPI(title="tolikAi Public", version="1.0")


# -----------------------------
# Простая защита от чужих данных
# -----------------------------

def contains_private_data_request(text: str) -> bool:
    text = text.lower()
    bad_words = [
        "чужой телефон",
        "чужой адрес",
        "чужие данные",
        "данные другого человека",
        "пароль другого",
        "карта другого",
        "чужой пароль",
        "чужой номер",
        "чужой email",
        "чужая почта",
    ]
    return any(word in text for word in bad_words)


def redact_pii(text: str) -> str:
    patterns = [
        (r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[EMAIL]'),
        (r'\+?\d[\d\s\-\(\)]{7,}\d', '[PHONE]'),
        (r'\b\d{16}\b', '[CARD]'),
    ]
    result = text
    for pattern, repl in patterns:
        result = re.sub(pattern, repl, result)
    return result


def assistant_answer(user_text: str) -> str:
    text = user_text.strip()
    lower = text.lower()

    if not text:
        return "Пожалуйста, напишите сообщение."

    if contains_private_data_request(lower):
        return "Извините, я не могу помогать с персональными данными других людей."

    safe_text = redact_pii(text)

    if "привет" in lower:
        return "Привет! Я tolikAi Public. Чем могу помочь?"
    if "как дела" in lower:
        return "Всё хорошо. Я работаю и отвечаю через веб-интерфейс."
    if "кто ты" in lower or "что ты умеешь" in lower:
        return "Я tolikAi Public — веб-помощник для обычных задач."
    if "помоги" in lower:
        return f"Я помогу с этим запросом: {safe_text}"

    return f"tolikAi Public: я получил ваш запрос: {safe_text}"


# -----------------------------
# HTML-страница
# -----------------------------

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>tolikAi Public</title>

    <!-- Чтобы не было 404 на favicon -->
    <link rel="icon" href="data:," />

    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(180deg, #f5f7fb, #eef2f7);
            margin: 0;
            padding: 20px;
            color: #111;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 16px;
            box-shadow: 0 4px 18px rgba(0,0,0,0.08);
        }

        h1 {
            margin: 0 0 8px 0;
        }

        .small {
            color: #666;
            font-size: 13px;
            margin-bottom: 16px;
        }

        #chat {
            border: 1px solid #ddd;
            min-height: 360px;
            padding: 15px;
            border-radius: 12px;
            background: #fafafa;
            white-space: pre-wrap;
            overflow-y: auto;
            margin-bottom: 15px;
        }

        .row {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        input {
            flex: 1;
            min-width: 220px;
            padding: 12px;
            border: 1px solid #ccc;
            border-radius: 10px;
            font-size: 16px;
            outline: none;
        }

        input:focus {
            border-color: #0066ff;
        }

        button {
            padding: 12px 16px;
            border: none;
            border-radius: 10px;
            background: #0066ff;
            color: white;
            cursor: pointer;
            font-size: 16px;
        }

        button:hover {
            background: #0052cc;
        }

        .secondary {
            background: #666;
        }

        .secondary:hover {
            background: #444;
        }

        .user {
            color: #1a73e8;
            margin-bottom: 10px;
        }

        .bot {
            color: #137333;
            margin-bottom: 14px;
        }

        .hint {
            margin-top: 14px;
            font-size: 13px;
            color: #666;
        }

        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            background: #e8f0fe;
            color: #174ea6;
            font-size: 12px;
            margin-left: 8px;
            vertical-align: middle;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>tolikAi Public <span class="badge">публичная версия</span></h1>
        <div class="small">
            Сайт доступен всем, кто откроет ссылку. Без авторизации.
        </div>

        <div id="chat"></div>

        <div class="row">
            <input id="message" type="text" placeholder="Напишите сообщение..." />
            <button onclick="sendMessage()">Отправить</button>
            <button class="secondary" onclick="clearChat()">Очистить чат</button>
        </div>

        <div class="hint">
            Подсказка: нажмите Enter, чтобы отправить сообщение.
        </div>
    </div>

    <script>
        const chat = document.getElementById("chat");
        const input = document.getElementById("message");

        function addMessage(type, text) {
            const div = document.createElement("div");
            div.className = type;
            div.textContent = (type === "user" ? "Вы: " : "tolikAi: ") + text;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        async function sendMessage() {
            const text = input.value.trim();
            if (!text) return;

            addMessage("user", text);
            input.value = "";

            try {
                const response = await fetch("/api/chat", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ message: text })
                });

                const data = await response.json();
                addMessage("bot", data.answer || "Пустой ответ от сервера.");
            } catch (error) {
                addMessage("bot", "Ошибка соединения с сервером.");
            }
        }

        function clearChat() {
            chat.innerHTML = "";
            addMessage("bot", "Чат очищен.");
        }

        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                sendMessage();
            }
        });

        addMessage("bot", "Здравствуйте! Я tolikAi Public. Напишите сообщение.");
    </script>
</body>
</html>
"""


# -----------------------------
# Роуты
# -----------------------------

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_PAGE


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()
    user_text = data.get("message", "")
    answer = assistant_answer(user_text)
    return JSONResponse({"answer": answer})