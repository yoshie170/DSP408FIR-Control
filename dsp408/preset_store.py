"""Manual native preset Store/name with validated destination and readback."""
import hashlib
from dsp408.preset_recall import RecallOperation,checked_slot,eeprom_requests
from dsp408.source_codec import frame

PRESET_STORE_AUTHORIZED=True
BLOCK_REASON='Preset Store/name requires authorization in this profile'


def encode_name(text):
    if not isinstance(text,str):raise ValueError('Preset name must be text')
    value=text.strip()
    try:raw=value.encode('ascii')
    except UnicodeEncodeError as error:raise ValueError('Preset name supports verified ASCII only') from error
    if not 1<=len(raw)<=14 or any(b<32 or b>126 for b in raw):
        raise ValueError('Preset name requires 1–14 printable ASCII characters')
    return raw.ljust(14,b' ')


def validate_store_context(slot,context):
    checked_slot(slot)
    if not PRESET_STORE_AUTHORIZED:raise ValueError(BLOCK_REASON)
    if not isinstance(context,dict):raise ValueError('Fresh Store context required')
    current=context.get('current',b'');target=context.get('target',b'');catalog=context.get('catalog',b'')
    if len(current)!=1556 or len(target)!=1556 or len(catalog)!=19:
        raise ValueError('Complete current/target/catalog required')
    marker=catalog[slot-1]
    if marker not in (0,255) or target[0]!=marker:raise ValueError('Target EEPROM marker differs')
    if marker==255 and target[2:16]!=context.get('target_name'):raise ValueError('Target EEPROM name differs')
    return current


class StoreOperation(RecallOperation):
    def report(self,stage,waiting=False):
        self.progress({'busy':True,'operation':'store','slot':self.slot,'stage':stage,
                       'done':self.done,'total':self.TOTAL,'waiting':waiting})

    def state(self,stage):
        result=bytearray()
        for i in range(32):
            body=self.exchange(frame(0x27,bytes((i,))),0x24,stage)
            if len(body)!=(7 if i==31 else 51) or body[0]!=i:raise ValueError('Store state block index or extent differs')
            result.extend(body[1:])
        return bytes(result)

    def stored(self,stage):
        result=bytearray()
        for raw in eeprom_requests(self.slot):
            body=self.exchange(raw,0x19,stage,arm=True)
            if len(body)!=raw[8]:raise ValueError('Store EEPROM block extent differs')
            result.extend(body)
        return bytes(result)

    def mutate(self,raw,stage,context,*,payload=None):
        validate_store_context(self.slot,context)
        self.record({'kind':'setter_intent','operation':'preset_store','slot':self.slot,
                     'frame_hex':raw.hex(),'current_state_hex':context['current'].hex(),
                     'target_before_hex':context['target'].hex(),'catalog_hex':context['catalog'].hex()})
        self.port.arm_store_request(raw,self.slot,context)
        return self.exchange(raw,1,stage,timeout=10.,expected_payload=payload)

    def run(self,slot,baseline,name,confirmed_target):
        checked_slot(slot)
        if not PRESET_STORE_AUTHORIZED:raise ValueError(BLOCK_REASON)
        self.slot=slot;desired=encode_name(name)
        # Maximum; adjust once the fresh current name establishes whether26 is needed.
        self.TOTAL=168
        catalog=self.exchange(frame(0x22,b''),0x22,'Checking Store destination')
        if len(catalog)!=19 or catalog[slot-1] not in (0,255):raise ValueError('Store catalog differs')
        active=self.exchange(frame(0x14,b''),0x14,'Checking current preset')
        if len(active)!=1 or not 1<=active[0]<=19:raise ValueError('Store requires a loaded user preset')
        named=self.exchange(frame(0x29,bytes((slot-1,))),0x29,'Reading destination name')
        if len(named)!=15 or named[0]!=slot-1:raise ValueError('Store destination name response differs')
        if not isinstance(confirmed_target,dict) or catalog[slot-1]!=confirmed_target.get('marker') or named[1:].hex()!=confirmed_target.get('name_hex'):
            raise ValueError('Store destination changed after confirmation; nothing written')
        target=self.stored('Backing up destination parameters')
        current=self.state('Checking current DSP parameters')
        if current!=baseline:raise ValueError('Current DSP state changed before Store; nothing written')
        context={'current':current,'target':target,'catalog':catalog,'target_name':named[1:]}
        validate_store_context(slot,context)
        renamed=current[2:16]!=desired
        self.TOTAL=168 if renamed else 135
        self.record({'kind':'preset_store_baseline','slot':slot,'current_state_hex':current.hex(),
                     'target_before_hex':target.hex(),'catalog_hex':catalog.hex(),'active_slot':active[0]})
        expected=bytearray(current);expected[2:16]=desired;expected=bytes(expected)
        if renamed:
            # MCU returns opcode01 with active slot +14 name bytes, NOT emptyACK.
            self.mutate(frame(0x26,desired),'Applying current configuration name',context,payload=active+desired)
            if self.state('Verifying current name change')!=expected:
                raise ValueError('Current name readback differs; Store stopped without repair')
            context={**context,'current':expected}
        self.mutate(frame(0x21,bytes((slot,))),'Saving preset in DSP',context)
        stored=self.stored('Verifying saved preset parameters')
        wanted=b'\xff'+target[1:2]+expected[2:]
        if stored!=wanted:raise ValueError('Stored preset differs; no retry or automatic restore')
        after_name=self.exchange(frame(0x29,bytes((slot-1,))),0x29,'Checking saved name')
        if after_name!=bytes((slot-1,))+desired:raise ValueError('Saved preset name differs')
        after=self.exchange(frame(0x22,b''),0x22,'Checking saved preset catalog')
        wanted_catalog=bytearray(catalog);wanted_catalog[slot-1]=255
        if after!=bytes(wanted_catalog):raise ValueError('Store catalog changes differ')
        after_active=self.exchange(frame(0x14,b''),0x14,'Checking saved active slot')
        if after_active!=bytes((slot,)):raise ValueError('Active slot differs after Store')
        current_after=self.state('Verifying current DSP parameters')
        if current_after!=expected:raise ValueError('Store changed current parameters unexpectedly')
        result={'operation':'store','slot':slot,'parameters_verified':True,'name_changed':renamed,
                'overwritten':catalog[slot-1]==255,'state_sha256':hashlib.sha256(current_after).hexdigest(),
                'stored_sha256':hashlib.sha256(stored).hexdigest(),'fir_bank_read':False,
                'audio_verified':False,'power_cycle_persistence_verified':False}
        self.record({'kind':'preset_store_verified',**result,'state_hex':current_after.hex(),'stored_hex':stored.hex()})
        self.report('Preset saved · parameters verified')
        return current_after,{'active_slot_raw':slot,'catalog_markers':list(after),
                              'name_index':slot-1,'name_raw_hex':desired.hex()},result
