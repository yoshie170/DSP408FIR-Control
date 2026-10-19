"""Metadata for native macOS preview builds; no device or OS calls."""
APP_NAME = 'DSP408FIR Control'
BUNDLE_IDENTIFIER = 'tech.gremium.dsp408fircontrol'
MINIMUM_MACOS = '14.4'
ARCHITECTURES = ('arm64', 'x86_64')


def bundle_info(version, build):
    return {
        'CFBundleDisplayName': APP_NAME,
        'CFBundleShortVersionString': version,
        'CFBundleVersion': str(build),
        'LSMinimumSystemVersion': MINIMUM_MACOS,
        'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright': 'Copyright © 2026 Łukasz Białas · https://gremium.tech',
        'NSLocalNetworkUsageDescription': 'Connect to your t.racks FIR DSP 408 on the local network when you choose Connect.',
    }
