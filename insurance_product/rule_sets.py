from trytond.modules.rule_engine import RuleEngineContext
from trytond.modules.rule_engine import InternalRuleEngineError
from trytond.modules.rule_engine import check_args, for_rule
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
    @for_rule('Name')
    @check_args('contract')
    def get_subscriber_name(cls, args):
        name = args['contract'].subscriber.name
        return name

    @classmethod
    @for_rule('Birthdate')
    @check_args('subscriber_person')
    def get_subscriber_birthdate(cls, args):
        subscriber = args['subscriber_person']
        if hasattr(subscriber, 'birth_date'):
            return subscriber.birth_date
        args['errors'].append('Subscriber does not have a birth date')
        raise InternalRuleEngineError

    @classmethod
    @for_rule('Gender')
    @check_args('subscriber_person')
    def get_subscriber_gender(cls, args):
        return args['subscriber_person'].gender

    @classmethod
    @for_rule('Nationality')
    @check_args('subscriber_person')
    def get_subscriber_nationality(cls, args):
        country = args['subscriber_person'].get_nationality()
        return country.code

    @classmethod
    @for_rule('Living country')
    @check_args('contract')
    def get_subscriber_living_country(cls, args):
        address = args['contract'].subscriber.address_get()
        return address.country

    @classmethod
    @for_rule('Product subscribed ?')
    @check_args('contract')
    def subscriber_subscribed(cls, args, product_name):
        contracts = args['contract'].subscriber.get_subscribed_contracts()
        matches = [1 for x in contracts
            if x.get_product().code == product_name]
        return len(matches) > 0


class PersonContext(RuleEngineContext):
    '''
        Context functions for Persons.
    '''
    __name__ = 'ins_product.rule_sets.person'

    @staticmethod
    def get_person(args):
        if 'person' in args:
            return args['person']
        elif 'sub_elem' in args:
            return args['sub_elem'].product_specific.person
        else:
            args['errors'].append('Cannot find a person to get')
            raise InternalRuleEngineError

    @classmethod
    @for_rule('Name')
    def get_person_name(cls, args):
        name = cls.get_person(args).name
        return name

    @classmethod
    @for_rule('Birthdate')
    def get_person_birthdate(cls, args):
        person = cls.get_person(args)
        if hasattr(person, 'birth_date'):
            return person.birth_date
        args['errors'].append('%s does not have a birth date' % person.name)
        raise InternalRuleEngineError

    @classmethod
    @for_rule('Gender')
    def get_person_gender(cls, args):
        return cls.get_person(args).gender

    @classmethod
    @for_rule('Nationality')
    def get_person_nationality(cls, args):
        country = cls.get_person(args).get_nationality()
        return country.code

    @classmethod
    @for_rule('Living Country')
    def get_person_living_country(cls, args):
        address = cls.get_person(args).address_get()
        return address.country

    @classmethod
    @for_rule('Product subscribed ?')
    def person_subscribed(cls, args, product_name):
        contracts = cls.get_person(args).get_subscribed_contracts()
        matches = [1 for x in contracts
            if x.get_product().code == product_name]
        return len(matches) > 0

    @classmethod
    @for_rule('Over majority age ?')
    def is_person_of_age(cls, args):
        person = cls.get_person(args)
        birthdate = cls.get_person_birthdate({'person': person})
        country = cls.get_person_nationality({'person': person})
        # Will be plugged in later
        # limit_age = country.get_majority_age()
        limit_age = 18
        return RuleTools.years_between(
            args,
            birthdate,
            RuleTools.today(args)) >= limit_age

    @classmethod
    @for_rule('Relation with subscriber')
    @check_args('contract')
    def link_with_subscriber(cls, args):
        person = cls.get_person(args)
        subscriber = args['contract'].subscriber
        return person.get_relation_with(subscriber)


class CoveredDataContext(RuleEngineContext):
    '''
        Context functions for Coverage-Covered associations objects
        (CoveredData)
    '''
    __name__ = 'ins_product.rule_sets.covered_data'

    @staticmethod
    def get_covered_data(args):
        if 'data' in args:
            return args['data']
        else:
            args['errors'].append('Cannot find a covered data to get')
            raise InternalRuleEngineError

    @classmethod
    @for_rule('Subscription date')
    def get_initial_subscription_date(cls, args):
        return cls.get_covered_data(args).start_date

    @classmethod
    @for_rule('End date')
    def get_subscription_end_date(cls, args):
        data = cls.get_covered_data(args)
        if hasattr(data, 'end_date') and data.end_date:
            return data.end_date
        else:
            args['errors'].append('No end date defined on provided data')
            raise InternalRuleEngineError
