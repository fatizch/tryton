from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement import values_mixin


__all__ = [
    'Loan',
    'LoanIncrement',
    'LoanPayment',
    'Endorsement',
    'EndorsementLoan',
    ]


class Loan:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'loan'


class LoanIncrement:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'loan.increment'


class LoanPayment:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'loan.payment'


class Endorsement:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement'

    loan_endorsements = fields.One2Many('endorsement.loan', 'endorsement',
        'Loan Endorsement')
    loans = fields.Function(
        fields.Many2Many('loan', '', '', 'Loans'),
        'get_loans', searcher='search_loans')

    def get_loans(self, name):
        return [x.loan.id for x in self.loan_endorsements]

    @classmethod
    def search_loans(cls, name, clause):
        return [('loan_endorsements.loan',) + tuple(clause[1:])]

    def all_endorsements(self):
        result = super(Endorsement, self).all_endorsements()
        result += self.loan_endorsements
        return result

    def find_parts(self, endorsement_part):
        # Finds the effective endorsement depending on the provided
        # endorsement part
        if endorsement_part.kind in ('loan'):
            return self.loan_endorsements
        return super(Endorsement, self).find_parts(endorsement_part)

    def new_endorsement(self, endorsement_part):
        if endorsement_part.kind in ('loan'):
            return Pool().get('endorsement.loan')(endorsement=self)
        return super(Endorsement, self).new_endorsement(endorsement_part)

    @classmethod
    def group_per_model(cls, endorsements):
        result = super(Endorsement, cls).group_per_model(endorsements)
        result['endorsement.loan'] = [
            loan_endorsement for endorsement in endorsements
            for loan_endorsement in endorsement.loan_endorsements]
        return result

    @classmethod
    def apply_order(cls):
        result = super(Endorsement, cls).apply_order()
        result.insert(0, 'endorsement.loan')
        return result


class EndorsementLoan(values_mixin('endorsement.loan.field'),
        model.CoopSQL, model.CoopView):
    'Endorsement Loan'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.loan'

    loan = fields.Many2One('loan', 'Loan', required=True,
        datetime_field='applied_on', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state'])
    endorsement = fields.Many2One('endorsement', 'Endorsement', required=True,
        ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    endorsement_summary = fields.Function(
        fields.Text('Endorsement Summary'),
        'get_endorsement_summary')
    state = fields.Function(
        fields.Selection([
                ('draft', 'Draft'),
                ('applied', 'Applied'),
                ], 'State'),
        'get_state', searcher='search_state')

    @classmethod
    def __setup__(cls):
        super(EndorsementLoan, cls).__setup__()
        cls._error_messages.update({
                'not_latest_applied': ('Endorsement "%s" is not the latest '
                    'applied.')
                })
        cls.values.states = {
            'readonly': Eval('state') == 'applied',
            }
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['state', 'definition']

    @staticmethod
    def default_state():
        return 'draft'

    @property
    def base_instance(self):
        if not self.loan:
            return None
        if not self.applied_on:
            return self.loan
        Loan = Pool().get('loan')
        with Transaction().set_context(_datetime=self.applied_on):
            return Loan(self.loan.id)

    def get_definition(self, name):
        return self.endorsement.definition.id if self.endorsement else None

    def get_endorsement_summary(self, name):
        result = self.definition.name + ':\n'
        loan_summary = self.get_summary('loan', self.base_instance, 2)
        if loan_summary:
            result += loan_summary
            result += '\n\n'
        return result

    def get_state(self, name):
        return self.endorsement.state if self.endorsement else 'draft'

    @classmethod
    def search_state(cls, name, clause):
        return [('endorsement.state',) + tuple(clause[1:])]

    def _restore_history(self):
        pool = Pool()
        Loan = pool.get('loan')

        hloan = self.loan
        loan = Loan(self.loan.id)
        Loan.restore_history([loan.id], self.applied_on)

        return loan, hloan

    @classmethod
    def draft(cls, loan_endorsements):
        for loan_endorsement in loan_endorsements:
            latest_applied, = cls.search([
                    ('loan', '=', loan_endorsement.loan.id),
                    ('state', '=', 'applied'),
                    ], order=[('applied_on', 'DESC')], limit=1)
            if latest_applied != loan_endorsement:
                cls.raise_user_error('not_latest_applied',
                    loan_endorsement.rec_name)

            loan_endorsement._restore_history()
            loan_endorsement.set_applied_on(None)
            loan_endorsement.state = 'draft'
            loan_endorsement.save()

    @classmethod
    def apply(cls, loan_endorsements):
        for loan_endorsement in loan_endorsements:
            loan = loan_endorsement.loan
            loan_endorsement.set_applied_on(loan.write_date
                or loan.create_date)
            values = loan_endorsement.apply_values
            # TODO: Make it better
            for k, v in values.iteritems():
                setattr(loan, k, v)
            loan.increments, loan.payments = [], []
            loan.calculate_increments()
            loan.payments = loan.calculate_payments()
            loan.save()
            loan_endorsement.save()

    def set_applied_on(self, at_datetime):
        self.applied_on = at_datetime

    @property
    def apply_values(self):
        return (self.values if self.values else {}).copy()

    def get_endorsed_record(self):
        return self.loan
