from trytond.pool import Pool
from .offered import *


def register():
    Pool.register(
        # From offered
        OptionDescription,
        module='offered_property_casualty', type_='model')
