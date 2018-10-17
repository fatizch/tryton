# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.wizard import StateView, Button, StateTransition
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, fields


__all__ = [
    'PrepaymentSyncShowRedeemedInconsistency',
    'PrepaymentSyncShowDisplayer',
    'PrepaymentSyncResult',
    'PrepaymentSyncShow',
    'PrepaymentSync',
    'SimulateCommissionsParameters',
    'SimulateCommissionsLine',
    ]


class PrepaymentSyncShowRedeemedInconsistency(model.CoogView):
    'Prepayment Sync Show Reedemed Inconsistency'
    __name__ = 'prepayment.sync.show.redeemed'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    agent = fields.Many2One('commission.agent', 'Agent', readonly=True)
    commissions = fields.Many2Many('commission', None, None, 'Commissions',
        readonly=True)
    consistency = fields.Integer('Consistency', readonly=True)
    line = fields.Many2One('account.invoice.line', 'Line', readonly=True)
    start = fields.Date('Start', readonly=True)
    end = fields.Date('End', readonly=True)
    description = fields.Text('Description', readonly=True)
    code = fields.Text('Codes', readonly=True)

    def as_dict(self):
        return {
            'contract': self.contract.id,
            'agent': self.agent.id,
            'commissions': [x.id for x in self.commissions],
            'consistency': self.consistency,
            'line': self.line.id,
            'start': self.start,
            'end': self.end,
            'description': self.description,
            'code': self.code,
            }


class PrepaymentSyncShowDisplayer(model.CoogView):
    'Prepayment Sync Show Displayer'
    __name__ = 'prepayment.sync.show.displayer'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    party = fields.Many2One('party.party', 'Party', readonly=True)
    agent = fields.Many2One('commission.agent', 'Agent', readonly=True)
    paid_amount = fields.Numeric('Amount Attached To An Invoice',
        digits=(16, 2), readonly=True)
    generated_amount = fields.Numeric('Remaining Amount',
        digits=(16, 2), readonly=True)
    actual_amount = fields.Numeric('Total Amount',
        digits=(16, 2), readonly=True)
    theoretical_amount = fields.Numeric('Recalculated Amount',
        digits=(16, 2), readonly=True)
    theoretical_amount_today = fields.Numeric('Real Recalculated Amount Based',
        digits=(16, 2), readonly=True)
    deviation_amount = fields.Numeric('Deviation Amount',
        digits=(16, 2), readonly=True)
    number_of_date = fields.Integer('Number Of Date(s)', readonly=True)
    dates = fields.Char('Date(s)', readonly=True)
    description = fields.Text('Description', readonly=True)
    codes = fields.Text('Codes', readonly=True)
    commissions = fields.Many2Many('commission', None, None, 'Commissions',
        readonly=True)

    def as_dict(self):
        return {
            'contract': self.contract.id,
            'party': self.party.id,
            'agent': self.agent.id,
            'paid_amount': self.paid_amount,
            'generated_amount': self.generated_amount,
            'actual_amount': self.actual_amount,
            'theoretical_amount': self.theoretical_amount,
            'theoretical_amount_today': self.theoretical_amount_today,
            'deviation_amount': self.deviation_amount,
            'number_of_date': self.number_of_date,
            'dates': self.dates,
            'description': self.description,
            'codes': self.codes,
            'commissions': [x.id for x in self.commissions],
            }


class PrepaymentSyncResult(model.CoogView):
    'Prepayment Sync Result'
    __name__ = 'prepayment.sync.show_result'

    adjusted = fields.One2Many('prepayment.sync.show.displayer',
        None, 'Adjusted')
    non_adjusted = fields.One2Many('prepayment.sync.show.displayer',
        None, 'Non Adjusted')


class PrepaymentSyncShow(model.CoogView):
    'Prepayment Sync Show'
    __name__ = 'prepayment.sync.show_prepayment'

    commissions = fields.One2Many('prepayment.sync.show.displayer',
        None, 'Commissions', readonly=True)
    inconsistencies = fields.One2Many('prepayment.sync.show.redeemed',
        None, 'Inconsistencies', readonly=True)


class PrepaymentSync(model.CoogWizard):
    'Prepayment Sync'
    __name__ = 'prepayment.sync'

    start = StateTransition()
    prepayment_view = StateView('prepayment.sync.show_prepayment',
        'commission_insurance_prepayment.prepayment_sync_show_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Synchronize', 'synchronize', 'tryton-next', default=True),
            ])
    synchronize = StateTransition()
    result = StateView('prepayment.sync.show_result',
        'commission_insurance_prepayment.prepayment_sync_result_view_form', [
            Button('End', 'end', 'tryton-ok', default=True),
            ])

    def transition_start(self):
        active_id = Transaction().context.get('active_id')
        model = Transaction().context.get('active_model')
        assert model == 'contract'
        Contract = Pool().get('contract')
        contract = Contract(active_id)
        deviations = Contract.get_prepayment_deviations([contract])[contract]
        Contract._add_prepayment_deviations_description(deviations)
        for deviation in deviations:
            deviation['dates'] = ', '.join(deviation['dates'])
        self.prepayment_view.commissions = deviations
        inconsistencies = contract.check_for_redeemned_inconsistencies(
            deviations)
        self.prepayment_view.inconsistencies = inconsistencies
        return 'prepayment_view'

    def default_prepayment_view(self, values):
        return {
            'commissions': [x.as_dict()
                for x in self.prepayment_view.commissions],
            'inconsistencies': [x.as_dict()
                for x in self.prepayment_view.inconsistencies],
            }

    def transition_synchronize(self):
        deviations = [x.as_dict() for x in self.prepayment_view.commissions]
        pool = Pool()
        Contract = pool.get('contract')
        Commission = pool.get('commission')
        for deviation in deviations:
            deviation['codes'] = [{'code': x, 'description': desc or ''}
                for x, desc in zip(
                    deviation['codes'].split('\n'),
                    deviation['description'].split('\n'))]
            deviation['contract'] = Contract(deviation['contract'])
            deviation['commissions'] = tuple(Commission.browse(
                    deviation['commissions']))
        adjusted, non_adjusted, _ = Pool().get('contract'
            ).try_adjust_prepayments(deviations)
        Contract = Pool().get('contract')
        Contract._add_prepayment_deviations_description(adjusted)
        Contract._add_prepayment_deviations_description(non_adjusted)
        inconsistencies = [x.as_dict()
            for x in self.prepayment_view.inconsistencies]
        for obj in inconsistencies:
            obj['commissions'] = tuple(Commission.browse(obj['commissions']))
        Contract.resolve_redeemed_inconsistencies(inconsistencies)
        self.result.adjusted = adjusted
        self.result.non_adjusted = non_adjusted
        return 'result'

    def default_result(self, values):
        return {
            'adjusted': [x.as_dict() for x in self.result.adjusted],
            'non_adjusted': [x.as_dict() for x in self.result.non_adjusted],
            }


class SimulateCommissionsParameters:
    __metaclass__ = PoolMeta
    __name__ = 'commission.simulate.params'

    def add_commissions(self, line, invoice, contract):
        commissions = super(SimulateCommissionsParameters,
            self).add_commissions(line, invoice, contract)
        if contract.with_prepayment:
            for commission in line.get_option(contract).compute_prepayment(
                    False, contract.start_date, contract.end_date):
                commission.redeemed_prepayment = None
                commission.base_amount = commission.get_base_amount(None)
                if (not commission.date
                        or commission.date >= self.invoice_date):
                    commissions.append(commission)
        return commissions

    def mock_contract(self, product):
        contract = super(SimulateCommissionsParameters, self).mock_contract(
            product)
        contract.has_prepayment = contract.getter_has_prepayment(None)
        return contract

    def mock_option(self, coverage, parent_contract, contract=None,
            covered=None):
        option = super(SimulateCommissionsParameters, self).mock_option(
            coverage, parent_contract, contract, covered)
        if not parent_contract.getter_has_prepayment(None):
            return option
        premium_rule, = [r for r in coverage.premium_rules
            if r.match(coverage.get_match_rule(option))]
        option.first_year_premium = option.get_first_year_premium(None)
        option.monthly_premium_incl_tax = None
        option.monthly_premium_excl_tax = None
        return option

    def new_line(self, parent, commission, currency):
        if commission.agent.plan.is_prepayment and not getattr(commission,
                'is_prepayment', False):
            return None
        return super(SimulateCommissionsParameters, self).new_line(parent,
            commission, currency)


class SimulateCommissionsLine:
    __metaclass__ = PoolMeta
    __name__ = 'commission.simulate.line'

    is_prepayment = fields.Boolean('Prepayment', readonly=True)

    def init_from_commission(self, commission):
        self.is_prepayment = getattr(commission, 'is_prepayment', False)
        commission.redeemed_prepayment = None
        super(SimulateCommissionsLine, self).init_from_commission(commission)
