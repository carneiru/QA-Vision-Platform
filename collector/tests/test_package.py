from importlib.metadata import version

import qav_collector


def test_the_version_has_a_single_source():
    assert qav_collector.__version__ == "0.3.0"
    assert version("qav-collector") == qav_collector.__version__
