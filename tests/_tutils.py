#! python
#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import logging
import os
from tempfile import mkdtemp


log = logging.getLogger(__name__)


DEFAULT_LOG_LEVEL = logging.INFO


def _init_logging(module_name, loglevel=DEFAULT_LOG_LEVEL):
    logging.basicConfig(level=loglevel)
    logging.getLogger().setLevel(level=loglevel)

    log = logging.getLogger(module_name)
    log.trace = lambda *args, **kws: log.log(0, *args, **kws)

    return log


class CustomAssertions(object):
    # Idea from: http://stackoverflow.com/a/15868615/548792

    def _raise_file_msg(self, msg, path, user_msg):
        msg = msg % os.path.abspath(path)
        if user_msg:
            msg = '%s: %s' % (msg, user_msg)
        raise AssertionError(msg)

    def assertFileExists(self, path, user_msg=None):
        if not os.path.lexists(path):
            self._raise_file_msg(
                "File does not exist in path '%s'!", path, user_msg)

    def assertFileNotExists(self, path, user_msg=None):
        if os.path.lexists(path):
            self._raise_file_msg("File exists in path '%s'!", path, user_msg)

try:
    from tempfile import TemporaryDirectory  # @UnusedImport
except ImportError:
    class TemporaryDirectory(object):
    
        """Create and return a temporary directory.  This has the same
        behavior as mkdtemp but can be used as a context manager.  For
        example:
    
            with TemporaryDirectory() as tmpdir:
                ...
    
        Upon exiting the context, the directory and everything contained
        in it are removed.
    
        From: http://stackoverflow.com/questions/19296146/tempfile-temporarydirectory-context-manager-in-python-2-7 
              http://stackoverflow.com/a/19299884/548792
        """
    
        def __init__(self, suffix="", prefix="tmp", dir=None):
            self._closed = False
            self.name = None  # Handle mkdtemp raising an exception
            self.name = mkdtemp(suffix, prefix, dir)
    
        def __repr__(self):
            return "<{} {!r}>".format(self.__class__.__name__, self.name)
    
        def __enter__(self):
            return self.name
    
        def cleanup(self, _warn=False):
            if self.name and not self._closed:
                try:
                    self._rmtree(self.name)
                except (TypeError, AttributeError) as ex:
                    # Issue #10188: Emit a warning on stderr
                    # if the directory could not be cleaned
                    # up due to missing globals
                    if "None" not in str(ex):
                        raise
                    log.warning("ERROR: %s while cleaning up %s", ex, self)
                    return
                self._closed = True
                log.warning("Implicitly cleaning up %s", self)
    
        def __exit__(self, exc, value, tb):
            self.cleanup()
    
        def __del__(self):
            # Issue a ResourceWarning if implicit cleanup needed
            self.cleanup(_warn=True)
    
        # XXX (ncoghlan): The following code attempts to make
        # this class tolerant of the module nulling out process
        # that happens during CPython interpreter shutdown
        # Alas, it doesn't actually manage it. See issue #10188
        _listdir = staticmethod(os.listdir)
        _path_join = staticmethod(os.path.join)
        _isdir = staticmethod(os.path.isdir)
        _islink = staticmethod(os.path.islink)
        _remove = staticmethod(os.remove)
        _rmdir = staticmethod(os.rmdir)
    
        def _rmtree(self, path):
            # Essentially a stripped down version of shutil.rmtree.  We can't
            # use globals because they may be None'ed out at shutdown.
            for name in self._listdir(path):
                fullname = self._path_join(path, name)
                try:
                    isdir = self._isdir(fullname) and not self._islink(fullname)
                except OSError:
                    isdir = False
                if isdir:
                    self._rmtree(fullname)
                else:
                    try:
                        self._remove(fullname)
                    except OSError:
                        pass
            try:
                self._rmdir(path)
            except OSError:
                pass