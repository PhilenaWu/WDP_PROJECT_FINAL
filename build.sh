#!/usr/bin/env bash
# Render build step for Genlink.
set -o errexit

echo "==> Installing Python dependencies"
pip install --upgrade pip
pip install -r requirements.txt

# The repo ships stockfish.exe, which is a Windows binary and cannot run on
# Render's Linux hosts. Fetch a Linux build instead. If this fails the app
# still works: routes/chess.py falls back to a random legal move when no
# engine is found, so the deploy is never blocked on it.
echo "==> Fetching Stockfish for Linux"
mkdir -p bin
SF_URL="https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64-avx2.tar"

if curl -fsSL --retry 2 --max-time 120 -o /tmp/stockfish.tar "$SF_URL"; then
  tar -xf /tmp/stockfish.tar -C /tmp
  SF_BIN="$(find /tmp/stockfish -type f -name 'stockfish-ubuntu-*' | head -n 1)"
  if [ -n "$SF_BIN" ]; then
    cp "$SF_BIN" bin/stockfish
    chmod +x bin/stockfish
    echo "    Stockfish installed at bin/stockfish"
  else
    echo "    WARNING: archive downloaded but no binary found; bot will play random legal moves"
  fi
else
  echo "    WARNING: could not download Stockfish; bot will play random legal moves"
fi

echo "==> Build complete"
