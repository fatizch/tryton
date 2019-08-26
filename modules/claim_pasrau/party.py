# This file is part of Coog. The COPYRIGHT file at the top level off
# this repository contains the full copyright notices and license terms.
from itertools import groupby

from trytond.pool import PoolMeta, Pool
from trytond.server_context import ServerContext
from trytond.modules.coog_core import model

__all__ = [
    'Party',
    ]


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    _history = True

    def update_pasrau_rate(self, at_date, rate, business_id=None):
        business_id = business_id or None
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
            business_id=business_id,
            )

    def get_personalized_pasrau_data(self, invoice_date):
        PartyCustomPasrauRate = Pool().get('party.pasrau.rate')
        candidates = PartyCustomPasrauRate.search([('party', '=', self.id),
                ('effective_date', '<=', invoice_date)],
            order=[('effective_date', 'ASC')])
        if candidates:
            pasrau_dict = ServerContext().get('pasrau_data')
            if pasrau_dict:
                pasrau_dict['pasrau_rate'] = candidates[-1].pasrau_tax_rate
                pasrau_dict['pasrau_rate_kind'] = candidates[-1].origin
                pasrau_dict['pasrau_rate_business_id'] = \
                    candidates[-1].business_id
                with ServerContext().set_context(pasrau_data=pasrau_dict):
                    return candidates[-1]
            return candidates[-1]

    def get_personalized_pasrau_rate(self, invoice_date):
        personalized_pasrau_rate = self.get_personalized_pasrau_data(
            invoice_date)
        if personalized_pasrau_rate:
            return personalized_pasrau_rate.pasrau_tax_rate

    def get_appliable_pasrau_rate(self, income, period_start, period_end,
            invoice_date):
        DefaultPasrauRate = Pool().get('claim.pasrau.default.rate')
        rate = self.get_personalized_pasrau_rate(invoice_date)
        if rate is None:
            zip_code = self.main_address.zip
            if not zip_code:
                raise ValidationError(gettext(
                        'claim_pasrau.msg_no_zip_for_pasrau'))
            rate = DefaultPasrauRate.get_appliable_default_pasrau_rate(zip_code,
                income, period_start, period_end, invoice_date)
        return rate

    def pasrau_modified_fields(self, from_date, max_date):
        if not from_date:
            return []
        fields_to_track = ['name', 'first_name', 'birth_date', 'ssn']
        previous_fields = model.fields_changed_since_date(self,
            from_date, fields_to_track)
        if not previous_fields:
            return []
        # Look for all versions since the last slip
        versions = model.history_versions(self, from_date, max_date)

        assert None not in versions  # "self" should not be deleted...

        # Apply upper to avoid "fake" modifications
        previous_fields = {k: v.upper() if isinstance(v, str) else v
            for k, v in previous_fields.items() if v}

        changes = []

        # We must group per date, and versions are per datetime
        for date, date_versions in groupby(sorted(iter(versions.items()),
                    key=lambda x: x[0]), key=lambda x: x[0].date()):
            cur_changes = {}
            for _, cur_version in sorted(date_versions, key=lambda x: x[0]):
                for field_name in fields_to_track:
                    if field_name not in previous_fields:
                        continue
                    new_value = getattr(cur_version, field_name)
                    if isinstance(new_value, str):
                        new_value = new_value.upper()
                    if new_value != previous_fields[field_name]:
                        cur_changes[field_name] = previous_fields[field_name]
                        previous_fields[field_name] = new_value
            if cur_changes:
                cur_changes['modification_date'] = date
                if 'ssn' in cur_changes:
                    cur_changes['ssn'] = cur_changes['ssn'][:-2]
                changes.append(cur_changes)
        return changes
