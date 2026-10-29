"""Packaging regressions: never read the output archive as an input file."""
import contextlib
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from scripts.package_skill import package_skill


class PackageSkillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.skill = self.root / 'sample'
        self.skill.mkdir()
        (self.skill / 'SKILL.md').write_text('---\nname: sample\ndescription: Example\n---\n# Example\n')
        (self.skill / 'asset.txt').write_text('payload')

    def package(self, output):
        expected = (output or Path.cwd()).resolve() / 'sample.skill'
        original = zipfile.ZipFile.write
        def guarded_write(archive, filename, *args, **kwargs):
            # Stop before reading a live output, which could expand indefinitely.
            self.assertNotEqual(Path(filename).resolve(), expected)
            return original(archive, filename, *args, **kwargs)
        with patch.object(zipfile.ZipFile, 'write', guarded_write), contextlib.redirect_stdout(io.StringIO()):
            result = package_skill(self.skill, output)
        self.assertEqual(result, expected)
        with zipfile.ZipFile(result) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read('sample/asset.txt'), b'payload')
            return set(archive.namelist())

    def test_output_at_skill_root(self):
        self.assertEqual(self.package(self.skill), {'sample/SKILL.md', 'sample/asset.txt'})

    def test_nested_output_and_repeat(self):
        for _ in range(2):
            self.assertEqual(self.package(self.skill / 'dist'), {'sample/SKILL.md', 'sample/asset.txt'})

    def test_default_output_uses_skill_cwd(self):
        previous = Path.cwd()
        try:
            os.chdir(self.skill)
            names = self.package(None)
        finally:
            os.chdir(previous)
        self.assertEqual(names, {'sample/SKILL.md', 'sample/asset.txt'})

    def test_output_alias_is_not_included(self):
        output = self.skill / 'sample.skill'
        output.touch()
        (self.skill / 'alias.skill').symlink_to(output)
        self.assertEqual(self.package(self.skill), {'sample/SKILL.md', 'sample/asset.txt'})

    def test_external_output_keeps_other_archives_and_exclusions(self):
        (self.skill / 'reference.skill').write_text('asset')
        for folder in ['evals', 'node_modules', '__pycache__']:
            (self.skill / folder).mkdir()
            (self.skill / folder / 'skip.txt').write_text('skip')
        self.assertEqual(self.package(self.root / 'out'), {'sample/SKILL.md', 'sample/asset.txt', 'sample/reference.skill'})


if __name__ == '__main__':
    unittest.main()
