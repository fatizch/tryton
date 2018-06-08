#!/usr/bin/env python

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import argparse
import smtplib
import urllib

from urlparse import parse_qs, urlparse

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from trytond.config import config


def get_smtp_server(uri=None):
    if uri is None:
        uri = config.get('batch_report', 'uri')
    uri = urlparse(uri)
    extra = {}
    if uri.query:
        cast = {'timeout': int}
        for key, value in parse_qs(uri.query, strict_parsing=True).iteritems():
            extra[key] = cast.get(key, lambda a: a)(value[0])
    if uri.scheme.startswith('smtps'):
        server = smtplib.SMTP_SSL(uri.hostname, uri.port, **extra)
    else:
        server = smtplib.SMTP(uri.hostname, uri.port, **extra)

    if 'tls' in uri.scheme:
        server.starttls()

    if uri.username and uri.password:
        server.login(
            urllib.unquote_plus(uri.username),
            urllib.unquote_plus(uri.password))
    return server


def sendmail(from_addr, to_addrs, msg, server=None):
    if server is None:
        server = get_smtp_server()
        quit = True
    else:
        quit = False
    try:
        senderrs = server.sendmail(from_addr, to_addrs, msg.as_string())
    except Exception as e:
        print >> sys.stderr, str(e)
    if quit:
        server.quit()
    return senderrs


def main():
    parser = argparse.ArgumentParser(description='Coog utils to send mail')
    parser.add_argument('--fromemail', '-fe', required=True, help='From email')
    parser.add_argument('--toemail', '-te', required=True, help='To email')
    parser.add_argument('--ccemail', '-cce', help='cc email')
    parser.add_argument('--bccemail', '-bcce', help='bcc email')
    parser.add_argument('--subject', '-s', required=True, help='Subject')
    args = parser.parse_args()

    msg = MIMEMultipart('mixed')
    msg['From'] = args.fromemail
    msg['To'] = args.toemail
    msg['Cc'] = args.ccemail
    msg['Subject'] = args.subject
    msg['Charset'] = 'UTF-8'
    msg['Content-Type'] = 'text/plain; charset=UTF-8'

    body = sys.stdin.read() or ''
    msg.attach(MIMEText(body, 'html', 'UTF-8'))

    try:
        sendmail(args.fromemail,
            args.toemail or '' + args.ccemail or '' + args.bccemail or '',
            msg)
    except Exception as e:
        print >> sys.stderr, str(e)
        sys.exit(2)

if __name__ == '__main__':
    main()
