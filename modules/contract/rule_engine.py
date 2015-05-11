from trytond.pool import Pool, PoolMeta

from trytond.modules.rule_engine import check_args

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    def get_lowest_level_object(cls, args):
        '''This method to be overriden in different modules sets the lowest
        object from where to search data. The object will level up itself if it
        doesn't find the good information at its own level'''
        if 'option' in args:
            return args['option']
        if 'contract' in args:
            return args['contract']

    @classmethod
    def _re_extra_data(cls, args, data_name, from_object=None):
        if not from_object:
            from_object = cls.get_lowest_level_object(args)
        ComplDataDef = Pool().get('extra_data')
        return ComplDataDef.get_extra_data_value(from_object,
            data_name, args['date'])

    @classmethod
    def _re_get_contract_initial_start_date(cls, args):
        return args['contract'].initial_start_date

    @classmethod
    def _re_get_contract_start_date(cls, args):
        return args['contract'].start_date

    @classmethod
    def _re_contract_conditions_date(cls, args):
        return args['appliable_conditions_date']

    @classmethod
    @check_args('contract')
    def _re_contract_extra_data(cls, args, data_name):
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

    @classmethod
    def _re_contract_signature_date(cls, args):
        return args['contract'].signature_date

    @classmethod
    def get_person(cls, args):
        if 'person' in args:
            return args['person']
        elif 'elem' in args:
            return args['elem'].party
        cls.append_error(args, 'Cannot find a person to get')

    @classmethod
    @check_args('contract')
    def _re_number_of_activation_periods(cls, args):
        return len(args['contract'].activation_history)
