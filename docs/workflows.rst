.. include:: links.rst


=============
BOLD Workflow
=============

.. workflow::
    :graph2use: orig
    :simple_form: yes

    import os

    from pkg_resources import resource_filename as pkgrf

    from xcp_d.utils.bids import collect_data, extract_t1w_seg, select_registrationfile
    from xcp_d.workflow.bold import init_boldpostprocess_wf

    fmri_dir = pkgrf('xcp_d', 'data/fmriprep')
    layout,subj_data = collect_data(
        bids_dir=fmri_dir,
        participant_label='sub-colornest001',
        task='rest',
        bids_validate=False,
    )

    bold_file = pkgrf(
        'xcp_d',
        'data/fmriprep/sub-colornest001/ses-1/func/sub-colornest001_ses-1_task-rest_run-1_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz',
    )
    custom_confounds = pkgrf(
        'xcp_d',
        'data/fmriprep/sub-colornest001/ses-1/func/sub-colornest001_ses-1_task-rest_run-1_desc-confounds_timeseries.tsv',
    )

    tseg = pkgrf('xcp_d','data/fmriprep/sub-colornest001/ses-1/anat/sub-colornest001_ses-1_rec-refaced_desc-preproc_T1w.nii.gz')
    t1w = pkgrf('xcp_d','data/fmriprep/sub-colornest001/ses-1/anat/sub-colornest001_ses-1_rec-refaced_dseg.nii.gz')

    wf = init_boldpostprocess_wf(
        bold_file=str(bold_file),
        bandpass_filter=True,
        upper_bpf=0.08,
        lower_bpf=0.01,
        bpf_order=2,
        motion_filter_order=4,
        motion_filter_type='notch',
        band_stop_min=0.,
        band_stop_max=0.,
        smoothing=6,
        head_radius=50.,
        params='27P',
        custom_confounds=custom_confounds,
        omp_nthreads=1,
        dummytime=0,
        output_dir='output_dir',
        fd_thresh=0.2,
        n_runs=1,
        layout=layout,
        despike=False,
        name='bold_postprocess_wf',
    )
    wf.inputs.inputnode.t1w = t1w
    wf.inputs.inputnode.t1seg = tseg
