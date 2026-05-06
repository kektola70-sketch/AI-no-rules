from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
import random
import re

app = FastAPI(title="tolikAi Private Engine", version="2.0")


# ============================================================
# СЕССИИ
# ============================================================

SESSIONS = {}


def get_session(session_id: str) -> dict:
    if not session_id:
        session_id = "default"

    if session_id not in SESSIONS:
        SESSIONS[session_id] = {
            "name": None,
            "history": []
        }
    return SESSIONS[session_id]


def reset_session(session_id: str) -> None:
    if session_id in SESSIONS:
        SESSIONS[session_id] = {
            "name": None,
            "history": []
        }


# ============================================================
# НОРМАЛИЗАЦИЯ
# ============================================================

def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = re.sub(r"[^\w\sа-яА-Я-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> list[str]:
    text = normalize(text)
    tokens = text.split()
    stopwords = {
        "и", "а", "но", "или", "что", "как", "когда", "где", "почему", "зачем",
        "я", "ты", "мы", "вы", "он", "она", "оно", "они",
        "это", "в", "на", "по", "с", "со", "к", "ко", "от", "до", "за",
        "у", "из", "для", "о", "об", "про", "не", "нет", "да", "ли"
    }
    return [t for t in tokens if t not in stopwords]


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# ============================================================
# ПРИВАТНОСТЬ И ЗАПРЕТЫ
# ============================================================

PRIVATE_REQUEST_PHRASES = [
    "чужие данные",
    "данные другого человека",
    "чужой телефон",
    "чужой адрес",
    "чужой пароль",
    "чужой номер",
    "чужой email",
    "чужая почта",
    "чужая карта",
    "паспорт другого",
    "номер карты другого",
    "персональные данные другого",
]

DENY_SELF_MODIFY_PHRASES = [
    "измени свой код",
    "измени себя",
    "перепиши себя",
    "обнови свой код",
    "измени программу",
    "перепиши программу",
    "самообучайся без контроля",
]

DENY_INTERNET_PHRASES = [
    "выйди в интернет",
    "зайди в интернет",
    "подключись к интернету",
    "открой сайт",
    "скачай файл",
    "скачай",
    "загрузи файл",
    "отправь в интернет",
    "поиск в интернете",
]

DENY_DEVICE_PHRASES = [
    "управляй устройством",
    "включи устройство",
    "выключи устройство",
    "настрой систему",
    "изменить файлы",
    "удали файл",
    "создай файл",
    "переименуй файл",
    "запусти программу",
    "открой программу",
]

DENY_FILE_ACCESS_PHRASES = [
    "прочитай файл",
    "изменить файл",
    "удали файл",
    "создай файл",
    "скачай файл",
    "запиши в файл",
    "открой мои файлы",
]

PII_PATTERNS = [
    (r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[EMAIL]'),
    (r'\+?\d[\d\s\-\(\)]{7,}\d', '[PHONE]'),
    (r'\b\d{16}\b', '[CARD]'),
]


def redact_pii(text: str) -> str:
    result = text
    for pattern, repl in PII_PATTERNS:
        result = re.sub(pattern, repl, result)
    return result


def is_private_data_request(text: str) -> bool:
    lower = normalize(text)
    return any(phrase in lower for phrase in PRIVATE_REQUEST_PHRASES)


def is_self_modify_request(text: str) -> bool:
    lower = normalize(text)
    return any(phrase in lower for phrase in DENY_SELF_MODIFY_PHRASES)


def is_internet_request(text: str) -> bool:
    lower = normalize(text)
    return any(phrase in lower for phrase in DENY_INTERNET_PHRASES)


def is_device_request(text: str) -> bool:
    lower = normalize(text)
    return any(phrase in lower for phrase in DENY_DEVICE_PHRASES)


def is_file_request(text: str) -> bool:
    lower = normalize(text)
    return any(phrase in lower for phrase in DENY_FILE_ACCESS_PHRASES)


# ============================================================
# НАМЕРЕНИЯ
# ============================================================

@dataclass
class IntentRule:
    name: str
    examples: list[str]
    keywords: set[str] = field(default_factory=set)
    priority: int = 0


INTENTS = [
    IntentRule(
        name="greet",
        examples=["привет", "здравствуй", "добрый день", "доброе утро", "добрый вечер", "хай"],
        keywords={"привет", "здравствуй", "здравствуйте", "добрый", "утро", "вечер", "день", "хай", "hello", "hi"},
        priority=1
    ),
    IntentRule(
        name="bye",
        examples=["пока", "до свидания", "увидимся", "до встречи"],
        keywords={"пока", "свидания", "встречи", "увидимся", "bye"},
        priority=1
    ),
    IntentRule(
        name="thanks",
        examples=["спасибо", "благодарю", "спс", "очень спасибо"],
        keywords={"спасибо", "благодарю", "спс", "thanks"},
        priority=1
    ),
    IntentRule(
        name="who_are_you",
        examples=["кто ты", "что ты такое", "что это за ии", "кто ты такой"],
        keywords={"кто", "ты", "ишь", "искусственный", "интеллект", "ии"},
        priority=1
    ),
    IntentRule(
        name="capabilities",
        examples=["что ты умеешь", "что ты можешь", "какие у тебя возможности", "что умеешь"],
        keywords={"умеешь", "можешь", "возможности", "способен", "уметь"},
        priority=1
    ),
    IntentRule(
        name="coding_help",
        examples=["помоги с кодом", "ошибка в python", "как написать код", "fastapi не работает", "html css js"],
        keywords={"python", "fastapi", "uvicorn", "html", "css", "javascript", "js", "код", "ошибка", "программа", "браузер", "powershell"},
        priority=1
    ),
    IntentRule(
        name="time",
        examples=["сколько времени", "который час", "время"],
        keywords={"время", "час", "сейчас"},
        priority=1
    ),
    IntentRule(
        name="date",
        examples=["какая сегодня дата", "какое сегодня число", "дата"],
        keywords={"дата", "число", "сегодня"},
        priority=1
    ),
    IntentRule(
        name="name_intro",
        examples=["меня зовут толик", "зови меня толик", "я толик"],
        keywords={"меня", "зовут", "зови", "имя"},
        priority=2
    ),
]


def match_intent(text: str) -> str | None:
    norm = normalize(text)
    tokens = set(tokenize(text))
    if not norm:
        return None

    best_name = None
    best_score = 0.0

    for rule in INTENTS:
        score = rule.priority * 100

        # Совпадения по фразам
        for phrase in rule.examples:
            if phrase in norm:
                score += 8.0
            else:
                score += similarity(norm, phrase) * 2.0

        # Совпадения по ключевым словам
        keyword_hits = 0
        for kw in rule.keywords:
            if kw in tokens or kw in norm:
                keyword_hits += 1
        score += keyword_hits * 2.0

        if score > best_score:
            best_score = score
            best_name = rule.name

    # Порог, чтобы не ловить ложные срабатывания
    if best_score >= 8.0:
        return best_name
    return None


# ============================================================
# ДВИЖОК
# ============================================================

class TolikAiEngine:
    def __init__(self):
        self.greet_responses = [
            "Привет, {name}! Я tolikAi Private Engine.",
            "Здравствуйте, {name}! Чем помочь?",
            "Рад видеть вас, {name}!"
        ]
        self.bye_responses = [
            "Пока, {name}! Если что — я на месте.",
            "До встречи, {name}!",
            "Хорошего дня, {name}!"
        ]
        self.thanks_responses = [
            "Пожалуйста, {name}!",
            "Всегда пожалуйста.",
            "Рад помочь, {name}."
        ]
        self.who_responses = [
            "Я tolikAi Private Engine — локальный приватный движок без интернета и доступа к файлам.",
            "Я приватный помощник tolikAi Private. Работаю без сети и без передачи данных наружу."
        ]
        self.capabilities_responses = [
            "Я умею отвечать на вопросы, помогать с Python, FastAPI, HTML, CSS и JavaScript, а ещё соблюдать приватность.",
            "Могу помогать с кодом, текстом, идеями и базовыми задачами."
        ]
        self.coding_responses = [
            "Да, могу помочь с Python, FastAPI, HTML, CSS, JavaScript и ошибками запуска.",
            "Могу разбирать код и объяснять, что исправить."
        ]
        self.private_denials = [
            "Извините, я не могу помогать с персональными данными других людей.",
            "Я не раскрываю и не передаю данные других людей."
        ]
        self.self_modify_denials = [
            "Я не могу менять свой код или сам себя переписывать.",
            "Самостоятельно менять себя мне запрещено."
        ]
        self.internet_denials = [
            "У меня нет доступа к интернету.",
            "Я работаю локально и не выхожу в сеть."
        ]
        self.device_denials = [
            "Я не управляю устройствами и не меняю файлы.",
            "Я не имею доступа к устройствам и файловой системе."
        ]
        self.fallback_responses = [
            "Я пока не уверен, что понял запрос. Можешь сформулировать его чуть точнее?",
            "Не до конца понял. Опиши задачу немного подробнее.",
            "Я могу помочь, но нужен более точный запрос."
        ]

    def format_name(self, raw_name: str) -> str:
        raw_name = raw_name.strip().strip(".,!?;:-")
        if not raw_name:
            return "друг"
        return raw_name[:1].upper() + raw_name[1:]

    def extract_name(self, text: str) -> str | None:
        norm = normalize(text)
        patterns = [
            r"(?:меня зовут|зови меня)\s+([a-zа-я\-]{2,30})",
            r"^я\s+([a-zа-я\-]{2,30})$",
        ]
        for pattern in patterns:
            m = re.search(pattern, norm, flags=re.IGNORECASE)
            if m:
                return self.format_name(m.group(1))
        return None

    def handle_time(self) -> str:
        now = datetime.now()
        return f"Сейчас {now.strftime('%H:%M')}."

    def handle_date(self) -> str:
        now = datetime.now()
        return f"Сегодня {now.strftime('%d.%m.%Y')}."

    def personalize(self, text: str, session: dict) -> str:
        name = session.get("name") or "друг"
        return text.format(name=name)

    def choose(self, options: list[str]) -> str:
        return random.choice(options)

    def respond(self, user_text: str, session: dict) -> str:
        raw = user_text.strip()
        norm = normalize(raw)

        if not raw:
            return "Пожалуйста, напишите сообщение."

        # Память имени
        extracted_name = self.extract_name(raw)
        if extracted_name:
            session["name"] = extracted_name
            return self.personalize(f"Приятно познакомиться, {extracted_name}.", session)

        # Запреты сначала
        if is_private_data_request(raw):
            return self.choose(self.private_denials)

        if is_self_modify_request(raw):
            return self.choose(self.self_modify_denials)

        if is_internet_request(raw):
            return self.choose(self.internet_denials)

        if is_device_request(raw) or is_file_request(raw):
            return self.choose(self.device_denials)

        # Интенты
        intent = match_intent(raw)

        if intent == "greet":
            return self.personalize(self.choose(self.greet_responses), session)

        if intent == "bye":
            return self.personalize(self.choose(self.bye_responses), session)

        if intent == "thanks":
            return self.personalize(self.choose(self.thanks_responses), session)

        if intent == "who_are_you":
            return self.choose(self.who_responses)

        if intent == "capabilities":
            return self.choose(self.capabilities_responses)

        if intent == "coding_help":
            return self.choose(self.coding_responses)

        if intent == "time":
            return self.handle_time()

        if intent == "date":
            return self.handle_date()

        # Дополнительные правила для обычных вопросов
        if "помоги" in norm or "помощь" in norm:
            name = session.get("name")
            if name:
                return f"{name}, опиши задачу чуть точнее — и я помогу."
            return "Опиши задачу чуть точнее — и я помогу."

        if "что делать" in norm or "как быть" in norm:
            return "Опиши проблему подробнее, и я подскажу следующий шаг."

        if "объясни" in norm or "почему" in norm or "как" in norm:
            return "Я могу объяснить это простыми словами, но мне нужна более конкретная формулировка."

        # Fallback без повтора текста пользователя
        return self.choose(self.fallback_responses)


engine = TolikAiEngine()


# ============================================================
# HTML
# ============================================================

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>tolikAi Private Engine</title>
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
            min-width: 240px;
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
        <h1>tolikAi Private Engine <span class="badge">локальный движок</span></h1>
        <div class="small">
            Без интернета. Без доступа к файлам. Без повторения вашего текста.
        </div>

        <div id="chat"></div>

        <div class="row">
            <input id="message" type="text" placeholder="Напишите сообщение..." />
            <button onclick="sendMessage()">Отправить</button>
            <button class="secondary" onclick="resetMemory()">Сбросить память</button>
        </div>

        <div class="hint">
            Подсказка: нажмите Enter, чтобы отправить сообщение.
        </div>
    </div>

    <script>
        const chat = document.getElementById("chat");
        const input = document.getElementById("message");

        function getSessionId() {
            let sid = localStorage.getItem("tolikai_session_id");
            if (!sid) {
                if (window.crypto && crypto.randomUUID) {
                    sid = crypto.randomUUID();
                } else {
                    sid = "sid_" + Math.random().toString(36).slice(2) + "_" + Date.now().toString(36);
                }
                localStorage.setItem("tolikai_session_id", sid);
            }
            return sid;
        }

        const sessionId = getSessionId();

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
                    body: JSON.stringify({
                        message: text,
                        session_id: sessionId
                    })
                });

                const data = await response.json();
                addMessage("bot", data.answer || "Пустой ответ от сервера.");
            } catch (error) {
                addMessage("bot", "Ошибка соединения с сервером.");
            }
        }

        async function resetMemory() {
            try {
                const response = await fetch("/api/reset", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        session_id: sessionId
                    })
                });

                const data = await response.json();
                chat.innerHTML = "";
                addMessage("bot", data.answer || "Память очищена.");
            } catch (error) {
                addMessage("bot", "Не удалось сбросить память.");
            }
        }

        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                sendMessage();
            }
        });

        addMessage("bot", "Здравствуйте. Я tolikAi Private Engine. Напишите сообщение.");
    </script>
</body>
</html>
"""


# ============================================================
# РОУТЫ
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_PAGE


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.post("/api/chat")
async def chat(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}

    session_id = str(data.get("session_id", "default"))
    user_text = str(data.get("message", ""))

    session = get_session(session_id)
    answer = engine.respond(user_text, session)

    session["history"].append({
        "user": user_text,
        "assistant": answer
    })

    if len(session["history"]) > 20:
        session["history"] = session["history"][-20:]

    return JSONResponse({
        "answer": answer,
        "name": session.get("name")
    })


@app.post("/api/reset")
async def api_reset(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}

    session_id = str(data.get("session_id", "default"))
    reset_session(session_id)

    return JSONResponse({
        "answer": "Память очищена. Я снова готов помочь."
    })