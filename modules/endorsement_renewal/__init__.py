# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import wizard
import contract


def register():
    Pool.register(
        wizard.ContractRenew,
        contract.Contract,
        module='endorsement_renewal', type_='model')
    Pool.register(
        wizard.StartEndorsement,
        module='endorsement_renewal', type_='wizard')
