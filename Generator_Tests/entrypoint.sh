#!/bin/bash
set -e

PROJECT="${INPUT_PROJECT:-.}"                  
TARGET_FUNCTION="${INPUT_TARGET_FUNCTION:-}"
TARGET_CLASS="${INPUT_TARGET_CLASS:-}"
TARGET_FILE="${INPUT_TARGET_FILE:-}"
TARGET_DIR="${INPUT_TARGET_DIR:-}"
MAX_ASYNC_WORKERS="${INPUT_MAX_ASYNC_WORKERS:-}"
MAX_GENERATE_RETRIES="${INPUT_MAX_GENERATE_RETRIES:-3}"
MAX_FIX_ATTEMPTS="${INPUT_MAX_FIX_ATTEMPTS:-4}"
TARGET_LINE_COVERAGE="${INPUT_TARGET_LINE_COVERAGE:-60}"
MODEL="${INPUT_MODEL:-}"
TEMPERATURE="${INPUT_TEMPERATURE:-}"
CONFIG="${INPUT_CONFIG:-config/config.yaml}"
VERBOSE="${INPUT_VERBOSE:-false}"
TESTS_DIR="${INPUT_TESTS_DIR:-tests}"

ARGS="--project $PROJECT"

if [ -n "$TARGET_FUNCTION" ]; then
    ARGS="$ARGS --target-function \"$TARGET_FUNCTION\""
fi
if [ -n "$TARGET_CLASS" ]; then
    ARGS="$ARGS --target-class \"$TARGET_CLASS\""
fi
if [ -n "$TARGET_FILE" ]; then
    ARGS="$ARGS --target-file \"$TARGET_FILE\""
fi
if [ -n "$TARGET_DIR" ]; then
    ARGS="$ARGS --target-dir \"$TARGET_DIR\""
fi
if [ -n "$MAX_ASYNC_WORKERS" ]; then
    ARGS="$ARGS --max_async_workers $MAX_ASYNC_WORKERS"
fi
if [ -n "$MAX_GENERATE_RETRIES" ]; then
    ARGS="$ARGS --max-generate-retries $MAX_GENERATE_RETRIES"
fi
if [ -n "$MAX_FIX_ATTEMPTS" ]; then
    ARGS="$ARGS --max-fix-attempts $MAX_FIX_ATTEMPTS"
fi
if [ -n "$TARGET_LINE_COVERAGE" ]; then
    ARGS="$ARGS --target_line_coverage $TARGET_LINE_COVERAGE"
fi
if [ -n "$MODEL" ]; then
    ARGS="$ARGS --model \"$MODEL\""
fi
if [ -n "$TEMPERATURE" ]; then
    ARGS="$ARGS --temperature $TEMPERATURE"
fi
if [ "$VERBOSE" = "true" ]; then
    ARGS="$ARGS --verbose"
fi

python main.py $ARGS