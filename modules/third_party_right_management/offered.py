# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt

from dateutil.relativedelta import relativedelta
from trytond.pool import PoolMeta
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
    party = fields.Function(
        fields.Many2One('party.party', "Party"),
        'get_party', searcher='search_party')
    start_date = fields.Date("Start Date", required=True,
        domain=['OR',
            ('end_date', '=', None),
            ('start_date', '<=', Eval('end_date', dt.date.max))
            ], depends=['end_date'])
    end_date = fields.Date("End Date",
        domain=['OR',
            ('end_date', '=', None),
            ('end_date', '>=', Eval('end_date_domain_date', dt.date.min))
            ], depends=['end_date_domain_date'])
    start_date_domain_date = fields.Function(
        fields.Date('Start Date Domain Date'),
        'getter_start_date_domain_date')
    end_date_domain_date = fields.Function(
        fields.Date('End Date Domain Date'),
        'getter_end_date_domain_date')
    send_after = fields.Date("Send After")
    protocol = fields.Many2One('third_party_manager.protocol', "Protocol",
        required=True, ondelete='RESTRICT')
    status = fields.Selection([
            ('waiting', "Waiting"),
            ('sent', "Sent"),
            ('validated', "Validated"),
            ('rejected', "Rejected"),
            ], "Status", required=True, readonly=True)
    color = fields.Function(
        fields.Char('Color'),
        'get_color')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.extra_details.readonly = True
        cls._error_messages.update({
                'tpp_overlap_error': "Third Party Period overlaps",
                })

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [(
                '/tree',
                'colors',
                Eval('color', 'black'))]

    @classmethod
    def default_status(cls):
        return 'waiting'

    @classmethod
    def get_color(cls, periods, name=None):
        colors = {
            'waiting': 'black',
            'sent': 'green',
            'validated': 'green',
            'rejected': 'red'
            }
        return {p.id: 'grey' if p.start_date > p.end_date
            else colors[p.status] for p in periods}

    def get_party(self, name=None):
        if self.option and self.option.covered_element:
            return self.option.covered_element.party.id
        return

    @classmethod
    def search_party(cls, name, clause):
        return [('option.covered_element.party',) + tuple(clause[1:])],

    def getter_end_date_domain_date(self, name):
        return (self.start_date + relativedelta(days=-1)) if self.start_date \
            else dt.date.min

    def getter_start_date_domain_date(self, name):
        return (self.end_date + relativedelta(days=1)) if self.end_date \
            else dt.date.max


class Coverage(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    third_party_protocols = fields.Many2Many(
        'third_party_manager.protocol-offered.option.description',
        'coverage', 'protocol', "Third Party Protocols")

    @classmethod
    def _export_skips(cls):
        return super()._export_skips() | {'third_party_protocols'}


class ThirdPartyProtocolCoverage(model.CoogSQL, model.CoogView):
    "Third Party Protocol - Coverage"
    __name__ = 'third_party_manager.protocol-offered.option.description'

    coverage = fields.Many2One('offered.option.description', "Coverage",
        required=True, ondelete='CASCADE')
    protocol = fields.Many2One('third_party_manager.protocol', "Protocol",
        required=True, ondelete='CASCADE')
