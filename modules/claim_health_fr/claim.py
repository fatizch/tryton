# encoding: utf-8
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields

__all__ = [
    'HealthLoss',
    'Claim',
    ]


class HealthLoss:
    __metaclass__ = PoolMeta
    __name__ = 'claim.loss.health'

    act_coefficient = fields.Numeric('Medical Act Coefficient')
    is_care_access_contract = fields.Boolean('Belongs To Care Access Contract')
    is_off_care_pathway = fields.Boolean('Is Off Care Pathway')
    ccam_act_code = fields.Char('CCAM act code')
    ss_agreement_price = fields.Numeric('Social Security Agreement Price')
    ss_agreement_rate = fields.Numeric('Social Security Agreement Rate')
    ss_reimbursement_amount = fields.Numeric('Social Security Reimbursement'
        ' Amount')


class Claim:
    __metaclass__ = PoolMeta
    __name__ = 'claim'

    slip_code = fields.Char('Slip Code')
    slip_date = fields.Date('Slip Date')
    invoice_number = fields.Char('Invoice Number')
    invoice_date = fields.Date('Invoice Date')
    noemie_archive_criterion = fields.Char('Noemie Archiving Criterion')
