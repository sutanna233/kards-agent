$ErrorActionPreference = "Stop"
$rawdir = "J:\dev\kards_tmp\raw"
$outdir = "J:\dev\kards_tmp\parsed"
New-Item -ItemType Directory -Path $outdir -Force | Out-Null

# Field extractor: given wikitext, find infobox section and its parameter lines.
function Get-InfoboxParams([string]$wt) {
    # Locate the {{Infobox ... }} block boundary loosely: take text from {{Infobox to the
    # first standalone }} that ends the block (a line like }} or the pattern directly).
    $idx = $wt.IndexOf("{{Infobox")
    if ($idx -lt 0) { return $null }
    $start = $idx
    # end of block: search for a "}}" that is not inside a nested {{...}} and not after a {{...}} template.
    # Simple approach: scan char by char tracking depth of {{ }}.
    $depth = 1
    $i = $idx + 3
    $len = $wt.Length
    while ($i -lt $len -and $depth -gt 0) {
        $c = $wt.Substring($i,1)
        if ($c -eq "{") {
            if ($i+1 -lt $len -and $wt.Substring($i+1,1) -eq "{") { $depth++; $i++ }
        } elseif ($c -eq "}") {
            if ($i+1 -lt $len -and $wt.Substring($i+1,1) -eq "}") { $depth--; $i++ }
        }
        $i++
    }
    $block = $wt.Substring($start, [Math]::Min($i-$start, $len-$start))
    $params = @{}
    # match each |name=value line
    $rx = [regex]'(?m)(?:^|\|)\s*([^|=\n\r]+?)\s*=\s*([^|\n\r]+)'
    foreach ($mm in $rx.Matches($block)) {
        $k = $mm.Groups[1].Value.Trim()
        $v = $mm.Groups[2].Value.Trim()
        if ($k -match '^abilities|^ability' -or $k -in @('faction','type','rarity','set','cost','op_cost','attack','defense','special')) {
            if ($params.ContainsKey($k)) { $params[$k] = $params[$k] + " " + $v } else { $params[$k] = $v }
        }
    }
    return $params
}

$out = [System.Collections.Generic.List[object]]::new()
foreach ($f in Get-ChildItem "$rawdir\*.json") {
    $nation_key = $f.BaseName -replace "_cards",""
    $o = Get-Content $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($p in $o.PSObject.Properties) {
        $title = $p.Name
        $wt = [string]$p.Value
        $par = Get-InfoboxParams $wt
        if ($null -eq $par) { continue }
        $faction = if ($par.ContainsKey('faction')) { $par['faction'] } else { $nation_key }
        $typeRaw = if ($par.ContainsKey('type')) { $par['type'] } else { "" }
        $cost = if ($par.ContainsKey('cost')) { try { [int]$par['cost'] } catch { 0 } } else { 0 }
        $attack = if ($par.ContainsKey('attack')) { try { [int]$par['attack'] } catch { 0 } } else { 0 }
        $defense = if ($par.ContainsKey('defense')) { try { [int]$par['defense'] } catch { 0 } } else { 0 }
        $abilityParts = @()
        foreach ($pk in $par.Keys) {
            if ($pk -eq 'abilities' -or $pk -match '^ability') { $abilityParts += $par[$pk] }
        }
        $abilities = ($abilityParts -join ', ')
        $special = if ($par.ContainsKey('special')) { $par['special'] } else { "" }
        $rarity = if ($par.ContainsKey('rarity')) { $par['rarity'] } else { "" }
        $set = if ($par.ContainsKey('set')) { $par['set'] } else { "" }
        $row = [ordered]@{
            name = $title
            title = $title
            faction = $faction
            typeRaw = $typeRaw
            cost = $cost
            attack = $attack
            defense = $defense
            abilities = $abilities
            special = $special
            rarity = $rarity
            set = $set
        }
        $out.Add([pscustomobject]$row)
    }
}
# dedupe by name keeping first
$seen = @{}
$uniq = @()
foreach ($row in $out) {
    if ($seen.ContainsKey($row.name)) { continue }
    $seen[$row.name] = $true
    $uniq += $row
}
Write-Host "Total parsed: $($out.Count), unique: $($uniq.Count)"
$uniq | ConvertTo-Json -Depth 5 | Set-Content -Path "$outdir\all_cards.json" -Encoding UTF8
Write-Host "Wrote $outdir\all_cards.json"
