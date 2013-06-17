from trytond.pool import Pool

from trytond.modules.rule_engine import RuleEngineContext

__all__ = [
    'OfferedContext',
    ]


class OfferedContext(RuleEngineContext):
    'Offered Context'

    __name__ = 'offered.rule_sets'

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
    def _re_complementary_data(cls, args, data_name, from_object=None):
        if not from_object:
            from_object = cls.get_lowest_level_object(args)
        ComplDataDef = Pool().get('offered.complementary_data_def')
        return ComplDataDef.get_complementary_data_value(from_object,
            data_name, args['date'])
