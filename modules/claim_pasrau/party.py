# This file is part of Coog. The COPYRIGHT file at the top level off
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta, Pool

__all__ = [
    'Party',
    ]


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._error_messages.update({
                'no_zip_for_pasrau': 'A zip is required to compute the '
                'default pasrau rate',
                })

    def update_pasrau_rate(self, at_date, rate):
        PartyCustomPasrauRate = Pool().get('party.pasrau.rate')
        existing = PartyCustomPasrauRate.search([
                ('party', '=', self.id), ('effective_date', '=', at_date)])
        if existing:
            if existing[0].pasrau_tax_rate == rate:
                return
            existing[0].pasrau_tax_rate = rate
            return existing[0]
        return PartyCustomPasrauRate(
            effective_date=at_date,
            pasrau_tax_rate=rate,
            origin='default',
            party=self.id,
            )

    def get_personalized_pasrau_rate(self, period_start, period_end):
        PartyCustomPasrauRate = Pool().get('party.pasrau.rate')
        candidates = PartyCustomPasrauRate.search([('party', '=', self.id),
                ('effective_date', '<=', period_start)],
            order=[('effective_date', 'ASC')])
        if candidates:
            return candidates[-1].pasrau_tax_rate

    def get_appliable_pasrau_rate(self, income, period_start, period_end):
        DefaultPasrauRate = Pool().get('claim.pasrau.default.rate')
        rate = self.get_personalized_pasrau_rate(period_start, period_end)
        if not rate:
            zip_code = self.main_address.zip
            if not zip_code:
                self.raise_user_error('no_zip_for_pasrau')
            rate = DefaultPasrauRate.get_appliable_default_pasrau_rate(zip_code,
                income, period_start, period_end)
        return rate
