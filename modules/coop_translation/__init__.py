from trytond.pool import Pool


def register():
    Pool.register(
        module='coop_translation', type_='model')
