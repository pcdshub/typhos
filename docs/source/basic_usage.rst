============
How it Works
============
Typhos has three major building blocks that combine into the final display seen
by the operator:

* **TyphosSuite** : The overall view for a Typhos window. It allows the
  operator to view all of the loaded components and tools.
* **TyphosDeviceDisplay** : This is the widget created for a standard
  ``ophyd.Device``. Signals can be organized based on their ``Kind`` and
  description.
* **typhos.tools** : These are widgets that interface with external
  applications. While you may have other GUIs for these systems,
  ``typhos.tools`` are built especially to handle the handshaking between all
  the information stored on your device and the tool you are interfacing with.
  This saves your operator clicks and ensures consistency in use.

All three of the widgets listed above share a similar API for creation.
Instantiating the object by itself handles loading the container widgets and
placing them in the correct place, but these do not accept ``ophyd.Device``
arguments. The reason for this is to ensure that we can use all of the
``typhos`` screens as templates, and regardless or not of whether you have an
``ophyd.Device`` you can always populate the screens by hand. If you do in fact
have an ``ophyd.Device`` every class has an ``add_device`` method and
alternatively and be constructed using the ``from_device`` classmethod.


.. autoclass:: typhos.utils.TyphosBase
    :members:
    :noindex:


Interpreting a Device
=====================
Typhos interprets the internal structure of the ``ophyd.Device`` to create the
`PyDM` user interface, so the most intuitive way to configure the created
display is to include components on the device itself. This also has the advantage
of keeping your Python API and display in sync, making the transition from
using screens to using an IPython shell seamless.

For the following applications we'll use the ``motor`` simulation contained
within ``ophyd`` itself. We also need to create a ``QApplication`` before we
create any widgets:

.. ipython:: python

   from qtpy.QtWidgets import QApplication
   app = QApplication([])


.. ipython:: python
    :suppress:

    from ophyd.sim import motor



Using Happi
^^^^^^^^^^^
While ``happi`` is not a requirement for using ``typhos``, it is recommended.
For more information, visit the `GitHub <https://github.com/pcdshub/happi/>`_
repository. The main purpose of the package is to store information on our
Ophyd objects so that we can load them in a variety of contexts. If you do not
use ``happi`` you will need to create your objects and displays in the same
process.

Here is a quick example if you wanted to get a feel for what ``typhos`` looks
like with `happi``:

.. code:: python

    import happi
    from typhos.plugins import register_client

    # Initialize a new JSON based client
    client = happi.Client(path='db.json', initialize=True)
    # Register this with typhos
    register_client(client)
    # Add a device to our new database
    device = happi.Device(device_class='ophyd.sim.SynAxis',
                          prefix='Tst:Mtr', args=[], kwargs='{{name}}',
                          name='my_motor', beamline='TST')
    client.add_device(device)

In practice, it is not necessary to call :func:`.register_client` if you have
configured the ``$HAPPI_CFG`` environment variable such that
``happi.Client.from_config`` yields the desired client.

We can now check that we can load the complete ``SynAxis`` object.

.. code:: python

    motor = client.load_device(name='my_motor')

Display Signals
^^^^^^^^^^^^^^^
The first thing we'll talk about is showing a group of signals associated with
our ``motor`` object in a basic form called a
:class:`~typhos.TyphosSignalPanel`.  Simply inspecting the device reveals a few
signals for us to display

.. ipython:: python

    motor.component_names

It is crucial that we understand the importance of these signals to the
operator. In order to glean this information from the object the ``kind``
attributes are inspected. For more information see the `ophyd documentation
<https://nsls-ii.github.io/ophyd/signals.html#kind/>`_. A quick inspection of
the various attributes allows us to see how our signals are organized.

.. ipython:: python

    # Most important signal(s)
    motor.hints
    # Important signals, all hints will be found here as well
    motor.read()
    # Configuration information
    motor.read_configuration()

The :class:`.TyphosSignalPanel` will render these, allowing us to select a
subset of the signals to display based on their kind. Below both the
``QtDesigner`` using ``happi`` and the corresponding ``Python`` code is shown
as well:

.. ipython:: python

   from typhos import TyphosSignalPanel
   panel = TyphosSignalPanel.from_device(motor)

.. figure:: /_static/kind_panel.gif
   :scale: 100%
   :align: center

Now, at first glance it may not be obvious, but there is a lot of information
here! We know which of these signals an operator will want to control and which
ones are purely meant to be read back. We also have these signals grouped by
their importance to operation, each with a terse human-readable description of
what the ``Signal`` represents.

Filling Templates
^^^^^^^^^^^^^^^^^
Taking this concept further, instead of filling a single panel
:class:`.TyphosDeviceDisplay` allows a template to be created with a multitude
of widgets and panels. ``Typhos`` will find widgets that accept devices, but do
not have any devices already. Typhos comes with some default templates, and you
can cycle between them by changing the ``display_type``

Once again, both the ``Python`` code and the ``QtDesigner`` use cases are
shown:

.. ipython:: python

    from typhos import TyphosDeviceDisplay
    display = TyphosDeviceDisplay.from_device(motor)


.. figure:: /_static/device_display.gif
   :scale: 100%
   :align: center


The TyphosSuite
===============
A complete application can be made by loading the :class:`.TyphosSuite`. Below
is the complete code from start to finish required to create the suite. Look at
the ``TyphosSuited.default_tools`` to control which ``typhos.tools`` are
loaded.

.. code:: python

    from ophyd.sim import motor
    from qtpy.QtWidgets import QApplication
    import typhos

    # Create our application
    app = QApplication([])
    typhos.use_stylesheet()  # Optional
    suite = typhos.TyphosSuite.from_device(motor)

    # Launch
    suite.show()
    app.exec_()


Using the StyleSheet
====================
While it is no means a requirement, Typhos ships with two stylesheets to
improve the look of the widgets. By default this isn't activated, but can be
configured with :func:`typhos.use_stylesheet`. The operator can elect whether
to use the "light" or "dark" stylesheets by using the optional ``dark``
keyword. This method also handles setting the "Fusion" ``QStyle`` which helps
make the interface have an operating system independent look and feel.


Using the Documentation Widget
==============================

Typhos has a built-in documentation helper, which allows for the in-line
linking and display of a user-provided website.

To inform Typhos how to load documentation specific to your facility, please
customize the following environment variables.

1. ``TYPHOS_HELP_URL`` (str): The help URL format string.  The help URL will
   be formatted with the ophyd device pertinent to the display, such that you
   may access its name, PV prefix, happi metadata (if available), and so on.
   For example, if a Confluence server exists at
   ``https://my-confluence-site.example.com/Controls/`` with document names
   that match your devices, ``TYPHOS_HELP_URL`` should be set to
   ``https://my-confluence-site.example.com/Controls/{device.name}``.
   If, perhaps, only top-level devices are guaranteed to have documentation,
   consider using: ``device.root.name`` instead in the format string.
2. ``TYPHOS_HELP_HEADERS`` (json): headers to pass to HELP_URL.  This should be
   in a JSON format, such as ``{"my_key":"my_value"}``.
3. ``TYPHOS_HELP_TOKEN`` (str): An optional token for the bearer authentication
   scheme - e.g., personal access tokens with Confluence.  This is a shortcut
   to add a header ``"Authorization"`` with the value
   ``"Bearer ${TYPHOS_HELP_TOKEN}"``.
