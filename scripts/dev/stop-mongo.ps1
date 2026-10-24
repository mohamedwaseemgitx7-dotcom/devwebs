# Cleanly shuts down the local mongod started by start-mongo.ps1 (data in .data\mongo is kept).
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$py = Join-Path $root 'apps\flashcart-api\.venv\Scripts\python.exe'
& $py -c @"
from pymongo import MongoClient
from pymongo.errors import AutoReconnect, ConnectionFailure, ServerSelectionTimeoutError
try:
    MongoClient('mongodb://127.0.0.1:27017/?directConnection=true', serverSelectionTimeoutMS=3000).admin.command('shutdown')
except (AutoReconnect, ConnectionFailure):
    print('mongod shut down')
except ServerSelectionTimeoutError:
    print('mongod was not running')
"@
