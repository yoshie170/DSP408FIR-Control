"""Durable, exclusive host journal. No transport or device access."""
import json
import os
from pathlib import Path
import time


class DurableJournal:
    def __init__(self, path, *, sync_each=True,max_bytes=32*1024*1024):
        if type(max_bytes) is not int or not 32*1024*1024<=max_bytes<=128*1024*1024:raise ValueError('Journal limit must be32–128 MiB')
        self.stream = Path(path).open('x', encoding='utf-8', newline='\n')
        self.count = 0
        self.size = 0
        self.sync_each = sync_each
        self.max_bytes=max_bytes
        self.last_sync = time.monotonic()

    def record(self, event):
        line = json.dumps({'index': self.count, 'time_ns': time.time_ns(), **event}, ensure_ascii=False) + '\n'
        line_bytes=len(line.encode('utf-8'))
        if self.size + line_bytes > self.max_bytes:
            raise OSError(f'USB journal limit reached ({self.max_bytes//(1024*1024)} MiB); reconnect only after reviewing the log')
        self.stream.write(line)
        self.stream.flush()
        # Trials keep their original per-record durability. Interactive control
        # syncs setter intents before USB I/O and confirmations/session boundaries;
        # telemetry is flushed in order and synced at most once per second.
        critical = event.get('kind') in ('setter_intent', 'parameter_verified', 'full_scan_verified',
                                         'control_failed', 'session_started', 'session_finished','control_startup_fir_complete','control_startup_fir_preview',
                                         'preset_recall_verified','preset_recall_failed',
                                         'preset_store_baseline','preset_store_verified','preset_store_failed',
                                         'prs_import_baseline','prs_import_verified','prs_import_failed',
                                         'prs_full_baseline','prs_full_verified','prs_full_failed',
                                         'link_baseline','link_verified','bank_backup_verified','bank_backup_failed',
                                         'bank_restore_baseline','bank_restore_verified','bank_restore_failed',
                                         'fir_trial_baseline','fir_trial_verified','fir_trial_failed',
                                         'fir_import_baseline','fir_import_verified','fir_import_failed',
                                         'output_fir_baseline','output_fir_verified','output_fir_failed',
                                         'unlock_clear_intent','unlock_clear_verified')
        if self.sync_each or critical or time.monotonic()-self.last_sync >= 1.:
            os.fsync(self.stream.fileno())
            self.last_sync = time.monotonic()
        self.size += line_bytes
        self.count += 1

    def close(self):
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()
