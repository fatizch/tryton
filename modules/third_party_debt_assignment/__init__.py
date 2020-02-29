# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import dunning
from . import payment
from . import wizard
from . import offered
from . import report_engine


def register():
    Pool.register(
        payment.ThirdPartyDebtAssignmentRequest,
        payment.ThirdPartyDebtAssignmentRequestInvoice,
        offered.OptionDescription,
        wizard.DebtAssignmentCreateRequestsView,
        report_engine.ReportTemplate,
        module='third_party_debt_assignment', type_='model')
    Pool.register(
        dunning.Level,
        module='third_party_debt_assignment', type_='model',
        depends=['contract_insurance_invoice_dunning'])
    Pool.register(
        wizard.DebtAssignmentCreateRequests,
        wizard.DebtAssignmentRequestsChangeState,
        module='third_party_debt_assignment', type_='wizard')
