# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Configuration',
    ]


class Configuration:
    __name__ = 'offered.configuration'

    default_quote_number_sequence = fields.Function(fields.Many2One(
        'ir.sequence', 'Default quote number sequence',
        domain=[
                ('code', '=', 'quote'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]),
        'get_sequence', setter='set_sequence')

    def get_sequence(self, name):
        return self.get_field('offered.product', name[8:])

    @classmethod
    def set_sequence(cls, configurations, name, value):
        return cls.set_field('offered.product', name[8:], 'ir.sequence', value)
