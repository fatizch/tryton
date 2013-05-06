from trytond.modules.coop_utils import utils, abstract
from trytond.modules.coop_utils import date
from trytond.modules.coop_utils import model, fields
from trytond.modules.insurance_product import product

# Needed for getting models
from trytond.pool import Pool

__all__ = [
    'GenericBillLine',
    'Bill'
]


class GenericBillLine(model.CoopSQL, model.CoopView):
    'Bill Line'

    __name__ = 'ins_contract.billing.generic_line'

    name = fields.Char('Short Description')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    amount_ht = fields.Numeric('Amount HT')
    amount_ttc = fields.Numeric('Amount TTC')
    base_price = fields.Numeric('Base Price')
    on_object = fields.Reference('Target', 'get_on_object_model')
    master = fields.Reference(
        'Master',
        [('ins_contract.billing.bill', 'Bill'),
            ('ins_contract.billing.generic_line', 'Line')])
    kind = fields.Selection([
        ('main', 'Node'),
        ('base', 'Base Amount'),
        ('tax', 'Tax'),
        ('fee', 'Fee')], 'Kind')
    childs = fields.One2Many(
        'ins_contract.billing.generic_line', 'master', 'Child Lines')
    node_childs = fields.Function(
        fields.One2Many(
            'ins_contract.billing.generic_line', None, 'Nodes'),
        'get_node_childs')
    detail_childs = fields.Function(
        fields.One2Many(
            'ins_contract.billing.generic_line', None, 'Details'),
        'get_detail_childs')

    @staticmethod
    def get_on_object_model():
        f = lambda x: (x, x)
        res = [
            f(''),
            f('ins_product.product'),
            f('ins_product.coverage'),
            f('ins_contract.contract'),
            f('ins_contract.option')]
        res += utils.get_descendents('ins_contract.covered_data')
        return res

    def get_detail_childs(self, name):
        res = []
        for elem in self.childs:
            if elem.kind != 'main':
                res.append(elem)
        return abstract.WithAbstract.serialize_field(res)

    def get_node_childs(self, name):
        res = []
        for elem in self.childs:
            if elem.kind == 'main':
                res.append(elem)
        return abstract.WithAbstract.serialize_field(res)

    def flat_init(self, start_date, end_date):
        self.start_date = start_date
        self.end_date = end_date
        self.amount_ht = 0
        self.amount_ttc = 0
        self.base_price = 0
        self.name = ''

    def update_from_price_line(self, line, number_of_days, base_days):
        LineModel = Pool().get(self.__name__)
        self.childs = []
        for elem in line.all_lines:
            sub_line = LineModel()
            sub_line.flat_init(self.start_date, self.end_date)
            sub_line.update_from_price_line(elem, number_of_days, base_days)
            self.childs.append(sub_line)
        if line.kind != 'tax':
            self.amount_ht = line.amount * number_of_days / base_days
            self.amount_ttc = self.amount_ht + line.get_total_detail('tax') \
                * number_of_days / base_days
        else:
            self.amount_ht = 0
            self.amount_ttc = line.amount * number_of_days / base_days
        self.base_price = line.amount
        self.kind = line.kind
        self.name = line.get_id()
        self.on_object = line.on_object

    def get_rec_name(self, name):
        if hasattr(self, 'on_object') and self.on_object:
            return utils.convert_ref_to_obj(
                self.on_object).get_name_for_billing()
        if hasattr(self, 'name') and self.name:
            return self.kind + ' - ' + self.name
        return self.kind

    def is_main_line(self):
        return hasattr(self, 'on_object') and self.on_object and \
            self.on_object.split(',')[0] in (
                'ins_product.product',
                'ins_product.coverage')

    def get_total_detail(self, name):
        res = 0
        for line in self.detail_childs:
            if line.kind == name:
                res += line.amount_ht
        return res

    def get_number_of_days(self):
        return self.end_date.toordinal() - self.start_date.toordinal() + 1


class Bill(model.CoopSQL, model.CoopView):
    'Bill'

    __name__ = 'ins_contract.billing.bill'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    amount_ht = fields.Numeric('Amount HT', required=True)
    amount_ttc = fields.Numeric('Amount TTC')
    lines = fields.One2Many(
        'ins_contract.billing.generic_line', 'master', 'Bill Lines',
        order=[('start_date', 'ASC'), ('name', 'ASC')])
    contract = fields.Many2One('ins_contract.contract', 'Contract')
    bill_details = fields.Function(
        fields.One2Many(
            'ins_contract.billing.generic_line', None, 'Bill Details'),
        'get_bill_details')

    def get_bill_details(self, name):
        DetailLine = Pool().get('ins_contract.billing.generic_line')
        existing = {}
        res = {}
        for line in self.lines:
            for elem in line.childs:
                if elem.kind != 'main':
                    if (elem.kind, elem.name) in existing:
                        good_line = existing[(elem.kind, elem.name)]
                        good_line.amount_ht += elem.amount_ht
                        good_line.amount_ttc += elem.amount_ttc
                    else:
                        new_line = DetailLine()
                        new_line.kind = elem.kind
                        new_line.name = elem.name
                        new_line.amount_ht = elem.amount_ht
                        new_line.amount_ttc = elem.amount_ttc
                        if elem.kind in res:
                            res[elem.kind].append(new_line)
                        else:
                            res[elem.kind] = [new_line]
                        existing[(elem.kind, elem.name)] = new_line
        details = []
        for k, v in res.iteritems():
            details.extend(v)
        return abstract.WithAbstract.serialize_field(details)

    def flat_init(self, start_date, end_date, contract):
        self.start_date = start_date
        self.end_date = end_date
        self.lines = []
        self.amount_ht = 0
        self.amount_ttc = 0
        self.contract = contract

    def append_bill_line(self, line):
        self.amount_ht += line.amount_ht
        self.amount_ttc += line.amount_ttc
        self.lines.append(line)

    def init_from_lines(self, lines):
        GenericBillLine = Pool().get('ins_contract.billing.generic_line')
        for start_date, end_date, cur_line in lines:
            number_of_days = date.number_of_days_between(start_date, end_date)
            try:
                frequency_days, _ = cur_line.on_object.get_result(
                    'frequency_days',
                    {'date': start_date},
                    kind='pricing')
            except product.NonExistingRuleKindException:
                frequency_days = 365
            bill_line = GenericBillLine()
            bill_line.flat_init(start_date, end_date)
            bill_line.update_from_price_line(
                cur_line, number_of_days, frequency_days)
            self.append_bill_line(bill_line)
