from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields


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
