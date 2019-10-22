# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond import backend
from trytond.pyson import Bool, Eval, Or
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, fields


class PremiumModificationMixin:

    start_date = fields.Function(
        fields.Date('Start Date'),
        'get_start_date')
    end_date = fields.Function(
        fields.Date('End Date'),
        'get_end_date')
    options_names = fields.Function(
        fields.Char('Options Names'),
        'get_options_names')
    contract = fields.Many2One('contract', 'Contract', required=True,
        select=True, ondelete='CASCADE', readonly=True)
    automatic = fields.Boolean('Automatic', readonly=True)

    def get_options_names(self, name):
        return ', '.join([x.rec_name for x in self.options])

    def get_start_date(self, name=None):
        start_dates = [x.start_date
            for x in self.premium_modification_options
            if x.start_date]
        if start_dates:
            return min(start_dates)

    def get_end_date(self, name=None):
        end_dates = [x.end_date
            for x in self.premium_modification_options
            if x.end_date]
        if end_dates:
            return max(end_dates)

    @property
    def premium_modification_options(self):
        raise NotImplementedError

    @premium_modification_options.setter
    def premium_modification_options(self, options):
        raise NotImplementedError


class WaiverPremiumOption(model.CoogSQL, model.CoogView):
    'Waiver Premium Option'

    __name__ = 'contract.waiver_premium-contract.option'

    option = fields.Many2One('contract.option', 'Option', required=True,
        ondelete='CASCADE', select=True, readonly=True)
    waiver = fields.Many2One('contract.waiver_premium', 'Waiver',
        required=True, ondelete='CASCADE', select=True, readonly=True)
    start_date = fields.Date('Start Date', readonly=True)
    end_date = fields.Date('End Date', readonly=True,
        domain=['OR', ('end_date', '>=', Eval('start_date')),
            ('end_date', '=', None)],
        depends=['start_date'])

    @classmethod
    def __register__(cls, module):
        # Migration from 1.12 Move Dates from WaiverPremium
        TableHandler = backend.get('TableHandler')
        WaiverPremium = Pool().get('contract.waiver_premium')
        waiver_h = TableHandler(WaiverPremium)
        migrate = waiver_h.column_exist('start_date')
        super(WaiverPremiumOption, cls).__register__(module)
        if migrate:
            waiver_premium_option = cls.__table__()
            waiver = WaiverPremium.__table__()
            cursor = Transaction().connection.cursor()
            update_data = waiver.join(waiver_premium_option, condition=(
                    waiver_premium_option.waiver == waiver.id)
                ).select(waiver.id, waiver.start_date, waiver.end_date)
            cursor.execute(*waiver_premium_option.update(
                    columns=[waiver_premium_option.start_date,
                        waiver_premium_option.end_date],
                    values=[update_data.start_date, update_data.end_date],
                    from_=[update_data],
                    where=(waiver_premium_option.waiver == update_data.id)))

            waiver_h.drop_column('start_date')
            waiver_h.drop_column('end_date')

    @property
    def premium_modification(self):
        return self.waiver

    @property
    def modification_rule(self):
        return self.option.coverage.waiver_premium_rule[0]

    @modification_rule.setter
    def modification_rule(self, rule):
        pass


class WaiverPremium(
        PremiumModificationMixin, model.CoogSQL, model.CoogView):
    'Waiver Premium'

    __name__ = 'contract.waiver_premium'

    options = fields.Many2Many('contract.waiver_premium-contract.option',
        'waiver', 'option', 'Options', readonly=True)
    waiver_options = fields.One2Many('contract.waiver_premium-contract.option',
        'waiver', 'Waiver Options', delete_missing=True, readonly=True)

    @classmethod
    def __setup__(cls):
        super(WaiverPremium, cls).__setup__()
        cls._buttons.update({
                'end_waiver': {
                    'invisible': Or(Bool(Eval('automatic')),
                        Bool(Eval('end_date'))),
                    },
                'end_discount': {
                    'invisible': Or(Bool(Eval('automatic')),
                        Bool(Eval('end_date'))),
                    },
                })

    @classmethod
    def view_attributes(cls):
        return super(WaiverPremium, cls).view_attributes() + [(
                '/form/group/button[starts-with(@name, "end_")]',
                'states',
                {'invisible': True}
                )]

    @classmethod
    @model.CoogView.button_action(
        'contract_premium_modification.act_set_waiver_end_date_wizard')
    def end_waiver(cls, modifications):
        pass

    @classmethod
    @model.CoogView.button_action(
        'contract_premium_modification.act_set_waiver_end_date_wizard')
    def end_discount(cls, modifications):
        pass

    @property
    def premium_modification_options(self):
        return self.waiver_options

    @premium_modification_options.setter
    def premium_modification_options(self, options):
        self.waiver_options = options
