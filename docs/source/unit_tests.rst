################
Unit Test Quirks
################

Typhos, from time to time, has had issues with its unit tests.
These often manifest as test failures and segmentation faults that only occur
when running the tests on a cloud platform.

By and large, these are related to difficulty with cleaning up resources from
tests that allocate qt widgets.


Things to Know for Test Writers
-------------------------------

- Always use the ``qtbot`` fixture (from the ``pytest-``qt package)
- Always call ``qtbot.add_widget(widget)`` on any widget you create in your test.
  This helps clean up your widget after the test is complete.
- Use the ``qapp`` fixture and call ``qapp.processEvents()`` if you need "something"
  in the qt world to happen.
- Use the ``noapp`` feature if you need to test code that calls ``qapp.exec_()`` or
  ``qapp.exit()``. Calling this code with no fixture will break the test suite for
  all future tests than need the ``qapp``.
- If your test is segfaulting, try using the ``@pytest.mark.no_gc`` decorator
  to skip the manual garbage collection step from the pytest_runtest_call hook
  in conftest.py. In some cases (e.g. the positioner widgets) this is an ill-timed
  redundant call.
- If an external package's widgets (and none of ours) are showing up in the
  widget cleanup check (also in the ``pytest_runtest_call`` hook), try using
  the ``@pytest.mark.no_cleanup_check`` decorator. If these come from ``typhos``
  it's fairly important to fix the issue, but if they come from external
  package it's hard to do something about it.


Local vs Cloud
--------------

There are a few major differences between local and cloud builds, even
on the same architecture:

- Cloud builds set the environment variable for offscreen rendering (no rendering).
  This slightly changes the timing and drastically changes the implementation of
  the qt drawing primitives. You can set this yourself locally via
  ``export QT_QPA_PLUGIN=offscreen``.
- Cloud builds use the latest versions of packages, which may differ from the ones
  you have installed locally.
