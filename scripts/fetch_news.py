"""Download the full official-announcements feed from the Steam News API for each game."""
import json, os, sys, time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.environ.get("RAW_DIR", os.path.join(ROOT, "raw"))
GAMES = {"cs2": 730, "dota2": 570, "deadlock": 1422450, "tf2": 440}
URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"


def fetch_all(appid):
    items, end = [], None
    while True:
        params = {"appid": appid, "count": 100, "maxlength": 0, "feeds": "steam_community_announcements"}
        if end:
            params["enddate"] = end
        for attempt in range(4):
            try:
                r = requests.get(URL, params=params, timeout=40)
                r.raise_for_status()
                break
            except Exception as e:  # retry transient errors
                print("  retry", attempt, e, file=sys.stderr)
                time.sleep(2 + attempt * 2)
        else:
            raise RuntimeError("giving up")
        batch = r.json()["appnews"]["newsitems"]
        if not batch:
            break
        items.extend(batch)
        oldest = min(b["date"] for b in batch)
        print(f"  appid {appid}: +{len(batch)} (total {len(items)}), oldest {time.strftime('%Y-%m-%d', time.gmtime(oldest))}")
        if len(batch) < 100 and len({b['gid'] for b in batch}) == len(batch):
            # fewer than a full page: could still be the end, but verify with one more request
            pass
        end = oldest - 1
        time.sleep(0.4)
    seen, uniq = set(), []
    for it in items:
        if it["gid"] not in seen:
            seen.add(it["gid"])
            uniq.append(it)
    return uniq


if __name__ == "__main__":
    os.makedirs(RAW, exist_ok=True)
    for name, appid in GAMES.items():
        print(name)
        news = fetch_all(appid)
        with open(os.path.join(RAW, f"news_{name}.json"), "w", encoding="utf-8") as f:
            json.dump(news, f, ensure_ascii=False)
        print(f"  saved {len(news)} items")
