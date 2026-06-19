param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [string]$OutDir = "temp\scan_colors",

    # 0 = bez limitu. Prakticky je u skenu lepší držet top N nebo MinCount.
    [int]$MaxColors = 64,

    [int]$MinCount = 100,

    # 1 = přesné RGB. 8-16 seskupí blízké odstíny ze stejného skenu (tisk/scan/antialias).
    [int]$QuantizeStep = 8,

    [switch]$IncludeNearWhite
)

Add-Type -AssemblyName System.Drawing

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if ($QuantizeStep -lt 1 -or $QuantizeStep -gt 64) {
    throw "QuantizeStep musí být v rozsahu 1..64."
}

function Save-RgbBitmap([string]$Path, [int]$Width, [int]$Height, [byte[]]$Bytes) {
    $bmp = [System.Drawing.Bitmap]::new($Width, $Height, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
    $rect = [System.Drawing.Rectangle]::new(0, 0, $Width, $Height)
    $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::WriteOnly, $bmp.PixelFormat)
    try {
        [Runtime.InteropServices.Marshal]::Copy($Bytes, 0, $data.Scan0, $Bytes.Length)
    } finally {
        $bmp.UnlockBits($data)
    }
    try {
        $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $bmp.Dispose()
    }
}

function Get-ColorBucket([int]$R, [int]$G, [int]$B) {
    $max = [Math]::Max($R, [Math]::Max($G, $B))
    $min = [Math]::Min($R, [Math]::Min($G, $B))
    $spread = $max - $min
    if ($max -gt 245 -and $spread -lt 12) { return "white" }
    if ($max -lt 130 -and $spread -lt 18) { return "black-neutral" }
    if ($R -ge 120 -and ($R - $G) -ge 45 -and $G -lt 150 -and $B -lt 110) { return "brown" }
    if ($B -gt 150 -and $G -gt 120 -and $R -lt 80) { return "cyan-blue" }
    if ($G -gt $R + 30 -and $G -gt $B + 20) { return "green" }
    if ($R -gt 210 -and $G -gt 170 -and $B -lt 190) { return "yellow-orange" }
    if ($R -gt 100 -and $G -gt 110 -and $B -lt 80) { return "olive" }
    return "other"
}

$src = [System.Drawing.Bitmap]::new($InputPath)
try {
    $width = $src.Width
    $height = $src.Height
    $rect = [System.Drawing.Rectangle]::new(0, 0, $width, $height)
    $clone = $src.Clone($rect, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
} finally {
    $src.Dispose()
}

try {
    $data = $clone.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly, $clone.PixelFormat)
    try {
        $stride = [Math]::Abs($data.Stride)
        $raw = [byte[]]::new($stride * $height)
        [Runtime.InteropServices.Marshal]::Copy($data.Scan0, $raw, 0, $raw.Length)
    } finally {
        $clone.UnlockBits($data)
    }

    $hist = @{}
    for ($y = 0; $y -lt $height; $y++) {
        $row = $y * $stride
        for ($x = 0; $x -lt $width; $x++) {
            $i = $row + $x * 3
            $b = [int]$raw[$i]
            $g = [int]$raw[$i + 1]
            $r = [int]$raw[$i + 2]
            if (-not $IncludeNearWhite) {
                $mx = [Math]::Max($r, [Math]::Max($g, $b))
                $mn = [Math]::Min($r, [Math]::Min($g, $b))
                if ($mx -gt 245 -and ($mx - $mn) -lt 12) { continue }
            }
            $qr = [Math]::Min(255, [int]([Math]::Floor($r / $QuantizeStep) * $QuantizeStep))
            $qg = [Math]::Min(255, [int]([Math]::Floor($g / $QuantizeStep) * $QuantizeStep))
            $qb = [Math]::Min(255, [int]([Math]::Floor($b / $QuantizeStep) * $QuantizeStep))
            $key = "{0:X2}{1:X2}{2:X2}" -f $qr, $qg, $qb
            if (-not $hist.ContainsKey($key)) {
                $hist[$key] = [pscustomobject]@{ Count = 0; RSum = 0L; GSum = 0L; BSum = 0L }
            }
            $bucket = $hist[$key]
            $bucket.Count++
            $bucket.RSum += $r
            $bucket.GSum += $g
            $bucket.BSum += $b
        }
    }

    $colors = $hist.GetEnumerator() |
        Where-Object { $_.Value.Count -ge $MinCount } |
        Sort-Object { $_.Value.Count } -Descending
    if ($MaxColors -gt 0) {
        $colors = $colors | Select-Object -First $MaxColors
    }
    $colors = @($colors)

    $manifest = New-Object System.Collections.Generic.List[object]
    $selected = @{}
    for ($rank = 0; $rank -lt $colors.Count; $rank++) {
        $key = [string]$colors[$rank].Key
        $selected[$key] = $rank
        $count = [int]$colors[$rank].Value.Count
        $r = [int][Math]::Round($colors[$rank].Value.RSum / $count)
        $g = [int][Math]::Round($colors[$rank].Value.GSum / $count)
        $b = [int][Math]::Round($colors[$rank].Value.BSum / $count)
        $meanKey = "{0:X2}{1:X2}{2:X2}" -f $r, $g, $b
        $manifest.Add([pscustomobject]@{
            rank = $rank + 1
            rgb = "#$meanKey"
            quantized_rgb = "#$key"
            r = $r
            g = $g
            b = $b
            count = $count
            share = [Math]::Round([double]$count / ($width * $height), 8)
            bucket = Get-ColorBucket $r $g $b
            mask = ("color_{0:D3}_{1}_mask.png" -f ($rank + 1), $meanKey)
            overlay = ("color_{0:D3}_{1}_overlay.png" -f ($rank + 1), $meanKey)
        })
    }

    $manifest | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $OutDir "manifest.csv")
    $manifest | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $OutDir "manifest.json")

    $maskBytes = @()
    $overlayBytes = @()
    for ($rank = 0; $rank -lt $colors.Count; $rank++) {
        $maskBytes += ,([byte[]]::new($raw.Length))
        $overlay = [byte[]]::new($raw.Length)
        [Array]::Copy($raw, $overlay, $raw.Length)
        $overlayBytes += ,$overlay
    }

    for ($y = 0; $y -lt $height; $y++) {
        $row = $y * $stride
        for ($x = 0; $x -lt $width; $x++) {
            $i = $row + $x * 3
            $b = [int]$raw[$i]
            $g = [int]$raw[$i + 1]
            $r = [int]$raw[$i + 2]
            $qr = [Math]::Min(255, [int]([Math]::Floor($r / $QuantizeStep) * $QuantizeStep))
            $qg = [Math]::Min(255, [int]([Math]::Floor($g / $QuantizeStep) * $QuantizeStep))
            $qb = [Math]::Min(255, [int]([Math]::Floor($b / $QuantizeStep) * $QuantizeStep))
            $key = "{0:X2}{1:X2}{2:X2}" -f $qr, $qg, $qb
            if (-not $selected.ContainsKey($key)) { continue }
            $rank = [int]$selected[$key]
            $mask = $maskBytes[$rank]
            $overlay = $overlayBytes[$rank]
            $mask[$i] = 255; $mask[$i + 1] = 255; $mask[$i + 2] = 255
            # Magenta zvýraznění pro vybranou přesnou barvu.
            $overlay[$i] = [byte]([Math]::Min(255, [int](0.35 * $b + 0.65 * 255)))
            $overlay[$i + 1] = [byte]([int](0.35 * $g))
            $overlay[$i + 2] = [byte]([Math]::Min(255, [int](0.35 * $r + 0.65 * 255)))
        }
    }

    foreach ($item in $manifest) {
        $idx = [int]$item.rank - 1
        Save-RgbBitmap (Join-Path $OutDir $item.mask) $width $height $maskBytes[$idx]
        Save-RgbBitmap (Join-Path $OutDir $item.overlay) $width $height $overlayBytes[$idx]
    }

    $summary = [ordered]@{
        input = $InputPath
        size = @{ w = $width; h = $height }
        min_count = $MinCount
        max_colors = $MaxColors
        quantize_step = $QuantizeStep
        include_near_white = [bool]$IncludeNearWhite
        selected_colors = $colors.Count
        selected_px = [int](($colors | ForEach-Object { $_.Value.Count } | Measure-Object -Sum).Sum)
        selected_share = [Math]::Round([double](($colors | ForEach-Object { $_.Value.Count } | Measure-Object -Sum).Sum) / ($width * $height), 6)
    }
    $summary | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $OutDir "summary.json")
    $summary | ConvertTo-Json -Depth 4
    Write-Output "Manifest: $(Join-Path $OutDir 'manifest.csv')"
} finally {
    $clone.Dispose()
}
