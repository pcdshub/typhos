Release History
###############


v3.0.0 (2023-09-27)
===================

API Changes
-----------
- Added ``TyphosSuite.save_screenshot`` which takes a screenshot of the entire
  suite as-displayed.
- Added ``TyphosSuite.save_device_screenshots`` which takes individual
  screenshots of each device display in the suite and saves them to the
  provided formatted filename.
- ``TyphosNoteEdit`` now supports ``.add_device()`` like other typhos widgets.
  This is alongside its original ``setup_data`` API.
- ``TyphosDeviceDisplay`` composite heuristics have been removed in favor of
  simpler methods, described in the features section.
- The packaged IOC for benchmark testing is now in ``typhos.benchmark.ioc``.
- Qt object names for displays will now be set automatically to aid in
  debugging.
- ``LazySubdisplay.get_subdisplay`` now provides the option to only get
  existing widgets (by using the argument ``instantiate=False``).
- The deprecated ``TyphosConsole`` has been removed as discussed in issue #538.

Features
--------
- Add ``typhos --screenshot filename_pattern`` to take screenshots of typhos
  displays prior to exiting early (in combination with ``--exit-after``).
- ``TyphosNoteEdit`` is now a ``TyphosBase`` object and is accessible in the Qt
  designer.
- Added new designable widget ``TyphosPositionerRowWidget``.  This compact
  positioner widget makes dense motor-heavy screens much more space efficient.
- The layout method for ``TyphosDeviceDisplay`` has changed.  For large device trees,
  it now favors showing the compact "embedded" screens over detailed screens.  The order
  of priority is now as follows:
- For top-level devices (e.g., ``at2l0``), the template load priority is as follows:
  * Happi-defined values (``"detailed_screen"``, ``embedded_screen"``, ``"engineering_screen"``)
  * Device-specific screens, if available (named as ``ClassNameHere.detailed.ui``)
  * The detailed tree, if the device has sub-devices
  * The default templates
- For nested displays in a device tree, sub-device (e.g., ``at2l0.blade_01``)
  template load priority is as follows:
  * Device-specific screens, if available (named as ``ClassNameHere.embedded.ui``)
  * The detailed tree, if the device has sub-devices
  * The default templates (``embedded_screen.ui``)
- Increase motor timeouts proportionally for longer moves.
- Python 3.11 is now being targeted for support in typhos.
- Added dynamic font sizer utility which can work with some Qt-provided widgets
  as well as PyDM widgets.

Bugfixes
--------
- Fix an issue where setpoint widgets in the full positioner
  widget had become zero-width.
- Creates new notes file if requested note file does not exist
- typhos suites will now resize in width to fit device displays.
- For devices which do not require keyword arguments to instantiate, the typhos
  CLI will no longer require an empty dictionary.  That is, ``$ typhos
  ophyd.sim.SynAxis[]`` is equivalent to ``$ typhos ophyd.sim.SynAxis[{}]``.
  As before, ophyd's required "name" keyword argument is filled in by typhos by
  default.
- Fix an issue where ophyd signals with floats would always display with a
  precision of 0 without special manual configuration. Floating-point signals
  now default to a precision of 3.
- Fix issues with running the CLI benchmarks in certain
  conda installs, particularly python>=3.10.
- ``ophyd.Kind`` usage has been fixed for Python 3.11. Python 3.11 differs in
  enumeration of ``IntFlag`` items, resulting in typhos only picking up
  component kinds that were a power of 2.
- ``multiprocessing`` is no longer used to spawn the test suite benchmarking
  IOC, as it was problematic for Python 3.11.  The provided IOC is now spawned
  using the same utilities provided by the caproto test suite.
- Vendored pydm ``load_ui_file`` and modified it so we can always get our
  ``Display`` instance back in ``TyphosDeviceDisplay``.
- Ignore deleted qt objects on ``SignalConnection.remove_connection``, avoiding
  teardown error tracebacks.
- Avoid creating subdisplays during a call to ``TyphosSuite.hide_subdisplays``
- Added a pytest hook helper to aid in finding widgets that were not cleaned
- Avoid failing screenshot taking when widgets are garbage collected at the
  same time.
- Avoid race condition in description cache if the cache is externally cleared
  when a new description callback is received.
- Avoid uncaught ``TypeError`` when ``None`` is present in a positioner
  ``.limits``.

Maintenance
-----------
- adds TyphosDisplaySwitcher to TyphosPositionerRowWidget
- adds checklist to Pull Request Template
- Add pre-release notes scripts
- Update build requirements to use pip-provided extras for documentation and test builds
- Update PyDM pin to >=1.19.1 due to Display method being used.
- Avoid hundreds of warnings during line profiling profiling by intercepting
  messages about profiling the wrapped function instead of the wrapper.
- The setpoint history menu on ``TyphosLineEdit`` is now only created on-demand.

Contributors
------------
- ZLLentz
- klauer
- tangkong
- zllentz


v2.4.1 (2023-4-4)
=================

Description
-----------
This is a bugfix and maintenance/CI release.

Bugfixes
--------
- Include the normal PyDM stylesheets in the loading process.
  Previously, this was leading to unexpected behavior.

Maintenance
-----------
- Fix an issue related to a deleted flake8 mirror.
- Migrates from Travis CI to GitHub Actions for continuous integration testing, and documentation deployment.
- Updates typhos to use setuptools-scm, replacing versioneer, as its version-string management tool of choice.
- Syntax has been updated to Python 3.9+ via ``pyupgrade``.
- typhos has migrated to modern ``pyproject.toml``, replacing ``setup.py``.
- Sphinx 6.0 now supported for documentation building.

Contributors
------------
- tangkong
- zllentz


v2.4.0 (2022-11-4)
==================

Description
-----------
This is a small release with features for improving the usage
and configurability of the ``PositionerWidget``.

Features
--------
- Report errors raised during the execution of positioner
  ``set`` commands in the positioner widget instead of in a pop-up.
  This makes it easier to keep track of which positioner widget
  is associated with which error and makes it less likely that the
  message will be missed or lost on large monitors.
- Add a designer property to ``PositionerWidget``, ``alarmKindLevel``,
  to configure the enclosed alarm widget's ``kindLevel`` property in
  designer. This was previously only configurable in code.

Contributors
------------
- zllentz


v2.3.3 (2022-10-20)
===================

Description
-----------
This is a small release with bugfixes and maintenance.

Bugfixes
--------
- Do not wait for lazy signals when creating a SignalPanel.
  This was causing long setup times in some applications.
- Call stop with success=True in the positioner widget to avoid causing
  our own UnknownStatusError, which was then displayed to the user.

Maintenance
-----------
- Add cleanup for background threads.
- Add replacement for functools.partial usage in methods as
  this was preventing TyphosSuite from getting garbage collected.
- Removes custom designer widget plugin,
  instead relying on PyDM's own mechanism
- Use pydm's data plugin entrypoint to include the sig and happi channels.
- Prevent TyphosStatusThread objects from being orphaned.

Contributors
------------
- klauer
- tangkong
- zllentz


v2.3.2 (2022-07-28)
===================

Description
-----------
This is a bugfix and maintenance release.

Fixes
-----
- Fix various instances of clipping in the positioner widget.
- Show Python documentation when no web help is available.
- Fix issues with suite sidebar width.
- Lazy load all tools to improve performance.
- Fix the profiler to also profile class methods.
- Use cached paths for finding class templates.
- Properly handle various deprecations and deprecation warnings.
- Fix usage of deprecated methods in happi (optional dependency).

Maintenance
-----------
- Log "unable to add device" without the traceback, which was previously unhelpful.
- Pin pyqt at 5.12 for test suite incompatibility in newer versions.
- Ensure that test.qss test suite artifact is cleaned up properly.
- Fix the broken test suite.
- Pin jinja2 at <3.1 in CI builds for sphinx <4.0.0 compatibility

Contributors
------------
- anleslac
- klauer
- zllentz


v2.3.1 (2022-05-02)
===================

Description
-----------
This is a small bugfix release.

Fixes
-----
- Fix an issue where the configuration menu would be defunct for
  custom template screens.

Maintenance
-----------
- Add some additional documentation about sig:// and cli usage.
- Configure and satisfy the repository's own pre-commit checks.
- Update versioneer install to current latest.

Contributors
------------
- klauer
- zllentz


v2.3.0 (2022-03-31)
===================

Description
-----------
This is a small release with fixes and features that were implemented
last month.

Features
--------
- Add the option to hide displays in the suite at launch,
  rather than automatically showing all of them.
- Allow the sig:// protocol to be used in typhos templates by
  automatically registering all of a device's signals at launch.

Fixes
-----
- Fix an issue where an assumption about the nature of EpicsSignal
  object was breaking when using PytmcSignal objects from pcdsdevices.
- Make a workaround for a C++ wrapped exception that could happen
  in specific orders of loading and unloading typhos alarm widgets.


v2.2.1 (2022-02-07)
===================

Description
-----------
This is a small bugfix release that was deployed as a hotfix
to avoid accidental moves.

Fixes
-----
- Disable scroll wheel interaction with positioner combo boxes.
  This created a situation where operators were accidentally
  requesting moves while trying to scroll past the control box.
  This was previously fixed for the typhos combo boxes found on
  the various automatically generated panels in v1.1.0, but not
  for the positioner combo boxes.


v2.2.0 (2021-11-30)
===================

Description
-----------
This is a feature and bugfix release to extend the customizability of
typhos suites and launcher scrips, to fix various issues in control
layer and enum handling, and to do some necessary CI maintenance.

Enhancements / What's new
-------------------------
* Add suite options for layouts, display types, scrollbars, and
  starting window size. These are all also available as CLI arguments,
  with the intention of augmenting typhos suite launcher scripts.
  Here are some examples:

  * ``--layout grid --cols 3``: lays out the device displays in a 3-column
    grid
  * ``--layout flow``: lays out the device displays in a grid that adjusts
    dynamically as the window is resized.
  * ``--display-type embed``: starts all device displays in their embedded
    state
  * ``--size 1000,1000``: sets a starting size of 1000 width, 1000 height for
    the suite window.

  See `#450 <https://github.com/pcdshub/typhos/pull/450>`_

Fixes
-----
* Respect ophyd signal enum_strs and metadata updates. Previously, these were
  ignored, but these can update during the lifetime of a screen and should be
  used. (`#459 <https://github.com/pcdshub/typhos/pull/459>`_)
* Identify signals that use non-EPICS control layers and handle them
  appropriately. Previously, these would be misidentified as EPICS signals
  and handled using the ca:// PyDM plugin, which was not correct.
  (`#463 <https://github.com/pcdshub/typhos/pull/463>`_)
* Fix an issue where get_native_methods could fail. This was not observed
  in the field, but it broke the test suite.
  (`#464 <https://github.com/pcdshub/typhos/pull/464>`_)

Maintenance
-----------
* Fix various issues related to the test suite stability.


v2.1.0 (2021-10-18)
===================

Description
-----------
This is a minor feature release of typhos.

Enhancements / What's new
-------------------------
* Added option to pop out documentation frame
  (`#458 <https://github.com/pcdshub/typhos/pull/458>`_)

Fixes
-----
* Fixed authorization headers on Typhos help widget redirect
  (`#457 <https://github.com/pcdshub/typhos/pull/457>`_)

  * This allows for the latest Confluence to work with Personal
    Access Tokens while navigating through the page

Maintenance
-----------
* Reduced javascript log message spam from the web view widget
  (part of `#457 <https://github.com/pcdshub/typhos/pull/457>`_)
* Reduced log message spam from variety metadata handling
  (part of `#457 <https://github.com/pcdshub/typhos/pull/457>`_)
* Fixed compatibility with pyqtgraph v0.12.3
* Web-related widgets are now in a new submodule `typhos.web`.


v2.0.0 (2021-08-05)
===================

Description
-----------
This is a feature update with backwards-incompatible changes, namely the
removal and relocation of the LCLS typhos templates.

API Breaks
----------
All device templates except for the ``PositionerBase`` template have been
moved from typhos to pcdsdevices, which is where their device classes
are defined. This will break LCLS environments that update typhos without
also updating pcdsdevices, but will not affect environments outside of LCLS.

Enhancements / What's New
-------------------------
- Add the ``TyphosRelatedSuiteButton``, a ``QPushButton`` that will open a device's
  typhos screen. This can be included in embedded widgets or placed on
  traditional hand-crafted pydm screens as a quick way to open the typhos
  expert screen.
- Add the typhos help widget, which is a new addition to the display switcher
  that is found in all built-in typhos templates. Check out the ``?`` button!
  See the docs for information on how to configure this.
  The main features implemented here are:

  - View the class docstring from inside the typhos window
  - Open site-specific web documentation in a browser
  - Report bugs directly from the typhos screen

- Expand the ``PositionerWidget`` with aesthetic updates and more features:

  - Show driver-specific error messages from the IOC
  - Add a "clear error" button that can be linked to IOC-specific error
    reset routines by adding a ``clear_error`` method to your positioner
    class. This will also clear status errors returned from the positioner's
    set routine from the display.
  - Add a moving/done_moving indicator (for ``EpicsMotor``, uses the ``.MOVN`` field)
  - Add an optional ``TyphosRelatedSuite`` button
  - Allow the ``stop`` button to be removed if the ``stop`` method is missing or
    otherwise raises an ``AttributeError`` on access
  - Add an alarm indicator

- Add the ``typhos.ui`` entry point. This allows a module to notify typhos that
  it should check specified directories for custom typhos templates. To be
  used by typhos, the entry point should load a ``str``, ``pathlib.Path``, or ``list``
  of such objects.
- Move the examples submodule into the ``typhos.examples`` submodule, so we can
  launch the examples by way of e.g. ``typhos -m typhos.examples.positioner``.
- For the alarm indicator widgets, allow the pen width, pen color, and
  pen style to be customized.

Compatibility / Fixes
---------------------
- Find a better fix for the issue where the positioner combobox widget would
  put to the PV on startup and on IOC reboot
  (see ``v1.1.0`` note about a hacky workaround).
- Fix the issue where the positioner combobox widget could not be used to
  move to the last position selected.
- Fix an issue where a positioner status that was marked as failed immediately
  would show as an unknown error, even if it had an associated exception
  with useful error text.

Docs / Testing
--------------
- Add documentation for all features included in this update
- Add documentation for how to create custom ``typhos`` templates


v1.2.0 (2021-07-09)
===================

Description
-----------
This is a feature update intended for use in lucid, but it may also be useful
elsewhere.

Enhancements / What's New
-------------------------
Add a handful of new widgets for indicating device alarm state. These will
change color based on the most severe alarm found among the device's signals.
Their shapes correlate with the available shapes of PyDMDrawingWidget:

- TyphosAlarmCircle
- TyphosAlarmRectangle
- TyphosAlarmTriangle
- TyphosAlarmEllipse
- TyphosAlarmPolygon

Compatibility / Fixes
---------------------
- Add a sigint handler to avoid annoying behavior when closing with Ctrl-C on
  macOS.
- Increase some timeouts to improve unit test consistency.


v1.1.6 (2021-04-05)
===================

Description
-----------
This is maintenance/compatibility release for pydm v1.11.0.

Compatibility / Fixes
---------------------
- Internal fixes regarding error handling and input sanitization.
  Some subtle issues cropped up here in the update to pydm v1.11.0.
- Fix issue where the test suite would freeze when pydm displays
  an exception to the user.


v1.1.5 (2020-04-02)
===================

Description
-----------
This is a maintenance release

Compatibility / Fixes
---------------------
- Fix an issue where certain data files were not included in the package
  build.


v1.1.4 (2020-02-26)
===================

Description
-----------
This is a bugfix release

Compatibility / Fixes
---------------------
- Fix returning issue where certain devices could fail to load with a
  "dictionary changed during iteration" error.
- Fix issue where the documentation was not building properly.


v1.1.3 (2020-02-10)
===================

Description
-----------
This is a minor screen inclusion release.

Enhancements / What's New
-------------------------
- Add a screen for AT1K4. This, and similar screens, should be moved out of
  typhos and into an LCLS-specific landing-zone, but this is not ready yet.


v1.1.2 (2020-12-22)
===================

Description
-----------
This is a minor bugfix release.

Compatibility / Fixes
---------------------
- Fix issue where ``SignalRO`` from ``ophyd`` was not showing as read-only.
- Update the AT2L0 screen to not have a redundant calculation dialog as per
  request.


v1.1.1 (2020-08-19)
===================

Description
-----------
This is a bugfix release. Please use this instead of v1.1.0.

Compatibility / Fixes
---------------------
- Fix issue with ui files not being included in the manifest
- Fix issue with profiler failing on tests submodule


v1.1.0 (2020-08-18)
===================

Description
-----------
This is a big release with many fixes and features.

Enhancements / What's New
-------------------------
- Make Typhos aware of variety metadata and assign appropriate widgets based
  on the variety metadata assigned in pcdsdevices.
- Split templates into three categories: core, devices, and widgets.
  Core templates are the main typhos display templates, e.g. detailed_tree.
  Devices templates are templates tailored for specific device classes.
  Widgets templates define special typhos widgets like tweakable, positioner,
  etc.
- Add attenuator calculator screens. These may be moved to another repo in a
  future release.
- Add information to loading widgets indicating timeout details.

Compatibility / fixes
---------------------
- Fix issue with comboboxes being set on mouse scroll.
- Allow loading classes from cli with numbers in the name.
- Fix issue with legacy codepath used in lightpath.
- Fix issue with widget UnboundLocalError.
- Hacky workaround for issue with newer versions of Python.
- Hacky workaround for issue where positioner widget puts on startup.
- Fix issue with unset _channel member.
- Fix issue with typhos creating and installing a tests package separate
  from the main typhos package.

Docs / Testing
--------------
- Add variety testing IOC.
- Add doctr_versions_menu extension to properly render version menu.
- Fix issues with failing benchmark tests


v1.0.2 (2020-07-01)
===================

Description
-----------

A bug fix and package maintenance release.

Enhancements / What's New
-------------------------
-   PositionerWidget moves set their timeouts based on expected
    velocity and acceleration, rather than a flat 10 seconds.

Compatibility / fixes
---------------------
-   Ensure that widgets with no layout or minimum size are still displayed.
-   Update local conda recipe to match conda-forge.
-   Update CI to used shared configurations.


v1.0.1 (2020-05-20)
===================

Description
-----------

A bug fix release with a minor addition.

Enhancements / What's New
-------------------------
-  TyphosLoading now takes in a timeout value to switch the animation
   with a text message stating that the operation timed-out after X
   seconds.


Compatibility / fixes
---------------------

-  Combobox widgets were appearing when switching or refreshing templates.


v1.0.0 (2020-05-18)
===================

Description
-----------

A major new feature release with added views for complex devices and
simplified configurability.

As planned, the deprecated import name ``typhon`` and the ``typhon``
command-line tool have been removed.

Enhancements / What's New
-------------------------

-  Panels: New ``TyphosCompositeSignalPanel``, which composes multiple
   ``TyphosDisplay``\ s in a tree-like view.
-  Benchmarking: new profiling tools accessible in the command-line
   ``typhos`` tool, allowing for per-line profiling of standardized
   devices. (``--benchmark``)
-  Template discovery: templates are discovered based on screen macros
   and class inheritance structure, with the fallback of built-in
   templates.
-  New command-line options for testing with mock devices
   (``--fake-device``).
-  Performance: Major performance improvements by way of background
   threading of signal description determination, display path caching,
   and connection status monitoring to reduce GUI thread blocking.
-  Display: Adds a "display switcher" tool for easy access to different
   screen types.
-  Display: Adds a "configuration" button to displays.
-  Filtering: Filter panel contents by kinds.
-  Filtering: Filter panel contents by signal names.
-  Setpoint history: a history of previous setpoints has been added to
   the context menu in ``TyphosLineEdit``.
-  Positioner widgets have been redesigned to be less magical and more fault-
   tolerant.  Adds designable properties that allow for specification of
   attribute names.
-  Anything that inherits from ``PositionerBase`` will have the template as an
   option (``EpicsMotor``, ``PCDSMotorBase``, etc.)
-  Reworked default templates to remove the ``miscellaneous`` panel.  Omitted
   signals may still be shown by way of panel context menus or configuration
   menus.

Compatibility / fixes
---------------------

-  Python 3.8 is now being included in the test suite.
-  Happi is now completely optional.
-  Popped-out widgets such as plots will persist even when the parent
   display is closed.
-  Font sizes should be more consistent on various DPI displays.
-  Module ``typhos.signal`` has been renamed to ``typhos.panel``.
-  ``TyphosTimePlot`` no longer automatically adds signals to the plot.
-  Removed internally-used ``typhos.utils.grab_kind``.
-  OSX layout of ``TyphosSuite`` should be improved using the unified title and
   toolbar.

v0.7.0 (2020-03-09)
===================

-  Fix docs deployment
-  Add “loading in progress” gif
-  Fix sorting of signals
-  Automatically choose exponential format based on engineering units
-  Fix lazy loading in ophyd 1.4
-  Save images of widgets when running tests
-  Add a new “PopBar” which pops in the device tree in the suite
-  Clean up the codebase - sort all imports + fix style
-  Relocate SignalRO to a single spot


v0.6.0 (2020-01-09)
===================

Description
-----------

This release is dedicated to the renaming of the package from ``Typhon``
to ``Typhos``. The main reason for the renaming is a naming conflict at
PyPI that is now addressed.

Compatibility
-------------

This release is still compatible and will throw some DeprecationWarnings
when ``typhon`` is used. The only incompatible piece is for Qt
Stylesheets. You will need to add the ``typhos`` equivalents to your
custom stylesheets if you ever created one.

**This is the first release with the backwards compatibility for typhon.
In two releases time it will be removed.**


v0.5.0 (2019-09-18)
===================

Description
-----------

It was a long time since the latest release of ``Typhon``. It is time
for a new one. Next releases will have again the beautiful and
descriptive messages for enhancements, bug fixes and etc.

What’s New
----------

A lot.


v0.2.1 (2018-09-28)
===================

Description
-----------

This is a minor release of the ``Typhon`` library. No major features
were added, but instead the library was made more stable and utilitarian
for use in other programs. This includes making sure that any calls to a
signal’s values or metadata are capable of handling disconnections. It
also moves some of the methods that were hidden in larger classes or
functions into smaller, more useful methods.

Enhancements
~~~~~~~~~~~~

-  ``SignalPlugin`` now transmits all the metadata that is guaranteed to
   be present from the base ``Signal`` object. This includes
   ``enum_strs``, ``precision``, and ``units``
   (`#92 <https://github.com/pcdshub/typhos/issues/92>`__)
-  ``DeviceDisplay`` now has an optional argument ``children``. This
   makes it possible to ignore a ``Device`` components when creating the
   display (`#96 <https://github.com/pcdshub/typhos/issues/96>`__)
-  The following utility functions have been created to ensure that a
   uniform approach is taken for\ ``Device`` introspection:
   ``is_signal_ro``, ``grab_hints``
   (`#98 <https://github.com/pcdshub/typhos/issues/98>`__)

Maintenance
~~~~~~~~~~~

-  Catch exceptions when requesting information from a ``Signal`` in
   case of disconnection, e.t.c
   (`#91 <https://github.com/pcdshub/typhos/issues/91>`__,
   `#92 <https://github.com/pcdshub/typhos/issues/92>`__)
-  The library now imports entirely from the ``qtpy`` compatibility
   layer (`#94 <https://github.com/pcdshub/typhos/issues/94>`__)

Deprecations
~~~~~~~~~~~~

-  The ``title`` command in ``SignalPanel`` was no longer used. It is
   still accepted in this release, but will dropped in the next major
   release (`#90 <https://github.com/pcdshub/typhos/issues/90>`__)


v0.2.0 (2018-06-27)
===================

Description
-----------

This ``Typhon`` release marks the transition from prototype to a stable
library. There was a variety of API breaks and deprecations after
``v0.1.0`` as many of the names and functions were not future-proof.

Enhancements
~~~~~~~~~~~~

-  ``Typhon`` is now available on the ``pcds-tag`` Anaconda channel
   (`#45 <https://github.com/pcdshub/typhos/issues/45>`__)
-  ``Typhon`` now installs a special data plugin for ``PyDM`` called
   ``SignalPlugin``. This uses the generic ``ophyd.Signal`` methods to
   communicate information to PyDM widgets.
   (`#63 <https://github.com/pcdshub/typhos/issues/63>`__)
-  ``Typhon`` now supports two different stylesheets a “light” and
   “dark” mode. These are not activated by default, but instead can be
   accessed via ``use_stylesheet`` function
   (`#61 <https://github.com/pcdshub/typhos/issues/61>`__,
   `#89 <https://github.com/pcdshub/typhos/issues/89>`__)
-  There is now a sidebar to the ``DeviceDisplay`` that makes adding
   devices and tools easier. The ``add_subdisplay`` function still works
   but it is preferable to use the more specific ``add_tool`` and
   ``add_subdevice``.
   (`#61 <https://github.com/pcdshub/typhos/issues/61>`__)
-  ``Typhon`` will automaticaly create a ``PyDMLogDisplay`` to show the
   output of the ``logging.Logger`` object attached to each
   ``ophyd.Device``
   (`#70 <https://github.com/pcdshub/typhos/issues/70>`__)
-  ``Typhon`` now creates a ``PyDMTimePlot`` with the “hinted”
   attributes of the Device. This can be configured at runtime to have
   fewer or more signals
   (`#73 <https://github.com/pcdshub/typhos/issues/73>`__)

API Changes
~~~~~~~~~~~

-  All of the ``Panel`` objects have been moved to different files.
   ``SignalPanel`` now resides in ``typhon.signal`` while the base
   ``Panel`` that is no longer used to display signals is in the generic
   ``typhon.widgets`` renamed as ``TogglePanel``
   (`#50 <https://github.com/pcdshub/typhos/issues/50>`__)

Deprecations
~~~~~~~~~~~~

-  ``RotatingImage`` has been removed as it is no longer used by the
   library (`#58 <https://github.com/pcdshub/typhos/issues/58>`__)
-  ``ComponentButton`` has been removed as it is no longer used by the
   library(`#58 <https://github.com/pcdshub/typhos/issues/58>`__)
-  The base ``DeviceDisplay`` no longer has a plot. The
   ``add_pv_to_plot`` function has been completely removed.
   (`#58 <https://github.com/pcdshub/typhos/issues/58>`__)

Dependencies
~~~~~~~~~~~~

-  ``TyphonDisplay`` requires ``ophyd >= 1.2.0``. The ``PyDMLogDisplay``
   tool is attached to the ``Device.log`` that is now present on all
   ``ophyd`` devices.
   (`#53 <https://github.com/pcdshub/typhos/issues/53>`__)
-  ``pydm >= 1.2.0`` due to various bug fixes and widget additions
   (`#63 <https://github.com/pcdshub/typhos/issues/63>`__)
-  ``QDarkStyleSheet`` is now included in the recipe to provide dark
   stylesheet support.
   (`#89 <https://github.com/pcdshub/typhos/issues/89>`__)

Bug Fixes
~~~~~~~~~

-  ``SignalPanel`` previously did not account for the fact that ``read``
   and ``configuration`` attributes could be devices themselves
   (`#42 <https://github.com/pcdshub/typhos/issues/42>`__)
-  ``SignalPanel`` no longer assumes that all signals are
   ``EpicsSignal`` objects
   (`#71 <https://github.com/pcdshub/typhos/issues/71>`__)


v0.1.0 (2017-12-15)
===================

The initial release of Typhon. This serves as a proof of concept for the
automation of PyDM screen building as informed by the structure of an
Ophyd Device.

Features
--------

-  Generate a full ``DeviceDisplay`` with all of the device signals and
   sub-devices available
-  Include methods from the ophyd Device in the User Interface,
   automatically parse the arguments to make a widget representation of
   the function
-  Include ``png`` images associated with devices and sub-devices
