# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond import backend
from trytond.i18n import gettext
from trytond.model.exceptions import RequiredValidationError
from trytond.pool import PoolMeta

from trytond.modules.coog_core import coog_date


__all__ = [
    'CoveredElement',
    'Contract',
    'ContractWithInvoice',
    ]


class CoveredElement(metaclass=PoolMeta):
    __name__ = 'contract.covered_element'

    @classmethod
    def __register__(cls, module_name):
        super(CoveredElement, cls).__register__(module_name)
        # Migration from 1.8: Drop law_madelin column
        TableHandler = backend.get('TableHandler')
        covered_element = TableHandler(cls)
        if covered_element.column_exist('is_law_madelin'):
            covered_element.drop_column('is_law_madelin')


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    @classmethod
    def validate(cls, contracts):
        super(Contract, cls).validate(contracts)
        cls.check_ssn_on_covered_elements(contracts)

    @classmethod
    def check_ssn_on_covered_elements(cls, contracts):
        for contract in contracts:
            for covered in contract.covered_elements:
                if (covered.party and covered.party.get_SSN_required(None)
                        and not covered.party.ssn):
                    raise RequiredValidationError(gettext(
                            'contract_insurance_health_fr'
                            '.msg_ssn_required_covered',
                            covered=covered.rec_name))


class ContractWithInvoice(metaclass=PoolMeta):
    __name__ = 'contract'

    def _get_subscriber_rsi_periods(self, start_date, end_date):
        all_periods = []
        prev_complement = None
        for idx, complement in enumerate(self.subscriber.health_complement):
            if all_periods:
                all_periods[idx - 1] += (
                    coog_date.add_day(complement.date, -1),
                    prev_complement.hc_system)
            prev_complement = complement
            all_periods.append((complement.date or datetime.date.min,))
        if all_periods:
            all_periods[-1] += (datetime.date.max, complement.hc_system)

        rsi_periods = []
        for period_start, period_end, hc_system in all_periods:
            if period_end > start_date and period_start < end_date and \
                    hc_system.code == '03':
                rsi_periods.append((max(start_date, period_start),
                        min(end_date, period_end)))
        return rsi_periods

    def _get_rsi_invoices(self, start_date, end_date, invoice_state=None):
        rsi_periods = self._get_subscriber_rsi_periods(start_date, end_date)
        invoices = []
        for invoice in [x for x in self.invoices if (not invoice_state or
                    x.invoice_state == invoice_state)]:
            for period_start, period_end in rsi_periods:
                if invoice._check_rsi_invoice_date(period_start, period_end):
                    invoices.append(invoice)
                    break
        return invoices
