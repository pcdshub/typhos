import logging

from pydm.widgets.qtplugin_base import qtplugin_factory

from .signal import TyphonSignalPanel
from .display import TyphonDeviceDisplay
from .func import TyphonMethodButton
from .positioner import TyphonPositionerWidget

logger = logging.getLogger(__name__)

logging.info("Loading Typhon QtDesigner plugins ...")
TyphonSignalPanelPlugin = qtplugin_factory(TyphonSignalPanel)
TyphonDeviceDisplayPlugin = qtplugin_factory(TyphonDeviceDisplay)
TyphonMethodButtonPlugin = qtplugin_factory(TyphonMethodButton)
TyphonPositionerWidgetPlugin = qtplugin_factory(TyphonPositionerWidget)
