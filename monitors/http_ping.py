#!/usr/bin/python

import base64
import optparse
import sys
import urllib2

def main(argv=None):
  if argv is None:
    argv = sys.argv[1:]

  parser = optparse.OptionParser(usage='%prog [options] <url>')
  #TODO add way to specify a password in a secure way
  parser.add_option('-a','--authorize',nargs=2,dest='authorize',help='authorize using USERNAME and PASSWORD',metavar=('USERNAME','PASSWORD'))

  (options, args) = parser.parse_args()
  if len(args) < 1:
    parser.error('missing argument url')

  url = args[0]

  if '://' not in url:
    url = 'http://' + url

  req = urllib2.Request(url)
  if options.authorize:
    auth_str = base64.encodestring('%s:%s' % options.authorize)[:-1]
    req.add_header('Authorization', 'Basic %s' % auth_str)
  try:
    urllib2.urlopen(req)
  except IOError, e:
    print >>sys.stderr, 'Failed to fetch url: %s (error: %s)' % (url, str(e))
    return 1
  return 0

if __name__ == '__main__':
  sys.exit(main())

