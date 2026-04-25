#!/usr/bin/env python3
"""Scrape all EMEA matches from the match_ids list"""

import subprocess
import time

match_ids = [
    # Original EMEA matches
    510145, 510149, 510153, 510155, 511548, 511554, 511566, 511573, 530926, 530930, 542201, 542202, 542264, 542268, 542270, 542279, 542272,
    511550, 511551, 511564, 511573, 511581, 530928, 530932, 530935, 542203, 542209, 542281,
    511549, 511551, 511566, 511571, 511578, 530927, 530933,
    510149, 511548, 511559, 511563, 511571, 511581, 530926,
    511550, 511554, 511563, 511567, 511577,
    511549, 511559, 511564, 511569, 511576,
    511552, 511557, 511562, 511570, 511578,
    511552, 511556, 511567, 511574, 530929, 530931, 542222, 542280,
    511553, 511560, 511569, 511574, 530929,
    510143, 511557, 511561, 511576, 530931, 530932, 530934,
    511553, 511556, 511561, 511562, 511579, 530928, 530930, 530933, 530934, 530935, 542212, 542221, 542240, 542267, 542277,
    510143, 510150, 510154, 510155, 511560, 511577, 511579, 530927, 542219, 542222, 542265, 542277, 542278,
    # New matches
    490752, 490758, 503468, 513741, 514826, 521657, 522007, 524280, 524281, 524284, 524703, 524704, 524938, 524940, 524943, 524947, 525080, 528616, 528617,
    530651, 530652, 531573, 532791, 532792, 532795, 532796, 532798, 532800, 532801, 534743, 534747, 534748, 535402, 535403, 535405, 535406,
    538425, 538430, 538432, 538433, 538436, 538437, 538439, 538441, 540997, 541686, 543076, 543078, 543081, 543083, 543173, 545624,
    555492, 555495, 555496, 555497, 555498, 555505, 556025, 560961, 560963, 560965, 560968, 560970, 560971, 560972, 560974,
    564937, 564939, 564940, 564943, 564944, 564945, 564949, 564950, 564955, 564957, 564959, 564960,
    565254, 565260, 565265, 565302, 565303, 565304, 565305, 565306, 565307, 565308, 565310
]
# Remove duplicates and sort
unique_matches = sorted(set(match_ids))

print(f"Total unique matches to scrape: {len(unique_matches)}")
print(f"Starting scrape...\n")

successful = 0
failed = []

for i, match_id in enumerate(unique_matches, 1):
    print(f"[{i}/{len(unique_matches)}] Scraping match {match_id}...")
    
    try:
        result = subprocess.run(
            ['python', 'vlr_veto_and_result.py', str(match_id)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            successful += 1
            print(f"  ✓ Success")
        else:
            failed.append(match_id)
            print(f"  ✗ Failed: {result.stderr[:100]}")
    
    except subprocess.TimeoutExpired:
        failed.append(match_id)
        print(f"  ✗ Timeout")
    except Exception as e:
        failed.append(match_id)
        print(f"  ✗ Error: {e}")
    
    # Small delay to be nice to the server
    time.sleep(1)

print(f"\n{'='*50}")
print(f"Scraping complete!")
print(f"Successful: {successful}/{len(unique_matches)}")
print(f"Failed: {len(failed)}")

if failed:
    print(f"\nFailed match IDs: {failed}")

print(f"\nNow run: python build_data_json.py --input ./data --output ./web")