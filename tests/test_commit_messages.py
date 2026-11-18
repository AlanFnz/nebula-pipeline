"""The same commit policy runs locally and on new pull request/main commits."""
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_commit_message import validate


@pytest.mark.parametrize('message', [
    'feat: add a project gallery',
    'fix(preview): preserve the prepared loop',
    'refactor!: organize modules',
    'build(macos)!: change bundle paths',
    'merge: integrate the preview fixes',
    'docs: clarify saving\n\nKeep QFileOpenEvent and README identifiers in the body.',
])
def test_conventional_lowercase_subjects(message):
    assert validate(message) is None


@pytest.mark.parametrize('message', [
    '', 'Fix preview', 'fix: Fix preview', 'Fix: preview', 'fix(UI): preview',
    'feat:', 'feat: ', 'fix: trailing ', 'unknown: title', 'feat: upper JSON',
])
def test_nonconforming_subjects_are_rejected(message):
    assert validate(message)


def test_range_checks_only_new_history_and_returns_nonzero(tmp_path):
    root = Path(__file__).resolve().parents[1]
    def git(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args], text=True).strip()
    git('init', '-q')
    git('config', 'user.name', 'Test'); git('config', 'user.email', 'test@example.invalid')
    git('-c', 'core.hooksPath=/dev/null', 'commit', '--allow-empty', '-qm', 'Historical Title')
    base = git('rev-parse', 'HEAD')
    git('-c', 'core.hooksPath=/dev/null', 'commit', '--allow-empty', '-qm', 'chore: configure checks')
    checker = [sys.executable, str(root/'scripts/check_commit_message.py'), '--range', base+'..HEAD']
    assert subprocess.run(checker, cwd=tmp_path, capture_output=True).returncode == 0
    git('-c', 'core.hooksPath=/dev/null', 'commit', '--allow-empty', '-qm', 'Wrong title')
    assert subprocess.run(checker, cwd=tmp_path, capture_output=True).returncode == 1


def test_installed_hook_rejects_invalid_subject(tmp_path):
    root = Path(__file__).resolve().parents[1]
    message = tmp_path/'message'
    message.write_text('Fix something\n')
    result = subprocess.run([str(root/'.githooks/commit-msg'), str(message)], cwd=root, capture_output=True)
    assert result.returncode == 1
    message.write_text('fix: preserve edits\n')
    assert subprocess.run([str(root/'.githooks/commit-msg'), str(message)], cwd=root, capture_output=True).returncode == 0
