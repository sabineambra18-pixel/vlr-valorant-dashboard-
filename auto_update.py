import os
import shutil
import json
import sys

# Import functions from your existing scripts
# (This works because they are in the same folder)
try:
    from fetch_team_ids import get_match_ids, TEAM_URLS
    import vlr_veto_and_result
    import build_data_json
except ImportError as e:
    print("Error: Could not import your other scripts.")
    print(f"Make sure fetch_team_ids.py, vlr_veto_and_result.py, and build_data_json.py are in this folder.")
    print(f"Details: {e}")
    sys.exit(1)

# Configuration
DATA_DIR = "./data"
WEB_DIR = "./web"

def main():
    print("="*50)
    print("   VALORANT DASHBOARD AUTO-UPDATER")
    print("="*50)

    # 1. CLEANUP: Move root json files to data folder
    print(f"\n[1/4] Checking file organization...")
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"Created {DATA_DIR} folder.")

    moved_count = 0
    for filename in os.listdir("."):
        if filename.startswith("match_") and filename.endswith(".json"):
            source = os.path.join(".", filename)
            destination = os.path.join(DATA_DIR, filename)
            
            # If file exists in dest, remove it first to ensure overwrite with latest
            if os.path.exists(destination):
                os.remove(destination)
                
            shutil.move(source, destination)
            moved_count += 1
    
    if moved_count > 0:
        print(f"Moved {moved_count} match files to {DATA_DIR} to keep folder tidy.")
    else:
        print("Folder structure looks good.")

    # 2. FETCH IDs
    print(f"\n[2/4] Checking for new matches from {len(TEAM_URLS)} teams...")
    # Pass the list of URLs from your config file
    found_ids = get_match_ids(TEAM_URLS)
    
    # 3. SCRAPE MISSING MATCHES
    print(f"\n[3/4] Syncing matches...")
    newly_scraped = 0
    errors = 0
    
    for match_id in found_ids:
        # Check if we already have this match in the data folder
        expected_file = os.path.join(DATA_DIR, f"match_{match_id}_veto.json")
        
        if not os.path.exists(expected_file):
            print(f"Downloading new match: {match_id}...")
            try:
                # Call the scraper function directly
                # We force headless=True so it runs in background
                vlr_veto_and_result.run_one(int(match_id), DATA_DIR, headless=True)
                newly_scraped += 1
            except Exception as e:
                print(f"Failed to scrape {match_id}: {e}")
                errors += 1
        # Else: silently skip matches we already have
    
    if newly_scraped == 0:
        print("All matches are already up to date!")
    else:
        print(f"Successfully downloaded {newly_scraped} new matches.")
        
    if errors > 0:
        print(f"WARNING: {errors} matches failed to download.")

    # 4. REBUILD DATABASE
    print(f"\n[4/4] Updating Dashboard Database...")
    matches = build_data_json.load_matches(DATA_DIR)
    data = build_data_json.summarize_for_web(matches)
    
    if not os.path.exists(WEB_DIR):
        os.makedirs(WEB_DIR)
        
    out_path = os.path.join(WEB_DIR, "data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print("\n" + "="*50)
    print("   UPDATE COMPLETE! ")
    print("="*50)
    print(f"Total Teams: {len(data['teams'])}")
    print(f"Total Matches: {len(data['matches'])}")
    print("\nYou can now refresh your Streamlit Dashboard.")

if __name__ == "__main__":
    main()