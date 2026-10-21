Open `slate/index.html` in a browser to see the slate; it needs nothing installed. For the commands, `experimentkit --help` lists them (`ingest`, `storage`, `cameras`) and `experimentkit storage --help` the storage ones. To see ingest work with no camera or card, run the example that builds a fake SD card and a throwaway project in a temporary folder:

```bat
.venv\Scripts\python examples\ingest_plan.py
```
