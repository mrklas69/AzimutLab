param(
    [string]$InputPath = "isom_scan\task_isom_scan.png",
    [string]$OutDir = "isom_scan\black_brown_poc",
    [int]$DarkMax = 130,
    [int]$NeutralSpread = 18,
    [int]$BrownRedMin = 120,
    [int]$BrownRedGreenDiff = 45
)

Add-Type -AssemblyName System.Drawing

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function New-RgbBitmap([int]$w, [int]$h, [byte[]]$bytes) {
    $bmp = [System.Drawing.Bitmap]::new($w, $h, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
    $rect = [System.Drawing.Rectangle]::new(0, 0, $w, $h)
    $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::WriteOnly, $bmp.PixelFormat)
    try {
        [Runtime.InteropServices.Marshal]::Copy($bytes, 0, $data.Scan0, $bytes.Length)
    } finally {
        $bmp.UnlockBits($data)
    }
    return $bmp
}

function Save-RgbBitmap([string]$path, [int]$w, [int]$h, [byte[]]$bytes) {
    $bmp = New-RgbBitmap $w $h $bytes
    try {
        $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $bmp.Dispose()
    }
}

$src = [System.Drawing.Bitmap]::new($InputPath)
try {
    $w = $src.Width
    $h = $src.Height
    $rect = [System.Drawing.Rectangle]::new(0, 0, $w, $h)
    $clone = $src.Clone($rect, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
} finally {
    $src.Dispose()
}

try {
    $data = $clone.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly, $clone.PixelFormat)
    try {
        $stride = [Math]::Abs($data.Stride)
        $raw = [byte[]]::new($stride * $h)
        [Runtime.InteropServices.Marshal]::Copy($data.Scan0, $raw, 0, $raw.Length)
    } finally {
        $clone.UnlockBits($data)
    }

    $blackOverlay = [byte[]]::new($raw.Length)
    $brownOverlay = [byte[]]::new($raw.Length)
    $bothOverlay = [byte[]]::new($raw.Length)
    $blackMask = [byte[]]::new($raw.Length)
    $brownMask = [byte[]]::new($raw.Length)
    [Array]::Copy($raw, $blackOverlay, $raw.Length)
    [Array]::Copy($raw, $brownOverlay, $raw.Length)
    [Array]::Copy($raw, $bothOverlay, $raw.Length)

    $blackPx = 0
    $brownPx = 0
    $overlapPx = 0
    $tile = 256
    $step = 192
    $tileCounts = @{}

    for ($y = 0; $y -lt $h; $y++) {
        $row = $y * $stride
        for ($x = 0; $x -lt $w; $x++) {
            $i = $row + $x * 3
            $b = [int]$raw[$i]
            $g = [int]$raw[$i + 1]
            $r = [int]$raw[$i + 2]
            $mx = [Math]::Max($r, [Math]::Max($g, $b))
            $mn = [Math]::Min($r, [Math]::Min($g, $b))
            $isBlack = ($mx -lt $DarkMax) -and (($mx - $mn) -lt $NeutralSpread)
            $isBrown = ($r -ge $BrownRedMin) -and (($r - $g) -ge $BrownRedGreenDiff) -and ($g -lt 140) -and ($b -lt 100)

            if ($isBlack) {
                $blackPx++
                $blackMask[$i] = 255; $blackMask[$i + 1] = 255; $blackMask[$i + 2] = 255
                $blackOverlay[$i] = [byte]([Math]::Min(255, [int](0.35 * $b + 0.65 * 255))) # B
                $blackOverlay[$i + 1] = [byte]([int](0.35 * $g))                            # G
                $blackOverlay[$i + 2] = [byte]([Math]::Min(255, [int](0.35 * $r + 0.65 * 255))) # R
                $bothOverlay[$i] = $blackOverlay[$i]
                $bothOverlay[$i + 1] = $blackOverlay[$i + 1]
                $bothOverlay[$i + 2] = $blackOverlay[$i + 2]
            }
            if ($isBrown) {
                $brownPx++
                $brownMask[$i] = 255; $brownMask[$i + 1] = 255; $brownMask[$i + 2] = 255
                $brownOverlay[$i] = [byte]([Math]::Min(255, [int](0.35 * $b + 0.65 * 255))) # B = cyan
                $brownOverlay[$i + 1] = [byte]([Math]::Min(255, [int](0.35 * $g + 0.65 * 255))) # G
                $brownOverlay[$i + 2] = [byte]([int](0.35 * $r)) # R
                if (-not $isBlack) {
                    $bothOverlay[$i] = $brownOverlay[$i]
                    $bothOverlay[$i + 1] = $brownOverlay[$i + 1]
                    $bothOverlay[$i + 2] = $brownOverlay[$i + 2]
                }
            }
            if ($isBlack -and $isBrown) { $overlapPx++ }
        }
    }

    Save-RgbBitmap (Join-Path $OutDir "black_neutral_mask.png") $w $h $blackMask
    Save-RgbBitmap (Join-Path $OutDir "brown_reference_mask.png") $w $h $brownMask
    Save-RgbBitmap (Join-Path $OutDir "black_overlay.png") $w $h $blackOverlay
    Save-RgbBitmap (Join-Path $OutDir "brown_overlay.png") $w $h $brownOverlay
    Save-RgbBitmap (Join-Path $OutDir "black_vs_brown_overlay.png") $w $h $bothOverlay

    $stats = [ordered]@{
        input = $InputPath
        size = @{ w = $w; h = $h }
        dark_max = $DarkMax
        neutral_spread = $NeutralSpread
        black_px = $blackPx
        black_share = [Math]::Round($blackPx / ($w * $h), 6)
        brown_px = $brownPx
        brown_share = [Math]::Round($brownPx / ($w * $h), 6)
        overlap_px = $overlapPx
    }
    $stats | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $OutDir "stats.json")
    $stats | ConvertTo-Json -Depth 4
    Write-Output "Výstupy: $OutDir"
} finally {
    $clone.Dispose()
}
