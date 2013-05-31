class RuleEngineResultLine(object):
    '''
        This class is the root of all rule engine result classes
    '''

    def __init__(self, rule_errors=None):
        super(RuleEngineResultLine, self).__init__()
        self.rule_errors = rule_errors or []


class EligibilityResultLine(RuleEngineResultLine):
    'Eligibility Line Result'

    def __init__(self, eligible=False, details=None):
        super(EligibilityResultLine, self).__init__()
        self.eligible = eligible
        self.details = details or []

    def __iadd__(self, other):
        if other is None or other.eligible is None:
            return self
        self.eligible = self.eligible and other.eligible
        self.details += other.details
        return self

    def __add__(self, other):
        tmp = EligibilityResultLine()

        tmp.eligible = self.eligible + other.eligible
        tmp.details = self.details + other.details
        return tmp


class PricingResultDetail(object):
    def __init__(self, amount=0, on_object=None, details=None):
        self.amount = amount
        self.on_object = on_object
        self.details = details or []


class PricingResultLine(RuleEngineResultLine):
    def __init__(self, amount=0, contract=None, start_date=None, end_date=None,
            on_object=None, frequency=None, details=None):
        self.amount = amount
        self.contract = contract
        self.start_date = start_date
        self.end_date = end_date
        self.on_object = on_object
        self.frequency = frequency
        self.details = details or []

    def __repr__(self):
        return str(self)

    def __str__(self):
        return '%s EUR %s %s %s' % (self.amount, self.contract,
            self.start_date, self.on_object)

    def init_from_args(self, args):
        if 'contract' in args:
            self.contract = args['contract']
        if 'date' in args:
            self.start_date = args['date']

    def add_detail(self, detail):
        self.amount += detail.amount
        self.details.append(detail)

    def add_detail_from_line(self, other_line):
        if not self.frequency and other_line.frequency:
            self.frequency = other_line.frequency
        elif (other_line.frequency and
                not self.frequency == other_line.frequency):
            # TODO : remove this once the frequency consistency checking is
            # performed on the managers
            raise Exception('Frequencies do not match')
        self.amount += other_line.amount
        new_detail = PricingResultDetail(other_line.amount,
            other_line.on_object, details=other_line.details)
        self.details.append(new_detail)
