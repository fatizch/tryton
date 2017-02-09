# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSingleton, ModelSQL, ModelView


__all__ = [
    'ProcessConfiguration',
    ]


class ProcessConfiguration(ModelSingleton, ModelSQL, ModelView):
    'Process Configuration'

    __name__ = 'process.configuration'
