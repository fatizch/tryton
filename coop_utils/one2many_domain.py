from itertools import chain

from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import fields as fields


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
