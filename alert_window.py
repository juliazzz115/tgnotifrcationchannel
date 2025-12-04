"""
Модуль для создания модального окна уведомления
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AlertWindow:
    """Класс для создания немодального окна уведомления с обязательным подтверждением"""

    def __init__(self, message_text: str, channel_name: str = ""):
        """
        Инициализация окна уведомления

        Args:
            message_text: Текст сообщения для отображения
            channel_name: Название канала (опционально)
        """
        self.message_text = message_text
        self.channel_name = channel_name
        self.confirmed = False
        self.user_name = ""

        # Создаем главное окно
        self.root = tk.Tk()
        self.root.title("⚠️ НОВОЕ СООБЩЕНИЕ ИЗ TELEGRAM")

        # Делаем окно очень большим и заметным
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Окно занимает 80% экрана по центру
        window_width = int(screen_width * 0.8)
        window_height = int(screen_height * 0.8)
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Настройки окна - всегда поверх всех окон
        self.root.attributes('-topmost', True)
        self.root.lift()
        self.root.focus_force()

        # Блокируем закрытие окна стандартным способом
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_attempt)

        # Устанавливаем красный фон для привлечения внимания
        self.root.configure(bg='#ff4444')

        self._create_widgets()

        # Устанавливаем фокус на поле ввода имени
        self.root.after(100, lambda: self.name_entry.focus_set())

    def _create_widgets(self):
        """Создание виджетов интерфейса"""
        # Основной контейнер с отступами
        main_frame = tk.Frame(self.root, bg='#ff4444', padx=30, pady=30)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Заголовок с предупреждением
        header_frame = tk.Frame(main_frame, bg='#ff4444')
        header_frame.pack(fill=tk.X, pady=(0, 20))

        warning_label = tk.Label(
            header_frame,
            text="⚠️ ВНИМАНИЕ! НОВОЕ СООБЩЕНИЕ ⚠️",
            font=('Arial', 32, 'bold'),
            bg='#ff4444',
            fg='white'
        )
        warning_label.pack()

        # Время получения
        time_label = tk.Label(
            header_frame,
            text=f"Получено: {datetime.now().strftime('%H:%M:%S')}",
            font=('Arial', 16),
            bg='#ff4444',
            fg='white'
        )
        time_label.pack(pady=(10, 0))

        if self.channel_name:
            channel_label = tk.Label(
                header_frame,
                text=f"Канал: {self.channel_name}",
                font=('Arial', 14),
                bg='#ff4444',
                fg='white'
            )
            channel_label.pack(pady=(5, 0))

        # Рамка для содержимого сообщения
        content_frame = tk.Frame(main_frame, bg='white', relief=tk.RAISED, borderwidth=3)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=20)

        # Метка "Содержимое сообщения"
        content_label = tk.Label(
            content_frame,
            text="Содержимое сообщения:",
            font=('Arial', 16, 'bold'),
            bg='white',
            anchor='w'
        )
        content_label.pack(fill=tk.X, padx=20, pady=(20, 10))

        # Текстовое поле с прокруткой для сообщения
        text_widget = scrolledtext.ScrolledText(
            content_frame,
            font=('Arial', 14),
            wrap=tk.WORD,
            height=15,
            relief=tk.SUNKEN,
            borderwidth=2
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        text_widget.insert('1.0', self.message_text)
        text_widget.config(state=tk.DISABLED)  # Только для чтения

        # Рамка для подтверждения
        confirm_frame = tk.Frame(main_frame, bg='white', relief=tk.RAISED, borderwidth=3)
        confirm_frame.pack(fill=tk.X, pady=(0, 20))

        # Внутренний контейнер для отступов
        confirm_inner = tk.Frame(confirm_frame, bg='white', padx=20, pady=20)
        confirm_inner.pack(fill=tk.X)

        # Инструкция
        instruction_label = tk.Label(
            confirm_inner,
            text="Для закрытия этого окна необходимо:",
            font=('Arial', 16, 'bold'),
            bg='white',
            fg='#ff4444',
            anchor='w'
        )
        instruction_label.pack(fill=tk.X, pady=(0, 15))

        # Поле ввода имени
        name_frame = tk.Frame(confirm_inner, bg='white')
        name_frame.pack(fill=tk.X, pady=10)

        name_label = tk.Label(
            name_frame,
            text="1. Введите ваше имя:",
            font=('Arial', 14),
            bg='white',
            anchor='w'
        )
        name_label.pack(anchor='w', pady=(0, 5))

        self.name_entry = tk.Entry(
            name_frame,
            font=('Arial', 14),
            width=40,
            relief=tk.SOLID,
            borderwidth=2
        )
        self.name_entry.pack(anchor='w', ipady=5)
        self.name_entry.bind('<Return>', lambda e: self._confirm())

        # Чекбокс подтверждения
        checkbox_frame = tk.Frame(confirm_inner, bg='white')
        checkbox_frame.pack(fill=tk.X, pady=10)

        checkbox_label = tk.Label(
            checkbox_frame,
            text="2. Подтвердите, что проверили сообщения:",
            font=('Arial', 14),
            bg='white',
            anchor='w'
        )
        checkbox_label.pack(anchor='w', pady=(0, 5))

        self.confirmed_var = tk.BooleanVar()
        self.confirm_checkbox = tk.Checkbutton(
            checkbox_frame,
            text="Я проверил(а) все сообщения и принял(а) меры",
            font=('Arial', 13),
            bg='white',
            variable=self.confirmed_var,
            activebackground='white'
        )
        self.confirm_checkbox.pack(anchor='w')

        # Кнопка подтверждения
        button_frame = tk.Frame(confirm_inner, bg='white')
        button_frame.pack(fill=tk.X, pady=(20, 0))

        self.confirm_button = tk.Button(
            button_frame,
            text="✓ ПОДТВЕРДИТЬ И ЗАКРЫТЬ",
            font=('Arial', 16, 'bold'),
            bg='#44ff44',
            fg='black',
            activebackground='#33dd33',
            command=self._confirm,
            relief=tk.RAISED,
            borderwidth=3,
            padx=30,
            pady=15,
            cursor='hand2'
        )
        self.confirm_button.pack()

        # Сообщение об ошибке (скрыто по умолчанию)
        self.error_label = tk.Label(
            confirm_inner,
            text="",
            font=('Arial', 12, 'bold'),
            bg='white',
            fg='#ff0000'
        )
        self.error_label.pack(pady=(10, 0))

    def _on_close_attempt(self):
        """Обработчик попытки закрыть окно"""
        # Показываем сообщение об ошибке
        self.error_label.config(
            text="❌ Окно нельзя закрыть без подтверждения!"
        )
        # Мигаем окном для привлечения внимания
        self.root.bell()

    def _confirm(self):
        """Обработчик подтверждения"""
        name = self.name_entry.get().strip()
        confirmed = self.confirmed_var.get()

        # Проверяем, что все поля заполнены
        if not name:
            self.error_label.config(text="❌ Пожалуйста, введите ваше имя!")
            self.name_entry.focus_set()
            self.root.bell()
            return

        if not confirmed:
            self.error_label.config(text="❌ Пожалуйста, подтвердите проверку сообщений!")
            self.root.bell()
            return

        # Все проверки пройдены
        self.user_name = name
        self.confirmed = True

        logger.info(f"Уведомление подтверждено пользователем: {name}")

        # Закрываем окно
        self.root.quit()
        self.root.destroy()

    def show(self):
        """Показать окно и ждать подтверждения"""
        logger.info("Показываю окно уведомления")
        self.root.mainloop()
        return self.user_name, self.confirmed


def test_window():
    """Тестовая функция для проверки окна"""
    test_message = """📋 *Чаты без ответа MCG1 (сегодня):*

– KIRYL ILYENKOU (15:32)
  💬 понял, спасибо

– Yelyzaveta Bachiieva (15:02)
  💬 Будут скорее эти и еще какие-то ,я отпишу сегодня - завтра

– Volodymyr SMIRNOV JDG L (13:29)
  💬 Да, буду пробовать на следующей неделе!

– Polina VITARO SPÓŁKA (13:18)
  💬 Здравствуйте
К сожалению нет
В понедельник займусь и этим и договором

– Павел (13:09)
  💬 Уточните и я им отпишу 🙏

– Plepo SP O.O. Accounting (12:17)
  💬 .

– Ксенія (12:04)
  💬 Спасибо

– Liza (08:46)
  💬 [нет текста]"""

    window = AlertWindow(test_message, "Test Channel")
    user_name, confirmed = window.show()
    print(f"Пользователь: {user_name}, Подтверждено: {confirmed}")


if __name__ == "__main__":
    # Настройка логирования для теста
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    test_window()
