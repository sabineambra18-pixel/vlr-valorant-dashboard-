import argparse
import json
import os
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from playwright.sync_api import sync_playwright
import time

DEBUG = True
VLR_BASE = "https://www.vlr.gg"
MAP_NAMES = {"Ascent", "Bind", "Breeze", "Haven", "Icebox", "Lotus", "Pearl", "Split", "Sunset", "Fracture", "Abyss", "Corrode"}

CLEAN_NAME_MAP = {
    "Guangzhou Huadu Bilibili Gaming (Bilibili Gaming)": "Bilibili Gaming",
    "JD Mall JDG Esports (JDG Esports)": "JDG Esports",
    "Wuxi Titan Esports Club (Titan Esports Club)": "Titan Esports Club",
    "Xi Lai Gaming": "Xi Lai Gaming"
}

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
    """Extract played maps with PISTOL data only (no attack/defense)"""
    out = []
    
    # JavaScript to extract round data - pistols only
    rounds_eval_js = """
        (rootEl) => {
          const cols = Array.from(rootEl.querySelectorAll('.vlr-rounds .vlr-rounds-row .vlr-rounds-row-col'));
          const rounds = [];
          for (const col of cols) {
            const sq = col.querySelectorAll('.rnd-sq');
            if (!sq || sq.length < 2) continue;
            const top = sq[0].className || '';
            const bot = sq[1].className || '';
            const topWin = top.includes('mod-win') && !bot.includes('mod-win');
            const botWin = bot.includes('mod-win') && !top.includes('mod-win');
            rounds.push({ topWin, botWin });
          }
          
          // Extract pistols (rounds 0 and 12)
          let leftP = 0, rightP = 0;
          [0,12].forEach(i => { 
            const r = rounds[i]; 
            if (!r) return;
            if (r.topWin && !r.botWin) leftP += 1;
            else if (r.botWin && !r.topWin) rightP += 1;
          });
          
          return { rounds, pistols: { left: leftP, right: rightP } };
        }
    """
    
    blocks = pg.query_selector_all('.vm-stats-game')
    
    for block in blocks:
        mid = block.get_attribute('data-game-id')
        if not mid or mid == "all": 
            continue
        
        # Extract map name
        map_name_raw = None
        try:
            map_elem = block.query_selector('.map div:first-child')
            if not map_elem:
                map_elem = block.query_selector('.map span:first-child')
            if not map_elem:
                map_elem = block.query_selector('.map')
            
            if map_elem:
                map_name_raw = map_elem.inner_text().strip()
        except Exception as e:
            if DEBUG:
                print(f"  Error extracting map name: {e}")
            continue
        
        if not map_name_raw:
            continue
        
        # Clean the map name
        map_name = ''.join(filter(str.isalpha, map_name_raw)).title()
        
        if map_name not in MAP_NAMES:
            for known_map in MAP_NAMES:
                if known_map.lower() in map_name.lower():
                    map_name = known_map
                    break
            else:
                if DEBUG:
                    print(f"  Unknown map: '{map_name_raw}'")
                continue
        
        if DEBUG:
            print(f"  Processing map: {map_name}")
        
        # Get scores
        scores = block.query_selector_all('.score')
        if len(scores) < 2:
            continue
            
        left_s = int(scores[0].inner_text())
        right_s = int(scores[1].inner_text())
        
        # Extract pistol data using JavaScript
        round_data = None
        try:
            round_data = block.evaluate(rounds_eval_js, block)
        except Exception as e:
            if DEBUG:
                print(f"    Could not extract pistol data: {e}")
        
        # Default values
        pistols = {"left": 0, "right": 0}
        
        if round_data:
            pistols = round_data.get("pistols", pistols)
            
            if DEBUG:
                print(f"    Score: {left_s}-{right_s}, Pistols: {pistols['left']}-{pistols['right']}")
        else:
            if DEBUG:
                print(f"    Score: {left_s}-{right_s} (no pistol data available)")
        
        out.append({
            "game_id": int(mid), 
            "map": map_name, 
            "left_score": left_s,
            "right_score": right_s,
            "left_agents": [], 
            "right_agents": [], 
            "pistols": pistols,
            "sides": {"left_atk": 0, "left_def": 0, "right_atk": 0, "right_def": 0},  # All zeros - not tracked
            "date": match_date
        })
    
    return out

def run_one(match_id: int, output_dir: str, headless: bool) -> None:
    url = f"{VLR_BASE}/{match_id}"
    with sync_playwright() as p:
        print(f"\n[Scraping match {match_id}...]")
        br = p.chromium.launch(headless=headless)
        pg = br.new_page()
        
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        try:
            pg.get_by_text("Overview", exact=True).first.click(timeout=3000)
        except Exception:
            pass
        
        time.sleep(1)
        
        date_iso = extract_date_from_page(pg)
        teams = pg.eval_on_selector(".match-header", "el => { const tms = el.querySelectorAll('.wf-title-med'); return { left: tms[0].textContent.trim(), right: tms[1].textContent.trim() }; }")
        
        teams['left'] = re.sub(r'\s+', ' ', teams['left']).strip()
        teams['right'] = re.sub(r'\s+', ' ', teams['right']).strip()
        
        # Apply CLEAN_NAME_MAP
        teams['left'] = CLEAN_NAME_MAP.get(teams['left'], teams['left'])
        teams['right'] = CLEAN_NAME_MAP.get(teams['right'], teams['right'])
        
        print(f"Teams: {teams['left']} vs {teams['right']}")
        
        veto_line = pg.query_selector('.match-header-note')
        veto_text = DEFAULT_VETO_OVERRIDES.get(str(match_id)) or (veto_line.inner_text() if veto_line else "")
        events, decider = parse_veto_from_text(veto_text, teams["left"], teams["right"])
        
        played = fetch_played_via_dom(pg, date_iso)
        print(f"Captured {len(played)} maps.")
        
        l_wins = sum(1 for r in played if r['left_score'] > r['right_score'])
        r_wins = sum(1 for r in played if r['right_score'] > r['left_score'])
        winner = teams["left"] if l_wins > r_wins else (teams["right"] if r_wins > l_wins else None)
        
        out = {
            "match_id": match_id, 
            "date": date_iso, 
            "teams": teams,
            "result": {
                "left_wins": l_wins,
                "right_wins": r_wins,
                "winner": winner
            },
            "veto": {"events": events, "decider": decider},
            "played": played
        }

        with open(os.path.join(output_dir, f"match_{match_id}_veto.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved to {output_dir}/match_{match_id}_veto.json")
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