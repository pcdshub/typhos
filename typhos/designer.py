from pydm.widgets.qtplugin_base import qtplugin_factory

from .alarm import (TyphosAlarmCircle, TyphosAlarmRectangle,
                    TyphosAlarmTriangle, TyphosAlarmEllipse,
                    TyphosAlarmPolygon)
from .display import (TyphosDeviceDisplay, TyphosDisplaySwitcher,
                      TyphosDisplayTitle)
from .func import TyphosMethodButton
from .panel import TyphosCompositeSignalPanel, TyphosSignalPanel
from .positioner import TyphosPositionerWidget
from .widgets_aux import TyphosRelatedSuiteButton

group_name = 'Typhos Widgets'
TyphosSignalPanelPlugin = qtplugin_factory(TyphosSignalPanel,
                                           group=group_name)
TyphosCompositeSignalPanelPlugin = qtplugin_factory(TyphosCompositeSignalPanel,
                                                    group=group_name)
TyphosDeviceDisplayPlugin = qtplugin_factory(TyphosDeviceDisplay,
                                             group=group_name)
TyphosMethodButtonPlugin = qtplugin_factory(TyphosMethodButton,
                                            group=group_name)
TyphosPositionerWidgetPlugin = qtplugin_factory(TyphosPositionerWidget,
                                                group=group_name)
TyphosDisplaySwitcherPlugin = qtplugin_factory(TyphosDisplaySwitcher,
                                               group=group_name)
TyphosDisplayTitlePlugin = qtplugin_factory(TyphosDisplayTitle,
                                            group=group_name)
TyphosAlarmCirclePlugin = qtplugin_factory(TyphosAlarmCircle,
                                           group=group_name)
TyphosAlarmRectanglePlugin = qtplugin_factory(TyphosAlarmRectangle,
                                              group=group_name)
TyphosAlarmTrianglePlugin = qtplugin_factory(TyphosAlarmTriangle,
                                             group=group_name)
TyphosAlarmEllipsePlugin = qtplugin_factory(TyphosAlarmEllipse,
                                            group=group_name)
TyphosAlarmPolygonPlugin = qtplugin_factory(TyphosAlarmPolygon,
                                            group=group_name)
TyphosRelatedSuiteButtonPlugin = qtplugin_factory(TyphosRelatedSuiteButton,
                                                  group=group_name)
