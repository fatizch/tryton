from collections import defaultdict
from trytond.pool import PoolMeta, Pool
from trytond.model import Unique
from trytond.wizard import StateView
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, fields, coop_string
from .endorsement import field_mixin
from .wizard import EndorsementWizardPreviewMixin


__metaclass__ = PoolMeta
__all__ = [
    'EndorsementDefinition',
    'EndorsementPart',
    'EndorsementDefinitionPartRelation',
    'EndorsementPartMethodRelation',
    'EndorsementContractField',
    'EndorsementOptionField',
    'EndorsementOptionVersionField',
    'EndorsementActivationHistoryField',
    'EndorsementContactField',
    'EndorsementExtraDataField',
    'Product',
    'EndorsementDefinitionProductRelation',
    'EndorsementSubState',
    ]


class EndorsementDefinition(model.CoopSQL, model.CoopView):
    'Endorsement Definition'

    __name__ = 'endorsement.definition'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)
    ordered_endorsement_parts = fields.One2Many(
        'endorsement.definition-endorsement.part', 'definition',
        'Endorsement Parts', delete_missing=True)
    preview_state = fields.Selection('get_preview_states', 'Preview States')
    active = fields.Boolean('Active')
    preview_state_string = preview_state.translated('preview_state')
    products = fields.Many2Many('endorsement.definition-product',
        'endorsement_definition', 'product', 'Products')
    endorsement_parts = fields.Function(
        fields.Many2Many('endorsement.part', None, None, 'Endorsement Parts'),
        'get_endorsement_parts')
    is_technical = fields.Function(
        fields.Boolean('Is technical'),
        'get_is_technical', searcher='search_is_technical')
    is_multi_instance = fields.Function(
        fields.Boolean('Handles Multiple Instances'),
        'get_is_multi_instance')

    @classmethod
    def __setup__(cls):
        super(EndorsementDefinition, cls).__setup__()
        cls._order = [('name', 'ASC')]

    @classmethod
    def _export_skips(cls):
        return (super(EndorsementDefinition, cls)._export_skips() |
            set(['products']))

    @classmethod
    def default_active(cls):
        return True

    def get_is_multi_instance(self, name):
        pool = Pool()
        StartEndorsement = pool.get('endorsement.start', type='wizard')
        for view in [x.view for x in self.endorsement_parts if x.view]:
            step_mixin_name = getattr(StartEndorsement, view).model_name
            StepMixin = pool.get(step_mixin_name)
            if not StepMixin.is_multi_instance():
                return False
        return True

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

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

    def get_is_technical(self, name):
        return any([x.endorsement_part.view == 'dummy_step'
                for x in self.ordered_endorsement_parts])

    @classmethod
    def search_is_technical(cls, name, clause):
        if clause[1] == '=':
            if clause[2]:
                operator = '='
            else:
                operator = '!='
        elif clause[2]:
            operator = '!='
        else:
            operator = '='

        return [('ordered_endorsement_parts.endorsement_part.view', operator,
                'dummy_step')]

    @classmethod
    def get_preview_states(cls):
        # Returns the endorsement wizard preview state views
        pool = Pool()
        StartEndorsement = pool.get('endorsement.start', type='wizard')
        result = {}
        for state_name, state in StartEndorsement.states.iteritems():
            if not issubclass(state.__class__, StateView):
                continue
            state_class = pool.get(state.model_name)
            if not issubclass(state_class, EndorsementWizardPreviewMixin):
                continue
            result[state_name] = state_class.__name__
            # TODO : Fix this. Fails on BasicPreview with
            # endorsement_insurance_invoice override
            # result[state_name] = \
            #     coop_string.translate_model_name(state_class)
        return [(k, v) for k, v in result.iteritems()] + [('', '')]

    def get_methods_for_model(self, model_name):
        result = {}
        for endorsement_part in self.endorsement_parts:
            for method in endorsement_part.post_apply_actions:
                if method.model.model != model_name:
                    continue
                result[method.method_name] = method
        return sorted(result.values(), key=lambda x: x.priority)


class EndorsementPart(model.CoopSQL, model.CoopView):
    'Endorsement Part'
    _func_key = 'code'

    __name__ = 'endorsement.part'

    activation_history_fields = fields.One2Many(
        'endorsement.contract.activation_history.field',
        'endorsement_part', 'ActivationHistory fields', states={
            'invisible': Eval('kind', '') != 'activation_history',
            }, depends=['kind'], delete_missing=True)
    code = fields.Char('Code')
    contract_fields = fields.One2Many('endorsement.contract.field',
        'endorsement_part', 'Contract fields', states={
            'invisible': (Eval('kind', '') != 'contract')},
        depends=['kind'], delete_missing=True)
    definitions = fields.Many2Many('endorsement.definition-endorsement.part',
        'endorsement_part', 'definition', 'Used by')
    name = fields.Char('Name', translate=True)
    description = fields.Text('Endorsement Description')
    kind = fields.Selection([
            ('contract', 'Contract'),
            ('option', 'Option'),
            ('activation_history', 'Activation Dates'),
            ('extra_data', 'Extra Data'),
            ], 'Kind')
    kind_string = kind.translated('kind')
    option_fields = fields.One2Many('endorsement.contract.option.field',
        'endorsement_part', 'Option fields', states={
            'invisible': Eval('kind', '') != 'option',
            }, depends=['kind'], delete_missing=True)
    view = fields.Selection('get_possible_views', 'View')
    post_apply_actions = fields.Many2Many('endorsement.part-method',
        'endorsement_part', 'method', 'Post Apply Actions',
        domain=[('model', '=', Eval('endorsed_model', None))],
        depends=['endorsed_model'])
    endorsed_model = fields.Function(
        fields.Many2One('ir.model', 'Endorsed Model'),
        'on_change_with_endorsed_model')

    @classmethod
    def view_attributes(cls):
        return super(EndorsementPart, cls).view_attributes() + [(
                '/form/notebook/page[@id="definition"]',
                'states',
                {'invisible': ~Eval('kind')}
                )]

    @classmethod
    def _export_skips(cls):
        return (super(EndorsementPart, cls)._export_skips() |
            set(['definitions']))

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

    @fields.depends('kind')
    def on_change_with_endorsed_model(self, name=None):
        if not self.kind:
            return None
        return Pool().get('ir.model').search([
                ('model', '=', 'contract')])[0].id

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
        if self.activation_history_fields:
            self.clean_up_relation(endorsement, 'activation_history_fields',
                'activation_history')

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
        required=True, ondelete='CASCADE', select=True)
    endorsement_part = fields.Many2One('endorsement.part',
        'Endorsement Part', required=True, ondelete='RESTRICT', select=True)
    order = fields.Integer('Order')

    @classmethod
    def __setup__(cls):
        super(EndorsementDefinitionPartRelation, cls).__setup__()
        cls._order.append(('order', 'ASC'))


class EndorsementPartMethodRelation(model.CoopSQL):
    'Endorsement Part Method Relation'

    __name__ = 'endorsement.part-method'

    endorsement_part = fields.Many2One('endorsement.part', 'Endorsement Part',
        required=True, select=1, ondelete='CASCADE')
    method = fields.Many2One('ir.model.method', 'Method', required=True,
        select=1, ondelete='RESTRICT')


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


class EndorsementOptionVersionField(field_mixin('contract.option.version'),
        model.CoopSQL, model.CoopView):
    'Endorsement Option Version Field'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.option.version.field'


class EndorsementActivationHistoryField(
        field_mixin('contract.activation_history'),
        model.CoopSQL, model.CoopView):
    'Endorsement Activation History Field'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.activation_history.field'


class EndorsementContactField(field_mixin('contract.contact'),
        model.CoopSQL, model.CoopView):
    'Endorsement Contact Field'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.contact.field'


class EndorsementExtraDataField(
        field_mixin('contract.extra_data'),
        model.CoopSQL, model.CoopView):
    'Endorsement Extra Data Field'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.extra_data.field'


class Product:
    'Product'

    __name__ = 'offered.product'

    endorsement_definitions = fields.Many2Many(
        'endorsement.definition-product', 'product', 'endorsement_definition',
        'Endorsement Definitions')

    @classmethod
    def _export_light(cls):
        return super(Product, cls)._export_light() | {
            'endorsement_definitions'}


class EndorsementDefinitionProductRelation(model.CoopSQL):
    'Endorsement Definition to Product Relation'

    __name__ = 'endorsement.definition-product'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    endorsement_definition = fields.Many2One('endorsement.definition',
        'Definition', ondelete='RESTRICT')


class EndorsementSubState(model.CoopSQL, model.CoopView):
    'Endorsement SubState'

    __name__ = 'endorsement.sub_state'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    state = fields.Selection([
            ('declined', 'Declined'),
            ], 'State', required=True)

    @classmethod
    def __setup__(cls):
        super(EndorsementSubState, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)
