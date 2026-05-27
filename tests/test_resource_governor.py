from quantaalpha.continuous.resource_governor import (
    GovernorConfig,
    ResourceRequest,
    ResourceState,
    evaluate_resource_request,
)


def test_compute_lock_held_defers_heavy_revalidation():
    decision = evaluate_resource_request(
        ResourceRequest(scheduler="revalidation", run_id="run-1", lock_name="global_compute_lock"),
        ResourceState(active_compute_owner="mining", data_ready=True),
        GovernorConfig(enabled=True),
    )

    assert decision.allowed is False
    assert decision.action == "defer"
    assert decision.reason == "global_compute_lock_held"
    assert decision.scheduler == "revalidation"
    assert decision.lock_name == "global_compute_lock"


def test_data_not_ready_defers_with_failed_probe_names():
    decision = evaluate_resource_request(
        ResourceRequest(scheduler="mining", run_id="run-2", lock_name="global_compute_lock"),
        ResourceState(data_ready=False, failed_readiness_probes=["app5_freshness", "snapshot_marker"]),
        GovernorConfig(enabled=True),
    )

    assert decision.allowed is False
    assert decision.action == "defer"
    assert decision.reason == "deferred_data_not_ready"
    assert decision.metadata["failed_readiness_probes"] == ["app5_freshness", "snapshot_marker"]


def test_governor_disabled_allows_request():
    decision = evaluate_resource_request(
        ResourceRequest(scheduler="mining", run_id="run-3", lock_name="global_compute_lock"),
        ResourceState(active_compute_owner="revalidation", data_ready=False),
        GovernorConfig(enabled=False),
    )

    assert decision.allowed is True
    assert decision.action == "allow"
    assert decision.reason == "resource_governor_disabled"
