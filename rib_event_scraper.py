#!/usr/bin/env python3
"""
RIB.GG Event Scraper - With Map-by-Map data and Vetoes
"""

import json
import re
import os
from typing import Dict, List, Optional, Any
from playwright.sync_api import sync_playwright
import argparse
from datetime import datetime

DEBUG = True

def log(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")

def get_all_series_ids(event_url: str, headless: bool = True) -> List[str]:
    """Navigate event page and find all series IDs"""
    
    print(f"\n🔍 Finding matches at event page...")
    print("=" * 60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.set_default_timeout(60000)
        
        log("Loading event page")
        page.goto(event_url, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        
        series_ids = page.evaluate(r"""
            () => {
                const links = Array.from(document.querySelectorAll('a'));
                const seriesIds = [];
                links.forEach(link => {
                    const match = link.href.match(/\/series\/(\d+)/);
                    if (match) {
                        seriesIds.push(match[1]);
                    }
                });
                return [...new Set(seriesIds)];
            }
        """)
        
        browser.close()
    
    print(f"\n✓ Found {len(series_ids)} unique series")
    for i, sid in enumerate(series_ids[:10], 1):
        print(f"  {i}. Series {sid}")
    if len(series_ids) > 10:
        print(f"  ... and {len(series_ids) - 10} more")
    
    return series_ids

def scrape_series(series_id: str, headless: bool = True) -> Dict:
    """Scrape a single series - get overall stats and per-map data"""
    
    print(f"\n📊 Scraping Series {series_id}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.set_default_timeout(15000)
        
        # Load the main series page to get overall info
        url = f"https://www.rib.gg/series/{series_id}?view=total&tab=team-stats"
        log("Loading series page")
        
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        
        # Get teams, maps, and vetoes
        data = page.evaluate(r"""
            () => {
                const pageTitle = document.title;
                const titleMatch = pageTitle.match(/(.+?)\s+vs\s+(.+?)\s*\|/i);
                
                let team1 = null, team2 = null;
                if (titleMatch) {
                    team1 = titleMatch[1].trim();
                    team2 = titleMatch[2].trim();
                }
                
                return {
                    teams: { team1, team2 },
                    page_text: document.body.innerText
                };
            }
        """)
        
        teams = None
        if data['teams']['team1']:
            teams = {
                "left": data['teams']['team1'],
                "right": data['teams']['team2']
            }
            log(f"Teams: {teams['left']} vs {teams['right']}")
        else:
            teams = {"left": "Team A", "right": "Team B"}
        
        # Extract map scores and vetoes
        maps = parse_map_scores(data['page_text'])
        vetoes = parse_map_vetoes(data['page_text'], teams)
        
        # Get breakdown and economy stats
        breakdown = parse_breakdown_from_text(data['page_text'])
        economy = parse_economy_from_text(data['page_text'])
        
        browser.close()
    
    result = {
        "series_id": series_id,
        "teams": teams,
        "map_vetoes": vetoes,
        "maps": maps,
        "overall_stats": {
            "breakdown": breakdown,
            "economy": economy
        }
    }
    
    print(f"  ✓ {teams['left']} vs {teams['right']}")
    
    # Print stats
    if breakdown.get('pistol_rounds', {}).get('left') is not None:
        pr = breakdown['pistol_rounds']
        print(f"    Pistols: {pr['left']} - {pr['right']}")
    if breakdown.get('first_kills', {}).get('left') is not None:
        fk = breakdown['first_kills']
        print(f"    First Kills: {fk['left']} - {fk['right']}")
    
    if maps:
        print(f"    Maps: {len(maps)} played")
        for map_data in maps:
            print(f"      {map_data['name']}: {map_data['score']['left']}-{map_data['score']['right']}")
    
    if vetoes:
        print(f"    Vetoes: {len(vetoes.get('actions', []))} actions")
    
    return result

def parse_map_scores(text: str) -> List[Dict]:
    """Extract individual map scores from the page"""
    maps = []
    
    lines = text.split('\n')
    
    # Common Valorant map names
    map_names = ['Bind', 'Haven', 'Split', 'Ascent', 'Icebox', 'Breeze', 
                'Fracture', 'Pearl', 'Lotus', 'Sunset', 'Abyss', 'Corrode']
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Check if this line is a map name
        if line in map_names:
            # Look ahead for scores: should be number, dash, number in next few lines
            try:
                search_start = i + 1
                search_end = min(i + 6, len(lines))
                
                left_score = None
                right_score = None
                
                for j in range(search_start, search_end):
                    check_line = lines[j].strip()
                    
                    # If we find a digit line, that's the left score
                    if check_line.isdigit() and left_score is None:
                        left_score = int(check_line)
                    # If we find another digit line after the first, that's the right score
                    elif check_line.isdigit() and left_score is not None:
                        right_score = int(check_line)
                        break
                
                if left_score is not None and right_score is not None:
                    # Avoid duplicates
                    if not any(m['name'] == line for m in maps):
                        maps.append({
                            "name": line,
                            "score": {
                                "left": left_score,
                                "right": right_score
                            },
                            "winner": "left" if left_score > right_score else "right"
                        })
            except:
                pass
    
    return maps

def parse_map_vetoes(text: str, teams: Dict) -> Dict:
    """Parse map veto information"""
    vetoes = {
        "actions": [],
        "raw_text": None
    }
    
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if ('ban' in line.lower() or 'pick' in line.lower()) and ';' in line:
            vetoes["raw_text"] = line
            
            actions = [a.strip() for a in line.split(';')]
            
            for action in actions:
                if 'remains' in action.lower():
                    map_match = re.search(r'(\w+)\s+remains', action, re.IGNORECASE)
                    if map_match:
                        vetoes["actions"].append({
                            "type": "decider",
                            "map": map_match.group(1),
                            "team": None
                        })
                else:
                    match = re.search(r'(.+?)\s+(ban|pick)\s+(.+)', action, re.IGNORECASE)
                    if match:
                        team_abbr = match.group(1).strip()
                        action_type = match.group(2).lower()
                        map_name = match.group(3).strip()
                        
                        vetoes["actions"].append({
                            "type": action_type,
                            "team": team_abbr,
                            "map": map_name
                        })
            
            break
    
    return vetoes if vetoes["actions"] else None

def parse_breakdown_from_text(text: str) -> Dict:
    """Parse breakdown stats"""
    stats = {
        "pistol_rounds": {"left": None, "right": None},
        "first_kills": {"left": None, "right": None},
        "sniper_kills": {"left": None, "right": None},
        "kast": {"left": None, "right": None},
        "clutches": {"left": None, "right": None}
    }
    
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line_clean = ' '.join(line.split())
        
        if 'Pistol Rounds Won' in line_clean:
            if i > 0 and i < len(lines) - 1:
                prev = lines[i-1].strip()
                next_line = lines[i+1].strip()
                if prev.isdigit():
                    stats["pistol_rounds"]["left"] = int(prev)
                if next_line.isdigit():
                    stats["pistol_rounds"]["right"] = int(next_line)
        
        if 'First Kills' in line_clean:
            if i > 0 and i < len(lines) - 1:
                prev = lines[i-1].strip()
                next_line = lines[i+1].strip()
                if prev.isdigit():
                    stats["first_kills"]["left"] = int(prev)
                if next_line.isdigit():
                    stats["first_kills"]["right"] = int(next_line)
        
        if 'Sniper Kills' in line_clean:
            if i > 0 and i < len(lines) - 1:
                prev = lines[i-1].strip()
                next_line = lines[i+1].strip()
                if prev.isdigit():
                    stats["sniper_kills"]["left"] = int(prev)
                if next_line.isdigit():
                    stats["sniper_kills"]["right"] = int(next_line)
        
        if line_clean.strip() == 'KAST':
            if i > 0 and i < len(lines) - 1:
                prev = lines[i-1].strip().replace('%', '')
                next_line = lines[i+1].strip().replace('%', '')
                try:
                    stats["kast"]["left"] = float(prev)
                    stats["kast"]["right"] = float(next_line)
                except:
                    pass
        
        if 'Clutches' in line_clean:
            if i > 0 and i < len(lines) - 1:
                prev = lines[i-1].strip()
                next_line = lines[i+1].strip()
                
                prev_match = re.match(r'(\d+)\s*/\s*(\d+)', prev)
                next_match = re.match(r'(\d+)\s*/\s*(\d+)', next_line)
                
                if prev_match:
                    stats["clutches"]["left"] = {
                        "won": int(prev_match.group(1)),
                        "attempted": int(prev_match.group(2))
                    }
                if next_match:
                    stats["clutches"]["right"] = {
                        "won": int(next_match.group(1)),
                        "attempted": int(next_match.group(2))
                    }
    
    return stats

def parse_economy_from_text(text: str) -> Dict:
    """Parse economy stats"""
    stats = {
        "eco": {"left": {}, "right": {}},
        "semi_eco": {"left": {}, "right": {}},
        "half_buy": {"left": {}, "right": {}},
        "full_buy": {"left": {}, "right": {}}
    }
    
    text_compact = re.sub(r'\s+', '', text)
    
    match = re.search(r'(\d+)%(\d+)W/(\d+)RoundsEco0-5k(\d+)%(\d+)W/(\d+)Rounds', text_compact, re.IGNORECASE)
    if match:
        stats["eco"]["left"] = {"winrate": int(match.group(1)), "wins": int(match.group(2)), "total": int(match.group(3))}
        stats["eco"]["right"] = {"winrate": int(match.group(4)), "wins": int(match.group(5)), "total": int(match.group(6))}
    
    match = re.search(r'(\d+)%(\d+)W/(\d+)RoundsSemi-Eco5-10k(\d+)%(\d+)W/(\d+)Rounds', text_compact, re.IGNORECASE)
    if match:
        stats["semi_eco"]["left"] = {"winrate": int(match.group(1)), "wins": int(match.group(2)), "total": int(match.group(3))}
        stats["semi_eco"]["right"] = {"winrate": int(match.group(4)), "wins": int(match.group(5)), "total": int(match.group(6))}
    
    match = re.search(r'(\d+)%(\d+)W/(\d+)RoundsHalf-Buy10-20k(\d+)%(\d+)W/(\d+)Rounds', text_compact, re.IGNORECASE)
    if match:
        stats["half_buy"]["left"] = {"winrate": int(match.group(1)), "wins": int(match.group(2)), "total": int(match.group(3))}
        stats["half_buy"]["right"] = {"winrate": int(match.group(4)), "wins": int(match.group(5)), "total": int(match.group(6))}
    
    match = re.search(r'(\d+)%(\d+)W/(\d+)RoundsFull-Buy20k\+(\d+)%(\d+)W/(\d+)Rounds', text_compact, re.IGNORECASE)
    if match:
        stats["full_buy"]["left"] = {"winrate": int(match.group(1)), "wins": int(match.group(2)), "total": int(match.group(3))}
        stats["full_buy"]["right"] = {"winrate": int(match.group(4)), "wins": int(match.group(5)), "total": int(match.group(6))}
    
    return stats

def main():
    parser = argparse.ArgumentParser(description="Scrape RIB.GG event matches")
    parser.add_argument("--event-url", required=True, help="Event page URL")
    parser.add_argument("--output", default="./rib_data", help="Output directory")
    parser.add_argument("--no-headless", action="store_true", help="Show browser")
    parser.add_argument("--limit", type=int, help="Limit number of series")
    args = parser.parse_args()
    
    os.makedirs(args.output, exist_ok=True)
    
    try:
        series_ids = get_all_series_ids(args.event_url, headless=not args.no_headless)
        
        if not series_ids:
            print("\n⚠️  No series found!")
            return 1
        
        if args.limit:
            series_ids = series_ids[:args.limit]
        
        print(f"\n🚀 Scraping {len(series_ids)} series...")
        print("=" * 60)
        
        results = []
        failed = []
        
        for i, series_id in enumerate(series_ids, 1):
            print(f"\n[{i}/{len(series_ids)}]", end=" ")
            try:
                result = scrape_series(series_id, headless=not args.no_headless)
                results.append(result)
            except Exception as e:
                print(f"  ❌ Failed: {e}")
                failed.append({"series_id": series_id, "error": str(e)})
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(args.output, f"event_data_{timestamp}.json")
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "event_url": args.event_url,
                "scraped_at": datetime.now().isoformat(),
                "total": len(series_ids),
                "successful": len(results),
                "matches": results,
                "errors": failed
            }, f, indent=2, ensure_ascii=False)
        
        print("\n" + "=" * 60)
        print("✅ SCRAPING COMPLETE!")
        print("=" * 60)
        print(f"📁 {output_file}")
        print(f"✓ {len(results)}/{len(series_ids)} successful")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())