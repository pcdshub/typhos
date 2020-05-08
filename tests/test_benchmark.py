"""
Run the benchmark test cases using pytest-benchmark
"""
import pytest

from typhos.benchmark.cases import benchmark_tests


# Name the test cases using the keys, run using the values
@pytest.mark.parametrize('test_function', benchmark_tests.keys())
def test_benchmark(test_function, benchmark):
    """
    Run all registered benchmarks.

    These typically just open and close a particular typhos screen.
    """
    benchmark(benchmark_registry[test_function])
