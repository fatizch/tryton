from collections import defaultdict
from sql.aggregate import Count

from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

from trytond.modules.cog_utils import model, fields, coop_string

__all__ = [
    'DistributionNetwork',
    'DistributionNetworkContactMechanism',
    ]


class DistributionNetwork(model.CoopSQL, model.CoopView):
    'Distribution Network'

    __name__ = 'distribution.network'
    _func_key = 'code'

    name = fields.Char('Name', translate=True,
        states={'required': ~Eval('party')},
        depends=['party'])
    code = fields.Char('Code', required=True)
    full_name = fields.Function(
        fields.Char('Name'),
        'get_full_name', searcher='search_full_name')
    parent = fields.Many2One('distribution.network', 'Top Level', select=True,
        left='left', right='right', ondelete='CASCADE')
    childs = fields.One2Many('distribution.network', 'parent', 'Sub Levels',
        add_remove=[], target_not_required=True)
    left = fields.Integer('Left', required=True, select=True)
    right = fields.Integer('Right', required=True, select=True)
    parents = fields.Function(
        fields.Many2Many('distribution.network', None, None, 'Parents'),
        'get_parents', searcher='search_parents')
    all_children = fields.Function(
        fields.Many2Many('distribution.network', None, None, 'Children'),
        'get_all_children', searcher='search_all_children')
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
        states={'required': ~Eval('name')}, depends=['name'])
    parent_party = fields.Function(
        fields.Many2One('party.party', 'Parent Party'),
        'get_parent_party', searcher='search_parent_party')
    address = fields.Many2One('party.address', 'Address', ondelete='SET NULL',
        domain=[('party', '=', Eval('parent_party'))],
        depends=['parent_party'])
    contact_mechanisms = fields.Many2Many(
        'distribution_network-party.contact_mechanism', 'distribution_network',
        'contact_mechanism', 'Contact Mechanisms',
        domain=[('party', '=', Eval('parent_party'))],
        depends=['parent_party'])
    phone = fields.Function(fields.Char('Phone'), 'get_mechanism')
    mobile = fields.Function(fields.Char('Mobile'), 'get_mechanism')
    fax = fields.Function(fields.Char('Fax'), 'get_mechanism')
    email = fields.Function(fields.Char('E-Mail'), 'get_mechanism')
    portfolio_size = fields.Function(
        fields.Integer('Portfolio Size'),
        'get_portfolio_size')
    is_portfolio = fields.Boolean('Client Portfolio',
        states={'readonly': Bool(Eval('portfolio_size', False))},
        depends=['portfolio_size'],
        help='If checked, parties will be defined within this distribution'
        ' network and can only be accessed by it or its children distribution'
        ' network.' )
    is_distributor = fields.Boolean('Distributor',
        help='If not checked, this distribution network will not be selectable'
        ' during subscription process.')
    portfolio = fields.Function(
        fields.Many2One('distribution.network', 'Portfolio'),
        'get_portfolio')
    visible_portfolios = fields.Function(
        fields.Many2Many('distribution.network', None, None,
            'Visible Portfolios'),
        'get_visible_portfolios', searcher='search_visible_portfolios')


    @classmethod
    def __setup__(cls):
        super(DistributionNetwork, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))

    @classmethod
    def _export_skips(cls):
        return super(DistributionNetwork, cls)._export_skips() | {'left',
            'right', 'childs'}

    @classmethod
    def _export_light(cls):
        return super(DistributionNetwork, cls)._export_light() | {'parent'}

    @classmethod
    def is_master_object(cls):
        return True

    @staticmethod
    def default_left():
        return 0

    @staticmethod
    def default_is_portfolio():
        return True

    @staticmethod
    def default_is_distributor():
        return True

    @staticmethod
    def default_right():
        return 0

    @fields.depends('parent', 'is_portfolio')
    def on_change_parent(self):
        if self.parent:
            self.is_portfolio = not self.parent.portfolio
        else:
            self.is_portfolio = True

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

    def get_rec_name(self, name=None):
        if self.code:
            return '[%s] %s' % (self.code, self.full_name)
        else:
            return self.full_name

    def get_parents(self, name=None):
        return [x.id for x in
            self.search([('left', '<', self.left), ('right', '>', self.right)])
            ]

    def get_all_children(self, name):
        return [x.id for x in self.search(
                [('left', '>=', self.left), ('right', '<=', self.right)])]

    def get_visible_portfolios(self, name):
        return [x.id for x in self.search([
                    ['OR',
                        [('left', '>=', self.left),
                            ('right', '<=', self.right)],
                        [('left', '<', self.left),
                            ('right', '>', self.right)]],
                    [('is_portfolio', '=', True)]])]

    def get_mechanism(self, name):
        for mechanism in self.contact_mechanisms:
            if mechanism.type == name:
                return mechanism.value
        return ''

    def get_full_name(self, name):
        if self.name:
            return self.name
        elif self.party:
            return self.party.name

    def get_parent_party(self, name):
        if self.party:
            return self.party.id
        elif self.parent and self.parent.parent_party:
            return self.parent.parent_party.id

    @classmethod
    def get_portfolio_size(cls, instances, name):
        pool = Pool()
        result = defaultdict(int)
        cursor = Transaction().cursor
        party = pool.get('party.party').__table__()
        cursor.execute(
            *party.select(party.portfolio, Count(party.id),
                where=(party.portfolio.in_([x.id for x in instances])),
                group_by=[party.portfolio]))
        for key, value in cursor.fetchall():
            result[key] = value
        return result

    def get_portfolio(self, name):
        if self.is_portfolio:
            return self.id
        if self.parent:
            portfolio = self.parent.portfolio
            return portfolio.id if portfolio else None

    @classmethod
    def search_parents(cls, name, clause):
        if clause[1] == '=':
            network = cls(clause[2])
            return [('left', '>', network.left), ('right', '<', network.right)]
        elif clause[1] == 'in':
            networks = cls.browse(clause[2])
            clause = ['OR']
            for network in networks:
                clause.append([
                        ('left', '>', network.left),
                        ('right', '<', network.right)])
            return clause
        else:
            raise NotImplementedError

    @classmethod
    def search_all_children(cls, name, clause):
        if clause[1] == '=':
            network = cls(clause[2])
            return [('left', '<=', network.left),
                ('right', '>=', network.right)]
        elif clause[1] == 'in':
            networks = cls.browse(clause[2])
            clause = ['OR']
            for network in networks:
                clause.append([
                        ('left', '<=', network.left),
                        ('right', '>=', network.right)])
            return clause
        else:
            raise NotImplementedError

    @classmethod
    def search_visible_portfolios(cls, name, clause):
        if clause[1] == 'in':
            networks = cls.browse(clause[2])
            clause = [[('is_portfolio', '=', True)], ['OR']]
            for network in networks:
                clause[1].append([('left', '<=', network.left),
                        ('right', '=>', network.right)],
                    [('left', '>', network.left),
                        ('right', '<', network.right)])
            return clause
        else:
            raise NotImplementedError

    @classmethod
    def search_full_name(cls, name, clause):
        return ['OR',
            ('name',) + tuple(clause[1:]),
            ('party.name',) + tuple(clause[1:]),
            ]

    @classmethod
    def search_parent_party(cls, name, clause):
        if clause[1] != '=':
            raise NotImplementedError
        networks = cls.search([('party', '=', clause[2])])
        if len(networks) == 1:
            return ['OR', ('parents', '=', networks[0]),
                    ('party', '=', clause[2])]
        elif len(networks) > 1:
            return ['OR', ('parents', 'in', networks),
                    ('party', '=', clause[2])]
        else:
            return [('id', '=', None)]

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('code',) + tuple(clause[1:]),
            ('full_name',) + tuple(clause[1:]),
            ]


class DistributionNetworkContactMechanism(model.CoopSQL):
    'Relation Distribution Network - Contact Mechanism'

    __name__ = 'distribution_network-party.contact_mechanism'

    distribution_network = fields.Many2One('distribution.network',
        'Distribution Network', ondelete='CASCADE')
    contact_mechanism = fields.Many2One('party.contact_mechanism',
        'Contact Mechanism', ondelete='CASCADE')
