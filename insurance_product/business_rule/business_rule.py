#-*- coding:utf-8 -*-
import copy

from trytond.model import fields
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model, utils, date
from trytond.modules.insurance_product.product import CONFIG_KIND
from trytond.modules.insurance_product.product import Templated

STATE_ADVANCED = Eval('config_kind') != 'advanced'
STATE_SIMPLE = Eval('config_kind') != 'simple'
STATE_SUB_SIMPLE = Eval('sub_elem_config_kind') != 'simple'

__all__ = [
   'BusinessRuleRoot',
    ]


#class BusinessRuleManager(model.CoopSQL, model.CoopView,
#        utils.GetResult, Templated):
#    'Business Rule Manager'
#
#    __name__ = 'ins_product.business_rule_manager'
#
#    offered = fields.Reference('Offered', selection='get_offered_models')
#    business_rules = fields.One2Many('ins_product.generic_business_rule',
#        'manager', 'Business Rules', on_change=['business_rules'])
#
#    @classmethod
#    def __setup__(cls):
#        super(BusinessRuleManager, cls).__setup__()
#        cls.template = copy.copy(cls.template)
#        cls.template.model_name = cls.__name__
#        cls.__rpc__.update({'get_offered_models': RPC()})
#
#    @classmethod
#    def get_offered_models(cls):
#        module_name = utils.get_module_name(cls)
#        return [x for x in utils.get_descendents('ins_product.offered')
#            if module_name in x[0]]
#
#    def on_change_business_rules(self):
#        res = {'business_rules': {}}
#        res['business_rules'].setdefault('update', [])
#        for business_rule1 in self.business_rules:
#            #the idea is to always set the end_date
#            #to the according next start_date
#            for business_rule2 in self.business_rules:
#                if (business_rule1 != business_rule2
#                    and business_rule2.start_date
#                    and business_rule1.start_date
#                    and business_rule2.start_date > business_rule1.start_date
#                    and (not business_rule1.end_date
#                    or business_rule1.end_date >= business_rule2.start_date
#                        )
#                    ):
#                    end_date = (business_rule2.start_date
#                        - datetime.timedelta(days=1))
#                    res['business_rules']['update'].append({
#                        'id': business_rule1.id,
#                        'end_date': end_date})
#
#            #if we change the start_date to a date after the end_date,
#            #we reinitialize the end_date
#            if (business_rule1.end_date
#                and business_rule1.start_date
#                and business_rule1.end_date < business_rule1.start_date):
#                res['business_rules']['update'].append(
#                    {
#                        'id': business_rule1.id,
#                        'end_date': None
#                    })
#        return res
#
#    def get_offered(self):
#        return self.offered
#
##    @classmethod
##    def create(cls, vals):
#        #We need a functional key for import/export, we'll create one when we
#        #create a brm and therefore a business rule because br is required for
#        #brm.
#        #the functional key is the concatenation of the func ey of the offered
#        #and the func key of the business rule (kind)
##        offered = utils.convert_ref_to_obj(vals['offered'])
##        offered_key = getattr(offered, offered._export_name)
##        kind = vals['business_rules'][0][1]['kind']
##        vals['code'] = '%s,%s,%s' % (
##            offered.__class__.__name__, offered_key, kind)
##        return super(BusinessRuleManager, cls).create(vals)
#
##    @classmethod
##    def default_business_rules(cls):
##        return utils.create_inst_with_default_val(cls, 'business_rules')
#
#    @classmethod
#    def recreate_rather_than_update(cls):
#        return True
#
#
#class GenericBusinessRule(model.CoopSQL, model.CoopView):
#    'Generic Business Rule'
#
#    __name__ = 'ins_product.generic_business_rule'
#
#    kind = fields.Selection('get_kind', 'Kind',
#        required=True, on_change=['kind'],
#        states={'readonly': Eval('id', -1) >= 0})
#    manager = fields.Many2One('ins_product.business_rule_manager', 'Manager',
#        ondelete='CASCADE')
#    start_date = fields.Date('From Date', required=True,
#        depends=['is_current'])
#    end_date = fields.Date('To Date')
#    is_current = fields.Function(fields.Boolean('Is current'),
#        'get_is_current')
#    pricing_rule = fields.One2Many('ins_product.pricing_rule',
#        'generic_rule', 'Pricing Rule', size=1)
#    eligibility_rule = fields.One2Many('ins_product.eligibility_rule',
#        'generic_rule', 'Eligibility Rule', size=1)
#    benefit_rule = fields.One2Many('ins_product.benefit_rule',
#        'generic_rule', 'Benefit Rule', size=1)
#    reserve_rule = fields.One2Many('ins_product.reserve_rule',
#        'generic_rule', 'Reserve Rule', size=1)
#    coverage_amount_rule = fields.One2Many('ins_product.coverage_amount_rule',
#        'generic_rule', 'Coverage Amount Rule', size=1)
#    clause_rule = fields.One2Many('ins_product.clause_rule',
#        'generic_rule', 'Clause Rule', size=1)
#    term_renewal_rule = fields.One2Many('ins_product.term_renewal_rule',
#        'generic_rule', 'Term - Renewal Rule', size=1)
#    deductible_rule = fields.One2Many('ins_product.deductible_rule',
#        'generic_rule', 'Deductible Rule', size=1)
#
#    def get_rec_name(self, name):
#        return self.kind
#
#    @classmethod
#    def __setup__(cls):
#        super(GenericBusinessRule, cls).__setup__()
#        cls.kind = copy.copy(cls.kind)
#        for field_name in (rule for rule in dir(cls) if rule.endswith('rule')
#            attr = copy.copy(getattr(cls, field_name))
#            if not hasattr(attr, 'model_name'):
#                continue
#            if cls.kind.on_change is None:
#                cls.kind.on_change = []
#            if field_name not in cls.kind.on_change:
#                cls.kind.on_change += [field_name]
#
#            attr.states = {
#                'invisible': (Eval('kind') != attr.model_name)
#            }
#            setattr(cls, field_name, attr)
#
#    def on_change_kind(self):
#        res = {}
#        for field_name, field in self._fields.iteritems():
#            if not (hasattr(field, 'model_name')
#                and getattr(field, 'model_name').endswith('_rule')
#                and (not getattr(self, field_name)
#                    or len(getattr(self, field_name)) == 0)):
#                continue
#            if field.model_name != self.kind:
#                continue
#            res[field_name] = utils.create_inst_with_default_val(
#                self.__class__, field_name, action='add')
#        return res
#
##    @classmethod
##    def get_kind(cls, vals=None):
##        return coop_string.get_descendents_name(BusinessRuleRoot)
#
#    def get_is_current(self, name):
#        #first we need the model for the manager (depends on the module used
#        if not hasattr(self.__class__, 'manager'):
#            return False
#        manager_attr = getattr(self.__class__, 'manager')
#        if not hasattr(manager_attr, 'model_name'):
#            return False
#        BRM = Pool().get(manager_attr.model_name)
#        date = utils.today()
#        return self == BRM.get_good_rule_at_date(self.manager,
#                {'date': date})
#
#    def get_offered(self):
#        return self.manager.get_offered()
#
#    @classmethod
#    def default_kind(cls):
#        return cls.get_kind()


class BusinessRuleRoot(model.CoopView, utils.GetResult, Templated):
    'Business Rule Root'

    __name__ = 'ins_product.business_rule_root'

    offered = fields.Reference('Offered', selection='get_offered_models')
    start_date = fields.Date('From Date', required=True)
    end_date = fields.Date('To Date')
    config_kind = fields.Selection(CONFIG_KIND,
        'Conf. kind', required=True)
    rule = fields.Many2One('rule_engine', 'Rule Engine',
        states={'invisible': STATE_ADVANCED},
        depends=['config_kind'])

    @classmethod
    def __setup__(cls):
        super(BusinessRuleRoot, cls).__setup__()
        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__
        if hasattr(cls, '_order'):
            cls._order.insert(0, ('start_date', 'ASC'))
        if hasattr(cls, '_constraints'):
            cls._constraints += [('check_dates', 'businessrule_overlaps')]
        if hasattr(cls, '_error_messages'):
            cls._error_messages.update({'businessrule_overlaps':
                'You can not have 2 business rules that overlaps!'})

    @staticmethod
    def default_config_kind():
        return 'simple'

    def get_offered(self):
        return self.generic_rule.get_offered()

    @classmethod
    def get_offered_models(cls):
        module_name = utils.get_module_name(cls)
        return [x for x in utils.get_descendents('ins_product.offered')
            if module_name in x[0]]

    @classmethod
    def recreate_rather_than_update(cls):
        return True

    def get_rec_name(self, name=None):
        if self.config_kind == 'advanced' and self.rule:
            return self.rule.get_rec_name
        return self.get_simple_rec_name()

    def get_simple_rec_name(self):
        return ''

    @staticmethod
    def default_start_date():
        res = Transaction().context.get('start_date')
        if not res:
            date = utils.today()
            res = date
        return res

    def check_dates(self):
        cursor = Transaction().cursor
        cursor.execute('SELECT id ' \
            'FROM ' + self._table + ' ' \
            'WHERE ((start_date <= %s AND end_date >= %s) ' \
                    'OR (start_date <= %s AND end_date >= %s) ' \
                    'OR (start_date >= %s AND end_date <= %s)) ' \
                'AND offered = %s' \
                'AND id != %s',
            (self.start_date, self.start_date,
             self.end_date, self.end_date,
             self.start_date, self.end_date,
             '%s,%s' % (self.offered.__class__.__name__, self.offered.id),
              self.id))
        if cursor.fetchone():
            return False
        return True

    @classmethod
    def copy(cls, rules, default):
        return super(BusinessRuleRoot, cls).copy(rules, default=default)
