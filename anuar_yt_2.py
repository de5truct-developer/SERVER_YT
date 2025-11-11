from googleapiclient.discovery import build
import json
import os
import random
import time

def get_api_key():
    with open("api_keys.txt", "r", encoding="utf-8") as f:
        keys = [k.strip() for k in f.read().split(",") if k.strip()]
    return random.choice(keys)

def fetch_channel_data(youtube, channel_ids):
    result = []
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i:i+50]
        try:
            request = youtube.channels().list(
                part="snippet,statistics",
                id=",".join(batch)
            )
            response = request.execute()
            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                data = {
                    "channel_id": item["id"],
                    "title": snippet.get("title"),
                    "description": snippet.get("description"),
                    "published_at": snippet.get("publishedAt"),
                    "channel_url": f"https://www.youtube.com/channel/{item['id']}",
                    "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url"),
                    "subscribers": int(stats.get("subscriberCount", 0)),
                    "views": int(stats.get("viewCount", 0)),
                    "videos": int(stats.get("videoCount", 0)),
                }
                result.append(data)
        except Exception as e:
            print(f"Ошибка при запросе каналов: {e}")
            time.sleep(2)
            continue
    return result

def process_files():
    api_key = get_api_key()
    youtube = build("youtube", "v3", developerKey=api_key)

    for filename in os.listdir():
        if filename.startswith("trending_channels_") and filename.endswith(".json") and not filename.endswith("_filtered.json"):
            print(f"\nОбработка файла: {filename}")
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)

            filtered_name = filename.replace(".json", "_filtered.json")

            if os.path.exists(filtered_name):
                with open(filtered_name, "r", encoding="utf-8") as f:
                    filtered_data = json.load(f)
            else:
                filtered_data = []

            existing_ids = {c["channel_id"] for c in filtered_data if "channel_id" in c}
            new_channel_ids = [c["channel_id"] for c in data if c["channel_id"] not in existing_ids]

            print(f"Новых каналов для добавления: {len(new_channel_ids)}")

            if not new_channel_ids:
                print("Новых каналов нет, пропуск файла.")
                continue

            new_data = fetch_channel_data(youtube, new_channel_ids)
            filtered_data.extend(new_data)

            with open(filtered_name, "w", encoding="utf-8") as f:
                json.dump(filtered_data, f, ensure_ascii=False, indent=2)

            print(f"Файл обновлён: {filtered_name} (всего {len(filtered_data)} каналов)")

if __name__ == "__main__":
    process_files()
