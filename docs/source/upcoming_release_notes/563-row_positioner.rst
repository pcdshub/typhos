563 row-positioner
##################

API Changes
-----------
- ``TyphosNoteEdit`` now supports ``.add_device()`` like other typhos widgets.
  This is alongside its original ``setup_data`` API.
- ``TyphosDeviceDisplay`` composite heuristics have been removed in favor of
  simpler methods, described in the features section.

Features
--------
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

Bugfixes
--------
- N/A

Maintenance
-----------
- N/A

Contributors
------------
- klauer
- ZLLentz
