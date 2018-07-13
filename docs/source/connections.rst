=======================
Application Connections
=======================

Ophyd Signals
=============
Typhon takes advantage of the flexible data plugin system contained within
``PyDM`` and the abstraction of the "control layer" within ``Ophyd``. In the
:class:`.SignalPanel`, objects signals are queried for their type. If these are
determined to be coming from ``EPICS`` the data plugin configured within
``PyDM`` is used directly, any other kind of signal goes through the generic
:class:`.SignalPlugin`. This uses the subscription system contained within
``Ophyd`` to keep widgets values updated. One caveat is that ``PyDM`` requires
that channels are specified by a string identifier. In the case of
``ophyd.Signal`` objects we want to ensure that these are passed by reference
to avoid duplicating objects. This means the workflow for adding these has one
more additonal step where the ``Signal`` is registered with the ``PyDM``
plugin.

.. code:: python

   from typhon.plugins import register_signal

   # Create an Ophyd Signal
   my_signal = ophyd.Signal(name='this_signal')
   # Register this with the Plugin
   register_signal(my_signal)
   # This signal is now available for use with PyDM widgets
   PyDMWidget(channel='sig://this_signal')

Note that this is all done for you if you use the :class:`.SignalPanel`, but
maybe useful if you would like to use the :class:`.SignalPlugin` directly.

Inclusion of Metadata
---------------------
In many cases just knowing the value of a signal is not enough to accurately
display it. Extra pieces of information such as the units and precision of
information can provide a richer operator experience. ``Typhon`` counts on this
information being available in the output of ``describe`` method of the signal.
If you want your child ``ophyd.Signal`` class to convey this information make
sure that it is expressed properly in the output of ``describe``.

===================== ===============
Metadata              Description Key
===================== ===============
Precision             `"precision"`
Enumeration Strings   `"enum_strs"`
Engineering Units     `"units"`
===================== ===============
