from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *


def register():
    Pool.register(
        EndorsementDefinition,
        EndorsementPart,
        EndorsementLoanField,
        EndorsementLoanShareField,
        Loan,
        LoanIncrement,
        LoanPayment,
        LoanShare,
        PremiumAmount,
        Endorsement,
        EndorsementContract,
        EndorsementLoan,
        EndorsementCoveredElementOption,
        EndorsementLoanShare,
        LoanChangeBasicData,
        LoanDisplayUpdatedPayments,
        LoanSelectContracts,
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
