#!/usr/bin/env python3
"""Smoke the default-catalog Linux git stack installed by `nb install`.

Checks the installed git and curl match the pinned registry versions, their
dynamic libraries resolve, git can commit/grep/fsck/ls-remote and curl can
reach GitHub over HTTPS. Writes dist/linux-git-smoke-<arch>.json evidence.
"""
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BIN = Path('/opt/nanobrew/prefix/bin')


def run(args, cwd=None, env=None):
    print('+', ' '.join(map(str, args)), flush=True)
    return subprocess.check_output(list(map(str, args)), cwd=cwd, env=env, text=True, timeout=120)


def pinned(name):
    for record in json.loads((ROOT / 'registry/upstream.json').read_text())['records']:
        if record.get('token') == name:
            # Homebrew revisions appear as an underscore suffix on the version.
            return record['resolved']['version'].split('_')[0]
    raise ValueError('No registry record: ' + name)


def pretty_os():
    try:
        for line in Path('/etc/os-release').read_text().splitlines():
            if line.startswith('PRETTY_NAME='):
                return line.split('=', 1)[1].strip('"')
    except OSError:
        pass
    return platform.platform()


def check(binary, flag, version):
    output = run([BIN / binary, flag])
    match = re.search(r'(?<![0-9.])' + re.escape(version) + r'(?![0-9.])', output)
    if not match:
        raise ValueError(f'{binary} {flag} does not report {version}: {output!r}')
    libs = run(['ldd', BIN / binary])
    if 'not found' in libs:
        raise ValueError(f'{binary} has unresolved libraries:\n{libs}')
    return output.strip().splitlines()[0]


def main():
    arch = platform.machine()
    versions = {'git': pinned('git'), 'curl': pinned('curl')}
    checks = [check('git', '--version', versions['git']),
              check('curl', '--version', versions['curl'])]
    with tempfile.TemporaryDirectory(prefix='nb-linux-smoke-') as td:
        work = Path(td)
        git = BIN / 'git'
        env = {'PATH': str(BIN) + ':/usr/bin:/bin', 'HOME': td}
        run([git, 'init', '.'], cwd=work, env=env)
        (work / 'hello.txt').write_text('Linux package support\n')
        run([git, 'add', 'hello.txt'], cwd=work, env=env)
        run([git, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'smoke'], cwd=work, env=env)
        run([git, 'grep', '-P', 'Linux.*support'], cwd=work, env=env)
        run([git, 'fsck', '--full'], cwd=work, env=env)
    checks.append('git init/add/commit/grep -P/fsck --full')
    run([BIN / 'git', 'ls-remote', 'https://github.com/justrach/nanobrew.git', 'HEAD'])
    checks.append('git HTTPS ls-remote')
    run([BIN / 'curl', '--fail', '--max-time', '60', '-I', 'https://github.com'])
    checks.append('curl HTTPS')
    out = {'tested_os': pretty_os(), 'arch': arch, 'versions': versions,
           'checks': checks, 'monterey_bottles': False}
    dest = ROOT / 'dist' / f'linux-git-smoke-{arch}.json'
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
