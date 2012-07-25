#!/usr/bin/python
# -*- coding: utf-8 -*-

from product_test_case import main

import os

os.remove('/home/giovanni/WorkDir/envs/active_record_env/\
tryton-workspace/data/Test.sqlite')

main(
'Test',
['insurance_contract'],
'admin',
'admin',
'/home/giovanni/WorkDir/envs/active_record_env/\
tryton-workspace/conf/trytond.conf')
