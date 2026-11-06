"""Local interface selection; no DSP framing or system network changes."""
import socket
import sys


def ipv4_interfaces():
    from PySide6.QtNetwork import QNetworkInterface, QAbstractSocket
    rows=[]
    for interface in QNetworkInterface.allInterfaces():
        flags=interface.flags()
        if not flags & QNetworkInterface.IsUp or not flags & QNetworkInterface.IsRunning:
            continue
        if flags & QNetworkInterface.IsLoopBack:
            continue
        for entry in interface.addressEntries():
            if entry.ip().protocol()==QAbstractSocket.IPv4Protocol:
                ip=entry.ip().toString()
                rows.append({'ip':ip,'index':interface.index(),
                             'label':f'{interface.humanReadableName()} · {ip}'})
    return rows


def create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    # bind(source IP) alone does not constrain Darwin's outgoing interface
    # when Wi-Fi and a direct Ethernet adapter share the same IPv4 subnet.
    if sys.platform!='darwin' or source_address is None:
        return socket.create_connection(address,timeout,source_address)
    matches=[row for row in ipv4_interfaces() if row['ip']==source_address[0]]
    if len(matches)!=1:
        raise OSError('Selected computer IPv4 is not assigned to one active interface. Select the Ethernet adapter in Connection.')
    stream=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:
        if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:stream.settimeout(timeout)
        # Darwin bsd/netinet/in.h: IP_BOUND_IF = 25. Python may omit the name.
        stream.setsockopt(socket.IPPROTO_IP,getattr(socket,'IP_BOUND_IF',25),matches[0]['index'])
        stream.bind(source_address)
        stream.connect(address)
        return stream
    except BaseException:
        stream.close()
        raise
