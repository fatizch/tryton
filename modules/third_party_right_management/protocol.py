# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
from itertools import groupby
from operator import attrgetter

from trytond.cache import Cache
from trytond.model import Unique
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id
from trytond.server_context import ServerContext
from trytond.transaction import Transaction
from trytond.wizard import Button, StateView, StateTransition

from trytond.modules.coog_core import model, fields, coog_string
from trytond.modules.rule_engine import get_rule_mixin


class Protocol(model.CoogView, model.CoogSQL, get_rule_mixin('rule', "Rule")):
    "Third Party Management Protocol"
    __name__ = 'third_party_manager.protocol'

    PROTOCOL_EVENTS = {'activate_contract', 'hold_contract', 'unhold_contract',
        'void_contract', 'renew_contract', 'first_invoice_payment',
        'apply_endorsement', 'terminate_contract', 'plan_contract_termination'}

    name = fields.Char("Name", required=True)
    code = fields.Char("Code", required=True)
    third_party_manager = fields.Many2One(
        'third_party_manager', "Third Party Manager", required=True,
        ondelete='CASCADE')
    technical_protocol = fields.Selection([], "Technical Protocol")
    watched_events = fields.Many2Many(
        'third_party_manager.protocol-event.type',
        'protocol', 'event_type', "Watched Events",
        domain=[
            ('code', 'in', list(PROTOCOL_EVENTS)),
            ])
    coverages = fields.Many2Many(
        'third_party_manager.protocol-offered.option.description',
        'protocol', 'coverage', "Coverages")

    _watched_codes_cache = Cache('watched_codes')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(table, table.code),
                "The code must be unique"),
            ]

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if not self.code:
            return coog_string.slugify(self.name)
        return self.code

    @property
    def watched_codes(self):
        codes = self._watched_codes_cache.get(self.id)
        if codes is None:
            codes = {evt_type.code for evt_type in self.watched_events}
            self._watched_codes_cache.set(self.id, codes)
        return codes

    @classmethod
    def _edit_periods(cls, option, protocol, periods, date, event_code):
        pool = Pool()
        Date = pool.get('ir.date')
        ThirdPartyPeriod = pool.get('contract.option.third_party_period')

        exec_ctx = {}
        option.init_dict_for_rule_engine(exec_ctx)
        exec_ctx['date'] = date
        exec_ctx['event_code'] = event_code
        rule_result = protocol.calculate_rule(exec_ctx)
        rule_result = rule_result if rule_result is not None else {}

        today = Date.today()
        start_date = rule_result.get('start_date', date)
        end_date = rule_result.get('end_date', option.end_date)
        add_period = rule_result.get('add_period', True)
        end_date_offset = dt.timedelta(days=1) if add_period else dt.timedelta()

        periods_to_remove = []
        modified_periods = []
        idx = len(periods) - 1
        while idx >= 0:
            period = periods[idx]
            if (end_date is not None and period.start_date > end_date):
                periods_to_remove.append(period)
            elif (period.end_date is not None
                    and period.end_date + dt.timedelta(days=1) == start_date
                    and period.extra_details == rule_result):
                period.end_date = end_date
                modified_periods.append(period)
                break
            else:
                if (period.end_date is None
                        or period.end_date > start_date):
                    period.end_date = start_date - end_date_offset
                    modified_periods.append(period)
                if add_period:
                    tpp = ThirdPartyPeriod(
                        option=option,
                        protocol=protocol,
                        start_date=start_date,
                        end_date=end_date,
                        send_after=rule_result.get('send_after', today),
                        extra_details=rule_result)
                    modified_periods.append(tpp)
                break
            idx -= 1
        else:
            if add_period:
                modified_periods.append(ThirdPartyPeriod(
                        option=option,
                        protocol=protocol,
                        start_date=start_date,
                        end_date=end_date,
                        send_after=rule_result.get('send_after', today),
                        extra_details=rule_result))

        return periods_to_remove, modified_periods

    @classmethod
    def edit_periods(cls, contract, date, event_code):
        periods_to_remove, modified_periods = [], []

        def update_periods(option, protocol, periods):
            if event_code not in protocol.watched_codes:
                return
            to_remove, modified = cls._edit_periods(
                option, protocol, periods, date, event_code)
            periods_to_remove.extend(to_remove)
            modified_periods.extend(modified)

        for covered in contract.covered_elements:
            for option in covered.options:
                if option.third_party_periods:
                    for protocol, periods in groupby(
                            option.third_party_periods,
                            key=attrgetter('protocol')):
                        update_periods(option, protocol, list(periods))
                else:
                    for protocol in option.coverage.third_party_protocols:
                        update_periods(option, protocol, [])
        return periods_to_remove, modified_periods

    @classmethod
    def do_activate_contract(cls, contract, origin, date=None, **kwargs):
        date = contract.start_date if date is None else date
        return cls.edit_periods(contract, date, 'activate_contract')

    @classmethod
    def do_apply_endorsement(cls, contract, origin, date=None, **kwargs):
        effective_date = origin.effective_date if date is None else date
        periods_to_remove, modified_periods = [], []
        for covered in contract.covered_elements:
            for option in covered.options:
                for protocol, periods in groupby(
                        option.third_party_periods, key=attrgetter('protocol')):
                    if 'apply_endorsement' not in protocol.watched_codes:
                        continue
                    for edpart in origin.definition.ordered_endorsement_parts:
                        tp_protocols = edpart.endorsement_part.\
                            third_party_protocols
                        if protocol not in tp_protocols:
                            continue
                        removed, modified = cls._edit_periods(
                            option, protocol, list(periods), effective_date,
                            'apply_endorsement')
                        periods_to_remove.extend(removed)
                        modified_periods.extend(modified)
        return periods_to_remove, modified_periods

    @classmethod
    def do_hold_contract(cls, contract, origin, date=None, **kwargs):
        pool = Pool()
        Date = pool.get('ir.date')
        suspension_date = ServerContext().get(
            'suspension_start_date',
            Date.today() - dt.timedelta(days=1))
        date = suspension_date if date is None else date
        return cls.edit_periods(contract, date, 'hold_contract')

    @classmethod
    def do_unhold_contract(cls, contract, origin, date=None, **kwargs):
        pool = Pool()
        Date = pool.get('ir.date')
        date = Date.today() if date is None else date
        return cls.edit_periods(contract, date, 'unhold_contract')

    @classmethod
    def do_void_contract(cls, contract, orign, date=None, **kwargs):
        pool = Pool()
        Date = pool.get('ir.date')
        date = Date.today() if date is None else date
        return cls.edit_periods(contract, date, 'void_contract')

    @classmethod
    def do_renew_contract(cls, contract, origin, date=None, **kwargs):
        if date is None:
            date = contract.activation_history[-1].start_date
        return cls.edit_periods(contract, date, 'renew_contract')

    @classmethod
    def do_first_invoice_payment(cls, contract, origin, date=None, **kwargs):
        date = contract.start_date if date is None else date
        return cls.edit_periods(contract, date, 'first_invoice_payment')

    @classmethod
    def do_terminate_contract(cls, contract, origin, date=None, **kwargs):
        pool = Pool()
        Date = pool.get('ir.date')
        date = Date.today() if date is None else date
        return cls.edit_periods(contract, date, 'terminate_contract')

    def do_plan_contract_termination(
            cls, contract, origin, date=None, **kwargs):
        date = contract.end_date if date is None else date
        return cls.edit_periods(contract, date, 'plan_contract_termination')


class ProtocolEventType(model.CoogSQL):
    "Third Party Management Protocol - Event Type"
    __name__ = 'third_party_manager.protocol-event.type'

    protocol = fields.Many2One('third_party_manager.protocol', "Protocol",
        required=True, ondelete='CASCADE')
    event_type = fields.Many2One('event.type', "Event Type", required=True,
        ondelete='CASCADE')


class ProtocolEndorsement(metaclass=PoolMeta):
    __name__ = 'third_party_manager.protocol'

    endorsement_parts = fields.Many2Many(
        'third_party_manager_protocol-endorsement_part',
        'protocol', 'endorsement_part', "Endorsement Parts",
        states={
            'invisible': ~Eval('watched_events', []).contains(
                Id('endorsement', 'event_apply_endorsement')),
            },
        depends=['watched_events'])


class RecomputePeriod(model.CoogWizard):
    "Recompute the periods"
    __name__ = 'third_party_manager.recompute_period'

    start_state = 'ask_date'
    ask_date = StateView(
        'third_party_manager.recompute_period.ask_date',
        'third_party_right_management.recompute_period_ask_date_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Recompute', 'recompute', 'tryton-go-next'),
            ])
    recompute = StateTransition()

    def default_benefits(self, name):
        pool = Pool()
        Date = pool.get('ir.date')
        Contract = pool.get('contract')
        contract = Contract(Transaction().context['active_id'])

        last_periods = []
        for covered in contract.covered_elements:
            for option in covered.options:
                for protocol, periods in groupby(
                        option.third_party_periods,
                        key=attrgetter('protocol')):
                    last_periods.append(list(periods)[-1])

        return {
            'periods': last_periods,
            'date': Date.today(),
            }

    def transition_recompute(self):
        pool = Pool()
        Contract = pool.get('contract')
        Protocol = pool.get('third_party_manager.protocol')
        ThirdPartyPeriod = pool.get('contract.option.third_party_period')

        contract = Contract(Transaction().context['active_id'])
        to_remove, modified_periods = Protocol.edit_periods(
            contract, self.ask_date.date, 'apply_endorsement')

        if to_remove or modified_periods:
            ThirdPartyPeriod.delete(to_remove)
            # Save first the modified periods then the new ones to prevent the
            # case where the new ones could overlap with the modified ones
            ThirdPartyPeriod.save(
                [p for p in modified_periods if p.id is not None])
            ThirdPartyPeriod.save([p for p in modified_periods if p.id is None])

        return 'end'


class RecomputePeriodAskDate(model.CoogView):
    "Recompute the periods - Ask Date"
    __name__ = 'third_party_manager.recompute_period.ask_date'
    periods = fields.One2Many('contract.option.third_party_period', None,
        "Last Periods", readonly=True)
    date = fields.Date("Date", required=True)
