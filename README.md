# Crypto Index Price Tracker

Сервис раз в минуту забирает с биржи [Deribit](https://docs.deribit.com/) текущие
index price для `btc_usd` и `eth_usd`, сохраняет в PostgreSQL тикер, цену и время
(UNIX timestamp) и отдаёт сохранённые данные через HTTP API на FastAPI.

**Стек:** Python 3.12 · FastAPI · Celery (Redis broker) · aiohttp · SQLAlchemy 2 (async, asyncpg) ·
Alembic · PostgreSQL · pydantic-settings · uv · ruff · mypy --strict · pytest.

---

## Содержание

- [Быстрый старт (Docker)](#быстрый-старт-docker)
- [HTTP API](#http-api)
- [Архитектура](#архитектура)
- [Конфигурация](#конфигурация)
- [Локальная разработка](#локальная-разработка)
- [Тесты и качество кода](#тесты-и-качество-кода)

---

## Быстрый старт (Docker)

Нужны Docker и Docker Compose v2.

```bash
cp .env.example .env        # и замените пароли change-me на свои, сгенерировать можно через `openssl rand -hex 32`
docker compose up --build -d
```

Поднимутся контейнеры:

| Сервис       | Что делает                                                         |
|--------------|--------------------------------------------------------------------|
| `postgres`   | PostgreSQL 17, данные в volume `postgres-data`                     |
| `redis`      | брокер сообщений Celery                                            |
| `migrations` | одноразовый `alembic upgrade head`  |
| `api`        | FastAPI (uvicorn) на <http://localhost:8000>                       |
| `worker`     | Celery worker: забирает цены с Deribit и пишет в БД                |
| `beat`       | Celery beat: раз в минуту ставит задачу сбора на каждый тикер      |

`api`, `worker`, `beat` и `migrations` это один и тот же образ с разными командами.

Проверка:

```bash
docker compose ps
docker compose logs --follow worker
curl "http://localhost:8000/api/v1/prices/latest?ticker=btc_usd"
```

Интерактивная документация: Swagger UI – <http://localhost:8000/docs>, ReDoc – <http://localhost:8000/redoc>.

Остановка: `docker compose down` (данные БД сохраняются в volume; `docker compose down -v` удалит и их).

> Если порты `5432`, `6379` или `8000` заняты, поменяйте `POSTGRES_PORT` / `REDIS_PORT` / `API_PORT` в `.env`.

---

## HTTP API

Все методы – `GET`, у каждого метода обязательный query-параметр `ticker` (`btc_usd` | `eth_usd`).

| Метод                         | Назначение                                     | Доп. параметры                              |
|-------------------------------|------------------------------------------------|---------------------------------------------|
| `GET /api/v1/prices`          | все сохранённые цены по тикеру                 | `limit`, `offset`                           |
| `GET /api/v1/prices/latest`   | последняя цена по тикеру                       | —                                           |
| `GET /api/v1/prices/by-date`  | цены по тикеру с фильтром по дате              | `date_from`, `date_to`, `limit`, `offset`   |
| `GET /health`                 | liveness probe                                 | —                                           |

**Параметры**

- `limit` – размер страницы, `1..1000`, по умолчанию `100`; `offset` – сколько записей пропустить, по умолчанию `0`
  (не больше `2^63 - 1`: PostgreSQL принимает `OFFSET` как `BIGINT`).
- `date_from`, `date_to` – границы периода, **обе включительные и обе необязательные** (без границы период открыт
  с этой стороны). Формат: ISO 8601 с часовым поясом (`2026-10-14T15:00:00Z`, `2026-10-14T18:00:00+03:00`)
  или UNIX timestamp (`1791990000`). Дата без часового пояса отклоняется.

Списки упорядочены от старых записей к новым.

**Примеры**

```bash
curl "http://localhost:8000/api/v1/prices?ticker=eth_usd&limit=2"
```

```json
{
  "items": [
    {"ticker": "eth_usd", "price": "2438.41", "timestamp": 1791991868},
    {"ticker": "eth_usd", "price": "2439.01", "timestamp": 1791991873}
  ],
  "total": 3,
  "limit": 2,
  "offset": 0
}
```

```bash
curl "http://localhost:8000/api/v1/prices/latest?ticker=btc_usd"
```

```json
{"ticker": "btc_usd", "price": "81841.29", "timestamp": 1791991878}
```

```bash
curl "http://localhost:8000/api/v1/prices/by-date?ticker=btc_usd&date_from=2026-10-14T15:31:00Z&date_to=1791991878"
```

**Ошибки** – JSON вида `{"detail": ...}`:

| Код   | Когда                                                                                  | `detail`                    |
|-------|----------------------------------------------------------------------------------------|-----------------------------|
| `404` | `/latest`: по тикеру ещё ничего не собрано                                             | строка                      |
| `422` | нет `ticker`, неизвестный тикер, `limit`/`offset` вне границ, некорректная дата, `date_from > date_to` | список ошибок в формате FastAPI (`loc`, `msg`, ...) |
| `503` | PostgreSQL недоступен или не ответил вовремя; запрос можно повторить                   | строка                      |

---

## Архитектура

Слоистая архитектура (clean / hexagonal): зависимости направлены только внутрь.

```
                 ┌──────────────────────── entrypoints ────────────────────────┐
                 │  api/ (FastAPI: routes, schemas,     worker/ (Celery app,   │
                 │  dependencies, error mapping)         tasks, beat schedule) │
                 │            composition roots: здесь собираются зависимости  │
                 └───────────────┬──────────────────────────────┬──────────────┘
                                 │                              │
                                 ▼                              ▼
  ┌──────────── infrastructure ────────────┐      ┌──────────── application ───────────┐
  │ deribit/   DeribitClient (aiohttp)     │─────▶│ ports: IndexPriceProvider,         │
  │ database/  Database, ORM, repository   │      │        PriceRepository, Clock      │
  │ clock.py   SystemClock                 │      │ CollectIndexPrice, PriceQueryService│
  └────────────────────────────────────────┘      │ Pagination, Page, ошибки use-case'ов│
                                                  └─────────────────┬───────────────────┘
                                                                    ▼
                                                  ┌────────────── domain ──────────────┐
                                                  │ IndexPrice, Ticker, TimeRange,     │
                                                  │ инварианты и доменные ошибки       │
                                                  └────────────────────────────────────┘
```

| Слой             | Ответственность                                                   | Зависит от                      |
|------------------|-------------------------------------------------------------------|---------------------------------|
| `domain`         | сущности, value objects, инварианты                                | только stdlib                   |
| `application`    | use-case'ы и порты (интерфейсы), которые им нужны                  | `domain`                        |
| `infrastructure` | адаптеры портов: Deribit, PostgreSQL, системные часы               | `application`, `domain`         |
| `entrypoints`    | HTTP API и Celery: разбор входа, сборка зависимостей, маппинг ошибок | все слои                       |

Поток данных:

```
beat ──(каждую минуту, задача на тикер)──▶ redis ──▶ worker
worker: CollectIndexPrice ── DeribitClient ──GET public/get_index_price──▶ Deribit
                          └─ SqlAlchemyPriceRepository ──INSERT ... ON CONFLICT DO NOTHING──▶ PostgreSQL
client ──GET /api/v1/prices…──▶ api: PriceQueryService ── SqlAlchemyPriceRepository ──SELECT──▶ PostgreSQL
```

Структура проекта:

```
src/price_tracker/
├── domain/                 # IndexPrice, Ticker, TimeRange, доменные исключения
├── application/            # порты, CollectIndexPrice, PriceQueryService, пагинация, исключения
├── infrastructure/
│   ├── deribit/            # DeribitClient + pydantic-схемы JSON-RPC ответа
│   ├── database/           # Database (engine/sessions), ORM-модель, репозиторий
│   └── clock.py
├── entrypoints/
│   ├── api/                # create_app(), роуты, зависимости, схемы ответов, обработчики ошибок
│   └── worker/             # create_celery_app(), задача сбора, расписание beat, __main__
└── config.py               # настройки из переменных окружения
migrations/                 # Alembic (async env)
tests/
├── unit/                   # domain, application, Deribit-клиент, API, Celery-задачи
└── integration/            # репозиторий на реальном PostgreSQL
```

---

## Конфигурация

Все настройки – переменные окружения (локально читаются и из `.env`). Образец – [`.env.example`](.env.example).

| Переменная                         | По умолчанию                       | Описание                                          |
|------------------------------------|------------------------------------|---------------------------------------------------|
| `POSTGRES_HOST`                    | `localhost`                        | хост PostgreSQL                                   |
| `POSTGRES_PORT`                    | `5432`                             | порт PostgreSQL (в compose — ещё и порт на хосте) |
| `POSTGRES_USER`                    | `postgres`                         | пользователь                                      |
| `POSTGRES_PASSWORD`                | — (обязательна)                    | пароль                                            |
| `POSTGRES_DB`                      | `price_tracker`                    | имя базы                                          |
| `REDIS_HOST`                       | `localhost`                        | хост Redis (брокер Celery)                        |
| `REDIS_PORT`                       | `6379`                             | порт Redis (в compose — ещё и порт на хосте)      |
| `REDIS_PASSWORD`                   | — (в compose обязателен)           | пароль Redis                                      |
| `REDIS_DB`                         | `0`                                | номер базы Redis                                  |
| `API_PORT`                         | `8000`                             | порт API на хосте (только для docker compose)     |
| `COLLECTOR_TICKERS`                | `["btc_usd", "eth_usd"]`           | какие тикеры собирать (JSON-список)               |
| `COLLECTOR_INTERVAL_SECONDS`       | `60`                               | период сбора; он же предельная длительность запуска |
| `COLLECTOR_MAX_RETRIES`            | `3`                                | повторы при временной недоступности биржи или БД  |
| `DERIBIT_BASE_URL`                 | `https://www.deribit.com/api/v2`   | базовый URL API Deribit (тестнет: `https://test.deribit.com/api/v2`) |
| `DERIBIT_REQUEST_TIMEOUT_SECONDS`  | `10`                               | таймаут запроса к Deribit                         |

Переменные `POSTGRES_*` те же, что у официального образа `postgres`, поэтому один `.env` настраивает и БД, и приложение.

---

## Локальная разработка

Нужен [uv](https://docs.astral.sh/uv/) (он сам поставит Python 3.12, если его нет).

```bash
uv sync                                   # зависимости, включая dev
cp .env.example .env
docker compose up --detach postgres redis # только инфраструктура
uv run alembic upgrade head               # миграции
```

Процессы (каждый в своём терминале):

```bash
uv run uvicorn price_tracker.entrypoints.api.app:create_app --factory --reload
uv run python -m price_tracker.entrypoints.worker worker --loglevel=INFO
uv run python -m price_tracker.entrypoints.worker beat --loglevel=INFO
```

`python -m price_tracker.entrypoints.worker` – это обычный CLI `celery`, привязанный к приложению из фабрики,
поэтому принимает все его команды и опции (`worker`, `beat`, `inspect`, ...).

Новая миграция после изменения ORM-моделей:

```bash
uv run alembic revision --autogenerate -m "describe change"
```

---

## Тесты и качество кода

```bash
make lint              # ruff format --check, ruff check (все правила), mypy --strict
make audit             # известные уязвимости в зависимостях из uv.lock
make test              # unit-тесты с покрытием (без внешних зависимостей, без .env и переменных окружения)
make test-integration  # интеграционные тесты: нужен PostgreSQL (docker compose up -d postgres)
make test-all          # всё вместе
```

| Что тестируется                     | Как                                                                                      |
|-------------------------------------|------------------------------------------------------------------------------------------|
| домен, use-case'ы                   | чистые unit-тесты с in-memory фейками портов (`tests/fakes.py`), без моков              |
| `DeribitClient`                     | против настоящего локального HTTP-сервера (`aiohttp.test_utils.TestServer`): успех, 429/5xx, таймаут, отказ соединения, JSON-RPC ошибка, мусор в ответе, редирект, слишком большой и gzip-«бомба» |
| ошибки хранилища                    | трансляция отказов соединения в `StorageUnavailableError`, недоступная БД → `503`        |
| HTTP API                            | через ASGI-транспорт `httpx2` с подменой `PriceQueryService` на in-memory репозиторий    |
| Celery-задачи                       | `task.apply()`: делегирование в use-case, политика ретраев, расписание beat              |
| `SqlAlchemyPriceRepository`         | на реальном PostgreSQL: отдельная БД `<POSTGRES_DB>_test` пересоздаётся и мигрируется Alembic'ом на каждый прогон, каждый тест — в откатываемой транзакции |
| `Database`                          | на реальном PostgreSQL: сессия API не может писать и читает один снимок; максимальный `offset` принимается |
| end-to-end                          | настоящие composition roots: worker собирает цену с фейкового Deribit (локальный HTTP-сервер) в PostgreSQL, API с реальным lifespan её отдаёт; зависший Deribit не держит запуск дольше интервала |

`alembic check` (модели совпадают с миграциями), сборка Docker-образа.

---