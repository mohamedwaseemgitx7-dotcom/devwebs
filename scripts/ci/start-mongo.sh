#!/usr/bin/env bash
# Start MongoDB 8.0 as a single-node replica set on 127.0.0.1:27017 for CI tests (transactions need a replica set).
set -euo pipefail
docker run -d --name mongo -p 127.0.0.1:27017:27017 mongo:8.0 --replSet rs0 --bind_ip_all >/dev/null
for _ in $(seq 1 60); do
  if docker exec mongo mongosh --quiet --eval "try { rs.status().ok } catch (e) { rs.initiate({_id: 'rs0', members: [{_id: 0, host: '127.0.0.1:27017'}]}).ok }" 2>/dev/null | grep -q 1; then
    # Wait until this node is PRIMARY so writes succeed.
    for _ in $(seq 1 30); do
      docker exec mongo mongosh --quiet --eval "db.hello().isWritablePrimary" | grep -q true && { echo "mongo ready"; exit 0; }
      sleep 1
    done
  fi
  sleep 1
done
echo "mongo did not become ready" >&2
docker logs mongo | tail -50 >&2
exit 1
