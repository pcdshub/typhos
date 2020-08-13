import random

import ophyd
import pytest
import pytestqt

import typhos.cache


def ensure_cache_clear(qtbot, signal, cache):
    """
    Really, really ensure the cache is clear.

    Waits for up to 1s to ensure no new signals are emitted from previous tests
    that could interfere with later tests.

    Parameters
    ----------
    qtbot : pytestqt.QtBot
        The qtbot helper.

    signal : QtCore.Signal
        A signal to wait for.
            The qtbot helper.

    cache : object
        Cache object with ``clear`` method.
    """
    cache.clear()

    # Ensure no callbacks are still in flight
    try:
        with qtbot.wait_signal(signal, timeout=1000):
            ...
    except pytestqt.exceptions.TimeoutError:
        ...

    cache.clear()


@pytest.fixture(scope='function')
def describe_cache(qtbot):
    cache = typhos.cache.get_global_describe_cache()

    ensure_cache_clear(qtbot, cache.new_description, cache)
    yield cache
    ensure_cache_clear(qtbot, cache.new_description, cache)


@pytest.fixture(scope='function')
def type_cache(qtbot, describe_cache):
    cache = typhos.cache.get_global_widget_type_cache()

    ensure_cache_clear(qtbot, cache.widgets_determined, cache)
    yield cache
    ensure_cache_clear(qtbot, cache.widgets_determined, cache)


@pytest.fixture(scope='function')
def sig():
    name = 'test{}'.format(random.randint(0, 10000))
    sig = ophyd.Signal(name=name)
    yield sig
    sig.destroy()


def test_describe_cache_signal(qtbot, describe_cache, sig):
    # Check that `new_description` is emitted with the correct args:
    with qtbot.wait_signal(describe_cache.new_description) as block:
        assert describe_cache.get(sig) is None

    assert block.args == [sig, sig.describe()[sig.name]]

    # And the description is now readily available:
    assert describe_cache.get(sig) == sig.describe()[sig.name]

    # And that clearing the cache works:
    describe_cache.clear()
    assert describe_cache.get(sig) is None


def test_widget_type_signal(qtbot, type_cache, sig):
    with qtbot.wait_signal(type_cache.widgets_determined) as block:
        assert type_cache.get(sig) is None

    assert block.args[0] is sig
    assert type_cache.get(sig) is block.args[1]
