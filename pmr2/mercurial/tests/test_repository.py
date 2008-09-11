import unittest
import tempfile
import shutil
import os
from os.path import dirname, join
from pmr2.mercurial import Storage, Sandbox

class RepositoryInitTestCase(unittest.TestCase):

    def setUp(self):
        self.repodir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.repodir)

    def test_init_failed(self):
        # testing init would fail on a directory not managed by hg
        self.assertRaises(ValueError, Storage, self.repodir)

    def test_create_failed(self):
        # existing directory
        self.assertRaises(ValueError, Storage.create, self.repodir)
        # invalid location
        self.assertRaises(ValueError, Storage.create, '/dev/null', False)

    def test_create_success1(self):
        result = Storage.create(self.repodir, False)
        self.assert_(result, 'Storage not created')

    def test_create_success2(self):
        result = Storage.create(self.repodir + '/test', True)
        self.assert_(result, 'Storage not created')

    def test_init_success(self):
        Storage.create(self.repodir, False)
        store = Storage(self.repodir)
        self.assert_(isinstance(store, Storage))


class RepositoryTestCase(unittest.TestCase):

    def setUp(self):
        self.repodir = tempfile.mkdtemp()
        Storage.create(self.repodir, False)
        self.workspace = Storage(self.repodir)
        
    def tearDown(self):
        shutil.rmtree(self.repodir)

    def test_changectx(self):
        # do we need this test?
        ctx = self.workspace._changectx('tip')  # as 'default' not exist yet
        self.assertNotEqual(ctx, None, msg='failed to get context')
        self.assertEqual(ctx.branch(), 'default', msg='unexpected context')

    def test_manifest_empty(self):
        # empty manifest
        result = [i for i in self.workspace.manifest('tip')]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['path'], '/')


class SandboxTestCase(unittest.TestCase):

    def setUp(self):
        self.repodir = tempfile.mkdtemp()
        Sandbox.create(self.repodir, False)
        self.sandbox = Sandbox(self.repodir, ctx='tip')
        self.path = dirname(__file__)
        self.filelist = ['file1', 'file2', 'file3',]
        self.files = [open(join(self.path, i)).read() for i in self.filelist]
        self.msg = 'added some files'
        self.user = 'Tester <test@example.com>'
        
    def tearDown(self):
        shutil.rmtree(self.repodir)

    def test_add_file_content_fail(self):
        # tests for exceptions raised by addition of file content.
        # this resolves to full path for failure
        # XXX these tests only works on system with POSIX path!
        self.assertRaises(ValueError, self.sandbox.add_file_content, 
                          '/tmp/nothere', '')
        self.assertRaises(ValueError, self.sandbox.add_file_content, 
                          '../invalidpath', '')
        self.assertRaises(ValueError, self.sandbox.add_file_content, 
                          '/a/b/../../../invalidpath', '')

    def test_add_file_content_success(self):
        # testing adding of file.
        def add(fn, oc):
            self.sandbox.add_file_content(fn, self.repodir)
            self.sandbox.add_file_content(fn, oc)
            fc = open(os.path.join(self.repodir, fn)).read()
            self.assertEqual(oc, fc, 'file content mismatch')

        add('file1', '1')
        add('d/file1', '')
        add('a/b/c/d/e/file1', 'this is totally nested')

        # this is valid for now because 'dir/' gets normalized to 'dir'
        self.sandbox.add_file_content('dir/', 'dirpath')
        fc = open(os.path.join(self.repodir, 'dir')).read()
        self.assertEqual('dirpath', fc, 'file content mismatch')

    def test_commit_fail(self):
        # commit failing due to missing required values
        self.assertRaises(ValueError, self.sandbox.commit, '', '')
        self.assertRaises(ValueError, self.sandbox.commit, 'm', '')
        self.assertRaises(ValueError, self.sandbox.commit, '', 'm')

    def test_file_modification(self):
        # testing file adding features

        self.sandbox.add_file_content('file1', self.files[0])
        self.sandbox.add_file_content('file2', self.files[1])
        # XXX - accessing private attributes for verification
        status = statdict(self.sandbox._repo.status())
        self.assertEqual(status['added'], ['file1', 'file2',])
        self.sandbox.commit(self.msg, self.user)
        # XXX - accessing private attributes for verification
        status = statdict(self.sandbox._repo.status(
                list_ignored=True, list_clean=True))
        self.assertEqual(status['clean'], ['file1', 'file2',])

    def test_mkdir(self):
        self.assertRaises(ValueError, self.sandbox.mkdir, '../1')
        self.assertRaises(ValueError, self.sandbox.mkdir, '/tmp/fail')
        self.assert_(self.sandbox.mkdir('1'))
        self.assert_(self.sandbox.mkdir('1/2'))
        self.assert_(self.sandbox.mkdir('3/2/1'))
        self.assert_(self.sandbox.mkdir('3/2/1'))

    def test_status(self):
        self.sandbox.add_file_content('file1', self.files[0])
        self.sandbox.add_file_content('file2', self.files[1])
        self.sandbox.commit(self.msg, self.user)
        self.sandbox.add_file_content('file2', self.files[2])
        self.sandbox.add_file_content('file3', self.files[2])
        stat = [i for i in self.sandbox.status()]
        fent = [i for i in stat[0]['fentries']()]
        # XXX could use more validation here based on below
        # print '%s\n%s\n' % (stat, fent)
        self.assertEqual(len(fent), 3, 'number of file entries != 3')

    def test_rename_file_failure(self):
        # invalid type
        self.assertRaises(TypeError,
                self.sandbox.rename, None, '../move1')
        self.assertRaises(TypeError,
                self.sandbox.rename, '../file1', None)
        self.assertRaises(TypeError,
                self.sandbox.rename, '../file1', ['../move1'])
        # invalid source (type is ignored, but 'True' does not exist)
        self.assertRaises(ValueError,
                self.sandbox.rename, [True], 'move1')
        # destination out
        self.assertRaises(ValueError,
                self.sandbox.rename, '../file1', '../move1')
        # source does not exist
        self.assertRaises(ValueError,
                self.sandbox.rename, '../file1', 'move1')
        self.assertRaises(ValueError,
                self.sandbox.rename, ['../file1', 'file'], 'move1')
        # can't overwrite file
        self.sandbox.add_file_content('file1', self.files[0])
        self.sandbox.add_file_content('move1', self.files[0])
        self.assertRaises(ValueError,
                self.sandbox.rename, ['file1'], 'move1')
        self.sandbox.add_file_content('file2', self.files[0])
        self.assertRaises(ValueError,
                self.sandbox.rename, ['file1', 'file2'], 'move1')
        self.assertRaises(ValueError,
                self.sandbox.rename, ['file1', 'file2'], 'move1/move2')
        # no valid source
        self.assertRaises(ValueError,
                self.sandbox.rename, ['/file1', '/file2'], 'move2')

    def test_rename_file_success(self):
        self.sandbox.add_file_content('file1', self.files[0])
        errs, copied = self.sandbox.rename('file1', 'move1')
        # private _repo
        status = statdict(self.sandbox._repo.status())
        self.assertEqual(errs, 0)
        # copied results are lists of tuples, first item is basename
        self.assertEqual(copied[0][0], 'file1')
        self.assertEqual(status['added'], ['move1',])
        self.sandbox.commit(self.msg, self.user)

        errs, copied = self.sandbox.rename('move1', 'move2')
        # private _repo
        status = statdict(self.sandbox._repo.status())
        self.assertEqual(status['removed'], ['move1',])
        self.assertEqual(status['added'], ['move2',])

        t = join('dir', 'move3')
        errs, copied = self.sandbox.rename('move2', t)
        # private _repo
        status = statdict(self.sandbox._repo.status())
        self.assertEqual(status['added'], [t,])

        self.sandbox.add_file_content(self.filelist[0], self.files[0])
        self.sandbox.add_file_content(self.filelist[1], self.files[1])
        self.sandbox.add_file_content(self.filelist[2], self.files[2])
        self.sandbox.commit(self.msg, self.user)

        nd = join('some', 'nested', 'dir')
        errs, copied = self.sandbox.rename(self.filelist, nd)
        # private _repo
        status = statdict(self.sandbox._repo.status())
        self.assertEqual(status['added'], [join(nd, i) for i in self.filelist])
        self.assertEqual(status['removed'], self.filelist)

    def test_rename_file_other(self):
        self.sandbox.add_file_content('file1', self.files[0])
        self.sandbox.add_file_content('file2', self.files[0])
        self.sandbox.add_file_content('file3', self.files[0])
        self.sandbox.commit(self.msg, self.user)
        errs, copied = self.sandbox.rename(['file1', 'file2', 'file3'], 'move1')
        self.assertEqual(errs, 0)
        errs, copied = self.sandbox.rename(
            ['move1/file1', 'move1/file2', 'move2/file3'],  # move2/file3
            '',  # empty = root
        )
        self.assertEqual(errs, 1)

    def test_delete_file(self):
        pass


def statdict(st):
    # build a stat dictionary
    changetypes = (
        'modified', 'added', 'removed', 'deleted', 'unknown', 
        'ignored', 'clean',
    )
    return dict(zip(changetypes, st))


if __name__ == '__main__':
    unittest.main()
