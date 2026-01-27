#!/usr/bin/env bash
# Wrapper script to run the data pipeline test suite

set -e

echo "========================================================"
echo "🚀 DATA PIPELINE TEST SUITE"
echo "========================================================"
echo "Starting tests at $(date)"
echo ""

# Activate virtual environment if present
if [ -d ".venv" ]; then
    echo "Using virtual environment..."
    source .venv/bin/activate
fi

# Install test dependencies if needed
echo "Installing/Updating test dependencies..."
pip install -q pytest pytest-html requests pandas pyarrow minio psycopg2-binary pika || {
    echo "⚠️ Failed to install dependencies. Please ensure pip is available."
    exit 1
}

echo ""
echo "Running Pytest..."
echo "--------------------------------------------------------"

# Run tests with verbose output
python -m pytest tests/ \
    -v \
    --tb=short \
    --html=test_report.html \
    --self-contained-html \
    || echo "⚠️ Some tests failed. Check report."

echo "--------------------------------------------------------"
echo "✅ Tests completed."
echo "Report generated: test_report.html (if pytest-html installed)"
