# HANDOFF — Личный AI-секретарь (Telegram-бот), модуль «Командировки»

> Документ для переноса проекта в другой чат/сессию. Вставьте его целиком в новый чат —
> в нём есть цель, все принятые решения, архитектура, текущее состояние кода и следующие шаги.

---

## 0. Стартовый промпт для нового чата (вставьте это первым)

> Я продолжаю проект «Личный AI-секретарь (Telegram-бот)» для ген. директора. Ниже — полный
> handoff: цель, решения, архитектура, что уже сделано (Планы 1 и 2 завершены и в `main`) и план.
> Рабочая папка: `c:\Users\User\Desktop\AI-clerk` (git-репозиторий, ветка `main`, venv на Python 3.14
> в `.venv`). Спецификация: `docs/superpowers/specs/2026-06-15-ai-secretary-business-trips-design.md`.
> Планы: `docs/superpowers/plans/2026-06-15-phase1-foundation.md`,
> `docs/superpowers/plans/2026-06-15-phase2-profile-location.md`.
> Задача: составить и реализовать **План 3 (Оркестрация поездки + поиск)**. Используй те же навыки
> (brainstorming → writing-plans → subagent-driven-development) и тот же стиль (TDD, мелкие коммиты,
> ревью между задачами). Сначала прочитай спеку и код в `src/ai_clerk/`, затем предложи План 3.

---

## 1. Цель проекта

Telegram-бот — личный AI-секретарь директора. Первая способность — **организация командировок**.
Каркас сразу проектируется как «секретарь с набором способностей», чтобы позже добавлять календарь,
встречи, расходы без переписывания ядра.

Задачи модуля «Командировки»: понять свободные пожелания → определить точку отправления → найти
билеты (самолёт предпочтительнее, «быстрее = лучше») и отель → показать варианты → директор
подтверждает в один тап → бот сам завершает покупку/бронь → сформировать командировочный приказ
бухгалтеру → сохранить историю в папки-контейнеры с индексом.

## 2. Журнал принятых решений (это и есть «мысли о плане»)

| Тема | Решение |
|---|---|
| Оплата | Бот показывает несколько вариантов → директор подтверждает один в **один тап** → бот сам завершает покупку |
| Механизм покупки | **LLM браузер-агент (computer-use, предположительно OpenClaw)** заходит на сайты OTA под логином владельца и проходит все шаги |
| Платёжные данные | **Карта привязана в аккаунте OTA — бот не касается карты** (минимизация PCI-рисков) |
| 3DS/OTP | **Бот запрашивает код у директора в чате** на этапе оплаты (банки КЗ требуют OTP) |
| География | **Сначала Казахстан**, потом международные (директор пишет город, бот уточняет полный адрес) |
| Сервисы поиска/покупки | Предпочтительно сервисы банков **Freedom** (Aviata/Freedom Travel) и **Kaspi** (Kaspi Travel) |
| Оптимизация | Ранжирование вариантов: **сначала по общему времени в пути (доезд+перелёт), затем по цене** в рамках политики |
| Ввод ПДн | Директор присылает **PDF-документ**, бот извлекает данные **локально** (text-layer pypdf → OCR Tesseract), показывает **маскированно** на подтверждение, хранит зашифрованно. Карта/сырые ПДн в чат не вводятся |
| Геолокация | Бот по запросу просит геопозицию (кнопка Telegram `request_location`) → ближайший аэропорт по встроенному датасету (haversine, без живого Nominatim); цепочка: явное указание → геопозиция → город из профиля → уточнить |
| Контейнеры истории | **Папки по чатам**; каждая поездка = папка-контейнер с **хэш-именем**; быстрый индекс в БД (хэш+путь для доступа за O(1)) |
| Роли | Хардкод **ADMIN / DIRECTOR / ACCOUNTANT**; онбординг по **одноразовой ссылке-приглашению** |
| LLM | **Гибрид**: Claude (облако) для диалога/планирования + локальный агент для браузера/чувствительного |
| Приказ | Документ по **DOCX-шаблону с размеченными местами** (docxtpl), доставка в Telegram (email/WhatsApp — позже) |
| Хостинг | **VPS в Казахстане** (резидентность ПДн), Linux + headless-браузер |
| Стек | **Python 3.14.x + aiogram 3.x**, PostgreSQL, Playwright, Tesseract (OCR), Anthropic Claude API |
| Архитектура | **Вариант A — модульный монолит** с подключаемыми провайдерами (микросервисы только при высоком RPS; штата до ~10 чел. монолита достаточно) |
| Политика/лимиты | Бюджет, класс, звёздность, суточные — **значения по умолчанию пока не заданы**, хранятся в профиле, применение — План 3 |

## 3. Архитектура (Вариант A — модульный монолит)

Ключевые элементы: браузер-агент изолирован в **отдельном процессе-воркере** (краш браузера не роняет
бот); покупка моделируется как **сохраняемая сага** (стейт-машина), переживающая перезапуск и
умеющая «паузу на человека» (ввод OTP).

Компоненты (полный список в спеке §3): Telegram Gateway (aiogram) · Dialog Orchestrator (Claude,
маскирует PII перед отправкой в облако) · Trip Saga · BookingProvider (интерфейс; `BrowserAgentProvider`
сейчас, `ApiProvider`/GDS позже) · Browser-Agent Worker (Playwright + локальный LLM) · OrderService ·
ProfileService (шифр. PII) · RoleService/AccessControl · LocationService · TripArchive (контейнеры) ·
Index/DB (PostgreSQL) · Crypto/Secrets.

Паттерн, выдержанный в коде: **провайдеры/движки за интерфейсами + фейк/мок для тестов** (так сделаны
`OcrEngine`, `ProfileExtractor`; так же будут `BookingProvider`/`MockProvider` в Плане 3).

Хранилище-контейнеры:
```
storage/chats/<chat_hash>/trips/<trip_hash>/
    manifest.json  order/prikaz.pdf  flights/  hotel/  receipts/  agent_log/
```

## 4. Дорожная карта (планы)

- **План 1 — Фундамент** ✅ ЗАВЕРШЁН, в `main` (см. §5).
- **План 2 — Профиль + геолокация** ✅ ЗАВЕРШЁН, в `main` (см. §5).
- **План 3 — Оркестрация поездки + поиск** ← СЛЕДУЮЩИЙ. Claude-оркестратор (slot-filling: куда/когда/
  предпочтения, уточняющие вопросы, маскировка PII перед облаком), Trip Saga (сохраняемая стейт-машина),
  `BookingProvider` (интерфейс) + `MockProvider` (для тестов), ранжирование «время→цена в рамках
  политики», показ топ-вариантов + подтверждение в 1 тап.
- **План 4 — Браузер-агент + оплата**: `BrowserAgentProvider` (Playwright/OpenClaw), воркер, очередь,
  OTP-хэндофф через чат, идемпотентность, защита от двойной покупки.
- **План 5 — Приказ + архив/индекс**: OrderService (DOCX-шаблон → PDF), доставка, контейнеры +
  PostgreSQL-индекс, история и быстрый поиск поездок.

## 5. Текущее состояние — Планы 1 и 2 завершены (в `main`)

**Тесты: 85 passed (ruff чисто). Всё смержено в `main` локально. Удалённого пуша нет — пуш делает
владелец вручную** (`main` опережает `origin/main`).

### План 1 (Фундамент)
`config.py` (pydantic-settings) · `crypto.py` (`Cipher`/Fernet) · `db/base.py`, `db/models.py`
(async SQLAlchemy 2.0; `User`, `PendingInvite`) · `roles/` (`Role`, `InviteService`, `RoleService`) ·
`bot/permissions.py`, `bot/onboarding.py`, `bot/admin.py`, `bot/middleware.py`, `bot/main.py`
(`/start`, `/invite <role>`) · `Dockerfile`, `docker-compose.yml`.

### План 2 (Профиль + геолокация)
- `profile/` — `dto.py` (`ProfileDTO`, frozen), `masking.py` (`mask_iin`/`mask_document`),
  `service.py` (`ProfileService`: шифрует ИИН/ФИО/№док/дату Fernet-ом, отдаёт дешифрованный DTO;
  методы `upsert_identity`/`set_preferences`/`set_policy`/`set_default_departure`/`get_profile`).
- `profile/extraction/` — `ocr.py` (`OcrEngine` Protocol, `FakeOcrEngine` для тестов,
  `TesseractOcrEngine` с **ленивыми** импортами poppler/pytesseract), `pdf_text.py`
  (`PdfTextExtractor`: text-layer pypdf → OCR-fallback), `fields.py` (`RegexProfileExtractor`:
  ИИН/ФИО/№/дата/тип документа passport|udo).
- `location/` — `aliases.py` (нормализация + 17 городов KZ → IATA), `airports.py` (`Airport`,
  `AirportIndex` над встроенным `data/airports_kz.csv`: `nearest` haversine, `by_city` alias-aware,
  `by_iata`), `service.py` (`LocationService.resolve_departure`: явный город → координаты → профиль → None).
- `db/models.py` — добавлена модель `Profile` (1:1 по `telegram_user_id`; `_enc`-поля = Fernet-токены).
- `bot/profile_handlers.py` — `/profile` (маскированная сводка), загрузка PDF → маскированное
  подтверждение → Сохранить/Заново, `/location` + геопозиция → ближайший аэропорт как город вылета.
  Всё под правом `profile.edit` (DIRECTOR/ADMIN). `bot/middleware.py` инжектит `profile_service`
  (рядом с `role_service`/`invite_service`), `bot/main.py` строит синглтоны и подключает router.
- `Dockerfile` — добавлены Tesseract `rus/kaz/eng` + poppler; в `pyproject.toml` группа `[ocr]`
  (`pytesseract`, `pdf2image`, `pillow`); `pypdf` в базовых deps, `reportlab` в dev.
- **OCR проверен в образе** `ai-clerk:phase2`: Tesseract 5.5.0, языки rus/kaz/eng, `recognize_pdf`
  корректно распознал текст со скан-PDF.

**Сознательно отложено (как в спеке):** применение политики при ранжировании, NLU-разбор города из
свободного текста, live-Nominatim, локальный LLM-экстрактор, международные документы/адреса.

**Что ещё проверить вручную (нужен реальный BOT_TOKEN):** живой прогон в Telegram — прислать PDF →
Сохранить; поделиться геопозицией.

### Уроки из код-ревью (учитывать дальше)
- **План 1:** подписанные `itsdangerous`-токены содержат `.` и длиннее 64 симв. → Telegram deep-link
  их ломает (юнит-тесты при этом проходили!). Исправлено на случайные одноразовые токены
  (`secrets.token_urlsafe(32)`, в таблице `pending_invites`, single-use + TTL). **Мораль: для внешних
  интеграций тестировать не только логику, но и форматные ограничения платформы.**
- **План 2 (план vs реальность):** план Задачи 11 предполагал middleware из Плана-1-как-в-доке, но в
  коде `InviteService` уже стал DB-backed и инжектился через middleware — наивная замена middleware
  выкинула бы `invite_service` и сломала `/start`,`/invite`. **Мораль: перед интеграционными задачами
  читать актуальный код, а не доверять плану.**
- **План 2 (тест-фикстуры):** reportlab дефолтным шрифтом не рендерит кириллицу → text-layer выходил
  короче порога и тест уходил в OCR-ветку. Чинили строкой фикстуры (ASCII ≥ порога), не самим кодом.
- **План 2 (OCR-граница):** `\b` не срабатывает между кириллицей и цифрой (`ИИН900101300123`) — для
  ИИН используются lookaround'ы `(?<!\d)(\d{12})(?!\d)`, а не `\b`.

## 6. Структура репозитория и ключевые файлы

```
c:\Users\User\Desktop\AI-clerk\
  .venv\                         # Python 3.14 venv (gitignored)
  .env.example                   # шаблон переменных окружения
  Dockerfile, docker-compose.yml
  pyproject.toml                 # deps + extras [dev],[ocr] + pytest (pythonpath=src, asyncio_mode=auto)
  src/ai_clerk/
    config.py crypto.py
    db/ (base.py, models.py: User, PendingInvite, Profile)
    roles/ (enums, invites, service)
    profile/ (dto, masking, service, extraction/{ocr,pdf_text,fields})
    location/ (aliases, airports, service)  data/airports_kz.csv
    bot/ (permissions, onboarding, admin, middleware, main, profile_handlers)
  tests/...                      # 85 тестов; tests/fixtures/airports_sample.csv
  docs/superpowers/specs/2026-06-15-ai-secretary-business-trips-design.md        # СПЕЦИФИКАЦИЯ
  docs/superpowers/specs/2026-06-15-phase2-profile-location-design.md            # дизайн Плана 2
  docs/superpowers/plans/2026-06-15-phase1-foundation.md                         # план Плана 1
  docs/superpowers/plans/2026-06-15-phase2-profile-location.md                   # план Плана 2
  HANDOFF.md                     # этот файл
```

## 7. Окружение и запуск

- Python: использовать `.venv\Scripts\python.exe` (системный `python` = 3.13, нам нужен 3.14).
- Тесты: `.venv\Scripts\python.exe -m pytest -q`
- OCR локально не обязателен: тесты используют `FakeOcrEngine`; реальный Tesseract нужен только в
  проде/Docker (образ `ai-clerk:phase2`, `docker build -t ai-clerk:phase2 .`).
- Запуск бота (нужен реальный токен):
  ```
  cp .env.example .env   # BOT_TOKEN от @BotFather; сгенерировать SECRET_KEY и FERNET_KEY;
                         # ADMIN_TELEGRAM_IDS=[<ваш_telegram_id>]
  .venv\Scripts\python.exe -m ai_clerk.bot.main
  ```
- Проверка: `/start` → попросит инвайт; `/invite director` (от admin-id) → ссылка; открыть → роль
  выдана; `/profile` → пусто; прислать PDF → маскированное подтверждение → Сохранить; `/location` →
  поделиться геопозицией → ближайший аэропорт.
- Генерация ключей:
  - `FERNET_KEY`: `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`
  - `SECRET_KEY`: `python -c "import secrets;print(secrets.token_urlsafe(32))"`

## 8. Открытые вопросы (к будущим планам)

- Сам файл DOCX-шаблона приказа + реквизиты компании (предоставит владелец) — План 5.
- Требования к GPU на VPS для локального LLM/OpenClaw — План 4.
- Anthropic API-ключ и модель для оркестратора (claude-opus-4-8 / актуальная) — План 3.
- Корпоративные аккаунты в Aviata/Kaspi/Booking и доступность авто-логина — Планы 3–4.
- Значения политики по умолчанию (бюджет/класс/звёздность/суточные) — пока не заданы.
- (Решено в Плане 2) Справочник аэропортов = **OurAirports**, KZ-подмножество встроено в репозиторий.

## 9. Рабочий процесс (как велась разработка — повторить в новом чате)

1. **brainstorming** — уточнить требования (вопросы по одному), согласовать дизайн → записать спеку,
   дать пользователю вычитать.
2. **writing-plans** — bite-sized TDD-план (тест → падает → реализация → проходит → коммит).
3. **subagent-driven-development** — отдельный субагент на задачу, двухэтапное ревью между задачами
   (соответствие спеке, затем качество кода), финальный код-ревью; мелкие частые коммиты; работа в
   отдельной ветке (`planN-...`), затем `--no-ff` merge в `main`, удаление ветки.

Принципы: TDD, DRY, YAGNI, шифрование PII, обработка PII только локально, маскировка PII в чате,
никаких сырых данных карты, подтверждение перед оплатой.
