# Инструкция по переезду на Render.com (Бесплатно + Надежно)

Render — это крутой хостинг, но он удаляет все файлы при перезагрузке (как на школьном компьютере). Поэтому базу данных нужно хранить отдельно.

Мы используем связку: **Render (Сайт)** + **Neon (База данных)**. Оба сервиса имеют бесплатные тарифы.

## Шаг 1: Создание Базы Данных (Neon.tech)
1.  Зайдите на [neon.tech](https://neon.tech) -> Sign Up (можно через Google/GitHub).
2.  Создайте проект (Create Project):
    *   Name: `facevosait-db`
    *   Region: Frankfurt (ближе к нам).
3.  После создания вам покажут **Connection String** (строка подключения).
    *   Она выглядит так: `postgres://neondb_owner:AbC123...@ep-icy-....aws.neon.tech/neondb?sslmode=require`
    *   **Скопируйте её и сохраните!** Это ключ к вашей базе.

## Шаг 2: Подготовка кода (Я уже сделал)
Я добавил файл `render.yaml` и обновил `requirements.txt` для работы с PostgreSQL (вместо SQLite).

Вам нужно:
1.  Загрузить этот код на **GitHub**. (Если у вас нет GitHub, зарегистрируйтесь там и создайте репозиторий, затем загрузите туда все файлы проекта).

## Шаг 3: Запуск на Render.com (через Docker - Рекомендуется)
1.  Зайдите на [render.com](https://render.com) -> Sign Up.
2.  Нажмите **New +** -> **Web Service**.
3.  Выберите **Build and deploy from a Git repository**.
4.  Подключите свой GitHub и выберите репозиторий `facevosait`.
5.  Настройки:
    *   **Name:** `facevosait` (или любое другое имя).
    *   **Region:** Frankfurt (Germany).
    *   **Branch:** `main` (или `master`).
    *   **Runtime:** **Docker** (Это важно! Мы подготовили Dockerfile).
    *   **Instance Type:** Free ($0/month).
6.  **Environment Variables** (Переменные окружения):
    *   Пролистайте вниз и нажмите **Add Environment Variable**.
    *   Добавьте **4** переменные:
        1.  Key: `DATABASE_URL`
            Value: Вставьте строку подключения из Neon (`postgres://...`).
        2.  Key: `SECRET_KEY`
            Value: Придумайте любой длинный пароль.
        3.  Key: `BOT_TOKEN`
            Value: Токен вашего бота из @BotFather.
        4.  Key: `WEB_APP_URL`
            Value: Ссылка на ваш сайт на Render (например: `https://facevosait.onrender.com`).
            *(Сначала создайте сервис, узнайте ссылку, а потом добавьте эту переменную)*.
7.  Нажмите **Create Web Service**.

## Итог
Render начнет сборку (это займет 2-5 минут в первый раз).
Когда увидите зеленый статус **Live**, сайт будет доступен по ссылке (например, `https://facevosait.onrender.com`).
Он будет работать автоматически, база данных в Neon, а файлы не пропадут.

