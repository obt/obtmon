#!/usr/bin/python

import optparse
import re
import subprocess
import sys

default_count = 2
def main(argv=None):
  if argv is None:
    argv = sys.argv[1:]

  parser = optparse.OptionParser(usage='%prog [options] <server>')
  parser.add_option('-c','--count',default=default_count,dest='count',type='int',help='send COUNT packets when pinging',metavar='COUNT')

  (options, args) = parser.parse_args()
  if len(args) < 1:
    parser.error('missing argument server')

  server = args[0]

  ping_proc = subprocess.Popen(['ping','-q','-c%d'%options.count,'-W1',server],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  stdout,stderr = ping_proc.communicate()
  retcode = ping_proc.returncode
  if not retcode:
    num_received_match = re.search(r'(\d) received',stdout)
    if num_received_match:
      num_received = num_received_match.groups()[0]
      if num_received < options.count/2.0:
        retcode = -1
        stderr = 'Fewer than half of packets were received (%d sent, %d received)' % (options.count, num_received)
    else:
      retcode = -1
      stderr = 'Incomprehensible output from ping: %s' % stdout

  if stderr:
    print >>sys.stderr, stderr.strip()
  return retcode

if __name__ == '__main__':
  sys.exit(main())
