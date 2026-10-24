# Dot-source in a PowerShell session to use the project-local tools:  . .\scripts\setup\env.ps1
# Only affects the current shell. Keeps caches on D: instead of the (nearly full) C: drive.
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$env:PATH = "$root\.tools\bin;$root\.tools\awscli\Amazon\AWSCLIV2;$env:PATH"
$env:UV_CACHE_DIR = "$root\.cache\uv"
$env:npm_config_cache = "$root\.cache\npm"
$env:PLAYWRIGHT_BROWSERS_PATH = "$root\.cache\ms-playwright"
$env:TRIVY_CACHE_DIR = "$root\.cache\trivy"
$env:K6_WEB_DASHBOARD = 'false'
$env:KUBECONFIG = "$root\.tools\kube\config"
$env:TF_PLUGIN_CACHE_DIR = "$root\.cache\terraform-plugins"
New-Item -ItemType Directory -Force $env:TF_PLUGIN_CACHE_DIR, (Split-Path $env:KUBECONFIG) | Out-Null
