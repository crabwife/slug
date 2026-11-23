# Report Wizard

Report Wizard connects numbers in your analysis CSVs to LaTeX commands. Install it once, then launch it from any project root. The wizard runs in your terminal and uses Python's standard library. The generated reporting task runs independently of the wizard.

## Install

Extract the download. From any directory, install the included wheel with Python 3.9 or newer. Use `pipx` if you have it.

```sh
pipx install /path/to/report-wizard/report_wizard-0.1.1-py3-none-any.whl
```

You can also install it with `python3 -m pip install /path/to/report-wizard/report_wizard-0.1.1-py3-none-any.whl` in an activated virtual environment. To try the interface before installing, set `PYTHONPATH=/path/to/report-wizard/src` and run `python3 -m report_wizard`.

## Set up a project

1. Open a terminal at your repository root and run `report-wizard`. The wizard suggests the next PDP task letter. You can specify a path with `report-wizard --task dblp_models/g_report`.
2. Choose your main `.tex` file and decide whether to have the wizard insert the preamble input. Choose **Report only** if you only need the macro exporter.
3. Choose **Add macro**. Select a results CSV, then add exact row filters until one row remains. For example, select `source = lognormal_grw` and `window = last_four`.
4. Pick the numeric column, then choose a LaTeX command name and precision. The wizard offers names based on the row and column, such as `GRWFourYearQQRtwo` for `qq_r2`. Use its suggestion or type your own. It previews the number and can suggest the same statistic for other models with the other row filters held fixed.
5. Choose **Save changes**. Scroll through the file paths and Makefile or manuscript edits, then choose **Apply changes**. Until you apply, selections are kept in memory.

Use ↑ and ↓ to move, Enter to select, and Esc to go back. Type into a menu to filter by name. Page Up and Page Down move faster in a long menu. Ctrl-U clears a search. Use `report-wizard --plain` for numbered prompts.

## Write and build

If the wizard inserted the input, you can use the generated command right away.

```tex
The GRW gives $R^2=\GRWFourYearQQRtwo$.
```

Use `\%` in the manuscript after a percentage macro. LaTeX command names consist of letters. The wizard checks for duplicates within its own configuration. Pick names that are also distinct from commands in your document and its packages.

From your repo root, use:

```sh
make report   # refresh the macros from the current CSVs
make paper    # refresh, then compile the manuscript
```

The paper target requires `latexmk` and PDFLaTeX. It writes the PDF to `build/` beside the main TeX file. If your project already owns a `report` or `paper` target or includes other Makefiles, the wizard writes `report-wizard.mk` and shows the equivalent `make -f report-wizard.mk report` and `make -f report-wizard.mk paper` commands.

After analysis produces new CSVs, run the report to refresh your numbers. Compiling on save uses the most recently generated commands. If you declined automatic manuscript insertion, the wizard gives you the input line to paste into the preamble. Relative input paths assume compilation from the main TeX file’s directory, as the generated paper target does.

## Manage an existing setup

Rerun `report-wizard` from the same root. Use **Rename macro** for the command name, **Edit source or formatting** after a CSV schema or selection changes, and **Preview values** to see how the current CSVs resolve. Replace uses of renamed or removed commands in your manuscript. Save after editing. Ambiguous rows, missing columns, and invalid numbers cause a report failure before it writes new results.

Commit the project configuration `.report-wizard.json`, its PDP task, and the Makefile and manuscript edits you want to share. The task contains relative links to selected upstream CSVs in `input/`, a code-only notebook in `src/`, and `results.tex` and `macro_manifest.csv` in `output/`. The manifest records each source file, column, row filters, and formatted value. The wizard reads CSVs as UTF-8 with a header row and keeps exact filter strings, including leading zeros.

In projects with an explicit task list, add the reporting task to your pipeline driver after the tasks that produce its source CSVs. The notebook also runs from the generated Make target. For an existing hand-built reporting task, choose an unused folder and reselect the macros you want to bring over. The wizard detects an occupied reporting folder and prompts you to pick another path.
