from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.model import fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.modules.coop_utils import utils, model

from trytond.pyson import Eval

__all__ = [
    'CollegeDisplayer',
    'CollegeSelection',
    'TrancheDisplayer',
    'TranchesSelection',
    'GBPWizard',
]


class GBPStateView(StateView):
    def get_defaults(self, wizard, state_name, fields):
        res = StateView.get_defaults(self, wizard,
                                                      state_name,
                                                      fields)
        # First we get the existing data for our step in the current session
        default_data = getattr(wizard, state_name)
        if default_data:
            # If it exists, we go through each field and set a new entry in the
            # return dict
            for field in fields:
                if hasattr(default_data, field):
                    field_value = getattr(default_data, field)
                    # We need to make the field json-compatible, so we use the
                    # serialize_field function which does exactly that.
                    res[field] = utils.WithAbstract.serialize_field(
                        field_value)

        return res


class CollegeDisplayer(model.CoopView):
    'College Displayer'

    __name__ = 'ins_collective.college_displayer'

    is_college = fields.Boolean('College')
    name = fields.Char('Name')
    displayer = fields.Many2One('ins_collective.college_displayer',
        'Displayer')
    colleges = fields.One2Many('ins_collective.college_displayer',
        'displayer', 'Colleges')
    college = fields.Many2One('party.college', 'College',
        states={'readonly': True})
    coverage = fields.Many2One('ins_collective.coverage', 'Coverage')
    is_selected = fields.Boolean('Selected',
        states={'readonly': ~Eval('college')})


class CollegeSelection(model.CoopView):
    'College Selection'

    __name__ = 'ins_collective.college_selection'

    college_displayers = fields.One2Many('ins_collective.college_displayer',
        'displayer', 'Colleges')


class TrancheDisplayer(model.CoopView):
    'Tranche Displayer'

    __name__ = 'ins_collective.tranche_displayer'
    coverage = fields.Many2One('ins_collective.coverage', 'Coverage',
        states={'readonly': True})
    college = fields.Many2One('party.college', 'College',
        states={'readonly': True})
    tranche = fields.Many2One('tranche.tranche', 'Tranche',
        states={'readonly': True})
    rate = fields.Numeric('Rate')


class TranchesSelection(model.CoopView):
    'Tranches Selection'

    __name__ = 'ins_collective.tranche_selection'

    tranches = fields.One2Many('ins_collective.tranche_displayer',
        None, 'Tranches')


class GBPWizard(Wizard):
    'GBP Wizard'

    __name__ = 'ins_collective.gbp_wizard'

    start_state = 'start'
    start = StateTransition()
    calculate_tranches = StateTransition()
    validate_tranches = StateTransition()
    college_sel = GBPStateView('ins_collective.college_selection',
        'insurance_collective.gbp_college_selection_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'calculate_tranches', 'tryton-go-next',
                default=True),
        ])
    display_tranches = GBPStateView('ins_collective.tranche_selection',
        'insurance_collective.gbp_tranche_selection_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Complete', 'validate_tranches', 'tryton-go-next',
                default=True),
            ])

    def transition_start(self):
        GBP = Pool().get('ins_collective.gbp_contract')
        College = Pool().get('party.college')
        CollegeDisplayer = Pool().get('ins_collective.college_displayer')

        displayers = []
        gbp = GBP(Transaction().context.get('active_id'))
        colleges = College.search([])
        for cov in gbp.final_product[0].options:
            displayer = CollegeDisplayer()
            displayer.coverage = cov
            displayer.name = cov.get_rec_name('name')
            displayer.colleges = []
            for college in colleges:
                college_disp = CollegeDisplayer()
                college_disp.is_college = True
                college_disp.college = college
                college_disp.name = college.get_rec_name('name')
                college_disp.is_selected = True
                displayer.colleges.append(college_disp)
            displayers.append(displayer)
        self.college_sel.college_displayers = displayers
        return 'college_sel'

    def transition_calculate_tranches(self):
        Tranche = Pool().get('ins_collective.tranche_displayer')
        displayers = []

        for displayer in self.college_sel.college_displayers:
            for tr_college in displayer.colleges:
                if not tr_college.is_selected:
                    continue
                for tranche in tr_college.college.tranches:
                    the_tranche = Tranche()
                    the_tranche.coverage = displayer.coverage
                    the_tranche.college = tr_college.college
                    the_tranche.tranche = tranche
                    displayers.append(the_tranche)

        self.display_tranches.tranches = displayers
        return 'display_tranches'

    def transition_validate_tranches(self):
        GBP = Pool().get('ins_collective.gbp_contract')
        gbp_id = Transaction().context.get('active_id', None)
        if not gbp_id:
            return

        flatten = {}
        for tranche in self.display_tranches.tranches:
            good_opt = flatten.get(tranche.coverage.id, {})
            good_college = good_opt.get(tranche.college.id, [])
            good_college.append(tranche)
            good_opt[tranche.college.id] = good_college
            flatten[tranche.coverage.id] = good_opt

        Pricing = Pool().get('ins_collective.pricing_rule')
        Calculator = Pool().get('ins_collective.pricing_calculator')
        Component = Pool().get('ins_collective.pricing_data')
        gbp = GBP(gbp_id)

        for option_id, values in flatten.iteritems():
            for option in gbp.final_product[0].options:
                if option.id != option_id:
                    continue

                pricing = Pricing()
                pricing.start_date = gbp.start_date
                pricing.calculators = []
                option.pricing_rules.append(pricing)

                for college_id, tranches in values.iteritems():
                    calculator = Calculator()
                    calculator.college = college_id
                    calculator.data = []
                    for tranche in tranches:
                        pricing_data = Component()
                        pricing_data.tranche = tranche.tranche
                        pricing_data.rate = tranche.rate
                        pricing_data.code = tranche.tranche.code
                        calculator.data.append(pricing_data)
                    pricing.calculators.append(calculator)

        return 'end'
