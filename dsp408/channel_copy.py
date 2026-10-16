"""Copy supported parameter families without aliasing channel storage/globals."""
from copy import deepcopy


COMMON_SECTIONS = {
    'gain': ('gain',), 'mute': ('mute',), 'polarity': ('polarity_inverted',),
    'delay': ('delay_ms',), 'peq': ('filters', 'eq_bypass'),
}
INPUT_SECTIONS = {'gate': ('gate',), 'compressor': ('compressor',)}
OUTPUT_SECTIONS = {
    'crossover': ('hpf_hz', 'hpf_type', 'hpf_bypass', 'lpf_hz', 'lpf_type', 'lpf_bypass'),
    'limiter': ('limiter',),
}


def copy_sections(model,source,targets,sections):
    """Validate the whole selection before changing any destination on a clone."""
    if (type(source) is not int or not 0<=source<12 or not isinstance(targets,(list,tuple))
            or not targets or any(type(t) is not int or not 0<=t<12 or t==source
                                 or (t<4)!=(source<4) for t in targets)
            or len(set(targets))!=len(targets)):
        raise ValueError('Choose a different channel in the same input/output group.')
    allowed={**COMMON_SECTIONS,**(INPUT_SECTIONS if source<4 else OUTPUT_SECTIONS)}
    if (not isinstance(sections,(list,tuple)) or not sections
            or any(type(s) is not str or s not in allowed for s in sections)
            or len(set(sections))!=len(sections)):
        raise ValueError('Choose at least one supported parameter section.')
    fields=[field for section in sections for field in allowed[section]]
    # FIR, names, Link, DEQ, routing/mix and global settings stay independent.
    if getattr(model,'device_link_masks',None) is not None:
        from dsp408.channel_link import members_for
        targets=sorted({i for target in targets for i in members_for(model.device_link_masks,target)})
    values={field:deepcopy(getattr(model.channels[source],field)) for field in fields}
    for target in targets:
        for field in fields:
            setattr(model.channels[target],field,deepcopy(values[field]))
    model.validate()


def copy_parameters(model,source,target,peq_only=False):
    if type(peq_only) is not bool:raise ValueError('Choose channel settings or PEQ only.')
    sections=['peq'] if peq_only else list(COMMON_SECTIONS)+list(INPUT_SECTIONS if type(source) is int and source<4 else OUTPUT_SECTIONS)
    copy_sections(model,source,[target],sections)
