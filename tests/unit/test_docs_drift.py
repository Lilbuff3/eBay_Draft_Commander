"""The context files (CLAUDE.md, AGENTS.md) must not name things that don't exist.

Phantom documentation is worse than missing documentation: an agent told that
`core/models.py` holds an `InternalListing` dataclass will go looking for it,
not find it, and guess. Both of those were documented for months. So was an
`OrphanedMedia` model and an `orphaned_media` table that exist nowhere in the
repo — and a reviewer re-typed `OrphanedMedia` into CLAUDE.md while correcting
a *different* stale line in the same file. Reading doesn't catch this. `git
ls-files` does.

The rule is deliberately asymmetric:

    documented-but-absent  -> failure (the doc is lying)
    present-but-undocumented -> fine (the table is a curated highlight list)

Enforcing the second direction would mean listing all ~80 test files in
tests/unit/AGENTS.md, which rots by next week and gets the test deleted. The
one exception is DB tables: there are four, and a table nobody documents is a
table nobody knows to query.
"""
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CLAUDE_MD = REPO / 'CLAUDE.md'
DATABASE_PY = REPO / 'backend' / 'app' / 'core' / 'database.py'

# Runtime artifacts CLAUDE.md names on purpose — created by the app, never tracked.
UNTRACKED_BY_DESIGN = {
    'data/listing_results.jsonl',
}

# `path.ext` in backticks. .md is excluded: CONTEXT.md and docs/adr/ are
# documented as created lazily, so absence is the documented state.
CODE_PATH = re.compile(r'`([A-Za-z0-9_./-]+\.(?:py|ts|tsx|html|json|jsonl))`')

# A filename opening an indented line of CLAUDE.md's ## Architecture tree.
# Tree entries are NOT backticked (they live in a code fence), so CODE_PATH
# misses them entirely — and the tree is exactly where `core/models.py` sat
# rotting. Matched by basename: reconstructing full paths from indentation
# breaks the first time someone reflows the tree.
TREE_ENTRY = re.compile(r'^\s+([A-Za-z0-9_.-]+\.(?:py|ts|tsx|html))\s{2,}\S', re.M)

# A "| `name.ext` |" row opening an AGENTS.md Key Files table. Rows whose
# description opens with "(generated" document a runtime artifact on purpose
# (e.g. tests/fixtures/_test_listings.json) — absence is the normal state.
TABLE_ROW = re.compile(r'^\| `([A-Za-z0-9_./-]+\.[a-z0-9]+)` \| (?!\(generated)', re.M)


def _tracked_files():
    """Tracked files plus not-yet-added ones, minus anything gitignored.

    --others keeps a brand-new file from failing the run that introduces it;
    --exclude-standard still drops node_modules, build output and data/.
    """
    try:
        out = subprocess.check_output(
            ['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
            text=True, cwd=REPO)
    except (OSError, subprocess.CalledProcessError):  # pragma: no cover
        pytest.skip('git not available')
    return out.splitlines()


def _agents_md_files():
    return [p for p in REPO.rglob('AGENTS.md')
            if 'node_modules' not in p.parts and '__pycache__' not in p.parts]


class TestClaudeMdPaths:
    def test_every_path_it_names_exists(self):
        """A file path in CLAUDE.md must resolve. core/models.py did not, for months."""
        tracked = _tracked_files()
        named = sorted(set(CODE_PATH.findall(CLAUDE_MD.read_text(encoding='utf-8'))))
        assert named, 'no paths found — did the regex or the file change shape?'

        missing = [p for p in named
                   if p not in UNTRACKED_BY_DESIGN
                   and not any(t == p or t.endswith('/' + p) for t in tracked)]
        assert not missing, (
            'CLAUDE.md names files that are not in the repo: ' + ', '.join(missing))

    def test_architecture_tree_names_real_files(self):
        """The tree is the map agents read first — and where core/models.py rotted."""
        tracked = _tracked_files()
        arch = CLAUDE_MD.read_text(encoding='utf-8').split('## Architecture', 1)[-1]
        arch = arch.split('\n## ', 1)[0]
        names = sorted(set(TREE_ENTRY.findall(arch)))
        assert len(names) > 40, f'only matched {len(names)} tree entries — did the tree change shape?'

        basenames = {t.rsplit('/', 1)[-1] for t in tracked}
        missing = [n for n in names if n not in basenames]
        assert not missing, (
            'architecture tree names files that do not exist: ' + ', '.join(missing))


class TestClaudeMdDatabase:
    """CLAUDE.md's Database section vs the actual SQLAlchemy models."""

    def setup_method(self):
        self.doc = CLAUDE_MD.read_text(encoding='utf-8')
        self.src = DATABASE_PY.read_text(encoding='utf-8')

    def test_named_models_are_defined(self):
        defined = set(re.findall(r'^class (\w+)', self.src, re.M))
        # *Model / *Token / *Media covers every naming shape used so far, and
        # *Media specifically re-catches OrphanedMedia if it creeps back. The
        # leading [A-Z] keeps browser APIs (getUserMedia) out of it.
        named = set(re.findall(r'\b([A-Z]\w*(?:Model|Token|Media))\b', self.doc))
        phantom = sorted(named - defined)
        assert not phantom, (
            'CLAUDE.md names models that database.py does not define: ' + ', '.join(phantom))

    def test_tables_match_both_ways(self):
        real = set(re.findall(r"__tablename__ = '(\w+)'", self.src))
        documented = set(re.findall(r'\*\*`(\w+)`\*\* table', self.doc))
        assert not documented - real, (
            'documented but absent: ' + ', '.join(sorted(documented - real)))
        assert not real - documented, (
            'real tables missing from CLAUDE.md: ' + ', '.join(sorted(real - documented)))


class TestAgentsMdTables:
    def test_no_table_row_names_a_missing_file(self):
        """Each AGENTS.md Key Files row must point at a file that is really there."""
        agents = _agents_md_files()
        assert agents, 'no AGENTS.md found — tree moved?'

        problems = []
        for md in agents:
            for name in TABLE_ROW.findall(md.read_text(encoding='utf-8', errors='replace')):
                if not (md.parent / name).exists():
                    problems.append(f'{md.relative_to(REPO).as_posix()} -> {name}')
        assert not problems, 'AGENTS.md rows naming missing files:\n  ' + '\n  '.join(problems)
