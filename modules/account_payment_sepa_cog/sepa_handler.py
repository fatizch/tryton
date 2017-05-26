# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from lxml import etree
from dateutil.parser import parse

from trytond.modules.account_payment_sepa.payment import CAMT054
from trytond.pool import Pool

from trytond.modules.coog_core import utils

__all__ = ['CAMT054Coog', 'CAMT054CoogPassive']


class CAMT054Coog(CAMT054):

    def set_return_information(self, payment, element):
        super(CAMT054Coog, self).set_return_information(payment, element)
        date_value = self.date_value(element)
        payment.sepa_bank_reject_date = date_value or utils.today()

    def date_value(self, element):
        date = super(CAMT054Coog, self).date_value(element)
        if date:
            return date
        tag = etree.QName(element)
        date = element.find('./{%(ns)s}BookgDt/{%(ns)s}Dt'
            % {'ns': tag.namespace})
        if date is None:
            # Some banks do not use BookgDt
            date = element.find(
                './{%(ns)s}NtryDtls//{%(ns)s}RltdDts/{%(ns)s}IntrBkSttlmDt' %
                {'ns': tag.namespace})
        if date is not None:
            return parse(date.text).date()


class CAMT054CoogPassive(CAMT054Coog):
    def __init__(self):
        self.Payment = Pool().get('account.payment')
