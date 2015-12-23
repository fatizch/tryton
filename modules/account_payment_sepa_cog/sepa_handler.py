from lxml import etree
from dateutil.parser import parse

from trytond.modules.account_payment_sepa.payment import CAMT054

__all__ = ['CAMT054Coog']


class CAMT054Coog(CAMT054):

    def set_return_information(self, payment, element):
        super(CAMT054Coog, self).set_return_information(payment, element)
        date_value = self.date_value(element)
        payment.sepa_bank_reject_date = date_value

    def date_value(self, element):
        # Override method until correction in tryton
        # https://bugs.tryton.org/issue5181: missing .date()
        tag = etree.QName(element)
        date = element.find('./{%(ns)s}ValDt/{%(ns)s}Dt'
            % {'ns': tag.namespace})
        if date is not None:
            return parse(date.text).date()
        else:
            datetime = element.find('./{%(ns)s}ValDt/{%(ns)s}DtTm'
                % {'ns': tag.namespace})
            if datetime:
                return parse(datetime.text).date()
