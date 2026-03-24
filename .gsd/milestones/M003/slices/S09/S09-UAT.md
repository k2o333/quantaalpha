# UAT Plan — S09

## Checks

| ID | Description | Mode | Verification |
|----|-------------|------|--------------|
| S09-ST-01 | M001 lessons doc exists and non-empty | artifact | `wc -l docs/constraints/m001_lessons.md` ≥ 100 |
| S09-ST-02 | 5 design constraints documented | artifact | grep DC-LOG-001 ... DC-TYPE-001 in doc |
| S09-ST-03 | Compliance checker script runs without error | runtime | `python scripts/check_m001_constraints.py` exit 0 |
| S09-ST-04 | All 5 constraints PASS | runtime | output contains "All checks PASSED" |
| S09-ST-05 | DC-TYPE-001 isinstance dict fix in consistency_checker.py | artifact | grep isinstance at line 265, 354 |
| S09-ST-06 | DC-TYPE-001 regression tests pass | runtime | pytest test_consistency_checker_dict_fix.py → 13 passed |
| S09-ST-07 | DC-LLM-001 empty response tests pass | runtime | pytest test_provider_pool.py → empty_response tests |
| S09-ST-08 | DC-LOOP-001 no while True in LLM context | runtime | check_m001_constraints.py DC-LOOP-001 PASS |
| S09-ST-09 | DC-JSON-001 newline tests pass | runtime | pytest test_checkpoint.py → newline tests |
| S09-ST-10 | DC-LOG-001 no %s format in log calls | runtime | check_m001_constraints.py DC-LOG-001 PASS |
