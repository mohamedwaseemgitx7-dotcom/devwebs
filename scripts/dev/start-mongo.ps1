<#
.SYNOPSIS
  Starts the portable local MongoDB as a single-node replica set (rs0) with data on D:.
  Replica-set mode is required for multi-document transactions (used by checkout).
  Binds to 127.0.0.1 only. Stop with: scripts\dev\stop-mongo.ps1
#>
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$mongod = Join-Path $root '.tools\bin\mongod.exe'
$data = Join-Path $root '.data\mongo'
$logDir = Join-Path $root '.data\logs'
New-Item -ItemType Directory -Force $data, $logDir | Out-Null

if (Get-NetTCPConnection -LocalPort 27017 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host 'mongod already listening on 127.0.0.1:27017'
} else {
    Start-Process -FilePath $mongod -WindowStyle Hidden -ArgumentList @(
        '--dbpath', $data, '--bind_ip', '127.0.0.1', '--port', '27017', '--replSet', 'rs0',
        '--logpath', (Join-Path $logDir 'mongod.log'), '--logappend', '--wiredTigerCacheSizeGB', '0.5'
    )
    for ($i = 0; $i -lt 30 -and -not (Get-NetTCPConnection -LocalPort 27017 -State Listen -ErrorAction SilentlyContinue); $i++) {
        Start-Sleep -Milliseconds 500
    }
    Write-Host 'mongod started on 127.0.0.1:27017 (replSet rs0)'
}

# Initiate the replica set once (idempotent).
$py = Join-Path $root 'apps\flashcart-api\.venv\Scripts\python.exe'
& $py -c @"
from pymongo import MongoClient
from pymongo.errors import OperationFailure
c = MongoClient('mongodb://127.0.0.1:27017/?directConnection=true', serverSelectionTimeoutMS=10000)
try:
    c.admin.command('replSetInitiate', {'_id': 'rs0', 'members': [{'_id': 0, 'host': '127.0.0.1:27017'}]})
    print('replica set rs0 initiated')
except OperationFailure as e:
    print('replica set already initiated' if e.code == 23 else f'replSetInitiate: {e}')
import time
for _ in range(40):
    if c.admin.command('hello').get('isWritablePrimary'): break
    time.sleep(0.5)
print('primary ready:', c.admin.command('hello').get('isWritablePrimary'))
"@
