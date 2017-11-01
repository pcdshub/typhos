"""
Utility functions for typhon
"""
############
# Standard #
############

############
# External #
############

#############
#  Package  #
#############

def channel_name(pv):
    """
    Create a valid PyDM channel from a PV name
    """
    return 'ca://' + pv.pvname
