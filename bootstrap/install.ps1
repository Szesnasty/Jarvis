Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$NodeLocalDir = Join-Path $ProjectRoot '.node-local'
$NodeCacheDir = Join-Path $NodeLocalDir 'cache'

function Write-Info([string]$Message) {
  Write-Host "[bootstrap] $Message"
}

function Get-NodeMajor([string]$VersionText) {
  if ($VersionText -notmatch '^v(\d+)\.\d+\.\d+$') {
    return $null
  }
  return [int]$Matches[1]
}

function Get-SystemNpmCommand {
  try {
    $nodeVersion = (& node --version).Trim()
    $nodeMajor = Get-NodeMajor $nodeVersion
    if ($null -eq $nodeMajor -or $nodeMajor -lt 20) {
      return $null
    }
    $npmCommand = (Get-Command npm -ErrorAction Stop).Source
    return $npmCommand
  } catch {
    return $null
  }
}

function Resolve-NodeArch {
  $arch = $env:PROCESSOR_ARCHITECTURE
  if ($arch -eq 'ARM64') {
    return 'arm64'
  }
  return 'x64'
}

function Download-LocalNode {
  $answer = Read-Host 'Node.js 20+ not found. Download a local copy now (~50 MB, no admin required)? [Y/n]'
  if ([string]::IsNullOrWhiteSpace($answer)) {
    $answer = 'Y'
  }
  if ($answer.ToLowerInvariant() -notin @('y', 'yes')) {
    throw 'Aborted. Install Node.js 20+ manually from https://nodejs.org/'
  }

  $arch = Resolve-NodeArch
  New-Item -ItemType Directory -Path $NodeCacheDir -Force | Out-Null

  Write-Info 'Resolving latest Node.js 20 release'
  $releases = Invoke-RestMethod -Uri 'https://nodejs.org/dist/index.json'
  $release = $releases | Where-Object { $_.version -like 'v20.*' -and $_.lts } | Select-Object -First 1
  if (-not $release) {
    $release = $releases | Where-Object { $_.version -like 'v20.*' } | Select-Object -First 1
  }
  if (-not $release) {
    throw 'Could not resolve latest Node.js 20 release.'
  }

  $version = $release.version
  $fileName = "node-$version-win-$arch.zip"
  $url = "https://nodejs.org/dist/$version/$fileName"
  $archivePath = Join-Path $NodeCacheDir $fileName
  $extractDir = Join-Path $NodeLocalDir "node-$version-win-$arch"

  if (-not (Test-Path $archivePath)) {
    Write-Info "Downloading $fileName"
    Invoke-WebRequest -Uri $url -OutFile $archivePath
  } else {
    Write-Info "Using cached archive $fileName"
  }

  if (-not (Test-Path $extractDir)) {
    Write-Info 'Extracting Node.js archive'
    New-Item -ItemType Directory -Path $NodeLocalDir -Force | Out-Null
    Expand-Archive -Path $archivePath -DestinationPath $NodeLocalDir -Force
  }

  $npmCmd = Join-Path $extractDir 'npm.cmd'
  if (-not (Test-Path $npmCmd)) {
    throw 'Local Node.js install appears incomplete.'
  }

  return $npmCmd
}

$npmToUse = Get-SystemNpmCommand
if ($null -eq $npmToUse) {
  $npmToUse = Download-LocalNode
  Write-Info "Using local Node.js bootstrap from $npmToUse"
} else {
  Write-Info "Using system Node.js bootstrap from $npmToUse"
}

Push-Location $ProjectRoot
try {
  & $npmToUse run wake-up-jarvis
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
