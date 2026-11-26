# 💱 fxbot — курсы валют в Telegram с графиками за час, сравнением и историей в PostgreSQL

Бот на **Python 3.11+** (aiogram 3), который по кнопке рисует график курса
за час/сутки/неделю/месяц, умеет сравнивать две валюты на одном графике,
отдаёт график в **SVG** и складывает все движения курсов **в PostgreSQL**.

Валюты: **рубль** (к доллару), **доллар**, **евро**, **юань**.

![Меню бота](docs/menu.png)

| График за час | Сравнение валют | История за 7 дней |
|---|---|---|
| ![USD/RUB за час](docs/chart-usd-1h.png) | ![EUR/RUB vs CNY/RUB](docs/chart-compare.png) | ![EUR/RUB 7 дней](docs/chart-eur-7d.png) |

---

## Что умеет

- **4 кнопки с валютами** под карточкой-меню: Рубль, Доллар, Евро, Юань.
  Рубль показан как `RUB/USD` (сколько долларов за 1 ₽), остальные — как `X/RUB`.
- **График за час** по умолчанию, плюс переключатели `1 час / 24 часа / 7 дней / 30 дней`.
- **Сравнение любых двух валют** на одном графике: обе линии приводятся к
  процентному изменению от начала периода — так видно, кто вырос сильнее.
- **SVG-файл** того же графика по кнопке (вектор, открывается в браузере).
- **PNG 2560×1440 без сжатия** — кнопка «Без сжатия»: Telegram пережимает
  обычные фото в JPEG, а документ отдаёт ровно так, как нарисовано.
  Режим `SEND_AS=document` делает такими все графики.
- **PostgreSQL**: раз в минуту бот снимает курсы в `rate_ticks`, раз в час
  пересчитывает дневную агрегацию `daily_stats` (open/high/low/close и % за день).
- Графики за час/сутки берутся из **своей** базы, когда она уже накопила данные,
  иначе — из Yahoo Finance (и попутно наполняют базу).
- Работает и без БД (`DATABASE_URL` пустой) — тогда все графики идут из провайдера.

---

## Как это устроено

```
Telegram  ──►  aiogram 3 (handlers)
                    │
                    ├── ChartService ──► charts/model.py (геометрия)
                    │                        ├── charts/svg.py  → .svg
                    │                        └── charts/png.py  → .png (Pillow, 2x SSAA)
                    │
                    ├── RateService ──► PostgreSQL (asyncpg): rate_ticks, daily_stats
                    │        └────────► YahooProvider (HTTP, без ключа) / DemoProvider
                    │
                    └── poller (asyncio task): раз в минуту снимает курсы,
                                               раз в час делает rollup в daily_stats
```

Важная деталь: **SVG и PNG рисуются из одного и того же «списка примитивов»**
(прямоугольники, линии, тексты). Поэтому картинка в чате и скачанный SVG
выглядят одинаково, а matplotlib/cairo в зависимостях не нужны.

```
fxbot/
├── run.py                     # python run.py
├── app/
│   ├── main.py                # запуск бота + поллера + БД
│   ├── config.py              # .env → Settings
│   ├── pairs.py               # валюты, периоды, тикеры Yahoo
│   ├── formatting.py          # формат чисел для подписей
│   ├── charts/
│   │   ├── model.py           # расчёт геометрии (единый для SVG и PNG)
│   │   ├── svg.py             # рендер в SVG
│   │   ├── png.py             # рендер в PNG (Pillow, суперсэмплинг 2x)
│   │   ├── menu.py            # карточка-меню с 4 плитками
│   │   └── theme.py           # палитра и поиск шрифтов
│   ├── db/
│   │   ├── schema.sql         # таблицы (идемпотентно)
│   │   ├── pool.py            # подключение + применение схемы
│   │   └── repo.py            # все SQL-запросы
│   ├── providers/
│   │   ├── base.py            # интерфейс источника
│   │   ├── yahoo.py           # Yahoo Finance (внутридневные данные)
│   │   ├── yahoo_parse.py     # чистый парсер ответа (тестируется без сети)
│   │   └── demo.py            # генератор правдоподобных данных
│   ├── services/
│   │   ├── rates.py           # откуда брать ряд: БД или провайдер
│   │   ├── charts_service.py  # данные → ChartSpec → PNG+SVG
│   │   └── poller.py          # фоновый опрос и rollup
│   └── bot/
│       ├── handlers.py        # команды и колбэки
│       ├── keyboards.py       # кнопки
│       ├── texts.py           # подписи (HTML)
│       └── middleware.py      # DI сервисов в хендлеры
├── scripts/
│   ├── set_token.py           # диалог «вставьте токен» с проверкой
│   ├── backfill.py            # дневная история за 30 дней
│   ├── seed_demo.py           # демо-данные без интернета
│   └── preview_charts.py      # перегенерировать картинки для README
├── tests/                     # 30 тестов без сети и БД
├── docs/                      # примеры графиков
├── set-token.cmd              # вставить токен (двойной щелчок)
├── run.cmd                    # запустить бота (двойной щелчок)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Быстрый старт: две двойные щелчка

Python, PostgreSQL, база и виртуальное окружение **уже установлены** — шаги 2 и 3
из инструкции ниже делать не нужно. Осталось два действия:

**1. Получите токен бота**

1. Откройте Telegram, найдите **@BotFather**.
2. Отправьте ему `/newbot`.
3. Придумайте имя (любое) и username — он обязан заканчиваться на `bot`,
   например `nikita_fx_rates_bot`.
4. BotFather ответит строкой вида `1234567890:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw`.
   Это и есть токен — скопируйте его целиком.

**2. Вставьте токен и запустите**

В папке `fxbot` двойной щелчок по **`set-token.cmd`**. Откроется окно, где нужно
вставить токен (правый клик в окне = вставка) и нажать Enter. Скрипт сам:

- проверит токен в Telegram и скажет, за какого бота он отвечает;
- запишет его в файл `.env` (искать его вручную не нужно);
- предложит сразу запустить бота.

Дальше откройте Telegram и отправьте боту `/start`.

> **Где находится `.env`**, если хотите отредактировать вручную:
> `C:\Users\nikita\Documents\deepseek-harness\default-workspace\fxbot\.env`.
> Открывается Блокнотом:
> `notepad "C:\Users\nikita\Documents\deepseek-harness\default-workspace\fxbot\.env"`.
> Внутри есть строка `BOT_TOKEN=` — токен дописывается после знака `=`:
> `BOT_TOKEN=1234567890:AAHdqTcv...` Без кавычек, без пробелов.

### Куда вводить команды из шагов 2 и 3

Никуда — они уже выполнены на этой машине:

| Шаг из инструкции | Статус |
|---|---|
| Шаг 2: `python -m venv .venv`, `pip install -r requirements.txt` | готово, окружение в `fxbot\.venv` |
| Шаг 3: установка и настройка PostgreSQL, создание базы | готово, база `fxbot` на порту 5432 |

Команды из инструкции — это текст для терминала (PowerShell или `cmd`), а не для
чата с ботом. Если понадобится вводить их вручную: нажмите `Win`, наберите
`PowerShell`, откройте, затем `cd` в папку проекта и вставляйте строку.
Но для запуска бота этого не требуется — достаточно `run.cmd`.

---

## Пошагово (полная версия)

### Шаг 0. Что нужно

- Python **3.11+** (проверено на 3.11.9 и 3.12).
- PostgreSQL **13+** (проверено на 13.22; в docker-compose используется 16).
- Токен бота.
- Интернет: курсы берутся с Yahoo Finance (`query1.finance.yahoo.com`), ключ не нужен.

### Что уже установлено и настроено на этой машине

Python и PostgreSQL уже развёрнуты, база под бота создана — остаётся вписать токен.

| Компонент | Где | Как проверить |
|---|---|---|
| Python 3.11.9 | `D:\Python 3.11\python.exe` | `python --version` |
| PostgreSQL 13.22 | `D:\postgreSQL` (данные в `D:\postgreSQL\data`) | `psql --version` |
| Служба PostgreSQL | `postgresql-x64-13`, автозапуск, порт 5432 | `Get-Service postgresql-x64-13` |
| Виртуальное окружение | `fxbot\.venv` (все зависимости стоят) | `fxbot\.venv\Scripts\python.exe -m pip list` |
| Роль и база | `fxbot` / `fxbot`, суперпользователь `postgres` / `postgres` | `psql -U fxbot -d fxbot -c "\dt"` |
| `D:\Python 3.11` и `D:\postgreSQL\bin` | добавлены в пользовательский `PATH` | `where python`, `where psql` |

Пароли ролей — локальные, для разработки: `postgres` / `postgres` и `fxbot` / `fxbot`.
Смените их, если база будет доступна по сети (`ALTER ROLE fxbot PASSWORD '...'`).

Запуск после вставки токена в `.env` (любой из способов):

```powershell
cd fxbot
.\run.cmd                      # проще всего: берёт Python из .venv
# либо
.\.venv\Scripts\python.exe run.py
```

Если токен ещё не вставлен, откройте `set-token.cmd` — он спросит токен,
проверит его и сам запишет в `.env`.

`run.cmd` не зависит от политики выполнения PowerShell. Если хотите
активировать окружение вручную и `Activate.ps1` блокируется политикой:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned   # один раз
.\.venv\Scripts\Activate.ps1
python run.py
```

### Шаг 1. Создать бота в Telegram

1. Откройте [@BotFather](https://t.me/BotFather) → `/newbot`.
2. Имя и username (должен заканчиваться на `bot`).
3. Скопируйте токен вида `123456789:AAE...`.

Ничего в настройках BotFather менять не нужно: бот работает через long polling,
вебхук и HTTPS не требуются.

### Шаг 2. Код и зависимости

```bash
cd fxbot
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

Зависимости: `aiogram` (Telegram), `aiohttp` (HTTP), `asyncpg` (PostgreSQL),
`Pillow` + `numpy` (рендер PNG), `python-dotenv` (.env), `tzdata` (часовые пояса).

> На Linux для картинок нужен шрифт с кириллицей:
> `sudo apt install fonts-dejavu-core` (в Dockerfile это уже сделано).
> На Windows/macOS бот сам найдёт Segoe UI / Arial.
>
> `tzdata` обязателен на Windows: без него `zoneinfo` не находит
> `Europe/Moscow`, и бот падает при старте с ошибкой часового пояса.

### Шаг 3. PostgreSQL

**Вариант А — уже установлен на этой машине** (`D:\postgreSQL`, служба
`postgresql-x64-13`): ничего делать не нужно, роль `fxbot` и база `fxbot` созданы.
Проверить:

```powershell
$env:PGPASSWORD="fxbot"; psql -h 127.0.0.1 -U fxbot -d fxbot -c "select version();"
```

**Вариант Б — Docker:**

```bash
docker run -d --name fxbot-db \
  -e POSTGRES_USER=fxbot \
  -e POSTGRES_PASSWORD=fxbot \
  -e POSTGRES_DB=fxbot \
  -p 5432:5432 \
  -v fxbot-pgdata:/var/lib/postgresql/data \
  postgres:16-alpine
```

**Вариант В — локальный Postgres на Linux:**

```bash
sudo -u postgres psql -c "CREATE USER fxbot WITH PASSWORD 'fxbot';"
sudo -u postgres psql -c "CREATE DATABASE fxbot OWNER fxbot;"
```

**Вариант Г — сразу всё в docker-compose** (бот + база), см. шаг 7.

Таблицы создавать вручную не нужно: бот применяет `app/db/schema.sql`
при каждом старте (скрипт идемпотентный).

### Шаг 4. Настройки

```bash
cp .env.example .env
```

Откройте `.env` и заполните:

```dotenv
BOT_TOKEN=123456789:AAE-your-token-here
DATABASE_URL=postgresql://fxbot:fxbot@localhost:5432/fxbot
RATES_PROVIDER=yahoo
TZ_NAME=Europe/Moscow
POLL_INTERVAL=60
ADMIN_IDS=            # ваш user_id, чтобы открыть /stats (узнать: /id)
LOG_LEVEL=INFO
```

| Переменная | Зачем |
|---|---|
| `BOT_TOKEN` | токен от BotFather (обязательно) |
| `DATABASE_URL` | DSN Postgres; пусто — работа без истории |
| `RATES_PROVIDER` | `yahoo` — реальные курсы, `demo` — генератор для проверки интерфейса |
| `TZ_NAME` | часовой пояс подписей на графиках |
| `POLL_INTERVAL` | как часто снимать курс, секунды (мин. 20) |
| `SEND_AS` | `photo` — график картинкой в чат, `document` — файлом без сжатия |
| `ADMIN_IDS` | кому доступна `/stats` |

### Шаг 5. Первый запуск

Двойной щелчок по `run.cmd` в папке `fxbot` (либо в терминале `.\run.cmd`).

Что произойдёт:

1. подключение к Postgres (с ретраями — можно стартовать раньше базы);
2. создание таблиц;
3. прогрев: бот тянет у провайдера историю за 30 дней и раскладывает её в
   `daily_stats`, чтобы графики «7 дней» и «30 дней» сразу были осмысленными;
4. запуск поллера: раз в минуту `rate_ticks`, раз в час `daily_stats`;
5. long polling Telegram.

В логе увидите:

```
12:00:01 INFO    app.main                 Провайдер курсов: yahoo · часовой пояс: Europe/Moscow
12:00:02 INFO    app.db.pool              PostgreSQL подключён (попытка 1)
12:00:02 INFO    app.db.pool              Схема БД применена: schema.sql
12:00:04 INFO    app.main                 Бот @my_fx_bot запущен
12:00:04 INFO    app.services.poller      Снимок курсов: 4 пар
```

Полезно на первом запуске (в другом терминале, с тем же `.env`):

```powershell
.\.venv\Scripts\python.exe -m scripts.backfill --days 30   # дневная история в daily_stats
```

### Шаг 6. Проверить в Telegram

1. `/start` → приходит карточка-меню с 4 плитками и кнопками
   «🇷🇺 Рубль / 🇺🇸 Доллар / 🇪🇺 Евро / 🇨🇳 Юань / 📊 Сравнить валюты».
2. Нажмите «Доллар» → фото с графиком за час, под ним кнопки периодов,
   «Сравнить» и «SVG-файл».
3. «Сравнить валюты» → выберите две валюты (`Евро` → `Юань`) → общий график
   в процентах и подпись с разрывом.
4. «SVG-файл» → бот присылает `.svg` документом.

### Шаг 7. Запуск одной командой (Docker Compose)

```bash
cp .env.example .env      # вписать BOT_TOKEN
docker compose up -d --build
docker compose logs -f bot
```

`docker-compose.yml` поднимает Postgres 16 с healthcheck и бота, который ждёт базу.
`DATABASE_URL` внутри compose уже переопределён на `db:5432`.

---

## База данных

### Таблицы

```sql
-- 1. Сырые точки: одна в минуту на пару (поллер) + бэкфилл провайдера
rate_ticks(id, pair, ts, price, source)          -- UNIQUE(pair, ts)

-- 2. Движение по дням: считается из rate_ticks раз в час
daily_stats(pair, day, open_price, high_price, low_price, close_price,
            change_pct, points, source, updated_at)   -- PK(pair, day)

-- 3. Журнал запросов: кто что смотрел
chart_events(id, user_id, pair, period, compare_pair, created_at)
```

`pair` — текст вида `USD/RUB`, `RUB/USD`, `EUR/RUB`, `CNY/RUB`.
`change_pct` — изменение close к open внутри дня в процентах.

### Агрегация `daily_stats`

Раз в час (и при старте) выполняется один `INSERT … SELECT` с
`array_agg(price ORDER BY ts)` для open/close, `min/max` для low/high и
`ON CONFLICT (pair, day) DO UPDATE` — поэтому сегодняшняя строка обновляется
по мере дня, а прошлые дни остаются неизменными:

```sql
WITH agg AS (
    SELECT pair, day,
           (array_agg(price ORDER BY ts))[1]      AS open_price,
           max(price)                             AS high_price,
           min(price)                             AS low_price,
           (array_agg(price ORDER BY ts DESC))[1] AS close_price,
           count(*)::int                          AS points
    FROM (
        SELECT pair, ts, price, ((ts AT TIME ZONE $1)::date) AS day
        FROM rate_ticks
        WHERE ts >= $2 AND ts < $3
    ) src
    GROUP BY pair, day
)
INSERT INTO daily_stats (pair, day, open_price, high_price, low_price,
                         close_price, change_pct, points, source)
SELECT pair, day, open_price, high_price, low_price, close_price,
       CASE WHEN open_price = 0 THEN 0
            ELSE round((close_price - open_price) / open_price * 100, 4) END,
       points, 'rollup'
FROM agg
ON CONFLICT (pair, day) DO UPDATE SET …;
```

Посмотреть своими глазами:

```sql
-- что бот накопил за последний час
SELECT ts, price FROM rate_ticks WHERE pair = 'USD/RUB' ORDER BY ts DESC LIMIT 20;

-- движения по дням
SELECT day, open_price, high_price, low_price, close_price, change_pct
FROM daily_stats WHERE pair = 'USD/RUB' ORDER BY day DESC LIMIT 7;
```

### Откуда берутся данные для графика

| Период | Сначала | Если мало данных |
|---|---|---|
| 1 час, 24 часа | `rate_ticks` (если покрывают ≥70% окна и ≥10 точек) | Yahoo `5m/1d` и `15m/2d`, найденное дописывается в `rate_ticks` |
| 7, 30 дней | `daily_stats` (если ≥3 дней и ≥70% периода) | Yahoo `1d/1mo` и `1d/3mo`, найденное пишется в `daily_stats` |

Поэтому: свежий бот показывает данные провайдера, а через час работы графики
за час уже строятся по собственной минутной истории (точнее, чем у провайдера),
и подпись под графиком честно меняется на `PostgreSQL · N точек`.

---

## Про «кнопки с изображением валют»

Bot API **не умеет рисовать картинки внутри inline-кнопок** — у кнопки есть
только текст. Поэтому сделано так, как это принято в ботах:

1. Над клавиатурой отправляется **карточка-картинка** с четырьмя плитками
   валют (флаг-цвет, код, название, текущий курс и изменение) — визуально это
   и есть «кнопки с картинками».
2. В самих кнопках — **флаги-эмодзи** `🇷🇺 🇺🇸 🇪🇺 🇨🇳`. В клиентах Telegram
   они отображаются как картинки, а порядок кнопок совпадает с плитками
   (2×2), так что нажатие считывается однозначно.

Если нужны именно растровые иконки в кнопках, есть два пути:
- **премиум-эмодзи** (custom emoji) в тексте кнопки — нужен свой набор эмодзи
  и подписка Telegram Premium у владельца бота;
- **Web App-кнопка** с HTML-интерфейсом внутри Telegram — тогда «кнопки»
  рисует уже ваш сайт. Это отдельный, более крупный проект.

---

## Настройка под себя

### Добавить валюту

`app/pairs.py`:

```python
"GBP": PairDef(
    code="GBP", pair="GBP/RUB", title="Фунт", unit="₽ за 1 £",
    symbol="₽", flag="🇬🇧", color="#7DD3FC", yahoo="GBPRUB=X",
    derive=("GBP/USD", "*", "USD/RUB"),   # если прямого тикера нет
),
```

и добавьте код в `PAIR_ORDER` (порядок кнопок). Больше ничего менять не нужно:
клавиатура, меню, сравнение и БД работают по этому словарю.

### Добавить период

`app/pairs.py` → `PERIODS`:

```python
"12h": PeriodDef("12h", 12 * 3600, "за 12 часов", "12 ч", 2 * 3600, "30m", "1d", False),
```

### Другой источник курсов

Нужен внутридневной ряд (ЦБ РФ даёт только курс на завтра — для графика за час
не подходит). Реализуйте `RateProvider` в `app/providers/`:

```python
class MyProvider(RateProvider):
    name = "My API"
    async def history(self, pair, period) -> list[Point]: ...
    async def latest(self, pair) -> float: ...
```

и добавьте его в `build_provider()` (`app/providers/__init__.py`).

---

## Деплой на сервер (systemd)

```ini
# /etc/systemd/system/fxbot.service
[Unit]
Description=fxbot telegram currency bot
After=network-online.target

[Service]
Type=simple
User=fxbot
WorkingDirectory=/opt/fxbot
EnvironmentFile=/opt/fxbot/.env
ExecStart=/opt/fxbot/.venv/bin/python run.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fxbot
journalctl -u fxbot -f
```

Ретеншн (если не нужна минутная история за годы):

```sql
DELETE FROM rate_ticks WHERE ts < now() - interval '180 days';
```

---

## Тесты и превью

```powershell
# 30 тестов: геометрия графиков, SVG/PNG, парсер Yahoo, форматирование,
# свёртка часового ряда в дневной, единственная HTTP-сессия
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .

# перегенерировать картинки для README (демо-данные, без сети и БД)
.\.venv\Scripts\python.exe -m scripts.preview_charts
```

Тесты не требуют ни Telegram, ни сети, ни Postgres — проверяются расчёты,
рендер и разбор ответа Yahoo.

---

## Частые проблемы

| Симптом | Причина и решение |
|---|---|
| `Ошибка конфигурации: Не задан BOT_TOKEN` | токен не вставлен — запустите `set-token.cmd` |
| `Не удалось подключиться к PostgreSQL` | служба не запущена (`Start-Service postgresql-x64-13`) или неверный DSN |
| `Не найден часовой пояс 'Europe/Moscow'` | на Windows не установлен `tzdata`: `pip install tzdata` |
| `Telegram server says - Unauthorized` | в `.env` лежит чужой/просроченный токен — возьмите новый у @BotFather |
| В подписи `Демо-данные` | стоит `RATES_PROVIDER=demo`; поставьте `yahoo` |
| График пустой, «мало данных» | провайдер не отдал ряд; проверьте сеть и `docker compose logs` |
| Вместо ₽/€/¥ квадратики | нет шрифта с этими символами: `apt install fonts-dejavu-core` |
| `HTTP 429` от Yahoo | слишком частые запросы; увеличьте `POLL_INTERVAL` |
| Кнопки не реагируют | бот не запущен либо вы жмёте кнопку старого сообщения после рестарта — нажмите `/start` |
| Нужны графики «за час» сразу после установки | выполните `python -m scripts.backfill --days 30` |
| `Activate.ps1` не запускается (политика) | используйте `.\run.cmd` или задайте `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

---

## Что проверено на живой системе

| Проверка | Результат |
|---|---|
| Тесты | 30 тестов, все проходят |
| Схема и запросы на PostgreSQL 13.22 | `upsert_ticks` (1156 строк, повтор даёт 0), `rollup` (повтор обновляет день), `upsert_daily`, `daily`, `ticks`, `stats`, `log_event` |
| Реальные курсы Yahoo | USD/RUB 82,19 · EUR/RUB 90,25 · CNY/RUB 12,33 · RUB/USD 0,0122 — все 4 пары |
| Графики на живых данных | за час, 24 часа, 7 и 30 дней + сравнение двух валют |
| Полный старт `run.py` | подключение к БД, схема, прогрев, снимок курсов — до авторизации в Telegram |

Две ошибки, найденные и исправленные при этой проверке:

1. **Утечка HTTP-сессий.** Прогрев запускает запросы к четырём парам
   параллельно, и `YahooProvider.start()` создавал по сессии на каждую
   корутину — лишние оставались висеть (`Unclosed client session`).
   Теперь создание сессии защищено `asyncio.Lock`.
2. **Китайский юань без дневной истории.** У пары `CNYRUB=X` Yahoo отдаёт
   ровно одну дневную свечу, поэтому графики «7 дней» и «30 дней» падали с
   «Недостаточно данных». Добавлен запасной путь: если дневных точек меньше
   трёх, ряд собирается из часовых данных (`aggregate_daily`).

Заодно: ряды, которые провайдер отдаёт с запасом (месяц на «7 дней», квартал
на «30 дней»), теперь обрезаются по запрошенному окну — график и подпись
говорят про один и тот же период.

---

## Лицензия

MIT — берите и меняйте под себя.
