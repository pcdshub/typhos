=======
Widgets
=======
Typhos uses a few custom widgets to create a clean and concise user interface.
While most users should not be interacting with these directly, there may be a
need if a user opts to create their display by hand instead of automatically
generating one.


Determining widget types
========================

If you would just like a widget for an ``ophyd.Signal``, there
is a function available:

.. autofunction:: typhos.widgets.create_signal_widget

.. autoclass:: typhos.widgets.SignalWidgetInfo
   :members:

.. autofunction:: typhos.widgets.widget_type_from_description

.. autofunction:: typhos.widgets.determine_widget_type


Panels
======
One of the major design principles of Typhos is that users should be able to
see what they need and hide one they don't. Thefore, many of the widget
implementations are placed in "Panels" these consist of QPushButton header that
hides and shows the contents. Each variation in Typhos is documented below.


Basic Signal Panels
-------------------

.. autoclass:: typhos.panel.SignalPanel
   :members:

.. autoclass:: typhos.TyphosSignalPanel
   :members:


Composite Signal Panels
-----------------------

.. autoclass:: typhos.panel.CompositeSignalPanel
   :members:

.. autoclass:: typhos.TyphosCompositeSignalPanel
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


Miscellaneous
=============

.. autoclass:: typhos.widgets.ClickableBitIndicator
   :members:

.. autoclass:: typhos.widgets.ImageDialogButton
   :members:

.. autoclass:: typhos.widgets.SignalDialogButton
   :members:

.. autoclass:: typhos.widgets.SubDisplay
   :members:

.. autoclass:: typhos.widgets.TyphosArrayTable
   :members:

.. autoclass:: typhos.widgets.TyphosByteIndicator
   :members:

.. autoclass:: typhos.widgets.TyphosByteSetpoint
   :members:

.. autoclass:: typhos.widgets.TyphosComboBox
   :members:

.. autoclass:: typhos.widgets.TyphosCommandButton
   :members:

.. autoclass:: typhos.widgets.TyphosCommandEnumButton
   :members:

.. autoclass:: typhos.widgets.TyphosLabel
   :members:

.. autoclass:: typhos.widgets.TyphosLineEdit
   :members:

.. autoclass:: typhos.widgets.TyphosScalarRange
   :members:

.. autoclass:: typhos.widgets.TyphosSidebarItem
   :members:

.. autoclass:: typhos.textedit.TyphosTextEdit
   :members:

.. autoclass:: typhos.widgets.WaveformDialogButton
   :members:


Designer
========

.. autoclass:: typhos.widgets.TyphosDesignerMixin
   :members:
