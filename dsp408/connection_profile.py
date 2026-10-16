"""Local Ethernet target preference; never renumbers a DSP or opens a socket."""
from ipaddress import IPv4Address

# Exact editor V1.12 network setup validates1..250, not all uint8 values.
# edIdExit495E44 and bnSetClick4958A8; docs/CONNECTION_DIALOGS_V91.md.
DEVICE_ID_MIN=1
DEVICE_ID_MAX=250
DEFAULT_TARGET={'ip':'192.168.1.101','device_id':1}


def target_profile(ip,device_id):
    if not isinstance(ip,str):raise ValueError('Enter the DSP IPv4 address as text.')
    if type(device_id) is not int or not DEVICE_ID_MIN<=device_id<=DEVICE_ID_MAX:
        raise ValueError('DSP ID must be an integer from 1 to 250.')
    address=IPv4Address(ip.strip())
    if address.is_unspecified or address.is_multicast or address.is_loopback or str(address)=='255.255.255.255':
        raise ValueError('Enter a unicast DSP IPv4 address.')
    return {'ip':str(address),'device_id':device_id}


def source_address(ip):
    if not isinstance(ip,str):raise ValueError('Enter the PC IPv4 address as text.')
    address=IPv4Address(ip.strip())
    if address.is_unspecified or address.is_multicast or address.is_loopback or str(address)=='255.255.255.255':
        raise ValueError('Enter a unicast PC IPv4 address.')
    return str(address)


def ethernet_profile(ip,device_id,source_ip,*,read=False):
    # Empty override delegates adapter/source selection to the OS route table.
    # An explicit address remains available for machines with several NICs.
    target=target_profile(ip,device_id);source=None if source_ip=='' else source_address(source_ip)
    if source==target['ip']:raise ValueError('PC and DSP must have different IP addresses.')
    return target,source
