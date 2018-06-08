import sys
import os
import argparse

import sendgrid
from sendgrid.helpers.mail import *



def sendmail(from_addr, to_addrs, msg, server=None):
    if server is None:
        server = get_smtp_server()
        quit = True
    else:
        quit = False
    try:
        senderrs = server.sendmail(from_addr, to_addrs, msg.as_string())
    except smtplib.SMTPException:
        logger.error('fail to send email', exc_info=True)
    else:
        if senderrs:
            logger.warn('fail to send email to %s', senderrs)
    if quit:
        server.quit()

def main():
    parser = argparse.ArgumentParser(description='Coog utils to send mail')
    parser.add_argument('--fromemail', '-fe', required=True, help='From email')
    parser.add_argument('--fromname', '-fn', help='From name')
    parser.add_argument('--toemail', '-te', required=True, help='To email')
    parser.add_argument('--toname', '-tn', help='To name')
    parser.add_argument('--subject', '-s', required=True, help='Subject')
    arguments = parser.parse_args()
    sg = sendgrid.SendGridAPIClient(apikey=os.environ.get('SENDGRID_API_KEY'))

    f = Email(email=arguments.fromemail, name=arguments.fromname)
    t = Email(email=arguments.toemail, name=arguments.toname)
    subject = arguments.subject
    content = Content('text/html', sys.stdin.read())
    mail = Mail(f, subject, t, content)
    response = sg.client.mail.send.post(request_body=mail.get())
    if response.status_code >= 300:
        print response.body
        print response.headers
        sys.exit(1)


main()
