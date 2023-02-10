from ..app import get_qapp, launch_suite
from ..suite import TyphosSuite
from ..utils import use_stylesheet
from .device_classes import ExampleComboPositioner, ExamplePositioner


def main():
    """
    Mini example app to show how the positioner widget works.
    """
    get_qapp()
    devices = [
        ExamplePositioner(name='example_motor'),
        ExampleComboPositioner(name='example_combo'),
    ]
    suite = TyphosSuite.from_devices(devices)
    use_stylesheet()
    launch_suite(suite)


if __name__ == '__main__':
    main()
