from trytond.pool import PoolMeta

from trytond.modules.cog_utils import model, fields, coop_string


__all__ = [
    'Product',
    'EndorsementTemplate',
    'EndorsementTemplateProductRelation',
]

__metaclass__ = PoolMeta


class EndorsementTemplate(model.CoopSQL, model.CoopView):
    'Endorsement Template'

    __name__ = 'endorsement.template'

    name = fields.Char('Name')
    code = fields.Char('Code')
    contract_fields = fields.One2Many('endorsement.field', 'template',
        'Contract fields')
    option_fields = fields.One2Many('endorsement.option.field', 'template',
        'Option fields')
    products = fields.Many2Many('endorsement.template-product', 'template',
        'product', 'Products')
    description = fields.Text('Endorsement Description')

    @classmethod
    def _export_keys(cls):
        return set(['code'])

    @classmethod
    def _export_skips(cls):
        result = super(EndorsementTemplate, cls)._export_skips()
        result.add('products')
        return result

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)

    def init_endorsement(self, endorsement):
        endorsement.template = self


class Product:
    'Product'

    __name__ = 'offered.product'

    endorsement_templates = fields.Many2Many('endorsement.template-product',
        'product', 'template', 'Endorsement Templates')


class EndorsementTemplateProductRelation(model.CoopSQL):
    'Endorsement Template to Product Relation'

    __name__ = 'endorsement.template-product'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    template = fields.Many2One('endorsement.template', 'Template',
        ondelete='RESTRICT')
