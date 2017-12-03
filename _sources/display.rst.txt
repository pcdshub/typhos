==============
Display Types
==============
Typhon has two major widgets that users are expected to interface with. The
first is the :class:`.TyphonDisplay`. This is the barebones implementation. No
signals, or widgets are automatically populated in the screen. In fact, by
default most of the widgets will be hidden. You can then manually add signals
to the panels and plots, the panels will only show themselves when you add PVs.

For a more automated approach, the :class:`.DeviceDisplay` will take your ophyd
Device and populate PVs and components into the appropriate locations

TyphonDisplay
=============
.. autoclass:: typhon.TyphonDisplay
   :members:

DeviceDisplay
=============
.. autoclass:: typhon.DeviceDisplay
   :members:
   :show-inheritance:
