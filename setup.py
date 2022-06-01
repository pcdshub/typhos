from setuptools import find_packages, setup

import versioneer

with open('requirements.txt') as f:
    requirements = f.read().split()

git_requirements = [r for r in requirements if r.startswith('git+')]
requirements = [r for r in requirements if not r.startswith('git+')]
if len(git_requirements) > 0:
    print("User must install the following packages manually:\n" +
          "\n".join(f' {r}' for r in git_requirements))

# Widgets for Qt Designer via the pydm entrypoint
designer_widgets = [
    "TyphosAlarmCirclePlugin=typhos.alarm:TyphosAlarmCircle",
    "TyphosAlarmEllipsePlugin=typhos.alarm:TyphosAlarmEllipse",
    "TyphosAlarmPolygonPlugin=typhos.alarm:TyphosAlarmPolygon",
    "TyphosAlarmRectanglePlugin=typhos.alarm:TyphosAlarmRectangle",
    "TyphosAlarmTrianglePlugin=typhos.alarm:TyphosAlarmTriangle",
    "TyphosCompositeSignalPanelPlugin=typhos.panel:TyphosCompositeSignalPanel",
    "TyphosDeviceDisplayPlugin=typhos.display:TyphosDeviceDisplay",
    "TyphosDisplaySwitcherPlugin=typhos.display:TyphosDisplaySwitcher",
    "TyphosDisplayTitlePlugin=typhos.display:TyphosDisplayTitle",
    "TyphosHelpFramePlugin=typhos.display:TyphosHelpFrame",
    "TyphosMethodButtonPlugin=typhos.func:TyphosMethodButton",
    "TyphosPositionerWidgetPlugin=typhos.positioner:TyphosPositionerWidget",
    "TyphosRelatedSuiteButtonPlugin=typhos.related_display:TyphosRelatedSuiteButton",  # noqa
    "TyphosSignalPanelPlugin=typhos.panel:TyphosSignalPanel",
]

setup(
    name="typhos",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    author="SLAC National Accelerator Laboratory",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    description="Interface generation for ophyd devices",
    entry_points={
        "console_scripts": ["typhos=typhos.cli:main"],
        "pydm.widget": designer_widgets,
        "pydm.data_plugin": [
            "HappiPlugin=typhos.plugins:HappiPlugin",
            "SignalPlugin=typhos.plugins:SignalPlugin",
        ],
    },
)
