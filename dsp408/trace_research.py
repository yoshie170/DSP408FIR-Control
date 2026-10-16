"""Explicit-direction offline RX scenarios. No driver, device session or writes.

Caller starts each configuration/FIR collection explicitly. Unsolicited
telemetry and empty01/02 replies never acknowledge a parameter transaction.
Complete bytes are candidates for analysis, not proof of a fresh device read.
"""
import hashlib,math
from dsp408.wire_research import decode_editor_frame
from dsp408.editor_state_research import StateBlockAssembler
from dsp408.editor_rx_research import decode_telemetry_payload,decode_system_payload,decode_preset_catalog_payload,decode_current_name_reply,FirAreaAssembler
from dsp408.link_research import resolve_link_mask


class OfflineReadTrace:
    def __init__(self,*,layout,device_address):
        if type(device_address) is not int or not 1<=device_address<=255:
            raise ValueError('Explicit source device address must be1..255')
        # Validate profile without silently selecting/padding1572 or1556.
        StateBlockAssembler(layout=layout)
        self.layout=layout;self.device_address=device_address;self.configuration=None;self.fir_area=None
        self.tx_count=0;self.rx_count=0;self.empty_replies=0;self.latest_telemetry=None;self.latest_system_status=None
        self.latest_preset_catalog=None;self.configuration_response_command=0x24
        self.latest_current_name_reply=None

    def begin_configuration_read(self,*,response_command=0x24):
        if type(response_command) is not int or response_command not in (0x24,0x28):raise ValueError('Configuration response must explicitly be24 or28')
        self.configuration_response_command=response_command
        self.configuration=StateBlockAssembler(layout=self.layout)
    def begin_fir_area_read(self,selector):self.fir_area=FirAreaAssembler(selector=selector)

    def feed(self,direction,raw):
        if direction not in ('tx','rx'):raise ValueError('Direction must be explicitly tx or rx')
        packet=decode_editor_frame(raw)
        # EXE TX490058 and MCU RXAE8A have different address byte positions.
        index=1 if direction=='tx' else 0
        if packet.address_bytes[index]!=self.device_address:raise ValueError('Trace source address differs from explicit device')
        event={'direction':direction,'command':f'0x{packet.command:02X}','payload_hex':packet.data.hex(),
               'address_bytes_hex':packet.address_bytes.hex(),'hardware_verified':False,
               'parameter_transaction_confirmed':False}
        if direction=='tx':
            self.tx_count+=1;event['classification']='outgoing source frame; no response correlation inferred'
            return event
        self.rx_count+=1
        if packet.command in (1,2):
            if packet.command==1 and packet.data:
                self.latest_current_name_reply=decode_current_name_reply(packet.data)
                event['classification']='source01 slot/name reply shape; no command echo or transaction confirmation'
            else:
                if packet.data:raise ValueError('Source MCU02 helper reply payload must be empty')
                self.empty_replies+=1;event['classification']='empty reply without command echo or transaction ID'
        elif packet.command==self.configuration_response_command and self.configuration is not None:
            self.configuration.add(packet.data)
            event['classification']='configuration block in explicit local collection'
            event['missing_blocks']=list(self.configuration.missing_blocks)
            if not self.configuration.missing_blocks:
                event['candidate_sha256']=hashlib.sha256(self.configuration.data()).hexdigest()
                event['complete_bytes_received']=True
        elif packet.command==0x22:
            self.latest_preset_catalog=decode_preset_catalog_payload(packet.data)
            event['classification']='raw stored-prefix markers, not confirmation of preset/FIR integrity'
        elif packet.command==0x2C:
            self.latest_system_status=decode_system_payload(packet.data)
            event['classification']='source system status raw fields; no automatic follow-up commands'
        elif packet.command==0x40:
            value=decode_telemetry_payload(packet.data);self.latest_telemetry=value
            event['classification']='source telemetry; no acknowledgement'
            event['source_dsp_percent']=value.editor_dsp_percent
            event['dynamics_word']=value.dynamics_word
        elif packet.command==0x56 and self.fir_area is not None:
            self.fir_area.add(packet.data)
            event['classification']='opaque FIR area block in explicit local collection'
            event['missing_block_count']=len(self.fir_area.missing_blocks)
            if not self.fir_area.missing_blocks:
                event['candidate_sha256']=hashlib.sha256(self.fir_area.data()).hexdigest()
                event['complete_bytes_received']=True
        else:event['classification']='raw response; no active supported collection or unresolved semantics'
        return event

    def report(self):
        from dataclasses import asdict
        result={'scope':'offline explicit-direction trace, no physical I/O',
                'hardware_verified':False,'device_address':self.device_address,'layout':self.layout,
                'tx_count':self.tx_count,'rx_count':self.rx_count,'empty_replies':self.empty_replies,
                'confirmed_parameter_transactions':0,'configuration_complete':False,'fir_area_complete':False}
        if self.configuration is not None:
            result['configuration_response_command']=f'0x{self.configuration_response_command:02X}'
            result['configuration_missing_blocks']=list(self.configuration.missing_blocks)
            if not self.configuration.missing_blocks:
                result['configuration_complete']=True
                state=self.configuration.decode();result['configuration_candidate_state']=state
                result['configuration_candidate_sha256']=hashlib.sha256(self.configuration.data()).hexdigest()
                masks=[c['link_mask_raw'] for c in state['channels']]
                result['source_link_resolutions']=[asdict(resolve_link_mask(masks,ch)) for ch in range(12)]
        if self.fir_area is not None:
            result['fir_area_selector']=self.fir_area.selector
            result['fir_area_missing_block_count']=len(self.fir_area.missing_blocks)
            if not self.fir_area.missing_blocks:
                result['fir_area_complete']=True
                result['fir_area_candidate_sha256']=hashlib.sha256(self.fir_area.data()).hexdigest()
        if self.latest_preset_catalog is not None:
            result['latest_preset_catalog']=asdict(self.latest_preset_catalog)
            result['latest_preset_catalog']['trailing_bytes_hex']=result['latest_preset_catalog'].pop('trailing_bytes').hex()
        if self.latest_current_name_reply is not None:
            result['latest_current_name_reply']=asdict(self.latest_current_name_reply)
        if self.latest_system_status is not None:
            result['latest_system_status']=asdict(self.latest_system_status)
            result['latest_system_status']['trailing_bytes_hex']=result['latest_system_status'].pop('trailing_bytes').hex()
        if self.latest_telemetry is not None:
            value=self.latest_telemetry
            levels=[]
            for l in value.levels:
                entry=asdict(l)
                if not math.isfinite(l.amplitude):entry['amplitude']=None
                levels.append(entry) # exact raw_word and unsupported status retained.
            result['latest_source_telemetry']={'levels':levels,
                 'input_compressor_bits':value.input_compressor_bits,'output_limiter_bits':value.output_limiter_bits,
                 'unknown_dynamics_bits':value.unknown_dynamics_bits,'dsp_counter':value.dsp_counter,
                 'source_dsp_percent':value.editor_dsp_percent,'trailing_bytes_hex':value.trailing_bytes.hex()}
        return result
