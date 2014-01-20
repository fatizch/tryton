from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'OptionSubscription',
    'OptionsDisplayer',
    ]


class OptionSubscription:
    'Option Subscription'

    __name__ = 'contract.wizard.option_subscription'

    def default_options_displayer(self, values):
        Contract = Pool().get('contract')
        contract = Contract(Transaction().context.get('active_id'))
        res = super(OptionSubscription, self).default_options_displayer(
            values)
        res['possible_covered_elements'] = [
            x.id for x in contract.covered_elements]
        if len(contract.covered_elements) == 1:
            res['covered_element'] = contract.covered_elements[0].id
        return res

    def subscribe_option(self, coverage):
        contract = self.options_displayer.contract
        options = [x for x in contract.options if x.offered == coverage]
        if len(options) == 1:
            option = options[0]
        else:
            option = super(OptionSubscription, self).subscribe_option(coverage)
            option.save()
            self.options_displayer.contract.save()
        cov_data = option.append_covered_data(
            self.options_displayer.covered_element)
        cov_data.save()
        return option

    def delete_options(self, options):
        Option = Pool().get('contract.option')
        CoveredData = Pool().get('contract.covered_data')
        cov_element = self.options_displayer.covered_element
        cov_data_to_del = []
        option_to_delete = []
        for option in options:
            cov_data_to_del.extend([x for x in option.covered_data
                    if x.covered_element == cov_element])
            option.covered_data = list(option.covered_data)
            option.covered_data[:] = [x for x in option.covered_data
                if not x in cov_data_to_del]
            if not len(option.covered_data):
                option_to_delete.append(option)
        CoveredData.delete(cov_data_to_del)
        if option_to_delete:
            Option.delete(option_to_delete)

    def transition_update_options(self):
        cov_element = self.options_displayer.covered_element
        to_delete = []
        to_subscribe = [x.coverage for x in self.options_displayer.options
            if x.is_selected]
        contract = self.options_displayer.contract
        if contract.options:
            contract.options = list(contract.options)
        for option in contract.options:
            if option.offered in to_subscribe:
                for cov_data in option.covered_data:
                    if cov_data.covered_element == cov_element:
                        to_subscribe.remove(option.offered)
            else:
                to_delete.append(option)
        for coverage in to_subscribe:
            self.subscribe_option(coverage)
        contract.options = list(contract.options)
        contract.options[:] = [x for x in contract.options
            if not x in to_delete]
        if to_delete:
            self.delete_options(to_delete)
        contract.init_extra_data()
        contract.save()
        return 'end'


class OptionsDisplayer:
    'Select Covered Element'

    __name__ = 'contract.wizard.option_subscription.options_displayer'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element',
        domain=[('id', 'in', Eval('possible_covered_elements'))],
        depends=['possible_covered_elements'], required=True)
    possible_covered_elements = fields.Many2Many(
        'contract.covered_element', None, None, 'Covered Elements',
        states={'invisible': True})
