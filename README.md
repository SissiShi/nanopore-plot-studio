# nanopore-plot-studio
A tool for Sisi's nanopore event plotting and analysis 

## Features

- Open nanopore event tables from `.txt`, `.tsv`, or `.csv`
- Plot histograms, scatter plots, 2D histograms, hexbin plots, CDFs, and time plots
- Convert units for `ΔI`, dwell time, and inter-event interval
- Use quick presets for common nanopore analysis views
- Customize plot size, DPI, colors, labels, ticks, borders, and export format
- Save figures and export filtered data tables

## Requirements

- Python 3.13
- pandas
- numpy
- matplotlib

## Installation

Install the required packages:

```bash
py -3.13 -m pip install pandas numpy matplotlib
```

## Run

Run the GUI with:

```bash
py -3.13 nanopore_plot_gui.py
```

Or launch it on Windows with:

```bash
Launch_nanopore_plot_gui.bat
```

## Notes

This project is designed for nanopore event-table visualization and figure generation in a simple desktop workflow.
