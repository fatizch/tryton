# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from trytond.pool import PoolMeta, Pool
from trytond.model import Unique
from trytond.wizard import StateView
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.pyson import Eval, If, Bool

from trytond.modules.coog_core import model, fields, coog_string
from trytond.modules.rule_engine import get_rule_mixin
from .endorsement import field_mixin
from .wizard import EndorsementWizardPreviewMixin


__all__ = [
    'EndorsementDefinitionGroupRelation',
    'EndorsementStartRule',
    'EndorsementDefinition',
    'EndorsementPart',
    'EndorsementDefinitionPartRelation',
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


class EndorsementDefinition(model.CoogSQL, model.CoogView):
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
    next_endorsement = fields.Many2One('endorsement.definition',
        'Next Endorsement', ondelete='RESTRICT')
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
    report_templates = fields.Many2Many(
        'endorsement.definition-report.template', 'definition',
        'report_template', 'Report Templates')
    groups = fields.Many2Many(
        'endorsement.definition-res.group', 'definition',
        'group', 'Groups')
    start_rule = fields.One2Many(
        'endorsement.start.rule', 'definition',
        'Endorsement Start Rule', delete_missing=True, size=1,
        help="This rule will be executed when the user tries to start "
        "an endorsement. You can add user errors and warnings. "
        "The endorsement creation will only be allowed if the rule returns "
        "the value True")
    async_application = fields.Boolean('Asynchronous Application',
        domain=[If(Bool(Eval('next_endorsement')),
                ('async_application', '=', False),
                (),
                )],
        depends=['next_endorsement'],
        help="If checked, the application will be handled by a background  "
        "process. The user can then come back later and check the result")

    _endorsement_by_code_cache = Cache('endorsement_definition_by_code')

    @classmethod
    def __setup__(cls):
        super(EndorsementDefinition, cls).__setup__()
        cls._order = [('name', 'ASC')]

    @classmethod
    def create(cls, *args, **kwargs):
        cls._endorsement_by_code_cache.clear()
        return super(EndorsementDefinition, cls).create(*args, **kwargs)

    @classmethod
    def write(cls, *args, **kwargs):
        cls._endorsement_by_code_cache.clear()
        return super(EndorsementDefinition, cls).write(*args, **kwargs)

    @classmethod
    def delete(cls, *args, **kwargs):
        cls._endorsement_by_code_cache.clear()
        return super(EndorsementDefinition, cls).delete(*args, **kwargs)

    @classmethod
    def _export_skips(cls):
        return (super(EndorsementDefinition, cls)._export_skips() |
            set(['products']))

    @classmethod
    def default_active(cls):
        return True

    @classmethod
    def _export_light(cls):
        return (super(EndorsementDefinition, cls)._export_skips() |
            set(['report_templates']))

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
        return coog_string.slugify(self.name)

    @classmethod
    def get_endorsement_parts(cls, definitions, name):
        cursor = Transaction().connection.cursor()
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
    def get_definition_by_code(cls, code):
        value = cls._endorsement_by_code_cache.get(None, None)
        if value is not None:
            return cls(value[code])
        cls._endorsement_by_code_cache.set(None, {x.code: x.id
                for x in cls.search([('active', 'in', [True, False])])})
        return cls.get_definition_by_code(code)

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
            #     coog_string.translate_model_name(state_class)
        return [(k, v) for k, v in result.iteritems()] + [('', '')]

    def get_methods_for_model(self, model_name):
        method_names = set()
        for endorsement_part in self.endorsement_parts:
            method_names |= endorsement_part.get_methods_for_model(model_name)
        return method_names

    def get_draft_methods_for_model(self, model_name):
        method_names = set()
        for endorsement_part in self.endorsement_parts:
            method_names |= endorsement_part.get_draft_methods_for_model(
                model_name)
        return method_names


class EndorsementStartRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoogSQL, model.CoogView):
    'Endorsement Start Rule'
    __name__ = 'endorsement.start.rule'

    definition = fields.Many2One('endorsement.definition',
        'Definition', required=True, ondelete='CASCADE',
        select=True)

    @classmethod
    def __setup__(cls):
        super(EndorsementStartRule, cls).__setup__()
        cls.rule.required = True
        cls.rule.domain = [('type_', '=', 'endorsement_start')]


class EndorsementPart(model.CoogSQL, model.CoogView):
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
        return coog_string.slugify(self.name)

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

    def get_methods_for_model(self, model_name):
        pool = Pool()
        EndorsementStart = pool.get('endorsement.start', type='wizard')
        possible_states = EndorsementStart.get_endorsement_states()
        Target = pool.get(possible_states[self.view])
        return Target.get_methods_for_model(model_name)

    def get_draft_methods_for_model(self, model_name):
        pool = Pool()
        EndorsementStart = pool.get('endorsement.start', type='wizard')
        possible_states = EndorsementStart.get_endorsement_states()
        Target = pool.get(possible_states[self.view])
        return Target.get_draft_methods_for_model(model_name)

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


class EndorsementDefinitionPartRelation(model.CoogSQL, model.CoogView):
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
        cls._order = [('order', 'ASC')]


class EndorsementContractField(field_mixin('contract'), model.CoogSQL,
        model.CoogView):
    'Endorsement Contract Field'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.field'


class EndorsementOptionField(field_mixin('contract.option'),
        model.CoogSQL, model.CoogView):
    'Endorsement Option Field'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.option.field'


class EndorsementOptionVersionField(field_mixin('contract.option.version'),
        model.CoogSQL, model.CoogView):
    'Endorsement Option Version Field'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.option.version.field'


class EndorsementActivationHistoryField(
        field_mixin('contract.activation_history'),
        model.CoogSQL, model.CoogView):
    'Endorsement Activation History Field'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.activation_history.field'


class EndorsementContactField(field_mixin('contract.contact'),
        model.CoogSQL, model.CoogView):
    'Endorsement Contact Field'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.contact.field'


class EndorsementExtraDataField(
        field_mixin('contract.extra_data'),
        model.CoogSQL, model.CoogView):
    'Endorsement Extra Data Field'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.extra_data.field'


class Product:
    'Product'

    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    endorsement_definitions = fields.Many2Many(
        'endorsement.definition-product', 'product', 'endorsement_definition',
        'Endorsement Definitions')

    @classmethod
    def _export_light(cls):
        return super(Product, cls)._export_light() | {
            'endorsement_definitions'}


class EndorsementDefinitionProductRelation(model.CoogSQL):
    'Endorsement Definition to Product Relation'

    __name__ = 'endorsement.definition-product'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    endorsement_definition = fields.Many2One('endorsement.definition',
        'Definition', ondelete='RESTRICT')


class EndorsementSubState(model.CoogSQL, model.CoogView):
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
        return coog_string.slugify(self.name)


class EndorsementDefinitionGroupRelation(model.CoogSQL, model.CoogView):
    'Endorsement Definition Group Relation'

    __name__ = 'endorsement.definition-res.group'

    definition = fields.Many2One('endorsement.definition', 'Definition',
        required=True, ondelete='CASCADE', select=True)
    group = fields.Many2One('res.group', 'Group', required=True,
        ondelete='RESTRICT', select=True)
