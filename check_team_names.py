#!/usr/bin/env python3
"""
Diagnostic script to check exact team names in scraped match data
"""

import os
import json
import sys

def check_team_names(data_folder):
    """Check all team names in scraped match files"""
    
    if not os.path.exists(data_folder):
        print(f"❌ Folder not found: {data_folder}")
        return
    
    team_names = set()
    naos_variations = []
    
    print(f"🔍 Scanning {data_folder} for team names...\n")
    
    for filename in os.listdir(data_folder):
        if not filename.endswith("_veto.json"):
            continue
            
        filepath = os.path.join(data_folder, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                match_data = json.load(f)
            
            # Check teams structure
            teams = match_data.get("teams", {})
            left = teams.get("left")
            right = teams.get("right")
            
            if left:
                team_names.add(left)
                if "naos" in left.lower():
                    naos_variations.append({
                        "match_id": match_data.get("match_id"),
                        "name": left,
                        "repr": repr(left),  # Shows exact string with special chars
                        "bytes": left.encode('utf-8').hex()
                    })
            
            if right:
                team_names.add(right)
                if "naos" in right.lower():
                    naos_variations.append({
                        "match_id": match_data.get("match_id"),
                        "name": right,
                        "repr": repr(right),
                        "bytes": right.encode('utf-8').hex()
                    })
                    
        except Exception as e:
            print(f"⚠️  Error reading {filename}: {e}")
    
    print(f"📊 Found {len(team_names)} unique team names:\n")
    for team in sorted(team_names):
        print(f"  • {team}")
    
    if naos_variations:
        print(f"\n\n🎯 NAOS variations found ({len(naos_variations)}):\n")
        for item in naos_variations:
            print(f"  Match ID: {item['match_id']}")
            print(f"  Team name: {item['name']}")
            print(f"  Repr: {item['repr']}")
            print(f"  Bytes: {item['bytes']}")
            print()
    else:
        print("\n⚠️  No NAOS variations found in the data!")
        print("   Make sure you've scraped NAOS matches.")

if __name__ == "__main__":
    # Check common locations
    possible_folders = ["./data", "../data", "/mnt/user-data/uploads"]
    
    data_folder = None
    for folder in possible_folders:
        if os.path.exists(folder):
            data_folder = folder
            break
    
    if len(sys.argv) > 1:
        data_folder = sys.argv[1]
    
    if not data_folder:
        print("❌ No data folder found!")
        print("Usage: python check_team_names.py [data_folder]")
        sys.exit(1)
    
    check_team_names(data_folder)