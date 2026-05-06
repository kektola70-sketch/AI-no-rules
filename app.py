from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import re

app = FastAPI(title="tolikAi Private", version="1.0")


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

    # Здесь потом можно подключить локальную модель
    return f"tolikAi Private: я получил ваш запрос: {safe_text}"


HTML_PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>tolikAi Private</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f3f5f7;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 14px;
            box-shadow: 0 2px 14px rgba(0,0,0,0.08);
        }
        h1 { margin-top: 0; }
        #chat {
            border: 1px solid #ddd;
            min-height: 320px;
            padding: 15px;
            border-radius: 10px;
            background: #fafafa;
            white-space: pre-wrap;
            overflow-y: auto;
            margin-bottom: 15px;
        }
        .row {
            display: flex;
            gap: 10px;
        }
        input {
            flex: 1;
            padding: 12px;
            border: 1px solid #ccc;
            border-radius: 8px;
            font-size: 16px;
        }
        button {
            padding: 12px 16px;
            border: none;
            border-radius: 8px;
            background: #0066ff;
            color: white;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover { background: #0052cc; }
        .user { color: #1a73e8; margin-bottom: 10px; }
        .bot { color: #137333; margin-bottom: 14px; }
        .small { color: #666; font-size: 13px; margin-top: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>tolikAi Private</h1>
        <div class="small">Локальная версия для России. Без интернета. Без передачи данных наружу.</div>
        <div id="chat"></div>

        <div class="row">
            <input id="message" type="text" placeholder="Напишите сообщение..." />
            <button onclick="sendMessage()">Отправить</button>
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
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message: text })
                });

                const data = await response.json();
                addMessage("bot", data.answer);
            } catch (error) {
                addMessage("bot", "Ошибка соединения с сервером. Проверь, запущен ли Python-сервер.");
            }
        }

        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") sendMessage();
        });
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_PAGE


@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()
    user_text = data.get("message", "")
    answer = assistant_answer(user_text)
    return JSONResponse({"answer": answer})