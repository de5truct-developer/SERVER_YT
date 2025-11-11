from googleapiclient.discovery import build
import json
from collections import Counter
import datetime
from datetime import date
import os
import random
import time

REGIONS = [
    "AE","AR","AT","AU","AZ","BE","BG","BH","BO","BR","BY","CA","CH","CL","CO","CR",
    "CZ","DE","DK","DO","DZ","EC","EE","EG","ES","FI","FR","GB","GE","GH","GR","GT",
    "HK","HN","HR","HU","ID","IE","IL","IN","IQ","IS","IT","JM","JO","JP","KE","KH",
    "KR","KW","KZ","LB","LT","LU","LV","LY","MA","MK","MM","MT","MX","MY","NG","NI",
    "NL","NO","NP","NZ","OM","PA","PE","PH","PK","PL","PS","PT","PY","QA","RO","RS",
    "RU","SA","SE","SG","SI","SK","SN","SV","TH","TN","TR","TT","TW","TZ","UA","UG",
    "US","UY","VE","VN","YE","ZA","ZW"
]

SCHEDULE_HOURS = [12, 23]
HISTORY_DIR = "channels_history"
os.makedirs(HISTORY_DIR, exist_ok=True)

def get_api_key():
    with open("api_keys.txt", "r", encoding="utf-8") as f:
        keys = [k.strip() for k in f.read().split(",") if k.strip()]
    return random.choice(keys)

def update_channel_history(channel):
    channel_id = channel["channel_id"]
    file_path = os.path.join(HISTORY_DIR, f"{channel_id}.json")

    # Загружаем старую историю
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"channel_id": channel_id, "channel_title": channel["channel_title"],
                "history": {"daily": [], "monthly": [], "quarterly": []}}

    today = datetime.date.fromisoformat(channel["last_seen"])
    current_month = today.strftime("%Y-%m")
    current_quarter = f"{today.year}-Q{(today.month-1)//3+1}"

    # --- Daily ---
    daily_history = data["history"]["daily"]
    if not daily_history or daily_history[-1]["date"] != channel["last_seen"]:
        daily_history.append({
            "date": channel["last_seen"],
            "subscribers": channel["subscribers"],
            "views_total": channel["views_total"],
            "videos_total": channel["videos_total"]
        })

    # --- Monthly ---
    month_history = data["history"]["monthly"]
    if not month_history or month_history[-1]["month"] != current_month:
        # Новый месяц — стартовые значения
        month_history.append({
            "month": current_month,
            "subscribers_start": channel["subscribers"],
            "subscribers_end": channel["subscribers"],
            "subscribers_growth": 0,
            "views_start": channel["views_total"],
            "views_total": channel["views_total"],
            "views_growth": 0,
            "videos_start": channel["videos_total"],
            "videos_total": channel["videos_total"],
            "videos_added": 0
        })
    else:
        # Обновляем текущий месяц
        month_record = month_history[-1]
        month_record["subscribers_end"] = channel["subscribers"]
        month_record["subscribers_growth"] = month_record["subscribers_end"] - month_record["subscribers_start"]
        month_record["views_total"] = channel["views_total"]
        month_record["views_growth"] = month_record["views_total"] - month_record["views_start"]
        month_record["videos_total"] = channel["videos_total"]
        month_record["videos_added"] = month_record["videos_total"] - month_record["videos_start"]

    # --- Quarterly ---
    quarter_history = data["history"]["quarterly"]
    if not quarter_history or quarter_history[-1]["quarter"] != current_quarter:
        # Новый квартал — стартовые значения
        quarter_history.append({
            "quarter": current_quarter,
            "subscribers_start": channel["subscribers"],
            "subscribers_end": channel["subscribers"],
            "subscribers_growth": 0,
            "views_start": channel["views_total"],
            "views_total": channel["views_total"],
            "views_growth": 0,
            "videos_start": channel["videos_total"],
            "videos_total": channel["videos_total"],
            "videos_added": 0
        })
    else:
        # Обновляем текущий квартал
        quarter_record = quarter_history[-1]
        quarter_record["subscribers_end"] = channel["subscribers"]
        quarter_record["subscribers_growth"] = quarter_record["subscribers_end"] - quarter_record["subscribers_start"]
        quarter_record["views_total"] = channel["views_total"]
        quarter_record["views_growth"] = quarter_record["views_total"] - quarter_record["views_start"]
        quarter_record["videos_total"] = channel["videos_total"]
        quarter_record["videos_added"] = quarter_record["videos_total"] - quarter_record["videos_start"]

    # Сохраняем историю
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)




def collect_trending(region):
    api_key = get_api_key()
    youtube = build("youtube", "v3", developerKey=api_key)
    date_str = datetime.date.today().isoformat()
    filename = f"trending_channels_{region}.json"
    hashtag_file = "trend_hashtags.txt"

    category_ids = [
        "1","10","15","17","19","20","22","23","24","25","26","27","28"
    ]

    videos = []
    for category_id in category_ids:
        try:
            request = youtube.videos().list(
                part="snippet,statistics",
                chart="mostPopular",
                regionCode=region,
                videoCategoryId=category_id,
                maxResults=50
            )
            response = request.execute()

            for item in response.get("items", []):
                videos.append({
                    "video_id": item["id"],
                    "title": item["snippet"]["title"],
                    "hashtags": item["snippet"].get("tags", []),
                    "channel_id": item["snippet"]["channelId"],
                    "channel_title": item["snippet"]["channelTitle"],
                    "views": int(item["statistics"].get("viewCount", 0)),
                    "category_id": category_id,
                    "region": region,
                    "trend_type": get_trend_type(),
                    "date": date_str
                })
            print(f"[{region}] Category {category_id}: {len(response.get('items', []))} videos")
        except Exception as e:
            print(f"[{region}] Error for category {category_id}: {e}")
            continue

    print(f"[{region}] Total videos collected: {len(videos)}")

    # === Анализ хэштегов ===
    hashtag_counter = Counter()
    for v in videos:
        unique_tags = set(tag.strip().lower() for tag in v.get("hashtags", []) if tag.strip())
        for tag in unique_tags:
            hashtag_counter[tag] += 1

    total_videos = len(videos) if videos else 1  # защита от деления на ноль

    # Подготовка новых хэштегов с процентами
    new_stats = {
        tag: round((count / total_videos) * 100, 2)
        for tag, count in hashtag_counter.items()
    }

    # Загрузка старых данных, если есть
    if os.path.exists(hashtag_file):
        with open(hashtag_file, "r", encoding="utf-8") as f:
            existing_lines = [line.strip() for line in f if line.strip()]
        existing_map = {}
        for line in existing_lines:
            if "|" in line:
                tag, pct = line.split("|", 1)
                existing_map[tag.strip().lower()] = pct.strip()
            else:
                existing_map[line.strip().lower()] = "0%"
    else:
        existing_map = {}

    # Обновляем процент или добавляем новый тег
    for tag, pct in new_stats.items():
        existing_map[tag] = f"{pct}%"

    # Сохраняем обратно без дубликатов
    with open(hashtag_file, "w", encoding="utf-8") as f:
        for tag in sorted(existing_map.keys()):
            f.write(f"{tag} | {existing_map[tag]}\n")

    print(f"[{region}] Updated {len(new_stats)} hashtags (with percentages).")

    # === Сбор статистики по каналам ===
    counter = Counter([v["channel_id"] for v in videos])
    trending_channels = [
        {
            "channel_id": cid,
            "channel_title": next(v["channel_title"] for v in videos if v["channel_id"] == cid),
            "count": count,
            "last_seen": date_str
        }
        for cid, count in counter.most_common()
    ]

    # Получаем расширенные данные о каналах
    channel_ids = [c["channel_id"] for c in trending_channels]
    channel_stats = []

    for i in range(0, len(channel_ids), 50):
        batch_ids = channel_ids[i:i + 50]
        channel_request = youtube.channels().list(
            part="snippet,statistics",
            id=",".join(batch_ids)
        )
        channel_response = channel_request.execute()

        for ch in channel_response.get("items", []):
            stats = ch.get("statistics", {})
            snippet = ch.get("snippet", {})
            channel_stats.append({
                "channel_id": ch["id"],
                "channel_title": snippet.get("title"),
                "custom_url": f"https://www.youtube.com/channel/{ch['id']}",
                "subscribers": int(stats.get("subscriberCount", 0)),
                "views_total": int(stats.get("viewCount", 0)),
                "videos_total": int(stats.get("videoCount", 0)),
                "created_at": snippet.get("publishedAt"),
                "last_seen": date_str
            })

    # Объединяем данные каналов
    for ch in trending_channels:
        info = next((s for s in channel_stats if s["channel_id"] == ch["channel_id"]), None)
        if info:
            ch.update(info)
    # Обновляем историю для каждого канала
    for ch in trending_channels:
        update_channel_history(ch)


    # Загрузка старых данных, если есть
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    else:
        existing_data = []

    # Обновляем или добавляем новые каналы без дубликатов
    existing_map_channels = {c["channel_id"]: c for c in existing_data}
    for new_ch in trending_channels:
        existing_map_channels[new_ch["channel_id"]] = new_ch

    # Сохраняем обновлённый список каналов
    unique_channels = list(existing_map_channels.values())
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(unique_channels, f, ensure_ascii=False, indent=2)

    print(f"[{region}] Saved {len(unique_channels)} unique channels to {filename}\n")




def get_trend_type():
    hour = datetime.datetime.now().hour
    if 0 <= hour < 8:
        return "night"
    elif 8 <= hour < 14:
        return "morning"
    elif 14 <= hour < 20:
        return "day"
    else:
        return "evening"


def wait_until_next_run():
    now = datetime.datetime.now()
    next_hour = min([h for h in SCHEDULE_HOURS if h > now.hour], default=SCHEDULE_HOURS[0])
    next_run = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += datetime.timedelta(days=1)
    seconds_to_wait = (next_run - now).total_seconds()
    print(f"Next run at {next_run} ({seconds_to_wait/3600:.1f} hours)")
    time.sleep(seconds_to_wait)


def main():
    print("YouTube Trending Collector started.")
    while True:
        print("\n=== New collection cycle ===")
        total_channels = 0
        for region in REGIONS:
            collect_trending(region)
            filename = f"trending_channels_{region}.json"
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                total_channels += len(data)
        print(f"\n=== Cycle completed. Total unique channels across all regions: {total_channels} ===\n")
        wait_until_next_run()


if __name__ == "__main__":
    main()
