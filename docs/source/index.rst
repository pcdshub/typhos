======
Typhon
======

EPICS is a flexible and powerful controls system to access to experimental
information, however, the relation and meaning of process variables is often
obscure. Many of the user interfaces for EPICS information reflect this, as
walls of buttons and flashing lights bombard the user with little thought to
structure or cohesion. 

Typhon addresses this by providing an automated way to generate screens based
on a provided hierarchy of devices and signals. Built using PyDM, a PyQt based
display manager developed at SLAC National Laboratory, Typhon utilizes a large
toolkit of widgets to display EPICS information. For each process variable, a
corresponding widget is created based on; the importance to the average
operator, the type of value the EPICS PV will return, and whether a user should
be allowed to write to the variable. These widgets are then placed in a
convenient tab-based system to only show the necessary information for basic
function, but still allow access to more advanced signals.

Instead of reinventing a new way to specify device structures, Typhon uses
`Ophyd`, a library to abstract EPICS information into consistently structured
Python objects. Originally built for scripting experimental procedures at
NSLSII, Ophyd represents devices as combinations of components which are
either signals or nested devices. Then, either at runtime or by using the
defaults of the representative Python class, these signals are sorted into
different categories based on their relevance to operators. Typhon uses this
information to craft user interfaces.

Related Projects
----------------
- `pydm <https://github.com/slaclab/pydm/>`_
- `ophyd <https://github.com/NSLS-II/ophyd/>`_

.. toctree::
   :maxdepth: 1
   :caption: Tutorial
   :hidden:

   basic_usage.rst
   python_methods.rst

.. toctree::
   :maxdepth: 1
   :caption: API Documentation
   :hidden:

   display.rst
   widgets.rst
   plugins.rst
