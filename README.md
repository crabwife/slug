# SLUG

`report-wizard` turns numbers from CSV files into LaTeX commands. Pick a row and column in the terminal, then use the resulting command in your paper.

Requires Python 3.9+. From this checkout, install with `pipx install .` or `python3 -m pip install .` in a virtual environment. Run `report-wizard` from the root of the project you want to set up.

Try the included [snail census](example/) with `cd example && make analysis && make report`. Run `make paper` there to build the PDF with LaTeX.

See [manual.md](manual.md) for setup and troubleshooting.
