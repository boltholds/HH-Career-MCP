# HH Career MCP

MCP-сервер для безопасной работы с карьерными данными HH.ru через официальный API: поиск вакансий, чтение собственных резюме и дальнейшая подготовка адаптированных вариантов резюме.

Проект развивается API-first. Playwright не входит в критический контур и может быть добавлен позднее только как управляемый пользователем UI-helper без массового скрапинга.

## Доступные MCP-инструменты

Текущая версия read-only:

- `hh_connection_status` — доступность HH API и безопасный статус OAuth;
- `hh_get_current_user` — текущий авторизованный пользователь;
- `hh_search_vacancies` — поиск вакансий с типизированными фильтрами;
- `hh_get_vacancy` — полная карточка вакансии;
- `hh_list_my_resumes` — список собственных резюме;
- `hh_get_my_resume` — полная карточка выбранного резюме.

Сервер не отправляет отклики и сообщения, не редактирует и не публикует резюме. Write-инструменты будут добавляться отдельно с явным подтверждением пользователя.

## OAuth HH.ru

Используется authorization-code flow с PKCE `S256` и проверкой `state`. Access и refresh токены сохраняются атомарно вне репозитория. Refresh выполняется только после фактического истечения access token, поскольку refresh token HH.ru одноразовый.

### Создание приложения

1. Создайте приложение в кабинете разработчика HH.ru.
2. Укажите redirect URI точно:

```text
http://127.0.0.1:8766/oauth/callback
```

3. Скопируйте `.env.example` в `.env`.
4. Заполните как минимум:

```dotenv
HH_CLIENT_ID=your_client_id
HH_CLIENT_SECRET=your_client_secret
HH_REDIRECT_URI=http://127.0.0.1:8766/oauth/callback
HH_USER_AGENT=HH-Career-MCP/0.2 (your-email@example.com)
```

`HH_USER_AGENT` должен содержать название приложения и рабочий контакт разработчика.

## Локальный запуск

Требуется Python 3.12+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Авторизация:

```powershell
hh-career-auth login
hh-career-auth status
```

Команда откроет HH.ru в браузере, примет callback только на localhost и сохранит токен в `.data/hh/token.json`. Файл исключён из Git.

Локальный stdio MCP:

```powershell
hh-career-mcp
```

## Docker Compose + Secure MCP Tunnel

Схема повторяет рабочую модель `Telegram_MCP_Bridge`:

```text
ChatGPT
   │ Secure MCP Tunnel
   ▼
tunnel-client sidecar
   │ http://hh-career-mcp:8000/mcp
   ▼
HH Career MCP
   │ OAuth2
   ▼
api.hh.ru
```

Нужны:

- Docker Desktop;
- HH.ru `client_id` и `client_secret`;
- OpenAI Tunnel ID;
- Runtime API key для tunnel-client.

Заполните в `.env`:

```dotenv
HH_CLIENT_ID=your_client_id
HH_CLIENT_SECRET=your_client_secret
HH_USER_AGENT=HH-Career-MCP/0.2 (your-email@example.com)
TUNNEL_ID=tunnel_your_id
CONTROL_PLANE_API_KEY=sk-your_runtime_key
```

Сначала выполните OAuth-авторизацию. Одноразовый контейнер использует тот же закрытый volume, что и MCP:

```powershell
docker compose run --rm --service-ports hh-auth
```

После успешной авторизации запустите MCP и туннель:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f
```

Проверка tunnel-client:

```powershell
curl.exe http://127.0.0.1:8082/readyz
```

По умолчанию:

- MCP доступен локально на `127.0.0.1:8000/mcp`;
- OAuth callback публикуется только на `127.0.0.1:8766`;
- health/UI tunnel-client доступны на `127.0.0.1:8082`;
- профиль туннеля называется `hh-career-mcp`;
- OAuth и tunnel state хранятся в отдельных Docker volumes.

В ChatGPT откройте **Настройки → Коннекторы**, создайте коннектор типа **Tunnel** и выберите тот же Tunnel ID. `tunnel-client` должен быть запущен во время обнаружения коннектора и последующих MCP-вызовов.

Не используйте `docker compose down -v`, если хотите сохранить OAuth-токен и профиль туннеля.

## Локальный tunnel-client на Windows

Этот вариант запускает MCP через stdio без Docker.

Установите проект в `.venv`, выполните `hh-career-auth login`, затем создайте профиль:

```powershell
.\scripts\setup-tunnel.ps1 -TunnelId tunnel_your_id -Force
```

Runtime API key храните только в текущей PowerShell-сессии или секрет-менеджере:

```powershell
$env:CONTROL_PLANE_API_KEY = "sk-your_runtime_key"
.\scripts\run-tunnel.ps1
```

`run-tunnel.ps1` сначала выполняет `doctor --explain`, а затем запускает профиль `hh-career-mcp`.

## Переменные окружения

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `HH_CLIENT_ID` | ID приложения HH.ru | обязательна для OAuth |
| `HH_CLIENT_SECRET` | секрет приложения HH.ru | обязательна для OAuth |
| `HH_REDIRECT_URI` | зарегистрированный callback | `http://127.0.0.1:8766/oauth/callback` |
| `HH_TOKEN_FILE` | локальный token store | `.data/hh/token.json` |
| `HH_ACCESS_TOKEN` | ручной override без refresh | пусто |
| `HH_MCP_TRANSPORT` | `stdio` или `streamable-http` | `stdio` |
| `HH_MCP_HOST` | адрес HTTP MCP | `127.0.0.1` |
| `HH_MCP_PORT` | порт HTTP MCP | `8000` |
| `HH_MCP_PATH` | Streamable HTTP endpoint | `/mcp` |
| `TUNNEL_ID` | Secure MCP Tunnel ID | обязательна для sidecar |
| `CONTROL_PLANE_API_KEY` | OpenAI Runtime API key | обязательна для sidecar |
| `TUNNEL_PROFILE` | профиль tunnel-client | `hh-career-mcp` |
| `TUNNEL_HEALTH_PORT` | локальный health/UI порт | `8082` |
| `TUNNEL_CLIENT_VERSION` | закреплённая версия sidecar | `0.0.10` |

## Безопасность

- OAuth-токены, client secret и Runtime API key не коммитятся.
- MCP и callback-порт Docker публикуются только на loopback-интерфейсе.
- Статус OAuth никогда не возвращает значения access или refresh token.
- Token store записывается атомарно с правами `0600`, где это поддерживается ОС.
- Tunnel-client открывает исходящее соединение; входящий публичный порт для MCP не нужен.
- Отправка откликов, сообщений и публикация изменений резюме отсутствуют.

## Разработка

```powershell
ruff check .
pytest -q
```

## Следующие этапы

1. Master-resume facts store с подтверждёнными фактами опыта.
2. Анализ соответствия вакансии и объяснимый scoring.
3. Генерация варианта резюме с diff без публикации.
4. Чтение откликов и актуального HH Chat API.
5. Подтверждаемые write-операции.
6. Опциональный browser helper без массового скрапинга.
