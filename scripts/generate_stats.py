"""Genera las gráficas SVG del perfil (ES/EN, tema claro/oscuro) con la API de GitHub.

Sin dependencias externas. Lo ejecuta a diario .github/workflows/stats.yml.
Uso local:  GITHUB_TOKEN=<token opcional> python scripts/generate_stats.py
"""
import json
import os
import re
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

USER = "RonaldBarberi"
OUT = Path(__file__).resolve().parents[1] / "assets" / "stats"
API = "https://api.github.com"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

THEMES = {
    "light": {"surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
              "grid": "#e1e0d9", "border": "#e1e0d9", "series": "#2a78d6"},
    "dark": {"surface": "#1a1a19", "ink": "#ffffff", "ink2": "#c3c2b7", "muted": "#898781",
             "grid": "#2c2c2a", "border": "#383835", "series": "#3987e5"},
}
TEXT = {
    "es": {"langs": "Lenguajes más usados", "langs_sub": "Por volumen de código en repos propios (sin notebooks)",
           "activity": "Commits por mes", "activity_sub": "Últimos 12 meses en repos propios",
           "repos": "Repos públicos", "commits": "Commits (12 meses)", "stars": "Estrellas",
           "languages": "Lenguajes", "updated": "Actualizado",
           "months": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]},
    "en": {"langs": "Top languages", "langs_sub": "By code volume in own repos (excluding notebooks)",
           "activity": "Commits per month", "activity_sub": "Last 12 months in own repos",
           "repos": "Public repos", "commits": "Commits (12 months)", "stars": "Stars",
           "languages": "Languages", "updated": "Updated",
           "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]},
}


# --------------------------------------------------------------------------- datos
def get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": USER})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        nxt = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get("Link", ""))
        return json.load(r), (nxt.group(1) if nxt else None)


def get_all(url):
    items = []
    while url:
        page, url = get(url)
        items.extend(page)
    return items


def collect():
    repos = [r for r in get_all(f"{API}/users/{USER}/repos?per_page=100&type=owner") if not r["fork"]]
    langs = Counter()
    for r in repos:
        data, _ = get(r["languages_url"])
        langs.update({k: v for k, v in data.items() if k != "Jupyter Notebook"})
    now = datetime.now(timezone.utc)
    y, m = divmod(now.year * 12 + now.month - 1 - 11, 12)   # primer día de hace 11 meses
    since = datetime(y, m + 1, 1, tzinfo=timezone.utc)
    months = Counter()
    for r in repos:
        if r["size"] == 0:
            continue
        url = f"{API}/repos/{USER}/{r['name']}/commits?author={USER}&since={since:%Y-%m-%dT%H:%M:%SZ}&per_page=100"
        for c in get_all(url):
            months[c["commit"]["author"]["date"][:7]] += 1
    keys = []
    d = since
    for _ in range(12):
        keys.append(d.strftime("%Y-%m"))
        d = (d + timedelta(days=32)).replace(day=1)
    return {
        "repos": len(repos),
        "stars": sum(r["stargazers_count"] for r in repos),
        "langs": langs,
        "months": [(k, months.get(k, 0)) for k in keys],
        "updated": now.strftime("%Y-%m-%d"),
    }


# --------------------------------------------------------------------------- SVG
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def frame(w, h, t, body, title, sub):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{esc(title)}" font-family="{FONT}">'
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" fill="{t["surface"]}" stroke="{t["border"]}"/>'
            f'<text x="24" y="34" font-size="15" font-weight="600" fill="{t["ink"]}">{esc(title)}</text>'
            f'<text x="24" y="54" font-size="11.5" fill="{t["ink2"]}">{esc(sub)}</text>{body}</svg>')


def hbar_path(x, y, w, h, r=4):
    """Barra horizontal anclada a la izquierda con extremo de datos redondeado."""
    r = min(r, w, h / 2)
    return (f"M{x},{y}H{x + w - r}Q{x + w},{y} {x + w},{y + r}V{y + h - r}"
            f"Q{x + w},{y + h} {x + w - r},{y + h}H{x}Z")


def vbar_path(x, base, w, h, r=4):
    """Barra vertical anclada a la línea base con extremo superior redondeado."""
    if h <= 0:
        return ""
    r = min(r, h, w / 2)
    top = base - h
    return (f"M{x},{base}V{top + r}Q{x},{top} {x + r},{top}H{x + w - r}"
            f"Q{x + w},{top} {x + w},{top + r}V{base}Z")


def svg_langs(data, t, tx, top=6):
    total = sum(data["langs"].values()) or 1
    items = data["langs"].most_common(top)
    rest = total - sum(v for _, v in items)
    if rest > 0:
        items.append(("Otros" if tx is TEXT["es"] else "Other", rest))
    w, row, x0, bw = 460, 30, 130, 250
    h = 80 + row * len(items)
    vmax = max(v for _, v in items)
    body = ""
    for i, (name, v) in enumerate(items):
        y = 76 + i * row
        pct = v / total
        body += (f'<text x="{x0 - 10}" y="{y + 13}" font-size="12" fill="{t["ink2"]}" text-anchor="end">{esc(name)}</text>'
                 f'<path d="{hbar_path(x0, y + 2, max(bw * v / vmax, 2), 16)}" fill="{t["series"]}"/>'
                 f'<text x="{x0 + bw * v / vmax + 8}" y="{y + 14}" font-size="12" fill="{t["ink"]}">{pct:.1%}</text>')
    return frame(w, h, t, body, tx["langs"], tx["langs_sub"])


def svg_activity(data, t, tx):
    w, h = 460, 230
    x0, base, plot_w, plot_h = 44, 190, 392, 110
    vals = [v for _, v in data["months"]]
    vmax = max(vals + [1])
    step = 10 ** max(len(str(vmax)) - 1, 0)
    ymax = ((vmax // step) + 1) * step
    body = ""
    for f in (0, 0.5, 1):
        y = base - plot_h * f
        body += (f'<line x1="{x0}" x2="{x0 + plot_w}" y1="{y}" y2="{y}" stroke="{t["grid"] if f else t["border"]}"/>'
                 f'<text x="{x0 - 8}" y="{y + 4}" font-size="10.5" fill="{t["muted"]}" text-anchor="end">{int(ymax * f)}</text>')
    slot = plot_w / len(vals)
    bw = slot * 0.62
    peak = vals.index(vmax) if vmax else -1
    for i, (k, v) in enumerate(data["months"]):
        x = x0 + i * slot + (slot - bw) / 2
        body += f'<path d="{vbar_path(x, base - 1, bw, plot_h * v / ymax)}" fill="{t["series"]}"/>'
        m = tx["months"][int(k[5:]) - 1]
        body += f'<text x="{x + bw / 2}" y="{base + 16}" font-size="10.5" fill="{t["ink2"]}" text-anchor="middle">{m}</text>'
        if i == peak or i == len(vals) - 1:
            body += (f'<text x="{x + bw / 2}" y="{base - plot_h * v / ymax - 6}" font-size="11" '
                     f'fill="{t["ink"]}" text-anchor="middle">{v}</text>')
    return frame(w, h, t, body, tx["activity"], tx["activity_sub"])


def svg_overview(data, t, tx):
    tiles = [(data["repos"], tx["repos"]), (sum(v for _, v in data["months"]), tx["commits"]),
             (data["stars"], tx["stars"]), (len(data["langs"]), tx["languages"])]
    w, h = 932, 110
    tw = (w - 48 - 3 * 16) / 4
    body = ""
    for i, (v, label) in enumerate(tiles):
        x = 24 + i * (tw + 16)
        body += (f'<rect x="{x}" y="20" width="{tw}" height="70" rx="8" fill="none" stroke="{t["border"]}"/>'
                 f'<text x="{x + 16}" y="58" font-size="26" font-weight="600" fill="{t["ink"]}">{v:,}</text>'
                 f'<text x="{x + 16}" y="78" font-size="12" fill="{t["ink2"]}">{esc(label)}</text>')
    body += (f'<text x="{w - 24}" y="104" font-size="10" fill="{t["muted"]}" text-anchor="end">'
             f'{tx["updated"]}: {data["updated"]}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h + 6}" viewBox="0 0 {w} {h + 6}" '
            f'role="img" aria-label="GitHub stats" font-family="{FONT}">'
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h + 5}" rx="10" fill="{t["surface"]}" stroke="{t["border"]}"/>'
            f'{body}</svg>')


def main():
    data = collect()
    OUT.mkdir(parents=True, exist_ok=True)
    for lang, tx in TEXT.items():
        for theme, t in THEMES.items():
            for name, fn in (("langs", svg_langs), ("activity", svg_activity), ("overview", svg_overview)):
                (OUT / f"{name}-{lang}-{theme}.svg").write_text(fn(data, t, tx), encoding="utf-8")
    print(json.dumps({k: (dict(v.most_common(8)) if k == "langs" else v) for k, v in data.items()}, indent=1))


if __name__ == "__main__":
    main()
