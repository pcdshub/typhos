import sys

# make sure typhos is in sys.modules
import typhos.ui

# link this module to typhon
sys.modules[__name__] = sys.modules['typhos.ui']