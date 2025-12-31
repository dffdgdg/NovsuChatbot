"""
Менеджер сессий для хранения истории диалогов.
"""

from typing import List, Dict


class SessionManager:
    """Хранит историю сообщений пользователей."""

    def __init__(self, max_history: int = 10):
        self.sessions: Dict[int, List[Dict]] = {}
        self.max_history = max_history

    def add_message(self, user_id: int, text: str, is_user: bool = True):
        """Добавляет сообщение в историю пользователя."""
        if user_id not in self.sessions:
            self.sessions[user_id] = []

        self.sessions[user_id].append({"text": text, "is_user": is_user})
        self.sessions[user_id] = self.sessions[user_id][-self.max_history:]

    def get_history(self, user_id: int) -> List[Dict]:
        """Возвращает историю сообщений пользователя."""
        return self.sessions.get(user_id, [])

    def clear_history(self, user_id: int):
        """Очищает историю пользователя."""
        if user_id in self.sessions:
            self.sessions[user_id] = []