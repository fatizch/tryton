# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import Unique
from trytond.modules.coog_core import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'LossDescription',
    'MedicalActDescription',
    'MedicalActFamily',
    ]


class LossDescription:

    __name__ = 'benefit.loss.description'

    @classmethod
    def __setup__(cls):
        super(LossDescription, cls).__setup__()
        cls.loss_kind.selection.append(('health', 'Health'))


class MedicalActDescription(model.CoogSQL, model.CoogView):
    'Medical Act Description'

    __name__ = 'benefit.act.description'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    family = fields.Many2One('benefit.act.family', 'Medical Act Family',
            ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(MedicalActDescription, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(t, t.code), 'The code must be unique'),
            ]

    def get_rec_name(self, name):
        return self.code


class MedicalActFamily(model.CoogSQL, model.CoogView):
    'Medical Act Family'

    __name__ = 'benefit.act.family'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)
    act_descriptions = fields.One2Many('benefit.act.description', 'family',
        'Medical Act Descriptions')

    @classmethod
    def __setup__(cls):
        super(MedicalActFamily, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(t, t.code), 'The code must be unique'),
            ]
