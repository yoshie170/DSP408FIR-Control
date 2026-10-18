"""Replace one local file using an exclusive temporary file in its directory."""
import os
from pathlib import Path
import tempfile


def write_bytes(path,data):
    target=Path(path);temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent,prefix=target.name+'.',
                                         suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name)
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
