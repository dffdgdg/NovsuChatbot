"""
Менеджер пользователей и неизвестных вопросов.
Сохраняет данные в JSON-файлы.
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional, List


class UserManager:
    """Управление данными пользователей и неизвестными вопросами."""

    def __init__(self, filepath: str = "users.json",
                 unknown_questions_file: str = "unknown_questions.json"):
        self.filepath = filepath
        self.unknown_questions_file = unknown_questions_file
        self.users: Dict[int, Dict] = {}
        self.unknown_questions: List[Dict] = []
        self._load()
        self._load_unknown_questions()

    def _load(self):
        """Загружает данные пользователей."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.users = {int(k): v for k, v in json.load(f).items()}
            except Exception as e:
                print(f"Ошибка загрузки users: {e}")
                self.users = {}

    def _load_unknown_questions(self):
        """Загружает неизвестные вопросы."""
        if os.path.exists(self.unknown_questions_file):
            try:
                with open(self.unknown_questions_file, 'r', encoding='utf-8') as f:
                    self.unknown_questions = json.load(f)
            except Exception as e:
                print(f"Ошибка загрузки unknown_questions: {e}")
                self.unknown_questions = []

    def _save(self):
        """Сохраняет данные пользователей."""
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения users: {e}")

    def _save_unknown_questions(self):
        """Сохраняет неизвестные вопросы."""
        try:
            with open(self.unknown_questions_file, 'w', encoding='utf-8') as f:
                json.dump(self.unknown_questions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения unknown_questions: {e}")

    def get_user(self, user_id: int) -> Dict:
        """Получает или создаёт данные пользователя."""
        if user_id not in self.users:
            self.users[user_id] = {
                "group": None,
                "history": [],
                "first_seen": datetime.now().isoformat(),
                "unknown_questions": []
            }
            self._save()
        return self.users[user_id]

    def set_group(self, user_id: int, group: str):
        """Устанавливает группу пользователя."""
        self.get_user(user_id)["group"] = group
        self._save()

    def get_group(self, user_id: int) -> Optional[str]:
        """Возвращает группу пользователя."""
        return self.get_user(user_id).get("group")

    def add_unknown_question(self, user_id: int, question: str, user_info: Dict = None):
        """Добавляет неизвестный вопрос в лог."""
        unknown_question = {
            "question": question,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "user_info": user_info or {}
        }

        self.unknown_questions.append(unknown_question)
        self._save_unknown_questions()

        # Сохраняем также в историю пользователя
        user_data = self.get_user(user_id)
        if "unknown_questions" not in user_data:
            user_data["unknown_questions"] = []
        user_data["unknown_questions"].append({
            "question": question,
            "timestamp": unknown_question["timestamp"]
        })
        self._save()

    def get_unknown_questions(self, limit: int = None) -> List[Dict]:
        """Возвращает список неизвестных вопросов."""
        if limit:
            return self.unknown_questions[-limit:]
        return self.unknown_questions

    def get_user_unknown_questions(self, user_id: int) -> List[Dict]:
        """Возвращает неизвестные вопросы конкретного пользователя."""
        return self.get_user(user_id).get("unknown_questions", [])

    def get_unknown_questions_stats(self) -> Dict:
        """Возвращает статистику по неизвестным вопросам."""
        total = len(self.unknown_questions)
        unique_questions = len(set(q['question'] for q in self.unknown_questions)) if self.unknown_questions else 0
        users_asked = len(set(q['user_id'] for q in self.unknown_questions)) if self.unknown_questions else 0

        return {
            "total_unknown_questions": total,
            "unique_questions": unique_questions,
            "unique_users_asked": users_asked
        }

    def clear_unknown_questions(self):
        """Очищает список неизвестных вопросов."""
        self.unknown_questions = []
        self._save_unknown_questions()