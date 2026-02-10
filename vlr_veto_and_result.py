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

AGENT_CANON = {
    "astra": "Astra", "breach": "Breach", "brimstone": "Brimstone", "chamber": "Chamber",
    "clove": "Clove", "cypher": "Cypher", "deadlock": "Deadlock", "fade": "Fade",
    "gekko": "Gekko", "harbor": "Harbor", "iso": "Iso", "jett": "Jett", "kayo": "KAY/O",
    "kay/o": "KAY/O", "killjoy": "Killjoy", "neon": "Neon", "omen": "Omen", "phoenix": "Phoenix",
    "raze": "Raze", "reyna": "Reyna", "sage": "Sage", "skye": "Skye", "sova": "Sova",
    "viper": "Viper", "vyse": "Vyse", "yoru": "Yoru", "veto": "Veto", "tejo": "Tejo", "waylay": "Waylay"
}

def canonical_agent(name: str) -> str:
    key = (name or "").strip().lower()
    # Filter out non-agent words
    if key in ['overview', 'performance', 'economy', 'pick', 'ban', '', 'all']:
        return None
    # Return canonical name if known, otherwise return titlecased original
    return AGENT_CANON.get(key, name.strip().title())

def dedup_agents(agents: List[str]) -> List[str]:
    """Deduplicate and canonicalize agent names"""
    seen, out = set(), []
    for a in agents:
        canon = canonical_agent(a)
        if canon and canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out

def clean_internal_name(name: str) -> str:
    name = CLEAN_NAME_MAP.get(name, name)
    return re.sub(r'^[A-Z][a-z]+ [A-Z][a-z]+ ', '', name).strip()

def resolve_team_strict(token: str, left_full: str, right_full: str) -> str:
    tag = token.strip().upper()
    l_clean = clean_internal_name(left_full).upper()
    r_clean = clean_internal_name(right_full).upper()
    
    # Common VLR abbreviations — verified from actual veto text
    ALIASES = {
        # EMEA
        "NAVI": "NATUS VINCERE", "NV": "NATUS VINCERE",
        "TL": "TEAM LIQUID", "VIT": "TEAM VITALITY", "TH": "TEAM HERETICS",
        "FNC": "FNATIC", "GX": "GIANTX", "M8": "GENTLE MATES",
        "KC": "KARMINE CORP", "BBL": "BBL ESPORTS",
        "FUT": "FUT ESPORTS", "ULF": "ULF ESPORTS",
        "PCF": "PCIFIC ESPORTS",
        # Americas
        "C9": "CLOUD9", "SEN": "SENTINELS",
        "100T": "100 THIEVES", "EG": "EVIL GENIUSES",
        "LEV": "LEVIATAN", "KRU": "KRU ESPORTS",
        "G2": "G2 ESPORTS", "NRG": "NRG",
        "MIBR": "MIBR", "LOUD": "LOUD",
        "FUR": "FURIA", "ENV": "ENVY",
        # Pacific
        "PRX": "PAPER REX", "DFM": "DETONATION FOCUSME",
        "TS": "TEAM SECRET", "GE": "GLOBAL ESPORTS",
        "RRQ": "REX REGUM QEON", "ZETA": "ZETA DIVISION",
        "T1": "T1", "DRX": "DRX", "GEN": "GEN.G",
        "NS": "NONGSHIM REDFORCE", "NSRF": "NONGSHIM REDFORCE",
        "FS": "FULL SENSE", "TLN": "TALON ESPORTS",
        "VL": "VARREL",
        # China
        "EDG": "EDWARD GAMING", "FPX": "FUNPLUS PHOENIX",
        "BLG": "BILIBILI GAMING", "WOL": "WOLVES ESPORTS",
        "TEC": "TITAN ESPORTS CLUB", "DRG": "DRAGON RANGER GAMING",
        "XLG": "XI LAI GAMING", "AG": "ALL GAMERS",
        "TE": "TRACE ESPORTS", "TYL": "TYLOO",
        "JDG": "JDG ESPORTS", "NOVA": "NOVA ESPORTS",
    }
    
    alias_full = ALIASES.get(tag, "")
    if alias_full:
        if alias_full in l_clean or l_clean in alias_full: return left_full
        if alias_full in r_clean or r_clean in alias_full: return right_full
    
    # Exact word match
    if re.search(rf'\b{re.escape(tag)}\b', l_clean): return left_full
    if re.search(rf'\b{re.escape(tag)}\b', r_clean): return right_full
    
    # Starts with match (e.g. "SEN" matches "SENTINELS")
    if l_clean.startswith(tag): return left_full
    if r_clean.startswith(tag): return right_full
    
    # Tag is contained in the name (e.g. "LEV" in "LEVIATAN")
    if tag in l_clean: return left_full
    if tag in r_clean: return right_full
    
    # Handle number-based abbreviations like "100T" for "100 Thieves"
    # Strip trailing letters from tag and check if number part matches
    num_match = re.match(r'^(\d+)', tag)
    if num_match:
        num = num_match.group(1)
        if num in l_clean: return left_full
        if num in r_clean: return right_full
    
    # Build abbreviation from full name initials and check
    # e.g. "Evil Geniuses" -> "EG", "Karmine Corp" -> "KC"
    l_words = l_clean.split()
    r_words = r_clean.split()
    l_abbr = ''.join(w[0] for w in l_words if w)
    r_abbr = ''.join(w[0] for w in r_words if w)
    if tag == l_abbr: return left_full
    if tag == r_abbr: return right_full
    
    # Fallback: first word match
    if l_words and tag.startswith(l_words[0][:3]): return left_full
    if r_words and tag.startswith(r_words[0][:3]): return right_full
    
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

def normalize_team_name(name: str) -> str:
    """Normalize team name for matching"""
    if not name:
        return ""
    name = name.strip().upper()
    name = re.sub(r'\b(ESPORTS|GAMING|TEAM)\b', '', name)
    name = re.sub(r'[^\w\s]', '', name)
    return name.strip()

def team_names_match(name1: str, name2: str) -> bool:
    """Check if two team names refer to the same team"""
    n1 = normalize_team_name(name1)
    n2 = normalize_team_name(name2)
    
    if n1 == n2:
        return True
    
    if n1 in n2 or n2 in n1:
        return True
    
    words1 = set(n1.split())
    words2 = set(n2.split())
    
    if len(words1.intersection(words2)) >= min(len(words1), len(words2)) // 2:
        return True
    
    return False

def extract_visible_map_data(pg, left_team: str, right_team: str):
    """Extract data from the currently visible map on the overview page"""
    
    result = pg.evaluate("""(args) => {
        const leftTeam = args.leftTeam;
        const rightTeam = args.rightTeam;
        
        const normalize = (name) => {
            if (!name) return '';
            return name.toUpperCase()
                .replace(/ESPORTS|GAMING|TEAM/gi, '')
                .replace(/[^\\w\\s]/g, '')
                .trim();
        };
        
        const namesMatch = (n1, n2) => {
            const norm1 = normalize(n1);
            const norm2 = normalize(n2);
            if (norm1 === norm2) return true;
            if (norm1.includes(norm2) || norm2.includes(norm1)) return true;
            
            const words1 = new Set(norm1.split(/\\s+/));
            const words2 = new Set(norm2.split(/\\s+/));
            const intersection = [...words1].filter(w => words2.has(w));
            return intersection.length >= Math.min(words1.size, words2.size) / 2;
        };
        
        // Find the visible game block - NOT the "all" block
        let visible = null;
        
        const blocks = Array.from(document.querySelectorAll('.vm-stats-game'));
        
        // Find visible block that is NOT game_id="all"
        visible = blocks.find(el => {
            const gid = el.getAttribute('data-game-id');
            if (gid === 'all') return false;  // Skip "all maps" block
            
            const st = window.getComputedStyle(el);
            return st && st.display !== 'none' && st.visibility !== 'hidden' && el.offsetParent !== null;
        });
        
        if (!visible && blocks.length > 0) {
            // Fallback: use first non-all block
            visible = blocks.find(el => el.getAttribute('data-game-id') !== 'all');
        }
        
        if (!visible) return { error: 'No visible non-all game block found' };
        
        // Get game ID
        const gameId = visible.getAttribute('data-game-id');
        
        // Find team names in match header (outside the game blocks)
        let topTeamName = null, bottomTeamName = null;
        
        const matchHeader = document.querySelector('.match-header-vs, .match-header');
        if (matchHeader) {
            const teamElements = matchHeader.querySelectorAll('.wf-title-med, .team-name');
            if (teamElements.length >= 2) {
                topTeamName = teamElements[0].textContent.trim();
                bottomTeamName = teamElements[1].textContent.trim();
            }
        }
        
        if (!topTeamName || !bottomTeamName) {
            return { error: 'Could not find team names in match header' };
        }
        
        // Determine which team is which
        const topIsLeft = namesMatch(topTeamName, leftTeam);
        
        // Get map name from visible block
        let mapName = null;
        const mapElements = visible.querySelectorAll('.map, [class*="map"]');
        for (const mapEl of mapElements) {
            const mapText = mapEl.textContent.trim();
            const mapNames = ['Ascent', 'Bind', 'Breeze', 'Haven', 'Icebox', 'Lotus', 'Pearl', 'Split', 'Sunset', 'Fracture', 'Abyss', 'Corrode'];
            for (const name of mapNames) {
                if (new RegExp('\\\\b' + name + '\\\\b', 'i').test(mapText)) {
                    mapName = name;
                    break;
                }
            }
            if (mapName) break;
        }
        
        // Get scores from visible block
        const scoreElements = visible.querySelectorAll('.score');
        let topScore = 0, bottomScore = 0;
        if (scoreElements.length >= 2) {
            topScore = parseInt(scoreElements[0].textContent || '0');
            bottomScore = parseInt(scoreElements[1].textContent || '0');
        }
        
        const leftScore = topIsLeft ? topScore : bottomScore;
        const rightScore = topIsLeft ? bottomScore : topScore;
        
        // Extract agents from tables
        const tables = Array.from(visible.querySelectorAll('table.wf-table-inset.mod-overview'));
        const topAgents = [], bottomAgents = [];
        
        const collectAgents = (table, bucket) => {
            if (!table) return;
            // Get all agent images, even without alt attribute
            table.querySelectorAll('td.mod-agents img').forEach(img => {
                const alt = (img.getAttribute('alt') || img.getAttribute('title') || '').trim();
                if (alt) bucket.push(alt);
            });
        };
        
        if (tables.length >= 2) {
            collectAgents(tables[0], topAgents);
            collectAgents(tables[1], bottomAgents);
        }
        
        const leftAgents = topIsLeft ? topAgents : bottomAgents;
        const rightAgents = topIsLeft ? bottomAgents : topAgents;
        
        // Extract rounds
        const cols = Array.from(visible.querySelectorAll('.vlr-rounds .vlr-rounds-row .vlr-rounds-row-col'));
        const rounds = [];
        
        for (const col of cols) {
            const sq = col.querySelectorAll('.rnd-sq');
            if (!sq || sq.length < 2) continue;
            
            const top = sq[0].className || '';
            const bot = sq[1].className || '';
            const topWin = top.includes('mod-win') && !bot.includes('mod-win');
            const botWin = bot.includes('mod-win') && !top.includes('mod-win');
            
            // Detect side from round icon classes: mod-t = attack win, mod-ct = defense win
            const topIsAtk = top.includes('mod-t') && !top.includes('mod-ct');
            const topIsDef = top.includes('mod-ct');
            const botIsAtk = bot.includes('mod-t') && !bot.includes('mod-ct');
            const botIsDef = bot.includes('mod-ct');
            
            // Determine which side the winning team was on
            let winnerSide = null;
            if (topWin) {
                winnerSide = topIsAtk ? 'atk' : (topIsDef ? 'def' : null);
            } else if (botWin) {
                winnerSide = botIsAtk ? 'atk' : (botIsDef ? 'def' : null);
            }
            
            const leftWin = topIsLeft ? topWin : botWin;
            const rightWin = topIsLeft ? botWin : topWin;
            
            rounds.push({ leftWin, rightWin, winnerSide });
        }
        
        // Calculate pistols
        let pistolLeft = 0, pistolRight = 0;
        [0, 12].forEach(i => {
            const r = rounds[i];
            if (!r) return;
            if (r.leftWin) pistolLeft++;
            else if (r.rightWin) pistolRight++;
        });
        
        // Calculate attack/defense from actual round side data
        let leftAtk = 0, leftDef = 0, rightAtk = 0, rightDef = 0;
        
        rounds.forEach((r) => {
            if (r.leftWin && r.winnerSide === 'atk') leftAtk++;
            else if (r.leftWin && r.winnerSide === 'def') leftDef++;
            if (r.rightWin && r.winnerSide === 'atk') rightAtk++;
            else if (r.rightWin && r.winnerSide === 'def') rightDef++;
        });
        
        return {
            gameId: parseInt(gameId || '0'),
            mapName: mapName,
            leftScore: leftScore,
            rightScore: rightScore,
            pistols: { left: pistolLeft, right: pistolRight },
            sides: { 
                left_atk: leftAtk, 
                left_def: leftDef, 
                right_atk: rightAtk, 
                right_def: rightDef 
            },
            agents: {
                left: leftAgents,
                right: rightAgents
            },
            topTeam: topTeamName,
            bottomTeam: bottomTeamName,
            topIsLeft: topIsLeft,
            totalRounds: rounds.length
        };
    }""", {"leftTeam": left_team, "rightTeam": right_team})
    
    return result

def fetch_played_via_pills(pg, match_date, left_team, right_team):
    """Extract map data by clicking pills and reading visible content"""
    out = []
    seen_maps = set()
    
    # Find all map pills using locator (not query_selector_all)
    pills = pg.locator('.vm-stats-gamesnav-item')
    pill_count = pills.count()
    
    if DEBUG:
        print(f"  Found {pill_count} map pills")
    
    # If no pills, try to read single visible block
    if pill_count == 0:
        try:
            pg.wait_for_selector(".vm-stats-game-header", timeout=2000)
        except:
            pass
        
        data = extract_visible_map_data(pg, left_team, right_team)
        if data and not data.get('error') and data.get('mapName'):
            left_agents = dedup_agents(data['agents']['left'])
            right_agents = dedup_agents(data['agents']['right'])
            
            out.append({
                "game_id": data['gameId'],
                "map": data['mapName'],
                "left_score": data['leftScore'],
                "right_score": data['rightScore'],
                "left_agents": left_agents,
                "right_agents": right_agents,
                "pistols": data['pistols'],
                "sides": data['sides'],
                "date": match_date
            })
        return out
    
    # Click each pill and extract data
    for i in range(pill_count):
        if DEBUG:
            print(f"  Clicking pill {i+1}/{pill_count}")
        
        # Click the pill
        for attempt in range(3):
            try:
                pills.nth(i).scroll_into_view_if_needed(timeout=600)
            except:
                pass
            
            try:
                pills.nth(i).click(timeout=1200)
                break
            except:
                time.sleep(0.15)
        
        # Wait for content to load - look for the actual player stats tables
        try:
            pg.wait_for_selector("table.wf-table-inset.mod-overview", timeout=3000)
        except:
            pass
        
        time.sleep(1.5)  # Extra wait for JS to fully update DOM
        
        # Check what game_id is now visible
        visible_gid = pg.evaluate("""() => {
            const blocks = Array.from(document.querySelectorAll('.vm-stats-game'));
            const visible = blocks.find(el => {
                const gid = el.getAttribute('data-game-id');
                if (gid === 'all') return false;
                const st = window.getComputedStyle(el);
                return st && st.display !== 'none' && st.visibility !== 'hidden' && el.offsetParent !== null;
            });
            return visible ? visible.getAttribute('data-game-id') : null;
        }""")
        
        if not visible_gid or visible_gid == 'all':
            if DEBUG:
                print(f"    ⏭️  Skipping - showing 'all' or no specific map")
            continue
        
        if DEBUG:
            print(f"    Visible game_id: {visible_gid}")
        
        # Extract data from visible content
        data = extract_visible_map_data(pg, left_team, right_team)
        
        if data and not data.get('error') and data.get('mapName'):
            # Check for duplicates
            map_sig = (data['mapName'], data['leftScore'], data['rightScore'])
            if map_sig in seen_maps:
                if DEBUG:
                    print(f"    ⏭️  Skipping duplicate: {data['mapName']} {data['leftScore']}-{data['rightScore']}")
                continue
            
            seen_maps.add(map_sig)
            
            left_agents = dedup_agents(data['agents']['left'])
            right_agents = dedup_agents(data['agents']['right'])
            
            if DEBUG:
                print(f"    Teams: TOP={data['topTeam']} ({'LEFT' if data['topIsLeft'] else 'RIGHT'})")
                print(f"    Score: {data['leftScore']}-{data['rightScore']}")
                print(f"    Pistols: {data['pistols']['left']}-{data['pistols']['right']}")
                sides = data['sides']
                print(f"    ATK/DEF - Left: {sides['left_atk']}/{sides['left_def']}, Right: {sides['right_atk']}/{sides['right_def']}")
                print(f"    Agents - Left: {', '.join(left_agents) if left_agents else 'none'}")
                print(f"    Agents - Right: {', '.join(right_agents) if right_agents else 'none'}")
                print(f"    ✓ Verification: Left total = {sides['left_atk'] + sides['left_def']} (should be {data['leftScore']})")
                print(f"    ✓ Verification: Right total = {sides['right_atk'] + sides['right_def']} (should be {data['rightScore']})")
            
            out.append({
                "game_id": data['gameId'],
                "map": data['mapName'],
                "left_score": data['leftScore'],
                "right_score": data['rightScore'],
                "left_agents": left_agents,
                "right_agents": right_agents,
                "pistols": data['pistols'],
                "sides": data['sides'],
                "date": match_date
            })
        elif DEBUG:
            print(f"    ❌ Error: {data.get('error', 'Unknown error')}")
            if data.get('debug'):
                debug = data['debug']
                print(f"       Debug: Found {debug.get('blockCount')} blocks")
                print(f"       Has vm-stats-game-header: {debug.get('hasHeader')}")
                print(f"       Has match-header-vs: {debug.get('hasMatchHeader')}")
                print(f"       Block classes: {debug.get('allClasses')}")
                print(f"       HTML preview: {debug.get('innerHTML', '')[:200]}")
    
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
        
        try:
            teams = pg.eval_on_selector(".match-header", "el => { const tms = el.querySelectorAll('.wf-title-med'); return { left: tms[0].textContent.trim(), right: tms[1].textContent.trim() }; }")
        except Exception as e:
            print(f"❌ Error: Could not find match header. Match may have different structure or not exist.")
            if DEBUG:
                print(f"   Exception: {e}")
            br.close()
            return
        
        teams['left'] = re.sub(r'\s+', ' ', teams['left']).strip()
        teams['right'] = re.sub(r'\s+', ' ', teams['right']).strip()
        
        # Apply CLEAN_NAME_MAP
        teams['left'] = CLEAN_NAME_MAP.get(teams['left'], teams['left'])
        teams['right'] = CLEAN_NAME_MAP.get(teams['right'], teams['right'])
        
        print(f"Teams: {teams['left']} vs {teams['right']}")
        
        veto_line = pg.query_selector('.match-header-note')
        veto_text = DEFAULT_VETO_OVERRIDES.get(str(match_id)) or (veto_line.inner_text() if veto_line else "")
        events, decider = parse_veto_from_text(veto_text, teams["left"], teams["right"])
        
        played = fetch_played_via_pills(pg, date_iso, teams["left"], teams["right"])
        print(f"✓ Captured {len(played)} maps.")
        
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