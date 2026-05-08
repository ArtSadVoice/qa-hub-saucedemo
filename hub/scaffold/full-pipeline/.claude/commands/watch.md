Start the Excel watch daemon that auto-regenerates the Word report whenever a TCM Excel file in input/ is saved.

```bash
python scripts/watch.py
```

The daemon polls every 5 seconds (default). Press Ctrl+C to stop.

Inform the user that:
- The watcher is now running in the background
- Any save to input/*.xlsx will automatically trigger report regeneration
- Output will appear in output/ with today's date in the filename
- To stop: press Ctrl+C in the terminal

If the user wants a different poll interval, run `python scripts/watch.py <seconds>` (e.g. `python scripts/watch.py 10` for 10-second polling).
