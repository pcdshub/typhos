"""
Run the benchmark test cases using pytest-benchmark
"""
import pytest

from typhos.benchmark.cases import benchmark_tests

from .conftest import save_image


# Name the test cases using the keys, run using the values
@pytest.mark.parametrize('test_function', benchmark_tests.keys())
def test_benchmark(test_function, benchmark):
    """
    Run all registered benchmarks.

    These typically just open and close a particular typhos screen.
    """
    window = benchmark(benchmark_tests[test_function])
    save_image(window, 'test_benchmark_' + test_function)
