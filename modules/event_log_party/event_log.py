# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Cast, Null

from sql.operators import Concat

from trytond import backend
from trytond.config import config

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'EventLog',
    'EndorsementEventLog',
    'PartyEndorsementEventLog',
    'ContractEventLog',
    'InvoiceEventLog',
    'PaymentEventLog',
    'ContractSetEventLog',
    'RightSuspensionEventLog'
    ]

# The problem with so many dependent classes on the same base class, is that
# the registers will be executed one after the other. That means that EventLog
# register will be executed before the others and therefore the column party
# will already exist on the event_log table when we try to register depending
# classes. Therefore, we define a global variable to determine if we should
# migrate party or not, and that variable value is changed in EventLog register
# if at that moment party column does not exist. This is not very elegant but
# it is the only way I found to detect if a migration is necessary or not.
global _MIGRATE_PARTY
_MIGRATE_PARTY = False


class EventLog(metaclass=PoolMeta):
    __name__ = 'event.log'

    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
        select=True, readonly=True)

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        event_h = TableHandler(cls, module_name)
        if not event_h.column_exist('party') and \
                config.getboolean('env', 'testing') is not True:
            # Please check comment above for more info on the use of this
            # variable
            global _MIGRATE_PARTY
            _MIGRATE_PARTY = True
        super().__register__(module_name)

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if model_name == 'party.party' and object_.__name__ == 'party':
            return [object_]
        return super().get_related_instances(object_, model_name)

    @classmethod
    def get_event_keys(cls, objects):
        cur_dicts = super().get_event_keys(objects)
        for object_, log_dicts in list(cur_dicts.items()):
            parties = [x for x in
                cls.get_related_instances(object_, 'party.party') if x]
            if not parties:
                continue
            new_dicts = []
            for log_dict in log_dicts:
                for party in parties:
                    new_dict = log_dict.copy()
                    new_dict['party'] = party.id
                    new_dicts.append(new_dict)
            cur_dicts[object_] = new_dicts
        return cur_dicts


class EndorsementEventLog(metaclass=PoolMeta):
    __name__ = 'event.log'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        event_log = cls.__table__()
        to_update = cls.__table__()
        pool = Pool()

        super().__register__(module_name)

        # Set party field on contract endorsement event log
        if _MIGRATE_PARTY:
            contract_endorsement = pool.get('endorsement.contract').__table__()
            contract = pool.get('contract').__table__()
            update_data = contract_endorsement.join(event_log, condition=(
                    event_log.object_ == Concat('endorsement,',
                        Cast(contract_endorsement.endorsement,
                            'VARCHAR')))
                    ).join(contract, condition=(
                        contract_endorsement.contract == contract.id)
                    ).select(contract.subscriber.as_('party_id'),
                        event_log.id, where=((event_log.object_.like(
                            'endorsement,%'))
                            & (event_log.party == Null)))
            cursor.execute(*to_update.update(
                    columns=[to_update.party],
                    values=[update_data.party_id],
                    from_=[update_data],
                    where=update_data.id == to_update.id))

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if model_name == 'party.party' and object_.__name__ == 'endorsement':
            return [x.contract.subscriber
                for x in object_.contract_endorsements]
        return super().get_related_instances(object_, model_name)


class PartyEndorsementEventLog(metaclass=PoolMeta):
    __name__ = 'event.log'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        event_log = cls.__table__()
        to_update = cls.__table__()

        super().__register__(module_name)

        # Set party field on party endorsement event log
        if _MIGRATE_PARTY:
            party_endorsement = Pool().get('endorsement.party').__table__()
            update_data = party_endorsement.join(event_log, condition=(
                event_log.object_ == Concat('endorsement,',
                    Cast(party_endorsement.endorsement, 'VARCHAR')))
                    ).select(party_endorsement.party.as_('party_id'),
                        event_log.id,
                        where=((event_log.object_.like('endorsement,%'))
                            & (event_log.party == Null)))
            cursor.execute(*to_update.update(
                    columns=[to_update.party],
                    values=[update_data.party_id],
                    from_=[update_data],
                    where=update_data.id == to_update.id))

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if model_name == 'party.party' and object_.__name__ == 'endorsement':
            return [x.party for x in object_.party_endorsements]
        return super().get_related_instances(object_, model_name)


class ContractEventLog(metaclass=PoolMeta):
    __name__ = 'event.log'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        event_log = cls.__table__()
        to_update = cls.__table__()

        super().__register__(module_name)

        # Set party field on contract event logs
        if _MIGRATE_PARTY:
            contract = Pool().get('contract').__table__()
            update_data = contract.join(event_log, condition=(
                    event_log.object_ == Concat('contract,', Cast(contract.id,
                            'VARCHAR')))
                    ).select(contract.subscriber.as_('party_id'),
                        event_log.id,
                        where=((event_log.object_.like('contract,%'))
                            & (event_log.party == Null)))
            cursor.execute(*to_update.update(
                    columns=[to_update.party],
                    values=[update_data.party_id],
                    from_=[update_data],
                    where=update_data.id == to_update.id))

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if model_name == 'party.party' and object_.__name__ == 'contract':
            return [object_.subscriber]
        return super().get_related_instances(object_, model_name)


class InvoiceEventLog(metaclass=PoolMeta):
    __name__ = 'event.log'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        event_log = cls.__table__()
        to_update = cls.__table__()

        super().__register__(module_name)

        # Set party field on account.invoice event logs
        if _MIGRATE_PARTY:
            invoice = Pool().get('account.invoice').__table__()
            update_data = event_log.join(invoice, condition=(
                    Concat('account.invoice,', Cast(invoice.id,
                            'VARCHAR')) == event_log.object_)
                    ).select(invoice.party.as_('party_id'),
                        event_log.id, where=((event_log.object_.like(
                            'account.invoice,%'))
                            & (event_log.party == Null)))
            cursor.execute(*to_update.update(
                    columns=[to_update.party],
                    values=[update_data.party_id],
                    from_=[update_data],
                    where=update_data.id == to_update.id))

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if (model_name == 'party.party'
                and object_.__name__ == 'account.invoice'):
            return [object_.party]
        return super().get_related_instances(object_, model_name)


class PaymentEventLog(metaclass=PoolMeta):
    __name__ = 'event.log'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        event_log = cls.__table__()
        to_update = cls.__table__()

        super().__register__(module_name)

        # Set party field on account.payment event logs
        if _MIGRATE_PARTY:
            payment = Pool().get('account.payment').__table__()
            update_data = event_log.join(payment, condition=(
                    Concat('account.payment,', Cast(payment.id,
                            'VARCHAR')) == event_log.object_)
                    ).select(payment.party.as_('party_id'),
                    event_log.id, where=((event_log.object_.like(
                            'account.payment,%'))
                            & (event_log.party == Null)))
            cursor.execute(*to_update.update(
                    columns=[to_update.party],
                    values=[update_data.party_id],
                    from_=[update_data],
                    where=update_data.id == to_update.id))

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if (model_name == 'party.party'
                and object_.__name__ == 'account.payment'):
            return [object_.party] if object_.party else []
        return super().get_related_instances(object_, model_name)


class ContractSetEventLog(metaclass=PoolMeta):
    __name__ = 'event.log'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        event_log = cls.__table__()
        to_update = cls.__table__()

        super().__register__(module_name)

        # Set party on contract.set event logs
        if _MIGRATE_PARTY:
            contract = Pool().get('contract').__table__()
            update_data = event_log.join(contract, condition=(
                    Concat('contract.set,', Cast(contract.contract_set,
                            'VARCHAR')) == event_log.object_)
                    ).select(contract.subscriber.as_('party_id'), event_log.id,
                        where=((event_log.object_.like('contract.set,%'))
                            & (event_log.party == Null)))
            cursor.execute(*to_update.update(
                    columns=[to_update.party],
                    values=[update_data.party_id],
                    from_=[update_data],
                    where=update_data.id == to_update.id))

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if (model_name == 'party.party'
                and object_.__name__ == 'contract.set'):
            return list(set([x.subscriber for x in object_.contracts]))
        return super().get_related_instances(object_, model_name)


class RightSuspensionEventLog(metaclass=PoolMeta):
    __name__ = 'event.log'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        event_log = cls.__table__()
        to_update = cls.__table__()

        super().__register__(module_name)
        # Set party on contract right suspensions
        if _MIGRATE_PARTY:
            pool = Pool()
            contract = pool.get('contract').__table__()
            right_suspension = pool.get('contract.right_suspension').__table__()
            update_data = event_log.join(right_suspension, condition=(
                    Concat('contract.right_suspension,',
                        Cast(right_suspension.id, 'VARCHAR')
                        ) == event_log.object_)
                    ).join(contract, condition=(
                            right_suspension.contract == contract.id)
                    ).select(contract.subscriber.as_('party_id'), event_log.id,
                        where=((event_log.object_.like(
                            'contract.right_suspension,%'))
                            & (event_log.party == Null)))
            cursor.execute(*to_update.update(
                    columns=[to_update.party],
                    values=[update_data.party_id],
                    from_=[update_data],
                    where=update_data.id == to_update.id))

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if (model_name == 'party.party'
                and object_.__name__ == 'contract.right_suspension'):
            return [object_.contract.subscriber]
        return super().get_related_instances(object_, model_name)
