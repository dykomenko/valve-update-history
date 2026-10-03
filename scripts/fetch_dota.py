"""Download every Dota 2 gameplay patch since 2024 from the dota2.com patch-notes datafeed."""
import json, os, time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.environ.get("RAW_DIR", os.path.join(ROOT, "raw"))
H = {"User-Agent": "Mozilla/5.0"}
SINCE = 1704067200  # 2024-01-01

os.makedirs(RAW, exist_ok=True)
patches = requests.get("https://www.dota2.com/datafeed/patchnoteslist?language=english", headers=H, timeout=30).json()["patches"]
out = []
for p in patches:
    if p["patch_timestamp"] < SINCE:
        continue
    r = requests.get("https://www.dota2.com/datafeed/patchnotes",
                     params={"version": p["patch_number"], "language": "english"}, headers=H, timeout=40)
    out.append(r.json())
    time.sleep(0.3)
with open(os.path.join(RAW, "dota_patches.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)
print("saved", len(out), "patches")
