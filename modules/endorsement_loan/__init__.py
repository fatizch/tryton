# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import endorsement
import offered
import wizard


def register():
    Pool.register(
        offered.EndorsementDefinition,
        offered.EndorsementLoanField,
        offered.EndorsementLoanShareField,
        offered.EndorsementLoanIncrementField,
        offered.EndorsementContractLoanField,
        offered.EndorsementPart,
        endorsement.Loan,
        endorsement.LoanIncrement,
        endorsement.LoanPayment,
        endorsement.LoanShare,
        endorsement.ExtraPremium,
        endorsement.ContractLoan,
        endorsement.Endorsement,
        endorsement.EndorsementContract,
        endorsement.EndorsementLoan,
        endorsement.EndorsementCoveredElementOption,
        endorsement.EndorsementLoanShare,
        endorsement.EndorsementLoanIncrement,
        endorsement.EndorsementContractLoan,
        wizard.ExtraPremiumDisplayer,
        wizard.NewExtraPremium,
        wizard.ManageExtraPremium,
        wizard.AddRemoveLoan,
        wizard.AddRemoveLoanDisplayer,
        wizard.ChangeLoanAtDate,
        wizard.ManageOptions,
        wizard.OptionDisplayer,
        wizard.ChangeLoanDisplayer,
        wizard.ChangeLoan,
        wizard.ChangeLoanUpdatedPayments,
        wizard.LoanDisplayUpdatedPayments,
        wizard.LoanSelectContracts,
        wizard.LoanContractDisplayer,
        wizard.SelectLoanShares,
        wizard.LoanShareSelector,
        wizard.SharePerLoan,
        wizard.SelectEndorsement,
        wizard.PreviewLoanEndorsement,
        wizard.PreviewContractPayments,
        wizard.ContractPreview,
        module='endorsement_loan', type_='model')

    Pool.register(
        wizard.StartEndorsement,
        module='endorsement_loan', type_='wizard')
