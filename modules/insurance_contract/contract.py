from trytond.pool import Pool
from trytond.pyson import Eval, If, Or
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model, fields, abstract
from trytond.modules.coop_utils import utils, date, business
from trytond.modules.coop_utils import coop_string
from trytond.modules.contract import contract
from trytond.modules.insurance_product.product import DEF_CUR_DIG
from trytond.modules.insurance_product import product


DELIVERED_SERVICES_STATUSES = [
    ('calculating', 'Calculating'),
    ('not_eligible', 'Not Eligible'),
    ('calculated', 'Calculated'),
    ('delivered', 'Delivered'),
]

IS_PARTY = Eval('item_kind').in_(['person', 'company', 'party'])

__all__ = [
    'InsurancePolicy',
    'ContractHistory',
    'InsuranceSubscribedCoverage',
    'StatusHistory',
    'PriceLine',
    'BillingManager',
    'CoveredElement',
    'CoveredElementPartyRelation',
    'CoveredData',
    'ManagementProtocol',
    'ManagementRole',
    'DeliveredService',
    'Expense',
    'ContractAddress',
    ]


class InsurancePolicy(contract.Contract):
    'Insurance Policy'

    __name__ = 'ins_contract.contract'
    _table = None

    covered_elements = fields.One2ManyDomain(
        'ins_contract.covered_element', 'contract', 'Covered Elements',
        domain=[('parent', '=', None)],
        context={'contract': Eval('id')})
    management = fields.One2Many(
        'ins_contract.management_role', 'contract', 'Management Roles')
    billing_manager = fields.One2Many(
        'ins_contract.billing_manager', 'contract', 'Billing Manager')
    contract_history = fields.One2Many('ins_contract.contract.history',
        'from_object', 'Contract History')
    addresses = fields.One2Many('ins_contract.address', 'contract',
        'Addresses', context={
            'policy_owner': Eval('current_policy_owner'),
            'start_date': Eval('start_date'),
            }, depends=['current_policy_owner'])

    @classmethod
    def get_options_model_name(cls):
        return 'ins_contract.option'

    def calculate_price_at_date(self, date):
        cur_dict = {'date': date}
        self.init_dict_for_rule_engine(cur_dict)
        prices, errs = self.offered.get_result('total_price', cur_dict)
        return (prices, errs)

    def calculate_prices_at_all_dates(self):
        prices = {}
        errs = []
        dates = self.get_dates()
        for cur_date in dates:
            price, err = self.calculate_price_at_date(cur_date)
            if price:
                prices[cur_date.isoformat()] = price
            errs += err
        return prices, errs

    def get_name_for_billing(self):
        return self.offered.name + ' - Base Price'

    def check_sub_elem_eligibility(self, at_date=None, ext=None):
        errors = []
        if not at_date:
            at_date = self.start_date
        options = dict(
            [(option.offered.code, option) for option in self.options])
        res, errs = (True, [])
        for covered_element in self.covered_elements:
            for covered_data in covered_element.covered_data:
                if (covered_data.start_date > at_date
                        or hasattr(covered_data, 'end_date') and
                        covered_data.end_date and
                        covered_data.end_date > at_date):
                    continue
                eligibility, errors = covered_data.get_coverage().get_result(
                    'sub_elem_eligibility',
                    {
                        'date': at_date,
                        'sub_elem': covered_element,
                        'data': covered_data,
                        'option': options[covered_data.get_coverage().code]
                    })
                res = res and (not eligibility or eligibility.eligible)
                if eligibility:
                    errs += eligibility.details
                errs += errors
        return (res, errs)

    @classmethod
    def get_offered_name(cls):
        return 'ins_product.product', 'Product'

    def check_at_least_one_covered(self):
        errors = []
        for covered in self.covered_elements:
            found, errors = covered.check_at_least_one_covered(errors)
            if found:
                break
        if errors:
            return False, errors
        return True, ()

    def init_covered_elements(self):
        options = dict([(o.offered.code, o) for o in self.options])
        for elem in self.covered_elements:
            CoveredData = utils.get_relation_model(elem, 'covered_data')
            if (hasattr(elem, 'covered_data') and elem.covered_data):
                existing_datas = dict([
                    (data.get_coverage().code, data)
                    for data in elem.covered_data])
            else:
                existing_datas = {}
            elem.covered_data = []
            to_delete = [data for data in existing_datas.itervalues()]
            good_datas = []
            for code, option in options.iteritems():
                if code in existing_datas:
                    existing_datas[code].init_complementary_data()
                    good_datas.append(existing_datas[code])
                    to_delete.remove(existing_datas[code])
                    continue
                else:
                    good_data = CoveredData()
                    good_data.init_from_option(option)
                    good_data.init_from_covered_element(elem)
                    good_data.status_selection = True
                    good_datas.append(good_data)
            CoveredData.delete(to_delete)
            elem.covered_data = good_datas
            elem.save()
        return True, ()

    def init_options_from_covered_elements(self):
        if self.options:
            return True, ()
        self.options = []
        for coverage in self.offered.coverages:
            option = utils.instanciate_relation(self, 'options')
            option.init_from_offered(coverage, self.start_date)
            for covered_element in self.covered_elements:
                option.append_covered_data(covered_element)
            self.options.append(option)
        return True, ()

    def get_sender(self):
        return self.get_management_role('contract_manager').protocol.party

    def get_management_role(self, role, good_date=None):
        if not good_date:
            good_date = utils.today()
        Role = Pool().get('ins_contract.management_role')
        domain = [
            utils.get_versioning_domain(good_date, do_eval=False),
            ('protocol.kind', '=', role)]
        good_roles = Role.search(domain)
        if not good_roles:
            return None
        return good_roles[0]

    def new_billing_manager(self):
        return utils.instanciate_relation(self, 'billing_manager')

    def init_billing_manager(self):
        if not (hasattr(self, 'billing_manager') and
                self.billing_manager):
            bm = self.new_billing_manager()
            bm.contract = self
            self.billing_manager = [bm]

    def on_change_complementary_data(self):
        return {'complementary_data': self.offered.get_result(
            'calculated_complementary_datas',
            {'date': self.start_date, 'contract': self})[0]}

    def get_next_renewal_date(self):
        return utils.add_frequency('yearly', self.start_date)


class InsuranceSubscribedCoverage(contract.SubscribedCoverage):
    'Subscribed Coverage'

    __name__ = 'ins_contract.option'
    _table = None

    covered_data = fields.One2ManyDomain(
        'ins_contract.covered_data', 'option', 'Covered Data',
        domain=[('covered_element.parent', '=', None)])
    deductible_duration = fields.Many2One('ins_product.deductible_duration',
        'Deductible Duration', states={
            'invisible': ~Eval('possible_deductible_duration'),
            # 'required': ~~Eval('possible_deductible_duration'),
            }, domain=[('id', 'in', Eval('possible_deductible_duration'))],
        depends=['possible_deductible_duration'])
    possible_deductible_duration = fields.Function(
        fields.Many2Many(
            'ins_product.deductible_duration', None, None,
            'Possible Deductible Duration', states={'invisible': True}),
        'get_possible_deductible_duration')

    @classmethod
    def get_contract_model_name(cls):
        return 'ins_contract.contract'

    def get_name_for_billing(self):
        return self.get_coverage().name + ' - Base Price'

    @classmethod
    def get_offered_name(cls):
        return 'ins_product.coverage', 'Coverage'

    def append_covered_data(self, covered_element=None):
        res = utils.instanciate_relation(self.__class__, 'covered_data')
        if not hasattr(self, 'covered_data'):
            self.covered_data = []
        self.covered_data.append(res)
        res.init_from_option(self)
        res.init_from_covered_element(covered_element)
        return res

    def get_covered_data(self):
        raise NotImplementedError

    def get_coverage_amount(self):
        raise NotImplementedError

    def get_possible_deductible_duration(self, name):
        try:
            durations = self.offered.get_result(
                'possible_deductible_duration',
                {'date': self.start_date, 'scope': 'coverage'},
                kind='deductible')[0]
            return [x.id for x in durations] if durations else []
        except product.NonExistingRuleKindException:
            return []


class StatusHistory(model.CoopSQL, model.CoopView):
    'Status History'

    __name__ = 'ins_contract.status_history'

    reference = fields.Reference('Reference', 'get_possible_reference')
    status = fields.Selection(contract.OPTIONSTATUS, 'Status',
        selection_change_with=['reference'])
    sub_status = fields.Char('Sub Status')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

    @classmethod
    def get_possible_reference(cls):
        res = []
        res.append(('ins_contract.contract', 'Contract'))
        res.append(('ins_contract.option', 'Option'))
        return res

    def init_from_reference(self, reference, to_status, at_date,
            sub_status=None):
        self.status = to_status
        self.start_date = at_date
        self.sub_status = sub_status
        if not reference.status_history:
            return
        previous_status = reference.status_history[-1]
        if not previous_status:
            return
        previous_status.end_date = max(date.add_day(at_date, -1),
            previous_status.start_date)
        if previous_status == 'active':
            reference.end_date = previous_status.end_date


class ContractHistory(model.ObjectHistory):
    'Contract History'

    __name__ = 'ins_contract.contract.history'

    offered = fields.Many2One('ins_product.product', 'Product',
        datetime_field='date')
    start_date = fields.Date('Effective Date')
    end_date = fields.Date('End Date')
    start_management_date = fields.Date('Management Date')
    status = fields.Selection('get_possible_status', 'Status')
    summary = fields.Function(fields.Text('Summary'), 'get_summary')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'get_currency_id')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_currency_digits')
    options = fields.Function(
        fields.One2Many('ins_contract.option', None, 'Options',
            datetime_field='date'),
        'get_options')
    subscriber = fields.Many2One('party.party', 'Subscriber',
        datetime_field='date')

    @classmethod
    def get_object_model(cls):
        return 'ins_contract.contract'

    @classmethod
    def get_object_name(cls):
        return 'Contract'

    @staticmethod
    def get_possible_status():
        return Pool().get('ins_contract.contract').get_possible_status()

    def get_options(self, name):
        Option = Pool().get('ins_contract.option')
        options = Option.search([
                ('contract', '=', self.from_object.id),
                ])
        return [o.id for o in options]


class PriceLine(model.CoopSQL, model.CoopView):
    'Price Line'

    __name__ = 'ins_contract.price_line'

    amount = fields.Numeric('Amount')
    name = fields.Char('Short Description')
    master = fields.Many2One('ins_contract.price_line', 'Master Line')
    kind = fields.Selection(
        [
            ('main', 'Line'),
            ('base', 'Base'),
            ('tax', 'Tax'),
            ('fee', 'Fee')
        ], 'Kind', readonly='True')
    on_object = fields.Reference('Priced object', 'get_line_target_models')
    billing_manager = fields.Many2One(
        'ins_contract.billing_manager', 'Billing Manager')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    all_lines = fields.One2Many(
        'ins_contract.price_line', 'master', 'Lines', readonly=True)
    taxes = fields.Function(fields.Numeric('Taxes'), 'get_total_taxes')
    amount_for_display = fields.Function(
        fields.Numeric('Amount'), 'get_amount_for_display')
    start_date_calculated = fields.Function(fields.Date(
        'Start Date'), 'get_start_date')
    end_date_calculated = fields.Function(fields.Date(
        'End Date'), 'get_end_date')
    details = fields.One2ManyDomain(
        'ins_contract.price_line', 'master', 'Details', domain=[
            ('kind', '!=', 'main')], readonly=True)
    child_lines = fields.One2ManyDomain(
        'ins_contract.price_line', 'master', 'Sub-Lines', domain=[
            ('kind', '=', 'main')], readonly=True)

    def get_id(self):
        if hasattr(self, 'on_object') and self.on_object:
            return self.on_object.get_name_for_billing()
        if hasattr(self, 'name') and self.name:
            return self.name
        return self.kind

    def init_values(self):
        if not hasattr(self, 'name') or not self.name:
            self.name = ''
        self.amount = 0
        self.all_lines = []

    def init_from_result_line(self, line):
        if not line:
            return
        PLModel = Pool().get(self.__name__)
        self.init_values()
        self.amount = line.value
        for (kind, code), value in line.details.iteritems():
            detail_line = PLModel()
            detail_line.name = code
            detail_line.amount = value
            detail_line.kind = kind
            self.all_lines.append(detail_line)
        if line.desc:
            for elem in line.desc:
                child_line = PLModel()
                child_line.init_from_result_line(elem)
                self.all_lines.append(child_line)
        if not self.name:
            if line.on_object:
                self.name = utils.convert_ref_to_obj(
                    line.on_object).get_name_for_billing()
            else:
                self.name = line.name
        if line.on_object:
            self.on_object = line.on_object

    @staticmethod
    def default_kind():
        return 'main'

    def get_total_taxes(self, field_name):
        res = self.get_total_detail('tax')
        if res:
            return res

    def get_total_detail(self, name):
        res = 0
        for line in self.details:
            if line.kind == name:
                res += line.amount
        return res

    def get_amount_for_display(self, field_name):
        res = self.amount
        if not res:
            return None
        return res

    def get_start_date(self, field_name):
        if hasattr(self, 'start_date') and self.start_date:
            return self.start_date
        if self.master:
            return self.master.start_date_calculated

    def get_end_date(self, field_name):
        if hasattr(self, 'end_date') and self.end_date:
            return self.end_date
        if self.master:
            return self.master.end_date_calculated

    @classmethod
    def get_line_target_models(cls):
        f = lambda x: (x, x)
        res = [
            f(''),
            f('ins_product.product'),
            f('ins_product.coverage'),
            f('ins_contract.contract'),
            f('ins_contract.option'),
            f('ins_contract.covered_data')]
        return res

    def is_main_line(self):
        return hasattr(self, 'on_object') and self.on_object and \
            self.on_object.__name__ in (
                'ins_product.product',
                'ins_product.coverage')

    def print_line(self):
        res = [self.get_id()]
        res.append(self.name)
        res.append('%.2f' % self.amount)
        res.append(self.kind)
        res.append('%s' % self.start_date)
        res.append('%s' % self.end_date)
        if self.on_object:
            res.append(self.on_object.__name__)
        else:
            res.append('')
        return ' - '.join(res)


class BillingManager(model.CoopSQL, model.CoopView):
    'Billing Manager'
    '''
        This object will manage all billing-related content on the contract.
        It will be the target of all sql requests for automated bill
        calculation, lapsing, etc...
    '''
    __name__ = 'ins_contract.billing_manager'

    contract = fields.Many2One('ins_contract.contract', 'Contract')
    next_billing_date = fields.Date('Next Billing Date')
    prices = fields.One2Many(
        'ins_contract.price_line', 'billing_manager', 'Prices')

    def store_prices(self, prices):
        if not prices:
            return
        PriceLine = Pool().get(self.get_price_line_model())
        to_delete = []
        if hasattr(self, 'prices') and self.prices:
            for price in self.prices:
                to_delete.append(price)
        result_prices = []
        dates = [utils.to_date(key) for key in prices.iterkeys()]
        end_date = self.contract.get_next_renewal_date()
        if not end_date in dates:
            dates.append(end_date)
        dates.sort()
        for cur_date, price in prices.iteritems():
            pl = PriceLine()
            pl.name = cur_date
            details = []
            for cur_price in price:
                detail = PriceLine()
                detail.init_from_result_line(cur_price)
                details.append(detail)
            pl.all_lines = details
            pl.start_date = utils.to_date(cur_date)
            try:
                pl.end_date = dates[dates.index(pl.start_date) + 1] + \
                    datetime.timedelta(days=-1)
            except IndexError:
                pass
            result_prices.append(pl)
        self.prices = result_prices

        self.save()

        PriceLine.delete(to_delete)

    @classmethod
    def get_price_line_model(cls):
        return cls._fields['prices'].model_name

    def get_product_frequency(self, at_date):
        res, errs = self.contract.offered.get_result(
            'frequency',
            {'date': at_date})
        if not errs:
            return res

    def next_billing_dates(self):
        cur_date = max(utils.today(), self.contract.start_date)
        return (
            cur_date,
            utils.add_frequency(self.get_product_frequency(date), date))

    def get_bill_model(self):
        return 'ins_contract.billing.bill'

    def get_prices_dates(self):
        return [elem.start_date for elem in self.prices].append(
            self.prices[-1].end_date)

    def create_price_list(self, start_date, end_date):
        dated_prices = [
            (elem.start_date, elem.end_date or end_date, elem)
            for elem in self.prices
            if (
                (elem.start_date >= start_date and elem.start_date <= end_date)
                or (
                    elem.end_date and elem.end_date >= start_date
                    and elem.end_date <= end_date))]
        print str([x.name for x in dated_prices[1][2].all_lines])
        return dated_prices

    def flatten(self, prices):
        # prices is a list of tuples (start, end, price_line).
        # aggregate returns one price_line which aggregates all of the
        # provided price_lines, in which all lines have set start and end dates
        lines_desc = []
        for elem in prices:
            if elem[2].is_main_line():
                if elem[2].amount:
                    lines_desc.append(elem)
            else:
                lines_desc += self.flatten(
                    [(elem[0], elem[1], line) for line in elem[2].child_lines])
        return lines_desc

    def lines_as_dict(self, lines):
        # lines are a list of tuples (start, end, price_line).
        # This function organizes the lines in a dict which uses the price_line
        # id (get_id) as keys
        the_dict = {}
        for elem in lines:
            id = elem[2].get_id()
            if id in the_dict:
                the_dict[id].append(elem)
            else:
                the_dict[id] = [elem]
        return the_dict

    def bill(self, start_date, end_date):
        Bill = Pool().get(self.get_bill_model())
        the_bill = Bill()
        the_bill.flat_init(start_date, end_date, self.contract)
        price_list = self.create_price_list(start_date, end_date)
        price_lines = self.flatten(price_list)
        the_bill.init_from_lines(price_lines)
        return the_bill


class CoveredElement(model.CoopSQL, model.CoopView):
    'Covered Element'
    '''
        Covered elements represents anything which is covered by at least one
        option of the contract.
        It has a list of covered datas which describes which options covers
        element and in which conditions.
        It could contains recursively sub covered element (fleet or population)
    '''

    __name__ = 'ins_contract.covered_element'

    contract = fields.Many2One(
        'ins_contract.contract', 'Contract', ondelete='CASCADE')
    #We need to put complementary data in depends, because the complementary
    #data are set through on_change_with and the item desc can be set on an
    #editable tree, or we can not display for the moment dictionnary in tree
    item_desc = fields.Many2One(
        'ins_product.item_desc', 'Item Desc',
        on_change=['item_desc', 'complementary_data', 'party'],
        domain=[If(
                ~~Eval('possible_item_desc'),
                ('id', 'in', Eval('possible_item_desc')),
                ())
            ], depends=['possible_item_desc', 'complementary_data'])
    possible_item_desc = fields.Function(
        fields.Many2Many('ins_product.item_desc', None, None,
            'Possible Item Desc', states={'invisible': True}),
        'get_possible_item_desc_ids')
    covered_data = fields.One2Many(
        'ins_contract.covered_data', 'covered_element', 'Covered Element Data')
    name = fields.Char('Name',
        states={'invisible': IS_PARTY})
    parent = fields.Many2One('ins_contract.covered_element', 'Parent')
    sub_covered_elements = fields.One2Many(
        'ins_contract.covered_element', 'parent', 'Sub Covered Elements',
        states={'invisible': Eval('item_kind') == 'person'},
        domain=[('covered_data.option.contract', '=', Eval('contract'))],
        depends=['contract'], context={'_master_covered': Eval('id')})
    complementary_data = fields.Dict('ins_product.complementary_data_def',
        'Complementary Data',
        on_change_with=['item_desc', 'complementary_data'],
        states={'invisible': Or(IS_PARTY, ~Eval('complementary_data'))})
    party_compl_data = fields.Function(
        fields.Dict('ins_product.complementary_data_def', 'Complementary Data',
            on_change_with=['item_desc', 'complementary_data', 'party'],
            states={'invisible': Or(~IS_PARTY, ~Eval('party_compl_data'))}),
        'on_change_with_party_compl_data', 'set_party_compl_data')
    complementary_data_summary = fields.Function(
        fields.Char('Complementary Data', on_change_with=['item_desc']),
        'on_change_with_complementary_data_summary')
    party = fields.Many2One('party.party', 'Actor',
        domain=[
            If(
                Eval('item_kind') == 'person',
                ('is_person', '=', True),
                (),
            ), If(
                Eval('item_kind') == 'company',
                ('is_company', '=', True),
                (),
            )], ondelete='RESTRICT',
        states={
            'invisible': ~IS_PARTY,
            'required': IS_PARTY,
            }, depends=['item_kind'])
    covered_relations = fields.Many2Many(
        'ins_contract.covered_element-party_relation', 'covered_element',
        'party_relation', 'Covered Relations', domain=[
            'OR',
            [('from_party', '=', Eval('party'))],
            [('to_party', '=', Eval('party'))],
            ], depends=['party'],
        states={'invisible': ~IS_PARTY})
    item_kind = fields.Function(
        fields.Char('Item Kind', on_change_with=['item_desc'],
            states={'invisible': True}),
        'on_change_with_item_kind')
    covered_name = fields.Function(
        fields.Char('Name', on_change_with=['party']),
        'on_change_with_covered_name')

    @classmethod
    def get_parent_in_transaction(cls):
        if not '_master_covered' in Transaction().context:
            return None
        GoodModel = Pool().get(cls.__name__)
        return GoodModel(Transaction().context.get('_master_covered'))

    @classmethod
    def default_covered_data(cls):
        master = cls.get_parent_in_transaction()
        if not master:
            return None
        CoveredData = Pool().get('ins_contract.covered_data')
        result = []
        for covered_data in master.covered_data:
            tmp_covered = CoveredData()
            tmp_covered.option = covered_data.option
            tmp_covered.start_date = covered_data.start_date
            tmp_covered.end_date = covered_data.end_date
            result.append(tmp_covered)
        return abstract.WithAbstract.serialize_field(result)

    def get_name_for_billing(self):
        return self.get_rec_name('billing')

    def get_name_for_info(self):
        return self.get_rec_name('info')

    def get_rec_name(self, value):
        if self.party:
            return self.party.rec_name
        res = super(CoveredElement, self).get_rec_name(value)
        if self.item_desc:
            res = coop_string.concat_strings(
                self.item_desc.get_rec_name(value), res)
            if self.name:
                res = '%s : %s' % (res, self.name)
        elif self.name:
            res = coop_string.concat_strings(res, self.name)
        return res

    def get_dates(self, dates=None, start=None, end=None):
        if dates:
            res = set(dates)
        else:
            res = set()
        for data in self.covered_data:
            res.update(data.get_dates(dates, start, end))
        if hasattr(self, 'sub_covered_elements'):
            for sub_elem in self.sub_covered_elements:
                res.update(sub_elem.get_dates(dates, start, end))
        return res

    def check_at_least_one_covered(self, errors=None):
        if not errors:
            errors = []
        found = False
        for data in self.covered_data:
            if data.status == 'active':
                found = True
                break
        if not found:
            errors.append(('need_option', (self.get_rec_name(''))))
        if errors:
            return False, errors
        return True, ()

    def on_change_item_desc(self):
        res = {}
        if not (hasattr(self, 'item_desc') and self.item_desc):
            res['complementary_data'] = {}
        else:
            res['complementary_data'] = \
                self.on_change_with_complementary_data()
        res['item_kind'] = self.on_change_with_item_kind()
        res['party_compl_data'] = self.on_change_with_party_compl_data()
        return res

    def on_change_with_complementary_data(self):
        res = {}
        if (self.item_desc and not self.item_desc.kind in
                ['party', 'person', 'company']):
            return utils.init_complementary_data(
                self.get_complementary_data_def())
        else:
            return res

    def on_change_with_complementary_data_summary(self, name=None):
        if not (hasattr(self, 'complementary_data') and
                self.complementary_data):
            return ''
        return ' '.join([
            '%s: %s' % (x[0], x[1])
            for x in self.complementary_data.iteritems()])

    def get_contract(self):
        if self.contract:
            return self.contract
        elif self.parent:
            return self.parent.get_contract()

    def on_change_with_party_compl_data(self, name=None):
        res = {}
        if not self.party or not (self.item_desc
                and self.item_desc.kind in ['party', 'person', 'company']):
            return res
        for compl_data_def in self.item_desc.complementary_data_def:
            if (self.party
                    and not utils.is_none(self.party, 'complementary_data')
                    and compl_data_def.name in self.party.complementary_data):
                res[compl_data_def.name] = self.party.complementary_data[
                    compl_data_def.name]
            else:
                res[compl_data_def.name] = compl_data_def.get_default_value(
                    None)
        return res

    @classmethod
    def set_party_compl_data(cls, instances, name, vals):
        #We'll update the party complementary data with existing key or add new
        #keys, but if others keys already exist we won't modify them
        Party = Pool().get('party.party')
        for covered in instances:
            if not covered.party:
                continue
            if utils.is_none(covered.party, 'complementary_data'):
                Party.write([covered.party], {'complementary_data': vals})
            else:
                covered.party.complementary_data.update(vals)
                covered.party.save()

    def get_complementary_data_def(self):
        if (self.item_desc
                and not self.item_desc.kind in ['party', 'person', 'company']):
            return self.item_desc.complementary_data_def

    def get_party_compl_data_def(self):
        if (self.item_desc
                and self.item_desc.kind in ['party', 'person', 'company']):
            return self.item_desc.complementary_data_def

    def get_complementary_data_value(self, at_date, value):
        res = utils.get_complementary_data_value(self, 'complementary_data',
            self.get_complementary_data_def(), at_date, value)
        if not res and self.party:
            res = utils.get_complementary_data_value(self.party,
                'complementary_data', self.get_party_compl_data_def(), at_date,
                value)
        return res

    def init_from_party(self, party):
        self.party = party

    def is_party_covered(self, party, at_date, option):
        if party in self.get_covered_parties(at_date):
            for covered_data in self.covered_data:
                if (utils.is_effective_at_date(covered_data, at_date)
                        and covered_data.option == option):
                    return True
        if hasattr(self, 'sub_covered_elements'):
            for sub_elem in self.sub_covered_elements:
                if sub_elem.is_party_covered(party, at_date, option):
                    return True
        return False

    def on_change_with_item_kind(self, name=None):
        if self.item_desc:
            return self.item_desc.kind
        return ''

    def get_covered_parties(self, at_date):
        '''
        Returns all covered persons sharing the same covered data
        for example an employe, his spouse and his children
        '''
        res = []
        if self.party:
            res.append(self.party)
        for relation in self.covered_relations:
            if not utils.is_effective_at_date(relation, at_date):
                continue
            if relation.from_party != self.party:
                res.append(relation.from_party)
            if relation.to_party != self.party:
                res.append(relation.to_party)
        return res

    def on_change_with_covered_name(self, name=None):
        if self.party:
            return self.party.rec_name
        return ''

    @classmethod
    def get_possible_covered_elements(cls, party, at_date):
        #TODO : To enhance with status control on contract and option linked
        domain = [
            ('party', '=', party.id),
            ('covered_data.start_date', '<=', at_date),
            ['OR',
                ['covered_data.end_date', '=', None],
                ['covered_data.end_date', '>=', at_date]]
        ]
        return cls.search([domain])

    def get_currency(self):
        return self.contract.currency if self.contract else None

    @classmethod
    def get_possible_item_desc(cls, contract=None, parent=None):
        if not parent:
            parent = cls.get_parent_in_transaction()
        if parent and parent.item_desc:
            return parent.item_desc.sub_item_descs
        if not contract:
            Contract = Pool().get('ins_contract.contract')
            contract = Contract(Transaction().context.get('contract'))
        if contract and not utils.is_none(contract, 'offered'):
            return contract.offered.item_descriptors
        return []

    def get_possible_item_desc_ids(self, name):
        return [x.id for x in
            self.get_possible_item_desc(self.contract, self.parent)]

    @classmethod
    def default_item_desc(cls):
        item_descs = cls.get_possible_item_desc()
        if len(item_descs) == 1:
            return item_descs[0].id

    @classmethod
    def default_possible_item_desc(cls):
        return [x.id for x in cls.get_possible_item_desc()]

    def match_key(self, from_name=None, party=None):
        if (from_name and self.name == from_name
                or party and self.party == party):
            return True
        if party:
            for relation in self.covered_relations:
                if relation.from_party == party or relation.to_party == party:
                    return self

    def get_covered_element(self, from_name=None, party=None):
        if self.match_key(from_name, party):
            return self
        for sub_element in self.sub_covered_elements:
            if sub_element.match_key(from_name, party):
                return sub_element


class CoveredElementPartyRelation(model.CoopSQL):
    'Relation between Covered Element and Covered Relations'

    __name__ = 'ins_contract.covered_element-party_relation'

    covered_element = fields.Many2One('ins_contract.covered_element',
        'Covered Element', ondelete='CASCADE')
    party_relation = fields.Many2One('party.party-relation', 'Party Relation',
        ondelete='RESTRICT')


class CoveredData(model.CoopSQL, model.CoopView):
    'Covered Data'

    __name__ = 'ins_contract.covered_data'

    option = fields.Many2One('ins_contract.option', 'Subscribed Coverage',
        domain=[('id', 'in', Eval('possible_options'))],
        depends=['possible_options'])
    possible_options = fields.Function(
        fields.Many2Many('ins_contract.option', None, None,
            'Possible Options', states={'invisible': True}),
        'get_possible_options')
    covered_element = fields.Many2One(
        'ins_contract.covered_element', 'Covered Element', ondelete='CASCADE')
    complementary_data = fields.Dict(
        'ins_product.complementary_data_def', 'Complementary Data', on_change=[
            'complementary_data', 'option', 'start_date'],
        depends=['complementary_data', 'option', 'start_date'],
        states={'invisible': ~Eval('complementary_data')})
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    status = fields.Selection(contract.OPTIONSTATUS, 'Status')
    contract = fields.Function(
        fields.Many2One('ins_contract.contract', 'Contract'),
        'get_contract_id')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency',
            states={'invisible': True}),
        'get_currency_id')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'get_currency_symbol')
    deductible_duration = fields.Many2One('ins_product.deductible_duration',
        'Deductible Duration', states={
            'invisible': ~Eval('possible_deductible_duration'),
            # 'required': ~~Eval('possible_deductible_duration')
            }, domain=[('id', 'in', Eval('possible_deductible_duration'))],
        depends=['possible_deductible_duration'])
    possible_deductible_duration = fields.Function(
        fields.Many2Many(
            'ins_product.deductible_duration', None, None,
            'Possible Deductible Duration', states={'invisible': True}),
        'get_possible_deductible_duration')

    @classmethod
    def default_status(cls):
        return 'active'

    def get_name_for_billing(self):
        return self.covered_element.get_name_for_billing()

    def get_rec_name(self, name):
        return self.get_coverage().name

    def get_complementary_data_value(self, at_date, value):
        res = utils.get_complementary_data_value(
            self, 'complementary_data', self.get_complementary_data_def(),
            at_date, value)
        if not res:
            res = self.covered_element.get_complementary_data_value(
                at_date, value)
        return res

    def get_complementary_data_def(self):
        return self.option.offered.get_complementary_data_def(
            ['sub_elem'], at_date=self.start_date)

    def init_complementary_data(self):
        if not (hasattr(self, 'complementary_data') and
                self.complementary_data):
            self.complementary_data = {}
        self.complementary_data = self.on_change_complementary_data()[
            'complementary_data']

    def init_from_option(self, option):
        self.option = option
        self.start_date = option.start_date
        self.end_date = option.end_date
        self.init_complementary_data()

    def on_change_complementary_data(self):
        return {'complementary_data': self.option.contract.offered.get_result(
            'calculated_complementary_datas', {
                'date': self.start_date,
                'contract': self.option.contract,
                'sub_elem': self})[0]}

    def init_from_covered_element(self, covered_element):
        #self.covered_element = covered_element
        pass

    def get_dates(self, dates=None, start=None, end=None):
        if dates:
            res = set(dates)
        else:
            res = set()
        res.add(self.start_date)
        if hasattr(self, 'end_date') and self.end_date:
            res.add(self.end_date)
        return utils.limit_dates(res, start, end)

    def get_coverage(self):
        if (hasattr(self, 'option') and self.option):
            return self.option.offered

    def get_contract_id(self, name):
        contract = self.option.get_contract() if self.option else None
        return contract.id if contract else None

    def get_currency(self):
        return (self.covered_element.get_currency()
            if self.covered_element else None)

    def get_currency_id(self, name):
        currency = self.get_currency()
        return currency.id if currency else None

    def get_currency_symbol(self, name):
        return self.currency.symbol if self.currency else None

    def get_possible_deductible_duration(self, name):
        try:
            durations = self.option.offered.get_result(
                'possible_deductible_duration',
                {'date': self.start_date, 'scope': 'covered'},
                kind='deductible')[0]
            return [x.id for x in durations] if durations else []
        except product.NonExistingRuleKindException:
            return []

    def get_deductible_duration(self):
        if self.deductible_duration:
            return self.deductible_duration
        elif self.option.deductible_duration:
            return self.option.deductible_duration

    def get_possible_options(self, name):
        return [x.id for x in self.contract.options] if self.contract else []

    def get_covered_element(self, from_name=None, party=None):
        if self.covered_element:
            return self.covered_element.get_covered_element(from_name, party)

    def get_covered_data(self, from_name=None, party=None):
        covered_element = self.get_covered_element(from_name, party)
        if not covered_element:
            return
        for covered_data in covered_element.covered_data:
            if covered_data.option == self.option:
                return covered_data

    def _expand_tree(self, name):
        return True


class ManagementProtocol(model.CoopSQL, model.CoopView):
    'Management Protocol'

    __name__ = 'ins_contract.management_protocol'

    kind = fields.Selection(
        [
            ('provider', 'Business Provider'),
            ('claim_manager', 'Claim Manager'),
            ('contract_manager', 'Contract Manager'),
        ],
        'Kind',
        required=True,
    )
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    party = fields.Many2One('party.party', 'Party')

    def get_rec_name(self, name):
        return self.party.get_rec_name(name)


class ManagementRole(model.CoopSQL, model.CoopView):
    'Management Role'

    __name__ = 'ins_contract.management_role'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    protocol = fields.Many2One(
        'ins_contract.management_protocol', 'Protocol', required=True,
        domain=[utils.get_versioning_domain('start_date', 'end_date')],
        depends=['start_date', 'end_date'],
        ondelete='RESTRICT',)
    contract = fields.Many2One(
        'ins_contract.contract', 'Contract', ondelete='CASCADE')
    kind = fields.Function(
        fields.Char(
            'Kind',
            on_change_with=['protocol'],
            depends=['protocol'],
        ),
        'on_change_with_kind',
    )

    def on_change_with_kind(self, name=None):
        if not (hasattr(self, 'protocol') and self.protocol):
            return ''
        return coop_string.translate_value(self.protocol, 'kind')


class DeliveredService(model.CoopView, model.CoopSQL):
    'Delivered Service'

    __name__ = 'ins_contract.delivered_service'

    status = fields.Selection(DELIVERED_SERVICES_STATUSES, 'Status')
    expenses = fields.One2Many('ins_contract.expense',
        'delivered_service', 'Expenses')
    contract = fields.Many2One('ins_contract.contract', 'Contract')
    subscribed_service = fields.Many2One(
        'ins_contract.option', 'Coverage', ondelete='RESTRICT',
        domain=[
            If(~~Eval('contract'), ('contract', '=', Eval('contract', {})), ())
        ], depends=['contract'])
    func_error = fields.Many2One('rule_engine.error', 'Error',
        ondelete='RESTRICT', states={
            'invisible': ~Eval('func_error'),
            'readonly': True})

    def get_rec_name(self, name=None):
        if self.subscribed_service:
            res = self.subscribed_service.get_rec_name(name)
        else:
            res = super(DeliveredService, self).get_rec_name(name)
        if self.status:
            res += ' [%s]' % coop_string.translate_value(self, 'status')
        return res

    def get_expense(self, code, currency):
        for expense in self.expenses:
            if (expense.kind and expense.kind.code == code
                    and expense.currency == currency):
                return expense.amount

    def get_total_expense(self, currency):
        res = 0
        for expense in self.expenses:
            if expense.currency == currency:
                res += expense.amount
        return res

    @staticmethod
    def default_status():
        return 'calculating'

    def get_contract(self):
        return self.contract


class Expense(model.CoopSQL, model.CoopView):
    'Expense'

    __name__ = 'ins_contract.expense'

    delivered_service = fields.Many2One(
        'ins_contract.delivered_service', 'Delivered Service',
        ondelete='CASCADE')
    kind = fields.Many2One('ins_product.expense_kind', 'Kind')
    amount = fields.Numeric(
        'Amount', required=True,
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    currency_digits = fields.Function(
        fields.Integer('Currency Digits', states={'invisible': True}),
        'get_currency_digits')

    @staticmethod
    def default_currency():
        return business.get_default_currency()

    def get_currency_digits(self, name):
        if hasattr(self, 'currency') and self.currency:
            return self.currency.digits


class ContractAddress(model.CoopSQL, model.CoopView):
    'Contract Address'

    __name__ = 'ins_contract.address'

    contract = fields.Many2One('ins_contract.contract', 'Contract',
        ondelete='CASCADE')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('policy_owner'))],
        depends=['policy_owner'])
    policy_owner = fields.Function(
        fields.Many2One('party.party', 'Policy Owner',
            states={'invisible': True}),
        'get_policy_owner')

    @staticmethod
    def default_policy_owner():
        return Transaction().context.get('policy_owner')

    def get_policy_owner(self, name):
        if self.contract and self.start_date:
            res = self.contract.get_policy_owner(self.start_date)
        else:
            res = self.default_policy_owner()
        if res:
            return res.id

    @staticmethod
    def default_start_date():
        return Transaction().context.get('start_date')
