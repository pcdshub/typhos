import logging

from pydm.widgets.qtplugin_base import qtplugin_factory

from .signal import TyphonSignalPanel, TyphosSignalPanel
from .display import TyphonDeviceDisplay, TyphosDeviceDisplay
from .func import TyphonMethodButton, TyphosMethodButton
from .positioner import TyphonPositionerWidget, TyphosPositionerWidget

logger = logging.getLogger(__name__)
logger.info("Loading Typhos QtDesigner plugins ...")

group_name = 'Typhon Widgets - Deprecated'
TyphonSignalPanelPlugin = qtplugin_factory(TyphonSignalPanel,
                                           group=group_name)
TyphonDeviceDisplayPlugin = qtplugin_factory(TyphonDeviceDisplay,
                                             group=group_name)
TyphonMethodButtonPlugin = qtplugin_factory(TyphonMethodButton,
                                            group=group_name)
TyphonPositionerWidgetPlugin = qtplugin_factory(TyphonPositionerWidget,
                                                group=group_name)

group_name = 'Typhos Widgets'
TyphosSignalPanelPlugin = qtplugin_factory(TyphosSignalPanel,
                                           group=group_name)
TyphosDeviceDisplayPlugin = qtplugin_factory(TyphosDeviceDisplay,
                                             group=group_name)
TyphosMethodButtonPlugin = qtplugin_factory(TyphosMethodButton,
                                            group=group_name)
TyphosPositionerWidgetPlugin = qtplugin_factory(TyphosPositionerWidget,
                                                group=group_name)
