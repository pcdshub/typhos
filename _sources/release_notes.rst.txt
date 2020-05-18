=================
 Release History
=================

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
