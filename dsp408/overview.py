"""Local configuration summary; configured blocks are not hardware activity."""
def channel_summary(model,index,software_bypass=(),fir_state=None):
    c=model.channels[index];input_channel=index<4
    def block(label,enabled,tab,detail,pending=False):
        token=label.split()[0]
        key={'EQ':'eq_bypass','HPF':'hpf_bypass','LPF':'lpf_bypass','Ø':'polarity_inverted'}.get(token)
        if token=='FIR' and input_channel:key='fir.bypass'
        software_supported=token in ('GATE','COMP','LIM','DLY')
        software_active=(index,token) in software_bypass
        bypassed=c.fir.bypass if key=='fir.bypass' else getattr(c,key) if key else None
        if software_supported:bypassed=software_active
        if software_active:enabled=False;detail+=' · software bypass · saved settings available'
        display_bypassed=software_active or token in ('EQ','HPF','LPF') and bool(bypassed)
        if token=='FIR':display_bypassed=(c.fir.bypass and fir_ready and not fir_empty) if input_channel else fir_selected and (c.fir.bypass or c.fir.mode=='BYPASS')
        return {'label':label,'enabled':enabled,'tab':tab,'detail':detail,'pending':pending,
                'action':token,'toggle_key':key or '', 'bypassed':bypassed,
                'software_supported':software_supported,'software_bypassed':software_active,
                'display_bypassed':display_bypassed}
    count=sum(f.enabled for f in c.filters)
    blocks=[block(f'EQ {count}',not c.eq_bypass and count>0,1,'Enabled PEQ bands; a zero-gain Bell can have a flat response')]
    if input_channel:
        blocks.extend([block('GATE',c.gate.threshold>-90,4,f'Threshold {c.gate.threshold:g} dB; default -90 dB remains stored'),
                       block('COMP',c.compressor.ratio_limit or c.compressor.ratio>1,5,f'Threshold {c.compressor.threshold:g} dB; ratio '+('Limit' if c.compressor.ratio_limit else f'{c.compressor.ratio:g}:1'))])
    elif c.crossover_mode=='IIR':
        blocks.extend([block('HPF',not c.hpf_bypass,2,f'{c.hpf_hz:g} Hz · {c.hpf_type}'),block('LPF',not c.lpf_bypass,2,f'{c.lpf_hz:g} Hz · {c.lpf_type}')])
    blocks.append(block('DLY',c.delay_ms>0,3,f'{c.delay_ms:g} ms'))
    fir_selected=input_channel or c.crossover_mode=='FIR'
    fir_ready=bool(c.fir.coefficients) if input_channel else c.fir.mode=='External FIR' and bool(c.fir.coefficients)
    if fir_state is not None:fir_ready=fir_state['ready']
    fir_empty=(fir_state.get('empty',False) if fir_state is not None else not c.fir.coefficients) if input_channel else False
    fir_requested=fir_selected and not fir_empty and not c.fir.bypass and (input_channel or c.fir.mode!='BYPASS')
    if input_channel:
        count=fir_state['count'] if fir_state is not None else len(c.fir.coefficients)
        fir_detail='No FIR loaded' if fir_empty else ('FIR bypassed' if c.fir.bypass else 'FIR enabled')+' · '+(f'{count} coefficients' if fir_ready else 'coefficients unavailable')
    elif not fir_selected:fir_detail='IIR crossover selected · FIR inactive · editor in XOVER'
    else:fir_detail=f'{c.fir.mode} · '+('bypassed' if c.fir.bypass or c.fir.mode=='BYPASS' else 'FIR crossover · editor in XOVER')
    blocks.append(block('FIR',fir_requested and fir_ready,7 if input_channel else 2,
        fir_detail,fir_requested and not fir_ready))
    if not input_channel:blocks.append(block('LIM',c.limiter.ratio_limit or c.limiter.ratio>1,6,f'Threshold {c.limiter.threshold:g} dB; ratio '+('Limit' if c.limiter.ratio_limit else f'{c.limiter.ratio:g}:1')))
    blocks.append(block('Ø',c.polarity_inverted,0,'Polarity inverted' if c.polarity_inverted else 'Normal polarity'))
    routes=[f'OUT {out+1}' for out in range(8) if model.routing[out][index]] if input_channel else [f'IN {chr(65+inp)} ({model.routing_gains[index-4][inp]:g} dB)' for inp in range(4) if model.routing[index-4][inp]]
    return {'index':index,'name':c.name,'label':f'IN {chr(65+index)}' if input_channel else f'OUT {index-3}',
            'mute':c.mute,'gain':c.gain,'blocks':blocks,'routing':', '.join(routes) or 'No route',
            'crossover':c.crossover_mode if not input_channel else 'INPUT'}
