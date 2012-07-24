from trytond.pyson import Eval, Bool
from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.wizard import Wizard
from trytond.pool import Pool

_TYPES = [
    ('bool', 'Boolean'),
    ('str', 'String'),
    ('int', 'Integer'),
    ('float', 'Numeric'),
    ('text', 'Text')
]


class CoopSQL(ModelSQL):
    pass


class CoopView(ModelView):
    pass


class CoopWizard(Wizard):
    pass


class DynamicSelection(CoopSQL, CoopView):
    'Dynamic Selection'

    __name__ = 'coop.dynamic_selection'

    kind = fields.Selection([('person_relation', 'Person Relation'),
                             ('company_relation', 'Company Relation')],
                            'Kind', required=True)
    key = fields.Char('Key', required=True)
    name = fields.Char('Value', required=True)
    reverse_key = fields.Char('Reverse Key')

    @classmethod
    def __setup__(cls):
        super(DynamicSelection, cls).__setup__()
        cls._sql_constraints += [
            ('key_uniq', 'UNIQUE(key)', 'The key must be unique!'),
        ]

    @staticmethod
    def get_dyn_sel(kind):
        res = []
        DynamicSelection = Pool().get('coop.dynamic_selection')
        dyn_sels = DynamicSelection.search([('kind', '=', kind)])
        for dyn_sel in dyn_sels:
            res.append([dyn_sel.key, dyn_sel.name])
        return res

    @staticmethod
    def get_reverse_dyn_sel(key):
        res = []
        DynamicSelection = Pool().get('coop.dynamic_selection')
        dyn_sels = DynamicSelection.search([('reverse_key', '=', key)],
                                           limit=1)
        for dyn_sel in dyn_sels:
            res.append([dyn_sel.key, dyn_sel.name])
        return res


class TableOfTable(CoopSQL, CoopView):
    'Table of table'

    __name__ = 'coop.table_of_table'
    #unnecessary line, but to think for children class to replace '.' by '_'
    _table = 'coop_table_of_table'

    my_model_name = fields.Char('Model Name')
    name = fields.Char('Value', required=True)
    parent = fields.Many2One('coop.table_of_table', 'Parent',
        ondelete='CASCADE')
    my_fields = fields.One2Many('coop.table_of_table', 'parent', 'Fields',
        domain=[('my_model_name', '=', Eval('my_model_name'))],
        depends=['my_model_name', 'parent'],
        states={'invisible': Bool(Eval('parent'))},)
    value_kind = fields.Selection(_TYPES, 'Value kind', required=True,
        sort=False)

    @classmethod
    def default_my_model_name(cls):
        return cls.__name__

    @staticmethod
    def default_value_kind():
        return 'bool'

#    @classmethod
#    def search(cls, domain, offset=0, limit=None, order=None, count=False):
#        print 'avant', domain
#        if len([item for item in domain if 'parent' in item] +
#            [item for item in domain if 'id' in item]) == 0:
#            domain = ['AND', domain[:], ('parent', '=', None)]
#        print 'apres', domain
#        return super(TableOfTable, cls).search(domain, offset=offset,
#                   limit=limit, order=order, count=count)
