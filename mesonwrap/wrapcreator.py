#!/usr/bin/env python

# Copyright 2015 The Meson development team

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import git
import hashlib
import os
import shutil
import tempfile
import zipfile

from mesonwrap import gitutils
from mesonwrap import upstream


_OUT_URL_BASE_DEFAULT = (
    'https://wrapdb.mesonbuild.com/v1/projects/%s/%s/%d/get_zip')


class WrapCreator:

    def __init__(self, name, repo_url, branch, out_dir='.',
                 out_url_base=_OUT_URL_BASE_DEFAULT):
        self.name = name
        self.repo_url = repo_url
        self.branch = branch
        self.out_dir = out_dir
        self.out_url_base = out_url_base

    def create(self):
        with tempfile.TemporaryDirectory() as workdir:
            return self.create_internal(workdir)

    @staticmethod
    def _get_revision(repo):
        return gitutils.get_revision(repo, repo.head.commit)

    @staticmethod
    def check_definition(definition):
        for i in ['directory', 'source_url', 'source_filename', 'source_hash']:
            if not getattr(definition, 'has_' + i):
                raise RuntimeError('Missing {!r} in upstream.wrap.'.format(i))

    def create_internal(self, workdir):
        repo = git.Repo.clone_from(self.repo_url, workdir, branch=self.branch)
        upstream_file = os.path.join(workdir, 'upstream.wrap')
        upstream_content = open(upstream_file).read()
        revision_id = self._get_revision(repo)
        self.upstream_file = os.path.join(workdir, 'upstream.wrap')
        self.definition = upstream.UpstreamWrap.from_file(self.upstream_file)
        self.check_definition(self.definition)
        shutil.rmtree(os.path.join(workdir, '.git'))
        os.unlink(os.path.join(workdir, 'readme.txt'))
        os.unlink(upstream_file)
        try:
            os.unlink(os.path.join(workdir, '.gitignore'))
        except OSError:
            pass
        base_name = (self.name + '-' +
                     self.branch + '-' +
                     str(revision_id) + '-wrap')
        zip_name = base_name + '.zip'
        wrap_name = base_name + '.wrap'
        zip_full = os.path.join(self.out_dir, zip_name)
        wrap_full = os.path.join(self.out_dir, wrap_name)
        with zipfile.ZipFile(zip_full, 'w',
                             compression=zipfile.ZIP_DEFLATED) as zip:
            for root, dirs, files in os.walk(workdir):
                for f in files:
                    abspath = os.path.join(root, f)
                    relpath = abspath[len(workdir) + 1:]
                    zip.write(abspath, os.path.join(self.definition.directory,
                                                    relpath))

        source_hash = hashlib.sha256(open(zip_full, 'rb').read()).hexdigest()
        with open(wrap_full, 'w') as wrapfile:
            url = self.out_url_base % (self.name, self.branch, revision_id)
            wrapfile.write(upstream_content)
            wrapfile.write('\n')
            wrapfile.write('patch_url = %s\n' % url)
            wrapfile.write('patch_filename = %s\n' % zip_name)
            wrapfile.write('patch_hash = %s\n' % source_hash)
        wrap_contents = open(wrap_full, 'r').read()
        zip_contents = open(zip_full, 'rb').read()
        return (wrap_contents, zip_contents, revision_id)


def main(prog, args):
    parser = argparse.ArgumentParser(prog)
    parser.add_argument('project_name')
    parser.add_argument('data_repo_url')
    parser.add_argument('branch')
    args = parser.parse_args(args)
    x = WrapCreator(args.project_name, args.data_repo_url, args.branch)
    x.create()
