from trytond.pool import Pool
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, fields, coop_string

__all__ = [
    'DistributionNetwork',
    'DistributionNetworkContactMechanism',
    ]


class DistributionNetwork(model.CoopSQL, model.CoopView):
    'Distribution Network'

    __name__ = 'distribution.network'
    _func_key = 'code'

    name = fields.Char('Name')
    code = fields.Char('Code')
    full_name = fields.Function(
        fields.Char('Name'),
        'get_full_name', searcher='search_full_name')
    parent = fields.Many2One('distribution.network', 'Top Level', select=True,
        left='left', right='right', ondelete='CASCADE')
    childs = fields.One2Many('distribution.network', 'parent', 'Sub Levels',
        add_remove=[])
    left = fields.Integer('Left', required=True, select=True)
    right = fields.Integer('Right', required=True, select=True)
    parents = fields.Function(
        fields.Many2Many('distribution.network', None, None, 'Parents'),
        'get_parents', searcher='search_parents')
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE')
    parent_party = fields.Function(
        fields.Many2One('party.party', 'Parent Party'),
        'get_parent_party')
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

    @classmethod
    def __setup__(cls):
        super(DistributionNetwork, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))

    @classmethod
    def is_master_object(cls):
        return True

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

    @staticmethod
    def default_left():
        return 0

    @staticmethod
    def default_right():
        return 0

    @classmethod
    def _export_skips(cls):
        res = super(DistributionNetwork, cls)._export_skips()
        res.add('left')
        res.add('right')
        return res

    def get_rec_name(self, name=None):
        if self.code:
            return '[%s] %s' % (self.code, self.full_name)
        else:
            return self.full_name

    def get_parents(self, name=None):
        return [x.id for x in
            self.search([('left', '<', self.left), ('right', '>', self.right)])
            ]

    def get_mechanism(self, name):
        for mechanism in self.contact_mechanisms:
            if mechanism.type == name:
                return mechanism.value
        return ''

    def get_full_name(self, name):
        return self.party.rec_name if self.party else self.name

    def get_parent_party(self, name):
        if self.party:
            return self.party.id
        elif self.parent and self.parent.parent_party:
            return self.parent.parent_party.id

    @classmethod
    def search_parents(cls, name, clause):
        Network = Pool().get('distribution.network')
        if clause[1] != '=':
            raise NotImplementedError
        network = Network(clause[2])
        return [('left', '>', network.left), ('right', '<', network.right)]

    @classmethod
    def search_full_name(cls, name, clause):
        return ['OR',
            ('name',) + tuple(clause[1:]),
            ('party.name',) + tuple(clause[1:]),
            ]

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
