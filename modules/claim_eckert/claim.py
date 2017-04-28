# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from dateutil.relativedelta import relativedelta
from sql import Null
from sql.aggregate import Max

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.model.fields import SQL_OPERATORS

from trytond.modules.coog_core import fields

__all__ = [
    'Claim',
    'ClaimBeneficiary',
    'Service',
    ]


class Claim:
    __metaclass__ = PoolMeta
    __name__ = 'claim'

    is_eckert = fields.Function(
        fields.Boolean('Is Eckert'),
        'getter_is_eckert')
    death_certificate_reception_date = fields.Function(
        fields.Boolean('Death certificate reception date',
            help='The date at which the death certificate was received. In '
            'case there were multiple documents, the latest one is used'),
        'getter_death_certificate_reception_date',
        searcher='searcher_death_certificate_reception_date')
    eckert_notes = fields.One2ManyDomain('ir.note', 'resource', 'Eckert notes',
        help='Notes related to Eckert Law beneficiary search / payment',
        domain=[('type_', '=', 'eckert')],
        states={'invisible': ~Eval('is_eckert')},
        depends=['is_eckert'], delete_missing=True)

    @classmethod
    def getter_death_certificate_reception_date(cls, claims, name):
        pool = Pool()
        Document = pool.get('document.description')
        request_line = pool.get('document.request.line').__table__()
        cursor = Transaction().connection.cursor()

        death_certificate_doc = Document.get_document_per_code(
            'death_certificate')
        dates = {x.id: None for x in claims}
        cursor.execute(*request_line.select(request_line.claim,
                Max(request_line.reception_date),
                where=(request_line.document_desc == death_certificate_doc.id)
                & (request_line.reception_date != Null)
                & request_line.claim.in_([x.id for x in claims]),
                group_by=[request_line.claim]))
        for claim_id, reception_date in cursor.fetchall():
            dates[claim_id] = reception_date
        return dates

    def getter_is_eckert(self, name):
        return any(service.benefit.is_eckert
            for loss in self.losses
            for service in loss.services)

    @classmethod
    def searcher_death_certificate_reception_date(cls, name, clause):
        pool = Pool()
        Document = pool.get('document.description')
        request_line = pool.get('document.request.line').__table__()
        claim = cls.__table__()

        death_certificate_doc = Document.get_document_per_code(
            'death_certificate')
        _, operator, operand = clause
        Operator = SQL_OPERATORS[operator]

        return ('id', 'in', claim.join(request_line, 'LEFT OUTER',
                condition=claim.id == request_line.claim
                ).select(claim.id,
                where=(request_line.document_desc == death_certificate_doc.id),
                group_by=[claim.id],
                having=Operator(Max(request_line.reception_date), operand)))


class Service:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    def get_beneficiaries_data(self, at_date):
        data = super(Service, self).get_beneficiaries_data(at_date)
        if not self.benefit.is_eckert:
            return data
        parties = {x.party for x in self.beneficiaries
            if x.documents_reception_date
            and x.documents_reception_date <= (at_date or datetime.date.max)}
        return [x for x in data if x[0] in parties]


class ClaimBeneficiary:
    __metaclass__ = PoolMeta
    __name__ = 'claim.beneficiary'

    is_eckert = fields.Function(
        fields.Boolean('Is Eckert'),
        'getter_is_eckert')
    identification_date = fields.Date('Identification Date',
        help='The date at which the beneficiary party is clearly identified',
        states={'required': Eval('is_eckert') & Bool(Eval('identified', False)),
            'readonly': Bool(Eval('identified', False))},
        depends=['is_eckert', 'identified'])
    expected_indemnification_date = fields.Function(
        fields.Date('Expected Indemnification Date',
            help='For Eckert benefits, indemnification should be paid at most '
            'after a configured date (see Claim Configuration)',
            states={'invisible': ~Eval('documents_reception_date')},
            depends=['documents_reception_date']),
        'getter_expected_indemnification_date')
    indemnification = fields.Function(
        fields.Many2One('claim.indemnification', 'Indemnification',
            help='The indemnification that paid the benefit for this '
            'beneficiary',
            states={'invisible': ~Eval('indemnification')}),
        'getter_indemnification')

    @classmethod
    def __setup__(cls):
        super(ClaimBeneficiary, cls).__setup__()
        cls._buttons['identify']['readonly'] |= ~Eval('identification_date')

    def getter_expected_indemnification_date(self, name):
        config = Pool().get('claim.configuration').get_singleton()
        delay = config.eckert_law_target_delay
        if not self.documents_reception_date or not delay:
            return None
        return self.documents_reception_date + relativedelta(days=delay)

    def getter_indemnification(self, name):
        for indemnification in self.service.indemnifications:
            if indemnification.beneficiary != self.party:
                continue
            if indemnification.status in ('calculated', 'controlled', 'paid',
                    'scheduled', 'validated'):
                return indemnification.id

    def getter_is_eckert(self, name):
        return self.service.benefit.is_eckert
