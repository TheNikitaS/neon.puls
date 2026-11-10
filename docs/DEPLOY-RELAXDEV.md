# Деплой через GitHub + Relax Dev + YandexGPT

Схема без виртуальной машины и без Docker на вашем компьютере:

```
GitHub (код)  →  Relax Dev (Python + PostgreSQL, HTTPS)  →  публичная ссылка
                                  │
                                  └──→ YandexGPT API (грант Yandex Cloud)
```

Приложение живёт на серверах Relax Dev, база — там же, AI вызывается по API из
Yandex Cloud. Грант расходуется только на модели, не на вычисления.

## 1. Что нужно

- аккаунт GitHub;
- аккаунт Relax Dev (есть бесплатный период, дальше тариф PRO);
- каталог в Yandex Cloud с грантом и сервисный аккаунт для YandexGPT.

## 2. Подготовка репозитория

В папке проекта уже есть `Procfile`, `runtime.txt`, `requirements.txt`,
`Dockerfile` и `.env.example`. Репозиторий инициализирован локально.

Создайте пустой репозиторий на GitHub и выполните:

```powershell
cd D:\Неон.Пульс
git remote add origin https://github.com/<ваш-логин>/neonpulse.git
git branch -M main
git push -u origin main
```

Git попросит войти в GitHub — это делает владелец аккаунта.

## 3. YandexGPT: ключ и каталог

1. Консоль Yandex Cloud → **Сервисные аккаунты** → создать `neonpulse-ai`.
2. Роль `ai.languageModels.user` на каталог.
3. Создать **API-ключ**, сохранить.
4. Записать **folder-id** каталога.

## 4. Приложение в Relax Dev

1. **Новый проект** → подключить GitHub → выбрать репозиторий `neonpulse`.
2. Тип проекта: Python (или Dockerfile, если платформа предложит выбор).
3. Команда запуска, если спросит:

```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

4. Добавить базу **PostgreSQL** в панели проекта.
5. Прописать переменные окружения:

| Переменная | Значение |
|---|---|
| `DATABASE_URL` | строка подключения из панели Relax Dev |
| `NEONPULSE_SECRET` | случайная строка 48+ символов |
| `NEONPULSE_SANDBOX` | `1` пока нет реальных камер и касс |
| `NEONPULSE_LLM_PROVIDER` | `yandexgpt` |
| `YANDEX_FOLDER_ID` | folder-id каталога |
| `YANDEX_API_KEY` | API-ключ сервисного аккаунта |
| `YANDEX_MODEL` | `yandexgpt-lite` |

6. Нажать **Deploy**. Платформа соберёт проект и выдаст адрес с HTTPS.

## 5. Проверка

```powershell
curl https://<адрес>/api/health
```

Ожидается `{"ok":true,...}`. Затем вход `demo@neonpulse.ru` / `Demo2026!`,
смена демо-паролей, проверка дашборда и ручного ввода выручки.

## 6. Обновления

Любой `git push` в `main` — Relax Dev пересоберёт и перезапустит приложение
автоматически.

## 7. Если база не подключается

- Убедитесь, что `DATABASE_URL` начинается с `postgresql://` или `postgres://` —
  приложение само приведёт его к драйверу `psycopg`.
- Если провайдер требует SSL, добавьте `?sslmode=require` в конец строки.
- Проверьте логи сборки и запуска в панели Relax Dev.

## 8. Ограничения

- Бесплатный период Relax Dev ограничен, дальше тариф PRO.
- Приложение должно слушать порт из переменной `PORT` — это уже настроено.
- SQLite на PaaS не подходит: диск эфемерный, данные пропадут при пересборке.
  Используйте PostgreSQL.
