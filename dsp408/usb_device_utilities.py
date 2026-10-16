"""Manual device utility operations on the existing serialized USB owner.

No enumeration/connect here. Only explicit typed requests are dispatched.
Source39 has no available value readback; its completion must not be described
as independently verified generator/audio state. Lock is checked through2C.
"""
from dsp408.device_utilities import validate_utility, system_lock,session_lock,input_selection_read_request,INPUT_SELECTIONS
from dsp408.source_codec import frame


class DeviceUtilities:
    def __init__(self, host, publish):
        self.host, self.publish = host, publish
        self.requested = None
        self.running = False
        self.locked = False
        self.lock_known = False
        self.source = None
        self.frequency = None
        self.input_selection=None
        self.secret_active = False
        self.device_settings=None
        self.authentication_pending=False
        self.authenticated=False
        self.last_system_frame=None
        self.password_protected=False

    @property
    def busy(self):
        return self.requested is not None or self.running

    def state(self, **extra):
        return dict(busy=self.busy, locked=self.locked, lock_known=self.lock_known,
                    authentication_pending=self.authentication_pending,
                    authenticated=self.authenticated,
                    password_protected=self.password_protected,
                    source=self.source, frequency=self.frequency,input_selection=self.input_selection,
                    device_settings_hex=self.device_settings.hex() if self.device_settings is not None else None, **extra)

    def observe_system(self, payload):
        self.password_protected=system_lock(payload)
        self.locked = session_lock(payload,self.authenticated)
        self.lock_known = True
        self.publish(self.state())

    def invalidate_generator(self):
        # Whole-configuration operations may affect globals absent from the
        # parameter record. Never retain a claimed current source across them.
        self.source = self.frequency = None
        self.input_selection=None
        self.publish(self.state())

    def request(self, request):
        validate_utility(request)
        if request.kind=='device_ip' and self.host.medium!='USB':raise ValueError('Change the processor IP over USB')
        host = self.host
        with host.lock:
            if self.authentication_pending:
                if request.kind!='unlock' or host.stop.is_set() or self.busy:return False
                self.requested=request
                self.publish(self.state())
                return True
            if not host.ready or host.stop.is_set() or self.busy or host.recall_running or host.recall_failed:
                return False
            if host.recall_slot is not None or host.store_request is not None or host.prs_request is not None:
                return False
            if host.inflight or host.dirty_blocks or host.generation != host.confirmed_generation:
                return False
            if request.kind == 'unlock' and self.lock_known and not self.locked:
                return False
            if request.kind != 'unlock' and self.locked:
                return False
            self.requested = request
        self.publish(self.state())
        return True

    def read_system(self):
        self.host.port.write(frame(0x2C, b''))
        self.host.log('tx', frame(0x2C, b''))
        result = self.host.wait(0x2C)
        self.last_system_frame=result.raw
        self.observe_system(result.data)
        return self.locked

    def authenticate_startup(self):
        """Only a user-submitted subtype0 unlock, before any configuration read."""
        host=self.host
        with host.lock:
            request=self.requested
            if request is None:return False
            self.requested=None;self.running=True
        self.secret_active=True;self.publish(self.state())
        try:
            if request.kind!='unlock' or not self.authentication_pending:
                raise ValueError('Only explicit unlock is allowed during authentication')
            if not self.read_system():raise ValueError('Processor lock changed before authentication')
            host.port.arm_utility(request);host.port.write(request.packet)
            reply=host.wait(0x2D)
            if reply.data==b'\0\0':
                host.record({'kind':'utility_denied','operation':'unlock','password_redacted':True})
                self.publish(self.state(error='Incorrect password.'));return False
            if reply.data!=b'\0\1':raise ValueError('Unexpected authentication response.')
            self.authenticated=True
            host.record({'kind':'authentication_accepted','subtype':0,'scope':'current session; stored password protection retained'})
            if self.read_system():raise ValueError('Device lock verification failed.')
            self.authentication_pending=False
            host.record({'kind':'utility_completed','operation':'unlock','lock_verified':True,
                         'parameters_unchanged':False,'configuration_read_pending':True,'password_redacted':True})
            self.publish(self.state(operation='unlock',completed=True));return True
        finally:
            self.running=False;self.secret_active=False;self.publish(self.state())

    def read_input_selection(self):
        request=input_selection_read_request()
        self.host.port.arm_utility(request);self.host.port.write(request.packet)
        self.host.log('tx',request.packet);reply=self.host.wait(0x19)
        if len(reply.data)!=1 or reply.data[0] not in (0,1):
            raise ValueError('Unsupported input source readback.')
        self.input_selection=INPUT_SELECTIONS[reply.data[0]]
        return self.input_selection

    def read_device_settings(self):
        from dsp408.device_utilities import device_settings_read_request
        request=device_settings_read_request();self.host.port.arm_utility(request)
        self.host.port.write(request.packet);self.host.log('tx',request.packet)
        result=self.host.wait(0x19).data
        if len(result)!=8 or not 0<=result[0]<=250 or result[1] not in (0,1) or result[2] not in (0,1):raise ValueError('Unrecognized device settings')
        self.device_settings=result;return result

    def dispatch(self):
        host = self.host
        with host.lock:
            request = self.requested
            self.requested = None
            self.running = True
            self.secret_active = request.kind in ('lock','unlock')
        self.publish(self.state())
        try:
            locked_before = self.read_system()
            if (request.kind == 'unlock') != locked_before:
                raise ValueError('Device lock changed. Reconnect before continuing.')
            if request.kind in ('device_settings_read','device_ip','device_id'):
                before=self.read_device_settings()
                if request.kind!='device_settings_read':
                    if before!=request.before:raise ValueError('Device settings changed after review; nothing written')
                    host.port.arm_utility(request);host.port.write(request.packet);host.log('tx',request.packet);host.wait(1)
                    from ipaddress import IPv4Address
                    expected=bytes((request.device_id,))+before[1:] if request.kind=='device_id' else before[:4]+IPv4Address(request.device_ip).packed
                    if self.read_device_settings()!=expected:raise ValueError('Device settings readback differs; no retry')
                for index in range(32):host.read_block(index)
                host.record({'kind':'utility_completed','operation':request.kind,'device_settings_hex':self.device_settings.hex(),'parameters_unchanged':True})
                self.publish(self.state(operation=request.kind,completed=True));return
            if request.kind=='input_selection_read':
                self.read_input_selection()
                for index in range(32):host.read_block(index)
                host.record({'kind':'utility_completed','operation':request.kind,'input_selection':self.input_selection,
                             'input_selection_readback':True,'parameters_unchanged':True})
                self.publish(self.state(operation=request.kind,completed=True));return
            if request.kind=='input_selection':self.read_input_selection()
            host.port.arm_utility(request)
            host.inflight = True
            host.port.write(request.packet)
            # Never put password-containing TX into Qt frame logs or journals.
            if request.kind in ('generator','input_selection'):
                host.log('tx', request.packet)
            result = host.wait(0x2D if request.kind == 'unlock' else 1)
            host.inflight = False
            if request.kind == 'unlock':
                if result.data not in (b'\0\0', b'\0\1'):
                    raise ValueError('Unexpected authentication response.')
                if result.data == b'\0\0':
                    host.record({'kind': 'utility_denied', 'operation': 'unlock', 'password_redacted': True})
                    self.publish(self.state(error='Incorrect password.'))
                    return
                self.authenticated=True
                host.record({'kind':'authentication_accepted','subtype':0,'scope':'current session; stored password protection retained'})
            if request.kind=='lock':self.authenticated=False
            locked_after = self.read_system()
            expected = request.kind == 'lock'
            if locked_after != expected:
                raise ValueError('Device lock verification failed.')
            if request.kind=='input_selection' and self.read_input_selection()!=request.source:
                raise ValueError('Input source readback differs; no retry or restore.')
            # Verify ordinary parameters remained unchanged; generator globals
            # live outside this record and cannot be verified by this scan.
            if request.kind!='lock':
                for index in range(32):host.read_block(index)
            if request.kind == 'generator':
                self.source, self.frequency = request.source, request.frequency
            host.record({'kind': 'utility_completed', 'operation': request.kind,
                         'lock_verified': True, 'parameters_unchanged': request.kind!='lock',
                         'generator_value_readback': False,
                         'input_selection_readback':request.kind=='input_selection',
                         'password_redacted': request.kind in ('lock','unlock')})
            self.publish(self.state(operation=request.kind, completed=True))
            if request.kind == 'lock':
                # Vendor48D954 sends SET_LOCK followed by session-end11.
                # The normal session runner sends11 once on healthy stop.
                host.stop.set()
        except Exception:
            # Unknown result stays fail-stop; no repair, retry or secret output.
            if request.kind in ('input_selection','input_selection_read'):self.input_selection=None
            self.publish(self.state(error='Device operation stopped. Reconnect to check its state.'))
            raise
        finally:
            self.running = False
            self.secret_active = False
            self.publish(self.state())
