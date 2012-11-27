#-*- coding:utf-8 -*-
import copy
import datetime

from trytond.model import fields
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model, utils, date, string
from trytond.modules.insurance_product.product import CONFIG_KIND
from trytond.modules.insurance_product.product import Templated, Offered

__all__ = [
   'BusinessRuleManager',
   'GenericBusinessRule',
   'BusinessRuleRoot',
    ]


class BusinessRuleManager(model.CoopSQL, model.CoopView,
        utils.GetResult, Templated):
    'Business Rule Manager'

    __name__ = 'ins_product.business_rule_manager'

    offered = fields.Reference('Offered', selection='get_offered_models')
    business_rules = fields.One2Many('ins_product.generic_business_rule',
        'manager', 'Business Rules', on_change=['business_rules'])
#    code = fields.Char('Code',
#        on_change_with=['business_rules', 'offered'])

    @classmethod
    def __setup__(cls):
        super(BusinessRuleManager, cls).__setup__()
        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__
        cls.__rpc__.update({'get_offered_models': RPC()})

    @staticmethod
    def get_offered_models():
        return utils.get_descendents(Offered)

    def on_change_business_rules(self):
        res = {'business_rules': {}}
        res['business_rules'].setdefault('update', [])
        for business_rule1 in self.business_rules:
            #the idea is to always set the end_date
            #to the according next start_date
            for business_rule2 in self.business_rules:
                if (business_rule1 != business_rule2
                    and business_rule2.start_date
                    and business_rule1.start_date
                    and business_rule2.start_date > business_rule1.start_date
                    and (not business_rule1.end_date
                        or business_rule1.end_date >= business_rule2.start_date
                        )
                    ):
                    end_date = (business_rule2.start_date
                        - datetime.timedelta(days=1))
                    res['business_rules']['update'].append({
                        'id': business_rule1.id,
                        'end_date': end_date})

            #if we change the start_date to a date after the end_date,
            #we reinitialize the end_date
            if (business_rule1.end_date
                and business_rule1.start_date
                and business_rule1.end_date < business_rule1.start_date):
                res['business_rules']['update'].append(
                    {
                        'id': business_rule1.id,
                        'end_date': None
                    })
        return res

    def get_good_rule_at_date(self, data):
        # First we got to check that the fields that we will need to calculate
        # which rule is appliable are available in the data dictionnary
        try:
            the_date = data['date']
        except KeyError:
            return None

        try:
            # We use the date field from the data argument to search for
            # the good rule.
            # (This is a given way to get a rule from a list, using the
            # applicable date, it could be anything)
            return utils.get_good_version_at_date(self, 'business_rules',
                the_date)
        except ValueError, _exception:
            return None

    def get_offered(self):
        return self.offered

#    @classmethod
#    def create(cls, vals):
        #We need a functional key for import/export, we'll create one when we
        #create a brm and therefore a business rule because br is required for
        #brm.
        #the functional key is the concatenation of the func key of the offered
        #and the func key of the business rule (kind)
#        offered = utils.convert_ref_to_obj(vals['offered'])
#        offered_key = getattr(offered, offered._export_name)
#        kind = vals['business_rules'][0][1]['kind']
#        vals['code'] = '%s,%s,%s' % (
#            offered.__class__.__name__, offered_key, kind)
#        return super(BusinessRuleManager, cls).create(vals)

#    @staticmethod
#    def default_business_rules():
#        return utils.create_inst_with_default_val(BusinessRuleManager,
#            'business_rules')


class GenericBusinessRule(model.CoopSQL, model.CoopView):
    'Generic Business Rule'

    __name__ = 'ins_product.generic_business_rule'

    kind = fields.Selection('get_kind', 'Kind',
        required=True, on_change=['kind'], states={'readonly': True})
    manager = fields.Many2One('ins_product.business_rule_manager', 'Manager',
        ondelete='CASCADE')
    start_date = fields.Date('From Date', required=True,
        depends=['is_current'])
    end_date = fields.Date('To Date')
    is_current = fields.Function(fields.Boolean('Is current'),
        'get_is_current')
    pricing_rule = fields.One2Many('ins_product.pricing_rule',
        'generic_rule', 'Pricing Rule', size=1)
    eligibility_rule = fields.One2Many('ins_product.eligibility_rule',
        'generic_rule', 'Eligibility Rule', size=1)
    benefit_rule = fields.One2Many('ins_product.benefit_rule',
        'generic_rule', 'Benefit Rule', size=1)
    reserve_rule = fields.One2Many('ins_product.reserve_rule',
        'generic_rule', 'Reserve Rule', size=1)
    coverage_amount_rule = fields.One2Many('ins_product.coverage_amount_rule',
        'generic_rule', 'Coverage Amount Rule', size=1)
    clause_rule = fields.One2Many('ins_product.clause_rule',
        'generic_rule', 'Clause Rule', size=1)
    term_renewal_rule = fields.One2Many('ins_product.term_renewal_rule',
        'generic_rule', 'Term - Renewal Rule', size=1)
    deductible_rule = fields.One2Many('ins_product.deductible_rule',
        'generic_rule', 'Deductible Rule', size=1)

    def get_rec_name(self, name):
        return self.kind

    @classmethod
    def __setup__(cls):
        super(GenericBusinessRule, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        for field_name in (rule for rule in dir(cls) if rule.endswith('rule')):
            attr = copy.copy(getattr(cls, field_name))
            if not hasattr(attr, 'model_name'):
                continue
            if cls.kind.on_change is None:
                cls.kind.on_change = []
            if field_name not in cls.kind.on_change:
                cls.kind.on_change += [field_name]

            attr.states = {
                'invisible': (Eval('kind') != attr.model_name)
            }
            setattr(cls, field_name, attr)

        cls._order.insert(0, ('start_date', 'ASC'))
        cls._constraints += [('check_dates', 'businessrule_overlaps')]
        cls._error_messages.update({'businessrule_overlaps':
            'You can not have 2 business rules that overlaps!'})

    def on_change_kind(self):
        res = {}
        for field_name, field in self._fields.iteritems():
            if not (hasattr(field, 'model_name')
                and getattr(field, 'model_name').endswith('_rule')
                and (not getattr(self, field_name)
                    or len(getattr(self, field_name)) == 0)):
                continue
            if field.model_name != self.kind:
                continue
            res[field_name] = utils.create_inst_with_default_val(
                self.__class__, field_name, action='add')
        return res

    @staticmethod
    def get_kind():
        return string.get_descendents_name(BusinessRuleRoot)

    def get_is_current(self, name):
        #first we need the model for the manager (depends on the module used
        if not hasattr(self.__class__, 'manager'):
            return False
        manager_attr = getattr(self.__class__, 'manager')
        if not hasattr(manager_attr, 'model_name'):
            return False
        BRM = Pool().get(manager_attr.model_name)
        date = utils.today()
        return self == BRM.get_good_rule_at_date(self.manager,
                {'date': date})

    def check_dates(self):
        cursor = Transaction().cursor
        cursor.execute('SELECT id ' \
                'FROM ' + self._table + ' ' \
                'WHERE ((start_date <= %s AND end_date >= %s) ' \
                        'OR (start_date <= %s AND end_date >= %s) ' \
                        'OR (start_date >= %s AND end_date <= %s)) ' \
                    'AND manager = %s ' \
                    'AND id != %s',
                (self.start_date, self.start_date,
                    self.end_date, self.end_date,
                    self.start_date, self.end_date,
                    self.manager.id, self.id))
        if cursor.fetchone():
            return False
        return True

    @staticmethod
    def default_start_date():
        res = Transaction().context.get('start_date')
        if not res:
            date = utils.today()
            res = date
        return res

    def get_good_rule_from_kind(self):
        for field_name, field_desc in self._fields.iteritems():
            if (hasattr(field_desc, 'model_name') and
                    field_desc.model_name == self.kind):
                return getattr(self, field_name)[0]

    def get_offered(self):
        return self.manager.get_offered()


class BusinessRuleRoot(model.CoopView, utils.GetResult, Templated):
    'Business Rule Root'

    __name__ = 'ins_product.business_rule_root'

    config_kind = fields.Selection(CONFIG_KIND,
        'Conf. kind', required=True)
    generic_rule = fields.Many2One('ins_product.generic_business_rule',
        'Generic Rule', ondelete='CASCADE')
    rule = fields.Many2One('rule_engine', 'Rule Engine',
        depends=['config_kind'])

    @classmethod
    def __setup__(cls):
        super(BusinessRuleRoot, cls).__setup__()
        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__

    @staticmethod
    def default_config_kind():
        return 'simple'

    def get_offered(self):
        return self.generic_rule.get_offered()
