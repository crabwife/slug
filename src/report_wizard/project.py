import difflib
import json
import os
import re
import shlex
from pathlib import Path

from . import engine
from .engine import link_name, render_report, repo_path, write_atomic

CONFIG = '.report-wizard.json'
BEGIN = '# BEGIN REPORT WIZARD'
END = '# END REPORT WIZARD'
RUN_NOTEBOOK = ('import json; from pathlib import Path; '
                'scope = {"__name__": "__main__"}; '
                '[exec(compile("".join(cell["source"]), "report.ipynb", "exec"), scope) '
                'for cell in json.loads(Path("report.ipynb").read_text())["cells"]]')


def build_path(root, value):
    if not re.fullmatch(r'[\w .()/+\-]+', value, flags=re.ASCII):
        raise ValueError('Build paths can contain letters, numbers, spaces, and . _ / + ( ) -')
    return repo_path(root, value)


def notebook(config):
    depth = len(Path(config['task']).parts)
    script = Path(engine.__file__).read_text(encoding='utf-8')
    code_cells = script.split('# cell\n')[1:]
    code_cells.insert(1, f"""TASK = Path.cwd().parent
ROOT = TASK.parents[{depth - 1}]
OUTPUT = TASK / 'output'
CONFIG = json.loads((ROOT / '{CONFIG}').read_text(encoding='utf-8'))
""")
    code_cells.extend(["results, manifest = render_report(ROOT, CONFIG)",
                       """write_atomic(OUTPUT / 'macro_manifest.csv', manifest.encode('utf-8'))
write_atomic(OUTPUT / 'results.tex', results.encode('utf-8'))
"""])
    cells = [{'cell_type':'code', 'id':f'report-{i:02}', 'execution_count':None, 'metadata':{},
              'outputs':[], 'source':source.strip().splitlines(keepends=True)}
             for i, source in enumerate(code_cells)]
    return json.dumps({'cells':cells, 'metadata':{'kernelspec':{'display_name':'Python 3', 'language':'python',
                      'name':'python3'}}, 'nbformat':4, 'nbformat_minor':5}, indent=1) + '\n'


def make_rules(config):
    source = shlex.quote('./' + str(Path(config['task']) / 'src'))
    lines = [BEGIN, 'PYTHON ?= python3', '.PHONY: report', '', 'report:',
             f'\tcd {source} && $(PYTHON) -c {shlex.quote(RUN_NOTEBOOK)}']
    if config.get('manuscript'):
        manuscript = Path(config['manuscript'])
        directory = shlex.quote('./' + str(manuscript.parent))
        lines.extend(['', 'LATEXMK ?= latexmk', '.PHONY: paper', '', 'paper: report',
                      f'\tcd {directory} && $(LATEXMK) '
                      '-pdf -interaction=nonstopmode -halt-on-error -outdir=build '
                      + shlex.quote('./' + manuscript.name)])
    return '\n'.join([*lines, END, ''])


def choose_makefile(root):
    active = next((name for name in ('GNUmakefile', 'makefile', 'Makefile') if (root/name).exists()), 'Makefile')
    path = root/active
    if not path.exists():
        return active
    content = path.read_text(encoding='utf-8')
    existing_rules = re.search(r'(?m)^\s*(?:-?include|sinclude)\s|^[^#\n\t:]*\b(?:paper|report)\b[^#\n:]*:', content)
    return 'report-wizard.mk' if existing_rules or path.is_symlink() else active


def make_command(config, target):
    prefix = 'make -f report-wizard.mk' if config['makefile'] == 'report-wizard.mk' else 'make'
    return f'{prefix} {target}'


def manuscript_input(root, config):
    manuscript = build_path(root, config['manuscript'])
    source = root / config['task'] / 'output/results.tex'
    relative = Path(os.path.relpath(source, manuscript.parent)).as_posix()
    return r'\input{' + relative + '}'


def patch_manuscript(content, command):
    if command in [line.strip().split('%', 1)[0].rstrip() for line in content.splitlines()]:
        return content
    match = re.search(r'(?m)^[ \t]*\\begin\s*\{document\}', content)
    if not match:
        raise ValueError(r'Manuscript needs a line with \begin{document} for automatic insertion')
    return content[:match.start()] + command + '\n\n' + content[match.start():]


def snapshot(path):
    if path.is_symlink():
        return ('link', os.readlink(path))
    if path.exists():
        if not path.is_file():
            raise ValueError(f'{path}: expected a regular file')
        return ('file', path.read_bytes())
    return None


def plan_changes(root, config, *, new):
    task = config['task']
    task_path = build_path(root, task)
    if task_path.resolve() != task_path:
        raise ValueError('Choose a task directory with a direct path, without directory symlinks')
    if task_path == root or not re.fullmatch('[a-z]_[A-Za-z0-9_-]+', task_path.name):
        raise ValueError('Choose a task folder such as g_report or dblp_models/g_report')
    changes = {}

    def put(relative, data, *, managed=False):
        path = repo_path(root, relative)
        before = snapshot(path)
        if before == data:
            return
        if before and (managed and new or before[0] != data[0]):
            raise ValueError(f'{relative} already exists; choose an unused task folder or path')
        changes[path] = before, data

    def file(relative, content, *, managed=False):
        put(relative, ('file', content.encode('utf-8')), managed=managed)

    config_text = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
    results, manifest = render_report(root, config, use_links=False)
    for source in dict.fromkeys(macro['source'] for macro in config['macros']):
        relative = link_name(task, source)
        link = repo_path(root, relative)
        actual = repo_path(root, source)
        if actual.is_relative_to(task_path) or actual.resolve().is_relative_to(task_path):
            raise ValueError('Pick a CSV from an upstream task')
        target = os.path.relpath(actual, link.parent)
        if link.is_symlink() and os.readlink(link) != target:
            raise ValueError(f'{relative} already points to a different source')
        put(relative, ('link', target), managed=True)

    nb_path = f'{task}/src/report.ipynb'
    if new:
        file(nb_path, notebook(config), managed=True)
    elif not repo_path(root, nb_path).is_file():
        file(nb_path, notebook(config), managed=True)
    file(f'{task}/output/results.tex', results, managed=True)
    file(f'{task}/output/macro_manifest.csv', manifest, managed=True)
    if new:
        makefile = build_path(root, config['makefile'])
        previous = makefile.read_bytes().decode('utf-8') if makefile.exists() else ''
        if BEGIN in previous or (makefile.name == 'report-wizard.mk' and makefile.exists()):
            raise ValueError(f'{makefile.name} already exists with report setup')
        file(config['makefile'], (previous + ('\n' if previous.endswith('\n') else '\n\n') if previous else '') + make_rules(config))
        if config.get('insert_input'):
            path = build_path(root, config['manuscript'])
            file(config['manuscript'], patch_manuscript(path.read_text(encoding='utf-8'),
                                                       manuscript_input(root, config)))
    file(CONFIG, config_text, managed=True)
    return changes


def describe_changes(root, changes):
    lines = []
    for path, (before, after) in changes.items():
        relative = path.relative_to(root)
        if after[0] == 'link':
            lines.append(f'Link {relative} → {after[1]}')
        else:
            lines.append(f'{"Update" if before else "Create"} {relative}')
            if (path.suffix in ('.tex', '.mk') and path.name != 'results.tex') or path.name.lower().endswith('makefile'):
                old = before[1].decode('utf-8').splitlines() if before else []
                new = after[1].decode('utf-8').splitlines()
                lines.extend('   ' + line for line in difflib.unified_diff(old, new, n=0)
                             if line.startswith(('+', '-')) and not line.startswith(('+++', '---')))
    return lines


def apply_changes(changes):
    for path, (before, _) in changes.items():
        if snapshot(path) != before:
            raise ValueError(f'{path.name} changed while the preview was open. Review the changes again.')
    completed = []
    def write(path, entry):
        if entry is None:
            path.unlink(missing_ok=True)
        elif entry[0] == 'file':
            write_atomic(path, entry[1])
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(entry[1])
    try:
        for path, (before, after) in changes.items():
            write(path, after)
            completed.append((path, before))
    except (OSError, KeyboardInterrupt):
        for path, before in reversed(completed):
            write(path, before)
        raise
