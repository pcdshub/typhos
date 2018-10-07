<img src="docs/source/_static/hydra.jpg" width="200" height="250" align="right"/>
  <h1>Typhon</h1>
  <h3>Automated User Interface Creation from Ophyd Devices</h3>
</p>

[![Build Status](https://travis-ci.org/pcdshub/typhon.svg?branch=master)](https://travis-ci.org/pcdshub/typhon)
[![codecov.io](https://codecov.io/github/pcdshub/typhon/coverage.svg?branch=master)](https://codecov.io/github/pcdshub/typhon?branch=master)

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

## Installation
Recommended installation:
```
conda install typhon -c pcds-tag -c conda-forge
```
All `-tag` channels have `-dev` counterparts for bleeding edge installations.
Both `requirements.txt` and optional `dev-requirements.txt` are kept up to date
as well for those who prefer installation via `pip`

## Getting Started
Creating your first ``typhon`` panel for an``ophyd.Device`` only takes two
lines:

```python

from typhon import TyphonSuite

suite = TyphonSuite.from_device(my_device)
```

## Available Widgets
Typhon has three major building blocks that combine into the final display seen
by the operator:

* ``TyphonSuite``: The overall view for a Typhon window. It allows the
operator to view all of the loaded components and tools

* ``TyphonDisplay``: This is the widget created for a standard
``ophyd.Device``. Signals are organized based on their
``Kind`` and description.

* ``typhon.tools``: These are widgets that interface with external
applications. While you may have other GUIs for these systems,
``typhon.tools`` are built especially to handle the handshaking between all the
information stored on your device and the tool you are interfacing with. This
saves your operator clicks and ensures consistency in use. 

### Initialization Pattern
All three of the widgets listed above share a similar API for creation.
Instantiating the object by itself handles loading the container widgets and
placing them in the correct place, but these do not accept ``ophyd.Device``
arguments. The reason for this is to ensure that we can use all of the
``typhon`` screens as templates, and regardless or not of whether you have an
``ophyd.Device`` you can always populate the screens by hand. If you do in fact
have an ``ophyd.Device`` every class has an ``add_device`` method and
alternatively and be constructed using the ``from_device`` classmethod.
 
## Related Projects
[**PyDM**](https://github.com/slaclab/pydm) - PyQT Display Manager for EPICS information

[**Ophyd**](https://github.com/NSLS-II/ophyd) - Device abstraction for Experimental Control
