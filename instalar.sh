#!/bin/bash
# Empacota o Splinter com a biblioteca Python do Mage Core e instala no console.
#   ./instalar.sh [host-ssh] [pasta-do-sdk]    (padrão: r36s e ../r36s-a11y-sdk)
set -euo pipefail
HOST=${1:-r36s}
HERE=$(cd "$(dirname "$0")" && pwd)
SDK=${2:-$HERE/../r36s-a11y-sdk}
SDK_PY="$SDK/python/r36s_a11y"
[ -d "$SDK_PY" ] || SDK_PY="$HERE/r36s_a11y"
[ -d "$SDK_PY" ] || { echo "Mage Core não encontrado."; exit 1; }
PKG=$(mktemp -d); trap 'rm -rf "$PKG"' EXIT
mkdir -p "$PKG/splinter"
cp -r "$HERE/game.json" "$HERE/main.py" "$HERE/leitor" "$HERE/sounds" "$SDK_PY" "$PKG/splinter/"
find "$PKG" -name __pycache__ -prune -exec rm -rf {} +
sed -i 's/"id": "splinter"/"id": "splinter"/' "$PKG/splinter/game.json"
tar -C "$PKG" -czf - splinter | ssh "$HOST" '
  set -e; mkdir -p /roms/a11y/games /roms/a11y/livros; cd /roms/a11y/games
  rm -rf splinter && tar -xzmf - && echo instalado
  echo "Coloque os .epub em /roms/a11y/livros"'
