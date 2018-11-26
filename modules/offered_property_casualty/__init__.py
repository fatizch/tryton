# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import offered


def register():
    Pool.register(
        offered.OptionDescription,
        module='offered_property_casualty', type_='model')
