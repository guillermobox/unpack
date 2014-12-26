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
    def __init__(self, data, env, path='unpack'):
        self.path = path
        self.data = data
        self.env = env

    def parent(self):
        '''Calculate the common parent name of the files in the archive.'''
        dirnames = map(os.path.dirname, self.filelist)
        common = os.path.commonprefix(dirnames)
        return common

    def get_unique_dirname(self, base):
        '''From a given directory name, generate a unique one if that is
        already occupied.'''
        if base.endswith('/'):
            base = base[:-1]
        n = 0
        target = base
        if self.env.force:
            return target
        while os.path.exists(target):
            n+=1
            target = '{0}-{1}'.format(base, n)
        return target

    def fix_path(self, path, extractdir, remap=False):
        '''Fix the path provided using the new extract dir. Remap means that the
        base directory of the file to be extracted will be renamed.'''
        if self.env.tarbomb:
            return path
        else:
            if remap:
                _, _, path = path.partition('/')
            return os.path.join(extractdir, path)

    def get_extractdir(self):
        '''Get the extract dir for the files in the archive. If there is
        neccesary a remap of the basename of the files, is applied here.'''
        common_folder = self.parent()
        if common_folder:
            remap = True
            extractdir = self.get_unique_dirname(common_folder)
        else:
            remap = False
            extractdir, _ = os.path.splitext(self.path)
            extractdir = self.get_unique_dirname(extractdir)
        return extractdir, remap

    def process(self):
        remap = False
        self.open()
        self.get_filelist()

        if self.env.list:
            self.command_list()
        else:
            self.command_extract()

    def command_extract(self):
        extractdir, remap = self.get_extractdir()

        for file in self.filelist:
            outfile = self.fix_path(file, extractdir, remap)
            if self.env.verbose:
                print outfile
            if not self.env.dryrun:
                self.extract_file(file, outfile)

        self.close()

    def command_list(self):
        for file in self.filelist:
            print file

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

class BaseTarDriver(FileDriver):
    def close(self):
        self.tarhandler.close()

    def get_filelist(self):
        self.filelist = self.tarhandler.getnames()

    def _getdata(self, filename):
        filedata = self.tarhandler.extractfile(filename)
        return filedata

    def extract_file(self, filename, path):
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
    data = open(path, 'r').read()
    for extension, driver in extmap.iteritems():
        if path.endswith(extension):
            return driver(data, env, path=path)
    return None

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

    if not environment.filepath:
        data = sys.stdin.read()
        driv = DriverFromData(data, environment)
        if driv:
            driv.process()

if __name__ == '__main__':
    main()

