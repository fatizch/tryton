# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .migrator import Migrator
import create_staging

__all__ = [
    'Migrator'
    ]


def register():
    Pool.register(
        create_staging.CreateStaging,
        module='migrator', type_='model')
