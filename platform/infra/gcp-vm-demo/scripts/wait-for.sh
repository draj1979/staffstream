#!/bin/sh
# Blocks until every host:port pair given is TCP-reachable (exponential
# backoff, capped), then execs the remaining arguments. Bind-mounted into
# every DB/Redis-backed service in backend-compose.yml (see that file's
# top comment) rather than baked into the images — this is a deployment-
# layer concern specific to the two-VM split (db-vm is now a network hop
# away instead of a local socket/container-network hostname), not
# something the application images themselves need to know about.
#
# Uses python3 for the actual TCP check (every image here is a Python
# service, so it's always present) instead of nc/netcat, which the
# python:3.12-slim base images don't include by default.
#
# Usage: wait-for.sh host1:port1 [host2:port2 ...] -- command [args...]
set -eu

hosts=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --)
      shift
      break
      ;;
    *)
      hosts="$hosts $1"
      shift
      ;;
  esac
done

delay=1
max_delay=15
for hp in $hosts; do
  host="${hp%%:*}"
  port="${hp##*:}"
  echo "wait-for: waiting for ${host}:${port}..."
  until python3 -c "
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(('${host}', ${port}))
except OSError:
    sys.exit(1)
else:
    s.close()
    sys.exit(0)
"; do
    echo "wait-for: ${host}:${port} not reachable yet, retrying in ${delay}s..."
    sleep "$delay"
    delay=$((delay * 2))
    if [ "$delay" -gt "$max_delay" ]; then
      delay=$max_delay
    fi
  done
  echo "wait-for: ${host}:${port} is up."
  delay=1
done

exec "$@"
