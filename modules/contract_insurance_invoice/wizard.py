# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta

__all__ = [
    'PartyErase',
    ]


class CreateStatement:
    __metaclass__ = PoolMeta
    __name__ = 'account.statement.create'

    def get_line_values(self, statement, invoice, line):
        values = super(CreateStatement, self).get_line_values(statement,
            invoice, line)
        values['contract'] = line.contract if line else None
        return values

    @classmethod
    def get_where_clause_from_context(cls, tables, active_model, instances,
            company, date=None):
        where_clause = super(CreateStatement,
                cls).get_where_clause_from_context(tables, active_model,
                    instances, company, date)
        if active_model == 'contract':
            return where_clause & (tables['line'].contract.in_(
                [x.id for x in instances]))
        return where_clause

    def get_default_values_from_context(self, active_model, instances, company):
        values = super(CreateStatement, self).get_default_values_from_context(
            active_model, instances, company)
        if active_model == 'contract':
            if len(list({x.subscriber.id for x in instances})) > 1:
                self.__class__.raise_user_error('too_many_parties')
            values['party'] = instances[0].subscriber.id
        return values


class PartyErase:
    __metaclass__ = PoolMeta
    __name__ = 'party.erase'

    def to_erase(self, party_id):
        to_erase = super(PartyErase, self).to_erase(party_id)
        InvoiceLine = Pool().get('account.invoice.line')
        InvoiceLineDetail = Pool().get('account.invoice.line.detail')
        details_to_erase = InvoiceLineDetail.search([
                ('covered_element.party', '=', party_id)])
        lines_to_erase = [d.invoice_line.id for d in details_to_erase]
        to_erase.extend([
                (InvoiceLine, [('id', 'in', lines_to_erase)], True,
                    ['description'],
                    [None]),
                (InvoiceLine, [('party', '=', party_id)], True,
                    ['description'],
                    [None])
                ])
        return to_erase
