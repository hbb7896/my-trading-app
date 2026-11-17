# Package the approved master artwork at platform-required pixel sizes.
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$projectRoot=Split-Path $PSScriptRoot -Parent
$sourcePath=Join-Path $projectRoot 'branding/tm-icon-master.png'
$sourceImage=[System.Drawing.Image]::FromFile($sourcePath)
function Write-Icon([string]$relativePath,[int]$pixels) {
  $destination=Join-Path $projectRoot $relativePath
  [System.IO.Directory]::CreateDirectory((Split-Path $destination -Parent)) | Out-Null
  $bitmap=New-Object System.Drawing.Bitmap($pixels,$pixels)
  $graphics=[System.Drawing.Graphics]::FromImage($bitmap)
  try {
    $graphics.InterpolationMode=[System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.CompositingQuality=[System.Drawing.Drawing2D.CompositingQuality]::HighQuality
    $graphics.DrawImage($sourceImage,0,0,$pixels,$pixels)
    $bitmap.Save($destination,[System.Drawing.Imaging.ImageFormat]::Png)
  } finally {$graphics.Dispose();$bitmap.Dispose()}
}
try {
  Write-Icon 'web/icons/tm-icon-v1-192.png' 192
  Write-Icon 'web/icons/tm-icon-v1-512.png' 512
  Write-Icon 'web/icons/tm-maskable-v1-192.png' 192
  Write-Icon 'web/icons/tm-maskable-v1-512.png' 512
  Write-Icon 'web/icons/tm-apple-v1-180.png' 180
  Write-Icon 'web/tm-favicon-v1.png' 64
  Write-Icon 'assets/branding/tm-icon.png' 128
  Write-Icon 'android/app/src/main/res/drawable/tm_brand.png' 512
  foreach($variant in @(@('mdpi',48),@('hdpi',72),@('xhdpi',96),@('xxhdpi',144),@('xxxhdpi',192))) {
    Write-Icon ('android/app/src/main/res/mipmap-'+$variant[0]+'/ic_launcher.png') $variant[1]
  }
} finally {$sourceImage.Dispose()}
Write-Output 'Approved TM artwork packaged for web and Android.'
