import sys
import os
import argparse

import sendgrid
from sendgrid.helpers.mail import *


def main():
    parser = argparse.ArgumentParser(description='Coog utils to send mail')
    parser.add_argument('--expeditor', '-f', required=True, help='From address')
    parser.add_argument('--destination', '-t', required=True, help='To address')
    parser.add_argument('--subject', '-s', required=True, help='Subject')
    arguments = parser.parse_args()
    sg = sendgrid.SendGridAPIClient(apikey=os.environ.get('SENDGRID_API_KEY'))
    from_email = Email(arguments.expeditor)
    to_email = Email(arguments.destination)
    subject = arguments.subject
    content = Content('text/plain', sys.stdin.read())
    mail = Mail(from_email, subject, to_email, content)
    response = sg.client.mail.send.post(request_body=mail.get())
    if response.status_code >= 300:
        print response.body
        print response.headers
        sys.exit(1)

main()
