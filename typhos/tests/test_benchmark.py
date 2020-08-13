"""
Run the benchmark test cases using pytest-benchmark
"""
import pytest
from epics import PV

import typhos.benchmark.utils as utils
from typhos.benchmark.cases import unit_tests
from typhos.benchmark.profile import profiler_context

from .conftest import save_image


# Name the test cases using the keys, run using the values
@pytest.mark.parametrize('unit_test_name', unit_tests.keys())
def test_benchmark(unit_test_name, qapp, qtbot, benchmark, monkeypatch):
    """
    Run all registered benchmarks.

    These typically just open and close a particular typhos screen.
    """
    # Crudely permenant patch here to get around cleanup bug
    PV.count = property(lambda self: 1)
    suite = benchmark(inner_benchmark, unit_tests[unit_test_name], qtbot)
    save_image(suite, 'test_benchmark_' + unit_test_name)


def inner_benchmark(unit_test, qtbot):
    suite, context = unit_test()
    with context:
        qtbot.add_widget(suite)
        qtbot.wait_active(suite)
    return suite


def test_profiler(capsys):
    """Super basic test that hits most functions here"""
    with profiler_context(['typhos.benchmark.utils']):
        utils.get_native_functions(utils)
    output = capsys.readouterr()
    assert 'get_native_functions' in output.out
