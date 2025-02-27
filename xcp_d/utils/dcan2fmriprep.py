# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Functions for converting DCAN-format derivatives to fMRIPrep format."""
import glob
import json
import os
import re

import nibabel as nb
import numpy as np
import pandas as pd
from nilearn.input_data import NiftiMasker


def dcan2fmriprep(dcandir, outdir, sub_id=None):
    """Loop over all subjects in dcan dir and convert to fmriprep format."""
    dcandir = os.path.abspath(dcandir)
    outdir = os.path.abspath(outdir)
    if sub_id is None:
        sub_idir = glob.glob(dcandir + '/sub*')
        sub_id = [os.path.basename(j) for j in sub_idir]
        if len(sub_id) == 0:
            raise ValueError(f'No subject found in {dcandir}')
        elif len(sub_id) > 0:
            for j in sub_id:
                dcan2fmriprepx(dcan_dir=dcandir, out_dir=outdir, sub_id=j)
    else:
        dcan2fmriprepx(dcan_dir=dcandir, out_dir=outdir, sub_id=str(sub_id))
    return sub_id


def dcan2fmriprepx(dcan_dir, out_dir, sub_id):
    """Convert dcan data to fmriprep format."""
    # get session id if available
    sess = glob.glob(dcan_dir + '/' + sub_id + '/s*')
    ses_id = []
    ses_id = [j.split('ses-')[1] for j in sess]

    # anat dirx

    for ses in ses_id:

        anat_dirx = dcan_dir + '/' + sub_id + '/ses-' + ses + '/files/MNINonLinear/'
        anatdir = out_dir + '/' + sub_id + '/ses-' + ses + '/anat/'
        os.makedirs(anatdir, exist_ok=True)
        sess = 'ses-' + ses
        tw1 = anat_dirx + '/T1w.nii.gz'
        brainmask = anat_dirx + '/brainmask_fs.nii.gz'
        ribbon = anat_dirx + '/ribbon.nii.gz'
        segm = anat_dirx + '/aparc+aseg.nii.gz'

        midR = glob.glob(
            anat_dirx
            + '/fsaverage_LR32k/*R.midthickness.32k_fs_LR.surf.gii')[0]
        midL = glob.glob(
            anat_dirx
            + '/fsaverage_LR32k/*L.midthickness.32k_fs_LR.surf.gii')[0]
        infR = glob.glob(anat_dirx
                         + '/fsaverage_LR32k/*R.inflated.32k_fs_LR.surf.gii')[0]
        infL = glob.glob(anat_dirx
                         + '/fsaverage_LR32k/*L.inflated.32k_fs_LR.surf.gii')[0]

        pialR = glob.glob(anat_dirx
                          + '_/fsaverage_LR32k/*R.pial.32k_fs_LR.surf.gii')[0]
        pialL = glob.glob(anat_dirx
                          + '/fsaverage_LR32k/*L.pial.32k_fs_LR.surf.gii')[0]

        whiteR = glob.glob(anat_dirx
                           + '/fsaverage_LR32k/*R.white.32k_fs_LR.surf.gii')[0]
        whiteL = glob.glob(anat_dirx
                           + '/fsaverage_LR32k/*L.white.32k_fs_LR.surf.gii')[0]

        dcanimages = [
            tw1, segm, ribbon, brainmask, tw1, tw1, midL, midR, pialL, pialR,
            whiteL, whiteR, infL, infR
        ]

        t1wim = anatdir + sub_id + '_' + sess + '_desc-preproc_T1w.nii.gz'
        t1seg = anatdir + sub_id + '_' + sess + '_dseg.nii.gz'
        t1ribbon = anatdir + sub_id + '_' + sess + '_desc-ribbon.nii.gz'
        t1brainm = anatdir + sub_id + '_' + sess + '_desc-brain_mask.nii.gz'
        regfile1 = (anatdir + sub_id + '_' + sess
                    + '_from-T1w_to-MNI152NLin2009cAsym_mode-image_xfm.h5')
        regfile2 = (anatdir + sub_id + '_' + sess
                    + '_from-MNI152NLin2009cAsym_to-T1w_mode-image_xfm.h5')

        lMid = anatdir + sub_id + '_' + sess + '_hemi-L_midthickness.surf.gii'
        rMid = anatdir + sub_id + '_' + sess + '_hemi-R_midthickness.surf.gii'

        lpial = anatdir + sub_id + '_' + sess + '_hemi-L_pial.surf.gii'
        rpial = anatdir + sub_id + '_' + sess + '_hemi-R_pial.surf.gii'

        lwhite = anatdir + sub_id + '_' + sess + '_hemi-L_smoothwm.surf.gii'
        rwhite = anatdir + sub_id + '_' + sess + '_hemi-R_smoothwm.surf.gii'

        linf = anatdir + sub_id + '_' + sess + '_hemi-L_inflated.surf.gii'
        rinf = anatdir + sub_id + '_' + sess + '_hemi-R_inflated.surf.gii'

        newanatfiles = [
            t1wim, t1seg, t1ribbon, t1brainm, regfile1, regfile2, lMid, rMid,
            lpial, rpial, lwhite, rwhite, linf, rinf
        ]

        for i, j in zip(dcanimages, newanatfiles):
            copyfileobj_example(i, j)

        # get masks and transforms

        wmmask = glob.glob(anat_dirx + '/wm_2mm_*_mask_eroded.nii.gz')[0]
        csfmask = glob.glob(anat_dirx + '/vent_2mm_*_mask_eroded.nii.gz')[0]
        tw1tonative = wmmask

        # get task and idx  run 01
        func_dirx = dcan_dir + '/' + sub_id + '/ses-' + ses_id[
            0] + '/files/MNINonLinear/Results/'
        taskd = glob.glob(func_dirx + 'task-*')
        taskid = []
        for k in taskd:
            if not os.path.isfile(k):
                taskid.append(os.path.basename(k).split('-')[1])

        func_dir = out_dir + '/' + sub_id + '/ses-' + ses + '/func/'
        os.makedirs(func_dir, exist_ok=True)
        ses_id = 'ses-' + ses
        for ttt in taskid:
            taskdir = 'task-' + ttt

            taskname = re.split(r'(\d+)', ttt)[0]
            run_id = '_run-' + str(int(re.split(r'(\d+)', ttt)[1]))
            func_dirxx = func_dirx + taskdir

            sbref = func_dirxx + '/' + taskdir + '_SBRef.nii.gz'
            volume = func_dirxx + '/' + taskdir + '.nii.gz'

            brainmask = func_dirxx + '/brainmask_fs.2.0.nii.gz'
            dtsereis = func_dirxx + '/' + taskdir + '_Atlas.dtseries.nii'
            motionp = func_dirxx + '/Movement_Regressors.txt'
            rmsdx = func_dirxx + '/Movement_AbsoluteRMS.txt'

            mvreg = pd.read_csv(motionp, header=None, delimiter=r"\s+")
            mvreg = mvreg.iloc[:, 0:6]
            mvreg.columns = [
                'trans_x', 'trans_y', 'trans_z', 'rot_x', 'rot_y', 'rot_z'
            ]
            # convert rot to rad
            mvreg['rot_x'] = mvreg['rot_x'] * np.pi / 180
            mvreg['rot_y'] = mvreg['rot_y'] * np.pi / 180
            mvreg['rot_z'] = mvreg['rot_z'] * np.pi / 180

            csfreg = extractreg(mask=csfmask, nifti=volume)
            wmreg = extractreg(mask=wmmask, nifti=volume)
            gsreg = extractreg(mask=brainmask, nifti=volume)
            rsmd = np.loadtxt(rmsdx)

            brainreg = pd.DataFrame({
                'global_signal': gsreg,
                'white_matter': wmreg,
                'csf': csfreg,
                'rmsd': rsmd
            })
            regressors = pd.concat([mvreg, brainreg], axis=1)

            dcanfunfiles = [sbref, dtsereis, tw1tonative, tw1tonative, volume]

            TR = nb.load(volume).header.get_zooms()[-1]  # repetition time
            jsontis = {"RepetitionTime": np.float(TR), "TaskName": taskname}

            json2 = {
                "grayordinates": "91k",
                "space": "HCP grayordinates",
                "surface": "fsLR",
                "surface_density": "32k",
                "volume": "MNI152NLin6Asym"
            }

            boldname = func_dir + sub_id + '_' + ses_id + '_task-' + taskname + \
                run_id + '_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz'
            boldjson = func_dir + sub_id + '_' + ses_id + '_task-' + taskname + \
                run_id + '_space-MNI152NLin6Asym_desc-preproc_bold.json'
            confreg = func_dir + sub_id + '_' + ses_id + '_task-' + \
                taskname + run_id + '_desc-confounds_timeseries.tsv'
            confregj = func_dir + sub_id + '_' + ses_id + '_task-' + \
                taskname + run_id + '_desc-confounds_timeseries.json'
            boldref = func_dir + sub_id + '_' + ses_id + '_task-' + \
                taskname + run_id + '_space-MNI152NLin6A' \
                                    'sym_boldref.nii.gz'
            dttseriesx = func_dir + sub_id + '_' + ses_id + '_task-' + \
                taskname + run_id + '_space-fsLR_den-91k_bold.dtseries.nii'
            dttseriesj = func_dir + sub_id + '_' + ses_id + '_task-' + \
                taskname + run_id + '_space-fsLR_den-91k_bold.dtseries.json'
            native2t1w = func_dir + sub_id + '_' + ses_id + '_task-' + \
                taskname + run_id + '_from-scanner_to-T1w_mode-image_xfm.txt'
            t12native = func_dir + sub_id + '_' + ses_id + '_task-' + \
                taskname + run_id + '_from-T1w_to-scanner_mode-image_xfm.txt'

            # maske  coreg files here

            fmfuncfiles = [
                boldref, dttseriesx, native2t1w, t12native, boldname
            ]

            # symlink files
            for jj, kk in zip(dcanfunfiles, fmfuncfiles):
                copyfileobj_example(jj, kk)

            figdir = out_dir + '/' + sub_id + '/figures/'
            os.makedirs(figdir, exist_ok=True)
            bbreg = (figdir + sub_id + '_' + ses_id + '_task-' + taskname
                     + run_id + '_desc-bbregister_bold.svg')
            bbreg = bbregplot(fixed_image=tw1,
                              moving_image=boldref,
                              out_file=bbreg,
                              contour=ribbon)

            # write json
            writejson(jsontis, boldjson)
            writejson(json2, dttseriesj)
            writejson(json2, confregj)

            # save confounds
            regressors.to_csv(confreg, sep='\t', index=False)

        dcanjosn = {
            "Name":
            "ABCDDCAN",
            "BIDSVersion":
            "1.4.0",
            "DatasetType":
            "derivative",
            "GeneratedBy": [{
                "Name":
                "DCAN",
                "Version":
                "0.0.4",
                "CodeURL":
                "https://github.com/DCAN-Labs/abcd-hcp-pipeline"
            }],
        }
        writejson(dcanjosn, out_dir + '/dataset_description.json')


def copyfileobj_example(src, dst):
    """Copy a file from source to dest.

    source and dest must be file-like objects,
    i.e. any object with a read or write method, like for example StringIO.
    """
    import filecmp
    import shutil
    if not os.path.exists(dst) or not filecmp.cmp(src, dst):
        shutil.copyfile(src, dst)


def symlinkfiles(source, dest):
    """Symlink source file to dest file."""
    # Beware, this example does not handle any edge cases!
    with open(source, 'rb') as src, open(dest, 'wb') as dst:
        copyfileobj_example(src, dst)


def extractreg(mask, nifti):
    """Extract mean signal within mask from NIFTI."""
    masker = NiftiMasker(mask_img=mask)
    signals = masker.fit_transform(nifti)
    return np.mean(signals, axis=1)


def writejson(data, outfile):
    """Write dictionary to JSON file."""
    with open(outfile, 'w') as f:
        json.dump(data, f)
    return outfile


def bbregplot(fixed_image, moving_image, contour, out_file='report.svg'):
    """Plot bbreg results."""
    import numpy as np
    from nilearn.image import load_img, resample_img, threshold_img
    from niworkflows.viz.utils import compose_view, cuts_from_bbox, plot_registration

    fixed_image_nii = load_img(fixed_image)
    moving_image_nii = load_img(moving_image)
    moving_image_nii = resample_img(moving_image_nii,
                                    target_affine=np.eye(3),
                                    interpolation='nearest')
    contour_nii = load_img(contour) if contour is not None else None

    mask_nii = threshold_img(fixed_image_nii, 1e-3)

    n_cuts = 7
    if contour_nii:
        cuts = cuts_from_bbox(contour_nii, cuts=n_cuts)
    else:
        cuts = cuts_from_bbox(mask_nii, cuts=n_cuts)

    compose_view(
        plot_registration(fixed_image_nii,
                          "fixed-image",
                          estimate_brightness=True,
                          cuts=cuts,
                          label='fixed',
                          contour=contour_nii,
                          compress='auto'),
        plot_registration(
            moving_image_nii,
            "moving-image",
            estimate_brightness=True,
            cuts=cuts,
            label='moving',
            contour=contour_nii,
            compress='auto',
        ),
        out_file=out_file,
    )
    return out_file
