# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import claim


def register():
    Pool.register(
        claim.ClaimDeclareFindProcess,
        module='claim_group_process', type_='model')
    Pool.register(
        claim.ClaimDeclare,
        module='claim_group_process', type_='wizard')
