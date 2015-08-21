# -*- coding:utf-8 -*-
from trytond.pool import PoolMeta
from trytond.model import Unique
from trytond.modules.cog_utils import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'LossDescription',
    'MedicalActDescription',
    ]


class LossDescription:

    __name__ = 'benefit.loss.description'

    @classmethod
    def __setup__(cls):
        super(LossDescription, cls).__setup__()
        cls.loss_kind.selection.append(('health', 'Health'))


class MedicalActDescription(model.CoopSQL, model.CoopView):
    'Medical Act Description'

    __name__ = 'benefit.act.description'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)

    @classmethod
    def __setup__(cls):
        super(MedicalActDescription, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(t, t.code), 'The code must be unique'),
            ]
