import email.mime.text
import logging
import logging.handlers
import optparse
import os
import os.path
import re
import shlex
import smtplib
import subprocess
import sys

default_emails = []
default_email_subject = 'OBT ERROR'
default_email_text = ''
default_from_email = 'obtbot@obtdev.com'
default_logfile = 'logs/obtmon.log'
default_log_level = 'warning'
default_monitors = []
default_monfile = 'conf/monitors.conf'

log_levels = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
    }

def monitor_callback(option, opt_str, value, parser):
  if len(parser.rargs) <= 1:
    parser.error('monitor must take at least two arguments')
    return

  monitor_name = parser.rargs[0]
  del parser.rargs[0]
  monitor_cmd = parser.rargs[0]
  del parser.rargs[0]

  if len(parser.rargs) > 0 and not parser.rargs[0].startswith('-'):
    config = parser.rargs[0]
    try:
      f = open(config)
      for line in config:
        args += line.strip().split()
      f.close()
    except IOError, e:
      parser.error('failed to read config file %s for monitor %s' % (config,monitor_name))
    else:
      monitor_cmd += ' '.join(args)
    del parser.rargs[0]
  getattr(parser.values, option.dest).append({
    'name': monitor_name,
    'cmd': monitor_cmd,
    })
 
def main(argv=None):
  if argv == None:
    argv = sys.argv[1:]

  parser = optparse.OptionParser()
  parser.add_option('-m','--monitor',action='callback',callback=monitor_callback,default=default_monitors,dest='monitors',help='use monitor MON (in addition to monitors specified with -M and other -ms)',metavar='MON')
  parser.add_option('-M','--monfile',default=default_monfile,dest='monfile',help='use monitors from file MON (in addition to monitors specified with -ms)',metavar='MON')
  parser.add_option('-l','--log',default=default_logfile,dest='logfile',help='send log messages to LOG',metavar='LOG')
  parser.add_option('-L','--loglevel',default=default_log_level,dest='log_level',help='set log level to LEVEL (one of: "debug", "info", "warning", "error", "critical")',metavar='LEVEL')
  parser.add_option('-e','--email',action='append',default=default_emails,dest='emails',help='on failure, send e-mails to EMAIL (in addition to e-mails specified with other -es)',metavar='EMAIL')
  parser.add_option('-E','--from-email',default=default_from_email,dest='from_email',help='on failure, send e-mails from EMAIL',metavar='EMAIL')
  parser.add_option('-s','--subject',default=default_email_subject,dest='email_subject',help='on failure, send e-mails with this SUBJECT',metavar='SUBJECT')
  parser.add_option('-t','--text',default=default_email_text,dest='email_text',help='on failure, include TEXT in the e-mail (for identifying jobs)',metavar='TEXT')

  (options, args) = parser.parse_args()
  
  if options.log_level not in log_levels:
    parser.error('bad log level, must be one of: "debug", "info", "warning", "error", "critical"')
    return 1

  obt_logger = logging.getLogger('obtmon')
  obt_logger.setLevel(log_levels[options.log_level])
  logdir = os.path.split(options.logfile)[0]
  if not os.path.exists(logdir):
    os.makedirs(logdir)
  obt_handler = logging.handlers.RotatingFileHandler(options.logfile, maxBytes=1000000, backupCount=10)
  obt_logger.addHandler(obt_handler)
  
  try:
    obt_logger.debug('processing monitors file: %s' % options.monfile)
    f = open(options.monfile)
    for line in f:
      parts = re.split(r':\s*',line.strip(),1)
      if len(parts) != 2:
        obt_logger.warning('bad line in monitor file, should be of the form "<name>: <command>": %s' % line)
        continue

      monitor_name,monitor_cmd = parts
      options.monitors.append({
        'name': monitor_name,
        'cmd': monitor_cmd,
        })
    f.close()
    obt_logger.debug('finished processing monitors file: %s' % options.monfile)
  except IOError, e:
    obt_logger.warning('failed to read monitor file %s: %s' % (options.monfile, e.strerror))

  if len(options.monitors) == 0:
    obt_logger.warning('no monitors specified, doing nothing')
    return 0

  # TODO: run monitors in parallel (optionally)
  obt_logger.debug('STARTING all monitors')
  problems = []
  for monitor in options.monitors:
    obt_logger.debug('starting work on monitor: ' + monitor['name'])
    try:
      obt_logger.debug('running command: ' + monitor['cmd'])
      args = shlex.split(monitor['cmd'])
      process = subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
      stdout,stderr = process.communicate()
      retcode = process.returncode
    except OSError,e:
      stdout = ''
      stderr = 'Failed to call monitor. Error was: %s' % str(e)
      retcode = -1

    stdout = stdout.strip()
    stderr = stderr.strip()

    obt_logger.debug('finished work on monitor: %s' % monitor['name'])
    obt_logger.debug('retcode: %d' % retcode)
    obt_logger.debug('stdout: %s' % stdout)
    obt_logger.debug('stderr: %s' % stderr)

    if retcode:
      obt_logger.debug('found error while working on monitor: ' + monitor['name'])
      problems.append({
        'monitor': monitor['name'],
        'stdout': stdout,
        'stderr': stderr,
        'retcode': retcode})
      

  obt_logger.debug('FINISHED all monitors')
  if len(problems) > 0:
    error_text = 'The following monitors FAILED: %s\n\n' % ', '.join([problem['monitor'] for problem in problems])
    if options.email_text:
      error_text += '%s\n\n' % options.email_text

    error_text += 'Details:\n' 
    for problem in problems:
      error_text += 'Monitor %s returned %d\n' % (problem['monitor'], problem['retcode'])
      error_text += '----\n'
      error_text += 'stdout:\n'
      error_text += '%s\n' % problem['stdout']
      error_text += '----\n'
      error_text += 'stderr:\n'
      error_text += '%s\n' % problem['stderr']
      error_text += '----\n'
      error_text += '\n'

    obt_logger.error(error_text)
    if len(options.emails) > 0:
      obt_logger.debug('sending e-mail to addresses: ' + ', '.join(options.emails))
      msg = email.mime.text.MIMEText(error_text)
      msg['Subject'] = options.email_subject
      msg['To'] = ', '.join(options.emails)
      msg['From'] = options.from_email
      s = smtplib.SMTP('localhost')
      s.sendmail(options.from_email,options.emails, msg.as_string())
      s.quit()
      obt_logger.debug('finished sending e-mail')
    else:
      obt_logger.debug('not sending any e-mails, since no addresses were given')
    return 1
  else:
    obt_logger.debug('not sending any e-mails, since there were no errors')

  return 0

if __name__ == '__main__':
  sys.exit(main())
