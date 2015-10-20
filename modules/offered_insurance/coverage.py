# -*- coding:utf-8 -*-
import copy
import datetime

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields
from trytond.modules.offered_insurance import offered


__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    'OfferedOptionDescription',
    ]

COULD_NOT_FIND_A_MATCHING_RULE = 'Could not find a matching rule'


class OptionDescription:
    __name__ = 'offered.option.description'

    insurance_kind = fields.Selection([('', '')], 'Insurance Kind',
        sort=False)
    insurer = fields.Many2One('insurer', 'Insurer',
        states={'required': ~Eval('is_service')}, ondelete='RESTRICT',
        depends=['is_service'])
    family = fields.Selection([('generic', 'Generic')], 'Family')
    family_string = family.translated('family')
    item_desc = fields.Many2One('offered.item.description', 'Item Description',
        ondelete='RESTRICT', states={'required': ~Eval('is_service')},
        depends=['is_service'], select=True)

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.extra_data_def.domain = [
            ('kind', 'in', ['contract', 'covered_element', 'option'])]
        for field_name in (mgr for mgr in dir(cls) if mgr.endswith('_mgr')):
            cur_attr = copy.copy(getattr(cls, field_name))
            if not hasattr(cur_attr, 'context') or not isinstance(
                    cur_attr, fields.Field):
                continue
            if cur_attr.context is None:
                cur_attr.context = {}
            # cur_attr.context['for_family'] = Eval('family')
            cur_attr = copy.copy(cur_attr)
            setattr(cls, field_name, cur_attr)

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
    def delete(cls, entities):
        cls.delete_rules(entities)
        super(OptionDescription, cls).delete(entities)

    @classmethod
    def get_possible_coverages_clause(cls, instance, at_date):
        clause = super(OptionDescription, cls).get_possible_coverages_clause(
            instance, at_date)
        if instance and instance.__name__ == 'contract.covered_element':
            return clause + [
                ('products', '=', instance.product.id),
                ('item_desc', '=', instance.item_desc.id)]
        return clause

    def give_me_covered_elements_at_date(self, args):
        contract = args['contract']
        res = []
        for covered in contract.covered_elements:
            for option in covered.options:
                if option.coverage != self:
                    continue
                if not(option.start_date <= args['date']
                        <= (option.end_date or datetime.date.max)):
                    continue
                if option.status in ('quote', 'active'):
                    res.append((covered, option))
        return res, []

    def get_currency(self):
        return self.currency

    @classmethod
    def get_var_names_for_full_extract(cls):
        res = super(OptionDescription, cls).get_var_names_for_full_extract()
        res.extend([('item_desc', 'light')])
        return res


class OfferedOptionDescription(offered.Offered):
    'OptionDescription'

    __name__ = 'offered.option.description'
    # This empty override is necessary to have in the coverage the fields added
    # in the override of offered
