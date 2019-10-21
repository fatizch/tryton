# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.conditionals import Case

from trytond import backend

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.tools import grouped_slice, reduce_ids
from trytond.pyson import Eval

from trytond.modules.coog_core import fields


class Claim(metaclass=PoolMeta):
    __name__ = 'claim'

    third_party_payment = fields.Boolean("Third Party Payment", readonly=True)
    is_almerys = fields.Boolean("Is Almerys", readonly=True)
    almerys_file = fields.Char("Almerys File", readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()

        for field_name in {
                'noemie_archive_criterion', 'quote_date',
                'quote_validity_end_date', 'slip_code', 'slip_date'}:
            attribute = getattr(cls, field_name)
            if 'invisible' not in attribute.states:
                attribute.states['invisible'] = Eval('is_almerys', False)
            else:
                attribute.states['invisible'] |= Eval('is_almerys', False)
            attribute.depends.append('is_almerys')


class AlmerysConfig(metaclass=PoolMeta):
    __name__ = 'third_party_protocol.almerys.configuration'

    claim_journal = fields.Many2One(
        'account.journal', "Claim Journal", required=True,
        domain=[
            ('type', '=', 'claim'),
            ],
        ondelete='RESTRICT')
    claim_statement_journal = fields.Many2One(
        'account.statement.journal', "Statement Journal", required=True,
        ondelete='RESTRICT',
        domain=[
            ('validation', '=', 'number_of_lines'),
            ])
    invoiced_party = fields.Many2One(
        'party.party', "Invoiced Party", required=True,
        ondelete='RESTRICT')
    account_statement = fields.Many2One(
        'account.account', "Account used in Statement", required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ],
        ondelete='RESTRICT')


class Loss(metaclass=PoolMeta):
    __name__ = 'claim.loss'

    code = fields.Char("Code")
    almerys_sequence = fields.Integer("Almerys Sequence")


class HealthLoss(metaclass=PoolMeta):
    __name__ = 'claim.loss.health'

    almerys_other_insurer_delivered_amount = fields.Numeric(
        "Almerys Other Insurer Delivered Amount", readonly=True)
    almerys_prescription_date = fields.Date("Almerys Prescription Date",
        readonly=True)
    almerys_accident_date = fields.Date("Almerys Accident Date", readonly=True)
    almerys_top_depassement = fields.Boolean("Almerys Top Depassement",
        readonly=True)
    almerys_depassement_amount = fields.Numeric("Almerys Depassement Amount",
        readonly=True)
    almerys_num_dents = fields.Integer("Almerys Num Dents", readonly=True)


class Service(metaclass=PoolMeta):
    __name__ = 'claim.service'

    third_party_invoice_line = fields.Many2One('account.invoice.line',
        "Third Party Invoice Line", ondelete='RESTRICT')
    third_party_invoice_line_payback = fields.Many2One('account.invoice.line',
        "Third Party Invoice Line Payback", ondelete='RESTRICT')

    @classmethod
    def __register__(cls, module):
        TableHandler = backend.get('TableHandler')
        handler = TableHandler(cls, module)
        # Migrate from 2.5 rename third_party_invoice_line_cancel to
        # third_party_invoice_line_payback
        if handler.column_exist('third_party_invoice_line_cancel'):
            handler.column_rename('third_party_invoice_line_cancel',
                'third_party_invoice_line_payback')
        super().__register__(module)


class Benefit(metaclass=PoolMeta):
    __name__ = 'benefit'

    delegation = fields.Selection([
            ('none', 'None'),
            ('prestation', 'Prestation'),
            ('prestation_reimbursement', 'Prestation & Reimbursement'),
            ], "Delegation")

    @classmethod
    def default_delegation(cls):
        return 'none'

    def calculate_benefit(self, args):
        if self.delegation == 'none':
            return super().calculate_benefit(args)
        loss = args['loss']
        health_loss, = loss.health_loss
        indemnification = args['indemnification']
        return [{
                'kind': 'benefit',
                'start_date': args['start_date'],
                'end_date': None,
                'nb_of_unit': 1,
                'amount': indemnification.forced_base_amount,
                'base_amount': indemnification.forced_base_amount,
                'amount_per_unit': indemnification.forced_base_amount,
                'forced_base_amount': indemnification.forced_base_amount,
                'description': health_loss.act_description.name,
                }]


class Indemnification(metaclass=PoolMeta):
    __name__ = 'claim.indemnification'

    beneficiary_as_text = fields.Char("Beneficiary as text")

    @classmethod
    def get_beneficiary_name(cls, indemnifications, name):
        pool = Pool()
        Party = pool.get('party.party')
        Service = pool.get('claim.service')
        Loss = pool.get('claim.loss')
        Claim = pool.get('claim')

        party = Party.__table__()
        indemnification = cls.__table__()
        service = Service.__table__()
        loss = Loss.__table__()
        claim = Claim.__table__()
        cursor = Transaction().connection.cursor()

        names = {}
        for sub_indemn in grouped_slice(indemnifications):
            cursor.execute(
                *indemnification.join(
                    party, condition=party.id == indemnification.beneficiary
                ).join(
                    service, condition=service.id == indemnification.service
                ).join(
                    loss, condition=loss.id == service.loss
                ).join(
                    claim, condition=claim.id == loss.claim
                ).select(
                    indemnification.id, Case(
                        (claim.third_party_payment,
                            indemnification.beneficiary_as_text),
                        else_=party.name),
                    where=reduce_ids(indemnification.id, map(int, sub_indemn))
                ))
            names.update(cursor.fetchall())
        return names
