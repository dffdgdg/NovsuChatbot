import torch
import faiss
from sentence_transformers import SentenceTransformer
import logging
from typing import List, Dict, Optional, Set
from rapidfuzz import fuzz, process
from utils import clean_text

logger = logging.getLogger(__name__)


class NeuralSearcher:
    """Нейросетевой поиск по базе знаний"""

    # Стоп-слова (УБРАЛ "привет" - это ключевое слово в базе!)
    STOP_WORDS: Set[str] = {
        'как', 'что', 'где', 'когда', 'почему', 'зачем', 'какой', 'какая', 'какое', 'какие',
        'кто', 'чей', 'чья', 'чьё', 'чьи', 'сколько', 'который', 'которая', 'которое',
        'это', 'этот', 'эта', 'эти', 'тот', 'та', 'то', 'те',
        'мой', 'моя', 'моё', 'мои', 'твой', 'твоя', 'твоё', 'твои',
        'наш', 'наша', 'наше', 'наши', 'ваш', 'ваша', 'ваше', 'ваши',
        'его', 'её', 'их', 'свой', 'своя', 'своё', 'свои',
        'весь', 'вся', 'всё', 'все', 'сам', 'сама', 'само', 'сами',
        'быть', 'есть', 'был', 'была', 'было', 'были', 'будет', 'будут',
        'можно', 'нужно', 'надо', 'нельзя', 'должен', 'хочу', 'хочет', 'могу', 'может',
        'для', 'без', 'при', 'про', 'под', 'над', 'перед', 'после', 'между',
        'очень', 'уже', 'ещё', 'еще', 'тоже', 'также', 'только', 'даже', 'именно',
        'или', 'либо', 'однако', 'поэтому', 'потому', 'если', 'чтобы',
        'меня', 'тебя', 'себя', 'нас', 'вас', 'них', 'ним', 'ней',
        'мне', 'тебе', 'себе', 'нам', 'вам', 'ему', 'ей', 'им',
        'бы', 'же', 'ли', 'не', 'ни', 'да', 'нет',
        'вот', 'вон', 'там', 'тут', 'здесь', 'туда', 'сюда', 'откуда', 'куда',
        'так', 'такой', 'такая', 'такое', 'такие', 'столько',
        'ну', 'ага', 'угу', 'ладно', 'хорошо', 'плохо', 'нормально',
        'пока', 'спасибо', 'пожалуйста',
    }

    def __init__(self, knowledge_base: List[Dict]):
        self.knowledge_base = knowledge_base
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Устройство для нейросети: {self.device}")

        logger.info("Загрузка модели SentenceTransformer...")
        self.model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        self.model.to(self.device)

        self._prepare_search_index()
        self._build_keyword_index()

    def _prepare_search_index(self):
        """Подготавливает индекс для поиска"""
        self.all_questions = []
        self.question_to_answer = {}
        self.hardcoded_keywords_map: Dict[str, Dict] = {}

        for item in self.knowledge_base:
            clean_q = clean_text(item['question'])
            if clean_q:
                self._add_to_index(clean_q, item)

            for variation in item.get('variations', []):
                clean_v = clean_text(variation)
                if clean_v:
                    self._add_to_index(clean_v, item)

            for keyword in item.get('keywords', []):
                cleaned_keyword = clean_text(keyword)
                if cleaned_keyword:
                    self.hardcoded_keywords_map[cleaned_keyword] = item

        if not self.all_questions:
            logger.error("⚠️ База знаний пуста!")
            self.index = None
            return

        logger.info("Создание FAISS индекса...")
        embeddings = self.model.encode(
            self.all_questions,
            convert_to_tensor=True,
            show_progress_bar=False
        ).cpu().numpy()

        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)
        logger.info(f"Индекс готов: {len(self.all_questions)} фраз")

    def _build_keyword_index(self):
        """Строит индекс значимых слов из базы знаний"""
        self.significant_words: Set[str] = set()

        for item in self.knowledge_base:
            # Добавляем ключевые слова
            for kw in item.get('keywords', []):
                word = clean_text(kw)
                if word and len(word) > 2:
                    self.significant_words.add(word)

            # Добавляем значимые слова из вариаций
            for var in item.get('variations', []):
                for word in clean_text(var).split():
                    if word not in self.STOP_WORDS and len(word) > 3:
                        self.significant_words.add(word)

            # Добавляем слова из вопроса
            for word in clean_text(item['question']).split():
                if word not in self.STOP_WORDS and len(word) > 3:
                    self.significant_words.add(word)

        logger.info(f"Индекс значимых слов: {len(self.significant_words)} слов")

    def _add_to_index(self, text: str, item: Dict):
        """Добавляет текст в индекс"""
        if text and text not in self.all_questions:
            self.all_questions.append(text)
            self.question_to_answer[text] = item

    def _get_significant_words(self, text: str) -> Set[str]:
        """Извлекает значимые слова из текста (без стоп-слов)"""
        words = set(clean_text(text).split())
        return {w for w in words if w not in self.STOP_WORDS and len(w) > 2}

    def _has_relevant_words(self, query: str) -> bool:
        """Проверяет, содержит ли запрос релевантные слова из базы знаний"""
        query_words = self._get_significant_words(query)

        if not query_words:
            # Проверяем также ключевые слова напрямую
            clean_q = clean_text(query)
            if clean_q in self.hardcoded_keywords_map:
                return True
            return False

        for word in query_words:
            # Точное совпадение
            if word in self.significant_words:
                return True

            # Проверяем начало слова (для разных форм)
            if len(word) > 4:
                word_stem = word[:5]
                for sig_word in self.significant_words:
                    if len(sig_word) > 4 and sig_word.startswith(word_stem):
                        return True

        return False

    def _calculate_word_overlap(self, query: str, matched_text: str) -> float:
        """Вычисляет совпадение значимых слов"""
        query_words = self._get_significant_words(query)
        matched_words = self._get_significant_words(matched_text)

        if not query_words:
            return 0.0

        overlap_count = 0

        for qw in query_words:
            if qw in matched_words:
                overlap_count += 1
                continue

            if len(qw) > 4:
                qw_stem = qw[:5]
                for mw in matched_words:
                    if len(mw) > 4 and mw.startswith(qw_stem):
                        overlap_count += 0.7
                        break

        return overlap_count / len(query_words)

    def search(self, query: str, top_k: int = 5, threshold: float = 0.55) -> List[Dict]:
        """Поиск по базе знаний"""
        if not query or self.index is None:
            return []

        clean_query = clean_text(query)

        if not clean_query or len(clean_query) < 2:
            return []

        # 1. Проверка точных ключевых слов (ПЕРВЫМ!)
        keyword_result = self._check_keywords(clean_query)
        if keyword_result:
            return [keyword_result]

        # 2. Проверяем наличие значимых слов
        significant_query_words = self._get_significant_words(query)
        has_relevant = self._has_relevant_words(query)

        logger.debug(f"Query: '{query}' | Significant: {significant_query_words} | Relevant: {has_relevant}")

        # Если нет значимых слов И нет релевантных - не ищем
        if not significant_query_words and not has_relevant:
            logger.info(f"Query '{query}' - no significant/relevant words")
            return []

        if not has_relevant:
            logger.info(f"Query '{query}' - no relevant words from KB")
            return []

        # 3. Нейросетевой поиск
        neural_results = self._neural_search(clean_query, top_k, threshold)

        if neural_results:
            return neural_results

        # 4. Fuzzy поиск
        fuzzy_results = self._fuzzy_search(clean_query, top_k)

        return fuzzy_results

    def _check_keywords(self, clean_query: str) -> Optional[Dict]:
        """Проверяет точные ключевые слова"""
        for keyword, kb_item in self.hardcoded_keywords_map.items():
            # Точное совпадение
            if clean_query == keyword:
                return {
                    'question': kb_item['question'],
                    'answer': kb_item['answer'],
                    'score': 1.0,
                    'match_type': 'keyword_exact'
                }

            # Очень похоже (> 92%)
            ratio = fuzz.ratio(clean_query, keyword)
            if ratio > 92:
                return {
                    'question': kb_item['question'],
                    'answer': kb_item['answer'],
                    'score': 0.98,
                    'match_type': 'keyword_fuzzy'
                }

            # Запрос содержит ключевое слово
            if len(keyword) > 5 and keyword in clean_query:
                return {
                    'question': kb_item['question'],
                    'answer': kb_item['answer'],
                    'score': 0.95,
                    'match_type': 'keyword_contains'
                }

            # Ключевое слово содержит запрос (для коротких запросов типа "привет")
            if len(clean_query) > 3 and clean_query in keyword:
                return {
                    'question': kb_item['question'],
                    'answer': kb_item['answer'],
                    'score': 0.90,
                    'match_type': 'query_in_keyword'
                }

        return None

    def _neural_search(self, clean_query: str, top_k: int, threshold: float) -> List[Dict]:
        """Нейросетевой поиск с валидацией"""
        query_emb = self.model.encode([clean_query], convert_to_tensor=True).cpu().numpy()
        faiss.normalize_L2(query_emb)

        scores, indices = self.index.search(query_emb, top_k * 3)

        results = []
        seen_answers = set()

        for i in range(len(scores[0])):
            raw_score = float(scores[0][i])

            if raw_score < threshold:
                continue

            idx = indices[0][i]
            matched_text = self.all_questions[idx]
            item = self.question_to_answer[matched_text]

            # Проверяем совпадение слов
            word_overlap = self._calculate_word_overlap(clean_query, matched_text)

            # Фильтрация: если нет совпадения слов - пропускаем
            if word_overlap < 0.3:
                logger.debug(f"Skip '{matched_text}' - overlap {word_overlap:.2f}")
                continue

            # Корректируем score
            adjusted_score = raw_score * 0.6 + word_overlap * 0.4

            if adjusted_score < threshold:
                continue

            # Дубликаты
            answer_key = item['answer'][:100]
            if answer_key in seen_answers:
                continue
            seen_answers.add(answer_key)

            results.append({
                'question': item['question'],
                'answer': item['answer'],
                'score': adjusted_score,
                'raw_score': raw_score,
                'match_type': 'neural',
                'matched_variation': matched_text,
                'word_overlap': word_overlap
            })

            if len(results) >= top_k:
                break

        results.sort(key=lambda x: x['score'], reverse=True)

        return results

    def _fuzzy_search(self, clean_query: str, top_k: int) -> List[Dict]:
        """Fuzzy поиск"""
        results = []
        seen_answers = set()

        matches = process.extract(
            clean_query,
            self.all_questions,
            scorer=fuzz.token_set_ratio,
            limit=top_k * 2
        )

        for match_text, match_score, _ in matches:
            if match_score < 70:
                continue

            word_overlap = self._calculate_word_overlap(clean_query, match_text)
            if word_overlap < 0.3:
                continue

            item = self.question_to_answer[match_text]

            answer_key = item['answer'][:100]
            if answer_key in seen_answers:
                continue
            seen_answers.add(answer_key)

            results.append({
                'question': item['question'],
                'answer': item['answer'],
                'score': match_score / 100.0,
                'match_type': 'fuzzy',
                'matched_variation': match_text,
                'word_overlap': word_overlap
            })

            if len(results) >= top_k:
                break

        return results

    def debug_search(self, query: str) -> None:
        """Отладка поиска"""
        clean_q = clean_text(query)
        sig_words = self._get_significant_words(query)
        has_rel = self._has_relevant_words(query)

        print(f"\n{'=' * 60}")
        print(f"Запрос: {query}")
        print(f"Очищенный: {clean_q}")
        print(f"Значимые слова: {sig_words}")
        print(f"Есть релевантные: {has_rel}")
        print(f"{'=' * 60}")

        results = self.search(query, top_k=5)

        if not results:
            print("❌ Ничего не найдено")
        else:
            for i, r in enumerate(results, 1):
                raw = r.get('raw_score')
                overlap = r.get('word_overlap')

                raw_str = f"{raw:.3f}" if isinstance(raw, float) else "N/A"
                overlap_str = f"{overlap:.2f}" if isinstance(overlap, float) else "N/A"

                print(f"\n{i}. Score: {r['score']:.3f} | Raw: {raw_str} | Overlap: {overlap_str}")
                print(f"   Type: {r['match_type']}")
                print(f"   Question: {r['question']}")
                print(f"   Matched: {r.get('matched_variation', 'N/A')}")


# Тестирование
if __name__ == "__main__":
    from config import KNOWLEDGE_BASE

    searcher = NeuralSearcher(KNOWLEDGE_BASE)

    test_queries = [
        "привет",  # ✅ Должен найти (keyword)
        "здравствуйте",  # ✅ Должен найти (keyword)
        "как какать",  # ❌ Мусор
        "что такое любовь",  # ❌ Мусор
        "абракадабра",  # ❌ Мусор
        "фывапролдж",  # ❌ Мусор
        "где расписание",  # ✅ Должен найти
        "расписание пар",  # ✅ Должен найти
        "потерял пропуск",  # ✅ Должен найти
        "стипендия",  # ✅ Должен найти
        "военная кафедра",  # ✅ Должен найти
        "как получить матпомощь",  # ✅ Должен найти
    ]

    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ПОИСКА")
    print("=" * 60)

    for q in test_queries:
        searcher.debug_search(q)