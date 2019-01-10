==============
Display Types
==============
Typhon has two major widgets that users are expected to interface with. The
first is the :class:`.TyphonDeviceDisplay`, which shows device information, and
:class:`.TyphonSuite` which contains multiple devices and tools. This is the
barebones implementation. No signals, or widgets are automatically populated in
the screen. In fact, by default most of the widgets will be hidden. You can
then manually add signals to the panels and plots, the panels will only show
themselves when you add PVs.


TyphonSuite
===========

.. autoclass:: typhon.TyphonSuite
   :members:

TyphonDeviceDisplay
===================

.. autoclass:: typhon.TyphonDeviceDisplay
   :members:
