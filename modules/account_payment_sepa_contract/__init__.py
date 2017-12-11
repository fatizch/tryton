# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond import backend
from trytond.pool import Pool

import contract
import invoice
import move
import payment
import event
import offered


def register():
    Pool.register(
        contract.Contract,
        contract.ContractBillingInformation,
        invoice.Invoice,
        move.MoveLine,
        payment.Mandate,
        payment.Payment,
        payment.Journal,
        payment.JournalFailureAction,
        payment.PaymentCreationStart,
        event.EventLog,
        payment.MergedPaymentsByContracts,
        offered.Product,
        module='account_payment_sepa_contract', type_='model')
    Pool.register_post_init_hooks(
        migrate_1_8_add_payer_from_mandate,
        module='contract_insurance_invoice')


def migrate_1_8_add_payer_from_mandate(pool, update):
    # Migrate from 1.8: Add payer
    # override behavior defined in contract_insurance_invoice
    # module to migrate payer from SEPA mandate
    if update != 'contract_insurance_invoice':
        return
    if pool.get('ir.module').search([('name', '=',
                    'account_payment_sepa_contract')])[0].state not in (
            'activated', 'to activate', 'to upgrade'):
        return

    from trytond.transaction import Transaction
    from trytond.modules.contract_insurance_invoice.contract import \
        ContractBillingInformation

    logging.getLogger('modules').info('Running post init hook %s' %
        'migrate_1_8_add_payer_from_mandate')
    previous_migrate = ContractBillingInformation._migrate_payer.im_func

    @classmethod
    def patched_migrate(cls):
        previous_migrate(cls)

        TableHandler = backend.get('TableHandler')
        billing_info = TableHandler(cls)
        if not billing_info.column_exist('sepa_mandate'):
            return

        cursor = Transaction().connection.cursor()
        Mandate = pool.get('account.payment.sepa.mandate')
        sepa_mandate = Mandate.__table__()
        contract_billing = pool.get('contract.billing_information').__table__()

        update_data = contract_billing.join(sepa_mandate, condition=(
                contract_billing.sepa_mandate == sepa_mandate.id)
            ).select(contract_billing.id.as_('billing_info'),
                sepa_mandate.party)

        cursor.execute(*contract_billing.update(
                columns=[contract_billing.payer],
                values=[update_data.party],
                from_=[update_data],
                where=(contract_billing.id == update_data.billing_info)))

    ContractBillingInformation._migrate_payer = patched_migrate
