# Price Radar

Telegram-бот для мониторинга новых товаров и поиска цен ниже рынка.

## Что уже есть

- Добавление правил мониторинга через Telegram.
- Источники: Avito как первый рабочий модуль, Ozon/Wildberries/Auto.ru как подключаемые модули.
- SQLite база: правила, найденные товары, отправленные уведомления.
- Расчет типичной цены через медиану с отсечением выбросов.
- Фоновая проверка по расписанию.

## Запуск

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp config.yaml.example config.yaml  # если используешь example
nano config.yaml
python bot.py
```

Или через переменную окружения:

```bash
export BOT_TOKEN="123456:ABC..."
python bot.py
```

## Команды

```text
/start
/add avito iPhone 15 Pro 256GB
/add all iPhone 15 Pro 256GB
/list
/delete 1
/check
```

## Важно

Парсинг сайтов может ломаться из-за изменений верстки и антибот-защиты. Ядро сделано модульным: если один источник временно сломается, остальные не должны падать.
