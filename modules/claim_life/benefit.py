# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool, Or, In, If

from trytond.modules.coog_core import fields, model

__all__ = [
    'Benefit',
    'BenefitBeneficiaryDocument',
    'LossDescription',
    'BeneficiaryExtraDataRelation',
    'ExtraData',
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
    beneficiary_extra_data_def = fields.Many2Many('beneficiary-extra_data',
        'benefit', 'extra_data_def', 'Beneficiary Extra Data',
        help='List of extra data displayed when defining a beneficiary in '
        'claim treatment',
        states={'invisible': Eval('beneficiary_kind') != 'manual_list'},
        domain=[('kind', '=', 'beneficiary')],
        depends=['beneficiary_kind'])
    ignore_shares = fields.Boolean('Ignore Shares',
        help='If checked, the shares will be ignored when closing the claim')
    manual_share_management = fields.Boolean('Manual Share Management',
        help='If set, the beneficiary share treatment has to be '
        'handle manually in the capital computation rule',
        states={'invisible': Or(Eval('beneficiary_kind') != 'manual_list',
                Bool(Eval('ignore_shares')))},
        depends=['beneficiary_kind', 'ignore_shares'])

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

    @fields.depends('beneficiary_extra_data_def', 'beneficiary_kind')
    def on_change_with_beneficiary_extra_data_def(self):
        if self.beneficiary_kind != 'manual_list':
            return []
        return [x.id for x in self.beneficiary_extra_data_def]

    def get_beneficiary_extra_data_def(self, beneficiary):
        ExtraData = Pool().get('extra_data')
        existing_data = beneficiary.extra_data_values
        condition_date = beneficiary.service.loss.get_date()
        all_schemas, possible_schemas = ExtraData.get_extra_data_definitions(
            self, 'beneficiary_extra_data_def', 'beneficiary', condition_date)
        return ExtraData.calculate_value_set(possible_schemas, all_schemas,
            existing_data)


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
        cls.with_end_date.domain.append(
            If(In(Eval('loss_kind', ''), ['std', 'ltd']),
                [('with_end_date', '=', True)],
                If(Eval('loss_kind') == 'death',
                    [('with_end_date', '=', False)],
                    [])))
        cls.with_end_date.depends.append('loss_kind')


class BeneficiaryExtraDataRelation(model.CoogSQL):
    'Beneficiary to Extra Datas Relation'

    __name__ = 'beneficiary-extra_data'

    benefit = fields.Many2One('benefit', 'Benefit', ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
        ondelete='RESTRICT')


class ExtraData:
    __metaclass__ = PoolMeta
    __name__ = 'extra_data'

    @classmethod
    def __setup__(cls):
        super(ExtraData, cls).__setup__()
        cls.kind.selection.append(('beneficiary', 'Beneficiary'))
