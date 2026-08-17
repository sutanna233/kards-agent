$ErrorActionPreference = "Stop"
$data = Get-Content "J:\dev\kards_tmp\parsed\all_cards.json" -Raw -Encoding UTF8 | ConvertFrom-Json

function NormNation([string]$n) {
    switch -Regex ($n) {
        'Germany'       { return 'Germany' }
        'Soviet'        { return 'Soviet' }
        'USA|United'    { return 'USA' }
        'Britain|UK'    { return 'Britain' }
        'Japan'         { return 'Japan' }
        default         { return $n }
    }
}

function TypeClass([string]$t) {
    if ($t -match 'Countermeasure') { return 'Countermeasure' }
    if ($t -eq 'Order') { return 'Order' }
    if ($t -match 'Infantry|Tank|Artillery|Fighter|Bomber|Naval') { return 'Unit' }
    return 'Other'
}

function AbilList([string]$a) {
    $clean = $a -split '[,;]' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    # Return recognizable keyword tokens, filtering heavy-armor to its base keyword
    $out = @()
    foreach ($c in $clean) {
        if ($c -match '^Ambush') { $out += 'Ambush' }
        elseif ($c -match '^Blitz') { $out += 'Blitz' }
        elseif ($c -match '^Fury') { $out += 'Fury' }
        elseif ($c -match '^Guard') { $out += 'Guard' }
        elseif ($c -match '^Smokescreen') { $out += 'Smokescreen' }
        elseif ($c -match '^Heavy Armor') { $out += 'Heavy Armor' }
        elseif ($c -eq 'Deployment') { $out += 'Deployment' }
    }
    return ($out | Select-Object -Unique)
}

function BuildEffect([string]$a, [string]$s) {
    $parts = @()
    if ($a) { $parts += $a }
    if ($s) { $parts += $s }
    return ($parts -join '. ')
}

$nations = @('Germany','Soviet','USA','Britain','Japan')
$out = [System.Collections.Generic.List[object]]::new()
$used = @{}
$id = 0

foreach ($nat in $nations) {
    $natCards = @($data | Where-Object {
        (NormNation $_.faction) -eq $nat `
        -and $_.title -notmatch '\(discarded\)' `
        -and $_.typeRaw -ne 'HQ' `
        -and [int]$_.cost -gt 0 `
        -and $_.abilities -notmatch '}}' -and $_.special -notmatch '}}'
    })
    $unitPool = @($natCards | Where-Object { (TypeClass $_.typeRaw) -eq 'Unit' })
    $orderPool = @($natCards | Where-Object { (TypeClass $_.typeRaw) -eq 'Order' })
    $cmPool   = @($natCards | Where-Object { (TypeClass $_.typeRaw) -eq 'Countermeasure' })

    # Units: pick up to 12 balanced across cost bands (early/mid/late)
    $unitPicked = @()
    $bandUsed = @{ early=0; mid=0; late=0 }
    $subSeen = @{}
    foreach ($c in ($unitPool | Sort-Object cost)) {
        if ($unitPicked.Count -ge 12) { break }
        $cost = [int]$c.cost
        $band = if ($cost -le 2) { 'early' } elseif ($cost -le 5) { 'mid' } else { 'late' }
        if ($bandUsed[$band] -ge 5) { continue }                      # cap per band
        if ($subSeen[$c.typeRaw] -ge 5) { continue }                   # cap per subtype
        if ($used.ContainsKey($c.title)) { continue }
        $used[$c.title] = $true
        $bandUsed[$band]++
        $subSeen[$c.typeRaw] = 1 + $subSeen[$c.typeRaw]
        $unitPicked += $c
    }
    # Orders: up to 6 spread by cost
    $orderPicked = @()
    foreach ($c in ($orderPool | Sort-Object cost)) {
        if ($orderPicked.Count -ge 6) { break }
        if ($used.ContainsKey($c.title)) { continue }
        $used[$c.title] = $true
        $orderPicked += $c
    }
    # Countermeasures: up to 4
    $cmPicked = @()
    foreach ($c in $cmPool) {
        if ($cmPicked.Count -ge 4) { break }
        if ($used.ContainsKey($c.title)) { continue }
        $used[$c.title] = $true
        $cmPicked += $c
    }

    foreach ($c in @($unitPicked + $orderPicked + $cmPicked)) {
        $id++
        $tc = TypeClass $c.typeRaw
        $row = [pscustomobject]@{
            id        = "k$nat-$id"
            name      = $c.title
            type      = $tc
            unitType  = if ($tc -eq 'Unit') { $c.typeRaw } else { $null }
            nation    = $nat
            cost      = [int]$c.cost
            attack    = [int]$c.attack
            defense   = [int]$c.defense
            abilities = @(AbilList $c.abilities)
            abilityText = (BuildEffect $c.abilities $c.special)
            rarity    = $c.rarity
            set       = $c.set
        }
        $out.Add($row)
    }
    Write-Host "[$nat] units=$($unitPicked.Count) orders=$($orderPicked.Count) cm=$($cmPicked.Count)"
}

Write-Host "TOTAL=$($out.Count)"
$out | ConvertTo-Json -Depth 6 | Set-Content -Path "J:\dev\kards_tmp\parsed\cards_curated.json" -Encoding UTF8
Write-Host "wrote cards_curated.json"
