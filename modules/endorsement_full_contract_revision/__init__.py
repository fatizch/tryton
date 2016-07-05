# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .process import *
from .wizard import *


def register():
    Pool.register(
        Process,
        StartFullContractRevision,
        module='endorsement_full_contract_revision', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_full_contract_revision', type_='wizard')
