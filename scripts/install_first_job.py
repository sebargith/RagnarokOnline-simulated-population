"""Stage the approved first-job NPC for the next map-server load, without reload."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'config/npc/first-job-changer.txt'
RATHENA = ROOT.parent / 'vendor/rathena'
RELATIVE = 'npc/custom/first-job-changer.txt'
ENTRY = ('npc: ' + RELATIVE).encode('ascii')


def install(root, source):
    target = root / RELATIVE
    conf = root / 'npc/scripts_custom.conf'
    content = source.read_bytes()
    original = conf.read_bytes()
    if any(line.strip() == b'npc: npc/custom/jobmaster.txt' for line in original.splitlines()):
        raise RuntimeError('Stock Job Master occupies the same location')
    active = [line.strip() for line in original.splitlines()
              if line.strip().startswith(b'npc:') and RELATIVE.encode() in line]
    if active and active != [ENTRY]:
        raise RuntimeError('Conflicting first-job configuration')
    normalize = lambda data: data.replace(b'\r\n', b'\n')
    if target.exists() and normalize(target.read_bytes()) != normalize(content):
        raise RuntimeError('Refusing to overwrite a different NPC script')
    if not target.exists():
        with target.open('xb') as handle:
            handle.write(content)
    if not active:
        newline = b'\r\n' if b'\r\n' in original else b'\n'
        with conf.open('ab') as handle:
            if original and not original.endswith((b'\n', b'\r')):
                handle.write(newline)
            handle.write(ENTRY + newline)


if __name__ == '__main__':
    install(RATHENA, SOURCE)
    print('NPC staged; running map-server was not reloaded.')
