print("Importing Typhos QtDesigner plugins...")
import pydm  # noqa
from typhos.designer import *  # noqa

print("Loaded Typhos QtDesigner plugins. Available PyDM data plugins:",
      ', '.join(pydm.data_plugins.plugin_modules))

if not pydm.config.DESIGNER_ONLINE:
    print()
    print("**WARNING**: PYDM_DESIGNER_ONLINE not set: no connections will be "
          "made from widgets to the underlying control system.")
    print()
