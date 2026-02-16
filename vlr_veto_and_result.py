import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from playwright.sync_api import sync_playwright

DEBUG = True
VLR_BASE = "https://www.vlr.gg"
MAP_NAMES = {"Ascent", "Bind", "Breeze", "Haven", "Icebox", "Lotus", "Pearl", "Split", "Sunset", "Fracture", "Abyss", "Corrode"}

AGENT_CANON = {
    "astra": "Astra", "breach": "Breach", "brimstone": "Brimstone", "chamber": "Chamber",
    "clove": "Clove", "cypher": "Cypher", "deadlock": "Deadlock", "fade": "Fade",
    "gekko": "Gekko", "harbor": "Harbor", "iso": "Iso", "jett": "Jett", "kayo": "KAY/O",
    "killjoy": "Killjoy", "neon": "Neon", "omen": "Omen", "phoenix": "Phoenix",
    "raze": "Raze", "reyna": "Reyna", "sage": "Sage", "skye": "Skye", "sova": "Sova",
    "viper": "Viper", "vyse": "Vyse", "waylay": "Waylay", "yoru": "Yoru"
}

CLEAN_NAME_MAP = {
    "Guangzhou Huadu Bilibili Gaming (Bilibili Gaming)": "Bilibili Gaming",
    "JD Mall JDG Esports (JDG Esports)": "JDG Esports"
}

# Pre-loaded overrides for tricky China veto strings
DEFAULT_VETO_OVERRIDES: Dict[str, str] = {
    "598923": "Trace Esports ban Breeze; Wolves Esports ban Corrode; Trace Esports pick Abyss; Wolves Esports pick Haven; Trace Esports ban Pearl; Wolves Esports ban Split; Bind remains",
    "598925": "All Gamers ban Breeze; Bilibili Gaming ban Corrode; All Gamers pick Split; Bilibili Gaming pick Abyss; All Gamers ban Haven; Bilibili Gaming ban Pearl; Bind remains",
    "598926": "Dragon Ranger Gaming ban Haven; JDG Esports ban Pearl; Dragon Ranger Gaming pick Abyss; JDG Esports pick Breeze; Dragon Ranger Gaming ban Split; JDG Esports ban Bind; Corrode remains"
}

def clean_internal_name(name: str) -> str:
    name = CLEAN_NAME_MAP.get(name, name)
    return re.sub(r'^[A-Z][a-z]+ [A-Z][a-z]+ ', '', name).strip()

def resolve_team_strict(token: str, left_full: str, right_full: str) -> str:
    tag = token.strip().upper()
    l_clean = clean_internal_name(left_full).upper()
    r_clean = clean_internal_name(right_full).upper()
    
    # Word boundary regex to prevent 'TE' matching 'Wolves'
    if re.search(rf'\b{re.escape(tag)}\b', l_clean): return left_full
    if re.search(rf'\b{re.escape(tag)}\b', r_clean): return right_full
    
    return left_full if l_clean.startswith(tag) else right_full

def extract_date_from_page(pg) -> Optional[str]:
    date_info = pg.evaluate("""() => {
        const texts = [];
        const el = document.querySelector('.match-header [data-utc-ts]');
        if (el) texts.push('ts:' + el.getAttribute('data-utc-ts'));
        const dateEl = document.querySelector('.match-header-date');
        if (dateEl) texts.push(dateEl.textContent.trim());
        return texts;
    }""") or []
    
    for text in date_info:
        if text.startswith('ts:'):
            val = text[3:].strip()
            if val.isdigit():
                return datetime.fromtimestamp(int(val)).strftime('%Y-%m-%d')
            try:
                return datetime.fromisoformat(val).strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        m = re.search(r'(\d{4}-\d{2}-\d{2})', text)
        if m: return m.group(1)
    return None

def parse_veto_from_text(veto_text: str, left_name: str, right_name: str) -> Tuple[List[Dict], Optional[str]]:
    txt = re.sub(r"\s+", " ", veto_text or "").strip()
    if not txt: return [], None
    
    parts = re.split(r";", txt)
    events = []; decider = None; order = 1
    
    for part in [p.strip() for p in parts if p.strip()]:
        m = re.match(r"^(?P<who>.+?)\s+(?P<verb>ban|pick)s?\s+(?P<map>[A-Za-z]+)$", part, re.I)
        if m:
            who, verb, mapn = m.group("who"), m.group("verb").lower(), m.group("map").title()
            team = resolve_team_strict(who, left_name, right_name)
            events.append({"order": order, "type": verb, "team": team, "map": mapn})
            order += 1
        elif "remains" in part.lower():
            m_dec = re.search(r"([A-Za-z]+)", part)
            if m_dec: 
                decider = m_dec.group(1).title()
                events.append({"order": order, "type": "decider", "team": None, "map": decider})
    return events, decider

def fetch_played_via_dom(pg, match_date: Optional[str]) -> List[Dict[str, Any]]:
    out = []
    blocks = pg.query_selector_all('.vm-stats-game')
    for block in blocks:
        mid = block.get_attribute('data-game-id')
        if not mid or mid == "all": continue
        
        # FIX: Strip whitespace and tabs from map names
        map_name_raw = block.eval_on_selector('.map', 'el => el.textContent.trim()')
        map_name = map_name_raw.strip() if map_name_raw else ""
        
        scores = block.query_selector_all('.score')
        left_s = int(scores[0].inner_text())
        right_s = int(scores[1].inner_text())
        out.append({
            "game_id": int(mid), "map": map_name, "left_score": left_s, "right_score": right_s,
            "left_agents": [], "right_agents": [], "pistols": {"left": 0, "right": 0}, "date": match_date
        })
    return out

def run_one(match_id: int, output_dir: str, headless: bool) -> None:
    url = f"{VLR_BASE}/{match_id}"
    with sync_playwright() as p:
        print(f"\n[Scraping match {match_id}...]")
        br = p.chromium.launch(headless=headless)
        pg = br.new_page()
        
        # Increased timeout and wait until DOM is loaded
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # 1. Extract Date and Team names
        date_iso = extract_date_from_page(pg)
        teams = pg.eval_on_selector(".match-header", "el => { const tms = el.querySelectorAll('.wf-title-med'); return { left: tms[0].textContent.trim(), right: tms[1].textContent.trim() }; }")
        print(f"Teams identified: {teams['left']} vs {teams['right']}")
        
        # 2. Extract Veto Information
        veto_line = pg.query_selector('.match-header-note')
        veto_text = DEFAULT_VETO_OVERRIDES.get(str(match_id)) or (veto_line.inner_text() if veto_line else "")
        events, decider = parse_veto_from_text(veto_text, teams["left"], teams["right"])
        if events:
            print(f"Veto details captured ({len(events)} events).")
        
        # 3. Extract Played Map Scores
        played = fetch_played_via_dom(pg, date_iso)
        if played:
            print(f"Played map data captured ({len(played)} maps).")
        
        # 4. Compile and Save
        out = {
            "match_id": match_id, "date": date_iso, "teams": teams,
            "result": {
                "left_wins": sum(1 for r in played if r['left_score'] > r['right_score']),
                "right_wins": sum(1 for r in played if r['right_score'] > r['left_score']),
                "winner": teams["left"] if sum(1 for r in played if r['left_score'] > r['right_score']) > sum(1 for r in played if r['right_score'] > r['left_score']) else teams["right"]
            },
            "veto": {"events": events, "decider": decider},
            "played": played
        }

        with open(os.path.join(output_dir, f"match_{match_id}_veto.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved to ./data/match_{match_id}_veto.json")
        br.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("match_ids", nargs="+", type=int)
    ap.add_argument("--output", default="./data")
    ap.add_argument("--no-headless", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.output, exist_ok=True)
    for mid in args.match_ids:
        run_one(mid, args.output, not args.no_headless)

if __name__ == "__main__":
    main()
