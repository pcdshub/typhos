"""
Run the benchmark test cases using pytest-benchmark
"""
from typing import List

import pytest
from epics import PV
from qtpy import QtWidgets

from ..benchmark import utils
from ..benchmark.cases import unit_tests
from ..benchmark.profile import profiler_context
from ..suite import TyphosSuite
from .conftest import save_image


def get_top_level_suites() -> list[TyphosSuite]:
    app = QtWidgets.QApplication.instance()
    assert app is not None
    return list(
        widget
        for widget in app.topLevelWidgets()
        if isinstance(widget, TyphosSuite)
    )


# Name the test cases using the keys, run using the values
@pytest.mark.parametrize('unit_test_name', unit_tests.keys())
def test_benchmark(unit_test_name, qapp, qtbot, benchmark, monkeypatch):
    """
    Run all registered benchmarks.

    These typically just open and close a particular typhos screen.
    """
    # Crudely permenant patch here to get around cleanup bug
    assert len(get_top_level_suites()) == 0
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
