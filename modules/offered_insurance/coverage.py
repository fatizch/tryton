# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.conditionals import Case

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, coog_string


__all__ = [
    'OptionDescription',
    ]


class OptionDescription(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    insurance_kind = fields.Selection([('', '')], 'Insurance Kind',
        sort=False, help='Categorized coverage (used in insurer delegation '
        'configuration)')
    insurance_kind_string = insurance_kind.translated('insurance_kind')
    insurer = fields.Many2One('insurer', 'Insurer',
        states={'required': ~Eval('is_service')}, ondelete='RESTRICT',
        depends=['is_service'], select=True)
    family = fields.Selection([('generic', 'Generic')], 'Family',
        help='Define the main insurance family. According to the family '
        'selected some behavior are different')
    with_extra_premiums = fields.Boolean('Extra Premium Management',
        help='If True, it is be possible to add extra premiums to subscribed'
        ' options')
    with_exclusions = fields.Boolean('Exclusions Management',
        help='If True, it is be possible to add exclusions to subscribed'
        ' options')
    family_string = family.translated('family')
    item_desc = fields.Many2One('offered.item.description', 'Item Description',
        ondelete='RESTRICT', states={'required': ~Eval('is_service')},
        depends=['is_service'], select=True,
        help='Define the risk covered by the coverage')

    _insurer_flags_cache = Cache('get_insurer_flag')

    @classmethod
    def kind_list_for_extra_data_domain(cls):
        return ['option']

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.extra_data_def.domain = [
            ('kind', 'in', cls.kind_list_for_extra_data_domain())]

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        coverage = TableHandler(cls)

        # Migration from 1.12 : Add with_extra_premiums field
        migrate_extra_premium = not coverage.column_exist(
            'with_extra_premiums')

        super(OptionDescription, cls).__register__(module_name)

        if migrate_extra_premium:
            cursor = Transaction().connection.cursor()
            coverage = cls.__table__()
            cursor.execute(*coverage.update(
                    columns=[coverage.with_extra_premiums,
                        coverage.with_exclusions],
                    values=[Case((coverage.item_desc != Null, True),
                            else_=False),
                        Case((coverage.item_desc != Null, True), else_=False)],
                    ))

    @classmethod
    def create(cls, vlist):
        created = super(OptionDescription, cls).create(vlist)
        Pool().get('offered.item.description')._check_sub_options_cache.clear()
        return created

    @classmethod
    def delete(cls, ids):
        super(OptionDescription, cls).delete(ids)
        Pool().get('offered.item.description')._check_sub_options_cache.clear()

    @classmethod
    def write(cls, *args):
        super(OptionDescription, cls).write(*args)
        Pool().get('offered.item.description')._check_sub_options_cache.clear()

    @classmethod
    def _export_light(cls):
        return (super(OptionDescription, cls)._export_light() |
            set(['insurer']))

    @classmethod
    def default_family(cls):
        return 'generic'

    @staticmethod
    def default_insurance_kind():
        return ''

    @fields.depends('item_desc')
    def on_change_with_is_service(self, name=None):
        return not self.item_desc

    @classmethod
    def get_possible_coverages_clause(cls, instance, at_date):
        clause = super(OptionDescription, cls).get_possible_coverages_clause(
            instance, at_date)
        if instance and instance.__name__ == 'contract.covered_element':
            return clause + [
                ('products', '=', instance.product.id),
                ('item_desc', '=', instance.item_desc.id)]
        return clause

    def get_currency(self):
        return self.currency

    @classmethod
    def get_insurer_flag(cls, coverage, flag_name):
        cached = cls._insurer_flags_cache.get(coverage.id, -1)
        if cached != -1:
            return cached[flag_name]
        flags = Pool().get('insurer.delegation')._delegation_flags
        if coverage.insurer:
            delegation_line = coverage.insurer.get_delegation(
                coverage.insurance_kind)
            cached = {x: getattr(delegation_line, x) for x in flags}
        else:
            cached = {x: True for x in flags}
        cls._insurer_flags_cache.set(coverage.id, cached)
        return cached[flag_name]

    def get_insurer(self, at_date=None):
        return self.insurer

    def is_contract_option(self):
        if self.item_desc:
            return False
        return super().is_contract_option()

    def get_documentation_structure(self):
        structure = super(OptionDescription, self).get_documentation_structure()
        structure['parameters'].extend([
            coog_string.doc_for_field(self, 'insurance_kind'),
            coog_string.doc_for_field(self, 'insurer',
                self.insurer.rec_name if self.insurer else ''),
            coog_string.doc_for_field(self, 'family'),
            coog_string.doc_for_field(self, 'with_extra_premiums'),
            coog_string.doc_for_field(self, 'with_exclusions'),
            coog_string.doc_for_field(self, 'item_desc',
                self.item_desc.rec_name if self.item_desc else ''),
            ])
        return structure
