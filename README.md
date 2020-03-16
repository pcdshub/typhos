<img src="docs/source/_static/hydra.jpg" width="200" height="250" align="right"/>
  <h1>Typhos</h1>
  <h3>Automated User Interface Creation from Ophyd Devices</h3>
</p>

[![Build Status](https://travis-ci.org/pcdshub/typhos.svg?branch=master)](https://travis-ci.org/pcdshub/typhos)
[![codecov.io](https://codecov.io/github/pcdshub/typhos/coverage.svg?branch=master)](https://codecov.io/github/pcdshub/typhos?branch=master)

> **WARNING**: This package was renamed.
>
> The last version supporting the `typhon` package name and command-line tool
> was v0.7.0.  Please upgrade to `typhos` or pin to that version.

EPICS is a flexible and powerful controls system to access to experimental
information, however, the relation and meaning of process variables is often
obscure. Many of the user interfaces for EPICS information reflect this, as
walls of buttons and flashing lights bombard the user with little thought to
structure or cohesion.

Typhos addresses this by providing an automated way to generate screens based
on a provided hierarchy of devices and signals. Built using PyDM, a PyQt based
display manager developed at SLAC National Laboratory, Typhos utilizes a large
toolkit of widgets to display EPICS information. For each process variable, a
corresponding widget is created based on; the importance to the average
operator, the type of value the EPICS PV will return, and whether a user should
be allowed to write to the variable. These widgets are then placed in a
convenient tab-based system to only show the necessary information for basic
function, but still allow access to more advanced signals.

Instead of reinventing a new way to specify device structures, Typhos uses
`Ophyd`, a library to abstract EPICS information into consistently structured
Python objects. Originally built for scripting experimental procedures at
NSLSII, Ophyd represents devices as combinations of components which are
either signals or nested devices. Then, either at runtime or by using the
defaults of the representative Python class, these signals are sorted into
different categories based on their relevance to operators. Typhos uses this
information to craft user interfaces.

## Installation
Recommended installation on Linux:
```
conda install typhos -c conda-forge -c pcds-tag
```
All `-tag` channels have `-dev` counterparts for bleeding edge installations.
Both `requirements.txt` and optional `dev-requirements.txt` are kept up to date
as well for those who prefer installation via `pip`

If installed in this manner, in an environment that is not **root**, the
environment variables will be setup in such a way that the Typhos widgets will
immediately be available in the `QtDesigner`. Otherwise, see the
``typhos_env.sh`` script contained in the ``etc`` folder of this repository.

`happi` is an optional dependency but is recommended. This must be installed
manually if not using the CONDA recipe.

### Qt Installation
There have been some observed inconsistencies between installations of `Qt`
available on `pip`, `defaults` and `conda-forge`. It is recommended that if you
want to use the full `typhos` feature to install via `conda-forge`. We have
found this the most reliable, especially when it comes to using the
`QtDesigner`. It is worth noting that since this library uses `qtpy` as an
interface layer to the various options for Qt Python bindings, the bare
requirements will not install a specific one for you. The testing suite runs
using `PyQt5`.

## Getting Started
Creating your first ``typhos`` panel for an``ophyd.Device`` only takes two
lines:

```python
import sys
from ophyd.sim import motor
from qtpy.QtWidgets import QApplication
import typhos

# Create our application
app = QApplication.instance() or QApplication(sys.argv)
typhos.use_stylesheet()  # Optional
suite = typhos.TyphosSuite.from_device(motor)

# Launch
suite.show()
app.exec_()
```

## Available Widgets
Typhos has three major building blocks that combine into the final display seen
by the operator:

* ``TyphosSuite``: The overall view for a Typhos window. It allows the
operator to view all of the loaded components and tools

* ``TyphosDeviceDisplay``: This is the widget created for a standard
``ophyd.Device``. Signals are organized based on their
``Kind`` and description.

* ``typhos.tools``: These are widgets that interface with external
applications. While you may have other GUIs for these systems,
``typhos.tools`` are built especially to handle the handshaking between all the
information stored on your device and the tool you are interfacing with. This
saves your operator clicks and ensures consistency in use.

### Initialization Pattern
All three of the widgets listed above share a similar API for creation.
Instantiating the object by itself handles loading the container widgets and
placing them in the correct place, but these do not accept ``ophyd.Device``
arguments. The reason for this is to ensure that we can use all of the
``typhos`` screens as templates, and regardless or not of whether you have an
``ophyd.Device`` you can always populate the screens by hand. If you do in fact
have an ``ophyd.Device`` every class has an ``add_device`` method and
alternatively and be constructed using the ``from_device`` classmethod.

## Related Projects
[**PyDM**](https://github.com/slaclab/pydm) - PyQT Display Manager for EPICS information

[**Ophyd**](https://github.com/NSLS-II/ophyd) - Device abstraction for Experimental Control
