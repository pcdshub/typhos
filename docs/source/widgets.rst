=======
Widgets
=======
Typhos uses a few custom widgets to create a clean and concise user interface.
While most users should not be interacting with these directly, there may be a
need if a user opts to create their display by hand instead of automatically
generating one. If you would just like a widget for an ``ophyd.Signal``, there
is a function available:

.. autofunction:: typhos.widgets.create_signal_widget

Panels
======
One of the major design principles of Typhos is that users should be able to
see what they need and hide one they don't. Thefore, many of the widget
implementations are placed in "Panels" these consist of QPushButton header that
hides and shows the contents. Each variation in Typhos is documented below.

.. autosummary::
   :toctree: generated


Basic Signal Panels
===================

.. autoclass:: typhos.panel.SignalPanel
   :members:

.. autoclass:: typhos.panel.CompositeSignalPanel
   :members:


Composite Signal Panels
=======================

.. autoclass:: typhos.panel.CompositeSignalPanel
   :members:

.. autoclass:: typhos.panel.TyphosCompositeSignalPanel
   :members:


TyphosPositionerWidget
======================

.. autoclass:: typhos.TyphosPositionerWidget
   :members:


Functions and Methods
=====================

.. autoclass:: typhos.func.FunctionPanel
    :members:

.. autoclass:: typhos.TyphosMethodButton
   :members:
