from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import KNOWLEDGE_BASE, ADMIN_IDS
from feedback_manager import FeedbackManager
from neural_searcher import NeuralSearcher
from session_manager import SessionManager
from user_manager import UserManager
import logging
import re
import hashlib

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self):
        self.searcher = NeuralSearcher(KNOWLEDGE_BASE)
        self.user_manager = UserManager()
        self.sessions = SessionManager()
        self.pending_confirmations = {}
        self.admin_pending_replies = {}
        self.feedback_manager = FeedbackManager()

        # ✅ ДОБАВЛЕНО: Хранилище для связки feedback с вопросом/ответом
        self.pending_feedback = {}  # {question_hash: {'question': ..., 'answer': ..., 'user_id': ...}}

        self._admin_ids = set()
        for admin_id in ADMIN_IDS:
            try:
                self._admin_ids.add(int(admin_id))
            except (ValueError, TypeError):
                logger.warning(f"Invalid admin ID: {admin_id}")

        logger.info(f"Initialized with admin IDs: {self._admin_ids}")

    def is_admin(self, user_id: int) -> bool:
        result = int(user_id) in self._admin_ids
        logger.debug(f"Admin check for {user_id}: {result}")
        return result

    def main_keyboard(self):
        kb = [
            [KeyboardButton("📚 Популярные вопросы"), KeyboardButton("🔍 Категории")],
            [KeyboardButton("🎓 Моя группа"), KeyboardButton("ℹ️ О боте")]
        ]
        return ReplyKeyboardMarkup(kb, resize_keyboard=True)

    def admin_keyboard(self):
        kb = [
            [KeyboardButton("📊 Статистика"), KeyboardButton("❓ Неизвестные вопросы")],
            [KeyboardButton("📈 Отзывы"), KeyboardButton("⬅️ Назад в меню")]  # ✅ Добавлена кнопка
        ]
        return ReplyKeyboardMarkup(kb, resize_keyboard=True)

    def admin_reply_keyboard(self):
        kb = [
            [KeyboardButton("❌ Отменить ответ")]
        ]
        return ReplyKeyboardMarkup(kb, resize_keyboard=True)

    def confirmation_keyboard(self, message_id: int):
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, это верно", callback_data=f"confirm:{message_id}"),
                InlineKeyboardButton("🔄 Нет, другой", callback_data=f"other:{message_id}")
            ],
            [
                InlineKeyboardButton("🚫 Нет ответа", callback_data=f"noanswer:{message_id}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    # ✅ ИСПРАВЛЕНО: Убран @staticmethod, добавлена логика сохранения контекста
    def feedback_keyboard(self, question_hash: str):
        """Клавиатура для оценки ответа"""
        keyboard = [
            [
                InlineKeyboardButton("👍 Полезно", callback_data=f"fb_yes:{question_hash}"),
                InlineKeyboardButton("👎 Не помогло", callback_data=f"fb_no:{question_hash}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    def _generate_feedback_hash(self, user_id: int, question: str) -> str:
        """Генерирует уникальный хэш для связки feedback"""
        data = f"{user_id}:{question}:{hash(question)}"
        return hashlib.md5(data.encode()).hexdigest()[:12]

    def _save_pending_feedback(self, user_id: int, question: str, answer: str) -> str:
        """Сохраняет контекст для последующего feedback"""
        question_hash = self._generate_feedback_hash(user_id, question)
        self.pending_feedback[question_hash] = {
            'user_id': user_id,
            'question': question,
            'answer': answer
        }

        # Очистка старых записей (храним максимум 1000)
        if len(self.pending_feedback) > 1000:
            oldest_keys = list(self.pending_feedback.keys())[:100]
            for key in oldest_keys:
                del self.pending_feedback[key]

        return question_hash

    def is_likely_real_question(self, text: str) -> bool:
        clean_text = re.sub(r'\s+', ' ', text.strip().lower())

        if len(clean_text) < 3:
            return False

        keyboard_patterns = ['qwerty', 'asdf', 'zxcv', 'йцукен', 'фыва', 'ячс', '1234']
        for pattern in keyboard_patterns:
            if pattern in clean_text:
                return False

        if len(set(clean_text.replace(' ', ''))) <= 2 and len(clean_text) > 5:
            return False

        return True

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        text = update.message.text
        user = update.message.from_user

        user_info = {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language_code": user.language_code
        }

        # ==================== АДМИН: РЕЖИМ ОТВЕТА ====================
        is_admin = self.is_admin(user_id)
        is_replying = user_id in self.admin_pending_replies

        logger.info(f"Message from {user_id}: is_admin={is_admin}, is_replying={is_replying}")

        if is_admin and is_replying:
            if text == "❌ Отменить ответ":
                del self.admin_pending_replies[user_id]
                await update.message.reply_text(
                    "✅ Режим ответа отменён",
                    reply_markup=self.admin_keyboard()
                )
                return

            await self._process_admin_reply(update, context, text)
            return

        # ==================== КОМАНДЫ МЕНЮ ====================
        if text == "/admin" and is_admin:
            await update.message.reply_text(
                "🔐 Режим администратора",
                reply_markup=self.admin_keyboard()
            )
            return

        if text == "📊 Статистика" and is_admin:
            stats = self.user_manager.get_unknown_questions_stats()
            fb_stats = self.feedback_manager.get_stats()  # ✅ Добавлена статистика feedback
            await update.message.reply_text(
                f"📊 *Статистика:*\n\n"
                f"*Вопросы:*\n"
                f"• Всего: {stats['total_unknown_questions']}\n"
                f"• Уникальных: {stats['unique_questions']}\n"
                f"• Пользователей: {stats['unique_users_asked']}\n\n"
                f"*Обратная связь:*\n"
                f"• Всего отзывов: {fb_stats['total']}\n"
                f"• 👍 Положительных: {fb_stats['positive']}\n"
                f"• 👎 Отрицательных: {fb_stats['negative']}\n"
                f"• Рейтинг: {fb_stats['rate']}%",
                parse_mode="Markdown"
            )
            return

        # ✅ ДОБАВЛЕНО: Просмотр отзывов
        if text == "📈 Отзывы" and is_admin:
            fb_stats = self.feedback_manager.get_stats()
            negative = self.feedback_manager.get_negative_feedback(limit=5)

            response = (
                f"📈 *Статистика отзывов:*\n\n"
                f"👍 Положительных: {fb_stats['positive']}\n"
                f"👎 Отрицательных: {fb_stats['negative']}\n"
                f"📊 Рейтинг: {fb_stats['rate']}%\n"
            )

            if negative:
                response += "\n*Последние негативные отзывы:*\n"
                for i, fb in enumerate(negative[-5:], 1):
                    q = fb.get('question', 'N/A')[:40]
                    response += f"\n{i}. _{q}_..."

            await update.message.reply_text(response, parse_mode="Markdown")
            return

        if text == "❓ Неизвестные вопросы" and is_admin:
            questions = self.user_manager.get_unknown_questions(limit=10)
            if questions:
                text_list = "\n".join([
                    f"• `{q['question'][:50]}` (ID: {q['user_id']})"
                    for q in reversed(questions[-10:])
                ])
                await update.message.reply_text(
                    f"❓ *Последние вопросы:*\n\n{text_list}",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("✅ Нет неизвестных вопросов")
            return

        if text == "⬅️ Назад в меню":
            await update.message.reply_text(
                "Главное меню",
                reply_markup=self.main_keyboard()
            )
            return

        if text == "📚 Популярные вопросы":
            questions = list(set([item['question'] for item in KNOWLEDGE_BASE]))[:5]
            popular = "\n🔹 ".join(questions)
            await update.message.reply_text(
                f"🔥 *Популярные вопросы:*\n\n🔹 {popular}",
                reply_markup=self.main_keyboard(),
                parse_mode="Markdown"
            )
            return

        if text == "🔍 Категории":
            categories = list({item['category'] for item in KNOWLEDGE_BASE})
            cat_text = "\n🔸 ".join(categories)
            await update.message.reply_text(
                f"📂 *Категории:*\n\n🔸 {cat_text}",
                reply_markup=self.main_keyboard(),
                parse_mode="Markdown"
            )
            return

        if text == "🎓 Моя группа":
            group = self.user_manager.get_group(user_id)
            if group:
                response = f"✅ Ваша группа: *{group}*"
            else:
                response = "🤷 Группа не указана.\nНапишите: *Группа 1234*"
            await update.message.reply_text(
                response,
                reply_markup=self.main_keyboard(),
                parse_mode="Markdown"
            )
            return

        if text == "ℹ️ О боте":
            await update.message.reply_text(
                "🤖 Я помощник НовГУ.\n\nПросто напишите вопрос!",
                reply_markup=self.main_keyboard()
            )
            return

        if text.lower().startswith("группа "):
            parts = text.split(maxsplit=1)
            if len(parts) >= 2:
                new_group = parts[1].strip()
                self.user_manager.set_group(user_id, new_group)
                await update.message.reply_text(
                    f"💾 Запомнил группу: *{new_group}*",
                    reply_markup=self.main_keyboard(),
                    parse_mode="Markdown"
                )
            return

        # ==================== ПОИСК ОТВЕТА ====================
        self.sessions.add_message(user_id, text, is_user=True)

        if not self.is_likely_real_question(text):
            await update.message.reply_text(
                "🤔 Не понял вопрос. Попробуйте переформулировать.\n\n"
                "💡 *Примеры:*\n• Где деканат?\n• Расписание пар\n• Как получить стипендию",
                reply_markup=self.main_keyboard(),
                parse_mode="Markdown"
            )
            return

        results = self.searcher.search(text, top_k=5)

        if not results:
            await self._forward_to_admin(context, user_id, text, user_info, results)
            await update.message.reply_text(
                "🤔 Не нашёл ответа. Вопрос отправлен администратору!",
                reply_markup=self.main_keyboard()
            )
            return

        best = results[0]
        score = best['score']

        logger.info(f"Query: '{text}' | Score: {score:.3f} | Match: '{best['question']}'")

        # ✅ ИЗМЕНЕНО: Добавлен feedback keyboard при высоком score
        if score > 0.80:
            # Сохраняем контекст для feedback
            fb_hash = self._save_pending_feedback(user_id, text, best['answer'])

            await update.message.reply_text(
                f"{best['answer']}\n\n"
                f"_Ответ был полезен?_",
                reply_markup=self.feedback_keyboard(fb_hash),
                parse_mode="Markdown"
            )
            return

        if score > 0.60:
            message_id = update.message.message_id
            self.pending_confirmations[user_id] = {
                message_id: {
                    'question': text,
                    'results': results,
                    'user_info': user_info
                }
            }

            await update.message.reply_text(
                f"🔍 *Возможно, вы спрашивали:*\n\n"
                f"❓ {best['question']}\n\n"
                f"💬 {best['answer']}\n\n"
                f"_Это правильный ответ?_",
                reply_markup=self.confirmation_keyboard(message_id),
                parse_mode="Markdown"
            )
            return

        await self._forward_to_admin(context, user_id, text, user_info, results)
        await update.message.reply_text(
            "🤔 Не уверен в ответе. Вопрос отправлен администратору!",
            reply_markup=self.main_keyboard()
        )

    # ✅ ДОБАВЛЕНО: Обработчик feedback callback
    async def handle_feedback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает оценку ответа пользователем"""
        query = update.callback_query
        user_id = query.from_user.id
        data = query.data

        await query.answer("Спасибо за отзыв! 🙏")

        if ':' not in data:
            logger.error(f"Invalid feedback callback data: {data}")
            return

        parts = data.split(':')
        action = parts[0]  # fb_yes или fb_no
        question_hash = parts[1] if len(parts) > 1 else None

        if not question_hash:
            logger.error(f"No question hash in feedback: {data}")
            return

        # Получаем сохранённый контекст
        feedback_data = self.pending_feedback.get(question_hash)

        if not feedback_data:
            # Контекст устарел, но всё равно благодарим
            await query.edit_message_text(
                query.message.text.replace("\n\n_Ответ был полезен?_", "") +
                "\n\n✅ Спасибо за отзыв!",
                parse_mode="Markdown"
            )
            return

        is_helpful = (action == "fb_yes")

        # Сохраняем feedback
        self.feedback_manager.add_feedback(
            user_id=feedback_data['user_id'],
            question=feedback_data['question'],
            answer=feedback_data['answer'],
            is_helpful=is_helpful
        )

        # Обновляем сообщение
        emoji = "👍" if is_helpful else "👎"
        original_text = query.message.text or ""

        # Убираем вопрос о полезности
        clean_text = original_text.replace("\n\n_Ответ был полезен?_", "")

        await query.edit_message_text(
            f"{clean_text}\n\n{emoji} Спасибо за отзыв!",
            parse_mode="Markdown"
        )

        # Удаляем из pending
        del self.pending_feedback[question_hash]

        logger.info(f"Feedback from {user_id}: helpful={is_helpful}, question='{feedback_data['question'][:50]}'")

    async def _process_admin_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Обрабатывает ответ администратора"""
        admin_id = update.message.from_user.id
        admin_data = self.admin_pending_replies.get(admin_id)

        logger.info(f"Processing admin reply from {admin_id}, data: {admin_data}")

        if not admin_data:
            await update.message.reply_text(
                "❌ Нет активного запроса на ответ",
                reply_markup=self.admin_keyboard()
            )
            return

        target_user_id = admin_data['user_id']
        original_question = admin_data.get('question', 'Неизвестный вопрос')

        del self.admin_pending_replies[admin_id]

        try:
            # ✅ ИЗМЕНЕНО: Добавляем feedback keyboard к ответу админа
            fb_hash = self._save_pending_feedback(target_user_id, original_question, text)

            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"💬 *Ответ от поддержки НовГУ:*\n\n"
                    f"❓ Ваш вопрос: _{original_question}_\n\n"
                    f"✉️ Ответ:\n{text}\n\n"
                    f"_Ответ был полезен?_"
                ),
                reply_markup=self.feedback_keyboard(fb_hash),
                parse_mode="Markdown"
            )

            await update.message.reply_text(
                f"✅ *Ответ отправлен!*\n\n"
                f"👤 Пользователь: `{target_user_id}`\n"
                f"❓ Вопрос: {original_question}\n"
                f"💬 Ваш ответ: {text[:100]}{'...' if len(text) > 100 else ''}",
                reply_markup=self.admin_keyboard(),
                parse_mode="Markdown"
            )

            logger.info(f"Admin {admin_id} replied to user {target_user_id}")

        except Exception as e:
            error_msg = str(e).lower()
            logger.error(f"Error sending reply to {target_user_id}: {e}")

            if "blocked" in error_msg:
                msg = "❌ Пользователь заблокировал бота"
            elif "not found" in error_msg:
                msg = "❌ Чат с пользователем не найден"
            else:
                msg = f"❌ Ошибка отправки: {e}"

            await update.message.reply_text(msg, reply_markup=self.admin_keyboard())

    async def handle_admin_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает нажатие кнопки 'Ответить'"""
        query = update.callback_query
        admin_id = query.from_user.id

        logger.info(f"handle_admin_reply called by {admin_id}")

        if not self.is_admin(admin_id):
            await query.answer("⛔ Нет доступа", show_alert=True)
            return

        await query.answer("Режим ответа активирован")

        data = query.data
        logger.info(f"Callback data: {data}")

        if not data.startswith("reply:"):
            return

        try:
            parts = data.split(':')
            target_user_id = int(parts[1])
        except (ValueError, IndexError) as e:
            logger.error(f"Cannot parse callback data '{data}': {e}")
            await query.edit_message_text("❌ Ошибка: неверный формат ID")
            return

        original_text = query.message.text or ""
        original_question = "Вопрос не найден"

        match = re.search(r'Вопрос:\s*(.+?)(?:\n|$)', original_text)
        if match:
            original_question = match.group(1).strip()

        self.admin_pending_replies[admin_id] = {
            'user_id': target_user_id,
            'question': original_question,
            'admin_message_id': query.message.message_id
        }

        logger.info(f"Saved pending reply: {self.admin_pending_replies[admin_id]}")

        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"📝 *Режим ответа пользователю* `{target_user_id}`\n"
                    f"Вопрос: _{original_question}_\n\n"
                    f"✍️ *Напишите ответ одним сообщением.*\n"
                    f"Для отмены нажмите кнопку ниже."
                ),
                reply_markup=self.admin_reply_keyboard(),
                parse_mode="Markdown"
            )

            await query.edit_message_text(
                f"{original_text}\n\n✅ *Вы отвечаете на этот вопрос*",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"UI update error: {e}")

    async def handle_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает кнопки подтверждения ответа"""
        query = update.callback_query
        user_id = query.from_user.id
        data = query.data

        await query.answer()

        if ':' not in data:
            logger.error(f"Invalid callback data format: {data}")
            return

        parts = data.split(':')
        action = parts[0]

        try:
            message_id = int(parts[1])
        except (ValueError, IndexError):
            logger.error(f"Cannot parse message_id from: {data}")
            return

        user_data = self.pending_confirmations.get(user_id, {}).get(message_id)

        if not user_data:
            await query.edit_message_text(
                "⏰ Время ожидания истекло. Задайте вопрос заново."
            )
            return

        question = user_data['question']
        results = user_data['results']
        user_info = user_data.get('user_info', {})

        if action == "confirm":
            best = results[0]

            # ✅ ИЗМЕНЕНО: Добавляем feedback после подтверждения
            fb_hash = self._save_pending_feedback(user_id, question, best['answer'])

            await query.edit_message_text(
                f"✅ *Ответ:*\n\n{best['answer']}\n\n"
                f"_Ответ был полезен?_",
                reply_markup=self.feedback_keyboard(fb_hash),
                parse_mode="Markdown"
            )

        elif action == "other":
            if len(results) > 1:
                other_text = "🔍 *Другие варианты:*\n\n"
                keyboard = []
                for i, r in enumerate(results[1:4], 1):
                    other_text += f"*{i}. {r['question']}*\n{r['answer'][:100]}...\n\n"
                    keyboard.append([InlineKeyboardButton(
                        f"✅ Вариант {i}",
                        callback_data=f"select:{message_id}:{i}"
                    )])

                keyboard.append([InlineKeyboardButton(
                    "🚫 Ни один не подходит",
                    callback_data=f"noanswer:{message_id}"
                )])

                await query.edit_message_text(
                    other_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            else:
                await self._forward_to_admin(context, user_id, question, user_info, results)
                await query.edit_message_text(
                    "🤔 Других вариантов нет. Вопрос отправлен администратору!"
                )

        elif action == "noanswer":
            await self._forward_to_admin(context, user_id, question, user_info, results)
            await query.edit_message_text(
                "✅ Вопрос отправлен администратору. Ожидайте ответа!"
            )

        elif action == "select":
            if len(parts) >= 3:
                try:
                    variant_idx = int(parts[2])
                    if 1 <= variant_idx < len(results):
                        selected = results[variant_idx]

                        # ✅ ИЗМЕНЕНО: Добавляем feedback после выбора варианта
                        fb_hash = self._save_pending_feedback(user_id, question, selected['answer'])

                        await query.edit_message_text(
                            f"✅ *Ответ:*\n\n{selected['answer']}\n\n"
                            f"_Ответ был полезен?_",
                            reply_markup=self.feedback_keyboard(fb_hash),
                            parse_mode="Markdown"
                        )
                except (ValueError, IndexError):
                    logger.error(f"Cannot parse variant from: {data}")

        if user_id in self.pending_confirmations:
            self.pending_confirmations[user_id].pop(message_id, None)

    async def _forward_to_admin(self, context: ContextTypes.DEFAULT_TYPE, user_id: int,
                                question: str, user_info: dict, results: list):
        """Пересылает вопрос администраторам"""
        logger.info(f"Forwarding question from user {user_id}: {question}")

        self.user_manager.add_unknown_question(user_id, question, user_info)

        username = user_info.get('username', 'нет')
        first_name = user_info.get('first_name', 'Unknown')

        admin_text = (
            f"❓ *Новый вопрос*\n\n"
            f"👤 {first_name} (@{username})\n"
            f"🆔 `{user_id}`\n\n"
            f"💬 Вопрос: {question}\n"
        )

        if results:
            admin_text += f"\n📋 Найденные варианты:\n"
            for i, r in enumerate(results[:3], 1):
                admin_text += f"{i}. {r['question']} ({r['score']:.0%})\n"

        callback_data = f"reply:{user_id}"

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📝 Ответить", callback_data=callback_data)
        ]])

        for admin_id in self._admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                logger.info(f"Forwarded question to admin {admin_id}")
            except Exception as e:
                logger.error(f"Error forwarding to admin {admin_id}: {e}")