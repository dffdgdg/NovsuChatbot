"""
Утилита для анализа неизвестных вопросов.
Помогает выявить частые вопросы для добавления в базу знаний.
"""
from collections import Counter
from user_manager import UserManager


def analyze_unknown_questions():
    """Выводит статистику и список неизвестных вопросов."""
    user_manager = UserManager()

    stats = user_manager.get_unknown_questions_stats()
    unknown_questions = user_manager.get_unknown_questions()

    print("=" * 50)
    print("АНАЛИЗ НЕИЗВЕСТНЫХ ВОПРОСОВ")
    print("=" * 50)

    print(f"Всего вопросов: {stats['total_unknown_questions']}")
    print(f"Уникальных вопросов: {stats['unique_questions']}")
    print(f"Уникальных пользователей: {stats['unique_users_asked']}")
    print()

    if unknown_questions:
        question_counts = Counter([q['question'] for q in unknown_questions])

        print("Самые частые неизвестные вопросы:")
        for question, count in question_counts.most_common(10):
            print(f"  {count}x: {question}")

        print("\nВсе уникальные вопросы (для добавления в базу знаний):")
        unique_questions = set(q['question'] for q in unknown_questions)
        for i, question in enumerate(unique_questions, 1):
            print(f"{i}. {question}")
    else:
        print("Нет неизвестных вопросов")


if __name__ == "__main__":
    analyze_unknown_questions()