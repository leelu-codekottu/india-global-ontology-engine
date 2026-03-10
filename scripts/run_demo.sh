#!/bin/bash
# ===========================================
# India Global Ontology Engine - Demo Runner
# ===========================================
# Usage: bash scripts/run_demo.sh
# Requires: Python 3.10+, Memgraph running on localhost:7687

set -e

echo "============================================"
echo "  India Global Ontology Engine - Demo"
echo "============================================"

cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo ""
echo "[1/6] Installing dependencies..."
pip install -r requirements.txt --quiet 2>/dev/null || pip install -r requirements.txt

echo ""
echo "[2/6] Setting up graph (constraints + bootstrap)..."
python -c "
import sys; sys.path.insert(0, '.')
from pipeline import run_step_1_graph_setup
run_step_1_graph_setup()
"

echo ""
echo "[3/6] Loading Data Commons bootstrap..."
python -c "
import sys; sys.path.insert(0, '.')
from pipeline import run_step_2_datacommons_bootstrap
run_step_2_datacommons_bootstrap()
"

echo ""
echo "[4/6] Running article extraction pipeline (sample articles)..."
python -c "
import sys; sys.path.insert(0, '.')
from pipeline import run_step_4_article_pipeline
run_step_4_article_pipeline(use_sample=True, max_articles=5)
"

echo ""
echo "[5/6] Running verification..."
python -c "
import sys; sys.path.insert(0, '.')
from pipeline import run_step_5_verification
run_step_5_verification()
"

echo ""
echo "[6/6] Running demo query..."
python -c "
import sys; sys.path.insert(0, '.')
from pipeline import run_step_6_demo_query
run_step_6_demo_query()
"

echo ""
echo "============================================"
echo "  Demo Complete!"
echo "============================================"
echo ""
echo "Results:"
echo "  - Graph snapshot: data/graph_snapshot.json"
echo "  - Demo result:    data/demo_result.json"
echo "  - Logs:           data/logs/"
echo ""
echo "To start the API server:"
echo "  python -m uvicorn src.ui.api:app --host 0.0.0.0 --port 8000"
echo ""
echo "To start the UI (in src/ui/frontend/):"
echo "  cd src/ui/frontend && npm install && npm run dev"
echo ""
