#!/usr/bin/env bash
# Render build script for Automa
set -o errexit

echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Installing Playwright Chromium browser ==="
playwright install chromium

echo "=== Ensuring data directories exist ==="
mkdir -p data content/media content/published content/rejected content/queue logs

echo "=== Build complete ==="

