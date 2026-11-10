# Деплой на виртуальную машину (без контейнеров)

Выбранный путь: Ubuntu 24.04 + PostgreSQL + systemd + nginx. Docker и Podman не
нужны.

## Что должно быть на машине

- Ubuntu 22.04 или 24.04 LTS;
- 2 vCPU, 2 ГБ RAM, 20 ГБ SSD;
- публичный IP;
- открытые порты 22, 80, 443 в группе безопасности;
- SSH-доступ.

## Порядок

1. Скопировать проект на сервер:

```bash
scp -r "D:\Неон.Пульс" user@<IP>:/opt/neonpulse
```

2. Запустить установку:

```bash
ssh user@<IP>
sudo bash /opt/neonpulse/deploy/install.sh
```

Скрипт поставит пакеты, создаст пользователя и базу, соберёт venv, настроит
systemd и nginx, проверит `/api/health`.

3. Открыть `http://<IP>` и войти под демо-доступом.

## Обновление

```bash
scp -r "D:\Неон.Пульс\app" user@<IP>:/opt/neonpulse/
scp -r "D:\Неон.Пульс\web" user@<IP>:/opt/neonpulse/
ssh user@<IP> "sudo /opt/neonpulse/.venv/bin/pip install -r /opt/neonpulse/requirements.txt && sudo systemctl restart neonpulse"
```

## Домен и HTTPS

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.ru
```

## Полезные команды

```bash
sudo systemctl status neonpulse
sudo journalctl -u neonpulse -f
sudo cat /etc/neonpulse.env
sudo -u postgres psql neonpulse
```
