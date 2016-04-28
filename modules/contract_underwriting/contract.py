# encoding: utf-8
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool
from trytond.model import dualmethod

from trytond.modules.cog_utils import model, fields
from trytond.modules.contract import _STATES as CONTRACT_STATES

__metaclass__ = PoolMeta
__all__ = [
    'ContractUnderwriting',
    'ContractUnderwritingOption',
    'Contract',
    ]


class ContractUnderwriting(model.CoopSQL, model.CoopView):
    'Contract Underwriting'

    __name__ = 'contract.underwriting'

    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE',
        required=True, select=True)
    decision_date = fields.Date('Decision Date', states={
            'required': Bool(Eval('decision'))},
        depends=['decision'])
    decision = fields.Many2One('underwriting.decision',
        'Underwriting Decision', ondelete='RESTRICT')
    subscriber_decision = fields.Selection([
            ('accepted', 'Accepted'),
            ('refused', 'Refused'),
            ('pending', 'Pending')],
        'Subscriber Underwriting Decision',
        states={
            'invisible': ~Eval('needs_subscriber_validation')
            },
        depends=['needs_subscriber_validation'])
    subscriber_decision_translated = subscriber_decision.translated(
        'subscriber_decision')
    decision_with_exclusion = fields.Function(
        fields.Boolean('Decision With Exclusion', states={'invisible': True}),
        'on_change_with_decision_with_exclusion')
    subscriber_decision_date = fields.Date(
        'Subscriber Underwriting Decision Date', states={
            'invisible': ~Eval('needs_subscriber_validation'),
            'required': Eval('subscriber_decision', '') != 'pending',
            },
        depends=['needs_subscriber_validation', 'subscriber_decision'])
    needs_subscriber_validation = fields.Function(
        fields.Boolean('Needs Subscriber Validation'),
        'on_change_with_needs_subscriber_validation')
    underwriting_options = fields.One2Many('contract.underwriting.option',
        'underwriting', 'Options Underwriting', delete_missing=True,
        states={'invisible': ~Eval('decision_with_exclusion')},
        depends=['decision_with_exclusion'])
    extra_data = fields.Dict('extra_data', 'Extra Data',
        states={'invisible': ~Eval('decision_with_exclusion')},
        domain=[('kind', '=', 'contract_underwriting')],
        depends=['decision_with_exclusion'])
    extra_data_summary = fields.Function(
        fields.Text('Extra Data Summary'),
        'get_extra_data_summary')

    @classmethod
    def __setup__(cls):
        super(ContractUnderwriting, cls).__setup__()
        cls._error_messages.update({
                'underwriting_still_in_progress': 'The underwriting '
                'process is still in progress',
                'refused_by_subscriber': 'The underwriting is refused '
                'by the subscriber',
                })

    @fields.depends('decision', 'needs_subscriber_validation')
    def on_change_with_needs_subscriber_validation(self, name=''):
        if not self.decision:
            return False
        return self.decision.with_subscriber_validation

    @fields.depends('decision')
    def on_change_with_decision_with_exclusion(self, name=''):
        if not self.decision:
            return False
        return self.decision.with_exclusion

    @staticmethod
    def default_subscriber_decision():
        return 'pending'

    @classmethod
    def get_extra_data_summary(cls, extra_datas, name):
        return Pool().get('extra_data').get_extra_data_summary(extra_datas,
            'extra_data')

    @dualmethod
    def update_extra_data(cls, instances):
        for instance in instances:
            extra_data_defs = instance.contract.product.extra_data_def
            res = instance.extra_data or {}
            res.update(
                {extra_data_def.name: extra_data_def.get_default_value(None)
                    for extra_data_def in extra_data_defs
                    if extra_data_def.kind == 'contract_underwriting' and
                    extra_data_def.name not in res})
            res = {k: v for k, v in res.iteritems() if k in [x.name for x in
                    extra_data_defs]}
            instance.extra_data = res

    @dualmethod
    def update_underwriting_options(cls, instances):
        pool = Pool()
        OptionUnderwriting = pool.get('contract.underwriting.option')
        for instance in instances:
            previous = getattr(instance, 'underwriting_options', [])
            previous_options = [x.option for x in previous]
            instance.underwriting_options = list(previous) + [
                OptionUnderwriting(underwriting=instance, extra_data={},
                    option=option)
                for covered_element in instance.contract.covered_elements
                for option in covered_element.options
                if option not in previous_options and
                option.coverage.with_underwriting != 'never_underwrite']
            for option_data in instance.underwriting_options:
                option_data.update_extra_data()
            instance.underwriting_options = instance.underwriting_options

    def check_decision(self):
        in_progress = False
        decision = self.decision
        if not decision or decision.status == 'pending':
            in_progress = True
        elif decision.with_subscriber_validation:
            in_progress = (not self.subscriber_decision or
                self.subscriber_decision == 'pending')
            if not in_progress:
                if self.subscriber_decision == 'refused':
                    self.raise_user_error('refused_by_subscriber')
        if in_progress:
            self.raise_user_error('underwriting_still_in_progress')


class ContractUnderwritingOption(model.CoopSQL, model.CoopView):
    'Contract Option Underwriting'

    __name__ = 'contract.underwriting.option'

    extra_data = fields.Dict('extra_data', 'Extra Data',
        domain=[('kind', '=', 'option_underwriting')])
    extra_data_summary = fields.Function(
        fields.Text('Extra Data Summary'),
        'on_change_with_extra_data_summary')
    option = fields.Many2One('contract.option', 'Option', ondelete='CASCADE',
        required=True, domain=[('parent_contract', '=', Eval('contract'))],
        depends=['contract', 'underwriting'], readonly=True)
    underwriting = fields.Many2One('contract.underwriting',
        'Underwriting', required=True, ondelete='CASCADE')
    contract = fields.Function(
        fields.Many2One('contract', 'Contract', states={'invisible': True}),
        'on_change_with_contract')

    @classmethod
    def _export_light(cls):
        return super(ContractUnderwritingOption, cls)._export_light() \
            | {'option'}

    @fields.depends('contract', 'underwriting', 'option')
    def on_change_with_contract(self, name=None):
        return self.underwriting.contract.id

    @fields.depends('extra_data')
    def on_change_with_extra_data_summary(self, name=None):
        return Pool().get('extra_data').get_extra_data_summary([self],
            'extra_data').values()[0]

    def update_extra_data(self):
        if not self.option:
            self.extra_data = {}
            return
        res = self.extra_data or {}
        extra_data_defs = self.option.coverage.extra_data_def
        res.update({extra_data_def.name: extra_data_def.get_default_value(None)
                for extra_data_def in extra_data_defs
                if extra_data_def.kind == 'option_underwriting' and
                extra_data_def.name not in res})
        res = {k: v for k, v in res.iteritems() if k in [x.name for x in
                extra_data_defs]}
        self.extra_data = res
        self.extra_data_summary = self.on_change_with_extra_data_summary()


class Contract:
    __name__ = 'contract'

    underwritings = fields.One2Many('contract.underwriting',
        'contract', 'Underwritings', delete_missing=True,
        states=CONTRACT_STATES)
    needs_underwriting = fields.Function(
        fields.Boolean('Needs Underwriting'),
        'on_change_with_needs_underwriting')

    @classmethod
    def view_attributes(cls):
        return super(Contract, cls).view_attributes() + [(
                '/form/notebook/page[@id="underwritings"]',
                'states',
                {'invisible': ~Eval('needs_underwriting')}
                )]

    def check_underwriting_complete(self):
        if self.needs_underwriting and self.underwritings:
            self.underwritings[-1].check_decision()

    @fields.depends('options', 'covered_elements')
    def on_change_with_needs_underwriting(self, name):
        all_options = self.options + self.covered_element_options
        return any([x.coverage.with_underwriting != 'never_underwrite'
                for x in all_options])

    def update_underwritings(self):
        pool = Pool()
        ContractUnderwriting = pool.get('contract.underwriting')
        if not self.needs_underwriting:
            return
        if not self.underwritings:
            self.create_underwritings()
        ContractUnderwriting.update_extra_data(self.underwritings)
        ContractUnderwriting.update_underwriting_options(self.underwritings)
        self.underwritings = self.underwritings
        self.save()

    def create_underwritings(self):
        pool = Pool()
        ContractUnderwriting = pool.get('contract.underwriting')
        self.underwritings = [ContractUnderwriting(contract=self,
                extra_data={})]
        self.update_underwritings()
