# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

from trytond.modules.coog_core import utils


class Event(metaclass=PoolMeta):
    __name__ = 'event'

    @classmethod
    def notify_events(cls, objects, event_code, description=None, **kwargs):
        pool = Pool()
        Date = pool.get('ir.date')
        Protocol = pool.get('third_party_manager.protocol')
        ThirdPartyPeriod = pool.get('contract.option.third_party_period')

        has_dunning = False
        if utils.is_module_installed('account_dunning_cog'):
            Dunning = pool.get('account.dunning')
            has_dunning = True

        periods_to_remove, modified_periods = [], []
        if objects and has_dunning and isinstance(objects[0], Dunning):
            method = getattr(Protocol, 'do_' + event_code, None)
            if method is not None:
                for dunning in objects:
                    contract = dunning.line.contract
                    removed, modified = method(
                        contract, dunning, Date.today(), **kwargs)
                    periods_to_remove.extend(removed)
                    modified_periods.extend(modified)
        elif event_code in {
                'activate_contract', 'hold_contract', 'unhold_contract',
                'void_contract', 'renew_contract', 'first_invoice_payment',
                'terminate_contract', 'plan_contract_termination'}:
            protocol_method = getattr(Protocol, 'do_' + event_code)
            for contract in objects:
                removed, modified = protocol_method(
                    contract, contract, **kwargs)
                periods_to_remove.extend(removed)
                modified_periods.extend(modified)
        elif event_code == 'apply_endorsement':
            for endorsement in objects:
                for contract_endorsement in endorsement.contract_endorsements:
                    if contract_endorsement.state != 'applied':
                        continue
                    removed, modified = Protocol.do_apply_endorsement(
                        contract_endorsement.contract, endorsement, **kwargs)
                    periods_to_remove.extend(removed)
                    modified_periods.extend(modified)

        if periods_to_remove or modified_periods:
            ThirdPartyPeriod.delete(periods_to_remove)
            # Save first the modified periods then the new ones to prevent the
            # case where the new ones could overlap with the modified ones
            ThirdPartyPeriod.save(
                [p for p in modified_periods if p.id is not None])
            ThirdPartyPeriod.save([p for p in modified_periods if p.id is None])

        super().notify_events(objects, event_code, description, **kwargs)
