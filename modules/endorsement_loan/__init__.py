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
        EndorsementContractLoanField,
        EndorsementPart,
        Loan,
        LoanIncrement,
        LoanPayment,
        LoanShare,
        ExtraPremium,
        ContractLoan,
        Endorsement,
        EndorsementContract,
        EndorsementLoan,
        EndorsementCoveredElementOption,
        EndorsementLoanShare,
        EndorsementLoanIncrement,
        EndorsementContractLoan,
        ExtraPremiumDisplayer,
        NewExtraPremium,
        ManageExtraPremium,
        AddRemoveLoan,
        AddRemoveLoanDisplayer,
        ChangeLoanAtDate,
        ManageOptions,
        OptionDisplayer,
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
        module='endorsement_loan', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_loan', type_='wizard')
