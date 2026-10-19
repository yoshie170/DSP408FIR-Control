from copy import deepcopy
from pathlib import Path
import math
import time
import json
from PySide6.QtCore import QObject,Signal,Slot,Property,QTimer
from PySide6.QtWidgets import QFileDialog
from dsp408.model import DeviceModel,FILTER_TYPES,CROSS_TYPES,FIR_WINDOWS,FIR_TYPES,DEQ_TYPES,DEQ_MODES,state_snapshot
from dsp408.editor_profile import FREQUENCY_MIN,FREQUENCY_MAX,DETECTOR_TYPES,RATIO_VALUES,Q_VALUES,DEQ_LIMITS,SINE_FREQUENCIES
from dsp408.editor_profile import FIR_HP_MIN,FIR_HP_MAX,FIR_LP_MIN,FIR_LP_MAX
from dsp408.fir import parse_coefficients
from dsp408.response import response,fir_response
from dsp408.dynamics import transfer_db,meter_position,METER_BREAKPOINTS
from dsp408.crossover import plot_data,intersections
from dsp408.delay import FACTORS, display_delay, delay_milliseconds,conversion_factors,sound_speed,checked_temperature,checked_air_conditions
from dsp408.wire_research import inspect_wire_file
from dsp408.overview import channel_summary
from dsp408.software_bypass import SoftwareBypass,SPECS
from dsp408.source_session import LocalSourceSession,SourceDocument,project_state
from dsp408.readback_audit import audit_readback
from dsp408.device_utilities import EditingLock, generator_request, lock_request, unlock_request,input_selection_request,input_selection_read_request

class Controller(QObject):
    @Property(QObject,constant=True)
    def information(self):return self._information
    @Property(str,constant=True)
    def applicationName(self):
        from dsp408.app_paths import application_name
        return application_name()
    @Property(str,constant=True)
    def applicationVersion(self):
        from dsp408.version import VERSION
        return VERSION

    changed=Signal()
    statusChanged=Signal()
    metersChanged=Signal()
    presetRecallStateChanged=Signal()
    prsReviewChanged=Signal()
    prsReviewReady=Signal()
    firImportReviewChanged=Signal()
    firImportReady=Signal()
    outputFirReviewChanged=Signal()
    outputFirReviewReady=Signal()
    bankBackupReady=Signal()
    bankRestoreReady=Signal()
    themeChanged=Signal()
    networkTargetChanged=Signal()
    meterPollChanged=Signal()
    dynamicsDisplayChanged=Signal()
    delayTemperatureChanged=Signal()
    def __init__(self,parent=None,*,preferences_path=None):
        super().__init__(parent);self.model=DeviceModel();self._selected=0;self._revision=0;self._message='DEMO / OFFLINE - no physical device communication';self._preset='Untitled';self._phase=False;self._meters=[0.0]*12;self.bank={};self._fir_cache=(None,[])
        self._pending_fir_action=None
        self._software_bypass=SoftwareBypass()
        self._output_fir_candidate=None;self._output_fir_review={}
        self._baseline=self.model.to_dict();self._dirty=False;self._active_slot=-1;self._slot_names={};self._previous_configuration=None
        self._fir_phase_cache=(None,[])
        self._usb_fir_coefficients_cache=(None,[])
        self._ethernet_fir_preview=None
        self._overview_fir_cache=(None,{})
        self._editing_lock=EditingLock();self._utility_state={};self._developer_tools=False
        from dsp408.preferences import Preferences
        self._preferences=Preferences(preferences_path);self._theme=self._preferences.theme()
        self._network_target=self._preferences.network_target()
        self._network_source_ip=self._preferences.network_source_ip();self._connection_transport='usb'
        self._meter_poll_ms=self._preferences.meter_poll_ms()
        self._dynamics_display=self._preferences.dynamics_display()
        self._ambient_temperature=self._preferences.ambient_temperature()
        self._delay_air=self._preferences.delay_air_conditions()
        from dsp408.application_info import ApplicationInfo
        self._information=ApplicationInfo(self,self._preferences)
        self._output_db=[-100.0]*12;self._peaks=[-100.0]*12;self._peak_hold=[0]*12
        self._peq_cache=(None,[],[])
        self._peq_compared=[];self._comparison_cache={};self._xover_compared=[];self._xover_curve_cache={}
        self._wire_summary='No local wire log loaded. Ethernet / USB not verified on hardware.'
        self._source_session=None;self._source_status='Local protocol test is stopped. No packets created at startup.'
        self._usb_worker=None;self._usb_status='USB read is stopped';self._usb_telemetry=None;self._usb_last=0.
        self._usb_offline=None;self._usb_raw_state=None;self._usb_issues=[];self._usb_journal=[];self._usb_total_frames=0
        self._usb_preset_metadata=None
        self._bank_backup_candidate=None;self._bank_backup_review={}
        self._bank_restore_candidate=None;self._bank_restore_review={}
        self._usb_fir_mode=False;self._usb_fir_bank=None;self._usb_fir_report=None;self._usb_fir_journal=''
        self._prs_review={}
        self._usb_prs_candidate=None
        self._usb_input_fir_candidate=None;self._fir_import_review={}
        self._usb_preview_mode=False;self._usb_preview=None;self._usb_preview_journal='';self._usb_preview_channels=[]
        self._usb_eeprom_mode=False
        self._usb_preset_trial_mode=False;self._usb_preset_trial_result=None;self._usb_preset_trial_journal=''
        self._usb_catalog_revision=0
        self._usb_coverage=None
        self._usb_gain_mode=False;self._usb_gain_ready=False;self._usb_gain_busy=False;self._usb_gain_journal=''
        self._usb_control_mode=False;self._usb_control_ready=False;self._usb_control_pending=False
        self._usb_control_generation=0;self._usb_control_journal=''
        self._usb_recall_progress={};self._usb_recall_result={}
        self._channel_views={};self._usb_confirmed_model=None
        self._control_refresh=QTimer(self);self._control_refresh.setSingleShot(True)
        self._control_refresh.setInterval(16);self._control_refresh.timeout.connect(self._publish_control_edit)
        self.timer=QTimer(self);self.timer.setInterval(100);self.timer.timeout.connect(self.update_meters)
        self.changed.connect(self.presetRecallStateChanged.emit)
        self.statusChanged.connect(self.presetRecallStateChanged.emit)
    def notify(self,message=None):
        self._software_bypass.reconcile(self.model)
        self._channel_views.clear()
        if message is not None:self._message=message
        if self._source_session is not None and self._source_session.active:
            self._source_session.observe(self.model.to_dict())
            last=self._source_session.latest
            if last:
                blocked=list(self._source_session.pending.values())
                self._source_status=f"LOCAL TEST · {self._source_session.total_packets} packets planned · latest batch {len(last['packets'])} packets, {len(blocked)} blocked fields"
                details=[f"{p['path']}: {p['reason']}" for p in blocked]
                if details:self._source_status+='\n'+'\n'.join(details[:6])
        self._dirty=self.model.to_dict()!=self._baseline
        self._revision+=1;self.changed.emit();self.statusChanged.emit()
    @Property(bool,notify=statusChanged)
    def dirty(self):return self._dirty
    @Property(int,notify=changed)
    def activeSlot(self):return self._active_slot
    @Property(bool,notify=changed)
    def canUndoSwitch(self):return self._previous_configuration is not None
    @Property(str,notify=changed)
    def previousConfigurationName(self):return self._previous_configuration[1] if self._previous_configuration else ''
    @Property('QVariantList',notify=changed)
    def configurations(self):
        return [{'slot':i,'name':self._slot_names.get(i,f'Config {i+1:02d}'),'stored':i in self.bank} for i in range(20)]
    @Property('QVariantList',notify=changed)
    def hardwarePresets(self):
        m=self._usb_preset_metadata
        if not self.usbReadActive or m is None:return []
        names=m.get('names_raw_hex',{});markers=m.get('catalog_markers',[])
        result=[]
        for index in range(19):
            raw=names.get(index,names.get(str(index)))
            if raw is None:continue
            try:name=bytes.fromhex(raw).split(b'\0',1)[0].decode('ascii').rstrip(' ')
            except UnicodeDecodeError:name='[encoding unverified]'
            result.append({'slot':index+1,'name':name or '[unnamed]',
                           'name_index':index,'name_raw_hex':raw,
                           'marker_raw':markers[index] if len(markers)==19 else None,
                           'stored':bool(markers[index]) if len(markers)==19 else None,
                           'active':m.get('active_slot_raw')==index+1})
        return result
    @Property(int,notify=changed)
    def usbCatalogRevision(self):return self._usb_catalog_revision
    @Property(int,notify=changed)
    def revision(self):return self._revision
    @Property(int,notify=changed)
    def selected(self):return self._selected
    @Property('QVariantMap',notify=changed)
    def current(self):return self.channel(self._selected)
    @Property(str,notify=statusChanged)
    def message(self):return self._message
    @Property(str,notify=statusChanged)
    def displayMessage(self):
        from dsp408.ui_status import display_status
        value=self._message if self.developerTools else display_status(self._message)
        return value.replace('USB','Ethernet') if self._connection_transport=='ethernet' else value
    @Property(str,notify=changed)
    def preset(self):return self._preset
    @Property('QVariantList',notify=metersChanged)
    def meters(self):return self._meters
    @Property('QVariantList',notify=metersChanged)
    def meterDb(self):return self._output_db[:]
    @Property('QVariantList',notify=metersChanged)
    def meterLabels(self):
        if not self.meterReadingsAvailable:return ['—']*12
        return [('—' if v.log_level_db is None else '−∞' if v.amplitude==0 or round(self._output_db[i],1)<-99 else f'{self._output_db[i]:.1f}')
                for i,v in enumerate(self._usb_telemetry.levels)]
    def _overview_fir_states(self):
        fir_states={}
        if self.usbReadActive and self._usb_raw_state is not None:
            preview=self._ethernet_fir_preview
            preview_key=None if preview is None else (preview['state_sha256'],tuple(
                (entry['count'],entry['status'],entry['coefficient_bytes_le_hex']) for entry in preview['inputs']))
            signature=(self._usb_raw_state,self._usb_fir_bank,preview_key)
            if self._overview_fir_cache[0]==signature:return self._overview_fir_cache[1]
            import struct
            rows=SourceDocument(self._usb_raw_state).decoded()['channels']
            for i in range(4):
                count=rows[i]['fir_coefficient_count_raw'];ready=False;empty=count==0
                if self._usb_fir_bank is not None:
                    empty=empty or self._usb_fir_bank[i*8192:i*8192+4]==b'\xff'*4
                elif self._ethernet_fir_preview is not None:
                    import hashlib
                    preview=self._ethernet_fir_preview
                    if preview['state_sha256']==hashlib.sha256(self._usb_raw_state).hexdigest():
                        entry=preview['inputs'][i]
                        empty=empty or (entry['count']==count and entry['status']=='empty_marker'
                                        and entry['coefficient_bytes_le_hex']=='ffffffff')
                if 1<=count<=2048:
                    if self._usb_fir_bank is not None:
                        raw=self._usb_fir_bank[i*8192:i*8192+count*4]
                        ready=len(raw)==count*4 and all(math.isfinite(v) for v in struct.unpack('<'+'f'*count,raw))
                    elif self._ethernet_fir_preview is not None:
                        from dsp408.fir_read_preview import coefficients
                        ready=len(coefficients(self._ethernet_fir_preview,self._usb_raw_state,i))==count
                fir_states[i]={'ready':ready,'count':count,'empty':empty}
            for i in range(4,12):
                row=rows[i];kind=row['fir_type_raw'];count=row['fir_tap_parameter_raw'];ready=kind in (1,2,3)
                if kind==4 and self._usb_fir_bank is not None and 1<=count<=1024:
                    raw=self._usb_fir_bank[(i+4)*4096:(i+4)*4096+count*4]
                    ready=len(raw)==count*4 and all(math.isfinite(v) for v in struct.unpack('<'+'f'*count,raw))
                fir_states[i]={'ready':ready,'count':count}
            self._overview_fir_cache=(signature,fir_states)
        else:self._overview_fir_cache=(None,{})
        return fir_states

    @Property('QVariantList',notify=changed)
    def channelSummaries(self):
        fir_states=self._overview_fir_states()
        return [channel_summary(self.model,i,self._software_bypass.entries,fir_states.get(i)) for i in range(12)]
    @Property('QVariantList',notify=metersChanged)
    def overviewActivity(self):
        return [{'db':self._output_db[i] if self.meterReadingsAvailable else -100.,
                 'peak':self._peaks[i] if self.meterReadingsAvailable else -100.,
                 'reduction':0.,'gateClosed':False,
                 'reducing':self._usb_reducing(i) if self.meterReadingsAvailable else False} for i in range(12)]
    @Property(bool,notify=metersChanged)
    def meterReadingsAvailable(self):return self.usbReadActive and self._usb_telemetry is not None
    @Property('QVariantList',notify=metersChanged)
    def meterPeaks(self):return [meter_position(db) for db in self._peaks]
    @Property('QVariantList',constant=True)
    def meterBreakpoints(self):return METER_BREAKPOINTS[:]
    @Property('QVariantMap',notify=metersChanged)
    def dspUsage(self):
        if self.usbReadActive and self._usb_telemetry is not None:
            return {'available':True,'percent':self._usb_telemetry.editor_dsp_percent,'source':self.connectionMedium+' RX40 · original editor formula'}
        return {'available':False,'percent':None,'source':'No verified hardware reading'}
    @Property(bool,notify=changed)
    def usbReadActive(self):return self._usb_worker is not None
    @Property(bool,notify=changed)
    def modelEditingAllowed(self):return not self.usbReadActive and not self.editingLocked
    @Property(bool,notify=changed)
    def usbControlMode(self):return self.usbReadActive and self._usb_control_mode
    @Property(bool,notify=changed)
    def usbControlReady(self):return self.usbControlMode and self.usbReadConnected and self._usb_control_ready and not self.usbPresetRecallBusy and not self.editingLocked and not self.utilityBusy

    @Property(bool,notify=changed)
    def developerTools(self):return self._developer_tools

    @Property(str,notify=themeChanged)
    def theme(self):return self._theme

    @Property(bool,notify=themeChanged)
    def lightTheme(self):return self._theme=='light'

    @Property('QVariantMap',notify=networkTargetChanged)
    def networkTarget(self):return self._network_target.copy()
    @Property(str,notify=networkTargetChanged)
    def networkSourceIp(self):return self._network_source_ip
    @Property(str,notify=changed)
    def connectionMedium(self):return 'Ethernet' if self._connection_transport=='ethernet' else 'USB'
    @Property(str,notify=changed)
    def activeTransport(self):return self._connection_transport if self.usbReadActive else 'offline'

    @Slot(str,int,str,result=bool)
    def ethernetTargetValid(self,ip,device_id,source_ip):
        from dsp408.connection_profile import ethernet_profile
        try:ethernet_profile(ip,device_id,source_ip,read=True);return True
        except (ValueError,TypeError):return False

    @Slot(str,int,str,result=bool)
    def setEthernetTarget(self,ip,device_id,source_ip):
        from dsp408.connection_profile import ethernet_profile
        try:
            target,source=ethernet_profile(ip,device_id,source_ip)
            self._preferences.save_network_connection(ip,device_id,source_ip)
        except (ValueError,TypeError,OSError) as error:
            self.notify('Cannot save Ethernet target: '+str(error));return False
        self._network_target=target;self._network_source_ip=source or '';self.networkTargetChanged.emit();return True

    @Slot(str,int,str,result=bool)
    def connectEthernetRead(self,ip,device_id,source_ip):
        return self._connect_ethernet(ip,device_id,source_ip,False)

    @Slot(str,int,str,result=bool)
    def connectEthernetControl(self,ip,device_id,source_ip):
        return self._connect_ethernet(ip,device_id,source_ip,True)

    def _connect_ethernet(self,ip,device_id,source_ip,control):
        if self.usbReadActive or self._editing_lock.locked:return False
        if not self.ethernetTargetValid(ip,device_id,source_ip):
            self.notify('Enter a DSP IPv4 address and ID1–250. Any PC address override must be valid and different.');return False
        if not self.setEthernetTarget(ip,device_id,source_ip):return False
        self._start_usb(False,control_mode=control,fir_mode=True,ethernet_profile=(self._network_target.copy(),self._network_source_ip or None))
        return self.usbReadActive

    @Property(int,notify=meterPollChanged)
    def meterPollMs(self):return self._meter_poll_ms

    @Property(bool,notify=dynamicsDisplayChanged)
    def dynamicsDisplayEnabled(self):return self._dynamics_display

    @Slot(bool,result=bool)
    def setDynamicsDisplay(self,value):
        try:self._preferences.save_dynamics_display(value)
        except (OSError,ValueError) as error:
            self._message='Cannot save display preference: '+str(error);self.statusChanged.emit();return False
        self._dynamics_display=value;self.dynamicsDisplayChanged.emit();return True

    @Slot(int,result=bool)
    def setMeterPollMs(self,value):
        try:self._preferences.save_meter_poll_ms(value)
        except (OSError,ValueError) as error:
            self._message=str(error);self.statusChanged.emit();return False
        self._meter_poll_ms=value
        setter=getattr(self._usb_worker,'set_meter_poll_ms',None)
        if setter is not None:setter(value)
        self.meterPollChanged.emit();return True

    @Slot(str,int,result=bool)
    def networkTargetValid(self,ip,device_id):
        from dsp408.connection_profile import target_profile
        try:target_profile(ip,device_id);return True
        except (ValueError,TypeError):return False

    @Slot(str,int,result=bool)
    def setNetworkTarget(self,ip,device_id):
        from dsp408.connection_profile import target_profile
        try:
            value=target_profile(ip,device_id);self._preferences.save_network_target(value)
        except (ValueError,TypeError,OSError) as error:
            self._message='Cannot save connection target: '+str(error);self.statusChanged.emit();return False
        self._network_target=value;self.networkTargetChanged.emit();return True

    @Slot(str,result=bool)
    def setTheme(self,value):
        if value not in ('dark','light'):return False
        if value==self._theme:return True
        try:self._preferences.save_theme(value)
        except OSError as error:
            self.notify('Could not save appearance preference: '+str(error));return False
        self._theme=value;self.themeChanged.emit();return True

    @Property(bool,notify=changed)
    def editingLocked(self):return self._editing_lock.locked or self.usbReadActive and bool(self._utility_state.get('locked'))

    @Property(bool,notify=changed)
    def processorLocked(self):return bool(self._utility_state.get('locked'))

    @Property(bool,notify=changed)
    def processorPasswordProtected(self):return bool(self._utility_state.get('password_protected'))

    @Property(bool,notify=changed)
    def utilityBusy(self):return bool(self._utility_state.get('busy'))

    @Property(bool,notify=changed)
    def utilitiesAvailable(self):
        return self.usbControlMode and (self.authenticationPending or self.usbReadConnected and self._usb_control_ready) and not self.usbPresetRecallBusy and not self.utilityBusy

    @Property(bool,notify=changed)
    def authenticationPending(self):
        return self.usbReadActive and self.usbControlMode and bool(self._utility_state.get('authentication_pending'))

    @Property(bool,notify=changed)
    def inputSelectionAvailable(self):
        return self.usbControlMode and self.usbReadConnected and self._usb_control_ready and not self.usbPresetRecallBusy and not self.utilityBusy

    @Property('QVariantMap',notify=changed)
    def generatorState(self):
        if self.usbReadActive:
            return {'source':self._utility_state.get('source'),'frequency':self._utility_state.get('frequency'),'known':self._utility_state.get('source') is not None}
        return {'source':self.model.settings['test_tone'],'frequency':self.model.settings['sine_hz'],'known':True}

    @Slot(object)
    def _utility_received(self,value):
        self._utility_state=dict(value)
        message=value.get('error')
        if value.get('completed'):
            message={'generator':'Signal source applied','lock':'Processor locked','unlock':'Processor unlocked',
                'input_selection':'Input source applied','input_selection_read':'Input source read',
                'device_settings_read':'Processor settings read','device_id':'Processor ID applied','device_ip':'Processor IP applied'}[value['operation']]
            if value['operation'] in ('device_id','device_ip'):
                raw=bytes.fromhex(value['device_settings_hex']);target={'ip':'.'.join(str(n) for n in raw[4:8]),'device_id':self._network_target['device_id']}
                try:self._preferences.save_network_target(target)
                except (OSError,ValueError) as error:message+=' · could not save connection target: '+str(error)
                self._network_target=target;self.networkTargetChanged.emit()
        self.notify(message)

    @Property('QVariantMap',notify=changed)
    def deviceSettings(self):
        raw=self._utility_state.get('device_settings_hex')
        if not raw or not self.usbReadConnected:return {'known':False,'writable':False,'id_writable':False}
        data=bytes.fromhex(raw)
        target=self._network_target['device_id']
        return {'known':True,'device_id':data[0],'connection_device_id':target,
                'stored_setting17':data[0],
                'writable':self._connection_transport=='usb','id_writable':False,
                'ip':'.'.join(str(n) for n in data[4:8])}

    @Slot(result=bool)
    def readDeviceSettings(self):
        from dsp408.device_utilities import device_settings_read_request
        return self._request_utility(device_settings_read_request())

    @Slot(str,'QVariant',str,result=bool)
    def applyDeviceSetting(self,kind,value,before_hex):
        if self.editingLocked:return False
        try:
            from dsp408.device_utilities import device_setting_request
            if kind=='device_id':raise ValueError('Stored setting17 is separate from the connection address; processor address changes are unavailable')
            if not self._utility_state.get('device_settings_hex') or before_hex!=self._utility_state['device_settings_hex']:raise ValueError('Read processor settings before applying')
            if kind=='device_ip' and self._connection_transport!='usb':raise ValueError('Change the processor IP over USB')
            request=device_setting_request(kind,value,bytes.fromhex(before_hex))
            if kind=='device_ip' and request.device_ip==self.deviceSettings.get('ip'):
                raise ValueError('The processor already uses this IP address')
            return self._request_utility(request)
        except (ValueError,TypeError) as error:self.notify(str(error));return False

    @Property(str,notify=changed)
    def deviceSettingsRaw(self):return self._utility_state.get('device_settings_hex') or ''

    def _request_utility(self,request):
        if self.authenticationPending and request.kind!='unlock':return False
        available=self.inputSelectionAvailable if request.kind in ('input_selection','input_selection_read') else self.utilitiesAvailable
        if not available:return False
        if not self._usb_worker.request_utility(request):
            self.notify('Wait until the current settings have finished applying.');return False
        self._utility_state={**self._utility_state,'busy':True};self.notify('Applying device settings…');return True

    @Slot(str,float,result=bool)
    def applyGenerator(self,source,frequency):
        if self.editingLocked:return False
        try:
            request=generator_request(source,frequency)
            if self.usbReadActive:return self._request_utility(request)
            self.model.settings['test_tone']=source;self.model.settings['sine_hz']=frequency
            self.notify('Signal source selected · DEMO');return True
        except ValueError as error:self.notify(str(error));return False

    @Property('QVariantMap',notify=changed)
    def inputSelectionState(self):
        source=self._utility_state.get('input_selection') if self.usbReadActive else self.model.settings['input_select']
        return {'source':source,'known':source is not None}

    @Slot(result=bool)
    def readInputSelection(self):return self._request_utility(input_selection_read_request())

    @Slot(str,result=bool)
    def applyInputSelection(self,source):
        if self.editingLocked:return False
        try:
            request=input_selection_request(source)
            if self.usbReadActive:return self._request_utility(request)
            self.model.settings['input_select']=source;self.notify('Input source selected · DEMO');return True
        except ValueError as error:self.notify(str(error));return False

    @Slot(str,result=bool)
    def lockEditing(self,password):
        if self.editingLocked:return False
        try:
            request=lock_request(password)
            if self.usbReadActive:return self._request_utility(request)
            self._editing_lock.lock(password);self.notify('Editing locked · DEMO');return True
        except ValueError as error:self.notify(str(error));return False

    @Slot(str,result=bool)
    @Slot(str,str,result=bool)
    def unlockEditing(self,password,mode='permanent'):
        try:
            request=unlock_request(password,mode)
            if self.usbReadActive:return self._request_utility(request)
            if not self._editing_lock.unlock(password):self.notify('Incorrect password.');return False
            self.notify('Editing unlocked · DEMO');return True
        except ValueError as error:self.notify(str(error));return False
    @Property(bool,notify=presetRecallStateChanged)
    def usbPresetRecallBusy(self):return self.usbReadActive and bool(self._usb_recall_progress.get('busy'))
    @Property(bool,notify=presetRecallStateChanged)
    def presetRecallAvailable(self):
        return self.usbControlMode and self.usbReadConnected and not self.usbPresetRecallBusy and not self._usb_control_pending and not self.editingLocked and not self.utilityBusy
    @Property(bool,notify=presetRecallStateChanged)
    def usbPresetRecallAvailable(self):
        # Legacy API name; both transports have typed transaction ports.
        return self.presetRecallAvailable
    @Property(bool,constant=True)
    def usbPresetStoreAuthorized(self):
        from dsp408.preset_store import PRESET_STORE_AUTHORIZED
        return PRESET_STORE_AUTHORIZED
    @Property(bool,notify=presetRecallStateChanged)
    def usbPresetStoreAvailable(self):return self.usbPresetStoreAuthorized and self.usbPresetRecallAvailable
    @Property(str,notify=changed)
    def usbCurrentPresetName(self):
        if self._usb_raw_state is None:return ''
        try:return self._usb_raw_state[2:16].split(b'\0',1)[0].decode('ascii').rstrip(' ')
        except UnicodeDecodeError:return ''
    @Slot(int,str,int,str,result=bool)
    def requestUsbPresetStore(self,slot,name,marker,name_hex):
        if not self.usbPresetStoreAuthorized:
            from dsp408.preset_store import BLOCK_REASON
            self.notify(BLOCK_REASON);return False
        if not self.usbPresetStoreAvailable:return False
        try:
            from dsp408.preset_store import encode_name
            from dsp408.preset_recall import checked_slot
            checked_slot(slot);encode_name(name)
            if not self._usb_worker.request_store(slot,name,{'marker':marker,'name_hex':name_hex}):return False
        except (ValueError,AttributeError) as error:self.notify(str(error));return False
        self._usb_recall_progress={'busy':True,'operation':'store','slot':slot,'stage':'Preparing preset Store',
                                   'done':0,'total':168,'waiting':True}
        self._usb_telemetry=None;self._clear_usb_meters();self.notify(f'Saving P{slot:02d} · settings locked until readback completes')
        return True
    @Property('QVariantMap',notify=presetRecallStateChanged)
    def usbPresetRecallProgress(self):return self._usb_recall_progress
    @Property(str,notify=presetRecallStateChanged)
    def usbOperationStage(self):
        from dsp408.ui_status import operation_status
        stage=self._usb_recall_progress.get('stage','')
        return stage if self.developerTools else operation_status(stage)
    @Property(str,notify=presetRecallStateChanged)
    def usbOperationPhase(self):
        from dsp408.ui_status import operation_status
        stage=self._usb_recall_progress.get('operation_phase','')
        return stage if self.developerTools else operation_status(stage)
    @Slot(int,result=bool)
    def requestUsbPresetRecall(self,slot):
        if not self.presetRecallAvailable:return False
        entries=[entry for entry in self.hardwarePresets if entry['slot']==slot and entry['marker_raw']==255]
        if not entries:self.notify('Choose a stored P01–P19 preset; empty/default slots cannot be loaded');return False
        try:
            if not self._usb_worker.request_recall(slot):
                self.notify('Wait for pending channel changes to finish before loading a preset');return False
        except (ValueError,AttributeError) as error:self.notify(str(error));return False
        # Recall may replace FIR even when ordinary parameter bytes are identical.
        # Never retain the prior preset's partial response or raw bank as current.
        self._ethernet_fir_preview=None;self._usb_fir_bank=None;self._usb_fir_report=None;self._fir_cache=(None,[])
        self._usb_recall_progress={'busy':True,'slot':slot,'stage':'Preparing preset recall',
                                   'done':0,'total':70,'waiting':True}
        self._usb_telemetry=None;self._clear_usb_meters();self.notify(f'Loading P{slot:02d} · settings locked until readback completes')
        return True
    @Slot(object)
    def _usb_recall_progress_received(self,value):
        was_busy=self.usbPresetRecallBusy
        self._usb_recall_progress=dict(value)
        if was_busy!=self.usbPresetRecallBusy:self.changed.emit()
        else:self.presetRecallStateChanged.emit()
    @Slot(object)
    def _usb_recall_result_received(self,value):
        self._usb_recall_result=value;self._usb_recall_progress={**self._usb_recall_progress,'busy':False,'waiting':False}
        if value.get('operation')=='fir_read':
            action=self._pending_fir_action;self._pending_fir_action=None
            self.notify('FIR storage read')
            if action is not None:
                channel,state,kind,args=action
                if channel!=self._selected or state!=self._usb_raw_state:
                    self.notify('DSP or selected channel changed; review FIR again');return
                if kind=='bypass':self.requestUsbFirBypass(*args)
                elif kind=='overview_bypass':self._request_channel_fir_bypass(*args)
                elif kind=='output_design':
                    if self.reviewOutputFir(*args):self.outputFirReviewReady.emit()
                elif kind=='channel_link':self.reviewChannelLink(*args)
                elif kind=='prs_import':
                    if self.previewPrsImportPath(*args):self.prsReviewReady.emit()
                elif kind=='prs_export':self.exportUsbPrsPath(*args)
                elif kind=='bank_backup':
                    if self.previewBankBackupPath(*args):self.bankBackupReady.emit()
                elif kind=='bank_restore':
                    if self.previewBankRestorePath(*args):self.bankRestoreReady.emit()
                elif self._review_input_fir(*args):self.firImportReady.emit()
            return
        if value.get('operation')=='bank_backup':
            self.notify('Preset bank backup saved · '+str(len(value['stored_slots']))+' stored presets · '+value['path']);return
        if value.get('operation')=='bank_restore':
            self.notify('Preset bank restored · current configuration unchanged · backup: '+value['backup_path']);return
        self._usb_fir_bank=None;self._usb_fir_report=None;self._fir_cache=(None,[])
        if value.get('operation') in ('fir_import','output_fir','channel_link') or value.get('full_prs'):
            if value.get('bank_hex') is not None:self._usb_fir_received(bytes.fromhex(value['bank_hex']))
            if value.get('full_prs'):
                self.notify('PRS configuration and FIR imported · full readback verified');return
            if value['operation']=='channel_link':
                self._ethernet_fir_preview=None
                self.notify('Channel Link applied · parameters checked; FIR handled by DSP');return
            if value['operation']=='output_fir':
                self.notify('Output FIR crossover applied · full parameters and storage verified');return
            self.notify('Input FIR cleared · bypass on · full storage verified' if value.get('clear') else 'Input FIR applied · full storage, parameters and final Mute verified');return
        self.notify('IN A identity FIR256 loaded · full storage and parameters verified' if value.get('operation')=='fir_trial' else 'PRS parameters imported · unchanged FIR and final Mute verified' if value.get('operation')=='prs_import' else f"P{value['slot']:02d} "+('saved' if value.get('operation')=='store' else 'loaded')+' · full parameter readback verified')
    @Property(bool,notify=changed)
    def parameterEditingAllowed(self):return self.modelEditingAllowed or self.usbControlReady
    @Property(bool,notify=statusChanged)
    def usbControlPending(self):return self.usbControlMode and self._usb_control_pending
    @Property('QVariantMap',notify=statusChanged)
    def usbConfirmedCurrent(self):
        return state_snapshot(self._usb_confirmed_model.channels[self._selected]) if self.usbControlMode and self._usb_confirmed_model is not None else {}
    @Property(str,notify=changed)
    def usbControlJournal(self):return self._usb_control_journal
    @Property(bool,notify=changed)
    def usbGainMode(self):return self.usbReadActive and self._usb_gain_mode
    @Property(bool,notify=changed)
    def usbGainReady(self):return not self.editingLocked and self.usbGainMode and self.usbReadConnected and self._usb_gain_ready and not self._usb_gain_busy
    @Property(bool,notify=changed)
    def usbGainBusy(self):return self.usbGainMode and self._usb_gain_busy
    @Property(str,notify=changed)
    def usbGainJournal(self):return self._usb_gain_journal
    @Slot(int,result=bool)
    def gainEditingAllowed(self,index):return self.parameterEditingAllowed or index==0 and self.usbGainReady
    @Property(str,notify=statusChanged)
    def usbStatus(self):return self._usb_status
    @Property(bool,notify=changed)
    def usbReadbackAvailable(self):return self._usb_raw_state is not None
    @Property(str,notify=changed)
    def usbWarnings(self):
        prefix=f'{len(self._usb_issues)} values outside UI representation retained in raw export.' if self._usb_issues else 'Supported channel values loaded without projection errors.'
        fir='Stored input FIR available; audio response unmeasured.' if self._usb_fir_bank is not None else 'Read-only input FIR preview; raw bank is incomplete.' if self._ethernet_fir_preview is not None else 'Active FIR coefficients not read.'
        return prefix+' Analog/AES and generator state unavailable. '+fir+' Link masks are diagnostic only.'
    @Property(str,notify=changed)
    def usbLinkSummary(self):
        if not self.usbReadActive or self._usb_coverage is None:return 'USB Link state unavailable'
        r=self._usb_coverage['link_resolutions'][self._selected]
        label=f"Raw 0x{r['stored_mask_raw']:04X}"
        if not r['topology_unambiguous']:return label+' · unresolved topology'
        names=[('IN '+chr(65+i)) if i<4 else ('OUT '+str(i-3)) for i in r['members']]
        return label+' · '+(' + '.join(names) if r['source_grouped'] else 'no group')+' · read only'
    @Property(str,notify=changed)
    def connectionLabel(self):
        if self.usbReadActive:
            if self.authenticationPending:return ('Ethernet' if self._connection_transport=='ethernet' else 'USB')+' · LOCKED'
            if self._connection_transport=='ethernet':
                if self._usb_status.startswith('USB read failed:'):return 'ETHERNET · ERROR'
                if self._usb_status=='Closing USB read':return 'DISCONNECTING · ETHERNET'
                if not self.usbReadConnected:return 'CONNECTING · ETHERNET'
                if self.usbControlMode:return 'CONNECTED · ETHERNET · CONTROL' if self.usbControlReady else 'CONNECTED · ETHERNET · CONTROL LOCKED'
                return 'CONNECTED · ETHERNET · READ ONLY'
            if self._usb_status.startswith('USB read failed:'):return 'USB · ERROR'
            if self._usb_status=='Closing USB read':return 'DISCONNECTING · USB'
            if not self.usbReadConnected:return 'CONNECTING · USB'
            if self.usbPresetTrialMode:return 'CONNECTED · USB · P19 PRESET TRIAL'
            if self.usbEepromReadMode:return 'CONNECTED · USB · P02 EEPROM'
            if self.usbPresetPreviewMode:return 'CONNECTED · USB · P02 PREVIEW'
            if self.usbFirMode:return 'CONNECTED · USB · FIR READ ONLY'
            if self.usbControlMode:return 'CONNECTED · USB · CONTROL' if self.usbControlReady else 'CONNECTED · USB · CONTROL LOCKED'
            return ('CONNECTED · USB · IN A GAIN' if self._usb_gain_ready else 'CONNECTED · USB · GAIN LOCKED') if self.usbGainMode else 'CONNECTED · USB · READ ONLY'
        return 'LOCAL PROTOCOL TEST' if self.localProtocolActive else 'DEMO / OFFLINE'
    @Property(bool,notify=changed)
    def usbReadConnected(self):
        return self.usbReadActive and self._usb_raw_state is not None and not self._usb_status.startswith('USB read failed:') and self._usb_status!='Closing USB read'
    @Property(bool,notify=changed)
    def usbConnectionBusy(self):
        return self.usbReadActive and not self.authenticationPending and self._usb_raw_state is None and not self._usb_status.startswith('USB read failed:') and self._usb_status!='Closing USB read'
    @Property(str,notify=statusChanged)
    def usbConnectionStage(self):return self._usb_status
    @Property(str,notify=statusChanged)
    def connectionError(self):
        prefix='USB read failed: '
        return self._usb_status[len(prefix):] if self._usb_status.startswith(prefix) else ''
    @Property(str,notify=statusChanged)
    def usbConnectionDisplayStage(self):
        from dsp408.ui_status import display_status
        value=self._usb_status if self.developerTools else display_status(self._usb_status)
        return value.replace('USB','Ethernet') if self._connection_transport=='ethernet' else value
    @Property(str,notify=changed)
    def meterSource(self):return self.connectionMedium+' · editor scale' if self.usbReadActive else 'OFFLINE'
    def _usb_reducing(self,index):
        value=self._usb_telemetry
        return bool(value and (value.input_compressor_bits[index] if index<4 else value.output_limiter_bits[index-4]))
    @Slot()
    def connectUsbRead(self):
        self._start_usb(False)
    @Slot()
    def connectUsbGain(self):
        self._start_usb(True)
    @Slot()
    def connectUsbControl(self):
        self._start_usb(False,True)
    @Slot()
    def connectUsbFirRead(self):
        self._start_usb(False,fir_mode=True)
    @Slot()
    def connectUsbPresetPreview(self):
        from dsp408.preset_preview import LIVE_PREVIEW_BLOCK_REASON
        self._usb_status=LIVE_PREVIEW_BLOCK_REASON;self.notify(LIVE_PREVIEW_BLOCK_REASON)
    @Slot()
    def connectUsbEepromRead(self):
        self._start_usb(False,eeprom_mode=True)
    @Property(bool,constant=True)
    def usbPresetTrialAvailable(self):
        from dsp408.usb_preset_roundtrip import PRESET_ROUNDTRIP_AUTHORIZED
        return PRESET_ROUNDTRIP_AUTHORIZED
    @Property(str,constant=True)
    def usbPresetTrialBlockReason(self):
        from dsp408.usb_preset_roundtrip import BLOCK_REASON
        return BLOCK_REASON
    @Property(bool,notify=changed)
    def usbPresetTrialMode(self):return self.usbReadActive and self._usb_preset_trial_mode
    @Property('QVariantMap',notify=changed)
    def usbPresetTrialResult(self):return self._usb_preset_trial_result or {}
    @Property(str,notify=changed)
    def usbPresetTrialJournal(self):return self._usb_preset_trial_journal
    @Slot()
    def connectUsbPresetTrial(self):self._start_usb(False,preset_trial_mode=True)
    @Slot(object)
    def _usb_preset_trial_received(self,value):self._usb_preset_trial_result=value;self.notify('P19 preset roundtrip complete; P02 active')
    @Slot(str)
    def _usb_preset_trial_journal_received(self,path):self._usb_preset_trial_journal=path;self.changed.emit()
    def _start_usb(self,gain_mode,control_mode=False,fir_mode=False,preset_mode=False,eeprom_mode=False,preset_trial_mode=False,ethernet_profile=None):
        if self.processorLocked and (gain_mode or preset_trial_mode):
            self.notify('Connect USB control to unlock the processor.');return
        if preset_mode:
            self.connectUsbPresetPreview();return
        if eeprom_mode and not self.usbEepromReadAvailable:
            self._usb_status=self.usbEepromReadBlockReason;self.notify(self._usb_status);return
        if preset_trial_mode and not self.usbPresetTrialAvailable:
            self._usb_status=self.usbPresetTrialBlockReason;self.notify(self._usb_status);return
        if self.usbReadActive:return
        if self._editing_lock.locked:self.notify('Unlock offline editing before connecting.');return
        self._utility_state={'locked':self._utility_state.get('locked',False)}
        self._usb_fir_trial_candidate=None;self._usb_prs_candidate=None;self._prs_review={};self.prsReviewChanged.emit()
        if ethernet_profile is not None:
            if control_mode:
                from dsp408.ethernet_control import EthernetControlWorker as EthernetWorker
            else:
                from dsp408.ethernet_worker import EthernetReadWorker as EthernetWorker
            target,source=ethernet_profile
            worker=EthernetWorker(target['ip'],source,self,poll_ms=self._meter_poll_ms,fir_strategy='source-display')
            worker.device_id=target['device_id']
        elif preset_trial_mode:
            from dsp408.usb_preset_roundtrip import UsbPresetRoundtripWorker
            worker=UsbPresetRoundtripWorker(self)
        elif eeprom_mode:
            from dsp408.usb_eeprom_read import UsbEepromReadWorker
            worker=UsbEepromReadWorker(self)
        elif fir_mode:
            from dsp408.usb_fir_read import UsbFirReadWorker
            worker=UsbFirReadWorker(self)
        elif control_mode:
            from dsp408.usb_parameter_control import UsbParameterWorker
            worker=UsbParameterWorker(self);worker.device_id=self._network_target['device_id']
            worker.set_meter_poll_ms(self._meter_poll_ms)
        elif gain_mode:
            from dsp408.usb_gain_control import UsbGainWorker
            worker=UsbGainWorker(self)
        else:
            from dsp408.usb_read import UsbReadWorker
            worker=UsbReadWorker(self);worker.device_id=self._network_target['device_id']
            worker.set_meter_poll_ms(self._meter_poll_ms)
        self._connection_transport='ethernet' if ethernet_profile is not None else 'usb'
        self._software_bypass.clear()
        self._pending_fir_action=None
        self._ethernet_fir_preview=None
        self._usb_gain_mode=gain_mode;self._usb_gain_ready=False;self._usb_gain_busy=False;self._usb_gain_journal=''
        self._usb_control_mode=control_mode;self._usb_control_ready=False;self._usb_control_pending=False
        self._usb_control_generation=0;self._usb_control_journal=''
        self._usb_recall_progress={};self._usb_recall_result={}
        self._usb_fir_mode=fir_mode;self._usb_fir_bank=None;self._usb_fir_report=None;self._usb_fir_journal=''
        self._usb_preview_mode=eeprom_mode;self._usb_preview=None;self._usb_preview_journal='';self._usb_preview_channels=[]
        self._usb_eeprom_mode=eeprom_mode
        self._usb_offline=(self.model.to_dict(),self._preset,self._active_slot,self._baseline)
        if self._source_session is not None:self._source_session.active=False
        self._source_status='Local test stopped for USB read; existing journal retained.'
        self._usb_telemetry=None;self._usb_raw_state=None;self._usb_journal=[];self._usb_total_frames=0;self._usb_issues=[]
        self._usb_preset_metadata=None
        self._usb_coverage=None
        self._usb_status='Starting '+self.connectionMedium+' read';self._clear_usb_meters()
        self._usb_worker=worker
        self.timer.start()
        self._usb_preset_trial_mode=preset_trial_mode
        if preset_trial_mode:self._usb_preset_trial_result=None;self._usb_preset_trial_journal=''
        worker.status.connect(self._usb_status_changed);worker.configuration.connect(self._usb_configuration)
        worker.presetMetadata.connect(self._usb_preset_metadata_received)
        worker.telemetry.connect(self._usb_receive_telemetry);worker.frameObserved.connect(self._usb_log)
        worker.failed.connect(self._usb_failed);worker.finished.connect(self._usb_finished)
        if fir_mode:
            worker.firBank.connect(self._usb_fir_received);worker.journalPath.connect(self._usb_fir_journal_received)
        if hasattr(worker,'firPreview'):worker.firPreview.connect(self._ethernet_fir_preview_received)
        if not control_mode and not fir_mode and hasattr(worker,'firBank'):worker.firBank.connect(self._usb_fir_received)
        if eeprom_mode:
            worker.journalPath.connect(self._usb_eeprom_journal_received);worker.snapshot.connect(self._usb_preview_received)
        if preset_trial_mode:
            worker.journalPath.connect(self._usb_preset_trial_journal_received);worker.result.connect(self._usb_preset_trial_received)
        if gain_mode:
            worker.gainAvailable.connect(self._usb_gain_available)
            worker.gainBusy.connect(self._usb_gain_busy_changed)
            worker.journalPath.connect(self._usb_gain_journal_received)
        if control_mode:
            if not fir_mode:worker.firBank.connect(self._usb_fir_received)
            worker.available.connect(self._usb_control_available)
            worker.pending.connect(self._usb_control_pending_changed)
            worker.confirmed.connect(self._usb_control_confirmed)
            worker.journalPath.connect(self._usb_control_journal_received)
            worker.recallProgress.connect(self._usb_recall_progress_received)
            worker.recallResult.connect(self._usb_recall_result_received)
            signal=getattr(worker,'utilityState',None)
            if signal is not None:signal.connect(self._utility_received)
        self.notify(('Ethernet Control requested · channel parameters' if control_mode else 'Ethernet read requested · direct PC–DSP · no settings written') if ethernet_profile is not None else 'Manual P19 preset trial requested; fresh checks precede every mutation.' if preset_trial_mode else 'USB Control requested · channel parameters and confirmed preset Recall; no Store, FIR uploads or grouped writes.' if control_mode else 'USB requested · only IN A -1/0 dB may be written after fresh readback; all other writes disabled.' if gain_mode else 'USB read requested. Parameter writes, presets and FIR upload disabled.');worker.start()
    @Slot(bool)
    def _usb_control_available(self,value):self._usb_control_ready=value;self.changed.emit()
    @Slot(bool)
    def _usb_control_pending_changed(self,value):
        # A delayed older verification must not clear a newer UI request.
        if value and not self._usb_control_pending:
            self._usb_control_pending=True;self.statusChanged.emit()
    @Slot(str)
    def _usb_control_journal_received(self,value):self._usb_control_journal=value;self._usb_fir_journal=value;self.changed.emit()
    @Slot(bytes,int)
    def _usb_control_confirmed(self,data,generation):
        if self._ethernet_fir_preview is not None:
            from dsp408.fir_read_preview import advance_preview
            self._ethernet_fir_preview=advance_preview(self._ethernet_fir_preview,self._usb_raw_state,bytes(data),allow_input_bypass=True)
        self._usb_raw_state=bytes(data)
        model,issues=project_state(SourceDocument(data),DeviceModel().to_dict(),strict=False)
        self._usb_confirmed_model=model
        if generation!=self._usb_control_generation:
            self.statusChanged.emit();return
        # The editor owns continuous user intent. A quantized background
        # readback must never replace controls or their in-progress gesture.
        # Keep the confirmed device representation separately and expose it.
        self._usb_confirmed_model=model;self._usb_issues=issues;self._usb_control_pending=False
        self._baseline=self.model.to_dict();self._dirty=False
        self._message=self.connectionMedium+' · settings verified at device resolution'
        self.statusChanged.emit()
    def _control_edit(self,change):
        if not self.usbControlReady:return False
        try:
            clone=deepcopy(self.model);change(clone);clone.validate()
            generation=self._usb_control_generation+1
            wanted=clone.to_dict()
            if wanted==self.model.to_dict():return True
            if not self._usb_worker.request_model(wanted,generation):return False
            self._usb_control_generation=generation;self._usb_control_pending=True
            self.model=clone
            self._software_bypass.reconcile(self.model)
            self._channel_views.clear();self._dirty=wanted!=self._baseline
            self._message='USB · requested value · background readback pending'
            # Native handles own the gesture immediately; data bindings update
            # once per UI frame, rather than rebuilding during every mouse event.
            if not self._control_refresh.isActive():self._control_refresh.start()
            return True
        except (ValueError,TypeError,AttributeError,IndexError,KeyError) as error:
            self.notify(str(error));return False
    def _publish_control_edit(self):
        if self.usbControlMode:self.notify()
    @Slot()
    def flushControlView(self):
        if self._control_refresh.isActive():
            self._control_refresh.stop();self._publish_control_edit()
    @Slot(bool)
    def _usb_gain_available(self,value):self._usb_gain_ready=value;self.changed.emit()
    @Slot(bool)
    def _usb_gain_busy_changed(self,value):self._usb_gain_busy=value;self.changed.emit()
    @Slot(str)
    def _usb_gain_journal_received(self,value):self._usb_gain_journal=value;self.changed.emit()
    @Slot(float,result=bool)
    def requestUsbGain(self,value):
        if not self.usbGainReady:return False
        try:
            from dsp408.usb_gain_control import target_frame
            target_frame(value)
            if not self._usb_worker.request_gain(value):return False
        except (ValueError,TypeError) as error:
            self.notify(str(error));return False
        self._usb_gain_busy=True
        self.notify(f'IN A {value:.1f} dB requested · awaiting full DSP readback')
        return True
    @Slot()
    def disconnectUsbRead(self):
        if self._usb_worker is not None:
            self._usb_worker.stop();self._usb_status='Closing USB read';self.changed.emit();self.statusChanged.emit()
    def shutdown(self):
        if self._usb_worker is not None:
            self._usb_worker.stop()
            # Worker reads have100ms timeout; Windows HID writes are bounded by HIDAPI.
            self._usb_worker.wait()
    @Slot(str)
    def _usb_status_changed(self,value):
        before=(self.usbReadConnected,self.usbConnectionBusy,self.connectionLabel)
        self._usb_status=value;self._message=value
        # Progress text does not edit the model, dirty state or chart revision.
        # Connection transitions still notify every dependent editing guard.
        after=(self.usbReadConnected,self.usbConnectionBusy,self.connectionLabel)
        if before!=after:self.changed.emit()
        self.statusChanged.emit()
    @Slot(object)
    def _usb_preset_metadata_received(self,value):
        if 'name_index' in value:
            previous=self._usb_preset_metadata or {}
            value={**previous,**value,'names_raw_hex':{**previous.get('names_raw_hex',{}),value['name_index']:value['name_raw_hex']}}
        self._usb_preset_metadata=value
        self._usb_catalog_revision+=1
        self.changed.emit()
    @Slot(bytes)
    def _usb_fir_received(self,raw):
        from dsp408.fir_bank import describe_bank
        try:report=describe_bank(raw)
        except ValueError as error:
            self._usb_failed(str(error))
            if self._usb_worker is not None:self._usb_worker.stop()
            return
        self._usb_fir_bank=bytes(raw);self._usb_fir_report=report
        self._ethernet_fir_preview=None
        self.notify('Full FIR storage bank received · 65536 bytes · no coefficient or preset writes')
    @Slot(object)
    def _ethernet_fir_preview_received(self,value):
        if not self.usbReadActive:return
        # Kept separately: this must never satisfy a complete-bank write guard.
        from copy import deepcopy
        self._ethernet_fir_preview=deepcopy(value);self.changed.emit()
    @Property('QVariantMap',notify=changed)
    def ethernetFirPreview(self):
        from copy import deepcopy
        return deepcopy(self._ethernet_fir_preview) if self._ethernet_fir_preview is not None else {}
    @Slot(str)
    def _usb_fir_journal_received(self,path):self._usb_fir_journal=path;self.changed.emit()
    @Property(bool,notify=changed)
    def usbFirMode(self):return self.usbReadActive and self._usb_fir_mode
    @Property(str,notify=changed)
    def usbFirJournal(self):return self._usb_fir_journal
    @Property('QVariantMap',notify=changed)
    def usbFirReport(self):return self._usb_fir_report or {}
    @Property(str,notify=changed)
    def usbFirSummary(self):
        if self._ethernet_fir_preview is not None:return 'Input FIR preview · received coefficients · partial storage read'
        r=self._usb_fir_report
        if not r:return 'Full FIR bank not read · no coefficients reconstructed'
        ch=r['channels'][self._selected]
        return f"FIR bank read: 65536 bytes · channel storage {ch['capacity']} words · {ch['sentinel_words']} FFFFFFFF markers · {ch['other_nonfinite_words']} other nonfinite words · audio application unverified"
    @Slot(object)
    def _usb_preview_received(self,snapshot):
        if snapshot.get('slot')!=2 or snapshot.get('complete') is not True or snapshot.get('current_state_unchanged') is not True:
            self._usb_failed('Invalid P02 preview result');return
        document=SourceDocument(bytes.fromhex(snapshot['state_hex']),'common-prefix1556',origin='Stored P02 read preview')
        model,issues=project_state(document,DeviceModel().to_dict(),strict=False)
        self._usb_preview_channels=[] if issues else [
            {'channel':('IN '+chr(65+i)) if i<4 else 'OUT '+str(i-3),'name':c.name,
             'gain':c.gain,'mute':c.mute,'delay_ms':c.delay_ms,
             'enabled_peq':sum(f.enabled for f in c.filters)} for i,c in enumerate(model.channels)]
        snapshot={**snapshot,'projection_issues':issues}
        self._usb_preview=snapshot
        self.notify('Stored P02 read · current state and active preset unchanged · no Recall/Store')
    @Slot(str)
    def _usb_preview_journal_received(self,path):self._usb_preview_journal=path;self._usb_fir_journal=path;self.changed.emit()
    @Slot(str)
    def _usb_eeprom_journal_received(self,path):self._usb_preview_journal=path;self.changed.emit()
    @Property(bool,notify=changed)
    def usbEepromReadMode(self):return self.usbReadActive and self._usb_eeprom_mode
    @Property(bool,constant=True)
    def usbEepromReadAvailable(self):
        from dsp408.usb_eeprom_read import EEPROM_READ_AUTHORIZED
        return EEPROM_READ_AUTHORIZED
    @Property(str,constant=True)
    def usbEepromReadBlockReason(self):
        from dsp408.usb_eeprom_read import BLOCK_REASON
        return BLOCK_REASON
    @Property(bool,notify=changed)
    def usbPresetPreviewMode(self):return self.usbReadActive and self._usb_preview_mode
    @Property(bool,constant=True)
    def usbPresetPreviewAvailable(self):return False
    @Property(str,constant=True)
    def usbPresetPreviewBlockReason(self):
        from dsp408.preset_preview import LIVE_PREVIEW_BLOCK_REASON
        return LIVE_PREVIEW_BLOCK_REASON
    @Property('QVariantMap',notify=changed)
    def usbPresetPreview(self):return self._usb_preview or {}
    @Property('QVariantList',notify=changed)
    def usbPresetPreviewChannels(self):return self._usb_preview_channels
    @Property(str,notify=changed)
    def usbPresetPreviewJournal(self):return self._usb_preview_journal
    @Slot(str,result=bool)
    def exportUsbPresetPreviewPath(self,path):
        if self._usb_preview is None:return False
        try:
            target=Path(path);temp=target.with_name(target.name+'.tmp')
            report={**self._usb_preview,'journal_path':self._usb_preview_journal}
            try:temp.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8');temp.replace(target)
            finally:temp.unlink(missing_ok=True)
            self.notify('Stored P02 raw preview exported locally · active state unchanged');return True
        except (ValueError,OSError) as error:self.notify(str(error));return False
    @Slot()
    def exportUsbPresetPreview(self):
        path,_=QFileDialog.getSaveFileName(None,'Export stored P02 preview','DSP408-P02-preview.json','JSON (*.json)')
        if path:self.exportUsbPresetPreviewPath(path if path.lower().endswith('.json') else path+'.json')
    @Slot(bytes)
    def _usb_configuration(self,data):
        self._bank_restore_candidate=None;self._bank_restore_review={}
        self._bank_backup_candidate=None;self._bank_backup_review={}
        self._channel_link_candidate=None;self._channel_link_review={}
        try:
            document=SourceDocument(data,'common-prefix1556',origin=self.connectionMedium+' read · FIR408 V0115P')
            # Never display offline FIR coefficients/globals as USB readings.
            model,issues=project_state(document,DeviceModel().to_dict())
        except ValueError as e:
            self._usb_failed(str(e))
            if self._usb_worker is not None:self._usb_worker.stop()
            return
        self._software_bypass.clear()
        self.model=model;self._usb_raw_state=bytes(data);self._usb_issues=issues
        self._usb_confirmed_model=model
        self._usb_coverage=audit_readback(data,layout='common-prefix1556')
        # The current RAM name is independent of the stored-name catalog.
        # Do not substitute a local session slot or guess an ANSI codepage.
        name_raw=bytes.fromhex(document.decoded()['configuration_name_bytes_hex'])
        try:name=name_raw.split(b'\0',1)[0].decode('ascii').rstrip(' ')
        except UnicodeDecodeError:name='[name encoding unverified]'
        slot=(self._usb_preset_metadata or {}).get('active_slot_raw')
        label=f'{self.connectionMedium} P{slot:02d}' if type(slot) is int and 0<=slot<=19 else self.connectionMedium
        self._preset=label+' · '+(name or '[unnamed configuration]');self._baseline=model.to_dict();self._active_slot=-1
        self.notify(f'{self.connectionMedium} configuration read · {len(data)} bytes · {len(issues)} raw/unrepresented fields')
    @Slot(object)
    def _usb_receive_telemetry(self,value):
        self._usb_telemetry=value;self._usb_last=time.monotonic()
        self._output_db=[v.log_level_db+17. if v.log_level_db is not None else -100. for v in value.levels]
        self._meters=[meter_position(db) for db in self._output_db]
        for i,db in enumerate(self._output_db):
            if db>=self._peaks[i]:self._peaks[i]=db;self._peak_hold[i]=10
        self.metersChanged.emit()
    @Slot(str,bytes)
    def _usb_log(self,direction,data):
        # Also filter at the UI boundary: late/unexpected authentication
        # frames must never enter snapshot exports after an ACK was accepted.
        if len(data)>5 and data[5] in (0x2D,0x2F):return
        if direction=='rx' and len(data)>5 and data[5]==0x2C:
            from dsp408.device_utilities import session_lock,system_lock
            from dsp408.wire_research import decode_editor_frame
            try:
                payload=decode_editor_frame(data).data
                self._utility_state={**self._utility_state,'locked':session_lock(payload),'password_protected':system_lock(payload),'lock_known':True}
                self.changed.emit()
            except ValueError:pass
        self._usb_total_frames+=1;self._usb_journal.append({'direction':direction,'frame_hex':bytes(data).hex()})
        if len(self._usb_journal)>2500:del self._usb_journal[0]
    @Slot(str)
    def _usb_failed(self,error):
        self._channel_link_candidate=None;self._channel_link_review={}
        self._software_bypass.clear()
        self._pending_fir_action=None
        self._ethernet_fir_preview=None
        self._usb_status='USB read failed: '+error;self.notify(self._usb_status)
    @Slot()
    def _usb_finished(self):
        self._bank_restore_candidate=None;self._bank_restore_review={}
        self._bank_backup_candidate=None;self._bank_backup_review={}
        self._channel_link_candidate=None;self._channel_link_review={}
        self._software_bypass.clear()
        self._pending_fir_action=None
        self.timer.stop()
        worker=self._usb_worker;self._usb_worker=None
        self._ethernet_fir_preview=None
        self._utility_state={**self._utility_state,'busy':False,'source':None,'frequency':None}
        self._usb_gain_mode=False;self._usb_gain_ready=False;self._usb_gain_busy=False
        self._usb_control_mode=False;self._usb_control_ready=False;self._usb_control_pending=False
        self._usb_fir_mode=False
        self._usb_preview_mode=False
        self._usb_eeprom_mode=False
        self._usb_preset_trial_mode=False
        if not self._usb_status.startswith('USB read failed:'):self._usb_status='USB read disconnected'
        if self._usb_offline is not None:
            state,name,slot,baseline=self._usb_offline
            self.model=DeviceModel.from_dict(state);self._preset=name;self._active_slot=slot;self._baseline=baseline
        self._usb_offline=None;self._usb_telemetry=None;self._clear_usb_meters()
        self.notify(self._usb_status+' · offline configuration restored')
        if worker is not None:worker.deleteLater()
    def _clear_usb_meters(self):
        self._output_db=[-100.]*12;self._peaks=[-100.]*12
        self._meters=[0.]*12;self._peak_hold=[0]*12;self.metersChanged.emit()
    @Slot(str,result=bool)
    def exportUsbReadPath(self,path):
        if self._usb_raw_state is None:return False
        try:
            report={'scope':self.connectionMedium+' EXE/MCU parameter verification; full journal separate' if self._usb_control_journal else 'USB read with guarded IN A gain; full durable journal is separate' if self._usb_gain_journal else self.connectionMedium+' read only; no parameter write verification','identity':'FIR408 V0115P',
                    'parameter_journal_path':self._usb_control_journal or None,
                    'requested_values_pending':self._usb_control_pending,
                    'gain_journal_path':self._usb_gain_journal or None,
                    'layout':'common-prefix1556','state_hex':self._usb_raw_state.hex(),'projection_issues':self._usb_issues,
                    'preset_metadata':self._usb_preset_metadata,
                    'fir_storage_bank':({**self._usb_fir_report,'raw_hex':self._usb_fir_bank.hex(),
                                         'journal_path':self._usb_fir_journal} if self._usb_fir_bank is not None else None),
                    'fir_read_preview':self._ethernet_fir_preview,
                    'readback_coverage':self._usb_coverage,
                    'total_frames':self._usb_total_frames,'retained_frames':len(self._usb_journal),'events':self._usb_journal}
            Path(path).write_text(json.dumps(report,indent=2),encoding='utf-8');self.notify('USB raw configuration and bounded journal exported');return True
        except OSError as e:self.notify(str(e));return False
    @Slot()
    def exportUsbRead(self):
        path,_=QFileDialog.getSaveFileName(None,'Export USB raw readback and journal','','JSON (*.json)')
        if path:self.exportUsbReadPath(path if path.lower().endswith('.json') else path+'.json')
    @Property(bool,notify=changed)
    def usbPrsSnapshotAvailable(self):
        return self._usb_raw_state is not None and (self._usb_fir_bank is not None or self.usbControlReady and hasattr(self._usb_worker,'request_fir_read'))
    @Slot(str,result=bool)
    def exportUsbPrsPath(self,path):
        if self.usbControlPending or self.usbPresetRecallBusy:
            self.notify('Wait for current settings to finish before exporting the configuration');return False
        if not self.usbPrsSnapshotAvailable:
            self.notify('PRS export requires complete parameter and FIR readback');return False
        if self._usb_fir_bank is None:return self._prepare_current_fir('prs_export',(path,))
        try:
            if Path(path).suffix.lower()!='.prs':raise ValueError('PRS snapshot destination must end in .prs')
            from dsp408.prs import from_read_snapshot
            model=from_read_snapshot(self._usb_raw_state,self._usb_fir_bank)
            model.save(path)
            self.notify('Configuration and FIR saved to PRS')
            return True
        except (ValueError,OSError) as error:self.notify(str(error));return False
    @Slot()
    def exportUsbPrs(self):
        path,_=QFileDialog.getSaveFileName(None,'Export configuration and FIR',
                                       'DSP408-read-snapshot.prs','Original editor preset (*.prs)')
        if path:self.exportUsbPrsPath(path if path.lower().endswith('.prs') else path+'.prs')

    @Property(bool,notify=changed)
    def bankBackupAvailable(self):
        return self.usbControlReady and self.usbPresetRecallAvailable and self._usb_preset_metadata is not None and hasattr(self._usb_worker,'request_bank_backup')

    @Property('QVariantMap',notify=changed)
    def bankBackupReview(self):return self._bank_backup_review

    @Slot(str,result=bool)
    def previewBankBackupPath(self,path):
        self._bank_backup_candidate=None;self._bank_backup_review={}
        if not self.bankBackupAvailable:return False
        if self._usb_fir_bank is None:
            self._prepare_current_fir('bank_backup',(path,));return False
        try:
            from dsp408.preset_bank import prepare_backup
            if Path(path).suffix.lower()!='.dspbank':raise ValueError('Use a .dspbank backup filename')
            meta=self._usb_preset_metadata;named=meta.get('names_raw_hex',{})
            names=tuple(bytes.fromhex(named.get(i,named.get(str(i),''))) for i in range(19))
            p=prepare_backup(self._usb_raw_state,self._usb_fir_bank,bytes(meta['catalog_markers']),meta['active_slot_raw'],names,True)
            self._bank_backup_candidate=(p,str(path))
            self._bank_backup_review={'path':str(path),'count':p.catalog.count(255),'total':len(p.requests)}
            self.changed.emit();return True
        except (ValueError,KeyError,TypeError) as error:self.notify(str(error));return False

    @Slot(result=bool)
    def chooseBankBackup(self):
        if not self.bankBackupAvailable:return False
        path,_=QFileDialog.getSaveFileName(None,'Back up complete preset bank','DSP408-presets.dspbank','DSP408 bank backup (*.dspbank)')
        return bool(path) and self.previewBankBackupPath(path if path.lower().endswith('.dspbank') else path+'.dspbank')

    @Slot(result=bool)
    def applyBankBackup(self):
        if not self.bankBackupAvailable or self._bank_backup_candidate is None:return False
        p,path=self._bank_backup_candidate
        if p.state!=self._usb_raw_state or p.bank!=self._usb_fir_bank:
            self.notify('DSP changed since backup review; review again');return False
        meta=self._usb_preset_metadata;named=meta.get('names_raw_hex',{})
        if (bytes(meta['catalog_markers']),meta['active_slot_raw'],tuple(bytes.fromhex(named.get(i,named.get(str(i),''))) for i in range(19)))!=(p.catalog,p.active,p.names):
            self.notify('Preset catalog changed since backup review; review again');return False
        try:
            if not self._usb_worker.request_bank_backup(p.state,p.bank,p.catalog,p.active,p.names,path,p.extended):return False
        except (ValueError,AttributeError) as error:self.notify(str(error));return False
        self._bank_backup_candidate=None
        self._usb_recall_progress={'busy':True,'operation':'bank_backup','stage':'Reading preset bank','done':0,'total':len(p.requests),'waiting':False}
        self._usb_telemetry=None;self._clear_usb_meters();self.notify('Reading preset bank');return True

    @Slot(str,str,result=bool)
    def extractBankBackupPath(self,path,destination):
        if self.usbPresetRecallBusy:return False
        try:
            from dsp408.preset_bank import extract_archive
            m=extract_archive(path,destination)
            self.notify('Backup extracted · '+str(sum(r['stored'] for r in m['slots']))+' presets and CURRENT.prs · '+str(destination));return True
        except (ValueError,OSError) as error:self.notify(str(error));return False

    @Slot()
    def extractBankBackup(self):
        if self.usbPresetRecallBusy:return
        path,_=QFileDialog.getOpenFileName(None,'Extract preset bank backup','','DSP408 bank backup (*.dspbank)')
        if not path:return
        destination=QFileDialog.getExistingDirectory(None,'Choose parent folder for extracted backup')
        if destination:self.extractBankBackupPath(path,str(Path(destination)/Path(path).stem))

    @Property('QVariantMap',notify=changed)
    def bankRestoreReview(self):return self._bank_restore_review

    @Slot(str,result=bool)
    def previewBankRestorePath(self,path):
        self._bank_restore_candidate=None;self._bank_restore_review={}
        if not self.bankBackupAvailable or not hasattr(self._usb_worker,'request_bank_restore'):return False
        if self._usb_fir_bank is None:
            self._prepare_current_fir('bank_restore',(path,));return False
        try:
            from dsp408.preset_bank_restore import source_data,prepare_restore
            records,banks=source_data(path);meta=self._usb_preset_metadata;named=meta['names_raw_hex']
            names=tuple(bytes.fromhex(named.get(i,named.get(str(i),''))) for i in range(19))
            p=prepare_restore(self._usb_raw_state,self._usb_fir_bank,bytes(meta['catalog_markers']),meta['active_slot_raw'],names,records,banks)
            self._bank_restore_candidate=(p,str(path));self._bank_restore_review={'path':str(path),'count':sum(r[0]==255 for r in records),'empty':sum(r[0]==0 for r in records),'total':len(p.requests)}
            self.changed.emit();return True
        except (ValueError,OSError,KeyError,TypeError) as error:self.notify(str(error));return False

    @Slot(result=bool)
    def chooseBankRestore(self):
        if not self.bankBackupAvailable:return False
        path,_=QFileDialog.getOpenFileName(None,'Restore complete preset bank','','DSP408 bank backup (*.dspbank)')
        return bool(path) and self.previewBankRestorePath(path)

    @Slot(result=bool)
    def applyBankRestore(self):
        if not self.bankBackupAvailable or self._bank_restore_candidate is None:return False
        p,path=self._bank_restore_candidate
        if p.state!=self._usb_raw_state or (p.bank is not None and p.bank!=self._usb_fir_bank):
            self.notify('DSP changed since review; review bank restore again');return False
        try:
            if not self._usb_worker.request_bank_restore(p.state,p.bank,p.catalog,p.active,p.names,p.records,p.banks,path):return False
        except (ValueError,AttributeError) as error:self.notify(str(error));return False
        self._bank_restore_candidate=None;self._usb_recall_progress={'busy':True,'operation':'bank_restore','stage':'Backing up before restore','done':0,'total':len(p.requests),'waiting':False}
        self._usb_telemetry=None;self._clear_usb_meters();self.notify('Restoring saved preset bank');return True
    @Property(str,notify=changed)
    def wireSummary(self):return self._wire_summary
    @Property(bool,notify=changed)
    def localProtocolActive(self):return self._source_session is not None and self._source_session.active
    @Property(str,notify=changed)
    def sourceStatus(self):return self._source_status
    @Property('QVariantList',constant=True)
    def sineFrequencies(self):return SINE_FREQUENCIES
    @Slot(bool)
    def setLocalProtocol(self,enabled):
        if self.usbReadActive:return
        if enabled:
            if self.localProtocolActive:return
            self._source_session=LocalSourceSession(self.model.to_dict())
            self._source_status='LOCAL TEST active · synthetic source document. Edit controls to build packets; no physical I/O.'
        elif self._source_session is not None:
            self._source_session.active=False;self._source_status='Local test stopped. Journal retained for export; physical communication disabled.'
        self.notify()
    @Slot(result=bool)
    def readLocalSource(self):
        if self.editingLocked:return False
        if self.usbReadActive:return False
        if self._source_session is None:return False
        try:
            model,issues=self._source_session.readback(self.model.to_dict())
            self.remember_configuration();self.model=model;self._source_session.previous=model.to_dict()
            self.notify(f'Local source readback via 32 configuration blocks; {len(issues)} fields retained raw/unrepresented')
            self._source_status=f'Local readback complete · {len(issues)} field reports. Export journal for details.'
            self._source_session.projection_issues=issues;self.changed.emit();return True
        except ValueError as e:self.notify(str(e));return False
    @Slot(str,str,result=bool)
    def loadSourceStatePath(self,path,layout):
        if self.editingLocked:return False
        if self.usbReadActive:return False
        try:
            from dsp408.editor_state_research import LAYOUT_SIZES
            if layout not in LAYOUT_SIZES:raise ValueError('Choose an explicit source state layout')
            source=Path(path)
            if source.stat().st_size!=LAYOUT_SIZES[layout]:raise ValueError('File size differs from the selected source layout')
            with source.open('rb') as stream:data=stream.read(LAYOUT_SIZES[layout]+1)
            document=SourceDocument(data,layout,origin='local state file: '+Path(path).name)
            model,issues=project_state(document,self.model.to_dict())
            self.remember_configuration();self.model=model
            self._source_session=LocalSourceSession(model.to_dict(),document)
            self._source_session.projection_issues=issues
            self.notify(f'Local source state imported; {len(issues)} fields retained raw/unrepresented. No hardware connection.')
            self._source_status=f'Imported {layout} · {len(issues)} field reports; opaque data retained. Local test active.'
            self.changed.emit();return True
        except (ValueError,OSError) as e:self.notify(str(e));return False
    @Slot(str)
    def importSourceState(self,layout):
        path,_=QFileDialog.getOpenFileName(None,'Import assembled source state (offline)','','Raw state (*.bin)')
        if path:self.loadSourceStatePath(path,layout)
    @Slot(str,result=bool)
    def exportSourceJournalPath(self,path):
        if self._source_session is None:return False
        try:self._source_session.save(path);self.notify('Local packet journal exported; not a hardware upload script');return True
        except (OSError,ValueError) as e:self.notify(str(e));return False
    @Slot()
    def exportSourceJournal(self):
        path,_=QFileDialog.getSaveFileName(None,'Export local protocol journal','','JSON (*.json)')
        if path:self.exportSourceJournalPath(path if path.lower().endswith('.json') else path+'.json')
    @Slot(str,result=bool)
    def inspectWirePath(self,path):
        try:
            report=inspect_wire_file(path)
            self._wire_summary=(f"{report['file']} · {report['bytes']} bytes · {report['frames']} valid editor frames\n"
                f"Invalid candidates: {report['invalid']} · discarded bytes: {report['discarded']} · pending: {report['pending']}\n"
                'Opaque commands: '+', '.join(f'{cmd}: {count}' for cmd,count in report['commands'].items())+
                '\nOffline analysis only. Device identity, direction and responses remain unverified.')
            self.notify('Local wire log inspected; no DSP contacted');return True
        except (OSError,ValueError,UnicodeError) as error:self.notify(str(error));return False
    @Slot()
    def inspectWireLog(self):
        path,_=QFileDialog.getOpenFileName(None,'Inspect offline wire log','','Raw / hex stream (*.bin *.hex *.txt)')
        if path:self.inspectWirePath(path)
    @Slot(str,result=float)
    def delayFactor(self,unit):return self.delayFactors[unit]
    @Property(float,notify=delayTemperatureChanged)
    def ambientTemperature(self):return self._ambient_temperature
    @Property(float,notify=delayTemperatureChanged)
    def soundSpeed(self):return sound_speed(self._ambient_temperature,**self._delay_air_options())
    @Property('QVariantMap',notify=delayTemperatureChanged)
    def delayFactors(self):return conversion_factors(self._ambient_temperature,**self._delay_air_options())
    @Property(bool,notify=delayTemperatureChanged)
    def delayAirCorrection(self):return self._delay_air['enabled']
    @Property(bool,notify=delayTemperatureChanged)
    def delayAirCorrectionActive(self):return self.delayAirCorrection and 0<=self._ambient_temperature<=30
    @Property(float,notify=delayTemperatureChanged)
    def delayHumidity(self):return self._delay_air['humidity']
    @Property(float,notify=delayTemperatureChanged)
    def delayPressureHpa(self):return self._delay_air['pressure_hpa']
    def _delay_air_options(self):
        return {'humidity':self.delayHumidity if self.delayAirCorrection else None,'pressure_hpa':self.delayPressureHpa}
    def _set_delay_air(self,**changes):
        try:
            value=checked_air_conditions(self._delay_air|changes)
            if value==self._delay_air:return True
            self._preferences.save_delay_air_conditions(value)
        except (ValueError,TypeError,KeyError,OSError) as error:
            self._message='Cannot save air conditions: '+str(error);self.statusChanged.emit();return False
        self._delay_air=value;self.delayTemperatureChanged.emit();return True
    @Slot(bool,result=bool)
    def setDelayAirCorrection(self,value):return self._set_delay_air(enabled=value)
    @Slot(float,result=bool)
    def setDelayHumidity(self,value):return self._set_delay_air(humidity=value)
    @Slot(float,result=bool)
    def setDelayPressureHpa(self,value):return self._set_delay_air(pressure_hpa=value)
    @Slot(float,result=bool)
    def setAmbientTemperature(self,value):
        try:
            value=checked_temperature(value)
            if value==self._ambient_temperature:return True
            self._preferences.save_ambient_temperature(value)
        except (ValueError,TypeError,OSError) as error:
            self._message='Cannot save temperature: '+str(error);self.statusChanged.emit();return False
        self._ambient_temperature=value;self.delayTemperatureChanged.emit();return True
    @Slot(float,str,result=float)
    def delayDisplay(self,milliseconds,unit):return display_delay(milliseconds,unit,self._ambient_temperature,**self._delay_air_options())
    @Slot(int,float,str)
    def editDelay(self,index,value,unit):
        if self.editingLocked:return
        try:self.edit(index,'delay_ms',delay_milliseconds(value,unit,self._ambient_temperature,**self._delay_air_options()))
        except (KeyError,ValueError,TypeError) as e:self.notify(str(e))
    @Slot(float,result=float)
    def meterPosition(self,db):return meter_position(db)
    @Property('QVariantList',notify=metersChanged)
    def reductionState(self):
        result=[]
        for index in range(12):
            if self.usbReadActive:
                routed=[{'index':o+4,'name':c.name,'db':0.} for o,c in enumerate(self.model.outputs) if index<4 and self.model.routing[o][index] and self._usb_reducing(o+4)]
                result.append({'kind':'COMP' if index<4 else 'LIM','db':0.,'active':self._usb_reducing(index),'routed':routed})
                continue
            result.append({'kind':'COMP' if index<4 else 'LIM','db':0.,'active':False,'routed':[]})
        return result
    @Property('QVariantList',notify=metersChanged)
    def rtaData(self):
        # Retain the empty RTA API for compatibility;
        # never replace unavailable DSP measurements with generated spectra.
        return []
    @Slot(str,result='QVariantMap')
    def dynamicsSample(self,section):
        # Static estimate driven only by a fresh real channel
        # reading. Its internal tap is unconfirmed; never claim measured GR or
        # actual pre/post taps, detector EQ or attack/release envelope tracking.
        if not self._dynamics_display:return {'input':-100.,'output':-100.,'reduction':0.,'peak':-100.,
            'available':False,'estimated':False,'source':'display_disabled','channel':self._selected,
            'reason':'Dynamics display disabled in SETUP'}
        applicable=section=='compressor' and self._selected<4 or section=='limiter' and self._selected>=4
        if (applicable and self.usbReadActive and self._usb_telemetry is not None
                and time.monotonic()-self._usb_last<=2.
                and self._usb_telemetry.levels[self._selected].log_level_db is not None):
            incoming=self._output_db[self._selected]
            outgoing=transfer_db(incoming,getattr(self.model.channels[self._selected],section),section)
            return {'input':incoming,'output':outgoing,'reduction':max(0.,incoming-outgoing),
                    'peak':self._peaks[self._selected],'available':True,'estimated':True,
                    'source':self._connection_transport+'_channel_static_estimate','channel':self._selected,
                    'reason':'Calculated preview · channel reading treated as model input; internal tap and attack/release unmeasured'}
        if self.usbReadActive:return {'input':-100.,'output':-100.,'reduction':0.,'peak':-100.,
            'available':False,'estimated':False,'source':self._connection_transport+'_unavailable','channel':self._selected,
            'reason':self.connectionMedium+': pre/post dynamics levels and numeric GR unavailable'}
        return {'input':-100.,'output':-100.,'reduction':0.,'peak':-100.,
            'available':False,'source':'offline_unavailable','channel':self._selected,
            'reason':'Offline · no live signal readings'}
    @Slot(str,float,result=float)
    def dynamicsOutput(self,section,level):
        """Pure display evaluation; no I/O or attack/release emulation."""
        return transfer_db(level,getattr(self.model.channels[self._selected],section),section)
    @Slot(str,result='QVariantMap')
    def kneePreview(self,section):
        from dsp408.dynamics import knee_detail
        if section not in ('compressor','limiter'):return {}
        return knee_detail(getattr(self.model.channels[self._selected],section),section)
    @Slot(str,float,float,result='QVariantList')
    def transferCurve(self,section,low,high):
        state=getattr(self.model.channels[self._selected],section)
        return [transfer_db(low+(high-low)*i/240,state,section) for i in range(241)]
    @Slot(int,bool,result='QVariantMap')
    def crossoverPlot(self,comparison,include_eq):
        channel=self.model.channels[self._selected]
        other=self.model.outputs[comparison] if 0<=comparison<8 and self._selected!=comparison+4 else None
        return plot_data(channel,other,include_eq)
    @Property('QVariantList',notify=changed)
    def xoverCompared(self):return self._xover_compared[:]
    @Slot(int,bool)
    def compareXover(self,index,enabled):
        if not 4<=index<12:return
        self._xover_compared=sorted(set(self._xover_compared+[index])) if enabled else [i for i in self._xover_compared if i!=index]
        self.notify()
    @Slot(bool,result='QVariantMap')
    def crossoverComparisonPlot(self,include_eq):
        def cached(index):return self._crossover_data(index,include_eq)
        original=cached(self._selected)
        result={**original,'traces':list(original['traces']),'crossings':list(original['crossings'])}
        current_total=next((t['values'] for t in result['traces'] if 'combined' in t['label']),None)
        colors=['#f9cf42','#40d9c4','#ed934b','#a5d76b','#aa99ef','#ff89c5','#b8d6ee','#d7b68c']
        missing=[];crossings=[];design_comparison=False
        for index in self._xover_compared:
            if index==self._selected:continue
            other=self.model.channels[index];data=cached(index)
            total=next((t for t in data['traces'] if 'combined' in t['label']),None)
            if total is None:missing.append(f'OUT {index-3}');continue
            design_comparison=design_comparison or total.get('preview')=='source_formula'
            result['traces'].append({**total,'label':f'OUT {index-3} · {other.name} · combined','color':colors[index-4],'comparison':True})
            if current_total is not None:
                for point in intersections(current_total,total['values']):
                    crossings.append({**point,'label':f'OUT {self._selected-3} / OUT {index-3}','color':colors[index-4]})
        if any(t.get('comparison') for t in result['traces']):result['crossings']=crossings
        if missing:result['notice']+=' · FIR preview unavailable: '+', '.join(missing)
        if design_comparison:result['notice']+=' · compared FIR: approximate design'
        return result
    def _crossover_data(self,index,include_eq):
        channel=self.model.channels[index]
        signature=(include_eq,channel.name,channel.gain,channel.crossover_mode)
        if channel.crossover_mode=='IIR':
            signature+=(channel.hpf_hz,channel.hpf_type,channel.hpf_bypass,
                        channel.lpf_hz,channel.lpf_type,channel.lpf_bypass)
        else:
            f=channel.fir
            signature+=(f.mode,f.window,f.taps,f.hpf_hz,f.lpf_hz,f.bypass,tuple(f.coefficients))
        if include_eq:
            signature+=(channel.eq_bypass,tuple((f.enabled,f.kind,f.frequency,f.gain,f.q) for f in channel.filters))
        entry=self._xover_curve_cache.get(index)
        if entry is None or entry[0]!=signature:
            entry=(signature,plot_data(channel,include_eq=include_eq));self._xover_curve_cache[index]=entry
        return entry[1]
    @Property('QVariantMap',notify=changed)
    def peqChannelResponse(self):
        if self._selected<4:return {'values':[],'available':False}
        data=self._crossover_data(self._selected,True)
        total=next((t['values'] for t in data['traces'] if 'combined' in t['label']),None)
        return {'values':list(total) if total is not None else [],'available':total is not None,
                'kind':self.model.channels[self._selected].crossover_mode,'notice':data['notice']}
    @Property('QVariantList',notify=changed)
    def curve(self):return self.peq_responses()[0]
    @Property('QVariantList',notify=changed)
    def bandCurves(self):return self.peq_responses()[1]
    @Property('QVariantList',notify=changed)
    def peqCompared(self):return self._peq_compared[:]
    @Slot(int,bool)
    def comparePeq(self,index,enabled):
        if not 0<=index<12:return
        self._peq_compared=sorted(set(self._peq_compared+[index])) if enabled else [i for i in self._peq_compared if i!=index]
        self.notify()
    @Property('QVariantList',notify=changed)
    def peqComparisons(self):
        colors=['#38aeff','#48e77c','#ff6774','#c66cf5','#f9cf42','#40d9c4','#ed934b','#a5d76b','#aa99ef','#ff89c5','#b8d6ee','#d7b68c']
        curves=[]
        for index in self._peq_compared:
            if index==self._selected:continue
            channel=self.model.channels[index]
            signature=(self._phase,channel.eq_bypass,tuple((f.enabled,f.kind,f.frequency,f.gain,f.q) for f in channel.filters))
            cached=self._comparison_cache.get(index)
            if cached is None or cached[0]!=signature:
                cached=(signature,response(channel,self._phase));self._comparison_cache[index]=cached
            curves.append({'index':index,'label':channel.name,'color':colors[index],'values':cached[1]})
        return curves
    def peq_responses(self):
        from copy import copy
        channel=self.model.channels[self._selected]
        signature=(self._selected,self._phase,channel.eq_bypass,tuple((f.enabled,f.kind,f.frequency,f.gain,f.q) for f in channel.filters))
        if self._peq_cache[0]==signature:return self._peq_cache[1:]
        result=[]
        if not hasattr(self,'_band_preview_cache'):self._band_preview_cache={}
        for f in channel.filters:
            if not f.enabled or channel.eq_bypass:result.append([]);continue
            key=(self._phase,f.kind,f.frequency,f.gain,f.q)
            if key not in self._band_preview_cache:
                single=copy(channel);single.filters=[f]
                if len(self._band_preview_cache)>=64:self._band_preview_cache.pop(next(iter(self._band_preview_cache)))
                self._band_preview_cache[key]=response(single,self._phase)
            result.append(self._band_preview_cache[key])
        self._peq_cache=(signature,response(channel,self._phase),result)
        return self._peq_cache[1:]
    @Property('QVariantList',notify=changed)
    def firCurve(self):
        coefficients=tuple(self.usbInputFirCoefficients if self.usbReadActive else self.model.channels[self._selected].fir.coefficients)
        if self._fir_cache[0]!=coefficients:self._fir_cache=(coefficients,fir_response(coefficients) if coefficients else [])
        return self._fir_cache[1]

    @Property('QVariantList',notify=changed)
    def firPhaseCurve(self):
        coefficients=tuple(self.usbInputFirCoefficients if self.usbReadActive else self.model.channels[self._selected].fir.coefficients)
        if self._fir_phase_cache[0]!=coefficients:
            self._fir_phase_cache=(coefficients,fir_response(coefficients,phase=True) if coefficients else [])
        return self._fir_phase_cache[1]

    @Property('QVariantMap',notify=changed)
    def firResponseRange(self):
        values=self.firCurve
        return {'minimum':min(values),'maximum':max(values)} if values else {}
    @Property('QVariantMap',constant=True)
    def options(self):return {'filters':FILTER_TYPES,'crossover':CROSS_TYPES,'windows':FIR_WINDOWS,'fir':FIR_TYPES,'deqTypes':DEQ_TYPES,'deqModes':DEQ_MODES,'detectorTypes':DETECTOR_TYPES,'ratios':RATIO_VALUES,'qValues':Q_VALUES,'frequencyMin':FREQUENCY_MIN,'frequencyMax':FREQUENCY_MAX,'firHpMin':FIR_HP_MIN,'firHpMax':FIR_HP_MAX,'firLpMin':FIR_LP_MIN,'firLpMax':FIR_LP_MAX,'deqLimits':{k:list(v) for k,v in DEQ_LIMITS.items()}}
    @Property('QVariantMap',notify=changed)
    def settings(self):return dict(self.model.settings)
    @Property('QVariantList',notify=changed)
    def links(self):return self.model.links[:]
    @Property('QVariantList',notify=changed)
    def routing(self):return self.model.routing
    @Property('QVariantList',notify=changed)
    def routingGains(self):return self.model.routing_gains
    @Property(int,notify=changed)
    def firUsed(self):return sum(len(c.fir.coefficients) for c in self.model.channels)
    @Slot(int,result='QVariantMap')
    def channel(self,index):
        if index not in self._channel_views:self._channel_views[index]=state_snapshot(self.model.channels[index])
        return self._channel_views[index]
    @Slot(int)
    def select(self,index):
        if 0<=index<12:
            self._channel_link_candidate=None;self._channel_link_review={}
            self._selected=index;self.notify()
    @Slot(int,str,'QVariant',int)
    def edit(self,index,key,value,band=-1):
        if self.editingLocked:return
        if self.usbReadActive:
            if self.usbControlMode:
                if self._control_edit(lambda m:m.set_channel(index,key,value,band)) and self._software_bypass.invalidate(self.model,index,key):self.notify()
            elif index==0 and key=='gain' and band==-1:self.requestUsbGain(value)
            return
        try:
            self.model.set_channel(index,key,value,band)
            self._software_bypass.invalidate(self.model,index,key);self.notify()
        except (ValueError,AttributeError,TypeError) as e:self.notify(str(e))
    @Slot(int,str,result=bool)
    def renameChannel(self,index,name):
        if type(index) is not int or not 0<=index<12 or not self.parameterEditingAllowed:return False
        try:
            from dsp408.channel_names import encode_channel_name
            encode_channel_name(name)
            if self.model.channels[index].name==name:return True
            if self.usbReadActive:
                accepted=self._control_edit(lambda m:m.set_channel(index,'name',name))
                if accepted:self.flushControlView()
                return accepted
            self.model.set_channel(index,'name',name);self.notify();return True
        except (ValueError,TypeError) as error:self.notify(str(error));return False

    @Slot(int,str,result=bool)
    def renameFir(self,index,name):
        if type(index) is not int or not 0<=index<12 or not self.parameterEditingAllowed:return False
        try:
            from dsp408.channel_names import encode_fir_name
            encode_fir_name(name)
            if self.model.channels[index].fir.name==name:return True
            if self.usbReadActive:
                accepted=self._control_edit(lambda m:m.set_channel(index,'fir.name',name))
                if accepted:self.flushControlView()
                return accepted
            self.model.set_channel(index,'fir.name',name);self.notify();return True
        except (ValueError,TypeError) as error:self.notify(str(error));return False

    @Property('QVariantList',notify=changed)
    def channelLinks(self):
        from dsp408.channel_link import masks,topology
        values=masks(self._usb_raw_state) if self.usbReadActive and self._usb_raw_state is not None else getattr(self.model,'device_link_masks',None)
        native=values is not None
        if native:
            try:groups=topology(values)
            except ValueError:groups=()
        elif self.usbReadActive:groups=()
        else:groups=tuple(tuple(i for i in scope if self.model.links[i]) for scope in (range(4),range(4,12)))
        result=[{'linked':False,'members':[],'label':'','description':'','color':'#40d9c4'} for _ in range(12)]
        # At most six disjoint groups. Assign distinct hues to actual groups,
        # rather than nearby pastel shades based on the owner's channel number.
        palette=('#37dab5','#ffb24d','#bb8dff','#9dd957','#ff739c','#559fff')
        for group_index,group in enumerate(g for g in groups if len(g)>1):
            short=lambda i:chr(65+i) if i<4 else str(i-3)
            labels=[('IN ' if i<4 else 'OUT ')+short(i) for i in group]
            label='+'.join(short(i) for i in group) if len(group)<=4 else str(len(group))+' CH'
            info={'linked':True,'members':list(group),'label':label,
                'description':('Linked: ' if native else 'Linked DEMO edits: ')+' + '.join(labels),
                'color':palette[group_index]}
            for i in group:result[i]=dict(info)
        return result

    @Property('QVariantList',notify=changed)
    def channelLinkMembers(self):
        from dsp408.channel_link import members_for,masks
        values=masks(self._usb_raw_state) if self.usbReadActive and self._usb_raw_state is not None else self.model.link_masks()
        if values is None:return [self._selected]
        try:return list(members_for(values,self._selected))
        except ValueError:return [self._selected]
    @Property('QVariantMap',notify=changed)
    def channelLinkReview(self):return getattr(self,'_channel_link_review',{})
    @Slot()
    def cancelChannelLink(self):
        self._channel_link_candidate=None;self._channel_link_review={};self.notify()
    @Slot('QVariantList',result=bool)
    def reviewChannelLink(self,members):
        self._channel_link_candidate=None;self._channel_link_review={}
        if not self.usbReadActive:
            if self.editingLocked:return False
            try:
                clone,copies=self.model.with_link_group(self._selected,members)
                self._channel_link_candidate={'selected':self._selected,'before':self.model.to_dict(),'after':clone.to_dict()}
                label=lambda i:('IN '+chr(65+i) if i<4 else 'OUT '+str(i-3))+' · '+self.model.channels[i].name
                self._channel_link_review={'members':', '.join(label(i) for i in sorted(members)),
                    'source':label(min(members)),'copies':[label(a)+' → '+label(b) for a,b in copies],
                    'unlink':len(members)==1,'offline':True}
                self.notify();return True
            except (ValueError,TypeError) as error:self.notify(str(error));return False
        if not self.usbControlReady or self.usbControlPending:return False
        try:
            from dsp408.channel_link import prepare_link
            p=prepare_link(self._usb_raw_state,None,self._selected,members)
            self._channel_link_candidate=p
            label=lambda i:('IN '+chr(65+i) if i<4 else 'OUT '+str(i-3))+' · '+self.model.channels[i].name
            self._channel_link_review={'members':', '.join(label(i) for i in p.members),
                'source':label(min(p.members)),'copies':[label(a)+' → '+label(b) for a,b,count in p.copies],
                'unlink':len(p.members)==1,'total':len(p.requests)}
            self.notify();return True
        except (ValueError,TypeError) as error:self.notify(str(error));return False
    @Slot(result=bool)
    def applyChannelLink(self):
        p=getattr(self,'_channel_link_candidate',None)
        if isinstance(p,dict):
            if self.usbReadActive or self.editingLocked or p['selected']!=self._selected or p['before']!=self.model.to_dict():
                self.cancelChannelLink();return False
            self.model=DeviceModel.from_dict(p['after']);self._software_bypass.clear()
            self.cancelChannelLink();return True
        if p is None or not self.usbControlReady or self.usbControlPending or p.selected!=self._selected:return False
        if p.state!=self._usb_raw_state or (p.bank is not None and p.bank!=self._usb_fir_bank):
            self.cancelChannelLink();self.notify('DSP changed; review channel Link again');return False
        try:
            if not self._usb_worker.request_link(p.state,p.bank,p.selected,p.members):return False
        except (ValueError,AttributeError) as error:self.notify(str(error));return False
        self._channel_link_candidate=None;self._channel_link_review={};self._software_bypass.clear()
        self._usb_recall_progress={'busy':True,'operation':'channel_link','stage':'Applying channel Link','done':0,'total':len(p.requests),'waiting':False}
        self._usb_telemetry=None;self._clear_usb_meters();self.notify();return True
    @Slot(int,str,result=bool)
    def toggleOverviewFunction(self,index,action):
        if type(index) is not int or not 0<=index<12 or not self.parameterEditingAllowed:return False
        block=next((b for b in self.channelSummaries[index]['blocks'] if b['action']==action),None)
        if block is None:return False
        if action in SPECS:
            try:
                clone,entries=self._software_bypass.plan(self.model,index,action)
                if self.usbReadActive:
                    def change(model):model.inputs,model.outputs=clone.inputs,clone.outputs
                    if not self._control_edit(change):return False
                else:self.model=clone
                self._software_bypass.entries=entries
                self.flushControlView();self.notify();return True
            except (ValueError,TypeError,IndexError) as error:self.notify(str(error));return False
        key=block['toggle_key']
        if not key:
            self.notify('Use right-click to edit; this block has no quick bypass control');return False
        target=not block['bypassed']
        if key=='fir.bypass' and self.usbReadActive:return self._request_channel_fir_bypass(index,target)
        if self.usbReadActive:
            accepted=self._control_edit(lambda m:m.set_channel(index,key,target))
            if accepted:self.flushControlView()
            return accepted
        self.model.set_channel(index,key,target);self.notify();return True
    @Property(bool,notify=changed)
    def outputsAllMuted(self):return all(ch.mute for ch in self.model.outputs)
    @Slot(bool,result=bool)
    def setOutputsMuted(self,muted):
        if type(muted) is not bool or not self.parameterEditingAllowed:return False
        def change(model):
            for index in range(4,12):model.set_channel(index,'mute',muted)
        if self.usbReadActive:
            accepted=self._control_edit(change)
            if accepted:self.flushControlView()
            return accepted
        clone=deepcopy(self.model);change(clone);clone.validate();self.model=clone
        self.notify('All outputs muted' if muted else 'All outputs unmuted');return True
    @Slot(int,int,float,float)
    def editPeqPoint(self,index,band,frequency,gain):
        if self.editingLocked:return
        if self.usbReadActive:
            self._control_edit(lambda m:m.set_peq_point(index,band,frequency,gain));return
        try:self.model.set_peq_point(index,band,frequency,gain);self.notify()
        except (ValueError,AttributeError,TypeError) as e:self.notify(str(e))
    @Slot(int,int,bool,float)
    def route(self,out,inp,enabled,gain):
        if self.editingLocked:return
        if self.usbReadActive:
            def change(m):m.routing[out][inp]=enabled;m.routing_gains[out][inp]=gain
            self._control_edit(change);return
        try:
            clone=DeviceModel.from_dict(self.model.to_dict());clone.routing[out][inp]=enabled;clone.routing_gains[out][inp]=gain;clone.validate();self.model=clone;self.notify()
        except (ValueError,IndexError) as e:self.notify(str(e))
    @Slot(int,bool)
    def link(self,index,value):
        if self.editingLocked:return
        if self.usbReadActive:return
        if 0<=index<12:
            if (index<4)!=(self._selected<4) or index==self._selected:return
            if hasattr(self.model,'device_link_masks'):del self.model.device_link_masks
            self._software_bypass.clear();self.model.links[index]=value
            scope=range(4) if self._selected<4 else range(4,12)
            self.model.links[self._selected]=any(self.model.links[i] for i in scope if i!=self._selected)
            self.notify('Linked edits are local DEMO only; FIR and names remain independent')
    @Slot(int)
    def copyTo(self,target):
        if self.editingLocked:return
        if self.usbReadActive:return
        try:
            self.model.copy_channel(self._selected,target)
            self._forget_copied_software_bypass([target],['delay','gate','compressor','limiter'])
            self.notify('Channel settings copied locally')
        except ValueError as e:self.notify(str(e))
    @Slot(int,int,bool,result=bool)
    def copyChannel(self,source,target,peq_only):
        if self.editingLocked:return False
        from dsp408.channel_copy import copy_parameters
        if self.usbReadActive:
            accepted=self._control_edit(lambda m:copy_parameters(m,source,target,peq_only))
            if accepted and not peq_only and self._forget_copied_software_bypass([target],['delay','gate','compressor','limiter']):self.notify()
            return accepted
        try:
            clone=DeviceModel.from_dict(self.model.to_dict());copy_parameters(clone,source,target,peq_only)
            self.model=clone
            if not peq_only:self._forget_copied_software_bypass([target],['delay','gate','compressor','limiter'])
            self.notify('PEQ copied' if peq_only else 'Channel parameters copied');return True
        except (ValueError,TypeError) as error:self.notify(str(error));return False
    @Slot(int,'QVariantList','QVariantList',result=bool)
    def copyChannelSections(self,source,targets,sections):
        if self.editingLocked:return False
        from dsp408.channel_copy import copy_sections
        if self.usbReadActive:
            accepted=self._control_edit(lambda m:copy_sections(m,source,targets,sections))
            if accepted and self._forget_copied_software_bypass(targets,sections):self.notify()
            return accepted
        try:
            clone=DeviceModel.from_dict(self.model.to_dict());copy_sections(clone,source,targets,sections)
            self.model=clone;self._forget_copied_software_bypass(targets,sections)
            self.notify('Selected channel settings copied');return True
        except (ValueError,TypeError) as error:self.notify(str(error));return False
    def _forget_copied_software_bypass(self,targets,sections):
        keys={'delay':'delay_ms','gate':'gate','compressor':'compressor','limiter':'limiter'}
        removed=False
        for target in targets:
            for section in sections:
                if section in keys:removed=self._software_bypass.invalidate(self.model,target,keys[section]) or removed
        return removed
    @Slot(str,'QVariant')
    def setting(self,key,value):
        if self.editingLocked:return
        if self.usbReadActive:
            if key=='delay_unit' and value in FACTORS:self.model.settings[key]=value;self.notify()
            return
        try:
            clone=DeviceModel.from_dict(self.model.to_dict())
            if key not in clone.settings:raise ValueError('Unknown setting')
            clone.settings[key]=value;clone.validate();self.model=clone;self.notify('Offline configuration saved locally - not applied to DSP')
        except ValueError as e:self.notify(str(e))
    @Slot(int,str,int)
    def setRatioIndex(self,index,section,position):
        if self.editingLocked:return
        if section not in ('compressor','limiter') or not 0<=position<=15:return
        if self.usbReadActive:
            def change(m):
                m.set_channel(index,section+'.ratio_limit',position==15)
                if position<15:m.set_channel(index,section+'.ratio',RATIO_VALUES[position])
            if self._control_edit(change) and self._software_bypass.invalidate(self.model,index,section):self.notify()
            return
        try:
            clone=DeviceModel.from_dict(self.model.to_dict())
            clone.set_channel(index,section+'.ratio_limit',position==15)
            if position<15:clone.set_channel(index,section+'.ratio',RATIO_VALUES[position])
            self.model=clone;self._software_bypass.invalidate(self.model,index,section);self.notify()
        except ValueError as e:self.notify(str(e))
    @Slot()
    def resetEQ(self):
        if self.editingLocked:return
        from dsp408.model import Channel
        default=Channel('reset').filters[:len(self.model.channels[self._selected].filters)]
        def reset(model):
            from dsp408.channel_link import members_for
            targets=members_for(model.device_link_masks,self._selected) if getattr(model,'device_link_masks',None) is not None else (self._selected,)
            for i in targets:model.channels[i].filters=deepcopy(default)
        if self.usbReadActive:
            self._control_edit(reset);return
        reset(self.model);self.notify('Selected channel EQ reset locally')
    @Slot(bool)
    def showPhase(self,value):self._phase=value;self.notify()
    @Slot(str,result=bool)
    def savePath(self,path):
        try:
            if self.usbReadActive and Path(path).suffix.lower()=='.prs':return self.exportUsbPrsPath(path)
            self.model.save(path)
            if self.usbReadActive:
                self.notify('UI snapshot saved locally; unread DSP fields/FIR data are not included')
            else:
                self._preset=Path(path).stem;self._active_slot=-1
                self._baseline=self.model.to_dict();self.notify('PRS saved locally · original opaque fields/FIR banks retained · no DSP write' if Path(path).suffix.lower()=='.prs' else 'Portable configuration saved · 12 channels and loaded FIR coefficients included · no DSP write')
            return True
        except (ValueError,OSError) as e:self.notify(str(e));return False
    @Slot(str,result=bool)
    def loadPath(self,path):
        if self.editingLocked:return False
        if self.usbReadActive:return False
        try:
            model=DeviceModel.load(path);self.remember_configuration();self.model=model;self._preset=Path(path).stem;self._active_slot=-1;self._baseline=model.to_dict();self.notify('PRS loaded offline · channel settings available · FIR banks and unrepresented globals retained raw' if self.prsActive else 'JSON preset loaded - offline state only');return True
        except (ValueError,OSError) as e:self.notify(str(e));return False
    @Slot(result=bool)
    def savePreset(self):
        title='Save configuration and FIR' if self.usbReadActive else 'Save portable configuration — computer or USB drive'
        filename='DSP408-configuration.prs' if self.usbReadActive or self.prsActive else 'DSP408-configuration.json'
        filters='Original editor preset (*.prs);;DSP408 configuration (*.json)' if self.prsActive or self.usbReadActive else 'DSP408 configuration (*.json);;Original editor preset (*.prs)'
        path,selected=QFileDialog.getSaveFileName(None,title,filename,filters)
        if path and Path(path).suffix.lower() not in ('.json','.prs'):path+='.prs' if '*.prs' in selected else '.json'
        return self.savePath(path) if path else False
    @Slot()
    def loadPreset(self):
        path,_=QFileDialog.getOpenFileName(None,'Load offline preset','','DSP408 configurations (*.prs *.json)')
        if path:self.loadPath(path)
    @Slot(result=str)
    def choosePresetPath(self):
        if self.usbReadActive:return ''
        path,_=QFileDialog.getOpenFileName(None,'Choose configuration — computer or USB drive','','DSP408 configurations (*.prs *.json)')
        return path
    @Property(bool,notify=changed)
    def prsActive(self):return not self.usbReadActive and bool(self.model.vendor_prs_hex)

    @Property('QVariantMap',notify=prsReviewChanged)
    def prsImportReview(self):return self._prs_review

    @Slot(str,result=bool)
    def previewPrsImportPath(self,path):
        self._prs_review={};self._usb_prs_candidate=None;self.prsReviewChanged.emit()
        try:
            hardware=self.usbReadActive
            if (hardware and not self.usbPresetRecallAvailable) or (not hardware and not self.prsActive):
                raise ValueError('PRS comparison requires an offline PRS configuration; it cannot use a partial DSP snapshot')
            from dsp408.prs import to_bytes,from_bytes,SIZE,FIR_START,FIR_END
            with Path(path).open('rb') as stream:target=stream.read(SIZE+1)
            wanted=from_bytes(target)
            if hardware:
                if self._usb_fir_bank is None:
                    self._prepare_current_fir('prs_import',(path,));return False
                from dsp408.prs_full_import import prepare_full_import
                self._usb_prs_candidate,report=prepare_full_import(self._usb_raw_state,self._usb_fir_bank,target)
            else:
                before=to_bytes(self.model)
                from dsp408.prs_full_import import prepare_full_import
                _,report=prepare_full_import(b'\xff\xff'+before[16:FIR_START],before[FIR_START:FIR_END],target)
            labels={0x30:'Compressor',0x31:'LPF',0x32:'HPF',0x33:'PEQ',0x34:'Gain',
                    0x35:'Mute',0x36:'Polarity',0x38:'Delay',0x3A:'Routing',0x3D:'Channel name',
                    0x3E:'Gate',0x3F:'Limiter',0x41:'Mix',0x5B:'FIR name',0x3B:'Channel Link',0x4E:'FIR coefficients',0x58:'FIR clear',0x4B:'FIR crossover',0x4C:'Crossover mode',0x4F:'FIR bypass'}
            groups={};name_changed=False
            for packet in report['packets']:
                op=int(packet['command'],16)
                if op==0x26:name_changed=True;continue
                if op==0x58:continue
                ch=bytes.fromhex(packet['payload_hex'])[0]
                groups.setdefault(ch,set()).add(labels[op])
            for ch in report.get('fir_channels',[]):groups.setdefault(ch,set()).add('FIR coefficients')
            rows=[{'channel':('IN '+chr(65+ch) if ch<4 else 'OUT '+str(ch-3)),
                   'name':self.model.channels[ch].name,'functions':', '.join(sorted(functions))}
                  for ch,functions in sorted(groups.items())]
            for row,ch in zip(rows,sorted(groups)):
                a,b=self.model.channels[ch],wanted.channels[ch];details=[]
                if a.gain!=b.gain:details.append(f'Gain: {a.gain:+.1f} → {b.gain:+.1f} dB')
                if a.delay_ms!=b.delay_ms:details.append(f'Delay: {a.delay_ms:.3f} → {b.delay_ms:.3f} ms')
                if a.mute!=b.mute:details.append('Mute: '+('On' if a.mute else 'Off')+' → '+('On' if b.mute else 'Off'))
                row['details']=' · '.join(details)
            self._prs_review={'file':Path(path).name,'scope':'Configuration and FIR' if hardware else 'Offline configuration comparison · no DSP connection',
                'complete':report['source_plan_complete'],'hardware_enabled':False,'channels':rows,
                'hardware_review':hardware,
                'name_changed':name_changed,'fir_different_bytes':report['fir_different_bytes'],
                'blockers':[b['path']+': '+b['reason'] for b in report['blockers']],
                'packet_count':len(report['packets'])}
            self.prsReviewChanged.emit();return True
        except (ValueError,OSError) as e:self.notify(str(e));return False

    @Slot(result=bool)
    def choosePrsImportReview(self):
        if not (self.prsActive or self.usbPresetRecallAvailable):return False
        path,_=QFileDialog.getOpenFileName(None,'Import configuration and FIR' if self.usbReadActive else 'Compare PRS with current offline configuration','','Original editor preset (*.prs)')
        return self.previewPrsImportPath(path) if path else False

    @Property(bool,constant=True)
    def usbFirTrialAuthorized(self):
        from dsp408.fir_usb_trial import FIR_TRIAL_AUTHORIZED
        return FIR_TRIAL_AUTHORIZED

    @Property(bool,constant=True)
    def usbInputFirAuthorized(self):
        from dsp408.fir_usb_import import FIR_IMPORT_AUTHORIZED
        return FIR_IMPORT_AUTHORIZED

    @Property(bool,notify=presetRecallStateChanged)
    def usbInputFirAvailable(self):
        return self._selected<4 and self.usbPresetRecallAvailable and (self._usb_fir_bank is not None or self.usbControlReady and hasattr(self._usb_worker,'request_fir_read'))

    def _prepare_current_fir(self,kind,args):
        if self._usb_fir_bank is not None or not self.usbControlReady:return False
        if not hasattr(self._usb_worker,'request_fir_read'):
            self.notify('Complete FIR read is unavailable for this connection');return False
        if not self._usb_worker.request_fir_read():
            self.notify('Wait for current settings to finish applying');return False
        self._pending_fir_action=(self._selected,self._usb_raw_state,kind,args)
        self._usb_recall_progress={'busy':True,'operation':'fir_read','stage':'Reading FIR storage','done':0,'total':1325,'waiting':False}
        self._usb_telemetry=None;self._clear_usb_meters();self.notify('Reading FIR storage before review')
        return True

    @Property('QVariantMap',notify=outputFirReviewChanged)
    def outputFirReview(self):return self._output_fir_review

    @Slot('QVariantMap',result=bool)
    def reviewOutputFir(self,settings):
        self._output_fir_candidate=None;self._output_fir_review={};self.outputFirReviewChanged.emit()
        if self._selected<4 or not self.usbControlReady or not self.usbPresetRecallAvailable:return False
        settings=dict(settings)
        taps=settings.get('taps')
        if type(taps) in (int,float) and math.isfinite(taps) and taps==int(taps):settings['taps']=int(taps)
        if self._usb_fir_bank is None:
            self._prepare_current_fir('output_design',(settings,));return False
        try:
            from dsp408.output_fir import prepare_output_permit
            from dsp408.fir_usb_import import resource_usage
            p=prepare_output_permit(self._usb_raw_state,self._usb_fir_bank,self._selected,settings)
            self._output_fir_candidate=p
            from dsp408.channel_link import validate_group_state,members_for
            affected=members_for(validate_group_state(p.state),self._selected)
            self._output_fir_review={**settings,'channel':' + '.join('OUT '+str(i-3) for i in affected),
                'used':resource_usage(p.plan.expected_state),'replaces_storage':bool(p.plan.sector_indices),
                'total':len(p.requests)}
            self.outputFirReviewChanged.emit();return True
        except (ValueError,TypeError) as error:self.notify(str(error));return False

    @Slot(result=bool)
    def applyOutputFir(self):
        p=self._output_fir_candidate
        if p is None or not self.usbControlReady or self._selected!=p.plan.channel:return False
        if p.state!=self._usb_raw_state or p.plan.bank!=self._usb_fir_bank:
            self.notify('DSP changed since review; review crossover again');return False
        try:
            if not self._usb_worker.request_output_fir(p.state,p.plan.bank,p.plan.channel,dict(p.plan.settings)):return False
        except (ValueError,AttributeError) as error:self.notify(str(error));return False
        self._output_fir_candidate=None;self._ethernet_fir_preview=None
        self._usb_recall_progress={'busy':True,'operation':'output_fir','stage':'Applying output FIR crossover',
            'done':0,'total':len(p.requests),'waiting':False}
        self._usb_telemetry=None;self._clear_usb_meters();self.notify('Applying output FIR crossover');return True

    @Property('QVariantMap',notify=firImportReviewChanged)
    def firImportReview(self):return self._fir_import_review

    @Property('QVariantList',notify=changed)
    def usbInputFirCoefficients(self):
        if self._ethernet_fir_preview is not None:
            if not self.usbReadConnected:return []
            from dsp408.fir_read_preview import coefficients
            return coefficients(self._ethernet_fir_preview,self._usb_raw_state,self._selected)
        if self._selected>=4 or self._usb_fir_bank is None or self._usb_raw_state is None:return []
        signature=(self._selected,self._usb_raw_state,self._usb_fir_bank)
        if self._usb_fir_coefficients_cache[0]==signature:return self._usb_fir_coefficients_cache[1][:]
        import struct
        from dsp408.source_session import SourceDocument
        count=SourceDocument(self._usb_raw_state).decoded()['channels'][self._selected]['fir_coefficient_count_raw']
        if not 1<=count<=2048:
            self._usb_fir_coefficients_cache=(signature,[]);return []
        raw=self._usb_fir_bank[self._selected*8192:self._selected*8192+count*4]
        values=struct.unpack('<'+'f'*count,raw)
        values=list(values) if all(math.isfinite(v) for v in values) else []
        self._usb_fir_coefficients_cache=(signature,values)
        return values[:]

    def _review_input_fir(self,coefficients,bypass,label,clear=False):
        self._usb_input_fir_candidate=None;self._fir_import_review={}
        if not self.usbInputFirAvailable:return False
        if self._usb_fir_bank is None:
            self._prepare_current_fir('review',(coefficients,bypass,label,clear));return False
        from dsp408.fir_usb_import import prepare_import,resource_usage,available_input_taps
        try:
            candidate=prepare_import(self._usb_raw_state,self._usb_fir_bank,self._selected,coefficients,bypass,clear)
            self._usb_input_fir_candidate=candidate
            from dsp408.channel_link import validate_group_state,members_for
            affected=members_for(validate_group_state(candidate.state),self._selected)
            self._fir_import_review={'file':label,'channel':' + '.join('IN '+chr(65+i) for i in affected),
                'count':0 if clear else len(candidate.plan.coefficients) if coefficients is not None else len(self.usbInputFirCoefficients),
                'bypass':bypass,'upload':coefficients is not None,'clear':clear,
                'available':available_input_taps(candidate.state,self._selected),
                'used':resource_usage(candidate.plan.expected_state),'total':len(candidate.requests)}
            self.firImportReviewChanged.emit();return True
        except ValueError as error:self.notify(str(error));return False

    @Slot(str,result=bool)
    def previewUsbInputFirPath(self,path):
        from dsp408.fir_usb_import import INPUT_UPLOAD_LIMIT
        self._usb_input_fir_candidate=None;self._fir_import_review={};self.firImportReviewChanged.emit()
        try:values=parse_coefficients(path,INPUT_UPLOAD_LIMIT)
        except (ValueError,OSError,UnicodeError) as error:self.notify(str(error));return False
        return self._review_input_fir(values,False,Path(path).name)

    @Slot(result=bool)
    def chooseUsbInputFir(self):
        if not self.usbInputFirAvailable:return False
        path,_=QFileDialog.getOpenFileName(None,'Load FIR on selected input','','FIR (*.csv *.txt)')
        return self.previewUsbInputFirPath(path) if path else False

    @Slot(bool,result=bool)
    def reviewUsbInputFirBypass(self,bypass):
        return self._review_input_fir(None,bypass,'Stored input FIR')

    @Slot(bool,result=bool)
    def requestUsbFirBypass(self,bypass):
        if not self.usbFirBypassAvailable:return False
        return self._request_channel_fir_bypass(self._selected,bypass)

    def _request_channel_fir_bypass(self,index,bypass):
        if type(index) is not int or not 0<=index<4 or type(bypass) is not bool or not self.usbInputFirAuthorized or not self.usbControlReady:return False
        if not bypass:
            if self._usb_fir_bank is None and hasattr(self._usb_worker,'request_fir_read'):
                return self._prepare_current_fir('overview_bypass',(index,bypass))
            from dsp408.fir_usb_import import prepare_input_fir
            try:
                from dsp408.channel_link import masks,self_mask,validate_input_activation
                if masks(self._usb_raw_state)==tuple(self_mask(i) for i in range(12)):
                    prepare_input_fir(self._usb_raw_state,self._usb_fir_bank,index,None,False)
                else:validate_input_activation(self._usb_raw_state,self._usb_fir_bank,index)
            except (ValueError,TypeError) as error:self.notify(str(error));return False
        accepted=self._control_edit(lambda m:m.set_channel(index,'fir.bypass',bypass,-1))
        if accepted:self.flushControlView()
        return accepted

    @Property(bool,notify=changed)
    def usbFirBypassAvailable(self):
        return self._selected<4 and self.usbInputFirAuthorized and self.usbControlReady

    @Slot(result=bool)
    def reviewUsbClearFir(self):
        return self._review_input_fir(None,True,'Clear stored input FIR',True)

    @Slot(result=bool)
    def requestUsbInputFir(self):
        p=self._usb_input_fir_candidate
        if not self.usbInputFirAuthorized or not self.usbInputFirAvailable or p is None:return False
        if p.state!=self._usb_raw_state or p.plan.bank!=self._usb_fir_bank or p.plan.channel!=self._selected:
            self.notify('DSP or selected channel changed since FIR review; review again');return False
        try:
            args=(p.state,p.plan.bank,p.plan.channel,p.plan.coefficients,p.plan.bypass)
            if not self._usb_worker.request_input_fir(*args,**({'clear':True} if p.plan.clear else {})):return False
        except ValueError as error:self.notify(str(error));return False
        self._usb_input_fir_candidate=None
        self._usb_recall_progress={'busy':True,'operation':'fir_import','stage':'Preparing input FIR',
                                  'done':0,'total':len(p.requests),'waiting':False}
        self._usb_telemetry=None;self._clear_usb_meters();self.notify('Applying input FIR · settings locked');return True

    @Slot(result=bool)
    def reviewUsbFirTrial(self):
        self._usb_fir_trial_candidate=None
        if self._connection_transport!='usb':return False
        if not self.usbPresetRecallAvailable:return False
        from dsp408.fir_usb_trial import prepare_fir_trial
        try:self._usb_fir_trial_candidate=prepare_fir_trial(self._usb_raw_state)
        except ValueError as error:self.notify(str(error));return False
        return True

    @Slot(result=bool)
    def requestUsbFirTrial(self):
        if self._connection_transport!='usb':return False
        if not self.usbFirTrialAuthorized or not self.usbPresetRecallAvailable:return False
        candidate=getattr(self,'_usb_fir_trial_candidate',None)
        if candidate is None:return False
        if candidate.state!=self._usb_raw_state:
            self.notify('DSP parameters changed since FIR review; open a fresh review');return False
        try:
            if not self._usb_worker.request_fir_trial(candidate.state):return False
        except ValueError as error:self.notify(str(error));return False
        self._usb_fir_trial_candidate=None
        self._usb_recall_progress={'busy':True,'operation':'fir_trial','stage':'Preparing IN A identity FIR256 trial',
                                   'done':0,'total':len(candidate.requests),'waiting':False}
        self._usb_telemetry=None;self._clear_usb_meters()
        self.notify('IN A FIR trial · settings locked until full readback completes')
        return True

    @Property(bool,constant=True)
    def usbPrsImportAuthorized(self):
        from dsp408.prs_usb_import import PRS_IMPORT_AUTHORIZED
        return PRS_IMPORT_AUTHORIZED

    @Property(bool,notify=prsReviewChanged)
    def prsHardwareReview(self):return bool(self._prs_review.get('hardware_review'))

    @Slot(result=bool)
    def requestUsbPrsImport(self):
        if not self.usbPrsImportAuthorized:return False
        if not self.usbPresetRecallAvailable or self._usb_prs_candidate is None:return False
        candidate=self._usb_prs_candidate
        if candidate.state!=self._usb_raw_state:
            self.notify('DSP parameters changed since PRS review; open a fresh review');return False
        try:
            if candidate.bank!=self._usb_fir_bank:
                self.notify('FIR changed since PRS review; open a fresh review');return False
            if not self._usb_worker.request_prs_import(candidate.state,candidate.prs,candidate.bank):return False
        except ValueError as error:self.notify(str(error));return False
        self._usb_prs_candidate=None
        self._usb_recall_progress={'busy':True,'operation':'prs_import','stage':'Preparing PRS import',
                                  'done':0,'total':len(candidate.requests),'waiting':False}
        self._usb_telemetry=None;self._clear_usb_meters();self.notify('Importing configuration and FIR · settings locked')
        return True
    @Slot(str,result=bool)
    def importPath(self,path):
        if self.editingLocked:return False
        if self.usbReadActive:return False
        try:
            c=self.model.channels[self._selected]
            if self._selected>=4 and (c.crossover_mode!='FIR' or c.fir.mode!='External FIR'):raise ValueError('Output import: select FIR crossover mode and External FIR type first')
            maximum=512 if self._selected<4 else 1024;values=parse_coefficients(path,maximum)
            clone=DeviceModel.from_dict(self.model.to_dict())
            from dsp408.channel_link import members_for
            for target in members_for(clone.link_masks(),self._selected):
                f=clone.channels[target].fir;f.path=path;f.coefficients=list(values);f.mode='External FIR'
            clone.validate();self.model=clone;self.notify(f'{len(values)} coefficients imported locally; no upload');return True
        except (ValueError,OSError,UnicodeError) as e:self.notify(str(e));return False
    @Slot()
    def importFIR(self):
        if self.editingLocked:return
        path,_=QFileDialog.getOpenFileName(None,'Import offline FIR coefficients','','FIR (*.csv *.txt)')
        if path:self.importPath(path)
    @Slot()
    def clearFIR(self):
        if self.editingLocked:return
        if self.usbReadActive:return
        from dsp408.channel_link import members_for
        clone=DeviceModel.from_dict(self.model.to_dict())
        for target in members_for(clone.link_masks(),self._selected):
            c=clone.channels[target];c.fir.coefficients=[];c.fir.path='';c.fir.bypass=True
        clone.validate();self.model=clone;self.notify('FIR coefficients removed locally')
    @Slot(int)
    def storeSlot(self,slot):
        if self.editingLocked:return
        self.storeNamedSlot(slot,self._slot_names.get(slot,f'Config {slot+1:02d}'))
    @Slot(int,str)
    def storeNamedSlot(self,slot,name):
        if self.editingLocked:return
        if self.usbReadActive:return
        if not 0<=slot<20:return
        self.bank[slot]=self.model.to_dict();self._slot_names[slot]=name.strip()[:14].rstrip() or f'Config {slot+1:02d}'
        self._active_slot=slot;self._preset=f'U{slot+1:02d} - '+self._slot_names[slot];self._baseline=self.model.to_dict();self.notify('Configuration stored in session memory; export JSON to keep it after exit')
    @Slot(int)
    def recallSlot(self,slot):
        if self.editingLocked:return
        if self.usbReadActive:return
        if slot in self.bank:
            self.remember_configuration();self.model=DeviceModel.from_dict(self.bank[slot]);self._active_slot=slot;self._preset=f'U{slot+1:02d} - '+self._slot_names.get(slot,f'Config {slot+1:02d}');self._baseline=self.model.to_dict();self.notify('Configuration applied to all 12 channels locally')
        else:self.notify('Empty DEMO slot; use Store first. Export JSON to retain after exit.')
    def remember_configuration(self):
        self._software_bypass.clear()
        from copy import deepcopy
        self._previous_configuration=(self.model.to_dict(),self._preset,self._active_slot,deepcopy(self._baseline))
    @Slot()
    def undoConfigurationSwitch(self):
        if self.editingLocked:return
        if self.usbReadActive:return
        if self._previous_configuration is None:return
        state,name,slot,baseline=self._previous_configuration;self.remember_configuration()
        self.model=DeviceModel.from_dict(state);self._preset=name;self._active_slot=slot;self._baseline=baseline;self.notify('Previous configuration restored; the other snapshot and its edits remain available')
    def update_meters(self):
        if self.usbReadActive:
            if self._usb_telemetry is not None and time.monotonic()-self._usb_last>2.:
                self._usb_telemetry=None;self._clear_usb_meters()
                self._usb_status='USB telemetry stale';self.changed.emit();self.statusChanged.emit()
            elif self._usb_telemetry is not None:
                for i,db in enumerate(self._output_db):
                    if self._peak_hold[i]>0:self._peak_hold[i]-=1
                    else:self._peaks[i]=max(db,self._peaks[i]-.3)
                self.metersChanged.emit()
            return
