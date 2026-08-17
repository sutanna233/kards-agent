$ErrorActionPreference = "Stop"
$outdir = "J:\dev\kards_tmp\raw"   # ASCII-only path to avoid encoding issues
New-Item -ItemType Directory -Path $outdir -Force | Out-Null
$headers = @{ "User-Agent" = "Mozilla/5.0 (KardsCardScraper/3.0; research)" }
$categories = @("Germany_cards","Soviet_Union_cards","USA_cards","Britain_cards","Japan_cards")
foreach ($cat in $categories) {
    $all = @{}
    $rvcont = $null
    $gcont = $null
    $rounds = 0
    do {
        $rounds++
        $u = "https://kards.fandom.com/api.php?action=query&generator=categorymembers&gcmtitle=Category:$cat&gcmtype=page&gcmlimit=50&prop=revisions&rvprop=content&rvslots=main&format=json"
        if ($rvcont) { $u += "&rvcontinue=$([uri]::EscapeDataString($rvcont))" }
        if ($gcont)  { $u += "&gcmcontinue=$([uri]::EscapeDataString($gcont))" }
        $r = Invoke-RestMethod -Uri $u -TimeoutSec 60 -Headers $headers
        if ($null -ne $r.query) {
            foreach ($p in $r.query.pages.PSObject.Properties.GetEnumerator()) {
                $title = $p.Value.title
                $rev = $p.Value.revisions
                if ($null -ne $rev -and $rev.Count -gt 0 -and $null -ne $rev[0].slots) {
                    try { $all[$title] = $rev[0].slots.main.'*' } catch {}
                }
            }
        }
        $rvcont = $null; $gcont = $null
        if ($null -ne $r.continue) {
            if ($null -ne $r.continue.rvcontinue) { $rvcont = $r.continue.rvcontinue }
            if ($null -ne $r.continue.gcmcontinue) { $gcont = $r.continue.gcmcontinue }
        }
        $cnt = ($all.PSObject.Properties | Measure-Object).Count
        Write-Host ("[{0}] r{1} total={2} rvcont={3} gcont={4}" -f $cat,$rounds,$cnt,$([bool]$rvcont),$([bool]$gcont))
        if ($rvcont -or $gcont) { Start-Sleep -Milliseconds 250 }
    } while (($rvcont -or $gcont) -and $rounds -lt 30)
    $all | ConvertTo-Json -Depth 3 | Set-Content -Path "$outdir\$cat.json" -Encoding UTF8
    $cnt = ($all.PSObject.Properties | Measure-Object).Count
    Write-Host "DONE $cat : $cnt cards -> $outdir\$cat.json"
}
