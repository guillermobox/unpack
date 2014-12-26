import argparse
import os
import StringIO
import sys

extmap={}
mimemap={}

# Get the mime type of a certain file data string
def getmimetype(data):
    from subprocess import Popen, PIPE
    commands = 'file --mime --brief -'.split()
    fileproc = Popen(commands, stdin=PIPE, stdout=PIPE)
    mimetype, err = fileproc.communicate(data)
    return mimetype

# Decorator for file drivers, assign the class to the required extensions or
# mimetypes, into the global dictionaries extmap and mimemap. Both extensions
# and mimes can be a string, or a list of strings.
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
    def __init__(self, data, env, path='unpack'):
        self.path = path
        self.data = data
        self.env = env

    def name(self):
        if self.path:
            return self.path
        else:
            return 'piped data'

    def parent(self):
        common = os.path.commonprefix(map(os.path.dirname, self.filelist))
        return common

    def getdirname(self, base):
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
        if self.env.tarbomb:
            return path
        else:
            if remap:
                _, _, path = path.partition('/')
            return os.path.join(extractdir, path)

    def extract(self):

        remap = False
        self.open()
        self.get_filelist()

        common_folder = self.parent()
        if common_folder:
            remap = True
            extractdir = self.getdirname(common_folder)
        else:
            extractdir, _ = os.path.splitext(self.path)
            extractdir = self.getdirname(extractdir)

        for file in self.filelist:
             outfile = self.fix_path(file, extractdir, remap)
             if self.env.verbose:
                 print outfile
             outfile = file
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
        if filename.endswith('/'):
            return
        dir = os.path.dirname(path)
        if not os.path.exists(dir):
            os.makedirs(dir)
        info = self.ziphandler.getinfo(filename)
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

def DriverFromPath(path, env):
    data = open(path, 'r').read()
    for extension, driver in extmap.iteritems():
        if path.endswith(extension):
            return driver(data, env, path=path)
    return None

def DriverFromData(data, env):
    mimetype = getmimetype(data);
    for mime, driver in mimemap.iteritems():
        if mimetype.startswith(mime):
            return driver(data, env)
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true', dest='verbose', help='show a list of the extracted files', default=False)
    parser.add_argument('-f', '--force', action='store_true', dest='force', help='force the extraction of the file to the default folder, even overwirting existing files', default=False)
    parser.add_argument('-n', '--dryrun', action='store_true', dest='dryrun', help='only show the actions that will be done, don\'t touch the disk', default=False)
    parser.add_argument('-t', '--tarbomb', action='store_true', dest='tarbomb', help='extract the files to the working directory, even if it\'s considered a tarbomb', default=False)
    parser.add_argument('-o', '--output', metavar='DIR', dest='output', help='extract the files to the given output folder')
    parser.add_argument('-l', '--list', action='store_true', dest='list', help='list the contents of the archive', default=False)
    parser.add_argument('filepath', nargs='*', help='compressed file to work with')

    environment = parser.parse_args()

    if not environment.filepath and sys.stdin.isatty():
        parser.print_help()
        exit(1)

    for filepath in environment.filepath:
        print filepath
        driv = DriverFromPath(filepath, environment)
        if driv:
            driv.extract()

    if not environment.filepath:
        data = sys.stdin.read()
        driv = DriverFromData(data, environment)
        if driv:
            driv.extract()

if __name__ == '__main__':
    main()

