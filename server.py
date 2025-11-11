from flask import Flask, jsonify, request
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)
# Абсолютный путь к папке channels_history
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.join(BASE_DIR, "channels_history")
def load_all_channels():
    """Загружает все *_filtered.json и убирает дубликаты по channel_id."""
    all_channels = []
    seen_ids = set()

    for filename in os.listdir():
        if filename.endswith("_filtered.json"):
            with open(filename, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    for c in data:
                        cid = c.get("channel_id")
                        if cid and cid not in seen_ids:
                            seen_ids.add(cid)
                            all_channels.append(c)
                except Exception as e:
                    print(f"Ошибка чтения {filename}: {e}")
    return all_channels
@app.route("/channel_growth/<channel_id>", methods=["GET"])
def get_channel_growth(channel_id):
    """
    Анализирует рост канала по подписчикам, просмотрам и видео.
    Ищет данные в файлах trending_channels_*.json
    """
    channel_history = []

    # Собираем все файлы с трендами
    for filename in os.listdir():
        if filename.startswith("trending_channels_") and filename.endswith(".json"):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for ch in data:
                        if ch.get("channel_id") == channel_id:
                            channel_history.append(ch)
            except Exception as e:
                print(f"Ошибка чтения {filename}: {e}")

    if not channel_history:
        return jsonify({"error": "Канал не найден"}), 404

    # Сортируем по дате
    channel_history.sort(key=lambda x: x.get("last_seen", ""), reverse=False)

    if len(channel_history) < 2:
        return jsonify({
            "message": "Недостаточно данных для анализа роста",
            "current": channel_history[-1]
        })

    # Берём последнюю и предыдущую запись
    prev = channel_history[-2]
    curr = channel_history[-1]

    def growth(old, new):
        if old == 0:
            return 0
        return round(((new - old) / old) * 100, 2)

    result = {
        "channel_id": channel_id,
        "channel_title": curr.get("channel_title"),
        "date_prev": prev.get("last_seen"),
        "date_curr": curr.get("last_seen"),
        "subscribers": {
            "previous": prev.get("subscribers", 0),
            "current": curr.get("subscribers", 0),
            "growth_percent": growth(prev.get("subscribers", 0), curr.get("subscribers", 0))
        },
        "views_total": {
            "previous": prev.get("views_total", 0),
            "current": curr.get("views_total", 0),
            "growth_percent": growth(prev.get("views_total", 0), curr.get("views_total", 0))
        },
        "videos_total": {
            "previous": prev.get("videos_total", 0),
            "current": curr.get("videos_total", 0),
            "growth_percent": growth(prev.get("videos_total", 0), curr.get("videos_total", 0))
        }
    }

    # Опционально — сохраняем статистику роста
    with open("channel_growth.json", "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

    return jsonify(result)

@app.route("/hashtags", methods=["GET"])
def get_hashtags():
    """
    Возвращает список хэштегов из файла trend_hashtags.txt,
    отсортированных по популярности (от большего к меньшему).
    """
    hashtag_file = "trend_hashtags.txt"
    if not os.path.exists(hashtag_file):
        return jsonify({"error": "Файл trend_hashtags.txt не найден"}), 404

    hashtags = []
    with open(hashtag_file, "r", encoding="utf-8") as f:
        for line in f:
            if "|" in line:
                try:
                    tag, pct = line.strip().split("|", 1)
                    pct_value = float(pct.strip().replace("%", ""))
                    hashtags.append({"tag": tag.strip(), "popularity": pct_value})
                except ValueError:
                    continue

    hashtags.sort(key=lambda x: x["popularity"], reverse=True)
    return jsonify(hashtags)
HISTORY_DIR = "channels_history"
def filter_by_date(channels, period):
    """Фильтрация по дате создания канала."""
    now = datetime.utcnow()
    if period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "month":
        cutoff = now - timedelta(days=30)
    elif period == "90days":
        cutoff = now - timedelta(days=90)
    else:
        return channels

    filtered = []
    for c in channels:
        try:
            created = datetime.fromisoformat(c["published_at"].replace("Z", "+00:00"))
            if created >= cutoff:
                filtered.append(c)
        except Exception:
            continue
    return filtered


@app.route("/channels", methods=["GET"])
def get_channels():
    """
    Основной роут:
    /channels?sort=subscribers|views&date=week|month|90days
    """
    sort_by = request.args.get("sort", "subscribers")
    date_filter = request.args.get("date")

    channels = load_all_channels()
    if not channels:
        return jsonify({"error": "Нет данных"}), 404

    if date_filter:
        channels = filter_by_date(channels, date_filter)

    # Сортировка по популярности
    reverse = True
    if sort_by == "views":
        channels.sort(key=lambda x: x.get("views", 0), reverse=reverse)
    else:
        channels.sort(key=lambda x: x.get("subscribers", 0), reverse=reverse)

    return jsonify(channels)


@app.route("/channel_analytics/<channel_id>", methods=["GET"])
def channel_analytics(channel_id):
    import urllib.parse
    channel_id = urllib.parse.unquote(channel_id)  # декодируем URL
    file_path = os.path.join(HISTORY_DIR, f"{channel_id}.json")
    print("Looking for file:", file_path)
    print("Exists:", os.path.exists(file_path))
    
    if not os.path.exists(file_path):
        return jsonify({"error": f"Канал {channel_id} не найден"}), 404

    with open(file_path, "r", encoding="utf-8") as f:
        history = json.load(f)
    return jsonify(history)



@app.route("/")
def index():
    return jsonify({
        "routes": {
            "/channels": "Получить все каналы (параметры: sort=subscribers|views, date=week|month|90days)",
            "/channel/<id>": "Получить данные конкретного канала"
        }
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
from flask import Flask, jsonify, request
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)

def load_all_channels():
    """Загружает все *_filtered.json и убирает дубликаты по channel_id."""
    all_channels = []
    seen_ids = set()

    for filename in os.listdir():
        if filename.endswith("_filtered.json"):
            with open(filename, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    for c in data:
                        cid = c.get("channel_id")
                        if cid and cid not in seen_ids:
                            seen_ids.add(cid)
                            all_channels.append(c)
                except Exception as e:
                    print(f"Ошибка чтения {filename}: {e}")
    return all_channels


def filter_by_date(channels, period):
    """Фильтрация по дате создания канала."""
    now = datetime.utcnow()
    if period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "month":
        cutoff = now - timedelta(days=30)
    elif period == "90days":
        cutoff = now - timedelta(days=90)
    else:
        return channels

    filtered = []
    for c in channels:
        try:
            created = datetime.fromisoformat(c["published_at"].replace("Z", "+00:00"))
            if created >= cutoff:
                filtered.append(c)
        except Exception:
            continue
    return filtered


@app.route("/channels", methods=["GET"])
def get_channels():
    """
    Основной роут:
    /channels?sort=subscribers|views&date=week|month|90days
    """
    sort_by = request.args.get("sort", "subscribers")
    date_filter = request.args.get("date")

    channels = load_all_channels()
    if not channels:
        return jsonify({"error": "Нет данных"}), 404

    if date_filter:
        channels = filter_by_date(channels, date_filter)

    # Сортировка по популярности
    reverse = True
    if sort_by == "views":
        channels.sort(key=lambda x: x.get("views", 0), reverse=reverse)
    else:
        channels.sort(key=lambda x: x.get("subscribers", 0), reverse=reverse)

    return jsonify(channels)


@app.route("/channel_analytics/<channel_id>", methods=["GET"])
def channel_analytics(channel_id):
    file_path = os.path.join(HISTORY_DIR, f"{channel_id}.json")
    
    # Логирование для отладки
    print("Looking for file:", file_path)
    print("Exists:", os.path.exists(file_path))
    
    if not os.path.exists(file_path):
        return jsonify({"error": f"Канал {channel_id} не найден"}), 404

    with open(file_path, "r", encoding="utf-8") as f:
        history = json.load(f)

    return jsonify(history)


@app.route("/")
def index():
    return jsonify({
        "routes": {
            "/channels": "Получить все каналы (параметры: sort=subscribers|views, date=week|month|90days)",
            "/channel/<id>": "Получить данные конкретного канала"
        }
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
