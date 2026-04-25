#!/usr/bin/env python3
"""
Manually update pistol round data for matches

Usage:
    python update_pistols.py 595635 --map Breeze --pistols 1,1 --map Pearl --pistols 0,2 --map Split --pistols 1,1
"""

import json
import argparse
import os

def update_pistols(match_id, map_pistols):
    """
    map_pistols is a dict like: {"Breeze": (1, 1), "Pearl": (0, 2)}
    where (left_wins, right_wins)
    """
    filepath = f"./data/match_{match_id}_veto.json"
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return False
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Backup
        with open(filepath + ".bak", 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        updated_count = 0
        for game in data.get('played', []):
            map_name = game.get('map')
            if map_name in map_pistols:
                left_pistols, right_pistols = map_pistols[map_name]
                game['pistols'] = {"left": left_pistols, "right": right_pistols}
                print(f"  ✓ Updated {map_name}: {left_pistols}-{right_pistols}")
                updated_count += 1
        
        # Save
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Updated {updated_count} maps in match {match_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Update pistol round data")
    parser.add_argument("match_id", type=int, help="Match ID")
    parser.add_argument("--map", action="append", dest="maps", help="Map name")
    parser.add_argument("--pistols", action="append", dest="pistols", help="Pistols as 'left,right' (e.g., '1,1')")
    
    args = parser.parse_args()
    
    if not args.maps or not args.pistols:
        print("Usage: python update_pistols.py <match_id> --map <MapName> --pistols <left,right>")
        print("\nExample:")
        print("  python update_pistols.py 595635 --map Breeze --pistols 1,1 --map Pearl --pistols 0,2 --map Split --pistols 1,1")
        return
    
    if len(args.maps) != len(args.pistols):
        print("❌ Number of --map and --pistols arguments must match")
        return
    
    # Parse pistols
    map_pistols = {}
    for map_name, pistol_str in zip(args.maps, args.pistols):
        try:
            left, right = map(int, pistol_str.split(','))
            if left + right > 2:
                print(f"⚠️  Warning: {map_name} has {left}+{right} = {left+right} pistol wins (should be ≤2)")
            map_pistols[map_name] = (left, right)
        except:
            print(f"❌ Invalid pistol format for {map_name}: '{pistol_str}' (should be 'left,right')")
            return
    
    print(f"Updating match {args.match_id}...")
    if update_pistols(args.match_id, map_pistols):
        print("\nNext steps:")
        print("1. python build_data_json.py --input ./data --output ./web")
        print("2. streamlit run valdashboard.py")

if __name__ == "__main__":
    main()