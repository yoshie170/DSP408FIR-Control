"""Native saved-slot restore25/5A/58; never Recall, Store or current-bank writes."""
from dataclasses import dataclass
from pathlib import Path
import uuid
from dsp408.source_codec import frame
from dsp408.preset_bank import (prepare_backup,metadata_requests,state_requests,bank_requests,
    record_requests,BankBackupOperation,read_archive,write_archive,digest)
from dsp408.prs import snapshot_bytes

def source_data(path):
    manifest,entries=read_archive(path)
    if manifest['version']!=2:raise ValueError('This older backup lacks extended preset records. Make a new bank backup before bulk restore; its individual PRS files remain usable.')
    records=tuple(entries[f'P{i:02d}.extended.bin'] for i in range(1,20))
    banks=tuple(entries[f'P{i:02d}.fir.bin'] if records[i-1][0]==255 else None for i in range(1,20))
    return records,banks

def record_packets(slot,record):
    return tuple(frame(0x25,bytes((i,slot-1))+record[i*50:i*50+(22 if i==31 else 50)]) for i in range(32))

def flash_packets(slot,bank):
    """5A copies raw words into saved flash only; no9396/DSP application."""
    packets=[frame(0x58,(slot*16+i).to_bytes(2,'little')) for i in range(16)]
    for ch in range(12):
        start=ch*8192 if ch<4 else 32768+(ch-4)*4096
        size=8192 if ch<4 else 4096;area=bank[start:start+size]
        if area==b'\xff'*size:continue
        words=tuple(area[i:i+4][::-1] for i in range(0,size,4));count=len(words)
        for block in range((count+11)//12):
            payload=bytes((slot,ch,block))+count.to_bytes(2,'little')+b''.join(words[block*12:block*12+12])
            packets.append(frame(0x5A,payload))
    return tuple(packets)

@dataclass(frozen=True)
class BankRestorePermit:
    state:bytes
    bank:bytes
    catalog:bytes
    active:int
    names:tuple
    records:tuple
    banks:tuple
    requests:tuple
    extended:bool=True

def prepare_restore(state,bank,catalog,active,names,records,banks):
    base=prepare_backup(state,bank,catalog,active,names,True)
    records=tuple(bytes(r) for r in records);banks=tuple(bytes(b) if b is not None else None for b in banks)
    if len(records)!=19 or len(banks)!=19:raise ValueError('Nineteen source slots required')
    requests=metadata_requests()+state_requests()+bank_requests(0)
    for slot,(record,flash) in enumerate(zip(records,banks),1):
        if len(record)!=1572 or record[0] not in (0,255):raise ValueError('Invalid extended preset record')
        if record[0]==255:
            if flash is None or len(flash)!=65536:raise ValueError('Complete FIR for every stored source slot required')
            snapshot_bytes(record[:1556],flash)
        elif flash is not None:raise ValueError('Empty source slot must not contain a FIR bank')
        # Keep this slot unavailable until its complete data and FIR are checked.
        staged=b'\0'+record[1:]
        requests+=record_packets(slot,staged)
        if flash is not None:requests+=flash_packets(slot,flash)
        requests+=record_requests(slot)
        if flash is not None:requests+=bank_requests(slot)+(record_packets(slot,record)[0],)+record_requests(slot)
    requests+=metadata_requests()+state_requests()+bank_requests(0)
    return BankRestorePermit(base.state,base.bank,base.catalog,base.active,base.names,records,banks,requests)

class BankRestoreOperation(BankBackupOperation):
    def exchange(self,raw,*args,**kwargs):
        body=super().exchange(raw,*args,**kwargs)
        if raw[5]==0x25 and body!=bytes((raw[6],)):raise ValueError('Preset write acknowledgment block differs')
        return body
    def report(self,stage,waiting=False):
        self.progress({'busy':True,'operation':'bank_restore','stage':stage,'done':self.done,'total':self.TOTAL,'waiting':waiting})
    def run_import(self,permit):
        canonical=prepare_restore(permit.state,permit.bank,permit.catalog,permit.active,permit.names,permit.records,permit.banks)
        if type(permit) is not BankRestorePermit or permit!=canonical:raise ValueError('Restore differs from canonical plan')
        source=Path(self.source_path);folder=Path(self.backup_directory);folder.mkdir(parents=True,exist_ok=True)
        tag=uuid.uuid4().hex;before_path=folder/('before-bank-restore-'+tag+'.dspbank')
        # Same single transport owner; a complete v2 destination backup must
        # finish before even the first EEPROM marker changes.
        baseline=prepare_backup(permit.state,permit.bank,permit.catalog,permit.active,permit.names,True)
        capture=BankBackupOperation(self.port,self.stop,record=self.record,log=self.log,
            progress=lambda e:self.progress({**e,'operation':'bank_restore','stage':'Backup before restore · '+e['stage']}),
            clock=self.clock,reply_decoder=self.reply_decoder,default_timeout=self.default_timeout)
        capture.run_import(baseline,before_path)
        # Freeze an independently validated copy of the exact source archive.
        m,entries=read_archive(source)
        current_records=tuple(entries[f'P{i:02d}.extended.bin'] for i in range(1,20))
        current_banks=tuple(entries[f'P{i:02d}.fir.bin'] if current_records[i-1][0]==255 else None for i in range(1,20))
        if (current_records,current_banks)!=(permit.records,permit.banks):raise ValueError('Source backup changed after review; no preset writes')
        source_copy=folder/('bank-restore-source-'+tag+'.dspbank');write_archive(source_copy,entries)
        self.permit=permit;self.TOTAL=len(permit.requests);self.done=0;self.port.begin_prs_import(permit)
        try:
            self.metadata()
            if self.state()!=permit.state or self.bank(0)!=permit.bank:raise ValueError('Current state changed; restore stopped before writing')
            self.record({'kind':'bank_restore_baseline','source':str(source_copy),'backup':str(before_path),'active_slot':permit.active})
            for slot,(record,flash) in enumerate(zip(permit.records,permit.banks),1):
                def send(raw):
                    self.record({'kind':'setter_intent','operation':'bank_restore','slot':slot,'frame_hex':raw.hex()})
                    self.exchange(raw,0x25 if raw[5]==0x25 else 1,f'Restoring P{slot:02d}',
                        expected_payload=bytes((raw[6],)) if raw[5]==0x25 else None,timeout=10.)
                staged=b'\0'+record[1:]
                for raw in record_packets(slot,staged):send(raw)
                if flash is not None:
                    for raw in flash_packets(slot,flash):send(raw)
                if self.state(slot)!=staged:raise ValueError(f'P{slot:02d} extended record differs; no commit')
                if flash is not None:
                    if self.bank(slot)!=flash:raise ValueError(f'P{slot:02d} FIR differs; no commit')
                    send(record_packets(slot,record)[0])
                    if self.state(slot)!=record:raise ValueError(f'P{slot:02d} final record differs')
                self.record({'kind':'bank_restore_slot_verified','slot':slot,'record_sha256':digest(record),'bank_sha256':digest(flash) if flash else None})
            # Metadata now reflects the source slots; active RAM/slot stay put.
            expected_catalog=bytes(r[0] for r in permit.records);actual_names=[]
            catalog=self.exchange(frame(0x22,b''),0x22,'Checking restored catalog')
            active=self.exchange(frame(0x14,b''),0x14,'Checking unchanged active preset')
            for i,record in enumerate(permit.records):
                body=self.exchange(frame(0x29,bytes((i,))),0x29,'Checking restored preset names')
                if len(body)!=15 or body[0]!=i:raise ValueError('Restored preset name index or extent differs')
                if record[0]==255 and body[1:]!=record[2:16]:raise ValueError('Restored preset names differ')
                actual_names.append(body[1:])
            if catalog!=expected_catalog or active!=bytes((permit.active,)):raise ValueError('Restored catalog or active slot differs')
            if self.state()!=permit.state or self.bank(0)!=permit.bank:raise ValueError('Current configuration changed during saved-bank restore')
            self.port.complete_prs_import(permit)
            result={'operation':'bank_restore','bank_hex':permit.bank.hex(),'parameters_verified':True,
                'backup_path':str(before_path),'source_copy':str(source_copy),'stored_slots':[i+1 for i,r in enumerate(permit.records) if r[0]==255],
                'metadata':{'catalog_markers':list(catalog),'active_slot_raw':permit.active,'names_raw_hex':{i:n.hex() for i,n in enumerate(actual_names)}},
                'done':self.done,'total':self.TOTAL,'audio_verified':False,'power_cycle_persistence_verified':False}
            self.record({'kind':'bank_restore_verified',**{k:v for k,v in result.items() if k!='bank_hex'}})
            return permit.state,result
        finally:self.port.end_prs_import()
