import argparse
import csv
import json
import os
import re
from pathlib import Path

from .engine import evaluate, formatted_value, read_table, repo_path
from .menu import Back, interactive, terminal_text
from .project import (CONFIG, apply_changes, build_path, choose_makefile, describe_changes,
                      make_command, manuscript_input, plan_changes)

ALIASES = {'lognormal_grw':'GRW', 'empirical_complete':'DBLP', 'ar1_s':'AROne',
           'ar6_6':'ARSix', 'arw4':'ARWFour', 'hurdle_ar1_s_p':'HurdleAROne',
           'se_hurdle_s':'SEHurdle', 'last_four':'FourYear', 'career_total':'Career',
           'mean_total':'MeanTotal', 'gini_total':'Gini', 'zero_fraction':'ZeroFraction'}
IDENTIFIERS = re.compile(r'^(source|model|window|cohort|dataset|scenario|group|metric|statistic|year|age|lag|reference)$', re.I)
MODELS = re.compile(r'^(source|model|method|scenario)$', re.I)
QQ = re.compile(r'^(?:(?:lognormal|qq)[_ -]*)*r[_ -]*(?:2|squared)$', re.I)


def title_case(value):
    if value in ALIASES:
        return ALIASES[value]
    if QQ.fullmatch(value):
        return 'QQRtwo'
    digits = ['Zero','One','Two','Three','Four','Five','Six','Seven','Eight','Nine']
    return ''.join(digits[int(part)] if part.isdigit() else part[0].upper()+part[1:]
                   for part in re.findall(r'[A-Za-z]+|[0-9]', value))


def suggest_name(where, column):
    order = sorted(where, key=lambda key: (not MODELS.fullmatch(key), key.casefold()))
    parts = [title_case(where[key]) for key in order]
    return ''.join(dict.fromkeys([*parts, title_case(column)])) or 'ReportValue'


def discover(root, extension, excluded=None):
    files = []
    for directory, folders, names in os.walk(root):
        path = Path(directory)
        folders[:] = sorted(folder for folder in folders
                            if not folder.startswith('.') and folder not in
                            {'venv','env','build','node_modules','__pycache__','site-packages'}
                            and path/folder != excluded)
        for name in names:
            candidate = path/name
            if name.lower().endswith(extension) and candidate.is_file() and candidate.resolve().is_relative_to(root):
                files.append(candidate.relative_to(root).as_posix())
    if extension == '.csv':
        return sorted(files, key=lambda name: ('output' not in Path(name).parts, name.casefold()))
    return sorted(files, key=lambda name: (Path(name).name != 'main.tex', name.casefold()))


def configure(ui, root, task_override):
    default = 'g_report'
    roots = [root/'dblp_models', root]
    for parent in roots:
        if not parent.is_dir():
            continue
        letters = [p.name[0] for p in parent.iterdir() if p.is_dir() and re.match('^[a-z]_',p.name)]
        if letters:
            letter = chr(ord(max(letters)) + 1)
            default = (parent.relative_to(root)/f'{letter}_report').as_posix() if letter <= 'z' else ''
            break
    task = task_override or ui.ask('Reporting task folder',
                                    'Use the next PDP letter or enter a path such as dblp_models/g_report.', default)
    task = build_path(root, task).relative_to(root).as_posix()
    if not re.fullmatch(r'[a-z]_[A-Za-z0-9_-]+', Path(task).name):
        raise ValueError('Use a task name like g_report or dblp_models/g_report')
    for item in ('src/report.ipynb','output/results.tex','output/macro_manifest.csv'):
        if (root/task/item).exists():
            raise ValueError(f'{task}/{item} already exists. Pick an unused task folder with --task.')
    candidates = discover(root, '.tex', root/task)
    choice = ui.choose('Manuscript', 'Choose the main TeX file for make paper. You can use report only.',
                       ['Enter a path', 'Report only', *candidates])
    manuscript, insert = '', False
    if choice != 1:
        name = candidates[choice-2] if choice >= 2 else ui.ask('Main TeX file', 'Enter a path from the repo root.')
        path = build_path(root, name)
        if not path.is_file() or path.suffix.lower() != '.tex':
            raise ValueError('Choose an existing main .tex file')
        manuscript = path.relative_to(root).as_posix()
        insert = ui.choose('Load generated macros',
                           'Insert an input line before the document begins, or add it yourself.',
                           ['Insert the input line', 'Keep the manuscript edit manual']) == 0
    return {'version':1,'task':task,'makefile':choose_makefile(root),'manuscript':manuscript,
            'insert_input':insert,'macros':[]}


def choose_source(ui, root, task, previous):
    candidates = discover(root,'.csv',root/task)
    labels = ['Enter a CSV path', *candidates]
    if previous:
        labels.insert(0, f'Keep {previous}')
    selected = ui.choose('Results CSV', 'Task output files appear first. Type part of a path to search.',labels)
    if previous and selected == 0:
        return previous
    label = labels[selected]
    value = ui.ask('CSV path', 'Enter a path from the repo root.',previous) if label == 'Enter a CSV path' else label
    source = repo_path(root,value)
    if source.suffix.lower() != '.csv' or not source.is_file():
        raise ValueError('Choose an existing CSV file')
    return source.relative_to(root).as_posix()


def choose_row(ui, columns, rows, current):
    where = {key:value for key,value in current.items() if key in columns}
    while True:
        matches = [row for row in rows if all(row[key] == value for key,value in where.items())]
        fields = sorted((key for key in columns if key not in where),
                        key=lambda key: (not IDENTIFIERS.fullmatch(key), columns.index(key)))
        labels = (['Use this row'] if len(matches) == 1 else []) + ['Clear filters']
        options = labels + [f'Filter by {field}' for field in fields]
        if matches:
            sample = ' | '.join(f'{key}={matches[0][key]}' for key in columns[:5])
            options.append('Sample: ' + sample)
        detail = f'{len(matches):,} matching rows. Add filters until exactly one remains.'
        if where:
            detail = f'{len(matches):,} matched  •  ' + ', '.join(f'{key}={value}' for key,value in where.items())
        selected = ui.choose('Select one row', detail,options)
        if options[selected] == 'Use this row':
            return where, matches[0]
        if options[selected] == 'Clear filters':
            where.clear()
        elif selected < len(labels)+len(fields):
            field = fields[selected-len(labels)]
            values = sorted({row[field] for row in matches})
            if values:
                index = ui.choose(f'Values for {field}', 'The saved rule uses an exact match.',
                                  [value or '(empty)' for value in values])
                where[field] = values[index]


def edit_macro(ui, root, config, previous=None):
    old = previous or {}
    source = choose_source(ui,root,config['task'],old.get('source',''))
    columns, rows = read_table(repo_path(root,source))
    if not rows:
        raise ValueError('This CSV has no data rows')
    where, row = choose_row(ui,columns,rows,old.get('where',{}) if source == old.get('source') else {})
    numeric = []
    for column in columns:
        try:
            formatted_value(row[column],3,False)
            numeric.append(column)
        except ValueError:
            pass
    if not numeric:
        raise ValueError('The selected row has no finite numeric values')
    numeric.sort(key=lambda col: (col != old.get('column'), not QQ.fullmatch(col),
                                  bool(IDENTIFIERS.fullmatch(col))))
    index = ui.choose('Statistic column', 'Select the number to insert in LaTeX.',
                      [f'{column}   {row[column]}' for column in numeric])
    column = numeric[index]
    suggested = old.get('name') or suggest_name(where,column)
    name = pick_name(ui,config,suggested,old.get('name'))
    decimal_text = ui.ask('Decimal places', 'Use 0 for whole numbers, or choose up to 15.',
                           str(old.get('decimals',3)))
    if not re.fullmatch(r'[0-9]{1,2}', decimal_text) or int(decimal_text) > 15:
        raise ValueError('Enter a whole number from 0 through 15')
    formats = [False,True] if not old.get('percent') else [True,False]
    labels = {False:'Keep numeric value',True:'Convert fraction to percent (×100)'}
    percent = formats[ui.choose('Number format', r'Percent macros supply the number. Write \% in LaTeX.',
                                [labels[format_] for format_ in formats])]
    macro = {'name':name,'source':source,'where':where,'column':column,
             'decimals':int(decimal_text),'percent':percent}
    _, value = evaluate(macro,columns,rows)
    if not ui.review('Preview macro', source, [f'Use in LaTeX: \\{name}  →  {value}',
                     f'{column} where {where or "the CSV contains one row"}'], 'Keep this macro'):
        raise Back
    return macro


def pick_name(ui,config,suggestion,previous=None):
    used = {macro['name'] for macro in config['macros']} - {previous}
    name = ui.ask('LaTeX command name', 'Use letters only. The backslash is optional.',suggestion).lstrip('\\')
    if not re.fullmatch('[A-Za-z]+',name) or name in used:
        raise ValueError('Use a unique name made up of letters A–Z or a–z')
    return name


def related_macros(ui, root, config, macro):
    field = next((key for key in macro['where'] if MODELS.fullmatch(key)),None)
    if field is None:
        return
    columns, rows = read_table(repo_path(root,macro['source']))
    proposed = []
    used = {item['name'] for item in config['macros']}
    selected = {key:value for key,value in macro['where'].items() if key != field}
    values = {row[field] for row in rows if all(row[key] == value for key,value in selected.items())}
    for value in sorted(values-{macro['where'][field]}):
        where = {**macro['where'],field:value}
        name = suggest_name(where,macro['column'])
        if name in used:
            continue
        other = {**macro,'name':name,'where':where}
        try:
            _, preview = evaluate(other,columns,rows)
        except ValueError:
            continue
        used.add(name)
        proposed.append((other,preview))
    while proposed:
        chosen = ui.choose('Same statistic for other models',
                           'Select a suggested command to add it. Other filters stay the same.',
                           ['Done', *[f'\\{item["name"]} → {value}   ({item["where"][field]})'
                                      for item,value in proposed]])
        if chosen == 0:
            return
        item,_ = proposed.pop(chosen-1)
        config['macros'].append(item)


def macro_menu(ui,root,config):
    options = ['Add macro','Rename macro','Edit source or formatting','Remove macro','Preview values',
               'Save changes','Help','Exit']
    while True:
        action = None
        try:
            action = ui.choose(f'Macro setup  •  {root.name}',
                               f'{len(config["macros"])} mapped  •  Save changes to update the repository.',
                               options)
            if action == 0:
                macro = edit_macro(ui,root,config)
                config['macros'].append(macro)
                related_macros(ui,root,config,macro)
            elif action in (1,2,3):
                if not config['macros']:
                    ui.message('No macros yet','Start with Add macro.')
                    continue
                index = ui.choose('Choose a macro','Type its name or source to filter.',
                                  [f'\\{m["name"]}   {m["source"]}   {m["column"]}' for m in config['macros']])
                macro = config['macros'][index]
                if action == 1:
                    macro['name'] = pick_name(ui,config,macro['name'],macro['name'])
                elif action == 2:
                    config['macros'][index] = edit_macro(ui,root,config,macro)
                elif ui.review('Remove macro','Update the manuscript if it uses this command.',
                               ['\\'+macro['name']], 'Remove this macro'):
                    del config['macros'][index]
            elif action == 4:
                labels, tables = [], {}
                for macro in config['macros']:
                    try:
                        source = macro['source']
                        if source not in tables:
                            tables[source] = read_table(repo_path(root,source))
                        _, value = evaluate(macro,*tables[source])
                    except (ValueError,OSError,csv.Error) as error:
                        value = f'Cannot resolve: {error}'
                    labels.append(f'\\{macro["name"]} → {value}')
                ui.choose('Preview values','Read from the current CSVs. Esc returns to the menu.',
                          ['Back',*labels])
            elif action == 5:
                return True
            elif action == 7:
                if ui.choose('Exit wizard','Edits since the last save will be discarded.',
                             ['Return to menu','Exit without saving']) == 1:
                    return False
            else:
                ui.choose('Help','Each macro maps one CSV cell to a LaTeX command.',
                          ['Back','Add: select a CSV, add exact row filters, choose a numeric column.',
                           'Edit: change a source, row, column, or display precision.',
                           'Rename: update any uses of the old command in your manuscript.',
                           'Save: review the proposed files before applying the changes.',
                           f'After saving: run {make_command(config,"report")} from the repo root.'])
        except Back:
            if action is None:
                try:
                    if ui.choose('Exit wizard','Edits since the last save will be discarded.',
                                 ['Return to menu','Exit without saving']) == 1:
                        return False
                except Back:
                    pass
        except (ValueError,OSError,csv.Error) as error:
            try:
                ui.message('Could not complete that action',str(error))
            except Back:
                pass


def launch(ui,root,task):
    path = repo_path(root, CONFIG)
    baseline = path.read_bytes() if path.exists() else None
    config = json.loads(baseline) if baseline is not None else configure(ui,root,task)
    if config.get('version') != 1:
        raise ValueError('Unsupported report wizard configuration version')
    if baseline is not None and task and Path(task) != Path(config['task']):
        raise ValueError('This repository already has a configured report task')
    while macro_menu(ui,root,config):
        try:
            if (path.read_bytes() if path.exists() else None) != baseline:
                raise ValueError('The configuration changed on disk. Reopen the wizard before saving.')
            changes = plan_changes(root,config,new=baseline is None)
            if not changes:
                return 'Everything is up to date.'
            lines = describe_changes(root,changes)
            if ui.review('Review repository changes','Scroll to inspect the paths and edits before applying.',lines):
                apply_changes(changes)
                report = make_command(config,'report')
                commands = f'\n  {report}  # refresh macros'
                if config['manuscript']:
                    commands += f'\n  {make_command(config,"paper")}   # refresh and compile'
                    if not config['insert_input']:
                        commands += '\nAdd to your LaTeX preamble: ' + manuscript_input(root,config)
                return f'Saved {len(config["macros"])} macros. From this repository root:{commands}'
        except Back:
            pass
        except (ValueError,OSError,csv.Error) as error:
            try:
                ui.message('Changes could not be saved',str(error))
            except Back:
                pass
    return 'Exited without saving.'


def main():
    parser = argparse.ArgumentParser(description='Set up and manage CSV-backed LaTeX macros from a repository root.')
    parser.add_argument('--plain',action='store_true',help='use numbered prompts instead of the fullscreen interface')
    parser.add_argument('--task',help='initial PDP task path, e.g. dblp_models/g_report')
    args = parser.parse_args()
    root = Path.cwd().resolve()
    try:
        print(interactive(lambda ui: launch(ui,root,args.task),args.plain))
    except (KeyboardInterrupt,EOFError,Back):
        print('Exited without saving.')
    except (ValueError,OSError,csv.Error) as error:
        parser.exit(1,f'report-wizard: {terminal_text(error)}\n')
