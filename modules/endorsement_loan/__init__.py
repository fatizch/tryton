from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *


def register():
    Pool.register(
        EndorsementPart,
        EndorsementLoanField,
        Loan,
        LoanIncrement,
        LoanPayment,
        Endorsement,
        EndorsementLoan,
        LoanChangeBasicData,
        LoanDisplayUpdatedPayments,
        SelectEndorsement,
        PreviewLoanEndorsement,
        module='endorsement_loan', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_loan', type_='wizard')
