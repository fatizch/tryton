# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval, Bool
from trytond.pool import PoolMeta
from trytond import backend
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (CompanyMultiValueMixin,
    CompanyValueMixin)

from trytond.modules.coog_core import fields, model
from trytond.modules.rule_engine import get_rule_mixin
from trytond.modules.rule_engine.rule_engine import RuleEngineResult

__all__ = [
    'Product',
    'ProductQuoteNumberSequence',
    'ContractDataRule'
    ]


class Product(CompanyMultiValueMixin):
    __name__ = 'offered.product'
    __metaclass__ = PoolMeta

    quote_number_sequence = fields.MultiValue(fields.Many2One('ir.sequence',
            'Quote number sequence', domain=[
                ('code', '=', 'quote'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'required': Bool(Eval('context', {}).get('company')),
                'invisible': ~Eval('context', {}).get('company'),
                }))
    contract_data_rule = fields.One2Many(
        'contract.data.rule', 'product',
        'Contract Data Rule', delete_missing=True, size=1)

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls._error_messages.update({
                'data_rule_misconfigured': 'The field %(field)s on contracts '
                'cannot be set by a data rule. Please fix the contract data '
                'rule on product %(product)s',
                })

    @classmethod
    def _export_light(cls):
        return (super(Product, cls)._export_light() |
            set(['quote_number_sequence']))

    def update_contract_from_rule(self, contract, no_rule_errors,
            **kwargs):
        rule = self.contract_data_rule[0]
        exec_context = {}
        try:
            contract.init_dict_for_rule_engine(exec_context)
            res = rule.calculate_rule(exec_context, **kwargs)
        except Exception as e:
            if no_rule_errors:
                return {}
            else:
                raise e
        if isinstance(res, RuleEngineResult):
            result = res.result
        else:
            result = res
        auth_fields = rule._get_authorized_fields()
        for k, v in result.items():
            if k not in auth_fields:
                self.raise_user_error('data_rule_misconfigured',
                    {'field': k, 'product': self.name})
            setattr(contract, k, v)
        return res


class ProductQuoteNumberSequence(model.CoogSQL, CompanyValueMixin):
    'Product Quote Number Sequence'
    __name__ = 'offered.product.quote_number_sequence'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        select=True)
    quote_number_sequence = fields.Many2One('ir.sequence',
        'Quote Number Sequence', domain=[('code', '=', 'quote'),
            ('company', '=', Eval('company', -1))], ondelete='RESTRICT',
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(ProductQuoteNumberSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('quote_number_sequence')
        value_names.append('quote_number_sequence')
        fields.append('company')
        migrate_property(
            'offered.product', field_names, cls, value_names,
            parent='product', fields=fields)


class ContractDataRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoogSQL, model.CoogView):
    'Contract Data Rule'
    __name__ = 'contract.data.rule'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        required=True, select=True)

    @classmethod
    def __setup__(cls):
        super(ContractDataRule, cls).__setup__()
        cls.rule.required = True
        cls.rule.domain = [('type_', '=', 'contract_data')]
        cls.rule.help = 'This rules defines how to initalize a new contract.' \
            ' It should return a dictionnary whose keys are the fields to ' \
            'update on the contract, and whose values are the new field values'

    def _get_authorized_fields(self):
        return ['start_date']
