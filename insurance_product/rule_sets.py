from trytond.modules.rule_engine import RuleEngineContext
from trytond.modules.rule_engine import InternalRuleEngineError
from trytond.modules.rule_engine import check_args


class ContractContext(RuleEngineContext):
    '''
        Context functions for Contracts.
    '''
    __name__ = 'ins_product.rule_sets.contract'

    @classmethod
    @check_args('contract')
    def get_subscriber_name(cls, args):
        name = args['contract'].subscriber.name
        return name

    @classmethod
    @check_args('contract')
    def get_subscriber_birthdate(cls, args):
        subscriber = args['contract'].subscriber
        if hasattr(subscriber, 'birth_date'):
            return subscriber.birth_date
        args['errors'].append('Subscriber does not have a birth date')
        raise InternalRuleEngineError


class PersonContext(RuleEngineContext):
    '''
        Context functions for Persons.
    '''
    __name__ = 'ins_product.rule_sets.person'

    @classmethod
    @check_args('person')
    def get_person_name(cls, args):
        name = args['person'].name
        return name

    @classmethod
    @check_args('person')
    def get_person_birthdate(cls, args):
        person = args['person']
        if hasattr(person, 'birth_date'):
            return person.birth_date
        args['errors'].append('%s does not have a birth date' % person.name)
        raise InternalRuleEngineError
