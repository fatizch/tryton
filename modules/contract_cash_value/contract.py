# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, fields


__metaclass__ = PoolMeta

__all__ = [
    'CashValueCollection',
    'Contract',
    ]


class CashValueCollection(model.CoopView, model.CoopSQL):
    'Cash Value Collection'

    __name__ = 'contract.cash_value.collection'

    reception_date = fields.Date('Reception Date', states={'required': True})
    amount = fields.Numeric('Amount')
    last_update = fields.Date('Last update')
    updated_amount = fields.Numeric('Updated Amount')
    kind = fields.Selection([('payment', 'Payment')], 'Kind')
    contract = fields.Many2One('contract', 'Contract',
        ondelete='CASCADE', required=True, select=True)
    # collection = fields.Many2One('collection', 'Collection',
    #     ondelete='CASCADE', states={'required': True})

    def init_dict_for_rule_engine(self, the_dict):
        the_dict['cash_value_collection'] = self

    @classmethod
    def update_values(cls, values, date, force=False, save=True):
        if not values:
            return 0
        good_coverage = None
        for elem in values[0].contract.offered.coverages:
            if elem.family == 'cash_value':
                good_coverage = elem
                break
        if not good_coverage:
            raise Exception('Cash Value component not detected on product %s' %
                values[0].contract.offered.rec_name)
        # No direct link to the covered_data, got to find it manually
        good_data = None
        for elem in values[0].contract.options:
            if not elem.offered == good_coverage:
                continue
            for data in elem.covered_data:
                if data.is_active_at_date(date):
                    good_data = data
                    break
            break
        if not good_data:
            raise Exception('Contract %s has no active cash value coverage' %
                values[0].contract.rec_name)
        result = 0
        for elem in values:
            if not force and elem.last_update >= date:
                continue
            the_dict = {}
            elem.init_dict_for_rule_engine(the_dict)
            good_data.init_dict_for_rule_engine(the_dict)
            the_dict['date'] = date
            # elem.updated_amount = good_coverage.get_result(
            #     'actualized_cash_value', the_dict).result
            elem.last_update = date
            result += elem.updated_amount
            if save:
                elem.save()
        return result


_STATES = {
    'readonly': Eval('status') != 'quote',
    }
_DEPENDS = ['status']


class Contract:
    'Contract'

    __name__ = 'contract'

    cash_value_collections = fields.One2Many('contract.cash_value.collection',
        'contract', 'Collections', states=_STATES, depends=_DEPENDS,
        delete_missing=True)
    is_cash_value = fields.Function(fields.Boolean('Is Cash Value'),
        'get_is_cash_value')

    @classmethod
    def view_attributes(cls):
        return super(Contract, cls).view_attributes() + [(
                '/form/notebook/page[@id="cash_value_collections"]',
                'states',
                {'invisible': ~Eval('is_cash_value')}
                )]

    def get_is_cash_value(self, name):
        return self.offered.is_cash_value
