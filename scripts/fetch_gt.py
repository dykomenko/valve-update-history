"""Download commit metadata (date, build id, files changed) from SteamDatabase/GameTracking-* since 2024-01-01."""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.environ.get("RAW_DIR", os.path.join(ROOT, "raw"))
REPOS = {"deadlock": "GameTracking-Deadlock", "cs2": "GameTracking-CS2", "dota2": "GameTracking-Dota2", "tf2": "GameTracking-TF2"}
JQ = '.[] | [.commit.author.date, (.commit.message | split("\\n")[0] | .[0:60])] | @tsv'

for game, repo in REPOS.items():
    out = os.path.join(RAW, f"gt_{game}.tsv")
    print("fetching", repo, flush=True)
    cmd = ["gh", "api", "--paginate", f"repos/SteamDatabase/{repo}/commits?since=2024-01-01T00:00:00Z&per_page=100", "--jq", JQ]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        print("  FAILED", p.stderr[:300], file=sys.stderr)
        continue
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(p.stdout)
    print("  rows:", p.stdout.count("\n"), flush=True)
