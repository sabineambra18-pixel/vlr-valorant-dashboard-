# build_data.py
# Builds data.json from scraped match files
# Usage: python build_data.py --input ./data --output ./web

import os
import json
import re
import argparse
from datetime import datetime

def safe_date(d):
    if not d:
        return None
    try:
        return datetime.fromisoformat(d.replace("Z","")).date().isoformat()
    except Exception:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", str(d))
        return m.group(1) if m else None

def load_matches(folder):
    out = []
    if not os.path.exists(folder):
        print(f"Warning: Folder {folder} does not exist")
        return out
    
    for fn in os.listdir(folder):
        if not fn.endswith("_veto.json"):
            continue
        p = os.path.join(folder, fn)
        try:
            with open(p, "r", encoding="utf-8") as f:
                j = json.load(f)
            j["date"] = safe_date(j.get("date") or j.get("match_date") or None)
            out.append(j)
        except Exception as e:
            print(f"Warning: Could not load {fn}: {e}")
    return out

def summarize_for_web(matches):
    teams = set()
    ms = []
    for m in matches:
        left = (m.get("teams", {}) or {}).get("left")
        right = (m.get("teams", {}) or {}).get("right")
        if left: teams.add(left)
        if right: teams.add(right)
        played = []
        for row in m.get("played", []):
            played.append({
                "map": row.get("map"),
                "ls": row.get("left_score"),
                "rs": row.get("right_score"),
                "picked_by": row.get("picked_by"),
                "left_agents": row.get("left_agents", []),
                "right_agents": row.get("right_agents", []),
                "pistols": row.get("pistols", {}),
                "sides": row.get("sides", {})
            })
        ms.append({
            "id": m.get("match_id"),
            "date": m.get("date"),
            "left": left,
            "right": right,
            "winner": (m.get("result") or {}).get("winner"),
            "played": played,
            "veto": m.get("veto")
        })
    return {"teams": sorted(t for t in teams if t), "matches": ms}

def main():
    ap = argparse.ArgumentParser(description="Build data.json from match files")
    ap.add_argument("--input", default="./data", help="Input directory with match_*_veto.json files")
    ap.add_argument("--output", default="./web", help="Output directory for data.json")
    args = ap.parse_args()
    
    matches = load_matches(args.input)
    print(f"Loaded {len(matches)} matches from {args.input}")
    
    if len(matches) == 0:
        print("Warning: No matches found! Make sure you've run the scraper first.")
        return
    
    data = summarize_for_web(matches)
    
    os.makedirs(args.output, exist_ok=True)
    out_path = os.path.join(args.output, "data.json")
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Wrote {out_path} with {len(data['teams'])} teams and {len(data['matches'])} matches")

if __name__ == "__main__":
    main()