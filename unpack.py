import optparse
import os
import subprocess
import StringIO
import sys

extmap={}
mimemap={}

def filedriver(extensions=None, mimes=None):
    if isinstance(extensions, str):
        extensions = [extensions]

    if isinstance(mimes, str):
        mimes = [mimes]

    def inner_filedriver(driver):
        for extension in extensions or []:
            extmap['.' + extension] = driver
        for mime in mimes or []:
            mimemap[mime] = driver
    return inner_filedriver

class FileDriver(object):
    def __init__(self, path, data=None, options=None):
        self.path = path or 'unpack'
        self.data = data
        self.options = options or {}

        if not self.data:
            self.data = open(self.path, 'r').read()

    def name(self):
        if self.path:
            return self.path
        else:
            return 'piped data'

    def parent(self):
        self.get_filelist()
        common = os.path.commonprefix(map(os.path.dirname, self.filelist))
        return common

    def getdirname(self, base, options={}):
        if base.endswith('/'):
            base = base[:-1]
        n = 0
        target = base
        while os.path.exists(target):
            n+=1
            target = '{0}-{1}'.format(base, n)
        return target

    def fix_path(self, path, extractdir, remap=False):
        "Fix the path provided using the new extract dir."
        if self.options.tarbomb:
            return path
        else:
            if remap:
                _, _, path = path.partition('/')
            return os.path.join(extractdir, path)

    def extract(self, options):

        remap = False
        self.open()

        common_folder = self.parent()
        if common_folder:
            remap = True
            extractdir = self.getdirname(common_folder)
        else:
            extractdir, _ = os.path.splitext(self.path)
            extractdir = self.getdirname(extractdir)


        print 'Extract dir', extractdir, remap, common_folder

        for file in self.filelist:
            outfile = self.fix_path(file, extractdir, remap)
            if self.options.verbose:
                print 'Extracting',filename,'to',outfile
            self.extract_file(file, outfile)

        self.close()

@filedriver('zip', 'application/zip')
class ZipDriver(FileDriver):
    def open(self):
        import zipfile
        self.filehandler = StringIO.StringIO(self.data)
        self.ziphandler = zipfile.ZipFile(self.filehandler)

    def close(self):
        self.ziphandler.close()

    def get_filelist(self):
        self.filelist = self.ziphandler.namelist()

    def extract_file(self, filename, path):
        dir = os.path.dirname(path)
        if not os.path.exists(dir):
            os.makedirs(dir)
        filedata = self.ziphandler.open(filename, 'r')
        fileout = open(path, 'w')
        fileout.write(filedata.read())
        fileout.close()
        filedata.close()

@filedriver(['tar.gz', 'tgz'], ['application/gzip', 'application/x-gzip'])
class GzipDriver(FileDriver):
    pass

#    def _getlist(self):
#        import tarfile
#
#        self.filehandler = StringIO.StringIO(self.data)
#        with tarfile.open(f.path, fileobj=self.filehandler, mode="r|gz") as f:
#            return f.getnames()
#
#    def _extract_command(self, options):
#        return ['tar', 'xzf']

@filedriver(['tar.bz', 'tbz', 'tar.bz2'], ['application/bzip'])
class BzipDriver(FileDriver):
    pass

#    def _getlist(self):
#        import tarfile
#
#        self.filehandler = StringIO.StringIO(self.data)
#        with tarfile.open(fileobj=self.filehandler, mode="r|bz2") as f:
#            return f.getnames()
#
#    def _extract_command(self, options):
#        return ['tar', 'xjf']

def DriverFromPath(path, options):
    for extension, driver in extmap.iteritems():
        if path.endswith(extension):
            return driver(path, None, options)
    return None

def DriverFromData(data, options):
    fileproc = subprocess.Popen(['file', '--mime', '--brief', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    mimetype, err = fileproc.communicate(data)
    for mime, driver in mimemap.iteritems():
        if mimetype.startswith(mime):
            return driver(None, data, options)
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
        driv = DriverFromPath(file, options)
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

