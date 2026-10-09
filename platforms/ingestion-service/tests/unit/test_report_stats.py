from src.ingestion.analytics.report_stats import mean, percentile


def test_percentiles_interpolate_between_ranks():
    values = [40, 10, 30, 20]
    assert percentile(values, 0.5) == 25
    assert percentile(values, 0.9) == 37
    assert percentile([7], 0.9) == 7
    assert percentile([], 0.5) is None


def test_mean_rounds_to_whole_milliseconds():
    assert mean([100, 200, 400]) == 233
    assert mean([]) is None
