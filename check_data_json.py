#!/usr/bin/env python3
"""
Check data.json to see if NAOS teams are properly included in the teams list
"""

import json
import sys
import os

def check_data_json(filepath):
    """Check if NAOS is in the data.json teams"""
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    teams_list = data.get('teams', [])
    matches_list = data.get('matches', [])
    
    print(f"📊 Data Summary:")
    print(f"   Total teams in teams array: {len(teams_list)}")
    print(f"   Total matches: {len(matches_list)}")
    print()
    
    # Check if NAOS is in teams list
    naos_in_teams = [t for t in teams_list if 'naos' in t.lower()]
    
    if naos_in_teams:
        print(f"✓ NAOS found in teams list: {naos_in_teams}")
    else:
        print(f"✗ NAOS NOT found in teams list!")
        print(f"   This is the problem! NAOS matches were scraped but not added to teams array.")
    
    print()
    
    # Check NAOS matches
    naos_matches = [m for m in matches_list 
                    if ('naos' in (m.get('left', '')).lower() or 
                        'naos' in (m.get('right', '')).lower())]
    
    print(f"📋 NAOS Matches ({len(naos_matches)}):")
    for match in naos_matches:
        match_id = match.get('id')
        left = match.get('left', '???')
        right = match.get('right', '???')
        date = match.get('date', 'No date')
        print(f"   Match {match_id}: {left} vs {right} ({date})")
    
    if naos_matches and not naos_in_teams:
        print()
        print("🔍 DIAGNOSIS:")
        print("   NAOS matches exist in the matches array,")
        print("   but NAOS is missing from the teams array!")
        print()
        print("   This means build_data_json.py is not properly")
        print("   extracting team names from matches.")
        print()
        print("🔧 FIX NEEDED:")
        print("   The teams array in data.json should be built from")
        print("   all unique team names in matches. Check build_data_json.py")
        print("   line 58-59 where teams are collected.")
    
    return teams_list, naos_matches

if __name__ == "__main__":
    # Try common locations
    possible_files = [
        "./web/data.json",
        "../web/data.json", 
        "./data.json",
        "/mnt/user-data/uploads/data.json"
    ]
    
    data_file = None
    if len(sys.argv) > 1:
        data_file = sys.argv[1]
    else:
        for path in possible_files:
            if os.path.exists(path):
                data_file = path
                break
    
    if not data_file:
        print("❌ data.json not found!")
        print("Usage: python check_data_json.py [path/to/data.json]")
        print()
        print("Make sure you've run: python build_data_json.py")
        sys.exit(1)
    
    print(f"Checking: {data_file}")
    print("="*60)
    print()
    
    check_data_json(data_file)