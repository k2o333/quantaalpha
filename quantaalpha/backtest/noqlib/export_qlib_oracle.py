"""导出 qlib oracle fixture。

该脚本只用于开发/回归阶段生成小型 parity fixture。它允许 import qlib，
但 no-qlib backend 本身不能依赖本脚本。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def export_oracle(
    *,
    provider_uri: str,
    output_dir: str,
    instruments: list[str],
    start_time: str,
    end_time: str,
    market_start_time: str | None = None,
    market_end_time: str | None = None,
    factor_source: str = "alpha158_20",
    region: str = "cn",
) -> dict[str, Any]:
    """从 qlib 导出小型 feature/label/market oracle fixture。"""
    import qlib
    from qlib.data import D
    from quantaalpha.backtest.factor_loader import FactorLoader

    qlib.init(provider_uri=provider_uri, region=region)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    config = {
        "factor_source": {"type": factor_source},
        "dataset": {"label": "Ref($close, -2) / Ref($close, -1) - 1"},
    }
    factors, _custom = FactorLoader(config).load_factors()
    market_fields = ["$open", "$high", "$low", "$close", "$volume", "$vwap"]
    market_start = market_start_time or start_time
    market_end = market_end_time or end_time
    market = D.features(instruments, market_fields, start_time=market_start, end_time=market_end, freq="day")
    features = D.features(instruments, list(factors.values()), start_time=start_time, end_time=end_time, freq="day")
    features.columns = list(factors.keys())
    label = D.features(instruments, [config["dataset"]["label"]], start_time=start_time, end_time=end_time, freq="day")
    label.columns = ["LABEL0"]

    paths = {
        "market": output / "oracle_market.parquet",
        "features": output / "oracle_features.parquet",
        "label": output / "oracle_label.parquet",
    }
    _write_frame(market, paths["market"])
    _write_frame(features, paths["features"])
    _write_frame(label, paths["label"])

    manifest = {
        "provider_uri_hash": _hash_text(str(Path(provider_uri).expanduser())),
        "region": region,
        "factor_source": factor_source,
        "instruments": instruments,
        "start_time": start_time,
        "end_time": end_time,
        "market_start_time": market_start,
        "market_end_time": market_end,
        "files": {key: path.name for key, path in paths.items()},
        "row_counts": {
            "market": int(len(market)),
            "features": int(len(features)),
            "label": int(len(label)),
        },
    }
    (output / "oracle_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _write_frame(frame: Any, path: Path) -> None:
    out = frame.reset_index()
    out.to_parquet(path, index=False)


def _hash_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export small qlib oracle fixtures for no-qlib parity.")
    parser.add_argument("--provider-uri", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--instrument", action="append", required=True, help="Instrument code; repeatable")
    parser.add_argument("--start-time", required=True)
    parser.add_argument("--end-time", required=True)
    parser.add_argument("--market-start-time", default=None, help="Optional earlier market start for rolling warmup")
    parser.add_argument("--market-end-time", default=None, help="Optional later market end for label lookahead")
    parser.add_argument("--factor-source", default="alpha158_20")
    parser.add_argument("--region", default="cn")
    args = parser.parse_args()
    manifest = export_oracle(
        provider_uri=args.provider_uri,
        output_dir=args.output_dir,
        instruments=args.instrument,
        start_time=args.start_time,
        end_time=args.end_time,
        market_start_time=args.market_start_time,
        market_end_time=args.market_end_time,
        factor_source=args.factor_source,
        region=args.region,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
