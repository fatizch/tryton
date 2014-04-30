#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta

from trytond.pyson import Eval, Or
from trytond.modules.cog_utils import model, coop_string
from trytond.modules.cog_utils import fields
from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.rule_engine import check_args
from trytond.modules.rule_engine import RuleTools

###############################################################################
# We write here sets of functions that will be available in the rule engine.  #
# There are a few decorators available for management of these functions :    #
#   - check_args(str1, str2...) => checks that each of the str in the args is #
#     a key in the 'args' parameter of the function                           #
###############################################################################

__metaclass__ = PoolMeta

__all__ = [
    'RuleEngineExtraData',
    'RuleEngine',
    'RuleEngineRuntime',
    ]


class RuleEngineExtraData(model.CoopSQL):
    'Rule Engine - Extra Data'

    __name__ = 'rule_engine-extra_data'

    parent_rule = fields.Many2One('rule_engine', 'Parent Rule', required=True,
        ondelete='CASCADE')
    extra_data = fields.Many2One('extra_data', 'External Data',
        ondelete='RESTRICT')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor

        super(RuleEngineExtraData, cls).__register__(module_name)

         # Migration from 1.1: split rule parameters in multiple table
        extradata_definition = cls.__table__()
        if TableHandler.table_exist(cursor, 'rule_engine_parameter'):
            cursor.execute(*extradata_definition.delete())
            cursor.execute("SELECT external_extra_data_def, parent_rule "
                "FROM rule_engine_parameter "
                "WHERE kind = 'compl'")
            for cur_rule_parameter in cursor.dictfetchall():
                cursor.execute(*extradata_definition.insert(
                    columns=[extradata_definition.parent_rule,
                    extradata_definition.extra_data],
                    values=[[cur_rule_parameter['parent_rule'],
                    cur_rule_parameter['external_extra_data_def']]]))
            TableHandler.table_rename(cursor, 'rule_engine_parameter',
                'rule_engine_parameter_backup')


class RuleEngine:
    __name__ = 'rule_engine'

    extra_data_used = fields.Many2Many(
        'rule_engine-extra_data', 'parent_rule',
        'extra_data', 'Extra Data', states={
            'invisible': Or(
                Eval('extra_data_kind') != 'extra_data',
                ~Eval('extra_data'),
                )
            }, depends=['extra_data_kind', 'extra_data'])

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.extra_data_kind = copy.copy(cls.extra_data_kind)
        cls.extra_data_kind.selection.extend([('extra_data', 'Extra Data')])
        cls.extra_data_kind.selection = list(set(
                cls.extra_data_kind.selection))

    @classmethod
    def fill_empty_data_tree(cls):
        res = super(RuleEngine, cls).fill_empty_data_tree()
        tmp_node = {}
        tmp_node['name'] = ''
        tmp_node['translated'] = ''
        tmp_node['fct_args'] = ''
        tmp_node['description'] = coop_string.translate_label(cls,
            'extra_data_used')
        tmp_node['type'] = 'folder'
        tmp_node['long_description'] = ''
        tmp_node['children'] = []
        res.append(tmp_node)
        return res

    @fields.depends('extra_data_used')
    def on_change_with_data_tree(self, name=None):
        return super(RuleEngine, self).on_change_with_data_tree(name)

    def build_node(self, elem, kind):
        res = super(RuleEngine, self).build_node(elem, kind)
        if kind == 'extra_data':
            res['translated'] = '%s_%s' % (kind, elem.string)
        return res

    def allowed_functions(self):
        res = super(RuleEngine, self).allowed_functions()
        res += [self.get_translated_name(elem, 'compl')
            for elem in self.extra_data_used]
        return res

    def get_translated_name(self, elem, kind):
        if kind != 'compl':
            return super(RuleEngine, self).get_translated_name(elem, kind)
        return '%s_%s' % (kind, elem.name)

    def data_tree_structure(self):
        res = super(RuleEngine, self).data_tree_structure()
        self.data_tree_structure_for_kind(res,
            coop_string.translate_label(self, 'extra_data_used'),
            'compl', self.extra_data_used)
        return res

    def get_external_extra_data_def(self, elem, args):
        OfferedSet = Pool().get('rule_engine.runtime')
        from_object = OfferedSet.get_lowest_level_object(args)
        res = elem.get_extra_data_value(from_object, elem.name, args['date'])
        return res

    def as_context(self, elem, kind, evaluation_context, context, forced_value,
            debug=False):
        super(RuleEngine, self).as_context(elem, kind, evaluation_context,
            context, forced_value, debug)
        if kind != 'compl':
            return
        technical_name = self.get_translated_name(elem, kind)
        if technical_name in context:
            # Looks like the value was forced
            return
        context[technical_name] = \
            lambda: self.get_external_extra_data_def(elem,
                evaluation_context)
        if debug:
            debug_wrapper = self.get_wrapper_func(context)
            context[technical_name] = debug_wrapper(context[technical_name])

    def add_rule_parameters_to_context(self, evaluation_context,
            execution_kwargs, context):
        super(RuleEngine, self).add_rule_parameters_to_context(
            evaluation_context, execution_kwargs, context)
        for elem in self.extra_data_used:
            self.as_context(elem, 'compl', evaluation_context, context, None,
                Transaction().context.get('debug'))


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('subscriber_person')
    def _re_get_subscriber_birthdate(cls, args):
        subscriber = args['subscriber_person']
        if hasattr(subscriber, 'birth_date'):
            return subscriber.birth_date
        cls.append_error(args, 'Subscriber does not have a birth date')

    @classmethod
    @check_args('contract')
    def _re_get_subscriber_living_country(cls, args):
        address = args['contract'].subscriber.address_get()
        return address.country

    @classmethod
    @check_args('contract')
    def _re_subscriber_subscribed(cls, args, product_name):
        contracts = args['contract'].subscriber.get_subscribed_contracts()
        matches = [
            1 for x in contracts if x.get_product().code == product_name]
        return len(matches) > 0

    @classmethod
    def get_person(cls, args):
        if 'person' in args:
            return args['person']
        elif 'elem' in args:
            return args['elem'].party
        cls.append_error(args, 'Cannot find a person to get')

    @classmethod
    def _re_get_person_birthdate(cls, args):
        person = cls.get_person(args)
        if hasattr(person, 'birth_date'):
            return person.birth_date
        cls.append_error(args, '%s does not have a birth date' % person.name)

    @classmethod
    def _re_get_person_living_country(cls, args):
        address = cls.get_person(args).address_get()
        return address.country

    @classmethod
    def _re_person_subscribed(cls, args, product_name):
        contracts = cls.get_person(args).get_subscribed_contracts()
        matches = [
            1 for x in contracts if x.get_product().code == product_name]
        return len(matches) > 0

    @classmethod
    def _re_is_person_of_age(cls, args):
        person = cls.get_person(args)
        birthdate = cls.get_person_birthdate({'person': person})
        limit_age = 18
        return RuleTools.years_between(
            args,
            birthdate,
            RuleTools.today(args)) >= limit_age

    @classmethod
    @check_args('contract')
    def _re_link_with_subscriber(cls, args):
        person = cls.get_person(args)
        subscriber = args['contract'].subscriber
        return person.get_relation_with(subscriber, args['date'])

    @classmethod
    def get_option(cls, args):
        if 'option' in args:
            return args['option']
        else:
            cls.append_error(args, 'Cannot find an option to get')

    @classmethod
    def _re_get_initial_subscription_date(cls, args):
        return cls.get_option(args).start_date

    @classmethod
    def _re_get_subscription_end_date(cls, args):
        data = cls.get_option(args)
        if hasattr(data, 'end_date') and data.end_date:
            return data.end_date
        else:
            cls.append_error(args, 'No end date defined on provided data')

    @classmethod
    @check_args('option')
    def _re_option_extra_data(cls, args, data_name):
        cls.append_error(args, 'deprecated_method')

    @classmethod
    @check_args('price_details')
    def _re_get_sub_component(cls, args, the_code):
        for detail in args['price_details']:
            if detail.on_object.code == the_code:
                return detail.amount
        cls.append_error(args, 'Inexisting code : %s' % the_code)

    @classmethod
    @check_args('price_details', 'final_details')
    def _re_append_detail(cls, args, the_code, amount):
        found = False
        for detail in args['price_details']:
            if not detail.on_object.code == the_code:
                continue
            args['final_details'][the_code] = (amount +
                args['final_details'].get(the_code, (0,))[0], detail)
            found = True
            break
        if not found:
            cls.append_error(args, 'Undefined Code %s' % the_code)
            return

    @classmethod
    @check_args('price_details')
    def _re_apply_tax(cls, args, code, base):
        tax = None
        for detail in args['price_details']:
            if detail.on_object.kind == 'tax':
                if detail.on_object.code == code:
                    tax = detail.on_object.tax
                    break
        if tax is None:
            cls.append_error(args, 'Undefined Tax %s' % code)
            return

        tax_vers = tax.get_version_at_date(args['date'])
        return tax_vers.apply_tax(base)

    @classmethod
    @check_args('price_details')
    def _re_apply_fee(cls, args, code, base):
        fee = None
        for detail in args['price_details']:
            if detail.on_object.kind == 'fee':
                if detail.on_object.code == code:
                    fee = detail.on_object.fee
                    break
        if fee is None:
            cls.append_error(args, 'Undefined Fee %s' % code)
            return

        fee_vers = fee.get_version_at_date(args['date'])
        return fee_vers.apply_fee(base)
