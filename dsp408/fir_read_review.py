"""Replay dedicated full FIR host journals offline; no device or file mutation."""
import hashlib,json
from dsp408.startup_research import StartupReview
from dsp408.usb_fir_read import validate_fir_read_request
from dsp408.usb_read import read_bus_frame,IDENTITY
from dsp408.fir_bank import describe_bank


def inspect_bytes(raw):
    raw=bytes(raw)
    if len(raw)>32*1024*1024 or not raw or not raw.endswith(b'\n'):raise ValueError('Invalid or incomplete FIR journal file')
    rows=raw.splitlines()
    if len(rows)>200000:raise ValueError('FIR journal record limit')
    review=StartupReview(transport='usb',layout='common-prefix1556',device_address=1,full_fir=True)
    intent=None;poll=False;closed=False;complete=None;failure=None;started=False;tx_count=0;issues=[];disconnecting=False
    for index,line in enumerate(rows):
        try:
            if len(line)>16384:raise ValueError('FIR journal line limit')
            row=json.loads(line)
            if not isinstance(row,dict) or type(row.get('index')) is not int or row['index']!=index:raise ValueError('Journal index differs')
            if closed:raise ValueError('Records after session end')
            kind=row['kind']
            if kind=='session_started':
                if started or index:raise ValueError('Duplicate session start')
                started=True
            elif not started:raise ValueError('Missing session start')
            elif kind=='tx_intent':
                if disconnecting:raise ValueError('TX after disconnect')
                if intent is not None:raise ValueError('Overlapping TX intents')
                intent=bytes.fromhex(row['frame_hex']);validate_fir_read_request(intent)
            elif kind=='tx_completed':
                outgoing=bytes.fromhex(row['frame_hex'])
                if intent is None or outgoing!=intent:raise ValueError('Completed TX differs from intent')
                packet=validate_fir_read_request(outgoing);intent=None;tx_count+=1
                if packet.command==0x11 and not packet.data and review.recognized:
                    disconnecting=True;poll=False
                elif review.phase!='complete_candidate':review.feed('tx',outgoing)
                elif packet.command==0x40 and not packet.data and not poll:poll=True
                else:raise ValueError('Unexpected post-startup TX')
            elif kind=='rx_report':
                packet=read_bus_frame(bytes.fromhex(row['report_hex']))
                if review.phase!='complete_candidate':
                    if packet.command!=review.response and not (packet.command==1 and not packet.data):raise ValueError('Unexpected startup response')
                    if packet.command==0x10 and packet.data!=b'\x33':raise ValueError('Hello differs from capture')
                    if packet.command==0x13 and packet.data!=IDENTITY:raise ValueError('Identity differs from capture')
                    review.feed('rx',packet.raw)
                elif packet.command==0x40 and poll and len(packet.data)==42:poll=False
                elif packet.command!=1 or packet.data:raise ValueError('Unrequested post-startup response')
            elif kind=='fir_bank_complete':
                if complete is not None or review.phase!='complete_candidate':raise ValueError('Bank certificate before complete startup or duplicate')
                bank=review.trace.fir_area.data();complete=describe_bank(bank)
                if (row.get('bytes'),row.get('blocks'),row.get('selector'),row.get('sha256'))!=(65536,1261,0,complete['sha256']):
                    raise ValueError('Bank certificate differs from received blocks')
            elif kind=='session_finished':
                failure=row.get('error');closed=True
                if not failure and (intent is not None or poll):raise ValueError('Healthy close with incomplete transaction')
            else:raise ValueError('Unsupported FIR journal event')
        except (ValueError,KeyError,TypeError,IndexError) as error:
            issues.append({'index':index,'reason':str(error)});break
    status=('invalid_prefix' if issues else 'failed_prefix' if failure else
            'cancelled_before_complete' if disconnecting and complete is None else
            'validated_closed' if closed else 'validated_open_prefix')
    result={'scope':'Offline replay of host FIR bank read, no audio or persistence certification',
            'status':status,'issues':issues,'session_error':failure,'records':len(rows),
            'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'tx_count':tx_count,
            'fir_bank':complete,'startup_complete':review.phase=='complete_candidate',
            'pending_intent':intent is not None,'configuration_sha256':hashlib.sha256(review.trace.configuration.data()).hexdigest()
                if review.trace.configuration is not None and not review.trace.configuration.missing_blocks else None}
    bank=review.trace.fir_area.data() if complete is not None and not issues else None
    return result,bank
