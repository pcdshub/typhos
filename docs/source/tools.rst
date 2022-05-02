###############
Supported Tools
###############

In experimental environments there are a variety of external tools and
applications that are critical to day to day operation. Typhos hopes to
integrate many of these services into the :class:`.TyphosDeviceDisplay` for
ease of operation. This approach has two advantages; the first is that getting
to helpful tools requires fewer clicks and therefore less time, secondly, if we
assume that the context in which they want to use the external tool includes
this device, we can pre-populate many of the fields for them.

All of the tools in ``typhos`` follow a basic pattern. Each one can be
instantiated as a standalone widget with no ``ophyd`` or ``Device`` required. The
intention is that these tools could be used in a separate application where the
underlying information is in a different form. However, in order to make these
objects easier to interface with ``ophyd`` objects the methods
:meth:`.TyphosTool.from_device` and :meth:`.TyphosTool.add_device` are
available. These automatically populate fields according to device structures.

Tool Classes
============

.. currentmodule:: typhos.tools

.. autosummary::
   :toctree: generated

   TyphosConsole
   TyphosLogDisplay
   TyphosTimePlot
