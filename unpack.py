#!/usr/bin/env python2
import argparse
import os
import StringIO
import sys

extmap={}
mimemap={}

def get_mimetype(data):
    ''' Get the mimetype from the data contents of a file.'''
    from subprocess import Popen, PIPE
    commands = 'file --mime --brief -'.split()
    fileproc = Popen(commands, stdin=PIPE, stdout=PIPE)
    mimetype, err = fileproc.communicate(data)
    return mimetype

def filedriver(extensions=None, mimes=None):
    ''' Decorator for file drivers, assign the class to the required extensions
    or mimetypes, into the global dictionaries extmap and mimemap. Both
    extensions and mimes can be a string, or a list of strings.'''
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
    ''' Main class to derive the format-specific classes. In the derivation,
    implement the abstract methods: open, close, filelist and extract.'''
    def __init__(self, data, env, path='unpack'):
        self.path = path
        self.data = data
        self.env = env

    def open(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def filelist(self):
        raise NotImplementedError()

    def extract(self, filename, path):
        raise NotImplementedError()

    @staticmethod
    def common_parent(filelist):
        '''Calculate the common parent name of the files in the archive. If this
        function returns a folder, means that the file is not a tarbomb.'''
        dirnames = map(os.path.dirname, filelist)
        common = os.path.commonprefix(dirnames)
        return common

    @staticmethod
    def unique_dirname(base):
        '''From a given directory name, generate a unique one if that is
        already occupied.'''
        if base.endswith('/'):
            base = base[:-1]
        n = 0
        target = base
        while os.path.exists(target):
            n+=1
            target = '{0}-{1}'.format(base, n)
        return target

    def calculate_mappings(self):
        '''Calculate the path to extract each file, return as a list of pairs.
        This takes into consideration any possible path remaping or environment
        flag.'''

        filelist = self.filelist()
        self.filemaps = []

        parent = self.common_parent(filelist)
        if parent:
            extractdir = parent
        else:
            extractdir, _ = os.path.splitext(self.path)

        if not self.env.force:
            extractdir = self.unique_dirname(extractdir)

        for path in filelist:
            if parent:
                _, _, tmppath = path.partition(parent)
                if tmppath.startswith('/'):
                    tmppath = tmppath[1:]
            else:
                tmppath = path
            outpath = os.path.join(extractdir, tmppath)
            self.filemaps.append((path, outpath))

    def process(self):
        '''Run the command selected by the user in the environment flags.'''
        self.open()
        self.calculate_mappings()

        if self.env.list:
            self.command_list()
        else:
            self.command_extract()

        self.close()

    def command_extract(self):
        '''Extract the contents of the file.'''
        for path, epath in self.filemaps:
            if self.env.verbose:
                print epath
            if not self.env.dryrun:
                self.extract(path, epath)

    def command_list(self):
        '''List the contents of the file.'''
        for path, epath in self.filemaps:
            print path

@filedriver('zip', 'application/zip')
class ZipDriver(FileDriver):
    def open(self):
        import zipfile
        self.filehandler = StringIO.StringIO(self.data)
        self.ziphandler = zipfile.ZipFile(self.filehandler)

    def close(self):
        self.ziphandler.close()

    def filelist(self):
        return self.ziphandler.namelist()

    def extract(self, filename, path):
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

class BaseTarDriver(FileDriver):
    def close(self):
        self.tarhandler.close()

    def filelist(self):
        return self.tarhandler.getnames()

    def _getdata(self, filename):
        filedata = self.tarhandler.extractfile(filename)
        return filedata

    def extract(self, filename, path):
        if filename.endswith('/'):
            return
        dir = os.path.dirname(path)
        if not os.path.exists(dir):
            os.makedirs(dir)
        filedata = self._getdata(filename)
        if not filedata:
            return
        fileout = open(path, 'w')
        fileout.write(filedata.read())
        fileout.close()
        filedata.close()

@filedriver(['tar.gz', 'tgz'], ['application/gzip', 'application/x-gzip'])
class GzipDriver(BaseTarDriver):
    def open(self):
        import tarfile
        self.filehandler = StringIO.StringIO(self.data)
        self.tarhandler = tarfile.open(fileobj=self.filehandler, mode='r:*')

@filedriver(['tar.bz', 'tbz', 'tar.bz2'], ['application/bzip'])
class BzipDriver(BaseTarDriver):
    def open(self):
        import tarfile
        self.filehandler = StringIO.StringIO(self.data)
        self.tarhandler = tarfile.open(fileobj=self.filehandler, mode='r:*')

def DriverFromPath(path, env):
    '''Factory, get a Driver from the path of a file.'''
    try:
        with open(path, 'r') as f:
            data = f.read()
            for extension, driver in extmap.iteritems():
                if path.endswith(extension):
                    return driver(data, env, path=path)
            return None
    except IOError as e:
        print 'Input error when reading {0}: {1}'.format(path, e.strerror)
        exit(1)

def DriverFromData(data, env):
    '''Factory, get a Driver from the data of a file, no path known.'''
    mimetype = get_mimetype(data);
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
        driv = DriverFromPath(filepath, environment)
        if driv:
            driv.process()
        else:
            print 'Unrecognized file format of {0}'.format(filepath)
            exit(1)

    if not environment.filepath:
        data = sys.stdin.read()
        driv = DriverFromData(data, environment)
        if driv:
            driv.process()

if __name__ == '__main__':
    main()

