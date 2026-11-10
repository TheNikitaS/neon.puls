# API НЕОН.ПУЛЬС

Базовый URL: `http://127.0.0.1:8010`. Авторизация — `Authorization: Bearer <token>`,
организация — `X-Organization-Id: <id>` (по умолчанию берётся из токена).

## Авторизация

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/api/auth/register` | регистрация компании и администратора |
| POST | `/api/auth/login` | вход, возвращает токен и список организаций |
| GET | `/api/auth/me` | профиль, организация, роль |
| POST | `/api/auth/switch/{org_id}` | переключение организации |

## Организация

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/org` | организация и подписка |
| GET | `/api/org/members` | сотрудники и роли |
| POST | `/api/org/members` | добавить сотрудника |
| PATCH | `/api/org/members/{id}` | роль, scope, активность |
| GET/POST | `/api/org/regions` | регионы |
| GET | `/api/org/audit` | журнал действий |

## Точки

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/locations` | список доступных точек |
| POST | `/api/locations` | создать точку |
| GET | `/api/locations/{id}` | карточка: камеры, зоны, изменения |
| PATCH | `/api/locations/{id}` | изменить точку |
| POST | `/api/locations/{id}/cameras` | добавить камеру |
| GET/POST | `/api/locations/{id}/changes` | изменения в точке |
| GET/PUT | `/api/locations/{id}/pilot` | настройки пилота точки |
| GET/POST | `/api/locations/{id}/audience` | локальная ЦА точки |
| DELETE | `/api/locations/{id}/audience/{segment_id}` | удалить сегмент |
| GET/PUT | `/api/locations/{id}/score` | оценка визуальной эффективности |
| GET/POST | `/api/locations/{id}/hypotheses` | гипотезы |
| PATCH | `/api/locations/{id}/hypotheses/{hid}` | итог гипотезы |
| GET/POST | `/api/locations/{id}/tests` | план тестов |
| PATCH | `/api/locations/{id}/tests/{tid}` | результат теста |
| GET/POST | `/api/locations/{id}/trends` | тренды и инфоповоды |
| GET/POST | `/api/locations/{id}/photos` | фото-аудит |

## Аналитика

Параметры: `date_from`, `date_to` (ISO), `location_ids` (через запятую).

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/analytics/overview` | KPI, динамика, серия, рейтинг |
| GET | `/api/analytics/series` | дневная серия |
| GET | `/api/analytics/compare` | текущий и предыдущий период |
| GET | `/api/analytics/ranking` | рейтинг точек |
| GET | `/api/analytics/hourly` | профиль по часам |
| GET | `/api/analytics/weekday` | профиль по дням недели |
| GET | `/api/analytics/before-after` | сравнение «до/после» (`location_id`, `change_id` или `change_at`) |

## AI

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/api/ai/analyze/{location_id}` | разбор точки, сохраняет выводы и рекомендации |
| POST | `/api/ai/analyze-network` | разбор сети |
| GET | `/api/ai/insights` | история выводов |
| GET | `/api/ai/recommendations` | рекомендации |
| PATCH | `/api/ai/recommendations/{id}` | статус рекомендации |
| POST | `/api/ai/ask` | вопрос по данным компании |
| GET/POST | `/api/ai/experiments` | эксперименты и вердикты |

## Интеграции

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/integrations/catalog` | доступные коннекторы |
| GET/POST | `/api/integrations` | список и создание |
| PATCH | `/api/integrations/{id}` | настройки |
| POST | `/api/integrations/{id}/test` | проверка соединения |
| POST | `/api/integrations/{id}/sync?days=3` | синхронизация |
| GET | `/api/integrations/{id}/logs` | журнал |
| DELETE | `/api/integrations/{id}` | удалить |

## Отчёты, уведомления, админ

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/reports/daily` | CSV: дневная детализация |
| GET | `/api/reports/ranking` | CSV: рейтинг точек |
| GET | `/api/notifications` | уведомления |
| POST | `/api/notifications/{id}/read` | отметить прочитанным |
| POST | `/api/notifications/scan` | поиск аномалий |
| GET | `/api/admin/stats` | сводка платформы (суперадмин) |
| GET | `/api/admin/organizations` | организации |
| GET | `/api/admin/users` | пользователи |
| GET | `/api/admin/integrations` | интеграции платформы |
| PATCH | `/api/admin/organizations/{id}` | тариф и статус |

## Пример

```bash
curl -s -X POST http://127.0.0.1:8010/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@neonpulse.ru","password":"Demo2026!"}'
```

```bash
curl -s "http://127.0.0.1:8010/api/analytics/overview?date_from=2026-10-13&date_to=2026-11-09" \
  -H "Authorization: Bearer <token>" -H "X-Organization-Id: 1"
```
