#!/usr/bin/env python3
"""
RIB.GG Team Scraper - Scrape first 20 matches from each team page
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

def get_team_series_ids(team_url: str, limit: int = 20, headless: bool = True) -> List[str]:
    """Get series IDs from a team's matches page"""
    
    print(f"\n🔍 Getting matches from: {team_url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.set_default_timeout(60000)
        
        log("Loading team page")
        page.goto(team_url, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        
        # Get all hrefs
        all_hrefs = page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a'));
                return links.map(link => link.href);
            }
        """)
        
        browser.close()
    
    log(f"Got {len(all_hrefs)} total hrefs")
    
    # Parse series IDs in Python using better regex
    series_ids = []
    for href in all_hrefs:
        # Match /series/ followed by digits, but ensure it's a proper series URL
        match = re.search(r'rib\.gg/series/(\d{4,})', href)  # At least 4 digits to avoid false matches
        if match:
            series_id = match.group(1)
            if series_id not in series_ids:
                series_ids.append(series_id)
                log(f"Found series: {series_id}")
    
    # Limit to first N matches
    if limit and len(series_ids) > limit:
        series_ids = series_ids[:limit]
    
    print(f"  ✓ Found {len(series_ids)} series to scrape")
    
    return series_ids

def scrape_series(series_id: str, headless: bool = True) -> Dict:
    """Scrape a single series"""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.set_default_timeout(15000)
        
        url = f"https://www.rib.gg/series/{series_id}?view=total&tab=team-stats"
        
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            
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
            else:
                teams = {"left": "Team A", "right": "Team B"}
            
            maps = parse_map_scores(data['page_text'])
            vetoes = parse_map_vetoes(data['page_text'], teams)
            breakdown = parse_breakdown_from_text(data['page_text'])
            economy = parse_economy_from_text(data['page_text'])
            
            browser.close()
            
            return {
                "series_id": series_id,
                "teams": teams,
                "map_vetoes": vetoes,
                "maps": maps,
                "overall_stats": {
                    "breakdown": breakdown,
                    "economy": economy
                }
            }
        except Exception as e:
            browser.close()
            raise e

def parse_map_scores(text: str) -> List[Dict]:
    """Extract individual map scores"""
    maps = []
    lines = text.split('\n')
    map_names = ['Bind', 'Haven', 'Split', 'Ascent', 'Icebox', 'Breeze', 
                'Fracture', 'Pearl', 'Lotus', 'Sunset', 'Abyss', 'Corrode']
    
    for i, line in enumerate(lines):
        line = line.strip()
        if line in map_names:
            try:
                search_start = i + 1
                search_end = min(i + 6, len(lines))
                left_score = None
                right_score = None
                
                for j in range(search_start, search_end):
                    check_line = lines[j].strip()
                    if check_line.isdigit() and left_score is None:
                        left_score = int(check_line)
                    elif check_line.isdigit() and left_score is not None:
                        right_score = int(check_line)
                        break
                
                if left_score is not None and right_score is not None:
                    if not any(m['name'] == line for m in maps):
                        maps.append({
                            "name": line,
                            "score": {"left": left_score, "right": right_score},
                            "winner": "left" if left_score > right_score else "right"
                        })
            except:
                pass
    return maps

def parse_map_vetoes(text: str, teams: Dict) -> Dict:
    """Parse map vetoes"""
    vetoes = {"actions": [], "raw_text": None}
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
                        vetoes["actions"].append({
                            "type": match.group(2).lower(),
                            "team": match.group(1).strip(),
                            "map": match.group(3).strip()
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
        
        if 'Pistol Rounds Won' in line_clean and i > 0 and i < len(lines) - 1:
            prev = lines[i-1].strip()
            next_line = lines[i+1].strip()
            if prev.isdigit():
                stats["pistol_rounds"]["left"] = int(prev)
            if next_line.isdigit():
                stats["pistol_rounds"]["right"] = int(next_line)
        
        if 'First Kills' in line_clean and i > 0 and i < len(lines) - 1:
            prev = lines[i-1].strip()
            next_line = lines[i+1].strip()
            if prev.isdigit():
                stats["first_kills"]["left"] = int(prev)
            if next_line.isdigit():
                stats["first_kills"]["right"] = int(next_line)
        
        if 'Sniper Kills' in line_clean and i > 0 and i < len(lines) - 1:
            prev = lines[i-1].strip()
            next_line = lines[i+1].strip()
            if prev.isdigit():
                stats["sniper_kills"]["left"] = int(prev)
            if next_line.isdigit():
                stats["sniper_kills"]["right"] = int(next_line)
        
        if line_clean.strip() == 'KAST' and i > 0 and i < len(lines) - 1:
            prev = lines[i-1].strip().replace('%', '')
            next_line = lines[i+1].strip().replace('%', '')
            try:
                stats["kast"]["left"] = float(prev)
                stats["kast"]["right"] = float(next_line)
            except:
                pass
        
        if 'Clutches' in line_clean and i > 0 and i < len(lines) - 1:
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
    # Team URLs to scrape (first 20 matches from each)
    team_urls = [
        "https://www.rib.gg/teams/mibr-gc/matches/6494",
        "https://www.rib.gg/teams/team-liquid-brazil/matches/5438",
        "https://www.rib.gg/teams/kru-blaze/matches/5837",
        "https://www.rib.gg/teams/shopify-rebellion-gold/matches/7510",
        "https://www.rib.gg/teams/xipto-esports-gc/matches/15847",
        "https://www.rib.gg/teams/team-ninetails/matches/19144",
        "https://www.rib.gg/teams/karmine-corp-gc/matches/10613",
        "https://www.rib.gg/teams/giantx-gc/matches/14785",
        "https://www.rib.gg/teams/g2-gozen/matches/4955"
    ]
    
    parser = argparse.ArgumentParser(description="Scrape RIB.GG team matches")
    parser.add_argument("--output", default="./rib_data", help="Output directory")
    parser.add_argument("--no-headless", action="store_true", help="Show browser")
    parser.add_argument("--matches-per-team", type=int, default=20, help="Number of matches per team")
    args = parser.parse_args()
    
    os.makedirs(args.output, exist_ok=True)
    
    try:
        all_results = []
        all_failed = []
        
        print("🚀 Starting team scraper...")
        print("=" * 60)
        
        for team_idx, team_url in enumerate(team_urls, 1):
            print(f"\n{'='*60}")
            print(f"TEAM {team_idx}/{len(team_urls)}")
            print(f"{'='*60}")
            
            try:
                # Get series IDs for this team
                series_ids = get_team_series_ids(
                    team_url, 
                    limit=args.matches_per_team,
                    headless=not args.no_headless
                )
                
                if not series_ids:
                    print(f"  ⚠️  No matches found for this team")
                    continue
                
                # Scrape each match
                for match_idx, series_id in enumerate(series_ids, 1):
                    print(f"\n  [{match_idx}/{len(series_ids)}] Series {series_id}", end=" ")
                    
                    try:
                        result = scrape_series(series_id, headless=not args.no_headless)
                        all_results.append(result)
                        
                        # Print summary
                        teams = result['teams']
                        maps = result.get('maps', [])
                        print(f"✓ {teams['left']} vs {teams['right']} ({len(maps)} maps)")
                        
                    except Exception as e:
                        print(f"❌ {str(e)[:50]}")
                        all_failed.append({"team_url": team_url, "series_id": series_id, "error": str(e)})
                
            except Exception as e:
                print(f"  ❌ Failed to process team: {e}")
                continue
        
        # Save all results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(args.output, f"team_data_{timestamp}.json")
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "scraped_at": datetime.now().isoformat(),
                "teams_scraped": len(team_urls),
                "total_matches": len(all_results),
                "failed_matches": len(all_failed),
                "matches": all_results,
                "errors": all_failed
            }, f, indent=2, ensure_ascii=False)
        
        print("\n" + "=" * 60)
        print("✅ SCRAPING COMPLETE!")
        print("=" * 60)
        print(f"📁 {output_file}")
        print(f"✓ Total: {len(all_results)} matches from {len(team_urls)} teams")
        if all_failed:
            print(f"❌ Failed: {len(all_failed)} matches")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())