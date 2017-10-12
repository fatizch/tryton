#!/usr/bin/env python
# -*- encoding: utf-8 -*-
import os
import shutil
import argparse
from doc_generation import generate
import logging


if __name__ == '__main__':
    logging.basicConfig()
    logger = logging.getLogger()
    parser = argparse.ArgumentParser(description='Document generation script')
    parser.add_argument('--output_doc_directory', help='Absolute path where '
        'the documentation will be generated', default=None, nargs='?')
    args = parser.parse_args()
    doc_files, final_html_path = generate(args.output_doc_directory)
    shutil.copytree(os.path.join(doc_files, '_build', 'html'), final_html_path)
    logger.info('HTML folder copied to ' + final_html_path)
