import re


def clean_text(text: str) -> str:
    """Очистка текста: приведение к нижнему регистру, удаление лишних символов"""
    if not text:
        return ""

    text = text.lower()
    # Оставляем буквы (включая кириллицу), цифры и пробелы
    text = re.sub(r'[^\w\s\d]', ' ', text)
    # Убираем множественные пробелы
    text = re.sub(r'\s+', ' ', text).strip()

    return text