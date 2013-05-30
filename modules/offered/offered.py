import copy

from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model, business, utils, fields

__all__ = [
    'NonExistingRuleKindException',
    'GetResult',
    'Offered',
    'Product',
    'ProductOptionsCoverage',
    'ProductComplementaryDataRelation',
    ]

CONFIG_KIND = [
    ('simple', 'Simple'),
    ('advanced', 'Advanced')
]

TEMPLATE_BEHAVIOUR = [
    ('', ''),
    ('pass', 'Add'),
    ('override', 'Remove'),
]

DEF_CUR_DIG = 2


class Templated(object):
    'Templated Class'

    __name__ = 'offered.templated'

    template = fields.Many2One(
        None, 'Template',
        domain=[('id', '!=', Eval('id'))],
        depends=['id'],
        on_change=['template'])
    template_behaviour = fields.Selection(
        TEMPLATE_BEHAVIOUR,
        'Template Behaviour',
        states={
            'invisible': ~Eval('template'),
        },
        depends=['template'])

    def on_change_template(self):
        if hasattr(self, 'template') and self.template:
            if not hasattr(self, 'template_behaviour') or \
                    not self.template_behaviour:
                return {'template_behaviour': 'pass'}
        else:
            return {'template_behaviour': None}


class NonExistingRuleKindException(Exception):
    pass


class GetResult(object):
    def get_result(self, target='result', args=None, kind='', path=''):
        # This method is a generic entry point for getting parameters.
        #
        # Arguments are :
        #  - The target value to compute. It is a key which will be used to
        #    decide which data is asked for
        #  - The dict of arguments which will be used by the rule to compute.
        #    Another way to do this would be a link to a method on the caller
        #    which would provide said args on demand.
        #  - The kind will usually be filled, it is a key to finding where
        #    the required data is stored. So if the target is "price", the
        #    kind should be set to "pricing".
        #  - We can use the 'path' arg to specify the way to our data.
        #    Basically, we try to match the first part of path (which looks
        #    like a '.' delimited string ('alpha1.beta3.gamma2')) to one of the
        #    sub-elements of self, then iterate.

        if path:
            # If a path is set, the data we look for is not set on self. So we
            # need to iterate on self's sub-elems.
            #
            # First of all, we need the sub-elems descriptor. This is the
            # result of the get_sub_elem_data method, which returns a tuple
            # with the field name to iterate on as the first element, and
            # this field's field on which to try to match the value.
            sub_elem_data = self.get_sub_elem_data()

            if not sub_elem_data:
                # If it does not exist, someone failed...
                return (None, ['Object %s does not have any sub_data.' % (
                    self.name)])

            path_elems = path.split('.')

            for elem in getattr(self, sub_elem_data[0]):
                # Now we iterate on the specified field
                if path_elems[0] in (
                        getattr(elem, attr) for attr in sub_elem_data[1]):
                    if isinstance(elem, GetResult):
                        return elem.get_result(
                            target, args, kind, '.'.join(path_elems[1:]))
                    return (
                        None, ['Sub element %s of %s cannot get_result !' % (
                            elem.name, self.name)])
            return (None, ['Could not find %s sub element in %s' % (
                path_elems[0], self.name)])

        if kind:
            try:
                good_rule = self.get_good_rule_at_date(args, kind)
            except Exception:
                good_rule = None
            if not good_rule:
                # We did not found any rule matching the specified name
                raise NonExistingRuleKindException
            return good_rule.get_result(target, args)

        # Now we look for our target, as it is at our level
        target_func = getattr(self, 'give_me_' + target)

        result = target_func(args)
        if not isinstance(result, tuple) and not result is None:
            return (result, [])
        return result

    def get_sub_elem_data(self):
        # Should be overridden
        return None


class Offered(model.CoopView, GetResult, Templated):
    'Offered'

    __name__ = 'offered.offered'
    _export_name = 'code'

    code = fields.Char('Code', required=True, select=1)
    name = fields.Char('Name', required=True, select=1, translate=True)
    start_date = fields.Date('Start Date', required=True, select=1)
    end_date = fields.Date('End Date')
    description = fields.Text('Description', translate=True)
    summary = fields.Function(
        fields.Text(
            'Summary', states={'invisible': ~Eval('summary',)}),
        'get_summary')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_currency_digits')
    complementary_data = fields.Dict(
        'offered.complementary_data_def', 'Offered Kind',
        context={'complementary_data_kind': 'product'},
        domain=[('kind', '=', 'product')],
        on_change_with=['complementary_data'])

    @classmethod
    def __setup__(cls):
        super(Offered, cls).__setup__()
        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__

    @staticmethod
    def default_start_date():
        res = Transaction().context.get('start_date')
        if not res:
            res = utils.today()
        return res

    @classmethod
    def get_summary(cls, offereds, name=None, at_date=None, lang=None):
        res = {}
        for offered in offereds:
            res[offered.id] = ''
        return res

    def get_currency_digits(self, name):
        if hasattr(self, 'currency') and self.currency:
            return self.currency.digits
        else:
            return Transaction().context.get('currency_digits')

    @staticmethod
    def default_complementary_data():
        good_se = Pool().get('offered.complementary_data_def').search([
            ('kind', '=', 'product')])
        res = {}
        for se in good_se:
            res[se.name] = se.get_default_value(None)
        return res

    def get_complementary_data_def(self, kinds=None, at_date=None):
        return [
            x for x in self.complementary_data_def
            if x.valid_at_date(at_date) and (not kinds or x.kind in kinds)]

    def get_complementary_data_for_execution(self, args):
        looking_for = 'contract' if not 'sub_elem' in args else 'sub_elem'
        all_schemas = set(self.get_complementary_data_def(
            ('contract', looking_for), args['date']))
        possible_schemas = set(self.get_complementary_data_def(
            (looking_for), args['date']))
        return all_schemas, possible_schemas

    def on_change_with_complementary_data(self):
        if not hasattr(self, 'complementary_data_def'):
            return {}
        ComplementaryData = Pool().get('offered.complementary_data_def')
        schemas = ComplementaryData.search([
            'name', 'in', [k for k in self.complementary_data_def.iterkeys()]])
        if not schemas:
            return {}
        result = copy.copy(self.complementary_data_def)
        for schema in schemas:
            schema.update_field_value(result)
        return result


class Product(model.CoopSQL, Offered):
    'Product'

    __name__ = 'offered.product'

    kind = fields.Selection([('', ''), ('default', 'Default')],
        'Product Kind')
    coverages = fields.Many2Many('offered.product-options-coverage',
        'product', 'coverage', 'Coverages',
        domain=[
            ('currency', '=', Eval('currency')),
            ('kind', '=', Eval('kind')),
            ], depends=['currency', 'kind'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    contract_generator = fields.Many2One('ir.sequence',
        'Contract Number Generator', context={'code': 'offered.product'},
        ondelete='RESTRICT')
    complementary_data_def = fields.Many2Many(
        'offered.product-complementary_data_def',
        'product', 'complementary_data_def', 'Complementary Data',
        domain=[('kind', '=', 'contract')])

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]

    def get_valid_coverages(self):
        for coverage in self.coverages:
            if coverage.is_valid():
                yield coverage

    def update_args(self, args):
        # We might need the product while computing the coverages
        if not 'product' in args:
            args['product'] = self

    @staticmethod
    def default_currency():
        return business.get_default_currency()

    def give_me_new_contract_number(self, args=None):
        return (self.contract_generator.get_id(self.contract_generator.id)
            if self.contract_generator else '')

    def give_me_complementary_data_ids_aggregate(self, args):
        if not 'dd_args' in args:
            return [], []
        res = set()
        errs = []
        for opt in self.coverages:
            result, errors = opt.get_result(
                'complementary_data_ids_aggregate',
                args)
            map(lambda x: res.add(x), result)
            errs += errors
        return list(res), errs

    def give_me_complementary_data_getter(self, args):
        if not 'dd_args' in args:
            return [], []
        dd_args = args['dd_args']
        if not 'path' in dd_args:
            if not 'options' in dd_args:
                return self.give_me_complementary_data_ids(args)
            dd_args['path'] = 'all'
        return self.give_me_complementary_data_ids_aggregate(args)

    def get_currency(self):
        return self.currency

    def give_me_calculated_complementary_datas(self, args):
        # We prepare the call to the 'calculate_value_set' API.
        # It needs the following parameters:
        #  - The list of the schemas it must look for
        #  - The list of all the schemas in the tree. This list should
        #    contain all the schemas from the first list
        #  - All the values available for all relevent schemas
        if not 'contract' in args or not 'date' in args:
            raise Exception('Expected contract and date in args, got %s' % (
                str([k for k in args.iterkeys()])))
        all_schemas, possible_schemas = \
            self.get_complementary_data_for_execution(args)
        if not 'sub_elem' in args:
            for coverage in args['contract'].get_active_coverages_at_date(
                    args['date']):
                coverage_all, coverage_possible = \
                    coverage.get_complementary_data_for_execution(args)
                all_schemas |= coverage_all
                possible_schemas |= coverage_possible
        else:
            coverage = args['sub_elem'].get_coverage()
            coverage_all, coverage_possible = \
                coverage.get_complementary_data_for_execution(args)
            all_schemas |= coverage_all
            possible_schemas |= coverage_possible
        existing_data = {}
        if args['contract'].complementary_data:
            existing_data.update(args['contract'].complementary_data)
        if 'sub_elem' in args and args['sub_elem'].complementary_data:
            existing_data.update(args['sub_elem'].complementary_data)
        ComplementaryData = Pool().get('offered.complementary_data_def')
        result = ComplementaryData.calculate_value_set(
            possible_schemas, all_schemas, existing_data)
        return result, ()


class ProductOptionsCoverage(model.CoopSQL):
    'Define Product - Coverage relations'

    __name__ = 'offered.product-options-coverage'

    product = fields.Many2One(
        'offered.product', 'Product',
        select=1, required=True, ondelete='CASCADE')
    coverage = fields.Many2One(
        'offered.coverage', 'Coverage',
        select=1, required=True, ondelete='RESTRICT')


class ProductComplementaryDataRelation(model.CoopSQL):
    'Relation between Product and Complementary Data'

    __name__ = 'offered.product-complementary_data_def'

    product = fields.Many2One(
        'offered.product', 'Product', ondelete='CASCADE')
    complementary_data_def = fields.Many2One(
        'offered.complementary_data_def',
        'Complementary Data', ondelete='RESTRICT')
