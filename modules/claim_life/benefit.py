# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model

__all__ = [
    'Benefit',
    'BenefitBeneficiaryDocument',
    'LossDescription',
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    beneficiary_documents = fields.Many2Many('benefit-beneficiary_document',
        'benefit', 'document', 'Beneficiary Documents',
        help='The list of documents that will be required from each '
        'beneficiary before indemnification can occur',
        states={'invisible': Eval('beneficiary_kind') != 'manual_list'},
        depends=['beneficiary_kind'])

    @classmethod
    def __setup__(cls):
        super(Benefit, cls).__setup__()
        cls._error_messages.update({
                'covered_party_enum': 'Covered Party',
                'manual_list_enum': 'Manual List',
                })

    @classmethod
    def get_beneficiary_kind(cls):
        res = super(Benefit, cls).get_beneficiary_kind()
        res.append(['covered_party', cls.raise_user_error(
                    'covered_party_enum', raise_exception=False)])
        res.append(['manual_list', cls.raise_user_error(
                    'manual_list_enum', raise_exception=False)])
        return res

    @fields.depends('beneficiary_documents', 'beneficiary_kind')
    def on_change_with_beneficiary_documents(self):
        if self.beneficiary_kind != 'manual_list':
            return []
        return [x.id for x in self.beneficiary_documents]


class BenefitBeneficiaryDocument(model.CoogSQL):
    'Benefit - Beneficiary Document'
    __name__ = 'benefit-beneficiary_document'

    benefit = fields.Many2One('benefit', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    document = fields.Many2One('document.description', 'Benefit',
        required=True, ondelete='RESTRICT', select=True)


class LossDescription:
    __metaclass__ = PoolMeta
    __name__ = 'benefit.loss.description'

    @classmethod
    def __setup__(cls):
        super(LossDescription, cls).__setup__()
        cls.item_kind.selection.append(('person', 'Person'))
        cls.loss_kind.selection.append(('std', 'Short Term'))
        cls.loss_kind.selection.append(('ltd', 'Long term'))
        cls.loss_kind.selection.append(('death', 'Death'))
