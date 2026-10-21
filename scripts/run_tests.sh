#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
python3 -m compileall -q research_review_agent workflow tests
python3 scripts/validate_workflow.py
python3 -m unittest discover -s tests -v

