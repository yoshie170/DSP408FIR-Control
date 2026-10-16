"""Shared on-demand complete current FIR read, same serialized owner."""
from dsp408.source_codec import frame


class FirRefreshMixin:
    def request_fir_read(self):
        s=self.service
        if s is None:return False
        with s.lock:
            if not s.ready or s.stop.is_set() or s.inflight or s.dirty_blocks or s.generation!=s.confirmed_generation:return False
            if s.utilities.busy or s.utilities.locked or s.recall_running or s.recall_slot is not None or s.store_request is not None or s.prs_request is not None:return False
            s.recall_running=True;s.ready=False;self.fir_read_requested=True
        self.available.emit(False)
        self.recallProgress.emit({'busy':True,'operation':'fir_read','stage':'Reading FIR storage','done':0,'total':1325,'waiting':False})
        return True

    def read_requested_fir(self):
        if not self.fir_read_requested:return
        import hashlib
        s=self.service;self.fir_read_requested=False;bank=bytearray();done=0
        def progress():
            self.recallProgress.emit({'busy':True,'operation':'fir_read','stage':'Reading FIR storage','done':done,'total':1325,'waiting':False})
        try:
            # A manual bulk action can arrive before the first meter/input read
            # after a sparse startup. TX12 must never masquerade as its RX2C.
            s.finish_startup_boundary(system_read=True)
            if s.utilities.read_system():raise ValueError('DSP was locked before FIR read')
            for i in range(32):s.read_block(i);done+=1
            s.port.begin_fir_startup()
            try:
                for i in range(1261):
                    raw=frame(0x56,b'\0'+i.to_bytes(2,'little'))
                    s.port.arm_fir_startup(raw);s.port.write(raw);s.log('tx',raw)
                    body=s.wait(0x56).data
                    if len(body)!=(19 if i==1260 else 55) or body[:3]!=b'\0'+i.to_bytes(2,'big'):
                        raise ValueError('FIR refresh bank/index/extent mismatch')
                    bank.extend(body[3:]);done+=1
                    if i%16==0:progress()
                s.port.complete_fir_startup()
            finally:s.port.end_fir_startup()
            for i in range(32):s.read_block(i);done+=1
            if len(bank)!=65536:raise ValueError('Incomplete current FIR bank')
            bank=bytes(bank)
            s.record({'kind':'control_startup_fir_complete','transport':s.medium.lower(),'selector':0,'blocks':1261,
                'bytes':len(bank),'raw_hex':bank.hex(),'sha256':hashlib.sha256(bank).hexdigest(),
                'state_hex':s.expected.hex(),'state_sha256':hashlib.sha256(s.expected).hexdigest()})
            s.observe_fir_bank(bank);self.firBank.emit(bank);s.ready=True;s.recall_running=False
            progress();self.available.emit(True);self.recallResult.emit({'operation':'fir_read','parameters_unchanged':True})
        except Exception:
            s.ready=False;s.recall_failed=True
            self.recallProgress.emit({'busy':False,'operation':'fir_read','failed':True,'stage':'FIR read stopped','done':done,'total':1325,'waiting':False})
            raise
        finally:s.recall_running=False

