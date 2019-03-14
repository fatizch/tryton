# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import event_log


def register():
    Pool.register(
        event_log.EventLog,
        module='event_log_party', type_='model')
    Pool.register(
        event_log.EndorsementEventLog,
        module='event_log_party', type_='model',
        depends=['endorsement'])
    Pool.register(
        event_log.PartyEndorsementEventLog,
        module='event_log_party', type_='model',
        depends=['endorsement_party'])
    Pool.register(
        event_log.ContractEventLog,
        module='event_log_party', type_='model',
        depends=['contract'])
    Pool.register(
        event_log.InvoiceEventLog,
        module='event_log_party', type_='model',
        depends=['contract_insurance_invoice'])
    Pool.register(
        event_log.PaymentEventLog,
        module='event_log_party', type_='model',
        depends=['contract_insurance_payment'])
    Pool.register(
        event_log.ContractSetEventLog,
        module='event_log_party', type_='model',
        depends=['contract_set'])
    Pool.register(
        event_log.RightSuspensionEventLog,
        module='event_log_party', type_='model',
        depends=['contract_insurance_suspension'])
