"""Validate Conventional Commit subjects or feature branch names."""
import re
import subprocess
import sys

SUBJECT = r'(feat|fix|docs|test|ci|chore|refactor)(\([\w-]+\))?!?: .{3,72}'
BRANCH = r'(feature|fix|docs|ci)/[a-z0-9]+(?:-[a-z0-9]+)*'


def validate(subject):
    if not re.fullmatch(SUBJECT, subject):
        raise SystemExit('Use Conventional Commits, e.g. feat: add calculator')


if __name__ == '__main__':
    if sys.argv[1] == 'message':
        with open(sys.argv[2], encoding='utf-8') as message:
            validate(message.readline().strip())
    elif sys.argv[1] == 'branch':
        if not re.fullmatch(BRANCH, sys.argv[2]):
            raise SystemExit('Use feature|fix|docs|ci/<lowercase-description>')
    elif sys.argv[1] == 'title':
        validate(sys.argv[2])
    elif sys.argv[1] == 'range':
        subjects = subprocess.check_output(
            ['git', 'log', '--format=%s', '--no-merges', sys.argv[2]],
            text=True).splitlines()
        for subject in subjects:
            validate(subject)
