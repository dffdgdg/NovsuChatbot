"""
Вспомогательные функции.
"""

import re

def clean_text(text: str) -> str:
    """
    Очищает текст для поиска.

    - Приводит к нижнему регистру
    - Удаляет знаки препинания
    - Убирает множественные пробелы
    """
    if not text:
        return ""

    text = text.lower()
    text = re.sub(r'[^\w\s\d]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    return text