#!/usr/bin/python

import email.mime.text
import optparse
import smtplib
import sys

default_subject = 'OBTMON ERROR!'
default_from = 'obtbot@obtdev.com'

def main(argv=None):
  if argv is None:
    argv = sys.argv[1:]

  #TODO add way to specify a password in a secure way
  parser = optparse.OptionParser(usage='%prog [options] <username> <password> <recipient-addr> [recipient-addr] ...')
  parser.add_option('-s','--subject',default=default_subject,dest='subject',help='Send an e-mail with this SUBJECT',metavar='SUBJECT')
  parser.add_option('-f','--from',default=default_from,dest='from_addr',help='Send an e-mail from ADDRESS',metavar='ADDRESS')

  (options, args) = parser.parse_args()
  if len(args) < 3:
    parser.error('missing arguments username, password, email')
  username, password, emails = args[0], args[1], args[2:]

  message_text = sys.stdin.read()
  if not message_text:
    parser.error('no message text sent through STDIN')

  print 'sending with Gmail user %s to e-mail to addresses: %s' % (username, ', '.join(emails))
  msg = email.mime.text.MIMEText(message_text)
  msg['Subject'] = options.subject
  msg['To'] = ', '.join(emails)
  msg['From'] = options.from_addr
  s = smtplib.SMTP('smtp.gmail.com',587)
  s.ehlo()
  s.starttls()
  s.login(username, password)
  s.sendmail(options.from_addr, emails, msg.as_string())
  s.quit()
  print 'finished sending e-mail'

if __name__ == '__main__':
  sys.exit(main())
