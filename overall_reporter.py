import logging
import logging.handlers
import optparse
import os
import os.path
import re
import shlex
import subprocess
import sys

default_logfile = 'logs/obtmon.log'
default_log_level = 'warning'
default_monitors = []
default_monfile = 'conf/monitors.conf'
default_reporters = []
default_repfile = 'conf/reporters.conf'

log_levels = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
    }

def processor_callback(option, opt_str, value, parser):
  if len(parser.rargs) <= 1:
    parser.error('%s must take at least two arguments' % opt_str)
    return

  processor_name = parser.rargs[0]
  del parser.rargs[0]
  processor_cmd = parser.rargs[0]
  del parser.rargs[0]

  if len(parser.rargs) > 0 and not parser.rargs[0].startswith('-'):
    config = parser.rargs[0]
    try:
      f = open(config)
      for line in config:
        args += line.strip().split()
      f.close()
    except IOError, e:
      parser.error('failed to read config file %s for %s %s' % (config,opt_str,processor_name))
    else:
      processor_cmd += ' '.join(args)
    del parser.rargs[0]
  getattr(parser.values, option.dest).append({
    'name': processor_name,
    'cmd': processor_cmd,
    })
 
def read_processor_file(proc_file, proc_type, logger):
  processors = []
  try:
    logger.debug('processing %s file: %s' % (proc_type, proc_file))
    f = open(proc_file)
    for line in f:
      parts = re.split(r':\s*',line.strip(),1)
      if len(parts) != 2:
        logger.warning('bad line in %s file, should be of the form "<name>: <command>": %s' % (proc_type, line))
        continue

      proc_name,proc_cmd = parts
      processors.append({
        'name': proc_name,
        'cmd': proc_cmd,
        })
    f.close()
    logger.debug('finished processing %s file: %s' % (proc_type, proc_file))
  except IOError, e:
    logger.warning('failed to read %s file %s: %s' % (proc_type, proc_file, e.strerror))
  return processors

def main(argv=None):
  if argv == None:
    argv = sys.argv[1:]

  parser = optparse.OptionParser()
  parser.add_option('-m','--monitor',action='callback',callback=processor_callback,default=default_monitors,dest='monitors',help='use monitor MON (in addition to monitors specified with -M and other -ms)',metavar='MON')
  parser.add_option('-M','--monfile',default=default_monfile,dest='monfile',help='use monitors from file MON (in addition to monitors specified with -ms)',metavar='MON')
  parser.add_option('-l','--log',default=default_logfile,dest='logfile',help='send log messages to LOG',metavar='LOG')
  parser.add_option('-L','--loglevel',default=default_log_level,dest='log_level',help='set log level to LEVEL (one of: "debug", "info", "warning", "error", "critical")',metavar='LEVEL')
  parser.add_option('-r','--reporters',action='callback',callback=processor_callback,default=default_reporters,dest='reporters',help='use reporter REP (in addition to reporters specified with -R and other -rs)',metavar='REP')
  parser.add_option('-R','--repfile',default=default_repfile,dest='repfile',help='use reporters from file REP (in addition to reporters specified with -rs)',metavar='REP')

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
  obt_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
  obt_handler.setFormatter(obt_formatter)
  obt_logger.addHandler(obt_handler)
  
  options.monitors += read_processor_file(options.monfile,'monitors',obt_logger)
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

  #TODO: optionally issue reports even when there aren't errors (for graphs)
  if len(problems) > 0:
    error_text = 'The following monitors FAILED: %s\n\n' % ', '.join([problem['monitor'] for problem in problems])

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

    # TODO: run reporters in parallel (optionally)
    options.reporters += read_processor_file(options.repfile,'reporters',obt_logger)
    if len(options.reporters) > 0:
      obt_logger.debug('STARTING all reporters')
      for reporter in options.reporters:
        obt_logger.debug('starting work on reporter: ' + reporter['name'])
        try:
          obt_logger.debug('running command: ' + reporter['cmd'])
          args = shlex.split(reporter['cmd'])
          process = subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.PIPE)
          stdout,stderr = process.communicate(error_text)
          retcode = process.returncode
        except OSError,e:
          stdout = ''
          stderr = 'Failed to call reporter. Error was: %s' % str(e)
          retcode = -1

        stdout = stdout.strip()
        stderr = stderr.strip()

        obt_logger.debug('finished work on reporter: %s' % reporter['name'])
        obt_logger.debug('retcode: %d' % retcode)
        obt_logger.debug('stdout: %s' % stdout)
        obt_logger.debug('stderr: %s' % stderr)

        if retcode > 0:
          obt_logger.warning('reporter %s FAILED with retcode %d, stderr: %s' % (reporter['name'], retcode, stderr))

      obt_logger.debug('FINISHED all reporters')

    else:
      obt_logger.debug('not issuing any reports, since no reporters were given')

    return 1

  else:
    obt_logger.debug('not issuing any reports, since there were no errors')

  return 0

if __name__ == '__main__':
  sys.exit(main())
