from trytond.modules.coop_utils import CoopSQL, CoopView, get_descendents
from trytond.modules.coop_utils import convert_ref_to_obj
from trytond.model import fields
from trytond.modules.insurance_contract import GenericContract

# Needed for getting models
from trytond.pool import Pool

__all__ = [
    'GenericBillLine',
    'Bill'
    ]


class GenericBillLine(CoopSQL, CoopView):
    'Bill Line'

    __name__ = 'ins_contract.billing.generic_line'

    name = fields.Char('Short Description')
    start_date = fields.Date(
        'Start Date',
        required=True)
    end_date = fields.Date(
        'End Date',
        required=True)
    amount_ht = fields.Numeric(
        'Amount HT',
        required=True)
    amount_ttc = fields.Numeric(
        'Amount TTC',
        required=True)
    base_price = fields.Numeric(
        'Base Price')
    on_object = fields.Reference(
        'Target',
        'get_on_object_model'
        )
    for_bill = fields.Many2One(
        'ins_contract.billing.bill',
        'For Bill')

    @staticmethod
    def get_on_object_model():
        f = lambda x: (x, x)
        return [
            f('ins_contract.contract'),
            f('ins_contract.option'),
            f('ins_contract.covered_data')]

    def flat_init(self, start_date, end_date):
        self.start_date = start_date
        self.end_date = end_date
        self.amount_ht = 0
        self.amount_ttc = 0
        self.base_price = 0
        self.name = ''

    def update_from_price_line(self, line):
        number_of_days = \
            self.end_date.toordinal() - self.start_date.toordinal() + 1
        self.amount_ht = line.amount * number_of_days / 365
        self.amount_ttc = line.amount * number_of_days / 365
        self.base_price = line.amount
        self.name = line.get_id()
        self.on_object = line.on_object

    def get_rec_name(self, name):
        if hasattr(self, 'on_object') and self.on_object:
            return convert_ref_to_obj(self.on_object).get_name_for_billing()
        return self.name


class Bill(CoopSQL, CoopView):
    'Bill'

    __name__ = 'ins_contract.billing.bill'

    start_date = fields.Date(
        'Start Date',
        required=True)
    end_date = fields.Date(
        'End Date',
        required=True)
    amount_ht = fields.Numeric(
        'Amount HT',
        required=True)
    amount_ttc = fields.Numeric(
        'Amount TTC',
        required=True)
    lines = fields.One2Many(
        'ins_contract.billing.generic_line',
        'for_bill',
        'Bill Lines')
    for_contract = fields.Reference(
        'Contract',
        'get_contract_models')

    def flat_init(self, start_date, end_date, contract=''):
        self.start_date = start_date
        self.end_date = end_date
        self.lines = []
        self.amount_ht = 0
        self.amount_ttc = 0
        if isinstance(contract, str):
            self.for_contract = contract
        elif isinstance(contract, GenericContract):
            self.for_contract = '%s,%s' % (contract.__name__, contract.id)

    @staticmethod
    def get_contract_models():
        return get_descendents(GenericContract)

    def get_bill_line_model(self):
        return 'ins_contract.billing.generic_line'

    def append_bill_line(self, line):
        self.amount_ht += line.amount_ht
        self.amount_ttc += line.amount_ttc
        self.lines.append(line)

    def init_from_lines(self, lines):
        GenericBillLine = Pool().get(self.get_bill_line_model())
        for start_date, end_date, cur_line in lines:
            bill_line = GenericBillLine()
            bill_line.flat_init(start_date, end_date)
            bill_line.update_from_price_line(cur_line)
            self.append_bill_line(bill_line)
