"""Validate release inputs shared by Home Assistant and GitHub Actions."""
import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    for path in [*ROOT.rglob('*.yaml'), *ROOT.rglob('*.yml')]:
        yaml.safe_load(path.read_text(encoding='utf-8'))
    config = yaml.safe_load((ROOT / 'codex/config.yaml').read_text())
    build = yaml.safe_load((ROOT / 'codex/build.yaml').read_text())
    repository = yaml.safe_load((ROOT / 'repository.yaml').read_text())
    url = 'https://github.com/lbouriez/ha.addon.codex'
    assert repository['url'] == config['url'] == build['labels']['org.opencontainers.image.source'] == url
    assert config['image'] == 'ghcr.io/lbouriez/ha.addon.codex'
    assert set(config['arch']) == set(build['build_from']) == {'amd64', 'aarch64'}
    assert set(config['options']) == set(config['schema'])
    for path in (ROOT / 'codex/translations').glob('*.yaml'):
        translation = yaml.safe_load(path.read_text(encoding='utf-8'))
        assert set(translation['configuration']) == set(config['options']), path
    version = config['version']
    assert re.fullmatch(r'\d+\.\d+\.\d+', version), version
    assert f'## [{version}]' in (ROOT / 'codex/CHANGELOG.md').read_text()
    assert re.search(r'^ARG CODEX_VERSION=\d+\.\d+\.\d+$', (ROOT / 'codex/Dockerfile').read_text(), re.M)
    for path in (ROOT / 'codex/rootfs').rglob('*'):
        if path.is_file():
            assert b'\r\n' not in path.read_bytes(), f'Linux runtime file has CRLF: {path}'
    if output := os.environ.get('GITHUB_OUTPUT'):
        with open(output, 'a', encoding='utf-8') as handle:
            print(f'version={version}', file=handle)
    print(f'Validated add-on {version}, image {config["image"]}, architectures {config["arch"]}')


if __name__ == '__main__':
    main()
