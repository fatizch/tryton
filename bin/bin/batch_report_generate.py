#!/usr/bin/env python

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from os import path
import sys
import json
from genshi.template import TemplateLoader
from datetime import datetime

from trytond.config import config


def _usage():  # print usage message
    print('')
    print(' Usage: batch_report_generate <genshi-template-filepath>')


def generate_report(obj, template_path):
    loader = TemplateLoader(path.join(path.dirname(template_path),
            ''), auto_reload=True)
    tmpl = loader.load(path.join(path.basename(template_path)))
    if not tmpl:
        raise IOError('File is no valid')
    env = config.get('batch_report', 'env_name')
    message = tmpl.generate(data=obj, datetime=datetime, env_name=env).render()
    return message


if len(sys.argv) != 2:
    _usage()
else:
    template_path = sys.argv[1]
    data = sys.stdin.read()
    obj = json.loads(data)
    res = generate_report(obj, template_path)
    res = res.encode('utf-8')
    print res
