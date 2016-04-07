from trytond.modules.cog_utils import utils
from trytond.config import config


def eval_today():
    return utils.today()

EVAL_METHODS = [
    ('today', eval_today),
    ]
