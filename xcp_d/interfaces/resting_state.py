# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Interfaces for working with resting-state fMRI data.

.. testsetup::

"""
import os
import shutil

import tempita
from brainsprite import viewer_substitute
from nipype import logging
from nipype.interfaces.afni.preprocess import AFNICommandOutputSpec, DespikeInputSpec
from nipype.interfaces.afni.utils import (
    ReHoInputSpec,
    ReHoOutputSpec,
    UnifizeInputSpec,
    UnifizeOutputSpec,
)
from nipype.interfaces.base import (
    BaseInterfaceInputSpec,
    File,
    SimpleInterface,
    TraitedSpec,
    traits,
)
from pkg_resources import resource_filename as pkgrf

from xcp_d.utils.fcon import compute_2d_reho, compute_alff, mesh_adjacency
from xcp_d.utils.filemanip import fname_presuffix
from xcp_d.utils.utils import zscore_nifti
from xcp_d.utils.write_save import read_gii, read_ndata, write_gii, write_ndata

LOGGER = logging.getLogger('nipype.interface')


# compute 2D reho
class _SurfaceReHoInputSpec(BaseInterfaceInputSpec):
    surf_bold = File(exists=True,
                     mandatory=True,
                     desc="left or right hemisphere gii ")
    surf_hemi = traits.Str(exists=True, mandatory=True, desc="L or R ")


class _SurfaceReHoOutputSpec(TraitedSpec):
    surf_gii = File(exists=True, mandatory=True, desc=" lh hemisphere reho")


class SurfaceReHo(SimpleInterface):
    """Calculate regional homogeneity (ReHo) on a surface file.

    Examples
    --------
    .. testsetup::
    >>> from tempfile import TemporaryDirectory
    >>> tmpdir = TemporaryDirectory()
    >>> os.chdir(tmpdir.name)
    .. doctest::
    >>> surfacereho_wf = SurfaceReHo()
    >>> surfacereho_wf.inputs.surf_bold = 'rhhemi.func.gii'
    >>> surfacereho_wf.inputs.surf_hemi = 'R'
    >>> surfacereho_wf.run()
    .. testcleanup::
    >>> tmpdir.cleanup()
    """

    input_spec = _SurfaceReHoInputSpec
    output_spec = _SurfaceReHoOutputSpec

    def _run_interface(self, runtime):

        # Read the gifti data
        data_matrix = read_gii(self.inputs.surf_bold)

        # Get the mesh adjacency matrix
        mesh_matrix = mesh_adjacency(self.inputs.surf_hemi)

        # Compute reho
        reho_surf = compute_2d_reho(datat=data_matrix,
                                    adjacency_matrix=mesh_matrix)

        # Write the output out
        self._results['surf_gii'] = fname_presuffix(self.inputs.surf_bold,
                                                    suffix='.shape.gii',
                                                    newpath=runtime.cwd,
                                                    use_ext=False)
        write_gii(datat=reho_surf,
                  template=self.inputs.surf_bold,
                  filename=self._results['surf_gii'],
                  hemi=self.inputs.surf_hemi)
        return runtime


class _ComputeALFFInputSpec(BaseInterfaceInputSpec):
    in_file = File(exists=True, mandatory=True, desc="nifti, cifti or gifti")
    TR = traits.Float(exists=True, mandatory=True, desc="repetition time")
    lowpass = traits.Float(exists=True,
                           mandatory=True,
                           default_value=0.10,
                           desc="lowpass filter in Hz")
    highpass = traits.Float(exists=True,
                            mandatory=True,
                            default_value=0.01,
                            desc="highpass filter in Hz")
    mask = File(exists=False,
                mandatory=False,
                desc=" brain mask for nifti file")


class _ComputeALFFOutputSpec(TraitedSpec):
    alff_out = File(exists=True, mandatory=True, desc=" alff")


class ComputeALFF(SimpleInterface):
    """Compute ALFF.

    Examples
    --------
    .. testsetup::
    >>> from tempfile import TemporaryDirectory
    >>> tmpdir = TemporaryDirectory()
    >>> os.chdir(tmpdir.name)
    .. doctest::
    computealffwf = ComputeALFF()
    computealffwf.inputs.in_file = datafile
    computealffwf.inputs.lowpass = 0.1
    computealffwf.inputs.highpass = 0.01
    computealffwf.inputs.TR = TR
    computealffwf.inputs.mask_file = mask
    computealffwf.run()
    .. testcleanup::
    >>> tmpdir.cleanup()
    """

    input_spec = _ComputeALFFInputSpec
    output_spec = _ComputeALFFOutputSpec

    def _run_interface(self, runtime):

        # Get the nifti/cifti into matrix form
        data_matrix = read_ndata(datafile=self.inputs.in_file,
                                 maskfile=self.inputs.mask)
        # compute the ALFF
        alff_mat = compute_alff(data_matrix=data_matrix,
                                low_pass=self.inputs.lowpass,
                                high_pass=self.inputs.highpass,
                                TR=self.inputs.TR)

        # Write out the data

        if self.inputs.in_file.endswith('.dtseries.nii'):
            suffix = '_alff.dtseries.nii'
        elif self.inputs.in_file.endswith('.nii.gz'):
            suffix = '_alff.nii.gz'

        self._results['alff_out'] = fname_presuffix(
            self.inputs.in_file,
            suffix=suffix,
            newpath=runtime.cwd,
            use_ext=False,
        )
        write_ndata(data_matrix=alff_mat,
                    template=self.inputs.in_file,
                    filename=self._results['alff_out'],
                    mask=self.inputs.mask)

        return runtime


class _BrainPlotInputSpec(BaseInterfaceInputSpec):
    in_file = File(exists=True, mandatory=True, desc="alff or reho")
    mask_file = File(exists=True, mandatory=True, desc="mask file ")


class _BrainPlotOutputSpec(TraitedSpec):
    nifti_html = File(exists=True, mandatory=True, desc="zscore html")


class BrainPlot(SimpleInterface):
    """Create a brainsprite figure from a NIFTI file.

    The image will first be normalized (z-scored) before the figure is generated.
    """

    input_spec = _BrainPlotInputSpec
    output_spec = _BrainPlotOutputSpec

    def _run_interface(self, runtime):

        # create a file name
        z_score_nifti = os.path.split(os.path.abspath(
            self.inputs.in_file))[0] + '/zscore.nii.gz'

        # create a nifti with z-scores
        z_score_nifti = zscore_nifti(img=self.inputs.in_file,
                                     mask=self.inputs.mask_file,
                                     outputname=z_score_nifti)
        #  get the right template
        temptlatehtml = pkgrf('xcp_d',
                              'data/transform/brainsprite_template.html')
        # adjust settings for viewing in HTML
        bsprite = viewer_substitute(threshold=0,
                                    opacity=0.5,
                                    title="zcore",
                                    cut_coords=[0, 0, 0])

        bsprite.fit(z_score_nifti, bg_img=None)

        template = tempita.Template.from_filename(temptlatehtml,
                                                  encoding="utf-8")
        viewer = bsprite.transform(template,
                                   javascript='js',
                                   html='html',
                                   library='bsprite')
        # write the html out
        self._results['nifti_html'] = fname_presuffix(
            'zscore_nifti_',
            suffix='stat.html',
            newpath=runtime.cwd,
            use_ext=False,
        )

        viewer.save_as_html(self._results['nifti_html'])
        return runtime


class ReHoNamePatch(SimpleInterface):
    """Compute ReHo for a given neighbourhood, based on a local neighborhood of that voxel.

    For complete details, see the `3dReHo Documentation.
    <https://afni.nimh.nih.gov/pub/dist/doc/program_help/3dReHo.html>`_

    Examples
    --------
    >>> from nipype.interfaces import afni
    >>> reho = afni.ReHo()
    >>> reho.inputs.in_file = 'functional.nii'
    >>> reho.inputs.out_file = 'reho.nii.gz'
    >>> reho.inputs.neighborhood = 'vertices'
    >>> reho.cmdline
    '3dReHo -prefix reho.nii.gz -inset functional.nii -nneigh 27'
    >>> res = reho.run()  # doctest: +SKIP
    """

    _cmd = "3dReHo"
    input_spec = ReHoInputSpec
    output_spec = ReHoOutputSpec

    def _run_interface(self, runtime):
        outfile = runtime.cwd + "/reho.nii.gz"
        shutil.copyfile(self.inputs.in_file, runtime.cwd + "/inset.nii.gz")
        shutil.copyfile(self.inputs.mask_file, runtime.cwd + "/mask.nii.gz")
        os.system(
            "3dReHo -inset inset.nii.gz -mask mask.nii.gz -nneigh 27 -prefix reho.nii.gz"
        )
        self._results['out_file'] = outfile


class DespikePatch(SimpleInterface):
    """Remove 'spikes' from the 3D+time input dataset.

    For complete details, see the `3dDespike Documentation.
    <https://afni.nimh.nih.gov/pub/dist/doc/program_help/3dDespike.html>`_

    Examples
    --------
    >>> from nipype.interfaces import afni
    >>> despike = afni.Despike()
    >>> despike.inputs.in_file = 'functional.nii'
    >>> despike.cmdline
    '3dDespike -prefix functional_despike functional.nii'
    >>> res = despike.run()  # doctest: +SKIP
    """

    _cmd = "3dDespike"
    input_spec = DespikeInputSpec
    output_spec = AFNICommandOutputSpec

    def _run_interface(self, runtime):
        outfile = runtime.cwd + "/3despike.nii.gz"
        shutil.copyfile(self.inputs.in_file, runtime.cwd + "/inset.nii.gz")
        os.system("3dDespike -NEW -prefix  3despike.nii.gz inset.nii.gz")
        self._results['out_file'] = outfile


class ContrastEnhancement(SimpleInterface):
    """Perform contrast enhancement with AFNI.

    3dUnifize  -input inputdat   -prefix  t1w_contras.nii.gz
    """

    _cmd = "3dUnifize"
    input_spec = UnifizeInputSpec
    output_spec = UnifizeOutputSpec

    def _run_interface(self, runtime):
        outfile = runtime.cwd + "/3dunfixed.nii.gz"

        if self.inputs.in_file.endswith(".nii.gz"):
            shutil.copyfile(self.inputs.in_file, runtime.cwd + "/inset.nii.gz")
        else:
            shutil.copyfile(self.inputs.in_file, runtime.cwd + "/inset.mgz")
            os.system("mri_convert inset.mgz inset.nii.gz")

        os.system(
            "3dUnifize -T2  -input inset.nii.gz   -prefix  3dunfixed.nii.gz")
        self._results['out_file'] = outfile
