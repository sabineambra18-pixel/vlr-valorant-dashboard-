import os, json, argparse
from collections import defaultdict
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt

# ======= Your data folder (all *_veto.json live here) =======
DATA_DIR = r"C:\Users\gluka\Documents\vlr-veto"

# ======= Default team list you gave me =======
DEFAULT_TEAMS = [
    "Motiv Esports",
    "FULL SENSE",
    "RIDDLE ORDER",
    "NAOS",
    "SLT Seongnam",
    "E-KING",
    "Team NKT",
    "BOOM Esports",
    "Nongshim RedForce",
    "Velocity Gaming",
]

# ======= Country mapping (edit as you like) =======
# NOTE: Updated as requested — RIDDLE ORDER = Japan, E-KING = Australia
TEAM_REGIONS = {
    "Motiv Esports": "Singapore",
    "FULL SENSE": "Thailand",
    "RIDDLE ORDER": "Japan",        # <-- fixed
    "NAOS": "Philippines",
    "SLT Seongnam": "South Korea",
    "E-KING": "Australia",          # <-- fixed
    "Team NKT": "Thailand",
    "BOOM Esports": "Indonesia",
    "Nongshim RedForce": "South Korea",
    "Velocity Gaming": "India",
}

# ============ Helpers ============

def norm(s):  # case-insensitive keying
    return (s or "").strip().lower()

def load_all_matches(path):
    data = []
    for fn in os.listdir(path):
        if fn.endswith("_veto.json"):
            fp = os.path.join(path, fn)
            with open(fp, "r", encoding="utf-8") as f:
                obj = json.load(f)
            # Attach file mtime as last-resort date
            try:
                obj["_file_mtime"] = datetime.fromtimestamp(os.path.getmtime(fp))
            except Exception:
                obj["_file_mtime"] = None
            data.append(obj)
    return data

def load_regions_from_csv(csv_path):
    """Optional CSV with two columns: Team,Region (we use full country names)."""
    if not os.path.exists(csv_path):
        return {}
    df = pd.read_csv(csv_path)
    out = {}
    for _, row in df.iterrows():
        team = str(row.get("Team", "")).strip()
        reg = str(row.get("Region", "")).strip()
        if team:
            out[team] = reg
    return out

def load_regions_from_flag(flag_str):
    """
    --regions "Team A=CountryA,Team B=CountryB"
    """
    mapping = {}
    if not flag_str:
        return mapping
    parts = [p.strip() for p in flag_str.split(",") if p.strip()]
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            mapping[k.strip()] = v.strip()
    return mapping

def compose_region_map(inline_dict, csv_map, flag_map):
    """
    Merge precedence: CLI flag > CSV file > Inline dict
    """
    merged = dict(inline_dict or {})
    for k, v in csv_map.items():
        if v and (k not in merged or not merged[k]):
            merged[k] = v
    for k, v in flag_map.items():
        if v:
            merged[k] = v
    return merged

def display_name(team, region_map):
    reg = (region_map.get(team) or "").strip()
    return f"{team} ({reg})" if reg else team

# ---- Date parsing helpers ----

DATE_FORMATS = [
    "%Y-%m-%d",
    "%b %d, %Y",
    "%B %d, %Y",
    "%Y/%m/%d",
    "%d %b %Y",
    "%d %B %Y",
]

def parse_date_any(s):
    """
    Try several formats; return datetime or None.
    """
    if not s:
        return None
    s = str(s).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    # ISO-ish fallback
    try:
        return datetime.fromisoformat(s.replace("Z","").replace("T"," "))
    except Exception:
        return None

def match_date(match_obj):
    """
    Pull a usable datetime from the JSON if present. Try:
      match["date"] OR match["result"]["date"] OR file mtime
    """
    # Top-level date we wrote in scraper (if present)
    cand = match_obj.get("date")
    dt = parse_date_any(cand)
    if dt:
        return dt

    # Sometimes date could be tucked in result
    cand = (match_obj.get("result") or {}).get("date")
    dt = parse_date_any(cand)
    if dt:
        return dt

    # Last resort: file mtime attached in loader
    return match_obj.get("_file_mtime")

def short_date(dt):
    return dt.strftime("%b %d, %Y") if isinstance(dt, datetime) else "Unknown"

# ============ Aggregation ============

def summarize_per_team(matches, team_filter=None):
    """
    Returns dict: team -> map -> stats for that team.
    team_filter: set of lowercase team names or None (means include all).
    """
    per_team = defaultdict(lambda: defaultdict(lambda: {
        "bans": 0,
        "picks": 0,
        "wins": 0,
        "losses": 0,
        "pistol_wins": 0,
        "pistol_rounds": 0,  # 2 per map for that team (pistols in rounds 1 & 13)
        "agents": defaultdict(int),
        # store structured results so we can sort by date
        "results_struct": []  # dicts: {"W":True/False,"score":"13-8","opp":"ABC","date":datetime}
    }))

    for match in matches:
        left = (match.get("teams") or {}).get("left")
        right = (match.get("teams") or {}).get("right")
        if not left or not right:
            continue
        left_n, right_n = norm(left), norm(right)
        dt = match_date(match)

        # Which teams in this match should we include?
        teams_in_match = []
        if team_filter is None or left_n in team_filter:
            teams_in_match.append(("left", left))
        if team_filter is None or right_n in team_filter:
            teams_in_match.append(("right", right))
        if not teams_in_match:
            continue

        # Veto events (count for the team performing the action)
        for ev in (match.get("veto") or {}).get("events", []):
            ev_team = ev.get("team")
            ev_map = ev.get("map")
            if not ev_team or not ev_map:
                continue
            ev_team_n = norm(ev_team)
            if team_filter is not None and ev_team_n not in team_filter:
                continue
            bucket = per_team[ev_team][ev_map]
            if ev["type"] == "ban":
                bucket["bans"] += 1
            elif ev["type"] == "pick":
                bucket["picks"] += 1

        # Played maps — attribute to each filtered side present in the match
        for row in match.get("played", []):
            m = row.get("map")
            ls, rs = row.get("left_score"), row.get("right_score")
            pist = row.get("pistols", {}) or {}
            if not m or ls is None or rs is None:
                continue

            for side, team_name in teams_in_match:
                opp_name = right if side == "left" else left
                team_bucket = per_team[team_name][m]

                team_score = ls if side == "left" else rs
                opp_score = rs if side == "left" else ls

                # Store structured result w/date for later sorting
                W = team_score > opp_score
                team_bucket["results_struct"].append({
                    "W": W,
                    "score": f"{team_score}-{opp_score}",
                    "opp": opp_name,
                    "date": dt
                })

                if W:
                    team_bucket["wins"] += 1
                elif opp_score > team_score:
                    team_bucket["losses"] += 1

                # Pistols: 2 per team per map (rounds 1 & 13)
                team_pist_wins = pist.get("left", 0) if side == "left" else pist.get("right", 0)
                team_bucket["pistol_wins"] += int(team_pist_wins)
                team_bucket["pistol_rounds"] += 2

                # Agents used by this team on this map
                agents_list = row.get("left_agents", []) if side == "left" else row.get("right_agents", [])
                for a in agents_list or []:
                    team_bucket["agents"][a] += 1

    return per_team

def team_maps_to_df(team_name, maps_dict):
    rows = []
    for m, s in maps_dict.items():
        pistol_wr = s["pistol_wins"] / s["pistol_rounds"] if s["pistol_rounds"] else 0.0

        # Sort results by date desc for the preview string
        rs = sorted(s["results_struct"], key=lambda r: (r["date"] or datetime.min), reverse=True)
        pretty_results = " | ".join([
            f"{'W' if r['W'] else 'L'} {r['score']} vs {r['opp']} ({short_date(r['date'])})"
            for r in rs
        ])

        top_agents = ", ".join([
            f"{a}×{c}" for a, c in sorted(s["agents"].items(), key=lambda x: x[1], reverse=True)[:5]
        ])

        rows.append({
            "Map": m,
            "Bans": s["bans"],
            "Picks": s["picks"],
            "Wins": s["wins"],
            "Losses": s["losses"],
            "PistolWinRate": round(pistol_wr, 3),
            "Results": pretty_results,
            "TopAgents": top_agents
        })
    if not rows:
        return pd.DataFrame(columns=["Map","Bans","Picks","Wins","Losses","PistolWinRate","Results","TopAgents"])
    df = pd.DataFrame(rows).sort_values(["Picks","Wins","Map"], ascending=[False, False, True])
    return df

def plot_team(team_disp, df_team):
    if df_team.empty:
        print(f"\n[{team_disp}] No data.")
        return

    # Picks vs Bans
    plt.figure(figsize=(10,6))
    plt.bar(df_team["Map"], df_team["Picks"], alpha=0.8, label="Picks")
    plt.bar(df_team["Map"], df_team["Bans"], alpha=0.6, label="Bans")
    plt.title(f"{team_disp} — Picks vs Bans by Map")
    plt.ylabel("Count")
    plt.legend()
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.show()

    # Pistol win rate by map
    plt.figure(figsize=(10,6))
    plt.bar(df_team["Map"], df_team["PistolWinRate"])
    plt.title(f"{team_disp} — Pistol Win Rate by Map")
    plt.ylabel("Win Rate (0–1)")
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.show()

# ============ Main ============

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teams", help='Comma-separated team names (case-insensitive). '
                                    'If omitted, uses built-in list.')
    ap.add_argument("--regions", help='Comma-separated "Team=Country" overrides, e.g. '
                                      '"Motiv Esports=Singapore,FULL SENSE=Thailand"')
    ap.add_argument("--regions-csv", default="team_regions.csv",
                    help='Optional CSV file (Team,Region) in the same folder. Default: team_regions.csv')
    args = ap.parse_args()

    # Build filter set (lowercased)
    if args.teams:
        team_filter = {t.strip().lower() for t in args.teams.split(",") if t.strip()}
        teams_requested = [t.strip() for t in args.teams.split(",") if t.strip()]
    else:
        team_filter = {t.lower() for t in DEFAULT_TEAMS}
        teams_requested = list(DEFAULT_TEAMS)

    # Compose country map (inline < CSV < CLI flag)
    csv_map = load_regions_from_csv(os.path.join(os.path.dirname(__file__), args.regions_csv))
    flag_map = load_regions_from_flag(args.regions)
    region_map = compose_region_map(TEAM_REGIONS, csv_map, flag_map)

    matches = load_all_matches(DATA_DIR)
    print(f"Loaded {len(matches)} match files from {DATA_DIR}")

    per_team = summarize_per_team(matches, team_filter=team_filter)

    # For stable display names, keep original casing where present
    name_lookup = {k.lower(): k for k in per_team.keys()}
    for team in teams_requested:
        key = team.lower()
        actual_name = name_lookup.get(key, team)  # if no data yet, keep requested name
        team_disp = display_name(actual_name, region_map)

        df = team_maps_to_df(actual_name, per_team.get(actual_name, {}))
        print(f"\n===== {team_disp} — Map Summary =====")
        if not df.empty:
            # Show results column too (now includes dates)
            print(df[["Map","Bans","Picks","Wins","Losses","PistolWinRate","TopAgents","Results"]].to_string(index=False))
        else:
            print("No rows.")

        plot_team(team_disp, df)

if __name__ == "__main__":
    main()
