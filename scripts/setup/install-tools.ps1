<#
.SYNOPSIS
  Downloads pinned, checksum-verified DevOps CLIs into .tools\ inside the project (D: drive).
.DESCRIPTION
  - No admin rights, no PATH or registry changes, nothing written to C: except the OS temp-free path we avoid.
  - Every artifact is verified against the publisher's SHA-256 before extraction; a mismatch aborts.
  - Versions follow a 14-day release cooldown (see docs/DECISIONS.md ADR-004).
  - Remove everything with:  Remove-Item -Recurse .tools
  Use the tools in a shell with:  . .\scripts\setup\env.ps1
#>
[CmdletBinding()]
param([string[]]$Only)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is ~10x faster without the progress bar
$root  = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$tools = Join-Path $root '.tools'
$dl    = Join-Path $tools 'downloads'
$bin   = Join-Path $tools 'bin'
New-Item -ItemType Directory -Force $dl, $bin | Out-Null

$tf = '1.16.5'; $trivy = '0.75.0'; $gitleaks = '8.30.1'; $k6 = '2.3.0'
$kind = '0.33.0'; $helm = '4.3.0'; $kubectl = '1.37.1'; $mongo = '8.0.34'

function Get-File([string]$Url, [string]$Name) {
    $out = Join-Path $dl $Name
    if (-not (Test-Path $out)) {
        Write-Host "  downloading $Url"
        Invoke-WebRequest -Uri $Url -OutFile $out -UseBasicParsing
    }
    return $out
}

# Looks up $FileName's hash in a checksum manifest (format: "<sha256>  <name>") or accepts a bare hash.
function Get-ExpectedHash([string]$ManifestText, [string]$FileName) {
    foreach ($line in $ManifestText -split "`n") {
        $parts = $line.Trim() -split '\s+'
        if ($parts.Count -ge 2 -and ($parts[-1].TrimStart('*') -eq $FileName)) { return $parts[0].ToLower() }
        if ($parts.Count -eq 1 -and $parts[0] -match '^[0-9a-f]{64}$') { return $parts[0].ToLower() }
    }
    throw "No checksum for $FileName in manifest"
}

function Assert-Hash([string]$Path, [string]$Expected) {
    $actual = (Get-FileHash -Algorithm SHA256 $Path).Hash.ToLower()
    if ($actual -ne $Expected) {
        Remove-Item $Path -Force
        throw "CHECKSUM MISMATCH for $(Split-Path $Path -Leaf): expected $Expected got $actual (file deleted)"
    }
    Write-Host "  sha256 OK $(Split-Path $Path -Leaf)"
}

function Install-Zip([string]$Name, [string]$Url, [string]$SumsUrl, [string]$Exe, [string]$ZipName) {
    if ($Only -and $Name -notin $Only) { return }
    Write-Host "== $Name"
    if (-not $ZipName) { $ZipName = Split-Path $Url -Leaf }
    $zip = Get-File $Url $ZipName
    $sums = (Invoke-WebRequest -Uri $SumsUrl -UseBasicParsing).Content
    if ($sums -is [byte[]]) { $sums = [Text.Encoding]::UTF8.GetString($sums) }
    Assert-Hash $zip (Get-ExpectedHash $sums $ZipName)
    $dest = Join-Path $tools $Name
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    Expand-Archive $zip -DestinationPath $dest
    $found = Get-ChildItem $dest -Recurse -Filter $Exe | Select-Object -First 1
    Copy-Item $found.FullName (Join-Path $bin $Exe) -Force
}

function Install-Exe([string]$Name, [string]$Url, [string]$SumsUrl, [string]$Exe) {
    if ($Only -and $Name -notin $Only) { return }
    Write-Host "== $Name"
    $file = Get-File $Url $Exe
    $sums = (Invoke-WebRequest -Uri $SumsUrl -UseBasicParsing).Content
    if ($sums -is [byte[]]) { $sums = [Text.Encoding]::UTF8.GetString($sums) }
    Assert-Hash $file (Get-ExpectedHash $sums (Split-Path $Url -Leaf))
    Copy-Item $file (Join-Path $bin $Exe) -Force
}

Install-Zip 'terraform' "https://releases.hashicorp.com/terraform/$tf/terraform_${tf}_windows_amd64.zip" `
    "https://releases.hashicorp.com/terraform/$tf/terraform_${tf}_SHA256SUMS" 'terraform.exe'
Install-Zip 'trivy' "https://github.com/aquasecurity/trivy/releases/download/v$trivy/trivy_${trivy}_windows-64bit.zip" `
    "https://github.com/aquasecurity/trivy/releases/download/v$trivy/trivy_${trivy}_checksums.txt" 'trivy.exe'
Install-Zip 'gitleaks' "https://github.com/gitleaks/gitleaks/releases/download/v$gitleaks/gitleaks_${gitleaks}_windows_x64.zip" `
    "https://github.com/gitleaks/gitleaks/releases/download/v$gitleaks/gitleaks_${gitleaks}_checksums.txt" 'gitleaks.exe'
Install-Zip 'k6' "https://github.com/grafana/k6/releases/download/v$k6/k6-v$k6-windows-amd64.zip" `
    "https://github.com/grafana/k6/releases/download/v$k6/k6-v$k6-checksums.txt" 'k6.exe'
Install-Zip 'helm' "https://get.helm.sh/helm-v$helm-windows-amd64.zip" `
    "https://get.helm.sh/helm-v$helm-windows-amd64.zip.sha256sum" 'helm.exe'
Install-Exe 'kind' "https://github.com/kubernetes-sigs/kind/releases/download/v$kind/kind-windows-amd64" `
    "https://github.com/kubernetes-sigs/kind/releases/download/v$kind/kind-windows-amd64.sha256sum" 'kind.exe'
Install-Exe 'kubectl' "https://dl.k8s.io/release/v$kubectl/bin/windows/amd64/kubectl.exe" `
    "https://dl.k8s.io/release/v$kubectl/bin/windows/amd64/kubectl.exe.sha256" 'kubectl.exe'
Install-Zip 'mongodb' "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-$mongo.zip" `
    "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-$mongo.zip.sha256" 'mongod.exe'

Write-Host "`nInstalled into $bin :"
Get-ChildItem $bin | Select-Object Name, Length | Format-Table -AutoSize
