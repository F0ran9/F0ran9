import json
import os
import time
import urllib.request

TOKEN = os.environ["GITHUB_TOKEN"]
LOGIN = os.environ.get("LOGIN") or os.environ.get("GITHUB_REPOSITORY_OWNER", "F0ran9")

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER) {
      nodes { isPrivate stargazerCount forkCount }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def run_query(retries=3):
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                "https://api.github.com/graphql",
                data=body,
                headers={
                    "Authorization": f"bearer {TOKEN}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = json.load(r)
            if "errors" in payload:
                raise RuntimeError(payload["errors"])
            return payload["data"]["user"]
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(10)
    raise last_err


def fetch_calendar():
    try:
        u = run_query()
    except Exception as e:
        print(f"GraphQL failed, rendering stats without calendar: {e}")
        return None, None, None
    cal = u["contributionsCollection"]["contributionCalendar"]
    weeks = [w["contributionDays"] for w in cal["weeks"]][-26:]
    days = [d for w in [w["contributionDays"] for w in cal["weeks"]] for d in w]
    return weeks, cal["totalContributions"], days


def streaks(days):
    today = days[-1]["date"]
    cur = 0
    for d in reversed(days):
        if d["contributionCount"] > 0:
            cur += 1
        elif d["date"] == today:
            continue
        else:
            break
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    return cur, longest


def cell_color(n):
    if n <= 0:
        return "#161B22"
    if n <= 3:
        return "#003822"
    if n <= 6:
        return "#006644"
    if n <= 9:
        return "#00AA66"
    return "#00FF88"


def fetch_rest():
    req = urllib.request.Request(
        f"https://api.github.com/users/{LOGIN}",
        headers={"Authorization": f"bearer {TOKEN}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    weeks, total, days = fetch_calendar()
    rest = fetch_rest()
    followers = rest["followers"]

    cur = longest = 0
    if days:
        cur, longest = streaks(days)

    req = urllib.request.Request(
        f"https://api.github.com/users/{LOGIN}/repos?per_page=100&sort=updated",
        headers={"Authorization": f"bearer {TOKEN}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        repos = json.load(r)
    stars = sum(r["stargazers_count"] for r in repos if not r["private"])

    stats = [
        ("CONTRIBUTIONS / 1Y", f"{total:,}" if total is not None else "—"),
        ("CURRENT STREAK", f"{cur}d" if days else "—"),
        ("LONGEST STREAK", f"{longest}d" if days else "—"),
        ("STARS EARNED", f"{stars:,}"),
        ("FOLLOWERS", f"{followers:,}"),
    ]

    has_grid = bool(weeks)
    height = 330 if has_grid else 150
    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="920" height="{height}" viewBox="0 0 920 {height}" '
        f'font-family="Consolas, \'JetBrains Mono\', monospace">'
    )
    parts.append(f'<rect width="920" height="{height}" rx="16" fill="#0D1117" stroke="#30363D"/>')
    parts.append(
        f'<text x="36" y="42" font-size="19" font-weight="700" letter-spacing="2" fill="#00FF88">'
        f"{LOGIN.upper()} · GITHUB STATS</text>"
    )
    parts.append(
        '<text x="884" y="42" text-anchor="end" font-size="11" fill="#8B949E">AUTO-REFRESHED DAILY</text>'
    )

    tx = 36
    for label, value in stats:
        parts.append(f'<text x="{tx}" y="92" font-size="27" font-weight="700" fill="#E6EDF3">{value}</text>')
        parts.append(f'<text x="{tx}" y="114" font-size="11" letter-spacing="1" fill="#8B949E">{label}</text>')
        tx += 172

    if has_grid:
        x0, y0, cell, gap = 36, 176, 12, 3
        parts.append(
            f'<text x="{x0}" y="160" font-size="11" letter-spacing="1" fill="#8B949E">CONTRIBUTIONS · LAST 26 WEEKS</text>'
        )
        for ci, week in enumerate(weeks):
            for ri, day in enumerate(week):
                x = x0 + ci * (cell + gap)
                y = y0 + ri * (cell + gap)
                c = cell_color(day["contributionCount"])
                stroke = ' stroke="#1F2730"' if c == "#161B22" else ""
                parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{c}"{stroke}/>')

        legend_x = x0 + 26 * (cell + gap) - 130
        parts.append(f'<text x="{legend_x}" y="292" font-size="10" fill="#8B949E">LESS</text>')
        lx = legend_x + 34
        for c in ["#161B22", "#003822", "#006644", "#00AA66", "#00FF88"]:
            parts.append(f'<rect x="{lx}" y="284" width="10" height="10" rx="2" fill="{c}" stroke="#1F2730"/>')
            lx += 15
        parts.append(f'<text x="{lx + 2}" y="292" font-size="10" fill="#8B949E">MORE</text>')
        first = weeks[0][0]["date"]
        last = weeks[-1][-1]["date"]
        parts.append(f'<text x="36" y="312" font-size="10" fill="#484F58">{first} → {last}</text>')
        parts.append(
            '<text x="884" y="312" text-anchor="end" font-size="10" fill="#484F58">Hack. Automate. Repeat. ⚡</text>'
        )
    else:
        parts.append(
            '<text x="884" y="130" text-anchor="end" font-size="10" fill="#484F58">Hack. Automate. Repeat. ⚡</text>'
        )
    parts.append("</svg>")

    os.makedirs("dist", exist_ok=True)
    with open("dist/stats.svg", "w", encoding="utf-8") as f:
        f.write("".join(parts))
    print(f"stats.svg written: total={total} cur={cur} longest={longest} stars={stars} followers={followers} grid={has_grid}")


if __name__ == "__main__":
    main()
