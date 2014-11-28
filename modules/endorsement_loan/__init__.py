from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *


def register():
    Pool.register(
        EndorsementDefinition,
        EndorsementLoanField,
        EndorsementLoanShareField,
        EndorsementLoanIncrementField,
        EndorsementPart,
        Contract,
        Loan,
        LoanIncrement,
        LoanPayment,
        LoanShare,
        PremiumAmount,
        ExtraPremium,
        Endorsement,
        EndorsementContract,
        EndorsementLoan,
        EndorsementCoveredElementOption,
        EndorsementLoanShare,
        EndorsementLoanIncrement,
        ExtraPremiumDisplayer,
        NewExtraPremium,
        ManageExtraPremium,
        ChangeLoanDisplayer,
        ChangeLoan,
        ChangeLoanUpdatedPayments,
        LoanDisplayUpdatedPayments,
        LoanSelectContracts,
        LoanContractDisplayer,
        SelectLoanShares,
        LoanShareSelector,
        SharePerLoan,
        SelectEndorsement,
        PreviewLoanEndorsement,
        PreviewContractPayments,
        ContractPreview,
        ContractPreviewPayment,
        module='endorsement_loan', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_loan', type_='wizard')
