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


class OldPricingResultLine(RuleEngineResultLine):
    'Pricing Line Result'

    def __init__(self, value=0, name='', desc=None):
        # Careful : whatever better it feels, using desc=[] for init is a very
        # bad idea...
        # Basically, that means that all instances 'desc' attributes will be
        # a pointer to the same list.
        # So if you change it in one of the instance, it will change it for all

        super(PricingResultLine, self).__init__()
        # value is the amount associated to the line.
        self.value = value

        # name describes the line
        self.name = name

        # desc is a list ob sublines. A line is the sum of all its sublines
        self.desc = desc or []

        # details are dicts with the following tuple as key :
        #  [0] - type (tax, base, fee)
        #  [1] - code (string which combined with the type should allow to find
        #        an object which details the 'cause' of the detail, like a tax)
        # and amount as values.
        self.details = {}

        # If the line is associated with a particular object, here is a
        # reference ("model,id") to it
        self.on_object = None

    def __iadd__(self, other):
        # __iadd__ will be called when doing a += b
        if other is None or other.value is None:
            return self

        self.value += other.get_add_value()

        # a += b means that a is a master of b (in some way), so we append b to
        # the list of a's subelements
        self.desc += [other]
        self.update_details(other.details)
        return self

    def __add__(self, other):
        # In this case (c = a + b), we must create a new instance (c) :
        tmp = PricingResultLine()

        # Then set what we can ; its value and its childs
        tmp.value = self.get_add_value() + other.get_add_value()
        tmp.desc = [self, other]
        tmp.update_details(self.details)
        tmp.update_details(other.details)
        return tmp

    def is_detail_alone(self, name):
        if not self.desc:
            if len(self.details) == 1:
                if self.details.keys()[0][0] == name:
                    return True
        return False

    def get_add_value(self):
        if self.is_detail_alone('tax'):
            return 0
        return self.value

    def update_details(self, other_details):
        for key, value in other_details.iteritems():
            if key in self.details:
                self.details[key] += value
            else:
                self.details[key] = value

    def get_total_detail(self, name):
        res = 0
        for key, value in self.details.iteritems():
            if key[0] == name:
                res += value
        return res

    def get_desc_from_key(self, key):
        for elem in self.desc:
            if elem.is_detail_alone() and key in elem.details:
                return elem

    def create_descs_from_details(self):
        for (key, code), value in self.details.iteritems():
            pl = PricingResultLine()
            pl.value = value
            pl.details = {(key, code): value}
            pl.name = '%s - %s' % (key, code)
            self.desc.append(pl)

    def encode_as_dict(self):
        res = {
            'name': self.name,
            'value': self.value,
            'details': self.details,
            'on_object': self.on_object,
            'desc': []}

        for elem in self.desc:
            res['desc'].append(elem.encode_as_dict())

        return res

    def decode_from_dict(self, from_dict):
        self.name = from_dict['name']
        self.value = from_dict['value']
        self.details = from_dict['details']
        self.on_object = from_dict['on_object']
        self.desc = []
        for elem in from_dict['desc']:
            tmp_desc = PricingResultLine()
            tmp_desc.decode_from_dict(elem)
            self.desc.append(tmp_desc)


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
