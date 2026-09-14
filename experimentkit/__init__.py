"""experimentkit: capture at the bench.

The Python side of ExperimentManager. Stage 1 is a dry run of ingest: point it
at an SD card or a capture folder and it reports where every clip would be
filed, by reading the slate out of the footage. It copies nothing.

    experimentkit ingest E:\\ --dry-run

An orchestrator, not a library. Frames come from markertracker; paths,
sidecars and schema checks come from projectkit. What lives here is the slate
protocol and the decisions: which experiment, which take, which camera, and
whether that is certain enough to act on.
"""

__version__ = "0.1.0"
