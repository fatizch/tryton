# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import zipcode
import batch
import load_data


def register():
    Pool.register(
        zipcode.Zip,
        batch.UpdateZipCodesFromHexaPost,
        load_data.HexaPostSet,
        module='country_hexaposte', type_='model')

    Pool.register(
        load_data.HexaPostSetWizard,
        module='country_hexaposte', type_='wizard')
