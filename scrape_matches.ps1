# scrape_matches.ps1
# Scrape all EMEA matches

$matchIds = @(
    510145, 510149, 510153, 510155, 511548, 511554, 511566, 511573, 530926, 530930, 542201, 542202, 542264, 542268, 542270, 542279, 542272,
    511550, 511551, 511564, 511573, 511581, 530928, 530932, 530935, 542203, 542209,
    511549, 511551, 511566, 511571, 530927, 530933,
    510149, 511548, 511563, 511571, 511581, 530926,
    511550, 511554, 511563, 511567, 511577,
    511549, 511564, 511569, 511576,
    511552, 511562, 511570,
    511552, 511567, 530929, 530931,
    511553, 511569, 530929,
    510143, 511576, 530931, 530932, 530934,
    511553, 511562, 511579, 530928, 530930, 530933, 530934, 530935, 542212, 542267, 542277,
    510143, 510150, 510154, 510155, 511577, 511579, 530927, 542265, 542277, 542278,
    490752, 490758, 503468, 513741, 514826, 521657, 522007, 524280, 524281, 524284, 524703, 524704, 524938, 524940, 524943, 524947, 528616, 528617,
    531573, 532791, 532792, 532795, 532796, 532798, 532800, 532801, 534743, 534747, 534748, 535402, 535403, 535405, 535406,
    538425, 538430, 538432, 538437, 538439, 538441, 541686,
    565302, 565303, 565305, 565307, 565308, 565310
)

# Remove duplicates and sort
$uniqueMatches = $matchIds | Select-Object -Unique | Sort-Object

Write-Host "Total unique matches to scrape: $($uniqueMatches.Count)"
Write-Host "Starting scrape..."
Write-Host ""

$successful = 0
$failed = @()
$total = $uniqueMatches.Count

foreach ($matchId in $uniqueMatches) {
    $current = $successful + $failed.Count + 1
    Write-Host "[$current/$total] Scraping match $matchId..."
    
    python vlr_veto_and_result.py $matchId
    
    if ($LASTEXITCODE -eq 0) {
        $successful++
        Write-Host "  Success"
    } else {
        $failed += $matchId
        Write-Host "  Failed"
    }
    
    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host "=================================================="
Write-Host "Scraping complete!"
Write-Host "Successful: $successful/$total"
Write-Host "Failed: $($failed.Count)"

if ($failed.Count -gt 0) {
    Write-Host ""
    Write-Host "Failed match IDs:"
    Write-Host ($failed -join ", ")
}

Write-Host ""
Write-Host "Now run: python build_data_json.py --input ./data --output ./web"