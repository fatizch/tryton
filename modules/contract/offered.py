# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pyson import Eval, Bool
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond import backend
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (CompanyMultiValueMixin,
    CompanyValueMixin)

from trytond.modules.coog_core import fields, model, coog_string
from trytond.modules.rule_engine import get_rule_mixin
from trytond.modules.rule_engine.rule_engine import RuleEngineResult

DatabaseOperationalError = backend.get('DatabaseOperationalError')


__all__ = [
    'Product',
    'ProductQuoteNumberSequence',
    'ContractDataRule',
    'OptionDescriptionEndingRule',
    ]


class Product(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'offered.product'

    quote_number_sequence = fields.MultiValue(fields.Many2One('ir.sequence',
            'Quote number sequence',
            help='Sequence used to compute the quote number on the contract',
            domain=[
                ('code', '=', 'quote'),
                ('company', 'in', [Eval('context', {}).get('company', -1), None]
                    ), ],
            states={
                'required': Bool(Eval('context', {}).get('company')),
                'invisible': ~Eval('context', {}).get('company'),
                }))
    quote_number_sequences = fields.One2Many(
            'offered.product.quote_number_sequence', 'product', 'Sequences',
            delete_missing=True)
    contract_data_rule = fields.One2Many(
        'contract.data.rule', 'product',
        'Contract Data Rule', help='Rule called at contract creation in order '
        'to initialize any contract field',
        delete_missing=True, size=1)

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        QuoteNumberSequence = pool.get('offered.product.quote_number_sequence')
        TableHandler = backend.get('TableHandler')
        sql_table = cls.__table__()
        quote_sequence = QuoteNumberSequence.__table__()

        super(Product, cls).__register__(module_name)

        cursor = Transaction().connection.cursor()
        table = TableHandler(cls, module_name)

        # Migration from 1.14 sequence Many2One change into MultiValue
        if table.column_exist('quote_number_sequence'):
            query = quote_sequence.insert(
                [quote_sequence.product, quote_sequence.quote_number_sequence],
                sql_table.select(sql_table.id, sql_table.quote_number_sequence))
            cursor.execute(*query)
            table.drop_column('quote_number_sequence', exception=True)

    @classmethod
    def _export_light(cls):
        return (super(Product, cls)._export_light() |
            set(['quote_number_sequences']))

    def update_contract_from_rule(self, contract, no_rule_errors, **kwargs):
        rule = self.contract_data_rule[0]
        exec_context = {}
        try:
            contract.init_dict_for_rule_engine(exec_context)
            res = rule.calculate_rule(exec_context, **kwargs)
        except DatabaseOperationalError:
            raise
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
        for k, v in list(result.items()):
            if k not in auth_fields:
                raise ValidationError(gettext(
                        'contract.msg_data_rule_misconfigured',
                        field=k, product=self.name))
            setattr(contract, k, v)
        return res

    def get_documentation_structure(self):
        doc = super(Product, self).get_documentation_structure()
        doc['parameters'].append(
            coog_string.doc_for_field(self, 'quote_number_sequence'))
        doc['rules'].append(
            coog_string.doc_for_rules(self, 'contract_data_rule'))
        return doc


class ProductQuoteNumberSequence(model.CoogSQL, CompanyValueMixin):
    'Product Quote Number Sequence'
    __name__ = 'offered.product.quote_number_sequence'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        select=True, required=True)
    quote_number_sequence = fields.Many2One('ir.sequence',
        'Quote Number Sequence', domain=[('code', '=', 'quote'),
            ('company', 'in',
                [Eval('company', -1), None])], ondelete='RESTRICT',
        depends=['company'], help='Sequence used to initalize the quote '
        'number')

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

    def get_rule_documentation_structure(self):
        return [self.get_rule_rule_engine_documentation_structure()]


class OptionDescriptionEndingRule(metaclass=PoolMeta):
    __name__ = 'offered.option.description.ending_rule'

    automatic_sub_status = fields.Many2One('contract.sub_status',
    'Automatic Sub Status', domain=[('status', '=', 'terminated')],
        required=True, ondelete='RESTRICT',
        help='Automatic sub status which will be applied on automatilcally '
        'terminated options')
