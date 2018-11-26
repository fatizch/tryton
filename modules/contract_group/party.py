# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, model
from trytond.pyson import Eval, Bool


__all__ = [
    'Party',
    ]


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    parent_company = fields.Many2One('party.party', 'Parent Company',
        states={'invisible': Bool(Eval('is_person'))}, ondelete='CASCADE',
        domain=[('is_person', '=', False), ('parent_company', '=', None)],
        depends=['is_person'])
    companies = fields.Function(
        fields.Many2Many('party.party', None, None, 'Companies',
            states={'invisible': ~Eval('is_person')},
            domain=[('is_person', '=', False)]),
        'get_companies', searcher='search_companies')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._buttons.update({
                'button_display_hierarchy': {
                    'readonly': ~Eval('active', True),
                    'invisible': Bool(Eval('is_person'))
                    },
                })

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [
            ("/form/group[@id='invisible']", 'states',
                {'invisible': True}),
            ]

    def get_companies(self, name):
        results = []
        for covered in sorted(self.covered_elements,
                key=lambda x: x.start_date, reverse=True):
            if covered.affiliated_to:
                results.append(covered.affiliated_to.id)
        return results

    @classmethod
    def search_companies(cls, name, clause):
        return [('covered_elements.affiliated_to',) + tuple(clause[1:])]

    @classmethod
    @model.CoogView.button_action('contract_group.act_hierarchy_form')
    def button_display_hierarchy(cls, parties):
        pass
