# SLUG manual

## Try the example

From the SLUG checkout, run:

```sh
cd example
make analysis
make report
cat c_report/output/results.tex
```

The three rows in `a_import/input/snails.csv` produce `\SnailCount` (3) and `\MeanLeaves` (3.0). Change Pip’s leaf count from 1 to 4 and rerun those commands to see the mean update to 4.0. If you have `latexmk` and PDFLaTeX, `make paper` refreshes the macros and builds `paper/build/main.pdf`. The example is already configured. Launch the wizard inside `example/` and choose **Preview values** to inspect it.

## Set up your own project

1. Install SLUG with Python 3.9 or newer. From the SLUG checkout, run `pipx install .` or `python3 -m pip install .` in an activated virtual environment.
2. From your own project’s root, run `report-wizard`. Accept the suggested report folder or enter one, such as `g_report`. Choose your main TeX file, or choose **Report only** to generate macros without a PDF target.
3. Choose **Add macro**, pick a CSV, and add exact filters until one row remains. A single-row CSV needs no filters. Select a numeric column, give it a command name using only letters, and choose the decimal precision.
4. Confirm the preview, then choose **Save changes** and **Apply changes**. The wizard writes `.report-wizard.json`, a report notebook, and the Make targets. Keep these files and the report task’s input links in version control.
5. Use the command in your paper, for example `\MeanLeaves{} leaves`. If you declined automatic insertion, paste the wizard’s `\input{...}` line into the preamble. For percentage macros, add `\%` after the command.

Use arrow keys and Enter to select, type to filter, and press Esc to go back. For numbered prompts, run `report-wizard --plain`. Run the wizard again to edit saved macros. Update references in your TeX if you rename or remove a command.

## Refresh and troubleshoot

Run your analysis first after changing the input data. Then run `make report` to refresh the TeX commands or `make paper` to refresh and compile. If your project already uses those Make targets, use the alternate commands shown by the wizard, such as `make -f report-wizard.mk report`.

- **Command not found.** Activate the virtual environment you used for installation or run its `bin/report-wizard` directly. If you installed with pipx, make sure its executable directory is on your PATH.
- **Zero or multiple matching rows.** Check the CSV values and adjust the filters. Each macro must match exactly one row. Blank cells and nonnumeric values cannot be exported.
- **Undefined control sequence or missing `results.tex`.** Run the report target and check that the command appears in the output. Check the preamble input path. When compiling manually, compile from the directory containing the main TeX file.
- **LaTeX command already defined.** Rename the macro in the wizard and update its uses in your manuscript.
- **PDF build fails.** Check that `latexmk` and PDFLaTeX are installed, then read the first error in the build log. You can run the report target on its own to check the macro export.
