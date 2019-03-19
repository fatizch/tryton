# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields
from trytond.modules.offered.extra_data import ExtraDataDefTable


__all__ = [
    'ExtraData',
    'QuestionnaireExtraDataRelation',
    ]


class ExtraData(metaclass=PoolMeta):
    __name__ = 'extra_data'

    @classmethod
    def __setup__(cls):
        super(ExtraData, cls).__setup__()
        cls.kind.selection.append(('questionnaire', 'Questionnaire'))


class QuestionnaireExtraDataRelation(ExtraDataDefTable, metaclass=PoolMeta):
    'Relation between Questionnaire and Extra Data'
    __name__ = 'questionnaire-extra_data'

    questionnaire = fields.Many2One('questionnaire', 'Questionnaire',
        ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
        ondelete='RESTRICT')
    order = fields.Integer('Order')
