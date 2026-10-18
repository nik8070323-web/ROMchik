# РОМчик

**Репозиторий Образовательных Материалов** — Telegram-бот для удобного доступа к учебным материалам. Он помогает студентам находить и скачивать лекции по ОИТ и МДК, учебник по иностранному языку, а также титульный лист и регламент для реферата прямо в Telegram.

Бот написан на Python с использованием aiogram 3. Команда `/start` открывает приветствие и меню, `/help` показывает список команд.

## Запуск

Из корневой папки репозитория:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp aiogram-learning/.env.example aiogram-learning/.env
```

В `aiogram-learning/.env` укажите токен своего бота, полученный у @BotFather:

```dotenv
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=
```

Для доступа к `/admin` укажите в `ADMIN_IDS` Telegram ID администраторов через запятую. Если список пуст, доступ закрыт для всех.

Запустите бота:

```bash
python aiogram-learning/main.py
```

Файл `.env`, виртуальные окружения, кеши Python и резервные копии исключены из Git через `.gitignore`. Не публикуйте настоящий токен бота.

Изображение приветствия находится в `images/welcome.png`, обработчики — в `aiogram-learning/handlers`, клавиатуры — в `aiogram-learning/keyboards`, учебные материалы — в `aiogram-learning/лекции`.
