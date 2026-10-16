"""Read-only P01–P19 bank backup. No staging, Recall, Store or EEPROM writes.

The project .dspbank ZIP contains original-format individual PRS files AND
lossless received parameter/flash bytes. It is not the OEM bulk-file format.
"""
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,os,tempfile,zipfile,zlib
from dsp408.source_codec import frame
from dsp408.preset_recall import RecallOperation,eeprom_requests,check_target
from dsp408.prs import snapshot_bytes

FORMAT='DSP408 preset bank'
LIMIT=4*1024*1024

def digest(raw):return hashlib.sha256(raw).hexdigest()
def state_requests():return tuple(frame(0x27,bytes((i,))) for i in range(32))
def bank_requests(slot):return tuple(frame(0x56,bytes((slot,))+i.to_bytes(2,'little')) for i in range(1261))
def record_requests(slot):
    start=25+(slot-1)*1580
    if type(slot) is not int or not 1<=slot<=19:raise ValueError('Stored preset P01–P19 required')
    return tuple(frame(0x19,(start+50*i).to_bytes(2,'little')+bytes((50 if i<31 else 22,))) for i in range(32))
def metadata_requests():return (frame(0x22,b''),frame(0x14,b''))+tuple(frame(0x29,bytes((i,))) for i in range(19))

@dataclass(frozen=True)
class BankBackupPermit:
    state:bytes
    bank:bytes
    catalog:bytes
    active:int
    names:tuple
    requests:tuple
    extended:bool=False

def prepare_backup(state,bank,catalog,active,names,extended=False):
    state,bank,catalog=bytes(state),bytes(bank),bytes(catalog);names=tuple(bytes(n) for n in names)
    if len(state)!=1556 or len(bank)!=65536:raise ValueError('Complete current parameters and FIR required')
    if len(catalog)!=19 or any(v not in (0,255) for v in catalog):raise ValueError('Unrecognized preset catalog markers')
    if type(active) is not int or not 1<=active<=19:raise ValueError('Known active preset P01–P19 required')
    if len(names)!=19 or any(len(n)!=14 for n in names):raise ValueError('Complete nineteen preset names required')
    if type(extended) is not bool:raise ValueError('Explicit backup version required')
    requests=metadata_requests()+state_requests()+bank_requests(0)
    for slot,marker in enumerate(catalog,1):
        if extended:requests+=record_requests(slot)+(bank_requests(slot) if marker==255 else ())+record_requests(slot)
        elif marker==255:requests+=eeprom_requests(slot)+bank_requests(slot)+eeprom_requests(slot)
    requests+=metadata_requests()+state_requests()+bank_requests(0)
    return BankBackupPermit(state,bank,catalog,active,names,requests,extended)

def archive_contents(current,bank,catalog,active,names,slots,records=None):
    """Preserve exact bytes independently of normalized vendor serialization."""
    entries={};catalog_rows=[]
    for label,state,flash in [('CURRENT',current,bank)]+[(f'P{i:02d}',*slots[i]) for i in sorted(slots)]:
        entries[label+'.parameters.bin']=bytes(state)
        entries[label+'.fir.bin']=bytes(flash)
        entries[label+'.prs']=snapshot_bytes(state,flash)
    if records is not None:
        if set(records)!=set(range(1,20)):raise ValueError('All nineteen extended preset records required')
        for slot,raw in records.items():entries[f'P{slot:02d}.extended.bin']=bytes(raw)
    for i in range(1,20):
        catalog_rows.append({'slot':i,'stored':catalog[i-1]==255,'name_hex':names[i-1].hex()})
    manifest={'format':FORMAT,'version':2 if records is not None else 1,'identity':'FIR408 V0115P',
        'created_utc':datetime.now(timezone.utc).isoformat(),'active_slot':active,
        'catalog_hex':catalog.hex(),'slots':catalog_rows,
        'files':{name:{'size':len(raw),'sha256':digest(raw)} for name,raw in entries.items()}}
    entries['manifest.json']=(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode('utf-8')
    return entries

def write_archive(path,entries):
    """Install only a complete fsynced archive; keep an existing backup on error."""
    path=Path(path)
    if path.suffix.lower()!='.dspbank':raise ValueError('Use the .dspbank backup extension')
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix=path.name+'.',suffix='.tmp',delete=False) as stream:
            temp=Path(stream.name)
            with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                for name,raw in entries.items():archive.writestr(name,raw)
            stream.flush();os.fsync(stream.fileno())
        read_archive(temp) # Includes raw/PRS consistency and checksums.
        os.replace(temp,path)
    finally:
        if temp is not None:temp.unlink(missing_ok=True)

def read_archive(path):
    path=Path(path)
    if path.stat().st_size>LIMIT:raise ValueError('Preset backup exceeds size limit')
    try:
        with zipfile.ZipFile(path) as archive:
            infos=archive.infolist()
            if not 4<=len(infos)<=80 or len({i.filename for i in infos})!=len(infos):raise ValueError('Duplicate or excessive backup entries')
            if sum(i.file_size for i in infos)>LIMIT or any(i.file_size>70000 or i.flag_bits&1 for i in infos):raise ValueError('Invalid backup entry size or encryption')
            entries={i.filename:archive.read(i) for i in infos}
        manifest=json.loads(entries['manifest.json'])
        if manifest['format']!=FORMAT or type(manifest['version']) is not int or manifest['version'] not in (1,2) or manifest['identity']!='FIR408 V0115P':raise ValueError('Unsupported preset backup')
        catalog=bytes.fromhex(manifest['catalog_hex']);rows=manifest['slots']
        if len(rows)!=19 or any(type(r['slot']) is not int for r in rows) or [r['slot'] for r in rows]!=list(range(1,20)):raise ValueError('Preset slot list differs')
        names=tuple(bytes.fromhex(r['name_hex']) for r in rows)
        prepare_backup(entries['CURRENT.parameters.bin'],entries['CURRENT.fir.bin'],catalog,manifest['active_slot'],names)
        if any(type(r['stored']) is not bool or r['stored']!=(catalog[i]==255) for i,r in enumerate(rows)):raise ValueError('Preset markers differ')
        labels=['CURRENT']+[f'P{r["slot"]:02d}' for r in rows if r['stored']]
        expected={label+suffix for label in labels for suffix in ('.parameters.bin','.fir.bin','.prs')}
        if manifest['version']==2:expected|={f'P{i:02d}.extended.bin' for i in range(1,20)}
        if set(entries)!=expected|{'manifest.json'} or set(manifest['files'])!=expected:raise ValueError('Unexpected or missing backup files')
        for name in expected:
            raw=entries[name]
            if manifest['files'][name]!={'size':len(raw),'sha256':digest(raw)}:raise ValueError('Backup checksum differs: '+name)
        for label in labels:
            state,flash=entries[label+'.parameters.bin'],entries[label+'.fir.bin']
            if entries[label+'.prs']!=snapshot_bytes(state,flash):raise ValueError('PRS differs from raw snapshot: '+label)
            if label!='CURRENT':
                slot=int(label[1:]);check_target(slot,state,catalog,names[slot-1])
        if manifest['version']==2:
            for slot in range(1,20):
                raw=entries[f'P{slot:02d}.extended.bin']
                if len(raw)!=1572 or raw[0]!=catalog[slot-1]:raise ValueError('Extended preset marker or extent differs')
                # Empty slots have a firmware-generated display name in RX29;
                # their EEPROM can retain an old name or erased bytes.
                if raw[0]==255 and raw[2:16]!=names[slot-1]:raise ValueError('Extended stored preset name differs')
                if catalog[slot-1]==255 and raw[:1556]!=entries[f'P{slot:02d}.parameters.bin']:raise ValueError('Extended preset differs from parameters')
        return manifest,entries
    except (KeyError,TypeError,IndexError,UnicodeError,zipfile.BadZipFile,OverflowError,zlib.error,NotImplementedError,RuntimeError) as error:
        raise ValueError('Invalid or incomplete preset backup') from error

def extract_archive(path,destination):
    """Offline export to a NEW folder, never extract arbitrary ZIP paths."""
    manifest,entries=read_archive(path);target=Path(destination)
    if target.exists():raise ValueError('Choose a new folder for the extracted backup')
    with tempfile.TemporaryDirectory(dir=target.parent,prefix='.dspbank-') as staging:
        prepared=Path(staging)/'complete';prepared.mkdir()
        for name,raw in entries.items():(prepared/name).write_bytes(raw)
        os.replace(prepared,target)
    return manifest

class BankBackupOperation(RecallOperation):
    def report(self,stage,waiting=False):
        self.progress({'busy':True,'operation':'bank_backup','stage':stage,
            'done':self.done,'total':self.TOTAL,'waiting':False})
    def exchange(self,raw,*args,**kwargs):
        self.port.arm_prs_request(raw,self.permit)
        return super().exchange(raw,*args,**kwargs)
    def metadata(self):
        catalog=self.exchange(frame(0x22,b''),0x22,'Reading preset catalog')
        active=self.exchange(frame(0x14,b''),0x14,'Reading active preset')
        names=[]
        for i in range(19):
            body=self.exchange(frame(0x29,bytes((i,))),0x29,'Reading preset names')
            if len(body)!=15 or body[0]!=i:raise ValueError('Preset name index or extent differs')
            names.append(body[1:])
        if (catalog,active,tuple(names))!=(self.permit.catalog,bytes((self.permit.active,)),self.permit.names):raise ValueError('Preset catalog, active slot or names changed after review')
        return catalog,self.permit.active,tuple(names)
    def state(self,slot=0):
        data=bytearray()
        for i,raw in enumerate((record_requests(slot) if self.permit.extended else eeprom_requests(slot)) if slot else state_requests()):
            body=self.exchange(raw,0x19 if slot else 0x24,f'Reading P{slot:02d} parameters' if slot else 'Checking current parameters')
            if slot:
                size=(22 if self.permit.extended else 6) if i==31 else 50
                if len(body)!=size:raise ValueError('Preset EEPROM extent differs')
                data.extend(body)
            else:
                if len(body)!=(7 if i==31 else 51) or body[0]!=i:raise ValueError('Current parameters index or extent differs')
                data.extend(body[1:])
        return bytes(data)
    def bank(self,slot):
        data=bytearray()
        for i,raw in enumerate(bank_requests(slot)):
            body=self.exchange(raw,0x56,f'P{slot:02d} FIR · {i+1}/1261' if slot else f'Checking current FIR · {i+1}/1261')
            if len(body)!=(19 if i==1260 else 55) or body[:3]!=bytes((slot,))+i.to_bytes(2,'big'):raise ValueError('Preset FIR bank, block or extent differs')
            data.extend(body[3:])
        return bytes(data)
    def run_import(self,permit,path=None):
        if type(permit) is not BankBackupPermit or permit!=prepare_backup(permit.state,permit.bank,permit.catalog,permit.active,permit.names,permit.extended):raise ValueError('Backup permit differs from canonical read plan')
        if path is None:path=self.destination
        self.permit=permit;self.TOTAL=len(permit.requests);self.port.begin_prs_import(permit)
        try:
            catalog,active,names=self.metadata()
            if self.state()!=permit.state or self.bank(0)!=permit.bank:raise ValueError('Current configuration changed after backup review')
            slots={};records={} if permit.extended else None
            for slot,marker in enumerate(catalog,1):
                if marker!=255 and not permit.extended:continue
                state=self.state(slot)
                if records is not None:records[slot]=state
                if state[0]!=marker:raise ValueError('Preset EEPROM marker differs')
                if marker==255:check_target(slot,state[:1556],catalog,names[slot-1])
                bank=self.bank(slot) if marker==255 else None
                if self.state(slot)!=state:raise ValueError('Stored preset changed during backup')
                if marker==255:slots[slot]=(state[:1556],bank)
                self.record({'kind':'bank_backup_slot','slot':slot,'state_sha256':digest(state),'bank_sha256':digest(bank) if bank is not None else None})
            self.metadata()
            if self.state()!=permit.state or self.bank(0)!=permit.bank:raise ValueError('Current configuration changed during backup')
            self.port.complete_prs_import(permit)
            if self.stop.is_set():raise InterruptedError('Backup cancelled before saving')
            write_archive(path,archive_contents(permit.state,permit.bank,catalog,active,names,slots,records))
            result={'operation':'bank_backup','path':str(path),'stored_slots':list(slots),
                'bank_hex':permit.bank.hex(),'parameters_verified':True,'read_only':True,
                'done':self.done,'total':self.TOTAL}
            self.record({'kind':'bank_backup_verified',**{k:v for k,v in result.items() if k!='bank_hex'}})
            return permit.state,result
        finally:self.port.end_prs_import()
