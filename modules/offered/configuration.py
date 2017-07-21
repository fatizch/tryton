# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton
__all__ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Offered Configuration'
    __name__ = 'offered.configuration'
