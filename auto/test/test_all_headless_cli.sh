#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_FILE="${SCRIPT_DIR}/cli_anythin_report.md"

echo "========================================" | tee "$REPORT_FILE"
echo "CLI ANYTHIN Research Report" | tee -a "$REPORT_FILE"
echo "Generated: $(date)" | tee -a "$REPORT_FILE"
echo "========================================" | tee -a "$REPORT_FILE"
echo "" | tee -a "$REPORT_FILE"

TASK="Search the web for information about 'cli anythin' and write a comprehensive report about what it is, its features, use cases, and any relevant details. Be thorough and informative."

echo "Starting headless mode tests for all coding agents..."
echo "Task: Research 'cli anythin'"
echo ""

run_test() {
    local agent_name=$1
    local command=$2
    local output_file="${SCRIPT_DIR}/${agent_name,,}_output.txt"

    echo "----------------------------------------" | tee -a "$REPORT_FILE"
    echo "Testing: $agent_name" | tee -a "$REPORT_FILE"
    echo "Command: $command" | tee -a "$REPORT_FILE"
    echo "----------------------------------------" | tee -a "$REPORT_FILE"

    echo "[$agent_name] Starting test..."
    local start_time=$(date +%s)

    if eval "$command" > "$output_file" 2>&1; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        echo "[$agent_name] Completed in ${duration}s" | tee -a "$REPORT_FILE"
        echo "[$agent_name] Output saved to: $output_file" | tee -a "$REPORT_FILE"

        local result_content=$(cat "$output_file")
        if [ -n "$result_content" ]; then
            echo "" | tee -a "$REPORT_FILE"
            echo "--- $agent_name Output ---" | tee -a "$REPORT_FILE"
            echo "$result_content" | head -100 | tee -a "$REPORT_FILE"
            if [ $(echo "$result_content" | wc -l) -gt 100 ]; then
                echo "... (truncated, full output in $output_file)" | tee -a "$REPORT_FILE"
            fi
            echo "--- End Output ---" | tee -a "$REPORT_FILE"
        else
            echo "[$agent_name] Warning: No output produced" | tee -a "$REPORT_FILE"
        fi
    else
        local exit_code=$?
        echo "[$agent_name] Failed with exit code: $exit_code" | tee -a "$REPORT_FILE"
        echo "[$agent_name] Error output:" | tee -a "$REPORT_FILE"
        cat "$output_file" | tee -a "$REPORT_FILE"
    fi

    echo "" | tee -a "$REPORT_FILE"
    sleep 2
}

echo "Testing CodeBuddy CLI (using -y for yolo mode)..." | tee -a "$REPORT_FILE"
run_test "CodeBuddy" "codebuddy -p \"$TASK\" -y"

echo "Testing iFlow CLI (using -y for yolo mode)..." | tee -a "$REPORT_FILE"
run_test "iFlow" "iflow -p \"$TASK\" -y"

echo "Testing Gemini CLI (using --approval-mode=yolo)..." | tee -a "$REPORT_FILE"
run_test "Gemini" "gemini -p \"$TASK\" --approval-mode=yolo"

echo "Testing KiloCode CLI (using --auto for auto-approve)..." | tee -a "$REPORT_FILE"
run_test "KiloCode" "kilo run --auto \"$TASK\""

echo "Testing OpenCode CLI (no yolo mode available)..." | tee -a "$REPORT_FILE"
run_test "OpenCode" "opencode run \"$TASK\""

echo "Testing Qwen Code CLI (using --yolo)..." | tee -a "$REPORT_FILE"
run_test "QwenCode" "qwen -p \"$TASK\" --yolo"

echo "========================================" | tee -a "$REPORT_FILE"
echo "All tests completed!" | tee -a "$REPORT_FILE"
echo "Full report saved to: $REPORT_FILE" | tee -a "$REPORT_FILE"
echo "Individual outputs saved to: ${SCRIPT_DIR}/*_output.txt" | tee -a "$REPORT_FILE"
echo "========================================" | tee -a "$REPORT_FILE"