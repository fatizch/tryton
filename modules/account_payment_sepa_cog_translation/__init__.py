from trytond.pool import Pool


def register():
    Pool.register(module='account_payment_sepa_cog_translation', type_='model')
