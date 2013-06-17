from trytond.modules.rule_engine import RuleEngineContext
from trytond.modules.rule_engine import check_args
from trytond.modules.rule_engine import RuleTools

###############################################################################
# We write here sets of functions that will be available in the rule engine.  #
# They will be automatically created as tree_elements in sub_folders          #
# matching the different RuleEngineContext classes.                           #
# There are a few decorators available for management of these functions :    #
#   - for_rule(str) => sets the 'rule_name' attribute which will be used      #
#     for automatic creation of the tree_element for the description field    #
#   - check_args(str1, str2...) => checks that each of the str in the args is #
#     a key in the 'args' parameter of the function                           #
###############################################################################


class SubscriberContext(RuleEngineContext):
    '''
        Context functions for Contracts.
    '''
    __name__ = 'ins_product.rule_sets.subscriber'

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


class PersonContext(RuleEngineContext):
    '''
        Context functions for Persons.
    '''
    __name__ = 'ins_product.rule_sets.person'

    @classmethod
    def get_person(cls, args):
        if 'person' in args:
            return args['person']
        elif 'sub_elem' in args:
            return args['sub_elem'].party
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
        return person.get_relation_with(subscriber)


class ContractContext(RuleEngineContext):
    '''
        Context functions for contract related data
    '''

    __name__ = 'ins_product.rule_sets.contract'

    @classmethod
    @check_args('contract')
    def _re_contract_complementary_data(cls, args, data_name):
        cls.append_error(args, 'deprecated_method')

    @classmethod
    @check_args('contract')
    def _re_contract_address_country(cls, args):
        contract = args['contract']
        address = contract.get_contract_address(args['date'])
        if address:
            return address.country

    @classmethod
    @check_args('contract')
    def _re_contract_address_zip(cls, args):
        contract = args['contract']
        address = contract.get_contract_address(args['date'])
        if address:
            return address.zip


class OptionContext(RuleEngineContext):
    '''
        Context functions for option related data
    '''

    __name__ = 'ins_product.rule_sets.option'


class CoveredDataContext(RuleEngineContext):
    '''
        Context functions for Coverage-Covered associations objects
        (CoveredData)
    '''
    __name__ = 'ins_product.rule_sets.covered_data'

    @classmethod
    def get_covered_data(cls, args):
        if 'data' in args:
            return args['data']
        else:
            cls.append_error(args, 'Cannot find a covered data to get')

    @classmethod
    def _re_get_initial_subscription_date(cls, args):
        return cls.get_covered_data(args).start_date

    @classmethod
    def _re_get_subscription_end_date(cls, args):
        data = cls.get_covered_data(args)
        if hasattr(data, 'end_date') and data.end_date:
            return data.end_date
        else:
            cls.append_error(args, 'No end date defined on provided data')

    @classmethod
    @check_args('data')
    def _re_covered_data_complementary_data(cls, args, data_name):
        cls.append_error(args, 'deprecated_method')


class RuleCombinationContext(RuleEngineContext):
    '''
        Context functions for combination of rule_engine results (see
        ins_product.pricing_rule
    '''

    __name__ = 'ins_product.rule_sets.rule_combination'

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
