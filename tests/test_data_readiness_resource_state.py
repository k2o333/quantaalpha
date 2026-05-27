import json

from quantaalpha.continuous.resource_governor import build_resource_state_from_readiness


def test_readiness_state_passes_when_all_configured_probes_pass(tmp_path):
    marker = tmp_path / "data_snapshot_ready.json"
    marker.write_text(json.dumps({"ready": True, "snapshot_id": "20260526"}))

    state = build_resource_state_from_readiness(
        app5_freshness={"status": "passed"},
        snapshot_marker_path=marker,
        data_monitor_ready=True,
    )

    assert state.data_ready is True
    assert state.failed_readiness_probes == []


def test_readiness_state_collects_all_failed_probes(tmp_path):
    marker = tmp_path / "data_snapshot_ready.json"
    marker.write_text(json.dumps({"ready": False, "reason": "updating"}))

    state = build_resource_state_from_readiness(
        app5_freshness={"status": "failed"},
        snapshot_marker_path=marker,
        data_monitor_ready=False,
        compaction_running=True,
        data_updating=True,
    )

    assert state.data_ready is False
    assert state.compaction_running is True
    assert state.data_updating is True
    assert state.failed_readiness_probes == [
        "app5_freshness",
        "snapshot_marker",
        "data_monitor",
    ]


def test_readiness_state_treats_missing_configured_marker_as_failed(tmp_path):
    state = build_resource_state_from_readiness(
        app5_freshness=None,
        snapshot_marker_path=tmp_path / "missing.json",
        data_monitor_ready=True,
    )

    assert state.data_ready is False
    assert state.failed_readiness_probes == ["snapshot_marker"]
