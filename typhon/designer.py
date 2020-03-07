from pydm.widgets.qtplugin_base import qtplugin_factory

from .display import TyphonDeviceDisplay
from .func import TyphonMethodButton
from .positioner import TyphonPositionerWidget
from .signal import TyphonSignalPanel

group_name = 'Typhon Widgets - Deprecated'
TyphonSignalPanelPlugin = qtplugin_factory(TyphonSignalPanel,
                                           group=group_name)
TyphonDeviceDisplayPlugin = qtplugin_factory(TyphonDeviceDisplay,
                                             group=group_name)
TyphonMethodButtonPlugin = qtplugin_factory(TyphonMethodButton,
                                            group=group_name)
TyphonPositionerWidgetPlugin = qtplugin_factory(TyphonPositionerWidget,
                                                group=group_name)
