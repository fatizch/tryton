# encoding: utf-8
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, If
from trytond.model import dualmethod

from trytond.modules.cog_utils import model, fields, utils
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
    automatic_decision = fields.Boolean('Automatic Decision')
    decision = fields.Many2One('underwriting.decision',
        'Underwriting Decision', domain=[('level', '=', 'contract'),
                If(Bool(Eval('possible_decisions')),
                    ('id', 'in', Eval('possible_decisions')),
                    ())], depends=['possible_decisions'], ondelete='RESTRICT')
    possible_decisions = fields.Function(
        fields.Many2Many('underwriting.decision', None, None,
            'Possible Decisions'),
        'get_possible_decisions_id')
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
    decision_with_extra_data = fields.Function(
        fields.Boolean('Decision With Extra Data', states={'invisible': True}),
        'on_change_with_decision_with_extra_data')
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
        states={'invisible': Bool(Eval('hide_underwriting_options'))},
        depends=['hide_underwriting_options'])
    hide_underwriting_options = fields.Function(
        fields.Boolean('Hide Underwriting Options'),
        'on_change_with_hide_underwriting_options')
    extra_data = fields.Dict('extra_data', 'Extra Data',
        states={'invisible': ~Eval('decision_with_extra_data')},
        domain=[('kind', '=', 'contract_underwriting')],
        depends=['decision_with_extra_data'])
    extra_data_summary = fields.Function(
        fields.Text('Extra Data Summary'),
        'get_extra_data_summary')
    underwriting_submission_date = fields.Date('Underwriting Submission Date')

    @classmethod
    def __setup__(cls):
        super(ContractUnderwriting, cls).__setup__()
        cls._error_messages.update({
                'underwriting_still_in_progress': 'The underwriting '
                'process is still in progress',
                'refused_by_subscriber': 'The underwriting is refused '
                'by the subscriber',
                'underwriting_denied': 'The underwriting is denied by '
                'the insurer',
                'postponed': 'The underwriting decision is postponed',
                })

    @fields.depends('decision', 'needs_subscriber_validation')
    def on_change_with_needs_subscriber_validation(self, name=''):
        if not self.decision:
            return False
        return self.decision.status == 'accepted_with_conditions'

    @fields.depends('decision')
    def on_change_with_decision_with_extra_data(self, name=''):
        if not self.decision:
            return False
        return self.decision.with_extra_data

    @fields.depends('underwriting_options', 'decision')
    def on_change_underwriting_options(self):
        self.possible_decisions = self.get_possible_decisions(
            self.underwriting_options)
        if len(self.possible_decisions) == 1:
            self.decision = self.possible_decisions[0]
        elif self.decision and self.decision not in self.possible_decisions:
            self.decision = None

    @fields.depends('decision')
    def on_change_with_hide_underwriting_options(self, name=None):
        return self.decision.status == 'accepted' if self.decision else False

    @fields.depends('decision')
    def on_change_decision(self):
        self.automatic_decision = False

    @staticmethod
    def default_subscriber_decision():
        return 'pending'

    def get_possible_decisions_id(self, name):
        return [d.id for d in self.get_possible_decisions(
                self.underwriting_options)]

    @classmethod
    def get_possible_decisions(cls, underwriting_options):
        # If all coverage decision have the same default contract decision
        contract_decisions = set(
            [list(x.decision.ordered_contract_decisions)[0].contract_decision
                for x in underwriting_options
                if getattr(x, 'decision', None)
                and x.decision.ordered_contract_decisions])
        if len(contract_decisions) == 1:
            return [list(contract_decisions)[0]]

        decisions = None
        for uw_option in underwriting_options:
            if not getattr(uw_option, 'decision', None):
                continue
            if not decisions:
                decisions = set(uw_option.decision.contract_decisions)
            elif uw_option.decision.contract_decisions:
                decisions = decisions.intersection(
                    uw_option.decision.contract_decisions)

        return list(decisions) if decisions is not None else []

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
            underwriting_options = list(
                getattr(instance, 'underwriting_options', []))
            existing_uw_options = dict([(x.option, x)
                    for x in underwriting_options])
            for option in [option for cov_element in
                instance.contract.covered_elements for option in [o for o
                    in cov_element.all_options
                    if o.coverage.underwriting_rules]]:
                option_data = existing_uw_options.get(option,
                    OptionUnderwriting(underwriting=instance, extra_data={},
                        option=option, automatic_decision=True))
                if (option_data.option.status != 'declined'
                        and option_data.automatic_decision
                        and option_data.calculate_rule_underwriting()):
                    # Automatic acceptation through rule
                    rule = option.coverage.get_underwriting_rule()
                    option_data.decision = rule.accepted_decision
                    option_data.automatic_decision = True
                elif (getattr(option_data, 'decision', None)
                        and option_data.decision.status == 'accepted'
                        and option_data.automatic_decision):
                    # Option was accepted, but the situation has changed
                    option_data.decision = None
                    option_data.automatic_decision = False
                if option_data.option not in existing_uw_options:
                    underwriting_options.append(option_data)

            for option_data in underwriting_options:
                option_data.update_extra_data()
            contract_decisions = cls.get_possible_decisions(
                underwriting_options)
            if len(contract_decisions) == 1 and all(
                    [getattr(option_data, 'decision', None)
                        for option_data in underwriting_options]):
                # Set automatic decision on contract underwriting if only
                # one possible value
                instance.decision = contract_decisions[0]
                instance.decision_date = utils.today()
                instance.automatic_decision = True
            elif (getattr(instance, 'decision', None)
                and instance.decision.status == 'accepted'
                and instance.automatic_decision
                and any([x.decision and x.decision.status != 'accepted'
                    or not x.check_decision_required()
                    for x in underwriting_options])):
                # Contract underwriting was previously accepted, but the
                # situation has changed
                instance.decision = None
                instance.decision_date = None
                instance.automatic_decision = False
            instance.underwriting_options = underwriting_options

    def check_decision(self):
        in_progress = False
        decision = self.decision
        if not decision:
            in_progress = True
        elif decision.status == 'postponed':
            self.raise_user_error('postponed')
        elif decision.status == 'pending':
            in_progress = True
        elif decision.status == 'denied':
            self.raise_user_error('underwriting_denied')
        elif decision.status == 'accepted_with_conditions':
            in_progress = (not self.subscriber_decision or
                self.subscriber_decision == 'pending')
            if not in_progress:
                if self.subscriber_decision == 'refused':
                    self.raise_user_error('refused_by_subscriber')
        if in_progress:
            self.raise_user_error('underwriting_still_in_progress')

    def init_dict_for_rule_engine(self, args):
        args['underwriting'] = self


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
    automatic_decision = fields.Boolean('Automatic Decision')
    decision = fields.Many2One('underwriting.decision',
        'Underwriting Decision', domain=[('level', '=', 'coverage'),
            If(Bool(Eval('possible_decisions')),
                ('id', 'in', Eval('possible_decisions')),
                ())],
        states={'invisible': ~Eval('possible_decisions')},
        depends=['possible_decisions'], ondelete='RESTRICT')
    possible_decisions = fields.Function(
        fields.Many2Many('underwriting.decision', None, None,
            'Possible Decisions'), 'on_change_with_possible_decisions')
    underwriting = fields.Many2One('contract.underwriting',
        'Underwriting', required=True, ondelete='CASCADE', select=True)
    contract = fields.Function(
        fields.Many2One('contract', 'Contract', states={'invisible': True}),
        'on_change_with_contract')

    @classmethod
    def _export_light(cls):
        return super(ContractUnderwritingOption, cls)._export_light() \
            | {'option'}

    @fields.depends('underwriting')
    def on_change_with_contract(self, name=None):
        return self.underwriting.contract.id

    @fields.depends('extra_data')
    def on_change_with_extra_data_summary(self, name=None):
        return Pool().get('extra_data').get_extra_data_summary([self],
            'extra_data').values()[0]

    @fields.depends('option')
    def on_change_with_possible_decisions(self, name=None):
        if not self.option:
            return []
        return [d.id for d in
            self.option.coverage.get_underwriting_rule().decisions]

    @fields.depends('decision')
    def on_change_decision(self):
        self.automatic_decision = False

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

    def calculate_rule_underwriting(self):
        args = {'date': self.option.start_date}
        self.init_dict_for_rule_engine(args)
        res = self.option.coverage.get_underwriting_rule().calculate(args)
        return res

    def init_dict_for_rule_engine(self, args):
        args['underwriting_option'] = self
        self.underwriting.init_dict_for_rule_engine(args)
        self.option.init_dict_for_rule_engine(args)
        args['extra_data'] = args.get('extra_data', {})
        args['extra_data'].update(self.extra_data)

    def check_decision_required(self):
        return (self.decision is not None
            or not self.option.coverage.get_underwriting_rule().decisions)


class Contract:
    __name__ = 'contract'

    underwritings = fields.One2Many('contract.underwriting',
        'contract', 'Underwritings', delete_missing=True,
        states=CONTRACT_STATES)

    @classmethod
    def view_attributes(cls):
        return super(Contract, cls).view_attributes() + [(
                '/form/notebook/page[@id="underwritings"]',
                'states',
                {'invisible': ~Eval('underwritings')}
                )]

    @classmethod
    def functional_skips_for_duplicate(cls):
        return (super(Contract, cls).functional_skips_for_duplicate() |
            set(['underwritings']))

    def check_underwriting_complete(self):
        if self.underwritings:
            self.underwritings[-1].check_decision()

    def update_underwritings(self):
        pool = Pool()
        ContractUnderwriting = pool.get('contract.underwriting')
        underwritings = self.underwritings
        if not underwritings:
            underwritings = [ContractUnderwriting(contract=self,
                extra_data={})]
        ContractUnderwriting.update_extra_data(underwritings)
        ContractUnderwriting.update_underwriting_options(underwritings)
        if underwritings[-1].underwriting_options:
            self.underwritings = underwritings
        else:
            self.underwritings = []
        self.save()

    def decline_options_after_underwriting(self):
        options_to_decline = []
        for underwriting in self.underwritings:
            for underwriting_option in underwriting.underwriting_options:
                if (not underwriting_option.decision
                        or not underwriting_option.decision.decline_option
                        or underwriting_option.option.status == 'declined'):
                    continue
                options_to_decline.append(underwriting_option.option)

        covered_elements = list(self.covered_elements)
        for covered_element in covered_elements:
            for option in list(covered_element.options):
                if option not in options_to_decline:
                    continue
                option.decline_option(None)
            covered_element.options = covered_element.options
        self.covered_elements = covered_elements
        self.save()
