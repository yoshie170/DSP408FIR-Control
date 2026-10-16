"""Exact typed authorization for PRS imports and the separate fixed FIR trial."""

def verify_permit(permit, *, reconstruct=False):
    from dsp408 import prs_usb_import, fir_usb_trial, fir_usb_import
    from dsp408 import output_fir
    from dsp408 import channel_link
    from dsp408 import prs_full_import
    from dsp408 import preset_bank
    from dsp408 import preset_bank_restore
    if type(permit) is preset_bank_restore.BankRestorePermit:
        if reconstruct:canonical=preset_bank_restore.prepare_restore(permit.state,permit.bank,permit.catalog,permit.active,permit.names,permit.records,permit.banks)
    elif type(permit) is preset_bank.BankBackupPermit:
        if reconstruct:canonical=preset_bank.prepare_backup(permit.state,permit.bank,permit.catalog,permit.active,permit.names,permit.extended)
    elif type(permit) is prs_full_import.FullPrsPermit:
        if not prs_usb_import.PRS_IMPORT_AUTHORIZED:raise ValueError(prs_usb_import.BLOCK_REASON)
        if reconstruct:canonical=prs_full_import.prepare_full_import(permit.state,permit.bank,permit.prs)[0]
    elif type(permit) is prs_usb_import.ImportPermit:
        if not prs_usb_import.PRS_IMPORT_AUTHORIZED:
            raise ValueError(prs_usb_import.BLOCK_REASON)
        if reconstruct:
            canonical,_=prs_usb_import.prepare_import(permit.state,permit.prs)
    elif type(permit) is fir_usb_trial.FirTrialPermit:
        if not fir_usb_trial.FIR_TRIAL_AUTHORIZED:
            raise ValueError(fir_usb_trial.BLOCK_REASON)
        if reconstruct:canonical=fir_usb_trial.prepare_fir_trial(permit.state)
    elif type(permit) is fir_usb_import.InputFirPermit:
        if not fir_usb_import.FIR_IMPORT_AUTHORIZED:
            raise ValueError(fir_usb_import.BLOCK_REASON)
        if reconstruct:
            p=permit.plan
            canonical=fir_usb_import.prepare_import(p.state,p.bank,p.channel,p.coefficients,p.bypass,p.clear)
    elif type(permit) is output_fir.OutputFirPermit:
        if not output_fir.OUTPUT_FIR_AUTHORIZED:raise ValueError('Output FIR authorization disabled')
        if reconstruct:
            p=permit.plan;canonical=output_fir.prepare_output_permit(p.state,p.bank,p.channel,dict(p.settings))
    elif type(permit) is channel_link.LinkPermit:
        if reconstruct:canonical=channel_link.prepare_link(permit.state,permit.bank,permit.selected,permit.members)
    else:
        raise ValueError('Unsupported USB transaction permit type')
    if reconstruct and permit!=canonical:
        raise ValueError('USB transaction permit differs from canonical plan')
