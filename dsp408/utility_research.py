"""Raw EXE utility layouts, for local files only. Not a device preset driver."""
from dsp408.source_codec import frame,integer

EMPTY_EFFECTS={0x10:'starts and initializes MCU session; not side-effect-free discovery',
    0x11:'ends MCU session',0x12:'source idle/session operation',0x13:'identity reply',
    0x14:'active preset index reply',0x22:'19 stored-prefix markers',
    0x23:'factory initialization, EEPROM writes/preset markers cleared; destructive',
    0x2C:'raw system status reply',0x40:'source telemetry reply'}
BYTE_EFFECTS={0x20:'loads preset into current state and FIR area; slot0 erases current FIR sectors',
    0x21:'stores current preset prefix and FIR bank',0x24:'overwrites shared current parameter RAM with stored preset; physical staging blocked',
    0x27:'reads current configuration block',0x28:'reads staged preset block',0x29:'reads preset name'}


def inspect_utility(command,payload):
    integer(command,0,255);payload=bytes(payload)
    record={'command':f'0x{command:02X}','payload_hex':payload.hex(),'hardware_verified':False,
            'scope':'source utility layout only; no execution or transaction confirmation'}
    if command in EMPTY_EFFECTS:
        if payload:raise ValueError('Source utility requires an empty payload')
        record['source_effect']=EMPTY_EFFECTS[command]
    elif command in BYTE_EFFECTS:
        if len(payload)!=1:raise ValueError('Source utility requires one explicit byte')
        if command in (0x27,0x28) and payload[0]>=32:raise ValueError('Source config block must be0..31')
        record.update(index_raw=payload[0],source_effect=BYTE_EFFECTS[command])
    elif command==0x19:
        if len(payload)!=3:raise ValueError('Source EEPROM read needs addressLE16 and countU8')
        record.update(address_raw=int.from_bytes(payload[:2],'little'),count_raw=payload[2],
                      source_effect='reads EEPROM bytes, RX19 carries bytes only; no address echo')
    elif command==0x26:
        if len(payload)!=14:raise ValueError('Configuration name needs14 explicit bytes')
        record.update(name_bytes_hex=payload.hex(),source_effect='writes current RAM name and EEPROM; NUL tail becomes spaces; source RX01 slot+14 name bytes')
    elif command==0x25:
        if len(payload)<2:raise ValueError('Preset block requires block and raw storage index')
        block=payload[0]
        if block>31 or len(payload)!=(24 if block==31 else 52):raise ValueError('EXE profile uses31x50 bytes then22 bytes')
        record.update(block_index_raw=block,storage_index_raw=payload[1],body_hex=payload[2:].hex(),
            source_effect='writes EEPROM at storage_index*1580+25+block*50; RX25 echoes block only',
            warning='Bulk backup restore, not single PRS import. Host takes1572 bytes from record+1; FIR loader starts at record+1557, so the spans overlap16 bytes. EEPROM meaning remains unresolved; no hardware upload authorization')
    else:raise ValueError('No audited utility layout for command')
    return record


def review_frame(command,payload,*,device_address):
    """Produce an offline review record, never a send action."""
    integer(device_address,1,255);record=inspect_utility(command,payload)
    record['frame_hex']=frame(command,payload,device_address).hex();return record
