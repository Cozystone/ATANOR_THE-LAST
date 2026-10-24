"""Preflight for owned research artifacts; never deletes or relocates user data."""
from pathlib import Path
import shutil
import tempfile


def require_space(output, *, minimum_bytes=8 * 1024**3):
    """Check output and process TEMP before an attempt, without creating files.

    The available-space observation is not a reservation; callers must also check
    during long experiments and preserve an INVALID result if storage disappears.
    """
    if type(minimum_bytes) is not int or minimum_bytes < 0:
        raise ValueError('invalid storage minimum')
    result = []
    for destination in (Path(output).absolute(), Path(tempfile.gettempdir()).absolute()):
        existing = destination
        while not existing.exists():
            if existing.parent == existing:
                raise ValueError('no existing storage ancestor')
            existing = existing.parent
        usage = shutil.disk_usage(existing)
        result.append({'destination': str(destination), 'free_bytes': usage.free})
        if usage.free < minimum_bytes:
            raise OSError(f'insufficient research storage: {destination}: {usage.free} < {minimum_bytes}')
    return result
