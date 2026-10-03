"""Turn the raw dumps in RAW_DIR into one compact, derived data/updates.json for the page.

Nothing from Valve's announcement texts is kept: only dates, titles, and per-update line counts.
"""
import collections, datetime as dt, json, os, re, statistics
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.environ.get("RAW_DIR", os.path.join(ROOT, "raw"))
OUT = os.path.join(ROOT, "data", "updates.json")

START = dt.date(2024, 1, 1)           # earliest month in the dataset
WINDOW_START = "2024-05"              # first public Deadlock changelog -> start of the common comparison window
GAMES = ["cs2", "dota2", "deadlock", "tf2"]
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date()
LAST_FULL_MONTH = (TODAY.replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")


# --------------------------------------------------------------------------- text -> entries
HEADER = re.compile(r"^(\[.*\]|=+|-{3,}|[A-Za-z0-9 &/'’\-]{2,40}:)$")
BULLETS = " \t-•*–·"


def classify(line):
    """Bucket one changelog entry. The same rules were applied in the browser to the Deadlock forum."""
    if re.search(r"\bfix(ed|es|ing)?\b", line, re.I):
        return "fix"
    if re.match(r"(added|adding|new|introduced|re-?added|enabled|unlocked|released)\b", line, re.I):
        return "new"
    if re.search(r"\d", line) or re.search(
        r"\b(increased|decreased|reduced|lowered|raised|buffed|nerfed|rebalanced|adjusted|tweaked|changed|improved|no longer|now)\b",
        line, re.I):
        return "tune"
    return "other"


def strip_tags(s):
    s = re.sub(r"\[/?[a-zA-Z0-9_]+(?:=[^\]]*)?\]", "", s)
    s = s.replace("\\[", "[").replace("\\]", "]")
    return re.sub(r"\s+", " ", s).strip()


def bb_entries(text):
    """Steam BBCode -> list of changelog entry strings (one per bullet / line, headers dropped)."""
    s = (text or "").replace("\r", "")
    s = re.sub(r"\[img\].*?\[/img\]", "", s, flags=re.S)
    if "[*]" in s:
        s = re.sub(r"\[/?(list|olist)\]|\[/\*\]", "\n", s)
        parts = [strip_tags(p) for p in s.split("[*]")[1:]]
        lines = [p for p in parts if p]
    else:
        s = re.sub(r"\[/?(p|list|olist|br|quote|h\d)\]|\[/\*\]", "\n", s)
        lines = []
        for raw in s.split("\n"):
            if re.match(r"^\s*\[b\].*\[/b\]\s*$", raw):  # a bold-only line is a section header
                continue
            lines.append(strip_tags(raw))
    entries = []
    for line in lines:
        line = line.lstrip(BULLETS).strip()
        if not line or HEADER.match(line) or line.endswith(":"):
            continue
        entries.append(line)
    return entries


def stats(entries):
    c = collections.Counter(classify(e) for e in entries)
    return {"entries": len(entries), "fix": c["fix"], "new": c["new"], "tune": c["tune"], "other": c["other"]}


def utc_date(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date()


def load_json(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------- events per game
def ev(date, title, source, st=None, stub=False):
    e = {"date": date.isoformat(), "titles": [title], "sources": [source], "stub": stub}
    e.update(st or {"entries": 0, "fix": 0, "new": 0, "tune": 0, "other": 0})
    return e


def merge_same_source(events):
    """Several posts from one source on one day -> one event, entries summed."""
    by = {}
    for e in events:
        k = e["date"]
        if k not in by:
            by[k] = e
        else:
            t = by[k]
            for f in ("entries", "fix", "new", "tune", "other"):
                t[f] += e[f]
            t["titles"] += e["titles"]
            t["stub"] = t["stub"] and e["stub"]
    return list(by.values())


def title_date(title):
    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", title)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return dt.date(y, a, b)
        except ValueError:
            return None
    return None


def cs2_events():
    out = []
    for i in load_json("news_cs2.json"):
        d = utc_date(i["date"])
        if d < START or "patchnotes" not in i.get("tags", []):
            continue
        if not re.search(r"update|release notes|patch", i["title"], re.I):
            continue  # tagged by mistake (e.g. Armory announcement)
        d = title_date(i["title"]) or d
        out.append(ev(d, i["title"], "steam-news", stats(bb_entries(i["contents"]))))
    return merge_same_source(out)


def tf2_events():
    out = []
    for i in load_json("news_tf2.json"):
        d = utc_date(i["date"])
        if d < START or "patchnotes" not in i.get("tags", []):
            continue
        out.append(ev(d, i["title"], "steam-news", stats(bb_entries(i["contents"]))))
    return merge_same_source(out)


def dota_note_texts(o, acc):
    if isinstance(o, dict):
        n = o.get("note")
        if isinstance(n, str):
            t = re.sub(r"<[^>]+>", "", n).strip()
            if t:
                acc.append(t)
        for v in o.values():
            if isinstance(v, (dict, list)):
                dota_note_texts(v, acc)
    elif isinstance(o, list):
        for v in o:
            dota_note_texts(v, acc)
    return acc


def dota_events():
    patches = load_json("dota_patches.json")
    events, by_version = [], {}
    for p in patches:
        d = utc_date(int(p["patch_timestamp"]))
        e = ev(d, f"Patch {p['patch_name']}", "dota2.com", stats(dota_note_texts(p, [])))
        events.append(e)
        by_version[p["patch_name"]] = e
    for i in load_json("news_dota2.json"):
        d = utc_date(i["date"])
        if d < START:
            continue
        m = re.search(r"\b(7\.\d{2}[a-z]?)\b", i["title"])
        tagged = "patchnotes" in i.get("tags", [])
        if m and m.group(1) in by_version:           # announcement / hotfix list of a datafeed patch -> same event
            st = stats(bb_entries(i["contents"]))
            tgt = by_version[m.group(1)]
            for f in ("entries", "fix", "new", "tune", "other"):
                tgt[f] += st[f]
            tgt["sources"].append("steam-news")
        elif tagged:
            events.append(ev(title_date(i["title"]) or d, i["title"], "steam-news", stats(bb_entries(i["contents"]))))
    return merge_same_source(events)


def deadlock_events():
    forum = []
    with open(os.path.join(ROOT, "data", "deadlock_forum.psv"), encoding="utf-8") as f:
        next(f)
        for line in f:
            title, ts, chars, ent, fix, new, tune, other, embed = line.rstrip("\n").split("|")
            d = title_date(title)
            forum.append((d, title, dict(entries=int(ent), fix=int(fix), new=int(new), tune=int(tune), other=int(other)),
                          bool(embed.strip())))
    ev_forum = merge_same_source([ev(d, f"Forum: {t}", "forum", st, stub=emb) for d, t, st, emb in forum])
    news = []
    for i in load_json("news_deadlock.json"):
        d = title_date(i["title"]) or utc_date(i["date"])
        if d < START:
            continue
        entries = bb_entries(i["contents"])
        stub = not re.search(r"update|patch|release notes", i["title"], re.I) and len(entries) < 40
        news.append(ev(d, i["title"], "steam-news", stats(entries), stub=stub))
    ev_news = merge_same_source(news)
    by = {e["date"]: e for e in ev_forum}
    for n in ev_news:
        f = by.get(n["date"])
        if not f:
            by[n["date"]] = n
            continue
        # same notes published twice (forum + Steam). A forum "stub" is only a link card to the Steam post,
        # otherwise keep whichever copy has the fuller text.
        best = n if (f["stub"] or n["entries"] > f["entries"]) else f
        merged = dict(best)
        merged["titles"] = f["titles"] + n["titles"]
        merged["sources"] = sorted(set(f["sources"] + n["sources"]))
        by[n["date"]] = merged
    return list(by.values())


def wiki_dates():
    """Dates of Deadlock updates listed on the community wiki (cross-check only)."""
    path = os.path.join(RAW, "deadlock_wiki_updates.html")
    if not os.path.exists(path):
        return []
    soup = BeautifulSoup(open(path, encoding="utf-8").read(), "lxml")
    out = []
    for tb in soup.find_all("table", class_="wikitable")[:3]:
        for tr in tb.find_all("tr")[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            try:
                d = dt.datetime.strptime(cells[0], "%B %d, %Y").date()
            except ValueError:
                continue
            if d > TODAY or "Upcoming" in cells[1]:
                continue
            out.append({"date": d.isoformat(), "summary": cells[1][:90], "undocumented": cells[1].startswith("(Undocumented)")})
    return out


# --------------------------------------------------------------------------- tiers / months
def tier(e):
    if e["stub"]:
        return "release"
    n = e["entries"]
    return "micro" if n < 10 else "small" if n < 30 else "medium" if n < 100 else "large"


def month_range(a, b):
    y, m = map(int, a.split("-"))
    ey, em = map(int, b.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


MONTHS = month_range("2024-01", TODAY.strftime("%Y-%m"))


def monthly(events):
    rows = {m: dict(updates=0, entries=0, fix=0, new=0, tune=0, other=0, micro=0, small=0, medium=0, large=0, release=0)
            for m in MONTHS}
    for e in events:
        m = e["date"][:7]
        if m not in rows:
            continue
        r = rows[m]
        r["updates"] += 1
        r[tier(e)] += 1
        if not e["stub"]:
            for f in ("entries", "fix", "new", "tune", "other"):
                r[f] += e[f]
    return rows


# --------------------------------------------------------------------------- GameTracking
def gametracking(game):
    days, commits = collections.defaultdict(int), collections.defaultdict(int)
    dayset = collections.defaultdict(set)
    first = None
    for line in open(os.path.join(RAW, f"gt_{game}.tsv"), encoding="utf-8"):
        ts, _, msg = line.rstrip("\n").partition("\t")
        m = re.match(r"(\d+) \| (\d+) files?", msg)
        if not m:
            continue                     # maintenance commits of the repo itself
        d = ts[:10]
        first = d if first is None or d < first else first
        commits[d[:7]] += 1
        dayset[d[:7]].add(d)
    return {"commits": {m: commits.get(m, 0) for m in MONTHS}, "days": {m: len(dayset.get(m, ())) for m in MONTHS}, "first": first}


# --------------------------------------------------------------------------- online
def steamcharts(app):
    soup = BeautifulSoup(open(os.path.join(RAW, f"steamcharts_{app}.html"), encoding="utf-8").read(), "lxml")
    out = {}
    for tr in soup.find("table", class_="common-table").find_all("tr")[1:]:
        c = [td.get_text(strip=True) for td in tr.find_all("td")]
        try:
            d = dt.datetime.strptime(c[0], "%B %Y")
        except ValueError:
            continue
        out[d.strftime("%Y-%m")] = {"avg": round(float(c[1])), "peak": int(c[4])}
    return {m: out[m] for m in MONTHS if m in out}


def live_snapshot():
    """Players right now. Deadlock is hidden from Steam's public endpoint, so it comes from steamdb.com's page."""
    import requests
    snap = {"at": NOW.strftime("%Y-%m-%d %H:%M UTC")}
    for g, app in (("cs2", 730), ("dota2", 570), ("tf2", 440)):
        try:
            r = requests.get("https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/",
                             params={"appid": app}, timeout=20)
            snap[g] = r.json()["response"]["player_count"]
        except Exception:
            snap[g] = None
    try:
        html = open(os.path.join(RAW, "steamdbcom_deadlock.html"), encoding="utf-8").read()
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
        snap["deadlock"] = int(re.search(r"Playing now ([\d,]+)", text).group(1).replace(",", ""))
    except Exception:
        snap["deadlock"] = None
    return snap


# --------------------------------------------------------------------------- summaries
def window_summary(events, months, gt_commits=None, gt_days=None):
    ms = set(months)
    es = sorted([e for e in events if e["date"][:7] in ms], key=lambda e: e["date"])
    n_months = len(months)
    sized = [e for e in es if not e["stub"]]
    dates = [dt.date.fromisoformat(e["date"]) for e in es]
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    tot = {f: sum(e[f] for e in sized) for f in ("entries", "fix", "new", "tune", "other")}
    s = {
        "months": n_months,
        "updates": len(es),
        "updates_per_month": round(len(es) / n_months, 2),
        "entries": tot["entries"],
        "entries_per_month": round(tot["entries"] / n_months, 1),
        "median_entries": statistics.median([e["entries"] for e in sized]) if sized else 0,
        "median_gap_days": statistics.median(gaps) if gaps else None,
        "max_gap_days": max(gaps) if gaps else None,
        "mix": {k: tot[k] for k in ("fix", "new", "tune", "other")},
        "tiers": dict(collections.Counter(tier(e) for e in es)),
    }
    if gt_commits is not None:
        s["gt_commits"] = sum(gt_commits[m] for m in months if gt_commits.get(m) is not None)
        s["gt_days"] = sum(gt_days[m] for m in months)
    return s


def main():
    builders = {"cs2": cs2_events, "dota2": dota_events, "deadlock": deadlock_events, "tf2": tf2_events}
    events = {g: sorted(builders[g](), key=lambda e: e["date"]) for g in GAMES}
    gt = {g: gametracking(g) for g in GAMES}
    ccu = {a: steamcharts(app) for a, app in (("cs2", 730), ("dota2", 570), ("tf2", 440))}

    full = month_range(WINDOW_START, LAST_FULL_MONTH)
    year = full[-12:]
    summaries = {}
    for g in GAMES:
        gtc = {m: (gt[g]["commits"][m] if (gt[g]["first"] and m >= gt[g]["first"][:7]) else None) for m in MONTHS}
        summaries[g] = {
            "window": window_summary(events[g], full, gtc, gt[g]["days"]),
            "year": window_summary(events[g], year, gtc, gt[g]["days"]),
        }
    last_update = {g: max(e["date"] for e in events[g]) for g in GAMES}

    # Deadlock: only verified monthly peaks exist (see data/deadlock_ccu.json). Unknown months stay unknown.
    with open(os.path.join(ROOT, "data", "deadlock_ccu.json"), encoding="utf-8") as f:
        dl_ccu = json.load(f)
    peaks = {g: {m: v["peak"] for m, v in ccu[g].items()} for g in ccu}
    peaks["deadlock"] = {p["month"]: p["peak"] for p in dl_ccu["monthly_peak"]}
    for g in GAMES:
        for key, months in (("window", full), ("year", year)):
            vals = [peaks[g][m] for m in months if m in peaks[g]]
            summaries[g][key]["peak_median"] = int(statistics.median(vals))
            summaries[g][key]["peak_months_known"] = len(vals)
            summaries[g][key]["peak_max"] = max(vals)
            per100k = summaries[g][key]["entries_per_month"] / (summaries[g][key]["peak_median"] / 100000)
            summaries[g][key]["entries_per_100k_peak"] = round(per100k, 2)
            summaries[g][key]["updates_per_100k_peak"] = round(summaries[g][key]["updates_per_month"] / (summaries[g][key]["peak_median"] / 100000), 3)

    # wiki-observed Deadlock updates that have no official post of their own (cross-check, dashed line on the page)
    ours = {e["date"] for e in events["deadlock"]}
    wiki = wiki_dates()
    wiki_only = collections.Counter(w["date"][:7] for w in wiki if w["date"] not in ours and w["date"] >= "2024-05-01")

    result = {
        "generated": NOW.strftime("%Y-%m-%d %H:%M UTC"),
        "months": MONTHS,
        "window": {"start": WINDOW_START, "end": LAST_FULL_MONTH, "months": full, "year": year},
        "events": {g: [{k: e[k] for k in ("date", "titles", "sources", "stub", "entries", "fix", "new", "tune", "other")}
                       | {"tier": tier(e)} for e in events[g]] for g in GAMES},
        "monthly": {g: monthly(events[g]) for g in GAMES},
        "gametracking": gt,
        "ccu_monthly": ccu,
        "summaries": summaries,
        "last_update": last_update,
        "deadlock_ccu": dl_ccu,
        "wiki": {
            "only_monthly": {m: wiki_only.get(m, 0) for m in MONTHS},
            "only_total": sum(wiki_only.values()),
            "only_undocumented": sum(1 for w in wiki if w["date"] not in ours and w["date"] >= "2024-05-01" and w["undocumented"]),
        },
        "live": live_snapshot(),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print("wrote", OUT, os.path.getsize(OUT), "bytes")
    for g in GAMES:
        w, y = summaries[g]["window"], summaries[g]["year"]
        print(f"{g:9s} window: {w['updates']:3d} upd ({w['updates_per_month']}/mo) entries={w['entries']:6d} med={w['median_entries']} gap_med={w['median_gap_days']} "
              f"| year: {y['updates']:3d} upd entries={y['entries']:6d} | gt window commits={w.get('gt_commits')} days={w.get('gt_days')}")


if __name__ == "__main__":
    main()
