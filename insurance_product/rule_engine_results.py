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
        self.value = value
        self.name = name

        # Use this instead :
        self.desc = desc or []
        self.details = []
        self.on_object = None

    def __iadd__(self, other):
        # __iadd__ will be called when doing a += b
        if other is None or other.value is None:
            return self
        self.value += other.value

        # a += b means that a is a master of b (in some way), so we append b to
        # the list of a's subelements
        self.desc += [other]
        return self

    def __add__(self, other):
        # In this case (c = a + b), we must create a new instance (c) :
        tmp = PricingResultLine()

        # Then set what we can ; its value and its childs
        tmp.value = self.value + other.value
        tmp.desc = [self, other]
        return tmp

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
