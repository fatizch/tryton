# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import claim
import wizard


def register():
    Pool.register(
        claim.Claim,
        wizard.ImportProcessSelect,
        module='claim_life_process', type_='model')
