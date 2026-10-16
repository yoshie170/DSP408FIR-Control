"""Prepared, separately gated USB trial: IN A identity FIR256 only."""
from dataclasses import dataclass
from dsp408.fir_upload_rehearsal import FirUploadRehearsal, prepare_fir_upload, FF_BANK
from dsp408.source_codec import frame

FIR_TRIAL_AUTHORIZED = True
BLOCK_REASON = 'The diagnostic FIR trial requires authorization in this profile'


@dataclass(frozen=True)
class FirTrialPermit:
    plan: object
    requests: tuple

    @property
    def state(self): return self.plan.state


def prepare_fir_trial(state):
    plan = prepare_fir_upload(state, FF_BANK, 0, [1.] + [0.]*255)
    states = tuple(frame(0x27, bytes((i,))) for i in range(32))
    banks = tuple(frame(0x56, b'\0'+i.to_bytes(2,'little')) for i in range(1261))
    start = (frame(0x22,b''),frame(0x14,b''))
    mutes = tuple(frame(0x35,bytes((ch,1))) for ch in range(12))
    final = []
    for ch in range(12):
        offset,bit=(1432,ch) if ch<4 else (1434,ch-4)
        flag=(int.from_bytes(plan.state[offset:offset+2],'little')>>bit)&1
        final.append(frame(0x35,bytes((ch,flag))))
    requests = start+states+banks+mutes+states+plan.frames+states+banks+tuple(final)+states+start
    return FirTrialPermit(plan, requests)


class UsbFirTrial(FirUploadRehearsal):
    def check_port(self, port):
        if not FIR_TRIAL_AUTHORIZED: raise ValueError(BLOCK_REASON)

    def exchange(self, raw, *args, **kwargs):
        if not FIR_TRIAL_AUTHORIZED: raise ValueError(BLOCK_REASON)
        self.port.arm_prs_request(raw, self.permit)
        return super().exchange(raw, *args, **kwargs)

    def run_import(self, permit):
        if permit != prepare_fir_trial(permit.state):
            raise ValueError('FIR trial differs from fixed IN A identity256 plan')
        self.check_port(self.port); self.permit=permit
        # Uses the same single-owner transaction slot and exact-frame policy
        # as PRS. Permit type selects a separate authorization and canonical plan.
        self.port.begin_prs_import(permit)
        original_record,original_progress=self.record,self.progress
        def record(event):
            event=dict(event)
            if event.get('kind')=='fir_rehearsal_verified':self.port.complete_prs_import(permit)
            if event.get('operation')=='fir_upload_rehearsal':event['operation']='fir_trial'
            if event.get('kind','').startswith('fir_rehearsal_'):
                event['kind']=event['kind'].replace('fir_rehearsal_','fir_trial_',1)
            event['hardware_enabled']=True;original_record(event)
        def progress(event):
            original_progress({**event,'operation':'fir_trial','hardware_enabled':True,'busy':True})
        self.record,self.progress=record,progress
        try:
            state,result=super().run_plan(permit.plan)
            return state,{**result,'operation':'fir_trial','hardware_enabled':True}
        finally:
            self.port.end_prs_import();self.record,self.progress=original_record,original_progress
