"""
Менеджер обратной связи.
Сохраняет и анализирует оценки пользователей.
"""

import json
import os
from datetime import datetime
from typing import Dict, List


class FeedbackManager:
    """Управление обратной связью по ответам."""

    def __init__(self, filepath: str = "feedback.json"):
        self.filepath = filepath
        self.feedback: List[Dict] = []
        self._load()

    def _load(self):
        """Загружает данные из файла."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.feedback = json.load(f)
            except Exception:
                self.feedback = []

    def _save(self):
        """Сохраняет данные в файл."""
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.feedback, f, ensure_ascii=False, indent=2)

    def add_feedback(self, user_id: int, question: str, answer: str,
                     is_helpful: bool, comment: str = None):
        """Добавляет отзыв пользователя."""
        self.feedback.append({
            'user_id': user_id,
            'question': question,
            'answer': answer[:200],
            'is_helpful': is_helpful,
            'comment': comment,
            'timestamp': datetime.now().isoformat()
        })
        self._save()

    def get_stats(self) -> Dict:
        """Возвращает статистику по отзывам."""
        if not self.feedback:
            return {'total': 0, 'positive': 0, 'negative': 0, 'rate': 0}

        positive = sum(1 for f in self.feedback if f['is_helpful'])
        total = len(self.feedback)

        return {
            'total': total,
            'positive': positive,
            'negative': total - positive,
            'rate': round(positive / total * 100, 1) if total > 0 else 0
        }

    def get_negative_feedback(self, limit: int = 20) -> List[Dict]:
        """Возвращает негативные отзывы для анализа."""
        negative = [f for f in self.feedback if not f['is_helpful']]
        return negative[-limit:]