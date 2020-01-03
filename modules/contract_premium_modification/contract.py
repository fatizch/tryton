# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict

from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Or
from trytond.modules.coog_core import fields, model


__all__ = [
    'Contract',
    'ContractOption',
    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    with_waiver_of_premium = fields.Function(
        fields.Boolean('With Waiver Of Premium'),
        'get_with_waiver_of_premium')
    with_discount_of_premium = fields.Function(
        fields.Boolean('With Modification of Premium'),
        'get_with_discount_of_premium')
    with_modifications_of_premium = fields.Function(
        fields.Boolean('With Modifications Of Premium'),
        'get_with_modifications_of_premium')
    waivers = fields.One2Many(
        'contract.waiver_premium', 'contract',
        'Waivers Of Premium',
        states={'invisible': ~Eval('waivers')}, readonly=True,
        delete_missing=True)
    discounts = fields.One2Many(
        'contract.premium_modification.discount', 'contract',
        'Discounts On Premium',
        states={'invisible': ~Eval('discounts')}, readonly=True,
        delete_missing=True)
    possible_discounts = fields.Function(
        fields.One2Many('commercial_discount', None, "Possible Discounts"),
        'get_possible_discounts')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'create_waivers': {
                    'invisible': Or(
                        ~Eval('with_waiver_of_premium'),
                        Eval('status') != 'active'),
                    'depends': ['with_waiver_of_premium', 'status'],
                    },
                'create_discounts': {
                    'invisible': Or(
                        ~Eval('with_discount_of_premium'),
                        Eval('status') != 'active'),
                    'depends': ['with_discount_of_premium', 'status'],
                    },
                })

    def get_possible_discounts(self, name=None):
        discounts = []
        for option in self.options + self.covered_element_options:
            discounts.extend([dr.commercial_discount.id
                    for dr in option.coverage.discount_rules])
        return discounts

    @classmethod
    def view_attributes(cls):
        return super(Contract, cls).view_attributes() + [(
                '/form/group[@id="premium_modification_buttons"]',
                'states',
                {'invisible': True}
                )]

    @classmethod
    @model.CoogView.button_action(
        'contract_premium_modification.act_create_waivers_wizard')
    def create_waivers(cls, contracts):
        pass

    @classmethod
    @model.CoogView.button_action(
        'contract_premium_modification.act_create_discounts_wizard')
    def create_discounts(cls, contracts):
        pass

    @classmethod
    def create_full_modification_period(
            cls, contracts, start, end, rebill=True):
        pool = Pool()
        PremiumModification = pool.get('contract.premium_modification')

        new_modifications = []
        for contract in contracts:
            if (contract.initial_start_date > end
                    or (contract.final_end_date
                        and contract.final_end_date < start)):
                continue
            new_modifications += contract.get_new_modifications(
                contract.covered_element_options, start, end,
                automatic=True)
        if new_modifications:
            PremiumModification.save(new_modifications)
        if rebill:
            for contract in contracts:
                contract.rebill(start)

    def get_new_modifications(
            self, options, start_date, end_date, automatic=False,
            modifications=None):
        """
        If automatic is set to True end_date and start_date will be ignored
        """
        pool = Pool()
        WaiverPremiumRule = pool.get('waiver_premium.rule')
        WaiverPremium = pool.get('contract.waiver_premium')
        WaiverPremiumOption = pool.get(
            'contract.waiver_premium-contract.option')
        Discount = pool.get('commercial_discount')
        DiscountModification = pool.get(
            'contract.premium_modification.discount')
        DiscountOption = pool.get(
            'contract.premium_modification.discount-contract.option')

        if not modifications:
            modifications = []
        eligible_modifications = defaultdict(lambda: defaultdict(list))
        for option in options:
            if option.status in {'void', 'quote', 'refused', 'declined'}:
                continue
            for rule in option.coverage.premium_modification_rules:
                if not rule.eligible(option, modifications):
                    continue
                if automatic and not rule.automatic:
                    continue
                eligible_modifications[rule.modification][rule].append(option)

        new_modifications = []
        for modification, rule_options in eligible_modifications.items():
            if isinstance(modification, WaiverPremiumRule):
                PremMod = WaiverPremium
                PremModOption = WaiverPremiumOption
            elif isinstance(modification, Discount):
                PremMod = DiscountModification
                PremModOption = DiscountOption

            prem_mod = PremMod()
            prem_mod.contract = self
            prem_mod.automatic = automatic
            new_options = []
            for rule, options in rule_options.items():
                for option in options:
                    if automatic:
                        start_date, end_date = \
                            option.calculate_automatic_discount_duration(rule)
                    premmod = PremModOption(
                        start_date=start_date, end_date=end_date,
                        option=option, modification_rule=rule)
                    new_options.append(premmod)
            prem_mod.premium_modification_options = new_options
            prem_mod.modification = modification
            new_modifications.append(prem_mod)
        return new_modifications

    def get_with_waiver_of_premium(self, name):
        all_options = self.get_all_options()
        return any(x.with_waiver_of_premium for x in all_options)

    def get_with_discount_of_premium(self, name):
        all_options = self.get_all_options()
        return any(x.with_discount_of_premium for x in all_options)

    def get_with_modifications_of_premium(self, name):
        all_options = self.get_all_options()
        return any(x.with_modifications_of_premium for x in all_options)

    def finalize_invoices_lines(self, lines):
        super(Contract, self).finalize_invoices_lines(lines)
        self.add_modifications_invoice_lines(lines)

    def add_modifications_invoice_lines(self, lines):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        InvoiceLineDetail = pool.get('account.invoice.line.detail')
        for line in list(lines):
            option = None
            if line.details and line.details[0].premium:
                option = line.details[0].premium.option
            if not option:
                continue
            modifications = option.get_premium_modifications_for_invoice_line(
                line)
            for modification_option in modifications:
                modification_ctx = option.get_context_modification_invoice_line(
                    modification_option, line)
                rule = modification_option.modification_rule
                line_fields = rule.get_modification_line_fields()
                line_detail_fields = rule.get_modification_line_detail_fields()
                modification_line = InvoiceLine(**{x: getattr(line, x, None)
                        for x in line_fields})
                modification_line.details = [
                    InvoiceLineDetail(**{x: getattr(line.details[0], x, None)
                            for x in line_detail_fields})]
                modification_line.details[0].premium_modification = \
                    modification_option.premium_modification
                rule.init_modification_line(modification_line, modification_ctx)
                lines.append(modification_line)

    @classmethod
    def _calculate_methods(cls, product):
        return super(Contract, cls)._calculate_methods(product) + [
            ('contract', 'create_automatic_premium_modifications')]

    def _get_modification_options(self, modification, current_options):
        """
        modification: either a contract.waiver_premium or a
                      contract.premium_modification.discount
        current_options: a list of contract.option
        """
        pool = Pool()
        WaiverPremium = pool.get('contract.waiver_premium')
        WaiverPremiumOption = pool.get(
            'contract.waiver_premium-contract.option')
        DiscountModification = pool.get(
            'contract.premium_modification.discount')
        DiscountOption = pool.get(
            'contract.premium_modification.discount-contract.option')
        if isinstance(modification, WaiverPremium):
            PremModOption = WaiverPremiumOption
        elif isinstance(modification, DiscountModification):
            PremModOption = DiscountOption

        modification_options = [mo
            for mo in modification.premium_modification_options
            if mo.option in current_options]
        for option in current_options:
            modification_option = next(
                (mo for mo in modification_options if mo.option == option),
                None)
            if modification_option is None:
                modification_option = PremModOption(option=option)
                modification_options.append(modification_option)
            dates = option.calculate_automatic_waiver_duration()
            if dates and len(dates) == 2:
                modification_option.start_date = dates[0]
                modification_option.end_date = dates[1]
            else:
                modification_option.start_date = None
                modification_option.end_date = None

        return modification_options

    def _create_modifications(self, modifications, options):
        """
        modifications: a list of contract.waiver_premium
                       or a list of contract.premium_modification.discount
        options: a list of contract.option
        """
        pool = Pool()
        WaiverPremium = pool.get('contract.waiver_premium')
        DiscountModification = pool.get(
            'contract.premium_modification.discount')

        new_modifications = []
        if not modifications or not options:
            return new_modifications

        if isinstance(modifications[0], WaiverPremium):
            PremMod = WaiverPremium
        elif isinstance(modifications[0], DiscountModification):
            PremMod = DiscountModification

        manual_modifications = []
        old_automatic_mods = []
        current_automatic_mods = []
        for mod in modifications:
            if not mod.automatic:
                manual_modifications.append(mod)
            elif self.start_date == self.initial_start_date:
                current_automatic_mods.append(mod)
            elif mod.start_date < self.start_date:
                old_automatic_mods.append(mod)
            else:
                current_automatic_mods.append(mod)

        if current_automatic_mods:
            for modification in current_automatic_mods:
                mod_options = self._get_modification_options(
                    modification, options)
                modification.premium_modification_options = mod_options
                modification.start_date = modification.get_start_date()
        else:
            modification = PremMod(
                automatic=True, premium_modification_options=[])
            mod_options = self._get_modification_options(
                modification, options)
            modification.premium_modification_options = mod_options
            modification.start_date = modification.get_start_date()

        new_modifications = old_automatic_mods + manual_modifications
        if (modification.start_date
                and modification.premium_modification_options):
            if current_automatic_mods:
                new_modifications.extend(current_automatic_mods)
            else:
                new_modifications.append(modification)
        return new_modifications

    def init_automatic_discount(self):
        manual_discounts = [x for x in self.discounts if not
            x.discount_options[0].discount_rule.automatic]
        if any(rule.automatic
                for discount in self.possible_discounts
                for rule in discount.rules):
            self.discounts = manual_discounts + self.get_new_modifications(
                self.options + self.covered_element_options, self.start_date,
                self.end_date, automatic=True)
        else:
            self.discounts = manual_discounts

    def before_activate(self):
        super().before_activate()
        self.init_automatic_discount()

    def create_automatic_premium_modifications(self):
        waiver_options, discount_options = [], []
        for option in self.get_all_options():
            if any(r.automatic for r in option.coverage.waiver_premium_rule):
                waiver_options.append(option)
            if any(r.automatic for r in option.coverage.discount_rules):
                discount_options.append(option)

        if not waiver_options and not discount_options:
            return

        self.waivers = self._create_modifications(
            self.waivers, waiver_options)
        self.discounts = self._create_modifications(
            self.discounts, discount_options)

    def get_invoice_periods(self, up_to_date, from_date=None,
            ignore_invoices=False):
        if (self.final_end_date and up_to_date and
                self.product._must_invoice_after_contract):
            up_to_date = min(up_to_date, self.final_end_date)
        return super(Contract, self).get_invoice_periods(up_to_date,
            from_date, ignore_invoices)

    def _calculate_final_invoice_end_date(self):
        if self.product._must_invoice_after_contract:
            return None
        return super(Contract, self)._calculate_final_invoice_end_date()

    def _get_schedule_displayer_details(self, line, contract_invoice):
        details = super(Contract, self)._get_schedule_displayer_details(line,
            contract_invoice)
        discount = line.details[0].discount if line.details else None
        if discount:
            details['discount'] = {
                'code': discount.discount_options[0].discount_rule
                .commercial_discount.code,
                'amount': details['amount'],
                }
        return details

    def update_displayer_from_details(self, displayer, details):
        if details.get('discount'):
            return
        super().update_displayer_from_details(displayer, details)


class ContractOption(metaclass=PoolMeta):
    __name__ = 'contract.option'

    waivers = fields.One2Many('contract.waiver_premium-contract.option',
        'option', 'Waivers', delete_missing=True,
        order=[('start_date', 'ASC NULLS FIRST')])
    discounts = fields.One2Many(
        'contract.premium_modification.discount-contract.option',
        'option', 'Discounts', delete_missing=True,
        order=[('start_date', 'ASC NULLS FIRST')])
    with_waiver_of_premium = fields.Function(
        fields.Boolean('With Waiver Of Premium'),
        'get_with_waiver_of_premium')
    with_discount_of_premium = fields.Function(
        fields.Boolean('With Discount of Premium'),
        'get_with_discount_of_premium')
    with_modifications_of_premium = fields.Function(
        fields.Boolean('With Modifications Of Premium'),
        'get_with_modifications_of_premium')
    possible_discounts = fields.Function(
        fields.One2Many('commercial_discount', None, "Possible Discounts"),
        'get_possible_discounts')

    def get_possible_discounts(self, name=None):
        return [dr.commercial_discount.id
            for dr in self.coverage.discount_rules]

    @property
    def premium_modifications(self):
        return self.waivers + self.discounts

    @classmethod
    def validate(cls, options):
        with model.error_manager():
            super(ContractOption, cls).validate(options)
            for option in options:
                if option.has_overlapping_waivers():
                    cls.append_functional_error(
                        ValidationError(gettext(
                                'contract_waiver_premium'
                                '.msg_overlapping_waivers',
                                option=option.rec_name)))

    def has_overlapping_waivers(self):
        previous_waiver = None
        for waiver in self.waivers:
            if previous_waiver is not None and (
                    waiver.start_date is None
                    or previous_waiver.end_date is None
                    or previous_waiver.start_date == waiver.start_date
                    or previous_waiver.end_date >= waiver.start_date):
                return True
            previous_waiver = waiver
        return False

    def get_modification_options_for_period(self, from_date, to_date):
        matching_modifs = []
        from_date = from_date or datetime.date.max
        to_date = to_date or datetime.date.min
        for modif in self.premium_modifications:
            if (not modif.start_date or modif.start_date <= to_date) and (
                    not modif.end_date or modif.end_date >= from_date):
                matching_modifs.append(modif)
        return matching_modifs

    def get_with_waiver_of_premium(self, name):
        return self.coverage.with_waiver_of_premium

    def get_with_discount_of_premium(self, name):
        return self.coverage.with_discount_of_premium

    def get_with_modifications_of_premium(self, name):
        return self.coverage.with_modifications_of_premium

    def get_modifications_at_date(self, from_date, to_date):
        pool = Pool()
        WaiverPremiumRule = pool.get('waiver_premium.rule')

        mod_option = None
        from_date = from_date or datetime.date.max
        to_date = to_date or datetime.date.min
        matching_options = self.get_modification_options_for_period(
            from_date, to_date)
        premium_modifications = []
        contains_waiver = False
        for mod_option in matching_options:
            if isinstance(
                    mod_option.modification_rule, WaiverPremiumRule):
                if contains_waiver:
                    Date = Pool().get('ir.date')
                    self.append_functional_error(
                        ValidationError(gettext(
                                'contract_waiver_premium.msg_too_many_waivers',
                                option=self.rec_name,
                                start=Date.date_as_string(from_date),
                                end=Date.date_as_string(to_date))))
                    return []
                contains_waiver = True
            behaviour = \
                mod_option.modification_rule.invoice_line_period_behaviour
            if behaviour in {'one_day_overlap', 'proportion'}:
                premium_modifications.append(mod_option)
            elif (behaviour == 'total_overlap'
                    and (not mod_option.end_date
                        or mod_option.end_date >= to_date)
                    and (not mod_option.start_date
                        or mod_option.start_date <= from_date)):
                premium_modifications.append(mod_option)
        return premium_modifications

    def get_premium_modifications_for_invoice_line(self, line):
        return self.get_modifications_at_date(
            line.coverage_start, line.coverage_end)

    def get_context_modification_invoice_line(self, modification_option, line):
        pool = Pool()
        WaiverPremium = pool.get('contract.waiver_premium')

        premium_modification = modification_option.premium_modification
        return {
            'is_waiver': isinstance(premium_modification, WaiverPremium),
            'start_date': modification_option.start_date,
            'end_date': modification_option.end_date,
            'discount_description': modification_option.rec_name,
            }

    def calculate_automatic_waiver_duration(self):
        if not self.with_waiver_of_premium:
            return [None, None]
        exec_context = {'date': self.start_date}
        self.init_dict_for_rule_engine(exec_context)
        return self.coverage.waiver_premium_rule[0].calculate_duration_rule(
            exec_context)

    def calculate_automatic_discount_duration(self, rule):
        exec_context = {'date': self.start_date}
        self.init_dict_for_rule_engine(exec_context)
        return rule.calculate_duration_rule(exec_context)

    def with_automatic_modifications(self):
        return any(r.automatic
            for r in self.coverage.premium_modification_rules)


class CommercialDiscountContract(model.CoogSQL, model.CoogView):
    "Commercial Discount - Contract"
    __name__ = 'commercial_discount-contract'

    discount = fields.Many2One('commercial_discount', "Discount",
        required=True, ondelete='CASCADE')
    contract = fields.Many2One('contract', "Contract",
        required=True, ondelete='CASCADE', select=True)
    start_date = fields.Date("Start Date",
        domain=['OR',
            ('start_date', '=', None),
            ('start_date', '<=', Eval('end_date')),
            ],
        depends=['end_date'])
    end_date = fields.Date("End Date",
        domain=['OR',
            ('end_date', '=', None),
            ('end_date', '>=', Eval('start_date')),
            ],
        depends=['start_date'])
