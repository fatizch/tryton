# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pyson import Eval
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Benefit',
    ]


SEQUENCE_SELECTION = [
    ('strict', 'Strict'),
    ('normal', 'Normal'),
    ('', ''),
    ]

SEQUENCE_REFERENCE = [
    ('ir.sequence', 'Sequence'),
    ('ir.sequence.strict', 'Sequence Strict'),
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    define_sequence = fields.Selection(SEQUENCE_SELECTION, 'Defined Sequence',
        states={
            }, depends=['sequence'])
    normal_sequence = fields.Many2One('ir.sequence', 'Normal Sequence',
        states={
            'invisible': Eval('define_sequence') != 'normal',
            }, domain=[('code', '=', 'claim.service')],
        depends=['define_sequence'], ondelete='RESTRICT')
    strict_sequence = fields.Many2One('ir.sequence.strict', 'Strict Sequence',
        states={
            'invisible': Eval('define_sequence') != 'strict',
            }, domain=[('code', '=', 'claim.service')],
        depends=['define_sequence'], ondelete='RESTRICT')
    sequence = fields.Function(fields.Reference('Sequence',
        SEQUENCE_REFERENCE, states={
            'invisible': Eval('define_sequence') == ''
            }, depends=['define_sequence'],
            ), 'get_sequence', loader='load_sequence')

    def load_sequence(self, name=None):
        return self.normal_sequence or self.strict_sequence

    def get_sequence(self, name=None):
        value = self.load_sequence(name)
        return str(value) if value else None

    @fields.depends('define_sequence')
    def on_change_define_sequence(self):
        if not self.define_sequence:
            self.normal_sequence = None
            self.strict_sequence = None
        else:
            if self.define_sequence == 'normal':
                self.strict_sequence = None
            else:
                self.normal_sequence = None
