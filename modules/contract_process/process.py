# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, utils, model
from trytond.modules.process_cog.process import ProcessFinder, ProcessStart


__all__ = [
    'Process',
    'ProcessProductRelation',
    'ProcessAction',
    'ContractSubscribeFindProcess',
    'ContractSubscribe',
    'ProcessResume',
    ]


class Process:
    __metaclass__ = PoolMeta
    __name__ = 'process'

    for_products = fields.Many2Many('process-offered.product',
        'process', 'product', 'Products')

    @classmethod
    def _export_skips(cls):
        return (super(Process, cls)._export_skips() | set(['for_products']))

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind.selection.append(('subscription', 'Contract Subscription'))


class ProcessProductRelation(model.CoogSQL):
    'Process Product Relation'

    __name__ = 'process-offered.product'

    product = fields.Many2One('offered.product', 'Product',
        ondelete='CASCADE')
    process = fields.Many2One('process', 'Process',
        ondelete='CASCADE')


class ProcessAction:
    __metaclass__ = PoolMeta
    __name__ = 'process.action'

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.12: migrate check_option_dates method
        super(ProcessAction, cls).__register__(module_name)
        process_action = cls.__table__()
        cursor = Transaction().connection.cursor()
        cursor.execute(*process_action.update(
                columns=[process_action.method_name],
                values=['check_options_dates'],
                where=(process_action.method_name == 'check_option_dates')
                ))


class ContractSubscribeFindProcess(ProcessStart):
    'ContractSubscribe Find Process'

    __name__ = 'contract.subscribe.find_process'

    start_date = fields.Date('Effective Date', required=True, states={
            'readonly': Bool(Eval('start_date_readonly'))},
        depends=['start_date_readonly'])
    signature_date = fields.Date('Signature Date')
    appliable_conditions_date = fields.Date('Appliable Conditions Date',
        required=True, states={'readonly': ~Eval('free_conditions_date')},
        depends=['free_conditions_date'])
    product = fields.Many2One('offered.product', 'Product', domain=[
            ['OR',
                [('end_date', '>=', Eval('appliable_conditions_date'))],
                [('end_date', '=', None)],
                ],
            ['OR',
                [('start_date', '<=', Eval('appliable_conditions_date'))],
                [('start_date', '=', None)],
                ]
            ], depends=['appliable_conditions_date'], required=True)
    party = fields.Many2One('party.party', 'Party', states={'invisible': True})
    free_conditions_date = fields.Boolean('Free Conditions Date', readonly=True)
    start_date_readonly = fields.Boolean('Start Date Is Read Only',
        readonly=True)
    errors = fields.Text("Errors", states={'invisible': ~Eval('errors')},
        readonly=True)

    @classmethod
    def view_attributes(cls):
        return super(ContractSubscribeFindProcess, cls).view_attributes() + [(
                'group[@id="error_group"]',
                'states',
                {'invisible': ~Eval('errors')}
                ),
            ]

    @classmethod
    def default_free_conditions_date(cls):
        configuration = Pool().get('offered.configuration').get_singleton()
        return configuration.free_conditions_date if configuration else False

    @fields.depends('product', 'start_date', 'signature_date',
        'appliable_conditions_date', 'free_conditions_date', 'model')
    def on_change_signature_date(self):
        self.simulate_init()

    @fields.depends('start_date', methods=['signature_date'])
    def on_change_start_date(self):
        self.simulate_init()

    @fields.depends('appliable_conditions_date', methods=['signature_date'])
    def on_change_appliable_conditions_date(self):
        self.simulate_init()

    @fields.depends('product', methods=['signature_date'])
    def on_change_product(self):
        self.simulate_init()

    def _fields_to_init(self):
        return ('appliable_conditions_date', 'start_date',
            'signature_date', 'product')

    def format_errors(self, rule_engine_errors):
        return '\n'.join(rule_engine_errors)

    def unset_product(self):
        self.product = None

    def simulate_init(self):
        self.start_date_readonly = False
        Contract = Pool().get('contract')
        simulated = Contract()
        for f in self._fields_to_init():
            setattr(simulated, f, getattr(self, f))
        rule_res = simulated.update_from_data_rule(return_full=True)
        if rule_res and rule_res.errors:
            self.unset_product()
            self.errors = self.format_errors(rule_res.errors)
            return rule_res
        else:
            self.errors = ''
        simulated.init_from_baseline_rule()
        for f in self._fields_to_init():
            new = getattr(simulated, f)
            setattr(self, f, new)
        if rule_res and rule_res.result and 'start_date' in rule_res.result:
            self.start_date_readonly = True
        return rule_res

    @classmethod
    def build_process_domain(cls):
        result = super(
            ContractSubscribeFindProcess, cls).build_process_domain()
        result.append(('for_products', '=', Eval('product')))
        result.append(('kind', '=', 'subscription'))
        return result

    @classmethod
    def build_process_depends(cls):
        result = super(
            ContractSubscribeFindProcess, cls).build_process_depends()
        result.append('product')
        return result

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'contract')])[0].id

    @staticmethod
    def default_party():
        if Transaction().context.get('active_model') == 'party.party':
            return Transaction().context.get('active_id', None)

    @fields.depends('appliable_conditions_date', 'product')
    def on_change_with_good_process(self):
        return super(ContractSubscribeFindProcess,
            self).on_change_with_good_process()


class ContractSubscribe(ProcessFinder):
    'Contract Subscribe'

    __name__ = 'contract.subscribe'

    @classmethod
    def get_parameters_model(cls):
        return 'contract.subscribe.find_process'

    @classmethod
    def get_parameters_view(cls):
        return \
            'contract_process.contract_subscribe_find_process_form'

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(ContractSubscribe,
            self).init_main_object_from_process(obj, process_param)
        if res:
            if process_param.party:
                obj.subscriber = process_param.party
            obj.start_date = process_param.start_date
            obj.initial_start_date = obj.start_date
            obj.signature_date = process_param.signature_date
            obj.appliable_conditions_date = \
                process_param.appliable_conditions_date
            obj.init_from_product(process_param.product)
        return res, errs

    def finalize_main_object(self, obj):
        document_reception = Transaction().context.get(
            'current_document_reception', None)
        if not document_reception:
            return
        document = Pool().get('document.reception')(document_reception)
        document.transfer(obj)


class ProcessResume:
    __metaclass__ = PoolMeta
    __name__ = 'process.resume'

    def do_resume(self, action):
        pool = Pool()
        active_id = Transaction().context.get('active_id')
        active_model = Transaction().context.get('active_model')
        instance = pool.get(active_model)(active_id)
        if (instance.current_state or active_model != 'contract'
                or instance.status != 'quote'):
            return super(ProcessResume, self).do_resume(action)
        model, = pool.get('ir.model').search(('model', '=', active_model),
            limit=1)
        process_finder = pool.get('contract.subscribe.find_process')(
            model=model,
            effective_date=instance.start_date,
            product=instance.product,
            party=instance.subscriber)
        process = utils.get_domain_instances(process_finder, 'good_process')
        if process:
            process = process[0]
            instance.current_state = process.all_steps[0]
            instance.save()
        return super(ProcessResume, self).do_resume(action)
