# Деплой НЕОН.ПУЛЬС в Yandex Cloud

Два рабочих варианта: **Serverless Containers** (проще, платите за запросы) и
**виртуальная машина** (полный контроль). База — Managed PostgreSQL, ключи и
модели ИИ — через сервисный аккаунт Yandex Cloud.

## 1. Подготовка

```bash
yc init
yc config set folder-id <FOLDER_ID>
```

Нужны: каталог (folder), сервисный аккаунт, Container Registry, Managed PostgreSQL.

## 2. База данных

```bash
yc managed-postgresql cluster create neonpulse-db \
  --network-name default \
  --host zone-id=ru-central1-a,subnet-id=<SUBNET_ID> \
  --resource-preset s2.micro \
  --disk-size 20 \
  --disk-type network-ssd \
  --user name=neonpulse,password=<DB_PASSWORD> \
  --database name=neonpulse,owner=neonpulse
```

Строка подключения:

```
postgresql+psycopg://neonpulse:<DB_PASSWORD>@<HOST>:6432/neonpulse
```

## 3. Образ приложения

```bash
yc container registry create --name neonpulse
REGISTRY_ID=$(yc container registry get --name neonpulse --format json | jq -r .id)

docker build -t cr.yandex/$REGISTRY_ID/neonpulse:latest .
docker push cr.yandex/$REGISTRY_ID/neonpulse:latest
```

## 4. Сервисный аккаунт для YandexGPT

```bash
yc iam service-account create --name neonpulse-ai
SA_ID=$(yc iam service-account get --name neonpulse-ai --format json | jq -r .id)

yc resource-manager folder add-access-binding <FOLDER_ID> \
  --role ai.languageModels.user \
  --subject serviceAccount:$SA_ID

yc iam key create --service-account-id $SA_ID --output sa-key.json
```

API-ключ для вызова модели:

```bash
yc iam api-key create --service-account-id $SA_ID
```

## 5. Serverless Container

```bash
yc serverless container create --name neonpulse

yc serverless container revision deploy \
  --container-name neonpulse \
  --image cr.yandex/$REGISTRY_ID/neonpulse:latest \
  --cores 1 --memory 1GB --concurrency 8 --execution-timeout 30s \
  --service-account-id $SA_ID \
  --environment DATABASE_URL="postgresql+psycopg://neonpulse:<DB_PASSWORD>@<HOST>:6432/neonpulse" \
  --environment NEONPULSE_SECRET="<RANDOM_SECRET>" \
  --environment NEONPULSE_LLM_PROVIDER="yandexgpt" \
  --environment YANDEX_FOLDER_ID="<FOLDER_ID>" \
  --environment YANDEX_API_KEY="<API_KEY>" \
  --environment YANDEX_MODEL="yandexgpt-lite"
```

Контейнер слушает порт **8080**. Публичный доступ:

```bash
yc serverless container allow-unauthenticated-invoke neonpulse
```

## 6. Виртуальная машина (альтернатива)

```bash
yc compute instance create-with-container neonpulse-vm \
  --zone ru-central1-a \
  --network-interface subnet-name=default-ru-central1-a,nat-ip-version=ipv4 \
  --container-name=neonpulse \
  --container-image=cr.yandex/$REGISTRY_ID/neonpulse:latest \
  --container-env=DATABASE_URL="postgresql+psycopg://...",NEONPULSE_SECRET="...",NEONPULSE_LLM_PROVIDER="yandexgpt",YANDEX_FOLDER_ID="...",YANDEX_API_KEY="..."
```

## 7. Переменные окружения

| Переменная | Значение |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://...` |
| `NEONPULSE_SECRET` | случайная строка 48+ символов |
| `NEONPULSE_SANDBOX` | `0` для реальных коннекторов |
| `NEONPULSE_LLM_PROVIDER` | `yandexgpt` |
| `YANDEX_FOLDER_ID` | id каталога |
| `YANDEX_API_KEY` | API-ключ сервисного аккаунта |
| `YANDEX_MODEL` | `yandexgpt-lite` или `yandexgpt` |

## 8. Проверка

```bash
curl https://<URL>/api/health
curl -X POST https://<URL>/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@neonpulse.ru","password":"Demo2026!"}'
```

## 9. Что важно

- Секреты храните в Lockbox или переменных ревизии, не в образе.
- Для Managed PostgreSQL включите резервное копирование.
- YandexGPT вызывается только на сервере: ключ не попадает в браузер.
- Если модель недоступна, AI-ядро автоматически отвечает детерминированно
  (`fallback: rules`) — платформа не ломается.
