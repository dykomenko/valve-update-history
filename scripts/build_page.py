"""Inline data/updates.json into src/index.template.html -> index.html (one self-contained file)."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = json.load(open(os.path.join(ROOT, "data", "updates.json"), encoding="utf-8"))
data.pop("events", None)                       # per-update log stays in data/updates.json, the page doesn't need it
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\/")
tpl = open(os.path.join(ROOT, "src", "index.template.html"), encoding="utf-8").read()
assert "/*__DATA__*/null" in tpl
open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(tpl.replace("/*__DATA__*/null", blob))
print("index.html", os.path.getsize(os.path.join(ROOT, "index.html")), "bytes")
