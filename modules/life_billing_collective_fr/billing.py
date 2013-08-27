from trytond.pyson import Eval

from trytond.modules.coop_utils import model, fields, utils

__all__ = [
    'RateLine',
    ]


class RateLine(model.CoopSQL, model.CoopView):
    'Rate Line'

    __name__ = 'billing.rate_line'

    contract = fields.Many2One('contract.contract', 'Contract',
        ondelete='CASCADE',
        states={'invisible': ~~Eval('parent')})
    covered_element = fields.Many2One('ins_contract.covered_element',
        'Covered Element', ondelete='RESTRICT')
    option = fields.Many2One('contract.subscribed_option', 'Option')
    tranche = fields.Many2One('tranche.tranche', 'Tranche',
        ondelete='RESTRICT', states={'invisible': ~Eval('tranche')})
    index = fields.Many2One('table.table_def', 'Index',
        states={'invisible': ~Eval('index')}, ondelete='RESTRICT')
    parent = fields.Many2One('billing.rate_line', 'Parent', ondelete='CASCADE')
    childs = fields.One2Many('billing.rate_line', 'parent', 'Childs',
        states={'invisible': ~~Eval('tranche')})
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    rate = fields.Numeric('Rate')
    sum_rate = fields.Function(
        fields.Numeric('Sum Rate', digits=(16, 4)),
        'get_sum_rate')

    def add_child(self):
        if utils.is_none(self, 'childs'):
            self.childs = []
        child_line = self.__class__()
        self.childs.append(child_line)
        return child_line

    def add_indexed_rate_line(self, tranche=None, index=None):
        child_line = self.add_child()
        child_line.tranche = tranche
        child_line.index = index
        return child_line

    def add_option_rate_line(self, option, rate):
        child_line = self.add_child()
        child_line.option = option
        child_line.rate = rate
        return child_line

    def get_rec_name(self, name):
        if self.covered_element:
            return self.covered_element.rec_name
        elif self.option:
            return self.option.rec_name
        elif self.tranche:
            return self.tranche.rec_name
        elif self.index:
            return self.index.rec_name

    def get_sum_rate(self, name):
        if self.contract:
            return None
        return (self.rate if self.rate else 0) + sum(
            map(lambda x: x.sum_rate, self.childs))
