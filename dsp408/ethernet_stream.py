"""Strict stream framing for the pinned editor's Ethernet mode.

No sockets, discovery, OS adapter changes or DSP commands. Unlike the offline
forensic decoder, malformed bytes stop parsing rather than resynchronize.
Framing evidence: docs/PROTOCOL_STATIC_V6.md and PROTOCOL_RX_V8.md.
"""
from ipaddress import IPv4Address,IPv4Interface
from dsp408.wire_research import decode_editor_frame

EDITOR_TCP_PORT=9761
MAX_CHUNK=65536


class ObservedEthernetGreeting:
    """Only the actual B8(IP)/BE(empty) startup pair, not an ACK/discovery API.

    May arrive alongside/between replies; filter at stream ingress. Neither
    frame advances startup. Unknown
    payload/order/duplicates fail closed; meaning beyond observed bytes unknown.
    """
    def __init__(self,host):self.address=IPv4Address(host);self.position=0
    def accept(self,packet):
        if packet.command not in (0xB8,0xBE):return False
        expected=((0xB8,self.address.packed),(0xBE,b''))
        if self.position>=2 or packet.address_bytes!=b'\1\0' or (packet.command,packet.data)!=expected[self.position]:
            raise ValueError('Ethernet greeting differs from actual B8/IP then BE/empty prefix')
        self.position+=1;return True


class EthernetFrames:
    def __init__(self):
        self.pending=bytearray();self.failed=False

    def feed(self,chunk):
        if self.failed:raise ValueError('Ethernet stream already failed')
        if not isinstance(chunk,(bytes,bytearray,memoryview)):
            raise TypeError('Ethernet data must be bytes')
        try:
            if len(chunk)>MAX_CHUNK:raise ValueError('Ethernet chunk exceeds bound')
            self.pending.extend(chunk);frames=[]
            while self.pending:
                if self.pending[0]!=0x10 or (len(self.pending)>1 and self.pending[1]!=0x02):
                    raise ValueError('Unexpected Ethernet frame header; no resynchronization')
                if len(self.pending)<5:break
                length=self.pending[4]
                if length<1:raise ValueError('Invalid Ethernet frame length')
                size=length+8
                if len(self.pending)<size:break
                frames.append(decode_editor_frame(self.pending[:size]))
                del self.pending[:size]
            return frames
        except ValueError:
            self.failed=True;self.pending.clear();raise

    def finish(self):
        if self.failed:raise ValueError('Ethernet stream already failed')
        if self.pending:
            self.failed=True;self.pending.clear()
            raise ValueError('Ethernet connection ended inside a frame')


def local_network_check(dsp_ip,pc_ip,pc_mask):
    """Validate manually supplied addresses, without assuming DSP DHCP/mask.

    Reachability is only a subnet assessment using the PC mask, not a probe
    or evidence about router isolation, DSP mask, duplicate IP or TCP service.
    """
    target=IPv4Address(dsp_ip);pc=IPv4Interface(f'{pc_ip}/{pc_mask}')
    for address in (target,pc.ip):
        if address.is_unspecified or address.is_multicast or address.is_loopback or address==IPv4Address('255.255.255.255'):
            raise ValueError('A unicast device/PC IPv4 address is required')
    if target==pc.ip:raise ValueError('DSP and PC cannot use the same IP address')
    same=target in pc.network
    if same and pc.network.prefixlen<=30 and (target in (pc.network.network_address,pc.network.broadcast_address) or pc.ip in (pc.network.network_address,pc.network.broadcast_address)):
        raise ValueError('Network/broadcast address cannot identify a host')
    return {'dsp_ip':str(target),'pc_ip':str(pc.ip),'pc_network':str(pc.network),
            'same_pc_subnet':same,'tcp_port':EDITOR_TCP_PORT,
            'reachable_verified':False,'dsp_mask_verified':False,'dhcp_verified':False}
