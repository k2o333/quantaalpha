#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_CONFIG_DEFAULT="${SCRIPT_DIR}/headless_agents.json"
LAYOUT_CONFIG_DEFAULT="${SCRIPT_DIR}/headless_run_layout.json"

usage() {
    cat <<'EOF'
Usage:
  run_parallel_headless_dev.sh --batch-dir <path> [options]

Options:
  --batch-dir <path>       Directory containing initial task pairs.
  --tasks-root <path>      Root directory where task_id folders are created.
  --agents-config <path>   Path to headless_agents.json.
  --layout-config <path>   Path to headless_run_layout.json.
  --dry-run                Print execution plan without running agents.
  -h, --help               Show this help.

Initial batch directory rules:
  - At most 6 task pairs per batch directory.
  - Each task pair must be:
      <name>.task.md
      <name>.prompt.txt
  - The shared <name> is used only for pairing and task-id slug generation.

Per generated task directory:
  <tasks-root>/<task_id>/
    task.md
    prompt.txt
    meta.json
    runs/
      <run_id>/
        stdout.log
        stderr.log
        exit_code.txt
        result.md
        summary.md
        status.json
EOF
}

die() {
    echo "ERROR: $*" >&2
    exit 1
}

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

json_string() {
    local file=$1
    local query=$2
    jq -er "$query" "$file"
}

replace_tokens() {
    local template=$1
    local tasks_root=$2
    local task_id=$3
    local run_id=$4
    local agent=${5:-}

    local result=$template
    result=${result//\{tasks_root\}/$tasks_root}
    result=${result//\{task_id\}/$task_id}
    result=${result//\{run_id\}/$run_id}
    result=${result//\{agent\}/$agent}
    printf '%s\n' "$result"
}

make_parent_dir() {
    local path=$1
    mkdir -p "$(dirname "$path")"
}

slugify() {
    local input=$1
    printf '%s' "$input" \
        | tr '[:upper:]' '[:lower:]' \
        | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/--+/-/g'
}

build_command_preview() {
    local agent=$1
    jq -r --arg agent "$agent" '
        .agents[$agent].command + .agents[$agent].append_args
        | join(" ")
    ' "$AGENTS_CONFIG"
}

run_one_task() {
    local task_id=$1
    local agent=$2
    local task_dir=$3
    local prompt_file=$4
    local run_id=$5
    local stdout_file=$6
    local stderr_file=$7
    local exit_file=$8
    local result_file=$9
    local summary_file=${10}
    local status_file=${11}

    local -a base=()
    local -a extra=()
    local -a cmd=()
    local prompt_style=""

    mapfile -t base < <(jq -r --arg agent "$agent" '.agents[$agent].command[]' "$AGENTS_CONFIG")
    mapfile -t extra < <(jq -r --arg agent "$agent" '.agents[$agent].append_args[]?' "$AGENTS_CONFIG")
    prompt_style="$(jq -r --arg agent "$agent" '.agents[$agent].prompt_style // "append_last"' "$AGENTS_CONFIG")"

    local prompt_content
    prompt_content="$(cat "$prompt_file")"

    make_parent_dir "$stdout_file"
    make_parent_dir "$stderr_file"
    make_parent_dir "$exit_file"
    make_parent_dir "$result_file"
    make_parent_dir "$summary_file"
    make_parent_dir "$status_file"

    cat >"$summary_file" <<EOF
# Run Summary

- Task ID: \`$task_id\`
- Agent: \`$agent\`
- Task Dir: \`$task_dir\`
- Run ID: \`$run_id\`
- Prompt File: \`$prompt_file\`
- Command: \`$(build_command_preview "$agent")\`

EOF

    cat >"$result_file" <<EOF
# Agent Result

- Task ID: \`$task_id\`
- Agent: \`$agent\`
- Run ID: \`$run_id\`

## Prompt

\`\`\`
$prompt_content
\`\`\`

## Output

EOF

    if (( DRY_RUN == 1 )); then
        echo "[DRY-RUN] task_id=${task_id} agent=${agent} prompt=${prompt_file}"
        printf '0\n' >"$exit_file"
        {
            printf '{\n'
            printf '  "task_id": "%s",\n' "$task_id"
            printf '  "run_id": "%s",\n' "$run_id"
            printf '  "agent": "%s",\n' "$agent"
            printf '  "status": "dry_run"\n'
            printf '}\n'
        } >"$status_file"
        return 0
    fi

    case "$prompt_style" in
        inline_after_command)
            cmd=("${base[@]}" "$prompt_content" "${extra[@]}")
            ;;
        append_last)
            cmd=("${base[@]}" "${extra[@]}" "$prompt_content")
            ;;
        *)
            echo "[ERROR] task_id=${task_id} agent=${agent} unknown prompt_style=${prompt_style}" >&2
            printf '2\n' >"$exit_file"
            return 2
            ;;
    esac

    echo "[START] task_id=${task_id} agent=${agent} run_id=${run_id}"
    if command -v timeout >/dev/null 2>&1; then
        timeout "$TIMEOUT_SECONDS" "${cmd[@]}" >"$stdout_file" 2>"$stderr_file"
    else
        "${cmd[@]}" >"$stdout_file" 2>"$stderr_file"
    fi
    local exit_code=$?
    printf '%s\n' "$exit_code" >"$exit_file"
    echo "[DONE] task_id=${task_id} agent=${agent} exit_code=${exit_code}"

    {
        printf '```\n'
        cat "$stdout_file" 2>/dev/null || true
        printf '\n```\n\n'
        printf '## Stderr\n\n```\n'
        cat "$stderr_file" 2>/dev/null || true
        printf '\n```\n'
    } >>"$result_file"

    {
        printf '\n## Result\n\n'
        printf -- '- Exit Code: `%s`\n' "$exit_code"
        printf -- '- Stdout: `%s`\n' "$stdout_file"
        printf -- '- Stderr: `%s`\n' "$stderr_file"
        printf -- '- Result Report: `%s`\n' "$result_file"
    } >>"$summary_file"

    {
        printf '{\n'
        printf '  "task_id": "%s",\n' "$task_id"
        printf '  "run_id": "%s",\n' "$run_id"
        printf '  "agent": "%s",\n' "$agent"
        printf '  "status": "%s",\n' "$([[ "$exit_code" == "0" ]] && echo success || echo failed)"
        printf '  "exit_code": "%s",\n' "$exit_code"
        printf '  "stdout": "%s",\n' "$stdout_file"
        printf '  "stderr": "%s",\n' "$stderr_file"
        printf '  "result_report": "%s"\n' "$result_file"
        printf '}\n'
    } >"$status_file"

    return "$exit_code"
}

BATCH_DIR=""
TASKS_ROOT=""
AGENTS_CONFIG="$AGENTS_CONFIG_DEFAULT"
LAYOUT_CONFIG="$LAYOUT_CONFIG_DEFAULT"
DRY_RUN=0
TIMEOUT_SECONDS=1800

while [[ $# -gt 0 ]]; do
    case "$1" in
        --batch-dir)
            BATCH_DIR=${2:-}
            shift 2
            ;;
        --tasks-root)
            TASKS_ROOT=${2:-}
            shift 2
            ;;
        --agents-config)
            AGENTS_CONFIG=${2:-}
            shift 2
            ;;
        --layout-config)
            LAYOUT_CONFIG=${2:-}
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "Unknown argument: $1"
            ;;
    esac
done

[[ -n "$BATCH_DIR" ]] || {
    usage
    die "--batch-dir is required"
}

need_cmd jq

[[ -f "$AGENTS_CONFIG" ]] || die "Agents config not found: $AGENTS_CONFIG"
[[ -f "$LAYOUT_CONFIG" ]] || die "Layout config not found: $LAYOUT_CONFIG"
[[ -d "$BATCH_DIR" ]] || die "Batch directory not found: $BATCH_DIR"

BATCH_DIR="$(cd "$BATCH_DIR" && pwd)"
if [[ -z "$TASKS_ROOT" ]]; then
    TASKS_ROOT="$(json_string "$LAYOUT_CONFIG" '.defaults.tasks_root_dir')"
fi
mkdir -p "$TASKS_ROOT"
TASKS_ROOT="$(cd "$TASKS_ROOT" && pwd)"

TASK_DOC_SUFFIX="$(json_string "$LAYOUT_CONFIG" '.defaults.initial_task_suffix')"
PROMPT_SUFFIX="$(json_string "$LAYOUT_CONFIG" '.defaults.initial_prompt_suffix')"
TASK_DOC_NAME="$(json_string "$LAYOUT_CONFIG" '.defaults.task_doc_name')"
PROMPT_FILE_NAME="$(json_string "$LAYOUT_CONFIG" '.defaults.prompt_file_name')"
RUN_DIR_NAME="$(json_string "$LAYOUT_CONFIG" '.defaults.run_dir_name')"
META_FILE_NAME="$(json_string "$LAYOUT_CONFIG" '.defaults.meta_file_name')"

STDOUT_TEMPLATE="$(json_string "$LAYOUT_CONFIG" '.stdout_files.agent_stdout')"
STDERR_TEMPLATE="$(json_string "$LAYOUT_CONFIG" '.stdout_files.agent_stderr')"
EXIT_TEMPLATE="$(json_string "$LAYOUT_CONFIG" '.stdout_files.agent_exit_code')"
RESULT_TEMPLATE="$(json_string "$LAYOUT_CONFIG" '.report_files.agent_result_report')"
SUMMARY_TEMPLATE="$(json_string "$LAYOUT_CONFIG" '.report_files.summary_report')"
STATUS_TEMPLATE="$(json_string "$LAYOUT_CONFIG" '.report_files.status_file')"

mapfile -t ENABLED_AGENTS < <(jq -r '.agents | to_entries[] | select(.value.enabled == true) | .key' "$AGENTS_CONFIG")
[[ ${#ENABLED_AGENTS[@]} -gt 0 ]] || die "No enabled agents found in $AGENTS_CONFIG"

mapfile -t TASK_FILES < <(find "$BATCH_DIR" -maxdepth 1 -type f -name "*${TASK_DOC_SUFFIX}" | sort)
[[ ${#TASK_FILES[@]} -gt 0 ]] || die "No initial task files found in: $BATCH_DIR"
if (( ${#TASK_FILES[@]} > 6 )); then
    die "Batch contains ${#TASK_FILES[@]} task files. Maximum allowed is 6."
fi

MAX_PARALLEL=${#TASK_FILES[@]}
if (( MAX_PARALLEL > 6 )); then
    MAX_PARALLEL=6
fi

declare -A TASKID_TO_AGENT=()
declare -A TASKID_TO_DIR=()
declare -A TASKID_TO_RUNID=()
declare -A TASKID_TO_PROMPT=()
declare -A TASKID_TO_STDOUT=()
declare -A TASKID_TO_STDERR=()
declare -A TASKID_TO_EXIT=()
declare -A TASKID_TO_RESULT=()
declare -A TASKID_TO_SUMMARY=()
declare -A TASKID_TO_STATUS=()
declare -A TASKID_TO_PID=()
declare -A TASKID_TO_EXITCODE=()
declare -A TASKID_TO_STATE=()
TASK_IDS=()

task_index=0
for task_file in "${TASK_FILES[@]}"; do
    base_name="$(basename "$task_file")"
    pair_name="${base_name%${TASK_DOC_SUFFIX}}"
    prompt_file="${BATCH_DIR}/${pair_name}${PROMPT_SUFFIX}"
    [[ -f "$prompt_file" ]] || die "Missing matching prompt file for ${base_name}: ${prompt_file}"

    slug="$(slugify "$pair_name")"
    [[ -n "$slug" ]] || slug="task"
    task_id="task-$(date -u +%Y%m%dT%H%M%SZ)-${task_index}-${slug}"
    run_id="run-$(date -u +%Y%m%dT%H%M%SZ)"
    task_dir="${TASKS_ROOT}/${task_id}"
    run_dir="${task_dir}/${RUN_DIR_NAME}/${run_id}"
    mkdir -p "$run_dir"

    cp "$task_file" "${task_dir}/${TASK_DOC_NAME}"
    cp "$prompt_file" "${task_dir}/${PROMPT_FILE_NAME}"

    {
        printf '{\n'
        printf '  "task_id": "%s",\n' "$task_id"
        printf '  "source_task_file": "%s",\n' "$task_file"
        printf '  "source_prompt_file": "%s",\n' "$prompt_file"
        printf '  "pair_name": "%s"\n' "$pair_name"
        printf '}\n'
    } >"${task_dir}/${META_FILE_NAME}"

    agent="${ENABLED_AGENTS[$((task_index % ${#ENABLED_AGENTS[@]}))]}"

    stdout_file="$(replace_tokens "$STDOUT_TEMPLATE" "$TASKS_ROOT" "$task_id" "$run_id" "$agent")"
    stderr_file="$(replace_tokens "$STDERR_TEMPLATE" "$TASKS_ROOT" "$task_id" "$run_id" "$agent")"
    exit_file="$(replace_tokens "$EXIT_TEMPLATE" "$TASKS_ROOT" "$task_id" "$run_id" "$agent")"
    result_file="$(replace_tokens "$RESULT_TEMPLATE" "$TASKS_ROOT" "$task_id" "$run_id" "$agent")"
    summary_file="$(replace_tokens "$SUMMARY_TEMPLATE" "$TASKS_ROOT" "$task_id" "$run_id" "$agent")"
    status_file="$(replace_tokens "$STATUS_TEMPLATE" "$TASKS_ROOT" "$task_id" "$run_id" "$agent")"

    TASK_IDS+=("$task_id")
    TASKID_TO_AGENT["$task_id"]="$agent"
    TASKID_TO_DIR["$task_id"]="$task_dir"
    TASKID_TO_RUNID["$task_id"]="$run_id"
    TASKID_TO_PROMPT["$task_id"]="${task_dir}/${PROMPT_FILE_NAME}"
    TASKID_TO_STDOUT["$task_id"]="$stdout_file"
    TASKID_TO_STDERR["$task_id"]="$stderr_file"
    TASKID_TO_EXIT["$task_id"]="$exit_file"
    TASKID_TO_RESULT["$task_id"]="$result_file"
    TASKID_TO_SUMMARY["$task_id"]="$summary_file"
    TASKID_TO_STATUS["$task_id"]="$status_file"
    TASKID_TO_STATE["$task_id"]="pending"
    task_index=$((task_index + 1))
done

for task_id in "${TASK_IDS[@]}"; do
    run_one_task \
        "$task_id" \
        "${TASKID_TO_AGENT[$task_id]}" \
        "${TASKID_TO_DIR[$task_id]}" \
        "${TASKID_TO_PROMPT[$task_id]}" \
        "${TASKID_TO_RUNID[$task_id]}" \
        "${TASKID_TO_STDOUT[$task_id]}" \
        "${TASKID_TO_STDERR[$task_id]}" \
        "${TASKID_TO_EXIT[$task_id]}" \
        "${TASKID_TO_RESULT[$task_id]}" \
        "${TASKID_TO_SUMMARY[$task_id]}" \
        "${TASKID_TO_STATUS[$task_id]}" &
    TASKID_TO_PID["$task_id"]=$!
    TASKID_TO_STATE["$task_id"]="running"
done

overall_status="success"
for task_id in "${TASK_IDS[@]}"; do
    pid="${TASKID_TO_PID[$task_id]}"
    if wait "$pid"; then
        TASKID_TO_STATE["$task_id"]="success"
        TASKID_TO_EXITCODE["$task_id"]="0"
    else
        exit_code=$?
        TASKID_TO_STATE["$task_id"]="failed"
        TASKID_TO_EXITCODE["$task_id"]="$exit_code"
        overall_status="partial_failed"
    fi
done

batch_status_file="${BATCH_DIR}/batch.status.json"
{
    printf '{\n'
    printf '  "batch_dir": "%s",\n' "$BATCH_DIR"
    printf '  "tasks_root": "%s",\n' "$TASKS_ROOT"
    printf '  "status": "%s",\n' "$overall_status"
    printf '  "task_count": %s,\n' "${#TASK_IDS[@]}"
    printf '  "max_parallel": %s,\n' "$MAX_PARALLEL"
    printf '  "tasks": [\n'
    first=1
    for task_id in "${TASK_IDS[@]}"; do
        if (( first == 0 )); then
            printf ',\n'
        fi
        first=0
        printf '    {"task_id":"%s","agent":"%s","status":"%s","exit_code":"%s","task_dir":"%s","summary":"%s"}' \
            "$task_id" \
            "${TASKID_TO_AGENT[$task_id]}" \
            "${TASKID_TO_STATE[$task_id]}" \
            "${TASKID_TO_EXITCODE[$task_id]}" \
            "${TASKID_TO_DIR[$task_id]}" \
            "${TASKID_TO_SUMMARY[$task_id]}"
    done
    printf '\n  ]\n'
    printf '}\n'
} >"$batch_status_file"

echo "Batch complete."
echo "Batch status: $batch_status_file"
