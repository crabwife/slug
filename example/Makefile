PYTHON ?= python3

.PHONY: analysis
analysis:
	cd a_import/src && $(PYTHON) -c 'import json; from pathlib import Path; scope = {"__name__": "__main__"}; [exec(compile("".join(cell["source"]), "run.ipynb", "exec"), scope) for cell in json.loads(Path("run.ipynb").read_text())["cells"]]'
	cd b_analyze/src && $(PYTHON) -c 'import json; from pathlib import Path; scope = {"__name__": "__main__"}; [exec(compile("".join(cell["source"]), "run.ipynb", "exec"), scope) for cell in json.loads(Path("run.ipynb").read_text())["cells"]]'

# BEGIN REPORT WIZARD
PYTHON ?= python3
.PHONY: report

report:
	cd ./c_report/src && $(PYTHON) -c 'import json; from pathlib import Path; scope = {"__name__": "__main__"}; [exec(compile("".join(cell["source"]), "report.ipynb", "exec"), scope) for cell in json.loads(Path("report.ipynb").read_text())["cells"]]'

LATEXMK ?= latexmk
.PHONY: paper

paper: report
	cd ./paper && $(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error -outdir=build ./main.tex
# END REPORT WIZARD
