from collections import defaultdict
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, fields, coop_string
from .endorsement import field_mixin


__metaclass__ = PoolMeta
__all__ = [
    'EndorsementDefinition',
    'EndorsementPart',
    'EndorsementDefinitionPartRelation',
    'EndorsementContractField',
    'EndorsementOptionField',
    'Product',
    'EndorsementDefinitionProductRelation',
    ]


class EndorsementDefinition(model.CoopSQL, model.CoopView):
    'Endorsement Definition'

    __name__ = 'endorsement.definition'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)
    ordered_endorsement_parts = fields.One2Many(
        'endorsement.definition-endorsement.part', 'definition',
        'Endorsement Parts')
    products = fields.Many2Many('endorsement.definition-product',
        'endorsement_definition', 'product', 'Products')
    endorsement_parts = fields.Function(
        fields.Many2Many('endorsement.part', None, None, 'Endorsement Parts'),
        'get_endorsement_parts')

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)

    @classmethod
    def get_endorsement_parts(cls, definitions, name):
        cursor = Transaction().cursor
        pool = Pool()
        intermediate_table = pool.get(
            'endorsement.definition-endorsement.part').__table__()

        cursor.execute(*intermediate_table.select(
                intermediate_table.definition,
                intermediate_table.endorsement_part,
                where=intermediate_table.definition.in_(
                    [x.id for x in definitions]),
                order_by=intermediate_table.order))

        result = defaultdict(list)
        for definition_id, part_id in cursor.fetchall():
            result[definition_id].append(part_id)
        return result

    def get_contract_modified_fields(self):
        return set([])

    def extract_contract_values(self, contract):
        result = {}
        for field_name in self.get_contract_modified_fields():
            result[field_name] = getattr(contract, field_name)
        return result


class EndorsementPart(model.CoopSQL, model.CoopView):
    'Endorsement Part'

    __name__ = 'endorsement.part'

    code = fields.Char('Code')
    contract_fields = fields.One2Many('endorsement.contract.field',
        'endorsement_part', 'Contract fields', states={
            'invisible': Eval('kind', '') != 'contract'},
        depends=['kind'])
    definitions = fields.Many2Many('endorsement.definition-endorsement.part',
        'endorsement_parts', 'definition', 'Used by')
    name = fields.Char('Name')
    description = fields.Text('Endorsement Description')
    kind = fields.Selection([
            ('contract', 'Contract'),
            ('option', 'Option'),
            ], 'Kind')
    option_fields = fields.One2Many('endorsement.contract.option.field',
        'endorsement_part', 'Option fields', states={
            'invisible': Eval('kind', '') != 'option',
            }, depends=['kind'])
    view = fields.Selection('get_possible_views', 'View')

    @classmethod
    def _export_keys(cls):
        return set(['code'])

    @classmethod
    def _export_skips(cls):
        result = super(EndorsementPart, cls)._export_skips()
        result.add('products')
        return result

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)

    @classmethod
    def get_possible_views(cls):
        EndorsementWizard = Pool().get('endorsement.start', type='wizard')
        return [(k, v) for k, v in
            EndorsementWizard.get_endorsement_states().iteritems()]

    def clean_up(self, endorsement):
        # Cleans up the current endorsement of all data relative to the
        # current endorsement part
        for field in self.contract_fields:
            endorsement.values.pop(field.name, None)
        if self.option_fields:
            self.clean_up_relation(endorsement, 'option_fields', 'options')

    def clean_up_relation(self, endorsement, field_name, endorsed_field_name):
        # Cleans up the current endorsement of relation data linked to the
        # relation part
        to_delete = []
        for elem in getattr(endorsement, endorsed_field_name):
            if elem.action == 'remove':
                continue
            for field in getattr(self, field_name):
                elem.values.pop(field.name, None)
            if not elem.values:
                to_delete.append(elem)
        if to_delete:
            BaseModel = Pool().get(
                endorsement._fields[endorsed_field_name].model_name)
            BaseModel.delete(to_delete)


class EndorsementDefinitionPartRelation(model.CoopSQL, model.CoopView):
    'Endorsement Definition Part Relation'

    __name__ = 'endorsement.definition-endorsement.part'

    definition = fields.Many2One('endorsement.definition', 'Definition',
        required=True, ondelete='CASCADE')
    endorsement_part = fields.Many2One('endorsement.part',
        'Endorsement Part', required=True, ondelete='RESTRICT')
    order = fields.Integer('Order')

    @classmethod
    def __setup__(cls):
        super(EndorsementDefinitionPartRelation, cls).__setup__()
        cls._order.append(('order', 'ASC'))


class EndorsementContractField(field_mixin('contract'), model.CoopSQL,
        model.CoopView):
    'Endorsement Contract Field'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.field'


class EndorsementOptionField(field_mixin('contract.option'),
        model.CoopSQL, model.CoopView):
    'Endorsement Option Field'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.option.field'


class Product:
    'Product'

    __name__ = 'offered.product'

    endorsement_definitions = fields.Many2Many(
        'endorsement.definition-product', 'product', 'endorsement_definition',
        'Endorsement Definitions')


class EndorsementDefinitionProductRelation(model.CoopSQL):
    'Endorsement Definition to Product Relation'

    __name__ = 'endorsement.definition-product'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    endorsement_definition = fields.Many2One('endorsement.definition',
        'Definition', ondelete='RESTRICT')
