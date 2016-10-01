# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.rpc import RPC
from trytond.pyson import Eval, Or, Bool
from trytond.transaction import Transaction
from trytond.modules.coog_core import fields

from trytond.modules.process import ClassAttr
from trytond.modules.process_cog import CoogProcessFramework

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    ]


class Contract(CoogProcessFramework):
    __name__ = 'contract'
    __metaclass__ = ClassAttr

    product_desc = fields.Function(
        fields.Text('Description', readonly=True),
        'on_change_with_product_desc', 'setter_void', )
    subscriber_desc = fields.Function(
        fields.Text('Summary', readonly=True),
        'on_change_with_subscriber_desc', 'setter_void', )

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._error_messages.update({
                'no_option': 'At least an option must be selected',
                'bad_start_date': 'Option %s must be subscribed after %s',
                'need_option': 'At least one option must be selected for %s',
                'need_covered': 'There must be at least one covered element',
                'no_subscriber_address': 'The selected subscriber does not '
                'have an address',
                })
        cls.__rpc__.update({'get_allowed_payment_methods': RPC(instantiate=0)})
        cls._buttons['button_activate']['invisible'] = Or(
            cls._buttons['button_activate']['invisible'],
            Bool(Eval('current_state', False)))

    @classmethod
    def copy(cls, contracts, default=None):
        clones = super(Contract, cls).copy(contracts, default)
        if Transaction().context.get('copy_mode', 'functional') != \
                'functional':
            return clones
        Process = Pool().get('process')
        products = set([x.product for x in clones])
        processes = Process.search([
                ('for_products', 'in', [x.id for x in products]),
                ('kind', '=', 'subscription'),
                ])
        for clone in clones:
            process = [x for x in processes if clone.product in x.for_products]
            if process:
                clone.current_state = process[0].all_steps[0]
                clone.save()
        return clones

    def get_task_name(self, name):
        names = []
        if self.product:
            names.append(self.product.rec_name)
        if self.subscriber:
            names.append(self.subscriber.rec_name)
        if not names:
            return super(Contract, self).get_task_name(name)
        return ' - '.join(names)

    @fields.depends('product')
    def on_change_with_product_desc(self, name=None):
        return self.product.description if self.product else ''

    @fields.depends('subscriber')
    def on_change_with_subscriber_desc(self, name=None):
        return self.subscriber.summary if self.subscriber else ''

    def on_change_subscriber_kind(self):
        super(Contract, self).on_change_subscriber_kind()
        self.subscriber_desc = ''

    def check_subscriber_address(self):
        if not self.subscriber:
            return False, (('no_subscriber', ()),)
        if not self.subscriber.addresses:
            return False, (('no_subscriber_address', ()),)
        return True, ()

    def check_option_selected(self):
        for option in self.options:
            if option.status == 'active':
                return True, ()
        return False, (('no_option', ()),)

    def check_option_dates(self):
        result = True
        for option in self.options:
            if option.start_date < self.start_date:
                result = False
                self.append_functional_error('bad_start_date', (
                        option.coverage.code, self.start_date))
            elif option.start_date < option.coverage.start_date:
                result = False
                self.append_functional_error('bad_start_date', (
                        option.coverage.code, option.coverage.start_date))
        return result

    @classmethod
    def subscribe_contract(cls, *args, **kwargs):
        # Set running process to None to avoid associating the new contract to
        # a process
        with Transaction().set_context(running_process=None):
            result = super(Contract, cls).subscribe_contract(*args, **kwargs)
            result.save()
            return result

    def init_first_covered_elements(self):
        pool = Pool()
        Covered = pool.get('contract.covered_element')
        if self.covered_elements:
            return
        covered = Covered(contract=self)
        if len(self.possible_item_desc) == 1:
            with Transaction().set_context(start_date=self.start_date):
                covered.init_covered_element(self.product,
                    self.possible_item_desc[0], {})
        self.covered_elements = [covered]
        self.save()


class ContractOption:
    __name__ = 'contract.option'

    status_selection = fields.Function(
        fields.Boolean('Status'),
        'on_change_with_status_selection', 'setter_void')

    @classmethod
    def default_status_selection(cls):
        return True

    @fields.depends('status_selection', 'status')
    def on_change_status_selection(self):
        self.status = 'active' if self.status_selection else 'refused'

    @fields.depends('status')
    def on_change_with_status_selection(self, name=None):
        return self.status and self.status == 'active'
