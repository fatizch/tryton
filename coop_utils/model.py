import copy

from itertools import chain

from trytond.pyson import Eval, Bool
from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.wizard import Wizard
from trytond.pool import Pool
from trytond.transaction import Transaction

import utils


class CoopSQL(ModelSQL):
    pass


class CoopView(ModelView):
    pass


class CoopWizard(Wizard):
    pass


class TableOfTable(CoopSQL, CoopView):
    'Table of table'

    __name__ = 'coop.table_of_table'
    #unnecessary line, but to think for children class to replace '.' by '_'
    _table = 'coop_table_of_table'

    my_model_name = fields.Char('Model Name')
    key = fields.Char('Key', states={'readonly': Bool(Eval('is_used'))},
        depends=['is_used'])
    name = fields.Char('Value', required=True, translate=True)
    parent = fields.Many2One(None, 'Parent',
        ondelete='CASCADE')
    childs = fields.One2Many('coop.table_of_table', 'parent', 'Sub values',
        domain=[('my_model_name', '=', Eval('my_model_name'))],
        depends=['my_model_name', 'parent'],
        states={'invisible': Bool(Eval('parent'))},)
    is_used = fields.Function(fields.Boolean('Is Used'), 'get_is_used')

    @classmethod
    def __setup__(cls):
        super(TableOfTable, cls).__setup__()
        cls.childs = copy.copy(cls.childs)
        cls.childs.model_name = cls.__name__
        cls.parent = copy.copy(cls.parent)
        cls.parent.model_name = cls.childs.model_name

    @classmethod
    def default_my_model_name(cls):
        return cls.__name__

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query_string=False):
        domain.append(('my_model_name', '=', cls.__name__))
        return super(TableOfTable, cls).search(domain, offset=offset,
            limit=limit, order=order, count=count, query_string=query_string)

    @staticmethod
    def get_values_as_selection(model_name):
        res = []
        DynamicSelection = Pool().get(model_name)
        for dyn_sel in DynamicSelection.search([]):
            res.append((dyn_sel.key, dyn_sel.name))
        return res

    @staticmethod
    def get_class_where_used():
        '''Method to override in all sub class and return the list of tuple
        class, var_name of object using this class'''
        raise NotImplementedError

    def get_instances_using_me(self):
        res = []
        for cur_class, var_name in self.get_class_where_used():
            Class = Pool().get(cur_class)
            for cur_instance in Class.search([(var_name, '=', self.key)]):
                res.append(cur_instance)
        return res

    def get_is_used(self, name):
        return len(self.get_instances_using_me()) > 0


class DynamicSelection(TableOfTable):
    'Dynamic Selection'

    __name__ = 'coop.dyn_selection'
    _table = 'coop_table_of_table'


class One2ManyDomain(fields.One2Many):

    def get(self, ids, model, name, values=None):
        '''
        Return target records ordered.
        '''
        pool = Pool()
        Relation = pool.get(self.model_name)
        if self.field in Relation._fields:
            field = Relation._fields[self.field]
        else:
            field = Relation._inherit_fields[self.field][2]
        res = {}
        for i in ids:
            res[i] = []
        ids2 = []
        for i in range(0, len(ids), Transaction().cursor.IN_MAX):
            sub_ids = ids[i:i + Transaction().cursor.IN_MAX]
            if field._type == 'reference':
                references = ['%s,%s' % (model.__name__, x) for x in sub_ids]
                clause = [(self.field, 'in', references)]
            else:
                clause = [(self.field, 'in', sub_ids)]
            clause.append(self.domain)
            ids2.append(map(int, Relation.search(clause, order=self.order)))

        cache = Transaction().cursor.get_cache(Transaction().context)
        cache.setdefault(self.model_name, {})
        ids3 = []
        for i in chain(*ids2):
            if i in cache[self.model_name] \
                    and self.field in cache[self.model_name][i]:
                res[cache[self.model_name][i][self.field].id].append(i)
            else:
                ids3.append(i)

        if ids3:
            for i in Relation.read(ids3, [self.field]):
                if field._type == 'reference':
                    _, id_ = i[self.field].split(',')
                    id_ = int(id_)
                else:
                    id_ = i[self.field]
                res[id_].append(i['id'])

        index_of_ids2 = dict((i, index)
            for index, i in enumerate(chain(*ids2)))
        for id_, val in res.iteritems():
            res[id_] = tuple(sorted(val, key=lambda x: index_of_ids2[x]))
        return res


class VersionedObject(CoopView):
    versions = fields.One2Many(
        None,
        'main_elem',
        'Versionned Rates')

    @classmethod
    def version_model(cls):
        raise NotImplementedError

    @classmethod
    def __setup__(cls):
        super(VersionedObject, cls).__setup__()
        versions = copy.copy(getattr(cls, 'versions'))
        versions.model_name = cls.version_model()
        setattr(cls, 'versions', versions)

    # To do : CTD0069
    # Check there is no overlapping of versions before save

    def get_previous_version(self, at_date):
        prev_version = None
        for version in self.versions:
            if version.start_date > at_date:
                return prev_version
            prev_version = version
        return prev_version

    def append_version(self, version):
        rank = 0
        prev_version = self.get_previous_version(version.start_date)
        if prev_version:
            prev_version.end_date = version.start_date - 1
            rank = self.versions.index(prev_version) + 1
        self.versions.insert(rank, version)
        return self

    def get_version_at_date(self, date):
        return utils.get_good_version_at_date(self, 'versions', date)


class VersionObject(CoopView):
    main_elem = fields.Many2One(
        None,
        'Descriptor',
        ondelete='CASCADE')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')

    @classmethod
    def main_model(cls):
        raise NotImplementedError

    @classmethod
    def __setup__(cls):
        super(VersionObject, cls).__setup__()
        main_elem = copy.copy(getattr(cls, 'main_elem'))
        main_elem.model_name = cls.main_model()
        setattr(cls, 'main_elem', main_elem)
