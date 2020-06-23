from textwrap import dedent

import caproto
from caproto.server import PVGroup, ioc_arg_parser, pvproperty, run

import ophyd
from ophyd import Component as Cpt
from ophyd import EpicsSignal
from pcdsdevices.variety import set_metadata


class MyDevice(ophyd.Device):
    command = Cpt(EpicsSignal, 'command')
    set_metadata(command, {'variety': 'command'})

    command_proc = Cpt(EpicsSignal, 'command-proc')
    set_metadata(command_proc, {'variety': 'command-proc'})

    command_enum = Cpt(EpicsSignal, 'command-enum')
    set_metadata(command_enum, {'variety': 'command-enum'})

    command_setpoint_tracks_readback = Cpt(EpicsSignal,
                                           'command-setpoint-tracks-readback')
    set_metadata(command_setpoint_tracks_readback,
                 {'variety': 'command-setpoint-tracks-readback'})

    tweakable = Cpt(EpicsSignal, 'tweakable')
    set_metadata(tweakable, {'variety': 'tweakable', 'delta': 0.5})

    array_timeseries = Cpt(EpicsSignal, 'array-timeseries')
    set_metadata(array_timeseries, {'variety': 'array-timeseries'})

    array_histogram = Cpt(EpicsSignal, 'array-histogram')
    set_metadata(array_histogram, {'variety': 'array-histogram'})

    array_image = Cpt(EpicsSignal, 'array-image')
    set_metadata(array_image, {'variety': 'array-image'})

    array_nd = Cpt(EpicsSignal, 'array-nd')
    set_metadata(array_nd, {'variety': 'array-nd'})

    scalar = Cpt(EpicsSignal, 'scalar')
    set_metadata(scalar, {'variety': 'scalar'})

    scalar_range = Cpt(EpicsSignal, 'scalar-range')
    set_metadata(scalar_range, {'variety': 'scalar-range'})

    bitmask = Cpt(EpicsSignal, 'bitmask')
    set_metadata(bitmask, {'variety': 'bitmask'})

    text = Cpt(EpicsSignal, 'text')
    set_metadata(text, {'variety': 'text'})

    text_multiline = Cpt(EpicsSignal, 'text-multiline')
    set_metadata(text_multiline, {'variety': 'text-multiline'})

    text_enum = Cpt(EpicsSignal, 'text-enum')
    set_metadata(text_enum, {'variety': 'text-enum'})

    enum = Cpt(EpicsSignal, 'enum')
    set_metadata(enum, {'variety': 'enum'})


class VarietyIOC(PVGroup):
    """
    """
    command = pvproperty(value=0, name='command')
    command_proc = pvproperty(value=0, name='command-proc')
    command_enum = pvproperty(value=0, name='command-enum')
    command_setpoint_tracks_readback = pvproperty(
        value=0, name='command-setpoint-tracks-readback')
    tweakable = pvproperty(value=0, name='tweakable')
    array_timeseries = pvproperty(value=[0.5] * 30, name='array-timeseries')
    array_histogram = pvproperty(value=[0.5] * 30, name='array-histogram')
    array_image = pvproperty(value=[200] * 1024, name='array-image')
    array_nd = pvproperty(value=[200] * 1024, name='array-nd')
    scalar = pvproperty(value=1.2, name='scalar')
    scalar_range = pvproperty(value=1.3, name='scalar-range')
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
