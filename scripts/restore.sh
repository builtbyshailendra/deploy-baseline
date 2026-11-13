#!/usr/bin/env bash
# Replace the cluster's database with a backup read from stdin.
#
#   scripts/restore.sh < backup.sql
#
# Everything written since the backup is lost, so the script asks first unless
# CONFIRM=yes is set.
set -euo pipefail
if [ "${CONFIRM:-}" != "yes" ]; then
  read -r -p "Replace the serviceops database with this backup? Type yes: " answer < /dev/tty
  [ "$answer" = "yes" ] || { echo "Not restored." >&2; exit 1; }
fi
kubectl -n serviceops exec -i statefulset/postgres -- \
  psql -U postgres --quiet -v ON_ERROR_STOP=1 --single-transaction serviceops
echo "Restored." >&2
