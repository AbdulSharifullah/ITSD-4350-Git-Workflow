"""Tests for the fail-closed staging-to-promotion candidate gate."""
import pytest

from monitoring.verify_promotion_candidate import validate_candidate


SHA = "a" * 40
STAGING = {
    "conclusion": "success",
    "head_sha": SHA,
    "head_branch": "main",
    "path": ".github/workflows/cd.yml",
}
MONITORING = {
    "workflow_runs": [{
        "conclusion": "success",
        "head_sha": SHA,
        "head_branch": "main",
        "path": ".github/workflows/monitoring-validation.yml",
    }]
}


def test_matching_successful_staging_and_monitoring_allow_gate():
    assert validate_candidate(SHA, STAGING, MONITORING)


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", None])
def test_failed_or_incomplete_staging_blocks_promotion(conclusion):
    staging = {**STAGING, "conclusion": conclusion}
    with pytest.raises(ValueError, match="staging run did not succeed"):
        validate_candidate(SHA, staging, MONITORING)


def test_staging_revision_mismatch_blocks_promotion():
    staging = {**STAGING, "head_sha": "b" * 40}
    with pytest.raises(ValueError, match="staging revision does not match"):
        validate_candidate(SHA, staging, MONITORING)


def test_missing_matching_monitoring_run_blocks_promotion():
    runs = {"workflow_runs": [{**MONITORING["workflow_runs"][0], "conclusion": "failure"}]}
    with pytest.raises(ValueError, match="no successful monitoring run"):
        validate_candidate(SHA, STAGING, runs)

