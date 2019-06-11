# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt

from sql import Null
from trytond.pool import PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.coog_core import model, fields
from trytond.modules.coog_core.extra_details import WithExtraDetails


class ContractOption(metaclass=PoolMeta):
    __name__ = 'contract.option'

    third_party_periods = fields.One2Many(
        'contract.option.third_party_period', 'option',
        "Third Party Periods", delete_missing=True, readonly=True,
        order=[('protocol', 'ASC'), ('start_date', 'ASC')])


class ThirdPartyPeriod(WithExtraDetails, model.CoogView, model.CoogSQL):
    "Third Party Period"
    __name__ = 'contract.option.third_party_period'

    option = fields.Many2One('contract.option', "Contract Option",
        required=True, ondelete='CASCADE', select=True)
    start_date = fields.Date("Start Date", required=True,
        domain=['OR',
            ('end_date', '=', None),
            ('start_date', '<', Eval('end_date', dt.date.max))],
        depends=['end_date'])
    end_date = fields.Date("End Date",
        domain=['OR',
            ('end_date', '=', None),
            ('end_date', '>', Eval('start_date', dt.date.min))
            ],
        depends=['start_date'])
    send_after = fields.Date("Send After")
    protocol = fields.Many2One('third_party_manager.protocol', "Protocol",
        required=True, ondelete='RESTRICT')
    status = fields.Selection([
            ('waiting', "Waiting"),
            ('sent', "Sent"),
            ('validated', "Validated"),
            ('rejected', "Rejected"),
            ], "Status", required=True, readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.extra_details.readonly = True
        cls._error_messages.update({
                'tpp_overlap_error': "Third Party Period overlaps",
                })

    @classmethod
    def validate(cls, periods):
        super().validate(periods)
        for period in periods:
            period.check_dates()

    def check_dates(self):
        transaction = Transaction()
        connection = transaction.connection
        transaction.database.lock(connection, self._table)

        table = self.__table__()
        if self.end_date is None:
            overlap_query = ((table.end_date == Null)
                | (table.end_date >= self.start_date))
        else:
            overlap_query = (
                ((table.end_date == Null)
                    & (table.start_date <= self.end_date))
                | ((table.end_date >= self.start_date)
                    & (table.end_date <= self.end_date)))

        cursor = connection.cursor()
        cursor.execute(*table.select(table.id,
                where=(overlap_query
                    & (table.protocol == self.protocol.id)
                    & (table.option == self.option.id)
                    & (table.id != self.id))))
        overlap_id = cursor.fetchone()
        if overlap_id:
            self.raise_user_error('tpp_overlap_error')

    @classmethod
    def default_status(cls):
        return 'waiting'


class Coverage(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    third_party_protocols = fields.Many2Many(
        'third_party_manager.protocol-offered.option.description',
        'coverage', 'protocol', "Third Party Protocols")


class ThirdPartyProtocolCoverage(model.CoogSQL, model.CoogView):
    "Third Party Protocol - Coverage"
    __name__ = 'third_party_manager.protocol-offered.option.description'

    coverage = fields.Many2One('offered.option.description', "Coverage",
        required=True, ondelete='CASCADE')
    protocol = fields.Many2One('third_party_manager.protocol', "Protocol",
        required=True, ondelete='CASCADE')
