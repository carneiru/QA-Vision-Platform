"""Pure helpers behind POST /analytics/duration-estimate: percentiles, per-test durations, the project fit."""
import math

import pytest

from src.ingestion.analytics.duration import (
    MAX_OVERHEAD_MS, Execution, combine, durations_for, fit_model, percentile,
)


def test_percentile_interpolates_linearly_between_the_sorted_values():
    assert percentile([30, 10, 20], 0.5) == 20
    assert percentile([10, 20, 30, 40], 0.5) == 25
    assert percentile([0, 100], 0.9) == pytest.approx(90)
    assert percentile([7], 0.9) == 7


def test_percentile_of_nothing_is_none():
    assert percentile([], 0.5) is None


def ex(status, duration, environment=None):
    return Execution(status=status, duration_ms=duration, environment=environment)


def test_typical_is_the_median_of_passed_and_upper_the_p90_of_every_non_skipped_execution():
    rows = [ex("passed", 100), ex("passed", 200), ex("passed", 300), ex("failed", 5000), ex("skipped", 0)]
    typical, upper, used_env = durations_for(rows, None)
    assert typical == 200
    assert upper == pytest.approx(percentile([100, 200, 300, 5000], 0.9))
    assert used_env is False


def test_a_test_that_never_passed_takes_the_median_of_its_non_skipped_executions():
    typical, upper, _ = durations_for([ex("failed", 100), ex("errored", 300), ex("skipped", 9)], None)
    assert typical == 200
    assert upper == pytest.approx(280)


def test_a_test_with_only_skips_has_no_history():
    assert durations_for([ex("skipped", 5)], None) is None
    assert durations_for([], None) is None


def test_the_environment_is_used_from_three_non_skipped_executions_there():
    rows = [ex("passed", 100, "staging")] * 3 + [ex("passed", 900, "prod")] * 5
    typical, _, used_env = durations_for(rows, "staging")
    assert (typical, used_env) == (100, True)


def test_below_three_executions_in_the_environment_every_environment_counts():
    rows = [ex("passed", 100, "staging")] * 2 + [ex("skipped", 1, "staging")] * 4 + [ex("passed", 900, "prod")] * 5
    typical, _, used_env = durations_for(rows, "staging")
    assert (typical, used_env) == (900, False)


def test_upper_is_never_below_typical():
    # every failure is fast, every pass slow: p90 of all could sit below the passed median
    rows = [ex("passed", 1000)] + [ex("failed", 10)] * 20
    typical, upper, _ = durations_for(rows, None)
    assert typical == 1000 and upper == 1000


def test_five_points_on_a_line_fit_overhead_and_factor():
    points = [(s, 60_000 + 0.5 * s) for s in (100_000, 200_000, 300_000, 400_000, 500_000)]
    model = fit_model(points)
    assert model.fitted is True and model.runs == 5
    assert model.overhead_ms == pytest.approx(60_000)
    assert model.factor == pytest.approx(0.5)


def test_fewer_than_five_points_use_the_median_ratio_and_no_overhead():
    model = fit_model([(100, 50), (100, 30), (100, 80)])
    assert (model.fitted, model.overhead_ms, model.runs) == (False, 0, 3)
    assert model.factor == pytest.approx(0.5)


def test_no_points_at_all_is_factor_one():
    model = fit_model([])
    assert (model.fitted, model.overhead_ms, model.factor, model.runs) == (False, 0, 1.0, 0)


def test_a_negative_slope_falls_back_to_the_median_ratio():
    points = [(100, 100), (200, 90), (300, 80), (400, 70), (500, 60)]
    model = fit_model(points)
    assert model.fitted is False and model.overhead_ms == 0
    assert model.factor == pytest.approx(80 / 300)  # ratios 1, .45, .267, .175, .12


def test_equal_serial_durations_cannot_be_fitted_and_fall_back():
    model = fit_model([(100, 40)] * 5)
    assert (model.fitted, model.factor) == (False, pytest.approx(0.4))


def test_the_fit_is_clamped():
    steep = fit_model([(s, 3 * s) for s in (100, 200, 300, 400, 500)])
    assert (steep.fitted, steep.factor) == (True, 1.0)
    flat = fit_model([(s, 1000 + 0.001 * s) for s in (1000, 2000, 3000, 4000, 5000)])
    assert (flat.fitted, flat.factor) == (True, 0.05)
    negative_overhead = fit_model([(s, 0.9 * s - 50_000) for s in (100_000, 200_000, 300_000, 400_000, 500_000)])
    assert negative_overhead.overhead_ms == 0 and negative_overhead.factor == pytest.approx(0.9)
    huge_overhead = fit_model([(s, 7_200_000 + 0.5 * s) for s in (100_000, 200_000, 300_000, 400_000, 500_000)])
    assert huge_overhead.overhead_ms == MAX_OVERHEAD_MS == 1_800_000


def test_the_fallback_ratio_is_clamped():
    assert fit_model([(100, 500)]).factor == 1.0
    assert fit_model([(1000, 1)]).factor == 0.05


def test_combine_applies_the_model_and_counts_the_tests():
    model = fit_model([(s, 60_000 + 0.5 * s) for s in (100_000, 200_000, 300_000, 400_000, 500_000)])
    out = combine([(1000.4, 2000.0, True), None, (3000.0, 5000.0, False)], model)
    assert out["estimate_ms"] == round(60_000 + 0.5 * 4000.4)
    assert out["upper_ms"] == round(60_000 + 0.5 * 7000)
    assert (out["tests_with_history"], out["tests_without_history"], out["environment_used"]) == (2, 1, 1)
    assert out["model"] == {"overhead_ms": 60_000, "factor": pytest.approx(0.5), "runs": 5, "fitted": True}
    assert isinstance(out["estimate_ms"], int) and isinstance(out["model"]["overhead_ms"], int)


def test_combine_without_history_has_no_estimate():
    out = combine([None, None], fit_model([]))
    assert (out["estimate_ms"], out["upper_ms"], out["tests_with_history"], out["tests_without_history"]) == (None, None, 0, 2)
    assert not math.isnan(out["model"]["factor"])
