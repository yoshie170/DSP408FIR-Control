"""Short operational messages for the normal UI; raw diagnostics stay in logs."""
import re


def display_status(message):
    if message.startswith('Ethernet synchronization · '):
        phase=message.split(' · ',1)[1]
        if phase.startswith(('Reading FIR','Opening TCP')):return phase
        return display_status('USB synchronization · '+phase).replace('USB','Ethernet')
    if message.startswith('DEMO / OFFLINE'):
        return 'DEMO · ready to edit'
    prefixes = {
        'Ethernet read requested': 'Connecting Ethernet…',
        'Ethernet Control requested': 'Connecting Ethernet…',
        'Ethernet control · EXE/MCU': 'Ethernet · ready for control',
        'Ethernet configuration read': 'Channel settings loaded',
        'Ethernet · read connected': 'Ethernet connected · read only',
        'USB Control requested': 'Connecting USB…',
        'USB configuration read': 'Channel settings loaded',
        'USB · read connected': 'USB connected',
        'USB read requested': 'Connecting USB…',
        'USB control · EXE/MCU': 'USB · ready for control',
        'USB · requested value': 'Applying changes…',
        'USB · settings verified': 'Settings applied',
        'Full FIR storage bank received': 'FIR loaded',
        'USB read disconnected': 'USB disconnected',
        'USB read failed': 'Connection failed',
        'Offline configuration saved locally': 'Offline settings updated',
        'PRS parameters imported': 'Settings imported',
    }
    for prefix, text in prefixes.items():
        if message.startswith(prefix):
            return text
    if message.startswith('USB synchronization · '):
        phase = message.split(' · ',1)[1]
        return {'hello':'Connecting USB…','identity':'Identifying processor…',
                'system':'Reading device settings…','catalog':'Reading presets…',
                'active_slot':'Reading active preset…','names':'Reading preset names…',
                'fir':'Reading FIR…','configuration':'Reading channel settings…',
                'finish':'Finishing connection…','finish_ack':'Finishing connection…'}.get(phase,'Connecting USB…')
    if message.startswith('USB FIR raw read'):
        percent = re.search(r'(\d+)%',message)
        return 'Reading FIR…' + (' '+percent.group(0) if percent else '')
    if message.startswith('P') and ' · full parameter readback verified' in message:
        return message.split(' · ',1)[0]
    if message.startswith('Input FIR complete'):
        return 'FIR applied'
    return message


def operation_status(stage):
    """Keep failures intact; shorten only known, successful operation phases."""
    if any(word in stage.lower() for word in ('stopped','failed','error','cancelled')):
        return stage
    groups = {
        ('Preflight ·',): 'Reading current settings…',
        ('Transfer ·','FIR transfer step'): 'Applying FIR…',
        ('Clear ·',): 'Clearing FIR…',
        ('Verification ·','Checking entire FIR','Checking count/type'): 'Checking FIR and settings…',
        ('Mute ·','Temporarily muting','Checking all channels muted'): 'Muting channels…',
        ('Finishing ·','Restoring original'): 'Finishing and restoring Mute…',
        ('Waiting for DSP Recall',): 'Loading preset…',
        ('Preset loaded ·',): 'Preset loaded',
        ('Preset saved ·',): 'Preset saved',
    }
    for prefixes, text in groups.items():
        if stage.startswith(prefixes):return text
    return stage
