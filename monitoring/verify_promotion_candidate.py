"""Validate staging and monitoring provenance before a promotion simulation."""
import argparse
import json
from pathlib import Path


STAGING_WORKFLOW = ".github/workflows/cd.yml"
MONITORING_WORKFLOW = ".github/workflows/monitoring-validation.yml"


def validate_candidate(candidate_sha, staging_run, workflow_runs):
    """Raise ValueError unless both successful runs match the main candidate."""
    failures = []
    if staging_run.get("conclusion") != "success":
        failures.append("staging run did not succeed")
    if staging_run.get("head_sha") != candidate_sha:
        failures.append("staging revision does not match candidate")
    if staging_run.get("head_branch") != "main":
        failures.append("staging run was not produced from main")
    if staging_run.get("path") != STAGING_WORKFLOW:
        failures.append("run is not the staging deployment workflow")

    runs = workflow_runs.get("workflow_runs", [])
    monitoring_ok = any(
        run.get("conclusion") == "success"
        and run.get("head_sha") == candidate_sha
        and run.get("head_branch") == "main"
        and run.get("path") == MONITORING_WORKFLOW
        for run in runs
    )
    if not monitoring_ok:
        failures.append("no successful monitoring run matches the candidate on main")
    if failures:
        raise ValueError("promotion blocked: " + "; ".join(failures))
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--staging-run", required=True, type=Path)
    parser.add_argument("--workflow-runs", required=True, type=Path)
    args = parser.parse_args()
    staging_run = json.loads(args.staging_run.read_text(encoding="utf-8"))
    workflow_runs = json.loads(args.workflow_runs.read_text(encoding="utf-8"))
    validate_candidate(args.candidate_sha, staging_run, workflow_runs)
    print("PASS: exact candidate has successful staging and monitoring evidence")


if __name__ == "__main__":
    main()