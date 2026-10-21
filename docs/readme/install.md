It needs two lab packages that are not on PyPI: **projectkit** (the record), from the sibling folder `../Tool-ProjectManager`, so clone that beside this repository; and **markertracker** (frame sources), from Tool-TrackAnything on GitHub at commit `a934ab5`, so Git must be installed. `pyproject.toml` names both under `[tool.uv.sources]`, which only [uv](https://docs.astral.sh/uv/) reads. With uv it is one step, test tools included:

```bat
uv sync
```

pip reads none of that. To install with pip, make the `.venv` (the first of the two lines at the end of this section), put the two lab packages into it, then install this one (the second line):

```bat
.venv\Scripts\pip install -e ..\Tool-ProjectManager
.venv\Scripts\pip install "markertracker @ git+https://github.com/Xu-Lab-CU-Boulder/Tool-TrackAnything.git@a934ab51b5fbca59435b199fc0894e6eff2b8c1d"
```

Optional: daviskit (Tool-DaVisKit) installed in the same environment reads the DaVis `.set` files and runs the QC; matplotlib draws the storage plots. `cameras temps` needs `harvesters` and `genicam` from PyPI, and DaVis's own camera drivers.
