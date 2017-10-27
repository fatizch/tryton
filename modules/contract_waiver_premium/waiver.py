# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond import backend
from trytond.pyson import Bool, Eval, Or
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'WaiverPremiumOption',
    'WaiverPremium',
    ]


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
        if not migrate:
            return

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


class WaiverPremium(model.CoogSQL, model.CoogView):
    'Waiver Premium'

    __name__ = 'contract.waiver_premium'

    start_date = fields.Function(
        fields.Date('Start Date'),
        'get_start_date')
    end_date = fields.Function(
        fields.Date('End Date'),
        'get_end_date')
    options = fields.Many2Many('contract.waiver_premium-contract.option',
        'waiver', 'option', 'Options', readonly=True)
    waiver_options = fields.One2Many('contract.waiver_premium-contract.option',
        'waiver', 'Waiver Options', delete_missing=True, readonly=True)
    options_names = fields.Function(
        fields.Char('Options Names'),
        'get_options_names')
    contract = fields.Many2One('contract', 'Contract', required=True,
        select=True, ondelete='CASCADE', readonly=True)
    automatic = fields.Boolean('Automatic', readonly=True)

    @classmethod
    def __setup__(cls):
        super(WaiverPremium, cls).__setup__()
        cls._buttons.update({
                'end_waiver': {
                    'invisible': Or(Bool(Eval('automatic')),
                        Bool(Eval('end_date'))),
                    },
                })

    @classmethod
    def view_attributes(cls):
        return super(WaiverPremium, cls).view_attributes() + [(
                '/form/group/button[@name="end_waiver"]',
                'states',
                {'invisible': True}
                )]

    @classmethod
    @model.CoogView.button_action(
        'contract_waiver_premium.act_set_waiver_end_date_wizard')
    def end_waiver(cls, waivers):
        pass

    def get_options_names(self, name):
        return ', '.join([x.rec_name for x in self.options])

    @staticmethod
    def get_waiver_line_fields():
        return ['type', 'description', 'origin', 'quantity',
            'unit', 'unit_price', 'invoice_type', 'coverage_start',
            'coverage_end', 'coverage']

    @staticmethod
    def get_waiver_line_detail_fields():
        return ['rated_entity', 'frequency', 'rate',
            'premium', 'loan', 'coverage']

    def get_start_date(self, name=None):
        start_dates = [x.start_date for x in self.waiver_options
            if x.start_date]
        if start_dates:
            return min(start_dates)

    def get_end_date(self, name=None):
        end_dates = [x.end_date for x in self.waiver_options if x.end_date]
        if end_dates:
            return max(end_dates)
