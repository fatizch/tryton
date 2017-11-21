# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
from dateutil.relativedelta import relativedelta

from trytond.pool import PoolMeta, Pool
from trytond.server_context import ServerContext
from trytond.pyson import Eval, Bool

from trytond.modules.coog_core import utils, model, fields, coog_string

__all__ = [
    'Contract',
    'ContractRightSuspension',
    ]


SUSPENSION_STATES = {
    'readonly': Bool(Eval('active')) & (Eval('type_') == 'definitive'),
    }


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    actives_rights_suspensions = fields.One2Many('contract.right_suspension',
        'contract', 'Actives Rights Suspensions', delete_missing=True)

    @classmethod
    def calculate_suspensions_from_date(cls, contracts):
        return {c: ServerContext().get('suspension_start_date', utils.today())
            for c in contracts}

    @classmethod
    def hold(cls, contracts, hold_reason):
        super(Contract, cls).hold(contracts, hold_reason)
        pool = Pool()
        Event = pool.get('event')
        ContractRightSuspension = pool.get('contract.right_suspension')
        suspensions = []
        contracts_to_suspend = [x for x in contracts if
            x.right_suspension_allowed()]
        contracts_suspensions_from_date = cls.calculate_suspensions_from_date(
            contracts_to_suspend)
        for contract in contracts_to_suspend:
            from_date = contracts_suspensions_from_date[contract]
            suspensions.append(contract.get_suspension('definitive',
                    from_date))
        if suspensions:
            ContractRightSuspension.save(suspensions)
            Event.notify_events(suspensions,
                'contract_right_suspension_creation')

    def right_suspension_allowed(self):
        return True

    def disable_right_suspensions(self, type_=None, to_date=None,
            days_delta=1):
        pool = Pool()
        ContractRightSuspension = pool.get('contract.right_suspension')
        Event = pool.get('event')
        to_date = to_date or ServerContext().get('suspension_end_date',
            utils.today() + relativedelta(days=days_delta))
        search_clause = [
            ('start_date', '<=', to_date),
            ('end_date', '=', None),
            ('contract', '=', self.id),
            ]
        if type_:
            search_clause.append(('type_', '=', type_)),
        suspensions_to_disable = ContractRightSuspension.search(search_clause)
        if suspensions_to_disable:
            due_invoices = sorted([x for x in self.due_invoices if x.end],
                key=lambda x: x.end)
            to_write = []
            temporary_suspensions = [x for x in suspensions_to_disable if
                x.type_ == 'temporary']
            definitive_suspensions = [x for x in suspensions_to_disable if
                x.type_ == 'definitive']
            if temporary_suspensions:
                to_write.extend([temporary_suspensions,
                    {'end_date': utils.today() + relativedelta(days=days_delta)
                        if not due_invoices
                        else to_date, 'active': False}])
                Event.notify_events(temporary_suspensions,
                    'contract_disable_temporary_right_suspension')
                if due_invoices:
                    suspension = self.get_suspension('temporary', to_date +
                        relativedelta(days=1))
                    suspension.save()
            if definitive_suspensions:
                to_write.extend([definitive_suspensions,
                    {'end_date': to_date}])
                Event.notify_events(definitive_suspensions,
                    'contract_disable_right_suspension')
            ContractRightSuspension.write(*to_write)

    @classmethod
    def reactivate(cls, contracts):
        for contract in contracts:
            if (contract.status == 'hold'
                    and contract.right_suspension_allowed()):
                contract.disable_right_suspensions()
        super(Contract, cls).reactivate(contracts)

    def reactivate_through_endorsement(self, caller=None):
        ContractEndorsement = Pool().get('endorsement.contract')
        if isinstance(caller, ContractEndorsement):
            with ServerContext().set_context(
                    suspension_end_date=caller.endorsement.effective_date):
                return super(Contract, self
                    ).reactivate_through_endorsement(caller)
        super(Contract, self).reactivate_through_endorsement(caller)

    def activate_contract(self):
        if self.status == 'hold' and self.right_suspension_allowed():
            self.disable_right_suspensions()
        super(Contract, self).activate_contract()

    def get_suspension(self, type_, start_date, end_date=None, active=True):
        ContractRightSuspension = Pool().get('contract.right_suspension')
        return ContractRightSuspension(contract=self.id, type_=type_,
            start_date=start_date, end_date=end_date, active=active)


class ContractRightSuspension(model.CoogSQL, model.CoogView):
    'Contract Right Suspension'

    __name__ = 'contract.right_suspension'
    _func_key = 'id'

    contract = fields.Many2One('contract', 'Contract',
        states=SUSPENSION_STATES, depends=['active', 'type_'],
        ondelete='CASCADE', select=True, required=True)
    start_date = fields.Date('Start Date', states=SUSPENSION_STATES,
        depends=['active', 'type_'])
    end_date = fields.Date('End Date', states=SUSPENSION_STATES,
        depends=['active', 'type_'])
    type_ = fields.Selection([
            ('definitive', 'Definitive'),
            ('temporary', 'Temporary')],
        'Suspension Type', states=SUSPENSION_STATES,
        depends=['active', 'type_'], required=True)
    type_string = type_.translated('type_')
    active = fields.Boolean('Active', states=SUSPENSION_STATES,
        depends=['active', 'type_'])

    @classmethod
    def __setup__(cls):
        super(ContractRightSuspension, cls).__setup__()
        cls._error_messages.update({
                'invalid_dates': 'Start date greater than end date (%s > %s)',
                })
        cls._buttons.update({
            'button_activate': {'invisible': Bool(Eval('active'))},
                })

    @staticmethod
    def default_active():
        return False

    @classmethod
    @model.CoogView.button
    def button_activate(cls, suspensions):
        cls.write(suspensions, {'active': True})

    @classmethod
    def validate(cls, records):
        super(ContractRightSuspension, cls).validate(records)
        with model.error_manager():
            for record in records:
                if record.start_date > (record.end_date or datetime.date.max):
                    cls.append_functional_error('invalid_dates',
                        (record.start_date, record.end_date))

    @classmethod
    def _export_light(cls):
        return (super(ContractRightSuspension, cls)._export_light() |
            set(['contract']))

    def get_rec_name(self, name):
        return '(%s) %s: [%s - %s]' % (
            self.type_string, self.contract.contract_number,
            coog_string.translate_value(self, 'start_date'),
            coog_string.translate_value(self, 'end_date')
            if self.end_date else '')
