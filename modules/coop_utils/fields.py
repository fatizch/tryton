from itertools import chain

from trytond.model import fields as tryton_fields
from trytond.pyson import PYSON
from trytond.pool import Pool
from trytond.transaction import Transaction


class Boolean(tryton_fields.Boolean):
    pass


class Integer(tryton_fields.Integer):
    pass


class Char(tryton_fields.Char):
    pass


class Sha(tryton_fields.Sha):
    pass


class Text(tryton_fields.Text):
    pass


class Float(tryton_fields.Float):
    pass


class Numeric(tryton_fields.Numeric):
    pass


class Date(tryton_fields.Date):
    pass


class DateTime(tryton_fields.DateTime):
    pass


class Binary(tryton_fields.Binary):
    pass


class Selection(tryton_fields.Selection):
    pass


class Reference(tryton_fields.Reference):
    pass


class Many2One(tryton_fields.Many2One):
    pass


class One2Many(tryton_fields.One2Many):
    pass


class One2ManyDomain(One2Many):

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

        targets = []
        for i in range(0, len(ids), Transaction().cursor.IN_MAX):
            sub_ids = ids[i:i + Transaction().cursor.IN_MAX]
            if field._type == 'reference':
                references = ['%s,%s' % (model.__name__, x) for x in sub_ids]
                clause = [(self.field, 'in', references)]
            else:
                clause = [(self.field, 'in', sub_ids)]

            def clean_domain(the_domain):
                if the_domain[0] in ('OR', 'AND'):
                    final_domain = [the_domain[0]]
                    for elem in the_domain[1:]:
                        good_domain = clean_domain(elem)
                        if not good_domain:
                            final_domain.append(True)
                        else:
                            final_domain.append(good_domain)
                elif isinstance(the_domain[0], (tuple, list)):
                    final_domain = []
                    for elem in the_domain:
                        good_domain = clean_domain(elem)
                        if not good_domain:
                            final_domain.append(True)
                        else:
                            final_domain.append(good_domain)
                else:
                    has_pyson = False
                    for value in the_domain:
                        if isinstance(value, PYSON):
                            has_pyson = True
                            break
                    if not has_pyson:
                        final_domain = the_domain
                    else:
                        final_domain = None
                return final_domain

            clause.append(clean_domain(self.domain))
            targets.append(Relation.search(clause, order=self.order))
        targets = list(chain(*targets))

        for target in targets:
            origin_id = getattr(target, self.field).id
            res[origin_id].append(target.id)
        return dict((key, tuple(value)) for key, value in res.iteritems())


class Many2Many(tryton_fields.Many2Many):
    pass


class Function(tryton_fields.Function):
    pass


class Property(tryton_fields.Property):
    pass


class One2One(tryton_fields.One2One):
    pass


class Dict(tryton_fields.Dict):
    pass
