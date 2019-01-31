# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import functools

from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import model, coog_string
from trytond.modules.coog_core import fields
from trytond import backend
from trytond.transaction import Transaction
from trytond.tools import cursor_dict

from trytond.modules.coog_core import utils
from trytond.modules.rule_engine import check_args, RuleTools

###############################################################################
# We write here sets of functions that will be available in the rule engine.  #
# There are a few decorators available for management of these functions :    #
#   - check_args(str1, str2...) => checks that each of the str in the args is #
#     a key in the 'args' parameter of the function                           #
###############################################################################


__all__ = [
    'RuleEngineExtraData',
    'RuleEngine',
    'RuleEngineRuntime',
    ]


class RuleEngineExtraData(model.CoogSQL):
    'Rule Engine - Extra Data'

    __name__ = 'rule_engine-extra_data'

    parent_rule = fields.Many2One('rule_engine', 'Parent Rule', required=True,
        ondelete='CASCADE')
    extra_data = fields.Many2One('extra_data', 'External Data',
        ondelete='RESTRICT')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()

        super(RuleEngineExtraData, cls).__register__(module_name)

        # Migration from 1.1: split rule parameters in multiple table
        extradata_definition = cls.__table__()
        if TableHandler.table_exist('rule_engine_parameter'):
            cursor.execute(*extradata_definition.delete())
            cursor.execute("SELECT external_extra_data_def, parent_rule "
                "FROM rule_engine_parameter "
                "WHERE kind = 'compl'")
            for cur_rule_parameter in cursor_dict(cursor):
                cursor.execute(*extradata_definition.insert(
                    columns=[extradata_definition.parent_rule,
                    extradata_definition.extra_data],
                    values=[[cur_rule_parameter['parent_rule'],
                    cur_rule_parameter['external_extra_data_def']]]))
            TableHandler.table_rename('rule_engine_parameter',
                'rule_engine_parameter_backup')


class RuleEngine(metaclass=PoolMeta):
    __name__ = 'rule_engine'

    extra_data_used = fields.Many2Many(
        'rule_engine-extra_data', 'parent_rule',
        'extra_data', 'Extra Data')

    @classmethod
    def fill_empty_data_tree(cls):
        res = super(RuleEngine, cls).fill_empty_data_tree()
        tmp_node = {}
        tmp_node['name'] = ''
        tmp_node['translated'] = ''
        tmp_node['fct_args'] = ''
        tmp_node['description'] = coog_string.translate_label(cls,
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
            coog_string.translate_label(self, 'extra_data_used'),
            'compl', self.extra_data_used)
        return res

    @staticmethod
    def get_external_extra_data_def(key, args):
        ExtraData = Pool().get('extra_data')
        if key in args.get('extra_data', {}):
            return args['extra_data'][key]
        return ExtraData._extra_data_value_for_rule(key, args)

    def as_context(self, elem, kind, base_context):
        super(RuleEngine, self).as_context(elem, kind, base_context)
        if kind != 'compl':
            return
        technical_name = self.get_translated_name(elem, kind)
        base_context[technical_name] = ('compl', elem.name)

    def deflat_element(self, element):
        if element[0] == 'compl':
            return functools.partial(self.get_external_extra_data_def,
                element[1])
        else:
            return super(RuleEngine, self).deflat_element(element)

    def add_rule_parameters_to_context(self, base_context):
        super(RuleEngine, self).add_rule_parameters_to_context(base_context)
        for elem in self.extra_data_used:
            self.as_context(elem, 'compl', base_context)


class RuleEngineRuntime(metaclass=PoolMeta):
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('subscriber')
    def _re_get_subscriber_birthdate(cls, args):
        subscriber = args['subscriber']
        if (hasattr(subscriber, 'birth_date') and hasattr(subscriber,
                'is_person') and subscriber.is_person):
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
            1 for x in contracts if x.product.code == product_name]
        return len(matches) > 0

    @classmethod
    def get_person(cls, args):
        if 'person' in args:
            return args['person']
        elif 'elem' in args:
            return args['elem'].party
        cls.append_error(args, 'Cannot find a person to get')

    @classmethod
    def _re_person_gender(cls, args):
        return cls.get_person(args).gender

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
            1 for x in contracts if x.product.code == product_name]
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
    def _re_get_option_initial_start_date(cls, args):
        return cls.get_option(args).initial_start_date

    @classmethod
    def _re_get_option_start_date(cls, args):
        return cls.get_option(args).start_date

    @classmethod
    def _re_get_option_end_date(cls, args):
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
    @check_args('option')
    def _re_option_code(cls, args):
        return args['option'].coverage.code

    @classmethod
    @check_args('option', 'contract')
    def _re_coverage_already_subscribed(cls, args):
        # This function returns True if the coverage was already subscribed by
        # another contract, and False if the coverage was never subscribed
        # or if this contract is the first one to subscribe it for the current
        # subscriber.
        Option = Pool().get('contract.option')
        date = args.get('date', utils.today())
        contract = args['contract']
        options = Option.get_covered_options_from_party(contract.subscriber,
            date)
        matches = []
        for o in options:
            if o.coverage == args['option'].coverage:
                matches.append(o.parent_contract.id)
        matches.sort()
        return matches and (contract.id not in matches or
            matches.index(contract.id) != 0)

    @classmethod
    @check_args('option')
    def _re_option_has_extra_premiums(cls, args):
        return bool(args['option'].extra_premiums)
