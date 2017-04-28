# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import utils, fields

__all__ = [
    'IndemnificationDefinition',
    ]


class IndemnificationDefinition:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification_definition'

    is_eckert = fields.Boolean('Is Eckert', states={'invisible': True})
    eckert_payment_date = fields.Date('Eckert Payment Date Limit',
        help='The date at which the indemnification should be paid according '
        'to Eckert Law', states={
            'invisible': ~Eval('is_eckert') | ~Eval('beneficiary')},
        depends=['beneficiary', 'is_eckert'])
    show_eckert_warning = fields.Boolean('Show Eckert Warning',
        states={'invisible': True})

    @classmethod
    def view_attributes(cls):
        return super(IndemnificationDefinition, cls).view_attributes() + [
            ("/form/group[@id='eckert_warning']", 'states',
                {'invisible': ~Eval('show_eckert_warning')}),
            ]

    @fields.depends('beneficiary', 'indemnification_date', 'service',
        'is_eckert', 'start_date')
    def on_change_beneficiary(self):
        super(IndemnificationDefinition, self).on_change_beneficiary()
        self.is_eckert = self.service and self.service.benefit.is_eckert
        self.update_eckert()
        self.show_eckert_warning = self.on_change_with_show_eckert_warning()

    @fields.depends('beneficiary', 'indemnification_date', 'service',
        'is_eckert', 'start_date')
    def on_change_service(self):
        super(IndemnificationDefinition, self).on_change_service()
        self.is_eckert = self.service and self.service.benefit.is_eckert
        self.update_eckert()
        self.show_eckert_warning = self.on_change_with_show_eckert_warning()

    def update_eckert(self):
        self.eckert_payment_date = None
        if (not self.is_eckert or not self.beneficiary or
                not self.indemnification_date):
            return
        claim_config = Pool().get('claim.configuration').get_singleton()
        beneficiary, = [x for x in self.service.beneficiaries
            if x.party == self.beneficiary]
        self.eckert_payment_date = beneficiary.expected_indemnification_date
        self.start_date = utils.today() + relativedelta(
            days=claim_config.eckert_law_default_delay or 0)
        self.end_date = None
        self.indemnification_date = self.start_date

    @fields.depends('eckert_payment_date', 'indemnification_date')
    def on_change_with_show_eckert_warning(self):
        if not self.indemnification_date or not self.eckert_payment_date:
            return False
        return self.indemnification_date >= self.eckert_payment_date
