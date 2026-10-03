"""Download the online-player sources: SteamCharts monthly tables, steamdb.com's Deadlock page, the Deadlock wiki update list."""
import os, time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.environ.get("RAW_DIR", os.path.join(ROOT, "raw"))
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

os.makedirs(RAW, exist_ok=True)
targets = {f"steamcharts_{app}.html": f"https://steamcharts.com/app/{app}" for app in (730, 570, 440)}
targets["steamdbcom_deadlock.html"] = "https://steamdb.com/en/tools/steam-charts/1422450-deadlock"
targets["deadlock_wiki_updates.html"] = "https://deadlock.wiki/Updates"
for name, url in targets.items():
    r = requests.get(url, headers=H, timeout=40)
    r.raise_for_status()
    with open(os.path.join(RAW, name), "w", encoding="utf-8") as f:
        f.write(r.text)
    print("saved", name, len(r.text))
    time.sleep(1)
