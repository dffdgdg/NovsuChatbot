# NovSU ChatBot

Telegram-бот для ответов на вопросы студентов НовГУ. Использует нейросетевой поиск по базе знаний.

## Что умеет

- Отвечает на вопросы по базе знаний
- Пересылает сложные вопросы администраторам
- Собирает обратную связь от пользователей
- Ведёт статистику

## Установка

```bash
git clone https://github.com/yourusername/novgu-helper-bot.git
cd novgu-helper-bot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Настройка

Создайте файл `.env`:

```env
BOT_TOKEN=токен_от_botfather
ADMIN_IDS=123456789,987654321
```

## Запуск

```bash
python main.py
```

## Структура проекта

```
main.py              — запуск бота
bot_handlers.py      — обработка сообщений
neural_searcher.py   — поиск по базе знаний
config.py            — настройки и база знаний
user_manager.py      — данные пользователей
feedback_manager.py  — обратная связь
session_manager.py   — история диалогов
utils.py             — вспомогательные функции
```

## База знаний

Редактируется в `config.py`:

```python
KNOWLEDGE_BASE = [
    {
        "question": "Где деканат?",
        "answer": "Главный корпус, каб. 305",
        "category": "Навигация",
        "keywords": ["деканат"],
        "variations": ["как найти деканат", "где находится деканат"]
    },
]
```

## Админ-команды

`/admin` — панель администратора (статистика, неотвеченные вопросы, ответы пользователям)

## Зависимости

- python-telegram-bot
- sentence-transformers
- faiss-cpu
- torch
- rapidfuzz
- python-dotenv
