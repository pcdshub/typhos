from textwrap import dedent

import caproto
import ophyd
import pytest
from caproto.server import PVGroup, ioc_arg_parser, pvproperty, run
from ophyd import Component as Cpt
from ophyd import EpicsSignal

pytest.importorskip('pcdsdevices')

from pcdsdevices.variety import set_metadata  # noqa: E402


class Variants(ophyd.Device):
    soft_delta = Cpt(ophyd.Signal, value=1)

    tweakable_delta_source_by_name = Cpt(EpicsSignal, 'tweakable')
    set_metadata(
        tweakable_delta_source_by_name,
        {'variety': 'scalar-tweakable',
         'delta.signal': 'soft_delta',
         'delta.source': 'signal',
         'range.source': 'value',
         'range.value': [-10, 10],
         }
    )

    tweakable_delta_source_by_component = Cpt(EpicsSignal, 'tweakable')
    set_metadata(
        tweakable_delta_source_by_component,
        {'variety': 'scalar-tweakable',
         'delta.signal': soft_delta,
         'delta.source': 'signal',
         'range.source': 'value',
         'range.value': [-10, 10],
         }
    )

    array_tabular = Cpt(EpicsSignal, 'array-tabular')
    set_metadata(
        array_tabular,
        {'variety': 'array-tabular',
         'shape': (3, 3),
         }
    )


class MyDevice(ophyd.Device):
    command = Cpt(EpicsSignal, 'command-with-enum')
    set_metadata(command,
                 {'variety': 'command',
                  'tags': {'confirm', 'protected'},
                  'value': 1,
                  }
                 )

    command_proc = Cpt(EpicsSignal, 'command-without-enum')
    set_metadata(command_proc, {'variety': 'command-proc'})

    command_enum = Cpt(EpicsSignal, 'command-without-enum')
    set_metadata(command_enum,
                 {'variety': 'command-enum',
                  'enum_dict': {0: 'No', 1: 'Yes', 3: 'Metadata-defined'},
                  }
                 )

    command_setpoint_tracks_readback = Cpt(EpicsSignal,
                                           'command-setpoint-tracks-readback')
    set_metadata(command_setpoint_tracks_readback,
                 {'variety': 'command-setpoint-tracks-readback'})

    tweakable = Cpt(EpicsSignal, 'tweakable')
    set_metadata(
        tweakable,
        {'variety': 'scalar-tweakable',
         'delta.value': 0.5,
         'delta.range': [-1, 1],
         'range.source': 'value',
         'range.value': [-1, 1],
         }
    )

    array_timeseries = Cpt(EpicsSignal, 'array-timeseries')
    set_metadata(array_timeseries, {'variety': 'array-timeseries'})

    array_histogram = Cpt(EpicsSignal, 'array-histogram')
    set_metadata(array_histogram, {'variety': 'array-histogram'})

    array_image = Cpt(EpicsSignal, 'array-image')
    set_metadata(
        array_image,
        {'variety': 'array-image',
         'shape': (32, 32)
         }
    )

    array_nd = Cpt(EpicsSignal, 'array-nd')
    set_metadata(
        array_nd,
        {'variety': 'array-nd',
         'shape': (16, 16, 4)
         }
    )

    scalar = Cpt(EpicsSignal, 'scalar')
    set_metadata(scalar, {'variety': 'scalar'})

    scalar_range = Cpt(EpicsSignal, 'scalar-range')
    set_metadata(scalar_range, {'variety': 'scalar-range'})

    bitmask = Cpt(EpicsSignal, 'bitmask')
    set_metadata(bitmask, {'variety': 'bitmask',
                           'bits': 4,
                           'style': dict(shape='circle',
                                         on_color='yellow',
                                         off_color='white'),
                           'meaning': ['A', 'B', 'C'],
                           })

    text = Cpt(EpicsSignal, 'text', string=True)
    set_metadata(text, {'variety': 'text'})

    text_multiline = Cpt(EpicsSignal, 'text-multiline', string=True)
    set_metadata(text_multiline, {'variety': 'text-multiline'})

    text_enum = Cpt(EpicsSignal, 'text-enum', string=True)
    set_metadata(text_enum, {'variety': 'text-enum'})

    enum = Cpt(EpicsSignal, 'enum')
    set_metadata(enum, {'variety': 'enum'})

    variants = Cpt(Variants, '')


class VarietyIOC(PVGroup):
    """
    """
    command_without_enum = pvproperty(value=0, name='command-without-enum')
    command_with_enum = pvproperty(value=0, name='command-with-enum',
                                   enum_strings=['Off', 'On'],
                                   dtype=caproto.ChannelType.ENUM)

    command_setpoint_tracks_readback = pvproperty(
        value=0, name='command-setpoint-tracks-readback')
    tweakable = pvproperty(value=0, name='tweakable',
                           lower_ctrl_limit=-5,
                           upper_ctrl_limit=5,
                           )
    array_tabular = pvproperty(value=[1.5] * (3 * 3), name='array-tabular')
    array_timeseries = pvproperty(value=[0.5] * 30, name='array-timeseries')
    array_histogram = pvproperty(value=[0.5] * 30, name='array-histogram')
    array_image = pvproperty(value=[200] * 1024, name='array-image')
    array_nd = pvproperty(value=[200] * 1024, name='array-nd')
    scalar = pvproperty(value=1.2, name='scalar')
    scalar_range = pvproperty(value=1.3, name='scalar-range',
                              lower_ctrl_limit=-3.14,
                              upper_ctrl_limit=3.14,
                              precision=3,
                              )
    bitmask = pvproperty(value=0, name='bitmask')
    text = pvproperty(value='the text', name='text')
    text_multiline = pvproperty(value='multiline\ntext', name='text-multiline')
    text_enum = pvproperty(value='enum value 0', name='text-enum')
    enum = pvproperty(
        value='enum1', enum_strings=['enum1', 'enum2'],
        dtype=caproto.ChannelType.ENUM, name='enum')


if __name__ == '__main__':
    ioc_options, run_options = ioc_arg_parser(
        default_prefix='variety:',
        desc=dedent(VarietyIOC.__doc__))
    ioc = VarietyIOC(**ioc_options)
    run(ioc.pvdb, **run_options)
