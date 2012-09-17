class RuleEngineResultLine(object):
    '''
        This class is the root of all rule engine result classes
    '''
    pass


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


class PricingResultLine(RuleEngineResultLine):
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
        self.value += other.value

        # a += b means that a is a master of b (in some way), so we append b to
        # the list of a's subelements
        self.desc += [other]
        self.update_details(other.details)
        return self

    def __add__(self, other):
        # In this case (c = a + b), we must create a new instance (c) :
        tmp = PricingResultLine()

        # Then set what we can ; its value and its childs
        tmp.value = self.value + other.value
        tmp.desc = [self, other]
        tmp.update_details(self.details)
        tmp.update_details(other.details)
        return tmp

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
