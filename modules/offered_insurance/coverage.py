# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.cache import Cache
from trytond.pyson import Eval

from trytond.modules.coog_core import fields


__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    ]


class OptionDescription:
    __name__ = 'offered.option.description'

    insurance_kind = fields.Selection([('', '')], 'Insurance Kind',
        sort=False)
    insurance_kind_string = insurance_kind.translated('insurance_kind')
    insurer = fields.Many2One('insurer', 'Insurer',
        states={'required': ~Eval('is_service')}, ondelete='RESTRICT',
        depends=['is_service'])
    family = fields.Selection([('generic', 'Generic')], 'Family')
    family_string = family.translated('family')
    item_desc = fields.Many2One('offered.item.description', 'Item Description',
        ondelete='RESTRICT', states={'required': ~Eval('is_service')},
        depends=['is_service'], select=True)

    _insurer_flags_cache = Cache('get_insurer_flag')

    @classmethod
    def kind_list_for_extra_data_domain(cls):
        return ['contract', 'covered_element', 'option']

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.extra_data_def.domain = [
            ('kind', 'in', cls.kind_list_for_extra_data_domain())]

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
            delegation_line = coverage.insurer.get_delegation(coverage.family)
            cached = {x: getattr(delegation_line, x) for x in flags}
        else:
            cached = {x: True for x in flags}
        cls._insurer_flags_cache.set(coverage.id, cached)
        return cached[flag_name]
