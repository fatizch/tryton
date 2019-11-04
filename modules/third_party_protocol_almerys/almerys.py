# -*- coding: utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.coog_core import model, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction


__all__ = [
    'ReturnAlmerys',
    'RecomputePeriod',
    ]

STATUS = [
    ('treated', 'Treated'),
    ('to_treat', 'To Treat'),
    ]

ERROR_CODE = [
    ('ERR_CIN_00000001', '[ERR_CIN_00000001] Validity of field supply in the '
                         'file'),
    ('ERR_CIN_00000002', '[ERR_CIN_00000002] Validity of field supply in the '
                         'file'),
    ('ERR_CIN_00000004', '[ERR_CIN_00000004] Contract member (management centre'
                         ', company, collective contract'),
    ('ERR_CIN_00000008', '[ERR_CIN_00000008] Contract member'),
    ('ERR_CIN_00000009', '[ERR_CIN_00000009] Contract member'),
    ('ERR_CIN_00000020', '[ERR_CIN_00000020] Content of the flow fields'),
    ('ERR_CIN_00000043', '[ERR_CIN_00000043] Mandatory tags'),
    ('ERR_CPI_00000013', '[ERR_CPI_00000013] Validity of field supply in the '
                         'file'),
    ('ERR_CPI_00000025', '[ERR_CPI_00000025] Company reference'),
    ('ERR_CPI_00000026', '[ERR_CPI_00000026] Company reference'),
    ('ERR_CPI_00000033', '[ERR_CPI_00000033] Consistency supplier/service '
                         'scope'),
    ('ERR_CPI_00000034', '[ERR_CPI_00000034] Scope of service'),
    ('ERR_CPII_00000001', '[ERR_CPII_00000001] Service provider'),
    ('ERR_GEN_00000001', '[ERR_GEN_00000001] The length of the fields in the '
                         'flow'),
    ('ERR_GEN_00000002', '[ERR_GEN_00000002] Validity of field supply in the '
                         'file'),
    ('ERR_GEN_00000003', '[ERR_GEN_00000003] Validity of field supply in the '
                         'file'),
    ('ERR_GEN_00000004', '[ERR_GEN_00000004] End of line detection'),
    ('ERR_GEN_00000005', '[ERR_GEN_00000005] Detection no impromptu end of '
                         'line'),
    ('ERR_GEN_00000006', '[ERR_GEN_00000006] Presence of mandatory fields'),
    ('ERR_GEN_00000007', '[ERR_GEN_00000007] Validity of entity types in the '
                         'flow'),
    ('ERR_GEN_00000112', '[ERR_GEN_00000112] Contract'),
    ('ERR_GEN_00000113', '[ERR_GEN_00000113] Enter exit'),
    ('ERR_GEN_00000120', '[ERR_GEN_00000120] Presence of the FILE tag'),
    ('ERR_GEN_00000121', '[ERR_GEN_00000121] Presence of the PERIMETER_SERVICE '
                         'tag'),
    ('ERR_GEN_00000122', '[ERR_GEN_00000122] Presence of the CONTRACT tag'),
    ('ERR_GEN_00000123', '[ERR_GEN_00000123] Setting up responsible contracts'),
    ('ERR_PB_00000001', '[ERR_PB_00000001] Field length'),
    ('ERR_PB_00000002', '[ERR_PB_00000002] Allowed values'),
    ('ERR_PB_00000003', '[ERR_PB_00000003] Allowed values'),
    ('ERR_PB_00000004', '[ERR_PB_00000004] End of registration delimiter'),
    ('ERR_PB_00000005', '[ERR_PB_00000005] Field length'),
    ('ERR_PB_00000006', '[ERR_PB_00000006] Required fields'),
    ('ERR_PB_00000007', '[ERR_PB_00000007] Service provider configuration'),
    ('ERR_PB_00000008', '[ERR_PB_00000008] Parameter setting of the service '
                        'perimeter'),
    ('ERR_PB_00000009', '[ERR_PB_00000009] Service provider'),
    ('ERR_PB_00000010', '[ERR_PB_00000010] Scope of service'),
    ('ERR_PB_00000013', '[ERR_PB_00000013] Empty file'),
    ('ERR_PR_00000011', '[ERR_PR_00000011] Coherence of the flow'),
    ('ERR_V3_00000001', '[ERR_V3_00000001] Version of the standard'),
    ('ERR_V3_00000002', '[ERR_V3_00000002] Service provider label'),
    ('ERR_V3_00000005', '[ERR_V3_00000005] Rattachement'),
    ('ERR_V3_00000006', '[ERR_V3_00000006] Grouping criteria'),
    ('ERR_V3_00000007', '[ERR_V3_00000007] Contract member'),
    ('ERR_V3_00000008', '[ERR_V3_00000008] Access rights'),
    ('ERR_V3_00000009', '[ERR_V3_00000009] Access rights'),
    ('ERR_V3_00000010', '[ERR_V3_00000010] Service TP PEC'),
    ('ERR_V3_00000011', '[ERR_V3_00000011] Service TP PEC'),
    ('ERR_V3_00000014', '[ERR_V3_00000014] Tag sequence'),
    ('ERR_V3_00000015', '[ERR_V3_00000015] Validity of field supply in '
                        'the file'),
    ('ERR_V3_00000016', '[ERR_V3_00000016] Contract member'),
    ('ERR_V3_00000017', '[ERR_V3_00000017] Service TP PEC'),
    ('ERR_V3_00000018', '[ERR_V3_00000018] Service TP PEC'),
    ('ERR_V3_00000019', '[ERR_V3_00000019] Service TP PEC'),
    ('ERR_V3_00000020', '[ERR_V3_00000020] Compliance with the service '
                        'perimeter code'),
    ('ERR_V3_00000021', '[ERR_V3_00000021] Service TP PEC'),
    ('ERR_V3_00000023', '[ERR_V3_00000023] Setting up responsible contracts by '
                        'service perimeter'),
    ('ERR_V3_00000024', '[ERR_V3_00000024] Contract member'),
    ('ERR_V3_00000025', '[ERR_V3_00000025] Management center '),
    ('ERR_V3_00000026', '[ERR_V3_00000026] Service TP PEC'),
    ('ERR_V3_00000027', '[ERR_V3_00000027] Validity of the date'),
    ('ERR_V3_00000028', '[ERR_V3_00000028] Date format'),
    ('ERR_V3_00000029', '[ERR_V3_00000029] Filling the date of birth in the '
                        'file'),
    ('ERR_V3_00000030', '[ERR_V3_00000030] Processing parameters by service '
                        'perimeter'),
    ('ERR_V3_00000031', '[ERR_V3_00000031] Missing address'),
    ('ERR_V3_00000032', '[ERR_V3_00000032] Perimeter unknown service'),
    ('ERR_V3_00000034', '[ERR_V3_00000034] Risk bearer'),
    ('ERR_V3_00000035', '[ERR_V3_00000035] Contract type'),
    ('ERR_V3_00000036', '[ERR_V3_00000036] Contract type'),
    ('ERR_V3_00000037', '[ERR_V3_00000037] Map background'),
    ('ERR_V3_00000038', '[ERR_V3_00000038] Map background'),
    ('ERR_V3_00000039', '[ERR_V3_00000039] Map background'),
    ('ERR_V3_00000040', '[ERR_V3_00000040] Contract status'),
    ('ERR_V3_00000041', '[ERR_V3_00000041] Contract status'),
    ('ERR_V3_00000042', '[ERR_V3_00000042] Contract status'),
    ('ERR_V3_00000043', '[ERR_V3_00000043] Code annexe'),
    ('ERR_V3_00000044', '[ERR_V3_00000044] Code annexe'),
    ('ERR_V3_00000045', '[ERR_V3_00000045] Code annexe'),
    ('ERR_V3_00000046', '[ERR_V3_00000046] Beneficiary'),
    ('ERR_V3_00000047', '[ERR_V3_00000047] Bank details'),
    ('ERR_V3_00000048', '[ERR_V3_00000048] Bank details'),
    ('WRN_CIN_00000037', '[WRN_CIN_00000037] Contract status'),
    ('WRN_CIN_00000038', '[WRN_CIN_00000038] Termination date'),
    ('WRN_CPI_00000016', '[WRN_CPI_00000016] Impossible to create the reject '
                         'file (for details, see log file)'),
    ('WRN_V3_00000030', '[WRN_V3_00000030] Powering the address components in '
                        'the file'),
    ('WRN_V3_00000046', '[WRN_V3_00000030] Beneficiary'),
    ('ERR_CPI_00000014', '[ERR_CPI_00000014] NNI'),
    ('ERR_V2_00000007', '[ERR_V2_00000007] TP Coverage'),
    ('ERR_V2_00000008', '[ERR_V2_00000008] missing address'),
    ('ERR_V2_00000013', '[ERR_V2_00000013] Parameter setting'),
    ('ERR_CPI_00000002', '[ERR_CPI_00000002] rejet'),
    ('ERR_CPI_00000012', '[ERR_CPI_00000012] client number'),
    ('ERR_CPI_00000047', '[ERR_CPI_00000047] Perimeter of service'),
    ('ERR_CPI_00000048', '[ERR_CPI_00000048] Perimeter of service'),
    ('UNKNOWN_CODE', '[N/A] Unknown Code'),
    ]


class ReturnAlmerys(model.CoogSQL, model.CoogView):
    'Return Almerys'

    __name__ = 'return.almerys'

    contract = fields.Many2One('contract', 'Contract', readonly=True,
        ondelete='CASCADE', required=True, select=True)
    error_code = fields.Selection(ERROR_CODE, 'Error Code', readonly=True)
    error_code_string = error_code.translated('Error Code')
    error_label = fields.Char('Error Label', readonly=True)
    status = fields.Selection(STATUS, 'Status')
    status_string = status.translated('status')
    file_number = fields.Char('File Number', readonly=True)


class RecomputePeriod(metaclass=PoolMeta):
    __name__ = 'third_party_manager.recompute_period'

    def get_contract(self):
        if Transaction().context['active_model'] == 'return.almerys':
            pool = Pool()
            ReturnAlmerys = pool.get('return.almerys')
            contract = ReturnAlmerys(Transaction().
                context['active_id']).contract
            return contract
        else:
            return super(RecomputePeriod, self).get_contract()
