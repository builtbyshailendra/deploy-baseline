#!/usr/bin/env bash
# Write a backup of the cluster's database to stdout.
#
#   scripts/backup.sh > backup.sql
#
# --clean adds DROP statements, so scripts/restore.sh can load the backup over
# a database that already has tables.
set -euo pipefail
kubectl -n serviceops exec statefulset/postgres -- \
  pg_dump -U postgres --clean --if-exists --no-owner serviceops
