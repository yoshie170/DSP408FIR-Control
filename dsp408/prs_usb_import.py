"""Prepared, separately gated PRS parameter import; no FIR/preset writes."""
from dataclasses import dataclass
from dsp408.prs import validate,BODY_START,FIR_START,FIR_END
from dsp408.prs_apply_review import review
from dsp408.prs_apply_transaction import PrsApplyRehearsal,ordered_packets
from dsp408.source_codec import frame

PRS_IMPORT_AUTHORIZED=True
BLOCK_REASON='PRS parameter import requires authorization in this profile'
FF_BANK=b'\xff'*65536


@dataclass(frozen=True)
class ImportPermit:
    state: bytes
    prs: bytes
    requests: tuple


def prepare_import(state,prs):
    """No I/O. FF is a required preflight predicate, NOT an observed bank."""
    state=bytes(state);prs=validate(bytes(prs))
    if prs[FIR_START:FIR_END]!=FF_BANK:raise ValueError('First PRS import requires an all-FF FIR file; numeric FIR remains locked')
    report=review(state,FF_BANK,prs);packets=ordered_packets(report)
    from dsp408.preset_store import encode_name
    for op,payload,path in packets:
        if op in (0x3D,0x5B):
            raise ValueError('Channel/FIR name changes are not released for USB PRS import')
        if op==0x26 and encode_name(payload.decode('ascii'))!=payload:
            raise ValueError('PRS import name requires canonical printable ASCII14')
    requests=[frame(0x22,b''),frame(0x14,b'')]
    states=tuple(frame(0x27,bytes((i,))) for i in range(32))
    banks=tuple(frame(0x56,b'\0'+i.to_bytes(2,'little')) for i in range(1261))
    requests.extend(states);requests.extend(banks)
    if report['packets']:
        requests.extend(frame(0x35,bytes((ch,1))) for ch in range(12));requests.extend(states)
        requests.extend(frame(op,payload) for op,payload,path in packets)
        requests.extend(states);requests.extend(banks)
        expected=state[:2]+prs[BODY_START:FIR_START]
        for ch in range(12):
            offset,bit=(1432,ch) if ch<4 else (1434,ch-4)
            flag=(int.from_bytes(expected[offset:offset+2],'little')>>bit)&1
            requests.append(frame(0x35,bytes((ch,flag))))
        requests.extend(states)
    requests.extend((frame(0x22,b''),frame(0x14,b'')))
    return ImportPermit(state,prs,tuple(requests)),report


class UsbPrsImport(PrsApplyRehearsal):
    def check_port(self,port):
        if not PRS_IMPORT_AUTHORIZED:raise ValueError(BLOCK_REASON)

    def exchange(self,raw,*args,**kwargs):
        if not PRS_IMPORT_AUTHORIZED:raise ValueError(BLOCK_REASON)
        self.port.arm_prs_request(raw,self.permit)
        return super().exchange(raw,*args,**kwargs)

    def run_import(self,permit):
        # Reconstruct from bytes rather than trusting caller-supplied frames.
        canonical,_=prepare_import(permit.state,permit.prs)
        if permit!=canonical:raise ValueError('PRS permit differs from complete canonical plan')
        self.check_port(self.port);self.permit=permit
        self.port.begin_prs_import(permit)
        original_record=self.record;original_progress=self.progress
        def record(event):
            event=dict(event)
            if event.get('kind')=='prs_rehearsal_verified':self.port.complete_prs_import(permit)
            if event.get('operation')=='prs_rehearsal':event['operation']='prs_import'
            if event.get('kind','').startswith('prs_rehearsal_'):
                event['kind']=event['kind'].replace('prs_rehearsal_','prs_import_',1)
            event['hardware_enabled']=True
            original_record(event)
        def progress(event):
            original_progress({**event,'operation':'prs_import','hardware_enabled':True,'busy':True})
        self.record=record;self.progress=progress
        try:
            state,result=super().run(permit.state,FF_BANK,permit.prs)
            result={**result,'operation':'prs_import','hardware_enabled':True}
            return state,result
        finally:
            self.port.end_prs_import();self.record=original_record;self.progress=original_progress
