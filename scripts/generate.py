"""Genera las tarjetas del perfil (dark_mode.svg / light_mode.svg).

Uso:  GITHUB_TOKEN=xxx python scripts/generate.py
Edita PROFILE para cambiar los textos; las stats y gráficos salen de la API de GitHub.
Con un token personal (secret STATS_TOKEN en Actions) los lenguajes incluyen repos privados.
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
    "role": "Full Stack Developer · Web · Mobile · Applied AI · Remote 🌍",
    "tagline": "Building web, mobile and backend apps end-to-end, and integrating AI (LLMs & agents) into real products.",
    "stack": ["TypeScript", "React", "Node.js", "Python", "PostgreSQL", "Supabase",
              "iOS · Android", "Docker", "LLMs · AI Agents"],
}

# Lenguajes de marcado/estilos/scripts de build que no aportan al perfil.
IGNORED_LANGUAGES = {"HTML", "CSS", "SCSS", "Batchfile"}
LANGUAGE_NAMES = {"PLpgSQL": "SQL (PL/pgSQL)", "Dockerfile": "Docker"}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

THEMES = {
    "dark": {"bg": "#0d1117", "panel": "#161b22", "border": "#30363d", "text": "#e6edf3",
             "muted": "#8b949e", "grid": "#21262d", "accent": "#3987e5", "track": "#21262d"},
    "light": {"bg": "#ffffff", "panel": "#f6f8fa", "border": "#d0d7de", "text": "#1f2328",
              "muted": "#59636e", "grid": "#e4e8ec", "accent": "#2a78d6", "track": "#e4e8ec"},
}

W, H = 985, 564
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
    repo_fields = """nodes { nameWithOwner isFork languages(first: 15) { nodes { name } } }"""
    data = graphql(
        f"""query($login: String!) {{ user(login: $login) {{
            createdAt
            contributionsCollection {{ contributionCalendar {{
                totalContributions weeks {{ contributionDays {{ date contributionCount }} }}
            }} }}
            repositories(ownerAffiliations: OWNER, first: 100) {{ {repo_fields} }}
            repositoriesContributedTo(first: 100, includeUserRepositories: true,
                contributionTypes: [COMMIT, PULL_REQUEST]) {{ {repo_fields} }}
        }} }}""",
        {"login": USER},
    )["user"]

    created = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
    yearly = {}
    for year in range(created.year, date.today().year + 1):
        yearly[year] = graphql(
            """query($login: String!, $from: DateTime!, $to: DateTime!) { user(login: $login) {
                contributionsCollection(from: $from, to: $to) { contributionCalendar { totalContributions } }
            } }""",
            {"login": USER, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"},
        )["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]

    # cada lenguaje cuenta una vez por repo: muestra amplitud, no bytes
    repos = {r["nameWithOwner"]: r for key in ("repositories", "repositoriesContributedTo")
             for r in data[key]["nodes"] if not r["isFork"]}
    languages = Counter()
    for repo in repos.values():
        for lang in repo["languages"]["nodes"]:
            if lang["name"] not in IGNORED_LANGUAGES:
                languages[LANGUAGE_NAMES.get(lang["name"], lang["name"])] += 1

    calendar = data["contributionsCollection"]["contributionCalendar"]
    months = OrderedDict()
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            key = day["date"][:7]
            months[key] = months.get(key, 0) + day["contributionCount"]

    return {
        "created": created.date(),
        "all_time": sum(yearly.values()),
        "best_year": max(yearly, key=yearly.get),
        "yearly": yearly,
        "contributions": calendar["totalContributions"],
        "repos": len(repos),
        "languages": languages,
        "months": list(months.items())[-12:],
    }


def text(x, y, value, size=14, fill="text", weight=400, anchor="start", font=SANS):
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}" class="{fill}">{escape(str(value))}</text>')


def header(stats):
    years = (date.today() - stats["created"]).days // 365
    out = [
        text(40, 70, PROFILE["name"], 34, weight=700),
        text(W - 40, 62, f"On GitHub since {stats['created'].year}", 13, "muted", 600, "end", MONO),
        text(W - 40, 82, f"{years} years on GitHub", 12, "muted", anchor="end", font=MONO),
        text(40, 100, PROFILE["role"], 16, "accent", 600),
        text(40, 128, PROFILE["tagline"], 14, "muted"),
    ]
    # chips del stack, de izquierda a derecha con salto de línea
    x, y = 40, 148
    for name in PROFILE["stack"]:
        width = len(name) * 7.6 + 24
        if x + width > W - 40:
            x, y = 40, y + 34
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{width:.1f}" height="26" rx="13" class="chip"/>')
        out.append(text(round(x + width / 2, 1), y + 17, name, 12, "text", 500, "middle", MONO))
        x += width + 8
    return out


def tiles(stats, top):
    items = [
        (f"{stats['all_time']:,}", "total contributions · all time"),
        (f"{stats['contributions']:,}", "contributions · last 12 months"),
        (f"{stats['yearly'][stats['best_year']]:,}", f"contributions in {stats['best_year']} · best year"),
        (stats["repos"], "repos contributed to"),
    ]
    gap, height = 16, 84
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
           text(x + 20, y + 34, "Languages · used across repos", 15, weight=600)]
    rows = stats["languages"].most_common(7)
    peak = rows[0][1] if rows else 1
    label_w, count_w = 130, 76
    bar_x = x + 20 + label_w
    bar_w = w - 40 - label_w - count_w
    for i, (name, count) in enumerate(rows):
        ry = y + 66 + i * 23
        out.append(text(x + 20, ry + 4, name, 13))
        out.append(f'<rect x="{bar_x}" y="{ry - 5}" width="{bar_w}" height="8" rx="4" fill="{c["track"]}"/>')
        out.append(f'<rect x="{bar_x}" y="{ry - 5}" width="{max(bar_w * count / peak, 8):.1f}" height="8" rx="4" '
                   f'fill="{c["accent"]}"/>')
        unit = "repo" if count == 1 else "repos"
        out.append(text(round(x + w - 20, 1), ry + 4, f"{count} {unit}", 12, "muted", anchor="end", font=MONO))
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
    panel_w = round((W - 80 - 16) / 2, 1)
    body = (header(stats) + tiles(stats, 200)
            + languages_panel(c, stats, 40, 300, panel_w, 240)
            + activity_panel(c, stats, round(40 + panel_w + 16, 1), 300, panel_w, 240))
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
    print({k: v for k, v in stats.items() if k not in ("languages", "yearly")}, stats["languages"].most_common(10))


if __name__ == "__main__":
    main()
