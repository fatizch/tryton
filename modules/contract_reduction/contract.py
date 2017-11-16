# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.server_context import ServerContext

from trytond.modules.coog_core import model, fields, utils

__all__ = [
    'Contract',
    'Option',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    reduction_date = fields.Date('Reduction Date', states={
            'invisible': ~Eval('reduction_date')}, readonly=True,
        help='The date at which the contract was reduced')
    can_reduce = fields.Function(
        fields.Boolean('Can be reduced'),
        'getter_can_reduce')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'button_reduce': {
                    'readonly': ~Eval('can_reduce', False)},
                })
        cls._error_messages.update({
                'will_reduce': 'Contracts will be reduced',
                'cannot_reduce': 'Contract %(contract)s cannot be '
                'reduced',
                'no_reductionable_options': 'No options were found that can '
                'be reduced for contract %(contract)s',
                'auto_reducing': 'Contracts will automatically be reduced',
                'cannot_reduce_surrendered': 'A contract that was surrendered '
                'cannot be reduced',
                })

    def get_icon(self, name=None):
        if self.reduction_date and self.status != 'terminated':
            return 'contract_reduced'
        return super(Contract, self).get_icon(name)

    def getter_can_reduce(self, name):
        if self.status in ('void', 'quote', 'terminated'):
            return False
        if self.reduction_date:
            return False
        if all(not x.reduction_rules for x in self.product.coverages):
            return False
        if utils.is_module_installed('contract_surrender'):
            if self.surrender_invoice:
                return False
        return True

    @classmethod
    @model.CoogView.button_action('contract_reduction.act_reduce_contract')
    def button_reduce(cls, contracts):
        pass

    @classmethod
    def reduce(cls, contracts, reduction_date):
        cls.do_reduce(contracts, reduction_date)

    @classmethod
    def do_reduce(cls, contracts, reduction_date):
        Event = Pool().get('event')
        cls.raise_user_warning('will_reduce_%s' % str([x.id for x in
                    contracts[:10]]), 'will_reduce')
        with model.error_manager():
            cls.check_for_reduction(contracts, reduction_date)
        for contract in contracts:
            contract.apply_reduction(reduction_date)
        cls.save(contracts)
        Event.notify_events(contracts, 'contract_reduction')

    @classmethod
    def check_for_reduction(cls, contracts, reduction_date,
            for_termination=False):
        for contract in contracts:
            if utils.is_module_installed('contract_surrender'):
                if contract.surrender_invoice:
                    contract.append_functional_error(
                        'cannot_reduce_surrendered')
            if not contract.can_reduce:
                contract.append_functional_error('cannot_reduce',
                    {'contract': contract.rec_name})
            options = [x for x in (contract.options +
                    contract.covered_element_options)
                if x.reduction_allowed(reduction_date)]
            if not options:
                contract.append_functional_error(
                    'no_reductionable_options', {
                        'contract': contract.rec_name})

    def apply_reduction(self, reduction_date):
        self.reduction_date = reduction_date
        for option in self.options:
            option.reduce(reduction_date)
        self.options = list(self.options)
        for covered_element in self.covered_elements:
            for option in covered_element.options:
                option.reduce(reduction_date)
            covered_element.options = list(covered_element.options)
        self.covered_elements = list(self.covered_elements)

    def calculate_reductions(self, reduction_date):
        reductions = []
        options = [x for x in (self.options + self.covered_element_options)
            if x.reduction_allowed(reduction_date)]
        for option in options:
            reductions.append(
                (option, option.calculate_reduction(reduction_date)))
        return reductions

    def get_invoice_periods(self, up_to_date, from_date=None):
        if self.reduction_date:
            up_to_date = min(up_to_date or datetime.date.max,
                self.reduction_date)
        return super(Contract, self).get_invoice_periods(up_to_date, from_date)

    @classmethod
    def terminate(cls, contracts, at_date, termination_reason):
        to_reduce, to_terminate = [], []
        for contract in contracts:
            if contract.auto_reduce(at_date):
                to_reduce.append(contract)
            else:
                to_terminate.append(contract)
        if to_reduce:
            # When reducing, contracts should not be terminated
            cls.raise_user_warning('auto_reducing_%s' % ','.join(
                    [str(x.id) for x in to_reduce]), 'auto_reducing')
            Contract.reduce(to_reduce, at_date)
        if to_terminate:
            super(Contract, cls).terminate(to_terminate, at_date,
                termination_reason)

    def auto_reduce(self, at_date):
        if self.reduction_date:
            return False
        with model.error_manager():
            self.check_for_reduction([self], at_date)
            manager = ServerContext().get('error_manager')
            result = not manager.has_errors
            manager.clear_errors()
        return result


class Option:
    __metaclass__ = PoolMeta
    __name__ = 'contract.option'

    def reduction_allowed(self, reduction_date):
        if not self.parent_contract.can_reduce:
            return False
        if not self.is_active_at_date(reduction_date):
            return False
        if not self.coverage.reduction_rules:
            return False
        reduction_rule = self.coverage.reduction_rules[0]
        if reduction_rule.eligibility_rule:
            data_dict = {}
            data_dict['date'] = reduction_date
            self.init_dict_for_rule_engine(data_dict)
            return reduction_rule.calculate_eligibility_rule(
                data_dict, raise_errors=True)
        return True

    def reduce(self, reduction_date):
        SubStatus = Pool().get('contract.sub_status')
        reduce_status = SubStatus.get_sub_status('contract_reduced')
        if not self.reduction_allowed(reduction_date):
            self.manual_end_date = reduction_date
            self.sub_status = reduce_status

    def calculate_reduction(self, reduction_date):
        data_dict = {}
        data_dict['date'] = reduction_date
        self.init_dict_for_rule_engine(data_dict)
        return self.coverage.reduction_rules[0].calculate_rule(data_dict)
