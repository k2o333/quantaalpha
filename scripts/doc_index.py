#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


STANDARD_STATUSES = {"draft", "planned", "doing", "done", "archived", "active", "superseded"}
LEGACY_STATUSES = {"in_progress", "blocked", "implemented", "tested", "accepted"}
ALL_STATUSES = STANDARD_STATUSES | LEGACY_STATUSES

DOC_TYPE_BY_TOP_DIR = {
    "00-governance": "governance",
    "01-overview": "overview",
    "02-modules": "module",
    "03-changes": "change",
    "04-decisions": "decision",
    "05-playbooks": "playbook",
    "06-references": "reference",
    "07-technical": "technical",
    "drafts": "draft",
}

MODULE_BUCKETS = {"app4", "quantaalpha", "backtest", "common", "vnpy"}


@dataclass
class Document:
    path: Path
    rel_path: str
    doc_type: str
    module: str | None
    status: str | None
    owner: str | None
    created: str | None
    updated: str | None
    summary: str | None
    metadata: dict
    validation_entries: list[str]
    legacy_status_dir: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index and validate repository documentation.")
    parser.add_argument("--docs-root", default="docs", help="Root docs directory to scan. Default: docs")

    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_filters(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--type", dest="doc_type")
        subparser.add_argument("--module")
        subparser.add_argument("--status")
        subparser.add_argument("--owner")
        subparser.add_argument("--json", action="store_true", dest="as_json")

    add_common_filters(subparsers.add_parser("list", help="List matching documents"))
    add_common_filters(subparsers.add_parser("summary", help="Show document summary"))

    stale = subparsers.add_parser("stale", help="List stale documents")
    add_common_filters(stale)
    stale.add_argument("--days", type=int, default=7)

    validate = subparsers.add_parser("validate", help="Validate docs metadata and structure")
    validate.add_argument("--json", action="store_true", dest="as_json")

    return parser.parse_args()


def parse_metadata(text: str) -> tuple[dict, int]:
    lines = text.splitlines()
    if not lines:
        return {}, 0

    if lines[0].strip() == "---":
        end_index = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_index = i
                break
        if end_index is not None:
            return parse_simple_yaml(lines[1:end_index]), end_index + 1

    metadata = {}
    for i, line in enumerate(lines[:30]):
        stripped = line.strip()
        if not stripped:
            break
        if stripped == "---":
            return metadata, i + 1
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = normalize_key(key)
        if key in {"status", "owner", "created", "updated", "summary", "doc_type", "module"}:
            metadata[key] = value.strip().strip("`")
    return metadata, 0


def parse_simple_yaml(lines: list[str]) -> dict:
    data: dict[str, object] = {}
    current_list_key: str | None = None
    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            if current_list_key is not None:
                data.setdefault(current_list_key, [])
                data[current_list_key].append(stripped[2:].strip())
            continue
        if ":" not in line:
            current_list_key = None
            continue
        key, value = line.split(":", 1)
        key = normalize_key(key)
        value = value.strip()
        if not value:
            data[key] = []
            current_list_key = key
            continue
        current_list_key = None
        data[key] = parse_scalar(value)
    return data


def normalize_key(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def parse_scalar(value: str):
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return value.strip().strip('"').strip("'").strip("`")


def infer_doc_type(rel_parts: tuple[str, ...], metadata: dict) -> str:
    if metadata.get("doc_type"):
        return str(metadata["doc_type"])
    if not rel_parts:
        return "unknown"
    return DOC_TYPE_BY_TOP_DIR.get(rel_parts[0], "unknown")


def infer_module(rel_parts: tuple[str, ...], metadata: dict) -> str | None:
    if metadata.get("module"):
        return str(metadata["module"])
    if len(rel_parts) >= 2 and rel_parts[0] == "03-changes":
        return rel_parts[1]
    return None


def infer_legacy_status_dir(rel_parts: tuple[str, ...]) -> str | None:
    if len(rel_parts) >= 3 and rel_parts[0] == "03-changes" and rel_parts[2] in ALL_STATUSES:
        return rel_parts[2]
    return None


def infer_status(metadata: dict, legacy_status_dir: str | None) -> str | None:
    if metadata.get("status"):
        return str(metadata["status"])
    return legacy_status_dir


def build_summary(text: str, metadata: dict) -> str | None:
    summary = metadata.get("summary")
    if summary:
        return str(summary)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return None


def read_document(path: Path, docs_root: Path) -> Document:
    text = path.read_text(encoding="utf-8")
    metadata, _ = parse_metadata(text)
    rel_parts = path.relative_to(docs_root).parts
    legacy_status_dir = infer_legacy_status_dir(rel_parts)
    doc_type = infer_doc_type(rel_parts, metadata)
    validation_entries = metadata.get("validation", [])
    if not isinstance(validation_entries, list):
        validation_entries = [str(validation_entries)]
    return Document(
        path=path,
        rel_path=str(path.relative_to(docs_root)),
        doc_type=doc_type,
        module=infer_module(rel_parts, metadata),
        status=infer_status(metadata, legacy_status_dir),
        owner=str(metadata["owner"]) if metadata.get("owner") else None,
        created=str(metadata["created"]) if metadata.get("created") else None,
        updated=str(metadata["updated"]) if metadata.get("updated") else None,
        summary=build_summary(text, metadata),
        metadata=metadata,
        validation_entries=validation_entries,
        legacy_status_dir=legacy_status_dir,
    )


def scan_docs(docs_root: Path) -> list[Document]:
    documents = []
    for path in sorted(docs_root.rglob("*.md")):
        if path.name.startswith("."):
            continue
        documents.append(read_document(path, docs_root))
    return documents


def filter_documents(documents: list[Document], args: argparse.Namespace) -> list[Document]:
    filtered = []
    for doc in documents:
        if getattr(args, "doc_type", None) and doc.doc_type != args.doc_type:
            continue
        if getattr(args, "module", None) and doc.module != args.module:
            continue
        if getattr(args, "status", None) and doc.status != args.status:
            continue
        if getattr(args, "owner", None) and doc.owner != args.owner:
            continue
        filtered.append(doc)
    return filtered


def doc_to_dict(doc: Document) -> dict:
    return {
        "path": doc.rel_path,
        "doc_type": doc.doc_type,
        "module": doc.module,
        "status": doc.status,
        "owner": doc.owner,
        "created": doc.created,
        "updated": doc.updated,
        "summary": doc.summary,
        "legacy_status_dir": doc.legacy_status_dir,
    }


def command_list(documents: list[Document], args: argparse.Namespace) -> int:
    filtered = filter_documents(documents, args)
    if args.as_json:
        print(json.dumps({"count": len(filtered), "documents": [doc_to_dict(doc) for doc in filtered]}, ensure_ascii=False, indent=2))
        return 0

    for doc in filtered:
        print(f"{doc.rel_path}")
        print(f"  type={doc.doc_type} module={doc.module or '-'} status={doc.status or '-'} owner={doc.owner or '-'}")
        if doc.summary:
            print(f"  summary={doc.summary}")
    print(f"Total: {len(filtered)}")
    return 0


def command_summary(documents: list[Document], args: argparse.Namespace) -> int:
    filtered = filter_documents(documents, args)
    status_counts = Counter(doc.status or "unknown" for doc in filtered)
    module_counts = Counter(doc.module or "unknown" for doc in filtered)
    type_counts = Counter(doc.doc_type for doc in filtered)
    payload = {
        "count": len(filtered),
        "status_counts": dict(sorted(status_counts.items())),
        "module_counts": dict(sorted(module_counts.items())),
        "type_counts": dict(sorted(type_counts.items())),
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("Status Summary:")
    for key, value in sorted(payload["status_counts"].items()):
        print(f"  {key}: {value}")
    print("Module Summary:")
    for key, value in sorted(payload["module_counts"].items()):
        print(f"  {key}: {value}")
    print("Type Summary:")
    for key, value in sorted(payload["type_counts"].items()):
        print(f"  {key}: {value}")
    return 0


def command_stale(documents: list[Document], args: argparse.Namespace) -> int:
    filtered = filter_documents(documents, args)
    stale_docs = [doc for doc in filtered if not doc.updated]
    if args.as_json:
        print(json.dumps({"count": len(stale_docs), "documents": [doc_to_dict(doc) for doc in stale_docs]}, ensure_ascii=False, indent=2))
        return 0
    for doc in stale_docs:
        print(f"{doc.rel_path} missing-updated")
    print(f"Total: {len(stale_docs)}")
    return 0


def validate_documents(documents: list[Document]) -> list[str]:
    issues: list[str] = []
    for doc in documents:
        if doc.doc_type == "change":
            if doc.module is None:
                issues.append(f"{doc.rel_path}: missing module")
            if doc.status is None:
                issues.append(f"{doc.rel_path}: missing status")
            elif doc.status not in ALL_STATUSES:
                issues.append(f"{doc.rel_path}: invalid status '{doc.status}'")
            if doc.module and doc.path.parts[-2] not in MODULE_BUCKETS and doc.legacy_status_dir is None:
                pass
            if doc.metadata.get("module") and doc.legacy_status_dir is None:
                rel_parts = doc.rel_path.split("/")
                if len(rel_parts) >= 2 and rel_parts[1] != doc.module:
                    issues.append(f"{doc.rel_path}: module metadata '{doc.module}' does not match path module '{rel_parts[1]}'")
            if doc.status == "done" and not doc.validation_entries:
                issues.append(f"{doc.rel_path}: done change doc missing validation")
        elif doc.doc_type in {"module", "governance", "overview", "decision", "playbook", "reference", "technical"}:
            if doc.status and doc.status not in STANDARD_STATUSES:
                issues.append(f"{doc.rel_path}: invalid status '{doc.status}' for doc_type '{doc.doc_type}'")
    return issues


def command_validate(documents: list[Document], args: argparse.Namespace) -> int:
    issues = validate_documents(documents)
    if args.as_json:
        print(json.dumps({"valid": not issues, "issues": issues}, ensure_ascii=False, indent=2))
    else:
        if issues:
            print("Validation issues:")
            for issue in issues:
                print(f"- {issue}")
        else:
            print("Validation passed.")
    return 1 if issues else 0


def main() -> int:
    args = parse_args()
    docs_root = Path(args.docs_root).resolve()
    if not docs_root.exists():
        print(f"docs root not found: {docs_root}", file=sys.stderr)
        return 2

    documents = scan_docs(docs_root)

    if args.command == "list":
        return command_list(documents, args)
    if args.command == "summary":
        return command_summary(documents, args)
    if args.command == "stale":
        return command_stale(documents, args)
    if args.command == "validate":
        return command_validate(documents, args)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
