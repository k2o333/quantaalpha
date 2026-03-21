import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "doc_index.py"


def run_doc_index(*args, docs_root=None, cwd=None):
    cmd = [sys.executable, str(SCRIPT)]
    if docs_root is not None:
        cmd.extend(["--docs-root", str(docs_root)])
    cmd.extend(args)
    return subprocess.run(
        cmd,
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
    )


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class DocIndexTests(unittest.TestCase):
    def test_list_json_includes_flat_change_doc(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_root = Path(tmpdir) / "docs"
            write(
                docs_root / "03-changes" / "quantaalpha" / "2026-03-21-flat-task.md",
                """---
doc_type: change
module: quantaalpha
status: planned
owner: quan
created: 2026-03-21
updated: 2026-03-21
summary: flat task
---

# Flat task
""",
            )

            result = run_doc_index("list", "--status", "planned", "--json", docs_root=docs_root)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["documents"][0]["module"], "quantaalpha")
            self.assertEqual(payload["documents"][0]["status"], "planned")
            self.assertTrue(payload["documents"][0]["path"].endswith("2026-03-21-flat-task.md"))

    def test_summary_counts_flat_and_legacy_docs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_root = Path(tmpdir) / "docs"
            write(
                docs_root / "03-changes" / "app4" / "2026-03-21-flat-task.md",
                """---
doc_type: change
module: app4
status: done
owner: quan
created: 2026-03-21
updated: 2026-03-21
summary: flat task
validation:
  - python3 -m unittest test.tests.test_doc_index
---
""",
            )
            write(
                docs_root / "03-changes" / "quantaalpha" / "planned" / "2026-03-21-legacy-task.md",
                """# Legacy task

Status: planned
Owner: quan
Created: 2026-03-21

---
""",
            )

            result = run_doc_index("summary", "--json", docs_root=docs_root)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status_counts"]["done"], 1)
            self.assertEqual(payload["status_counts"]["planned"], 1)
            self.assertEqual(payload["module_counts"]["app4"], 1)
            self.assertEqual(payload["module_counts"]["quantaalpha"], 1)

    def test_validate_flags_invalid_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_root = Path(tmpdir) / "docs"
            write(
                docs_root / "03-changes" / "quantaalpha" / "2026-03-21-invalid.md",
                """---
doc_type: change
module: quantaalpha
status: banana
owner: quan
created: 2026-03-21
updated: 2026-03-21
summary: invalid status
---
""",
            )

            result = run_doc_index("validate", docs_root=docs_root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("invalid status", result.stdout.lower())
            self.assertIn("banana", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
