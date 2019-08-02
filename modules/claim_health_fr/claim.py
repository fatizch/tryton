# encoding: utf-8
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields

__all__ = [
    'HealthLoss',
    'Claim',
    ]


class HealthLoss(metaclass=PoolMeta):
    __name__ = 'claim.loss.health'

    act_coefficient = fields.Numeric('Medical Act Coefficient')
    is_care_access_contract = fields.Boolean('Belongs To Care Access Contract')
    is_off_care_pathway = fields.Boolean('Is Off Care Pathway')
    ss_agreement_price = fields.Numeric('Social Security Agreement Price')
    ss_agreement_rate = fields.Numeric('Social Security Agreement Rate')
    ss_reimbursement_amount = fields.Numeric('Social Security Reimbursement'
        ' Amount')

    @classmethod
    def __register__(cls, module_name):
        super().__register__(module_name)

        table = backend.get('TableHandler')(cls, module_name)

        if table.column_exist('ccam_act_code'):
            table.drop_column('ccam_act_code')


class Claim(metaclass=PoolMeta):
    __name__ = 'claim'

    slip_code = fields.Char('Slip Code')
    slip_date = fields.Date('Slip Date')
    invoice_number = fields.Char('Invoice Number')
    invoice_date = fields.Date('Invoice Date')
    noemie_archive_criterion = fields.Char('Noemie Archiving Criterion')
