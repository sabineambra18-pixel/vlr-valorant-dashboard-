#!/usr/bin/env python3
"""
Emergency fix for corrupted map names in match JSON files
"""

import os
import json
import re
import glob

def extract_clean_map_name(dirty_map):
    """Extract just the map name from corrupted string"""
    if not dirty_map:
        return ""
    
    # Known valid map names
    valid_maps = ["Ascent", "Bind", "Breeze", "Haven", "Icebox", "Lotus", 
                  "Pearl", "Split", "Sunset", "Fracture", "Abyss", "Corrode"]
    
    # Try to find a valid map name in the string
    dirty_upper = str(dirty_map).upper()
    for map_name in valid_maps:
        if map_name.upper() in dirty_upper:
            return map_name
    
    # Fallback: take first word that's alphabetic
    words = re.findall(r'[A-Za-z]+', str(dirty_map))
    if words:
        return words[0].title()
    
    return "Unknown"

def fix_match_file(filepath):
    """Fix a single match file"""
    print(f"Fixing {os.path.basename(filepath)}...")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Backup
        backup_path = filepath + ".bak"
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Fix played maps
        if 'played' in data:
            for game in data['played']:
                if 'map' in game:
                    old_map = game['map']
                    new_map = extract_clean_map_name(old_map)
                    game['map'] = new_map
                    if old_map != new_map:
                        print(f"  Fixed: '{old_map[:50]}...' -> '{new_map}'")
                
                # Ensure ls/rs fields
                if 'ls' not in game and 'left_score' in game:
                    game['ls'] = game['left_score']
                if 'rs' not in game and 'right_score' in game:
                    game['rs'] = game['right_score']
        
        # Save fixed version
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"  ✅ Fixed and saved\n")
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}\n")
        return False

def main():
    data_dir = "./data"
    pattern = os.path.join(data_dir, "match_*_veto.json")
    files = glob.glob(pattern)
    
    if not files:
        print(f"No match files found in {data_dir}")
        return
    
    print(f"Found {len(files)} files to fix\n")
    
    fixed = 0
    for filepath in files:
        if fix_match_file(filepath):
            fixed += 1
    
    print("=" * 60)
    print(f"Fixed {fixed}/{len(files)} files")
    print("=" * 60)
    print("\nNext steps:")
    print("1. python build_data_json.py --input ./data --output ./web")
    print("2. streamlit run valdashboard.py")

if __name__ == "__main__":
    main()