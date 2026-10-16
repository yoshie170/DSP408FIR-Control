"""Session-local parameter substitution requested by user; never a DSP bypass flag."""
from copy import deepcopy
from dataclasses import asdict
from dsp408.editor_profile import RATIO_VALUES

SPECS={
    'GATE':('gate',{'threshold':-90.}),
    'COMP':('compressor',{'ratio':RATIO_VALUES[0],'ratio_limit':False,'threshold':20.}),
    'LIM':('limiter',{'ratio':RATIO_VALUES[0],'ratio_limit':False,'threshold':20.}),
    'DLY':(None,{'delay_ms':0.}),
}


def targets(model,index):
    if getattr(model,'device_link_masks',None) is not None:
        from dsp408.channel_link import members_for
        return list(members_for(model.device_link_masks,index))
    if not model.links[index]:return [index]
    return [i for i in (range(4) if index<4 else range(4,12)) if model.links[i]]


def snapshot(model,index,action):
    section,_=SPECS[action];channel=model.channels[index]
    return asdict(getattr(channel,section)) if section else {'delay_ms':channel.delay_ms}


class SoftwareBypass:
    def __init__(self):self.entries={}
    def clear(self):self.entries.clear()
    def reconcile(self,model):
        self.entries={key:value for key,value in self.entries.items()
                      if snapshot(model,*key)==value['expected']}
    def invalidate(self,model,index,key):
        action=next((action for action,(section,_) in SPECS.items()
                     if key=='delay_ms' and action=='DLY' or section and (key==section or key.startswith(section+'.'))),None)
        if action is None:return False
        removed=False
        for target in targets(model,index):removed=self.entries.pop((target,action),None) is not None or removed
        return removed
    def plan(self,model,index,action):
        if type(index) is not int or not 0<=index<12 or action not in SPECS or (action in ('GATE','COMP') and index>=4) or (action=='LIM' and index<4):
            raise ValueError('Invalid software bypass block')
        clone=deepcopy(model)
        entries={key:deepcopy(value) for key,value in self.entries.items() if snapshot(model,*key)==value['expected']}
        restoring=(index,action) in entries
        section,neutral=SPECS[action]
        for target in targets(model,index):
            obj=getattr(clone.channels[target],section) if section else clone.channels[target]
            key=(target,action)
            if restoring:
                previous=entries.pop(key,None)
                if previous is None:continue
                values=previous['saved']
            else:
                values=neutral
                entries[key]={'saved':{field:deepcopy(getattr(obj,field)) for field in neutral}}
            for field,value in values.items():setattr(obj,field,deepcopy(value))
            if not restoring:entries[key]['expected']=snapshot(clone,target,action)
        clone.validate()
        return clone,entries
