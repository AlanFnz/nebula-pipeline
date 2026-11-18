#!/usr/bin/env python3
"""Check lowercase conventional commit subjects without changing history."""
import argparse
from pathlib import Path
import re
import subprocess
import sys

TYPES = ('feat', 'fix', 'refactor', 'perf', 'docs', 'test', 'build', 'ci', 'chore', 'revert', 'merge')
SUBJECT = re.compile(r'(' + '|'.join(TYPES) + r')(\([a-z0-9][a-z0-9_-]*\))?!?: \S.*')


def validate(message):
    lines = message.splitlines()
    subject = lines[0] if lines else ''
    if not SUBJECT.fullmatch(subject):
        return 'use type(scope): description, or type: description; scope is optional'
    if subject != subject.lower():
        return 'the complete subject must be lowercase'
    if subject != subject.rstrip():
        return 'remove trailing whitespace from the subject'
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--message-file', type=Path)
    source.add_argument('--range', dest='revision_range', help='only check commits in this git range')
    args = parser.parse_args()
    if args.message_file:
        messages = [(str(args.message_file), args.message_file.read_text())]
    else:
        commits = subprocess.check_output(['git', 'rev-list', args.revision_range, '--'], text=True).splitlines()
        messages = [(commit[:10], subprocess.check_output(['git', 'show', '-s', '--format=%B', commit], text=True)) for commit in commits]
    failed = False
    for identifier, message in messages:
        error = validate(message)
        if error:
            print(f'{identifier}: {error}', file=sys.stderr)
            print('example: fix(preview): preserve the prepared loop', file=sys.stderr)
            failed = True
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
