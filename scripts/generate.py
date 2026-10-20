"""Genera las tarjetas del perfil (dark_mode.svg / light_mode.svg).

Uso:  GITHUB_TOKEN=xxx python scripts/generate.py
Edita PROFILE para cambiar los textos; las stats y gráficos salen de la API de GitHub.
"""

import json
import os
import urllib.request
from collections import Counter, OrderedDict
from datetime import date, datetime
from html import escape
from pathlib import Path

USER = "pabloossandon88"
ROOT = Path(__file__).resolve().parent.parent

PROFILE = {
    "name": "Pablo Ossandón",
    "role": "Full Stack Developer · Applied AI · Remote 🌍",
    "tagline": "Building end-to-end web products and integrating AI (LLMs & agents) into real apps.",
    "stack": ["React", "TypeScript", "Node.js", "Supabase", "LLMs · AI Agents"],
}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Paleta categórica validada (orden fijo); "Other" siempre en gris.
THEMES = {
    "dark": {"bg": "#0d1117", "panel": "#161b22", "border": "#30363d", "text": "#e6edf3",
             "muted": "#8b949e", "grid": "#21262d", "accent": "#3987e5", "other": "#6e7681",
             "series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"]},
    "light": {"bg": "#ffffff", "panel": "#f6f8fa", "border": "#d0d7de", "text": "#1f2328",
              "muted": "#59636e", "grid": "#e4e8ec", "accent": "#2a78d6", "other": "#8c959f",
              "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]},
}

W, H = 985, 540
SANS = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',monospace"


def graphql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"},
    )
    with urllib.request.urlopen(req) as res:
        body = json.load(res)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch_stats():
    data = graphql(
        """query($login: String!) { user(login: $login) {
            createdAt
            followers { totalCount }
            contributionsCollection { contributionCalendar {
                totalContributions weeks { contributionDays { date contributionCount } }
            } }
            repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
                totalCount
                nodes { languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
                    edges { size node { name } }
                } }
            }
        } }""",
        {"login": USER},
    )["user"]

    created = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))

    languages = Counter()
    for repo in data["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            languages[edge["node"]["name"]] += edge["size"]

    calendar = data["contributionsCollection"]["contributionCalendar"]
    days = [day for week in calendar["weeks"] for day in week["contributionDays"]]
    months = OrderedDict()
    streak = longest = 0
    for day in days:
        key = day["date"][:7]
        months[key] = months.get(key, 0) + day["contributionCount"]
        streak = streak + 1 if day["contributionCount"] else 0
        longest = max(longest, streak)

    return {
        "created": created.date(),
        "repos": data["repositories"]["totalCount"],
        "followers": data["followers"]["totalCount"],
        "active_days": sum(1 for day in days if day["contributionCount"]),
        "longest_streak": longest,
        "contributions": calendar["totalContributions"],
        "languages": languages,
        "months": list(months.items())[-12:],
    }


def text(x, y, value, size=14, fill="text", weight=400, anchor="start", font=SANS):
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}" class="{fill}">{escape(str(value))}</text>')


def header(c):
    out = [
        text(40, 70, PROFILE["name"], 34, weight=700),
        text(40, 100, PROFILE["role"], 16, "accent", 600),
        text(40, 128, PROFILE["tagline"], 14, "muted"),
    ]
    # chips del stack, alineados a la derecha en una fila
    x = W - 40
    for name in reversed(PROFILE["stack"]):
        width = len(name) * 7.6 + 24
        x -= width
        out.append(f'<rect x="{x:.1f}" y="52" width="{width:.1f}" height="26" rx="13" class="chip"/>')
        out.append(text(round(x + width / 2, 1), 69, name, 12, "text", 500, "middle", MONO))
        x -= 8
    return out


def tiles(stats):
    years = (date.today() - stats["created"]).days // 365
    items = [
        (f"{stats['contributions']:,}", "contributions · last 12 months"),
        (stats["active_days"], "active days · last 12 months"),
        (f"{stats['longest_streak']} days", "longest streak · last 12 months"),
        (years, f"years on GitHub · since {stats['created'].year}"),
    ]
    gap, top, height = 16, 160, 84
    width = (W - 80 - gap * (len(items) - 1)) / len(items)
    out = []
    for i, (value, label) in enumerate(items):
        x = 40 + i * (width + gap)
        out.append(f'<rect x="{x:.1f}" y="{top}" width="{width:.1f}" height="{height}" rx="12" class="panel"/>')
        out.append(text(round(x + 20, 1), top + 44, value, 28, weight=700))
        out.append(text(round(x + 20, 1), top + 66, label, 12, "muted"))
    return out


def languages_panel(c, stats, x, y, w, h):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" class="panel"/>',
           text(x + 20, y + 34, "Top languages", 15, weight=600)]
    total = sum(stats["languages"].values()) or 1
    top = stats["languages"].most_common(5)
    rows = [(name, size, c["series"][i]) for i, (name, size) in enumerate(top)]
    rest = total - sum(size for _, size in top)
    if rest > 0:
        rows.append(("Other", rest, c["other"]))

    # barra apilada con 2px de separación entre segmentos
    bar_x, bar_y, bar_w = x + 20, y + 54, w - 40
    usable = bar_w - 2 * (len(rows) - 1)
    out.append(f'<clipPath id="lang-bar"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="12" rx="6"/></clipPath>')
    out.append('<g clip-path="url(#lang-bar)">')
    cursor = bar_x
    for _, size, color in rows:
        seg = usable * size / total
        out.append(f'<rect x="{cursor:.1f}" y="{bar_y}" width="{seg:.1f}" height="12" fill="{color}"/>')
        cursor += seg + 2
    out.append("</g>")

    # leyenda en dos columnas, con porcentaje visible
    col_w = (w - 40) / 2
    for i, (name, size, color) in enumerate(rows):
        lx = x + 20 + (i % 2) * col_w
        ly = y + 100 + (i // 2) * 34
        out.append(f'<circle cx="{lx + 6:.1f}" cy="{ly - 5}" r="6" fill="{color}"/>')
        out.append(text(round(lx + 20, 1), ly, name, 14))
        out.append(text(round(lx + col_w - 24, 1), ly, f"{size / total:.1%}", 13, "muted", anchor="end", font=MONO))
    return out


def activity_panel(c, stats, x, y, w, h):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" class="panel"/>',
           text(x + 20, y + 34, "Activity · last 12 months", 15, weight=600)]
    months = stats["months"]
    peak = max((v for _, v in months), default=0) or 1
    chart_x, chart_w = x + 20, w - 40
    base, chart_h = y + h - 40, h - 110
    slot = chart_w / len(months)
    bar_w = min(slot - 8, 22)

    for frac in (0.5, 1):
        gy = base - chart_h * frac
        out.append(f'<line x1="{chart_x}" x2="{chart_x + chart_w}" y1="{gy:.1f}" y2="{gy:.1f}" class="grid-line" stroke-dasharray="3 4"/>')
    out.append(f'<line x1="{chart_x}" x2="{chart_x + chart_w}" y1="{base}" y2="{base}" class="grid-line"/>')

    peak_index = max(range(len(months)), key=lambda i: months[i][1])
    for i, (key, value) in enumerate(months):
        bx = chart_x + i * slot + (slot - bar_w) / 2
        bh = max(chart_h * value / peak, 2 if value else 0)
        if bh:
            # barra con extremo superior redondeado y base recta
            r = min(4, bh / 2, bar_w / 2)
            top = base - bh
            out.append(
                f'<path d="M{bx:.1f},{base} V{top + r:.1f} Q{bx:.1f},{top:.1f} {bx + r:.1f},{top:.1f} '
                f'H{bx + bar_w - r:.1f} Q{bx + bar_w:.1f},{top:.1f} {bx + bar_w:.1f},{top + r:.1f} V{base} Z" '
                f'fill="{c["accent"]}"><title>{MONTHS[int(key[5:]) - 1]} {key[:4]}: {value}</title></path>')
        if i == peak_index and value:
            out.append(text(round(bx + bar_w / 2, 1), round(base - bh - 8, 1), value, 12, "text", 600, "middle", MONO))
        out.append(text(round(bx + bar_w / 2, 1), base + 20, MONTHS[int(key[5:]) - 1], 11, "muted", anchor="middle"))
    return out


def render(theme, stats):
    c = THEMES[theme]
    panel_w = (W - 80 - 16) / 2
    body = (header(c) + tiles(stats)
            + languages_panel(c, stats, 40, 260, round(panel_w, 1), 240)
            + activity_panel(c, stats, round(40 + panel_w + 16, 1), 260, round(panel_w, 1), 240))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<title>{escape(PROFILE['name'])} · GitHub</title>
<style>
.text {{fill: {c['text']};}}
.muted {{fill: {c['muted']};}}
.accent {{fill: {c['accent']};}}
.panel {{fill: {c['panel']}; stroke: {c['border']};}}
.chip {{fill: {c['panel']}; stroke: {c['border']};}}
.grid-line {{stroke: {c['grid']}; stroke-width: 1;}}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="16" fill="{c['bg']}" stroke="{c['border']}"/>
{chr(10).join(body)}
</svg>
"""


def main():
    stats = fetch_stats()
    for theme in THEMES:
        (ROOT / f"{theme}_mode.svg").write_text(render(theme, stats), encoding="utf-8")
    print({k: v for k, v in stats.items() if k != "languages"}, stats["languages"].most_common(6))


if __name__ == "__main__":
    main()
