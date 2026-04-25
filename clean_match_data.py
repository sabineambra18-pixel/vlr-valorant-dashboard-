#!/usr/bin/env python3
"""
Script to clean existing match_*_veto.json files
Fixes:
1. Corrupted map names (tabs, newlines, weird characters)
2. Missing ls/rs fields (converts left_score/right_score)
3. Invalid data
"""

import os
import json
import re
import glob
import argparse
from typing import Dict, Any

def clean_map_name(map_name):
    """Aggressively clean map names"""
    if not map_name:
        return ""
    
    # Convert to string and remove ALL whitespace
    cleaned = str(map_name)
    cleaned = re.sub(r'\s+', '', cleaned)
    cleaned = cleaned.strip()
    
    # If it's still weird (too long, has weird chars), return empty
    if len(cleaned) > 20 or not cleaned.isalpha():
        print(f"  ⚠️  WARNING: Suspicious map name '{map_name}' -> '{cleaned}'")
        # Try to extract just the letters
        alpha_only = ''.join(c for c in cleaned if c.isalpha())
        if alpha_only:
            cleaned = alpha_only
        else:
            return ""
    
    return cleaned

def safe_int(value, default=0):
    """Safely convert to int"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def clean_match_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean a single match data structure"""
    
    # Clean played maps
    if "played" in data and isinstance(data["played"], list):
        cleaned_played = []
        for i, game in enumerate(data["played"]):
            if not isinstance(game, dict):
                continue
            
            # Clean map name
            raw_map = game.get("map", "")
            clean_map = clean_map_name(raw_map)
            
            if not clean_map:
                print(f"  ⚠️  Skipping game {i+1} with invalid map: '{raw_map}'")
                continue
            
            # Ensure ls/rs fields exist (convert from left_score/right_score if needed)
            if "ls" not in game and "left_score" in game:
                game["ls"] = safe_int(game["left_score"])
            if "rs" not in game and "right_score" in game:
                game["rs"] = safe_int(game["right_score"])
            
            # Ensure ls/rs are integers
            game["ls"] = safe_int(game.get("ls", 0))
            game["rs"] = safe_int(game.get("rs", 0))
            
            # Update the map name
            game["map"] = clean_map
            
            # Ensure pistols is a dict
            if "pistols" not in game or not isinstance(game["pistols"], dict):
                game["pistols"] = {"left": 0, "right": 0}
            else:
                game["pistols"]["left"] = safe_int(game["pistols"].get("left", 0))
                game["pistols"]["right"] = safe_int(game["pistols"].get("right", 0))
            
            cleaned_played.append(game)
        
        data["played"] = cleaned_played
        print(f"  ✓ Cleaned {len(cleaned_played)} maps")
    
    return data

def process_directory(data_dir: str, backup: bool = True):
    """Process all match JSON files in a directory"""
    
    pattern = os.path.join(data_dir, "match_*_veto.json")
    files = glob.glob(pattern)
    
    if not files:
        print(f"❌ No match files found in {data_dir}")
        return
    
    print(f"Found {len(files)} match files to process\n")
    
    fixed_count = 0
    error_count = 0
    
    for filepath in files:
        filename = os.path.basename(filepath)
        print(f"Processing {filename}...")
        
        try:
            # Read original
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Backup if requested
            if backup:
                backup_path = filepath + ".backup"
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"  📦 Backup saved to {os.path.basename(backup_path)}")
            
            # Clean the data
            cleaned_data = clean_match_data(data)
            
            # Save cleaned version
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
            
            print(f"  ✅ Cleaned and saved\n")
            fixed_count += 1
            
        except Exception as e:
            print(f"  ❌ ERROR: {e}\n")
            error_count += 1
    
    print("=" * 80)
    print(f"Summary: {fixed_count} files fixed, {error_count} errors")
    print("=" * 80)
    
    if fixed_count > 0:
        print("\n✅ Next step: Run build_data_json.py to regenerate data.json")
        print("   python build_data_json.py --input ./data --output ./web")

def main():
    parser = argparse.ArgumentParser(description="Clean corrupted match JSON files")
    parser.add_argument("--data-dir", default="./data", help="Directory containing match files")
    parser.add_argument("--no-backup", action="store_true", help="Don't create backup files")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.data_dir):
        print(f"❌ Directory not found: {args.data_dir}")
        return
    
    process_directory(args.data_dir, backup=not args.no_backup)

if __name__ == "__main__":
    main()