#!/usr/bin/env bash
# Spielt server/ auf LXC 192 (ssh pgh-wartung) ein: Code nach /opt/pgh-wartung/app, venv, Migrationen, Neustart.
# Daten bleiben unberührt in /var/lib/pgh-wartung (nur Benutzer "wartung").
set -euo pipefail
cd "$(dirname "$0")"
( cd server && ../.venv-test/bin/python -m pytest -q ) 2>/dev/null || { echo "Tests (lokal) fehlgeschlagen oder .venv-test fehlt – Abbruch"; exit 1; }
STAND=$(git describe --always --dirty)
tar -C server --exclude '__pycache__' --exclude 'tests' -czf - . | ssh pgh-wartung \
  'rm -rf /opt/pgh-wartung/app.neu && mkdir /opt/pgh-wartung/app.neu && tar -C /opt/pgh-wartung/app.neu -xzf - && rm -rf /opt/pgh-wartung/app && mv /opt/pgh-wartung/app.neu /opt/pgh-wartung/app'
ssh pgh-wartung "set -e
  echo '$STAND' > /opt/pgh-wartung/app/STAND
  [ -x /opt/pgh-wartung/venv/bin/python ] || python3 -m venv /opt/pgh-wartung/venv
  /opt/pgh-wartung/venv/bin/pip install -q -r /opt/pgh-wartung/app/requirements.txt
  cd /opt/pgh-wartung/app && sudo -u wartung WARTUNG_DATEN=/var/lib/pgh-wartung /opt/pgh-wartung/venv/bin/python -m wartung migrieren
  systemctl restart pgh-wartung && sleep 2 && systemctl is-active pgh-wartung"
echo "Eingespielt: $STAND"
