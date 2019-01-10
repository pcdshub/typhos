============
How it Works
============
Typhon has three major building blocks that combine into the final display seen
by the operator:

* **TyphonSuite** : The overall view for a Typhon window. It allows the
  operator to view all of the loaded components and tools.
* **TyphonDisplay** : This is the widget created for a standard
  ``ophyd.Device``. Signals are organized based on their ``Kind`` and
  description.
* **typhon.tools** : These are widgets that interface with external
  applications. While you may have other GUIs for these systems,
  ``typhon.tools`` are built especially to handle the handshaking between all
  the information stored on your device and the tool you are interfacing with.
  This saves your operator clicks and ensures consistency in use. 

All three of the widgets listed above share a similar API for creation.
Instantiating the object by itself handles loading the container widgets and
placing them in the correct place, but these do not accept ``ophyd.Device``
arguments. The reason for this is to ensure that we can use all of the
``typhon`` screens as templates, and regardless or not of whether you have an
``ophyd.Device`` you can always populate the screens by hand. If you do in fact
have an ``ophyd.Device`` every class has an ``add_device`` method and
alternatively and be constructed using the ``from_device`` classmethod.


.. autoclass:: typhon.utils.TyphonBase
   :members:


Interpreting a Device
=====================
Typhon interprets the internal structure of the ``ophyd.Device`` to create the
`PyDM` user interface, so the most intuitive way to configure the created
display is to include things in the device itself. This also has the advantage
of keeping your Python API and display in sync, making the transition from
using screens to using an IPython shell seamless.

Take for instance the built-in ``ophyd.EpicsMotor`` class, we can do a quick
survey of what the default ``read`` and ``configuration`` attributes are:

.. ipython:: python

    import ophyd

    ophyd.EpicsMotor._default_read_attrs

    ophyd.EpicsMotor._default_configuration_attrs


These ``read`` and ``configuration`` attributes can always be changed when the
device is instantiated.  However, this is only a small subset of the signals
that are associated with the class.

.. ipython:: python

   ophyd.EpicsMotor._sig_attrs

Now, at first glance it may not be obvious, but there is a lot of information
here! We have a Python abstraction capable of instantiating a number of useful
EPICS signals based on a given ``prefix``. We know which of these signals an
operator will want to control and which ones are purely meant to be read back.
We also have these signals grouped by their importance to operation, each with
a terse human legible description of what the PV represents.

Typhon takes advantage of this to generate a concise PyDM user display. The
:class:`.TyphonDeviceDisplay` uses the signal groups; ``read_attrs``,
``configuration_attrs`` and ``hints`` to generate plots and widgets based on
the type and class of EPICSSignals. In order to best select the widget types,
:class:`.TyphonDeviceDisplay` attempts to connect to all of the PVs listed. If this
is not possible, there are ways to manually configure which widget will be
used. Simply invoke your device and then create your ``PyDMApplication`` and
widget

.. code:: python
 
   from qtpy.QtWidgets import QApplication

   from typhon import TyphonSuite

   app = QApplication()

   dg1_m1 = EpicsMotor('MFX:DG1:MMS:01', name="DG1 M1")

   typhon_suite = TyphonSuite.from_device(dg1_m1)

   typhon_suite.show()

Typhon also watches for trees of devices, for instance, if we wanted to
represent a stack of three EPICS motors as a single object.

.. code:: python
   
   from ophyd import EpicsMotor, Device, Component as C

   class XYZStage(Device):

        # Define three separate motor axes 
        x = C(EpicsMotor, ":MMS:01", name= 'X Positioner')
        y = C(EpicsMotor, ":MMS:02", name= 'Y Positioner')
        z = C(EpicsMotor, ":MMS:03", name= 'Z Positioner')

        # Define basic read attributes
        _default_read_attrs = ['x.user_readback', 'y.user_readback',
                               'z.user_readback', 'x.user_setpoint',
                               'y.user_setpoint', 'z.user_setpoint']

        @property
        def hints(self):
            return ['x.readback', 'y.readback', 'z.readback']

Typhon will show the top level features of the class, but still allow the
operator to view lower level details as they see fit. This allows for the
representation of complex devices with nested structures in clean consistent
user displays. 

Using the StyleSheet
====================
While it is no means a requirement, Typhon ships with two stylesheets to
improve the look of the widgets. By default this isn't activated, but can be
configured with :func:`typhon.use_stylesheet`. The operator can elect whether to use
the "light" or "dark" stylesheets by using the optional ``dark`` keyword. This
method also handles setting the "Fusion" ``QStyle`` which helps make the
interface have an operating system independent look and feel.
