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

    def parent(self):
        if self.data:
            self.filehandler = StringIO.StringIO(data)
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
        command = self.extract_command(options)

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
        input = self.path or self.filehandler
        with zipfile.ZipFile(input) as f:
            return f.namelist()

    def _extract_command(self, options):
        return ['unzip', '-qq']

@filedriver
class GzipDriver(FileDriver):
    extensions = ['tar.gz', 'tgz']
    mimes = ['application/gzip']

    def _getlist(self):
        import tarfile
        with tarfile.open(name=self.path, fileobj=self.filehandler, mode="r|gz") as f:
            return f.getnames()

    def _extract_command(self, options):
        return ['tar', 'xzf']

@filedriver
class BzipDriver(FileDriver):
    extensions = ['tar.bz', 'tbz', 'tar.bz2']
    mimes = ['application/bzip']

    def _getlist(self):
        import tarfile
        with tarfile.open(name=self.path, fileobj=self.filehandler, mode="r|bz2") as f:
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

if len(sys.argv) > 1:
    for file in sys.argv[1:]:
        driv = DriverFromPath(file)
        if driv:
            driv.extract({})
else:
    if sys.stdin.isatty():
        print 'Usage: unpack [-v|--verbose] [<file>  ...]'
        print
        exit(1)
    data = sys.stdin.read()
    driv = DriverFromData(data)
    if driv:
        driv.extract({})

