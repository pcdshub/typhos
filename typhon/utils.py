"""
Utility functions for typhon
"""
############
# Standard #
############
import os.path

############
# External #
############

#############
#  Package  #
#############

ui_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'ui')

def channel_name(pv):
    """
    Create a valid PyDM channel from a PV name
    """
    return 'ca://' + pv.pvname

def clean_attr(attr):
    """
    Create a nicer, human readable alias from a Python attribute name
    """
    return ' '.join([word[0].upper() + word[1:] for word in attr.split('_')])
