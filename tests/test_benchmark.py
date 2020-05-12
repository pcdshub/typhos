"""
Run the benchmark test cases using pytest-benchmark
"""
import pytest

from typhos.benchmark.cases import unit_tests
from typhos.suite import TyphosSuite

from .conftest import save_image


# Name the test cases using the keys, run using the values
@pytest.mark.parametrize('unit_test_name', unit_tests.keys())
def test_benchmark(unit_test_name, qtbot, benchmark):
    """
    Run all registered benchmarks.

    These typically just open and close a particular typhos screen.
    """
    suite = benchmark(inner_benchmark, unit_tests[unit_test_name], qtbot)
    save_image(suite, 'test_benchmark_' + unit_test_name)


def inner_benchmark(unit_test, qtbot):
    suite, context = unit_test()
    with context:
        qtbot.add_widget(suite)
        qtbot.wait_active(suite)
    return suite
