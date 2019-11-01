import logging

from pydm.widgets.qtplugin_base import qtplugin_factory

from .signal import TyphonSignalPanel
from .display import TyphonDeviceDisplay
from .func import TyphonMethodButton
from .positioner import TyphonPositionerWidget

logger = logging.getLogger(__name__)
logger.info("Loading Typhon QtDesigner plugins ...")

group_name = 'Typhon Widgets'
TyphonSignalPanelPlugin = qtplugin_factory(TyphonSignalPanel,
                                           group=group_name)
TyphonDeviceDisplayPlugin = qtplugin_factory(TyphonDeviceDisplay,
                                             group=group_name)
TyphonMethodButtonPlugin = qtplugin_factory(TyphonMethodButton,
                                            group=group_name)
TyphonPositionerWidgetPlugin = qtplugin_factory(TyphonPositionerWidget,
                                                group=group_name)
