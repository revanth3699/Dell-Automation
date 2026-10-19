"""Every scenarios/*.yaml must load and validate against the real Target/Source models --
the same check `scenario_runner --validate-only` performs, run as a unit test so a renamed
action or a typo in a YAML file fails here, not twenty minutes into a live run."""

from __future__ import annotations

from pathlib import Path

import pytest

from orchestration import scenario_runner
from orchestration.statemachine import source_model, target_model
from orchestration.statemachine.scenario import (
    lint_scenario,
    load_scenario,
    validate_scenario,
)

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "scenarios"
SCENARIO_FILES = sorted(p for p in SCENARIO_DIR.glob("*.yaml") if not p.name.startswith("_"))


@pytest.fixture(scope="module")
def models():
    return {"target": target_model.build(None), "source": source_model.build(None)}


def test_there_are_scenarios():
    assert SCENARIO_FILES, f"no scenario files in {SCENARIO_DIR}"


@pytest.mark.parametrize("path", SCENARIO_FILES, ids=[p.stem for p in SCENARIO_FILES])
def test_scenario_validates_against_models(path, models):
    scenario = load_scenario(path)
    assert scenario.name == path.stem, "scenario name should match its file name"
    validate_scenario(scenario, models)
    assert lint_scenario(scenario, models) == [], "every ending the app can reach must be handled by a later step"


def test_cli_validate_only_accepts_every_scenario(capsys):
    for path in SCENARIO_FILES:
        assert scenario_runner.main(["--scenario", path.stem, "--validate-only"]) == 0, path.stem


def test_models_are_consistent(models):
    for role, model in models.items():
        model.validate()
        for state in model.states.values():
            assert state.text is not None, f"{role}.{state.id} has no snapshot text match"
            assert "publish" in state.actions and "wait_for_peer" in state.actions, f"{role}.{state.id} lacks peer actions"


def test_target_model_covers_the_documented_states(models):
    documented = {
        # TARGET_STATE_MACHINE.md Sec 2
        "welcome", "welcomeDeferral", "welcomeDeferralError", "deferralSuccess", "checkPrerequisites",
        "connectOldPc", "enterCode", "readyToMove", "chooseWhatToMove", "migrating", "resultsSummary",
        "complete", "skippedFiles", "migrationDone", "learnAboutErase",
        # Sec 3
        "signIn", "signOut", "trustNetwork", "closeApplications", "closeApplicationsFailed", "installBrowser",
        "accountMismatch", "notAdmin", "batteryCritical", "noNetwork", "otherPcNoNetwork", "connectionLost",
        "migrationCancelled", "localeNotSupported", "localeMismatch", "failure",
        # Sec 4
        "cancelMigrationConfirm", "desktopShortcut",
    }
    missing = documented - set(models["target"].states)
    assert not missing, f"documented states missing from the model: {sorted(missing)}"
