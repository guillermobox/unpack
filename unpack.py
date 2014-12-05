import optparse
import os
import subprocess
import StringIO
import sys

extmap={}
mimemap={}

def filedriver(driver):
    for extension in driver.extensions:
        extmap['.' + extension] = driver
    for mime in driver.mimes:
        mimemap[mime] = driver

class FileDriver(object):
    def __init__(self, path, data=None):
        self.path = path
        self.data = data

        if not self.data:
            self.data = open(self.path, 'r').read()

    def name(self):
        if self.path:
            return self.path
        else:
            return 'piped data'

    def parent(self):
        files = self._getlist()
        common = os.path.commonprefix(files)
        if common != '' and len(files) == 1:
            return ''
        return common

    def getdirname(self, base, options={}):
        n = 0
        target = base
        while os.path.exists(target):
            n+=1
            target = '{0}.{1}'.format(base, n)
        return target

    def extract(self, options):
        command = self._extract_command(options)

        if not self.parent():
            if self.path:
                extractdir, _ = os.path.splitext(self.path)
            else:
                extractdir = 'unpack'
        else:
            extractdir = '.'

        if self.path:
            if extractdir != '.':
                command.append('../'+self.path)
                extractdir = self.getdirname(extractdir)
                os.mkdir(extractdir)
                os.chdir(extractdir)
                print 'Extracting {0} in {1}'.format(self.path, extractdir)
                subprocess.call(command)
                os.chdir('..')
            else:
                command.append(self.path)
                print 'Extracting {0} in {1}'.format(self.path, self.parent())
                subprocess.call(command)
        else:
            command.append('-')
            if extractdir != '.':
                extractdir = self.getdirname(extractdir)
                os.mkdir(extractdir)
                os.chdir(extractdir)
                proc = subprocess.Popen(command, stdin=subprocess.PIPE)
                proc.communicate(self.data)
                print 'Extracting {0} in {1}'.format('piped input', extractdir)
                ret = proc.wait()
            else:
                proc = subprocess.Popen(command, stdin=subprocess.PIPE)
                proc.communicate(self.data)
                print 'Extracting {0} in {1}'.format('piped input', self.parent())
                ret = proc.wait()

@filedriver
class ZipDriver(FileDriver):
    extensions = ['zip']
    mimes = ['application/zip']

    def _getlist(self):
        import zipfile
        self.filehandler = StringIO.StringIO(self.data)
        with zipfile.ZipFile(self.filehandler) as f:
            return f.namelist()

    def _extract_command(self, options):
        return ['unzip', '-qq']

@filedriver
class GzipDriver(FileDriver):
    extensions = ['tar.gz', 'tgz']
    mimes = ['application/gzip', 'application/x-gzip']

    def _getlist(self):
        import tarfile

        self.filehandler = StringIO.StringIO(self.data)
        with tarfile.open(f.path, fileobj=self.filehandler, mode="r|gz") as f:
            return f.getnames()

    def _extract_command(self, options):
        return ['tar', 'xzf']

@filedriver
class BzipDriver(FileDriver):
    extensions = ['tar.bz', 'tbz', 'tar.bz2']
    mimes = ['application/bzip']

    def _getlist(self):
        import tarfile

        self.filehandler = StringIO.StringIO(self.data)
        with tarfile.open(fileobj=self.filehandler, mode="r|bz2") as f:
            return f.getnames()

    def _extract_command(self, options):
        return ['tar', 'xjf']

def DriverFromPath(path):
    for extension, driver in extmap.iteritems():
        if path.endswith(extension):
            return driver(path)
    return None

def DriverFromData(data):
    fileproc = subprocess.Popen(['file', '--mime', '--brief', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    mimetype, err = fileproc.communicate(data)
    for mime, driver in mimemap.iteritems():
        if mimetype.startswith(mime):
            return driver(None, data)
    return None

usage = 'usage: %prog [options] [<filename> ...]'
parser = optparse.OptionParser(usage)
parser.add_option('-v', '--verbose', action='store_true', dest='verbose', help='show a list of the extracted files', default=False)
parser.add_option('-f', '--force', action='store_true', dest='force', help='force the extraction of the file to the default folder, even overwirting existing files', default=False)
parser.add_option('-n', '--dryrun', action='store_true', dest='dryrun', help='only show the actions that will be done, don\'t touch the disk', default=False)
parser.add_option('-t', '--tarbomb', action='store_true', dest='tarbomb', help='extract the files to the working directory, even if it\'s considered a tarbomb', default=False)
parser.add_option('-o', '--output', metavar='DIR', dest='output', help='extract the files to the given output folder')

(options, args) = parser.parse_args()

if args:
    for file in args:
        driv = DriverFromPath(file)
        if driv:
            driv.extract({})
else:
    if sys.stdin.isatty():
        parser.print_help()
        exit(1)
    data = sys.stdin.read()
    driv = DriverFromData(data)
    if driv:
        driv.extract({})

