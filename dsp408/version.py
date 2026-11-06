"""Public release and Windows build revision. No runtime dependencies."""
VERSION = '0.9.2'
BUILD = 170
WINDOWS_VERSION = tuple(map(int, VERSION.split('.'))) + (BUILD,)
