# Mining Pipeline Bug Fix Plan

**Date:** 2026-03-24  
**Scope:** Consolidated fix plan for verified bugs in the mining pipeline and the newly confirmed `rdagent.log` dependency breakage.

---

## Goal

Stabilize the factor mining pipeline by fixing:

1. malformed `corrected_expression` handling in consistency correction,
2. weak prompt constraints that allow unparsable expressions,
3. wasteful retries on unrecoverable LLM API errors,
4. incomplete JSON escape repair,
5. misleading deprecated prompt wiring, and
6. hard import failure caused by `quantaalpha.log` depending on a non-existent `rdagent.log` module.

---

## Priority Summary

| ID | Issue | Severity | Why it matters |
|----|-------|----------|----------------|
| Bug-6 | `quantaalpha.log` hard-depends on missing `rdagent.log` | P0 | Breaks module import and blocks local verification/runtime paths |
| Bug-1 | `normalize_corrected_expression` passes dirty strings through | P0 | Corrected expressions can still be unparsable and derail correction loop |
| Bug-2 | `consistency_check_system` lacks strict output constraints | P0 | Root cause of malformed `corrected_expression` payloads |
| Bug-3 | BadRequest retry treats invalid model names as recoverable | P1 | Wastes retries and hides configuration errors |
| Bug-4 | JSON escape repair is incomplete and duplicated | P2 | Some malformed JSON outputs still fail parsing |
| Bug-5 | `proposal.yaml` is shadowed by later reassignment | P2 | Causes maintenance confusion and misleading analysis |

---

## Root Cause Notes

- The active correction path is `check_consistency() -> corrected_expression -> proposal.py normalize_corrected_expression() -> parser re-check`.
- `expression_correction_system` exists in prompt config, but is not wired into the current correction flow. Fixes that only touch that prompt will not materially change runtime behavior.
- The parser rejects characters such as `#`, `\\`, `;`, `{}`, and `=` in expressions, so comment-heavy or pseudo-code outputs are not acceptable inputs.
- `quantaalpha.log` and `third_party/quantaalpha/quantaalpha/log` both import `rdagent.log`, but the installed `rdagent` package does not provide that module in this environment.

---

## Fix Plan

### Task 1: Remove hard runtime dependency on `rdagent.log`

**Files:**
- Modify: `quantaalpha/log/__init__.py`
- Modify: `third_party/quantaalpha/quantaalpha/log/__init__.py`
- Add if needed: `quantaalpha/log/_fallback.py`

**Plan:**

1. Replace the unconditional `from rdagent.log ...` import with a guarded import.
2. Keep compatibility with `logger` and `LogColors` public names.
3. If `rdagent.log` is unavailable, fall back to a local lightweight logger implementation based on Python `logging`.
4. Preserve the AlphaAgent-specific APIs already expected by callers:
   - `logger.info(...)`
   - `logger.warning(...)`
   - `logger.error(...)`
   - `logger.exception(...)`
   - `logger.log_trace_path`
   - `logger.set_trace_path(path)`
5. Ensure the fallback does not assume `storage.path` or other `rdagent`-specific internals.
6. Mirror the same logic in the vendored `third_party` copy or remove divergence by importing from one canonical implementation if that is safe in this repo structure.

**Recommended implementation shape:**

- Preferred:
  - `try` import `rdagent.log` implementation
  - `except ImportError` use local fallback wrapper
- Avoid:
  - fully replacing behavior with a brand-new logger that breaks existing call signatures
  - leaving the vendored copy inconsistent with the main package

**Verification:**

- `python -c "from quantaalpha.log import logger, LogColors; print(type(logger).__name__)"`
- `python -c "from quantaalpha.factors.proposal import normalize_corrected_expression; print('ok')"`

---

### Task 2: Harden `normalize_corrected_expression`

**Files:**
- Modify: `quantaalpha/factors/proposal.py`

**Plan:**

1. Expand `normalize_corrected_expression()` so it handles:
   - dict payloads,
   - fenced code blocks,
   - `//` and `#` comments,
   - multi-line outputs,
   - variable-assignment pseudo-code,
   - stringified JSON/dict-like payloads.
2. Do not simply drop assignment lines. If the model returns:
   - `x = ...`
   - `factor = ...`
   extract the right-hand side of the final meaningful assignment.
3. If input looks like JSON or a Python-like dict string, first attempt structured extraction of `expression` / `corrected_expression`.
4. Normalize whitespace to a single-line expression.
5. Return the cleaned expression only if non-empty; otherwise preserve the original for debugging and let caller log failure explicitly.
6. Add a final parsability check at the call site or inside the function only if that does not introduce circular dependencies.

**Important caution:**

The previously suggested approach of skipping all `name = ...` lines is insufficient. It can delete the only valid expression and fall back to the original dirty payload.

**Verification cases:**

- `TS_STD($close, 10) // comment` -> `TS_STD($close, 10)`
- `alpha = TS_STD($close, 10)\nfactor = RANK(alpha)` -> `RANK(alpha)` or equivalent final expression
- ````json {"expression": "TS_CORR($high-$low, $volume, 20)"}```` -> extracted expression
- multi-line fenced block -> single-line expression

---

### Task 3: Tighten the prompt that actually drives correction

**Files:**
- Modify: `quantaalpha/factors/regulator/consistency_prompts.yaml`

**Plan:**

1. Update `consistency_check_system` output contract for `corrected_expression`:
   - require a single-line expression,
   - forbid comments,
   - forbid variable assignments,
   - forbid multiple options,
   - forbid pseudo-code,
   - require only allowed functions and variables.
2. Update `consistency_check_user` to repeat the same constraints near the request body.
3. Keep `expression_correction_system` aligned for future use, but treat it as secondary because it is not currently wired into runtime.

**Recommended wording requirements:**

- "Return ONLY a SINGLE-LINE factor expression."
- "Do NOT include comments, markdown fences, variable assignments, prose, or multiple candidate expressions."
- "Use only the listed variables/functions."

**Verification:**

- Capture several `check_consistency()` outputs and confirm `corrected_expression` arrives as a plain one-line DSL expression.

---

### Task 4: Stop retrying unrecoverable BadRequest errors

**Files:**
- Modify: `quantaalpha/llm/client.py`

**Plan:**

1. In `_try_create_chat_completion_or_embedding()`, detect unrecoverable `openai.BadRequestError` messages before logging `Retrying...`.
2. Immediately re-raise for at least:
   - invalid model name / invalid model,
   - other clearly configuration-related 400 errors if identified during implementation.
3. Use `str(e)` instead of relying on `e.message`.
4. Log the actual failing model name:
   - chat path: chat model
   - embedding path: embedding model
5. Preserve the existing special handling for:
   - missing `json` keyword in JSON-mode request
   - embedding maximum context length shrink

**Verification:**

- Simulate a bad model config and confirm the first failure surfaces immediately without consuming all retries.

---

### Task 5: Centralize JSON escape repair

**Files:**
- Modify: `quantaalpha/llm/client.py`

**Plan:**

1. Extend the shared helper `_escape_common_json_sequences()` to include a generic fallback:
   - `re.sub(r'\\(?!["\\\\/bfnrtu])', r'\\\\', text)`
2. Reuse that helper from all JSON-repair paths instead of keeping two partially divergent implementations.
3. Keep existing targeted LaTeX escape fixes because they are still useful and readable.
4. Do not add the generic regex in only one branch; that would leave parsing behavior inconsistent.

**Verification:**

- JSON containing `\\_`, `\\alpha`, stray backslashes before unsupported letters, and mixed LaTeX content should parse through the same repair path.

---

### Task 6: Remove prompt source ambiguity in `proposal.py`

**Files:**
- Modify: `quantaalpha/factors/proposal.py`
- Remove or archive if appropriate: `quantaalpha/factors/prompts/proposal.yaml`

**Plan:**

1. Remove the earlier `qa_prompt_dict = Prompts(... proposal.yaml)` assignment if it is truly dead.
2. Confirm all active runtime lookups resolve against `prompts.yaml`.
3. Either:
   - delete `proposal.yaml`, or
   - move it to an archive/deprecated location with an explicit note that it is unused.
4. If any content from `proposal.yaml` is still needed for documentation value, copy that content intentionally into active prompt files instead of keeping silent shadowing.

**Verification:**

- `rg "proposal.yaml|qa_prompt_dict =" quantaalpha/factors/proposal.py`
- sanity-check prompt rendering paths in hypothesis generation and experiment generation

---

## Suggested Implementation Order

1. Fix Bug-6 first so imports and local verification paths stop failing.
2. Fix Bug-2 and Bug-1 together because they are upstream/downstream parts of the same correction failure.
3. Fix Bug-3 to improve API failure visibility.
4. Fix Bug-5 to remove misleading dead configuration.
5. Fix Bug-4 last unless JSON parsing failures are currently common in logs.

---

## Validation Checklist

- `from quantaalpha.log import logger` succeeds without `rdagent.log`
- consistency correction returns single-line expressions
- corrected expressions survive `normalize_corrected_expression()`
- corrected expressions pass parser validation in the proposal flow
- invalid model configuration fails fast without exhausting retries
- malformed JSON with stray backslashes is repaired consistently
- no active code path still depends on shadowed `proposal.yaml`

---

## Risks

- A fallback logger that diverges too far from the expected `rdagent` surface may break subtle call sites. Keep the compatibility wrapper minimal and interface-driven.
- Over-aggressive expression cleaning can destroy legitimate expressions. Prefer extraction of the final DSL expression over blanket deletion.
- Prompt-only fixes will reduce malformed output frequency but will not eliminate it. Runtime normalization must remain defensive.
- JSON auto-repair can hide upstream model formatting issues if logging is too quiet. Keep warning logs when repairs are applied.

---

## Done Criteria

This fix plan is complete when:

- the repo imports cleanly in the current environment,
- the consistency correction path no longer re-injects obvious pseudo-code into the parser,
- unrecoverable LLM config errors fail fast,
- JSON repair is centralized and more robust, and
- prompt/config ambiguity is removed from the factor proposal flow.
