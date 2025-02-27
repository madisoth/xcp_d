# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Interfaces to generate reportlets."""

import os
import time

import pandas as pd
from nipype.interfaces.base import (
    BaseInterfaceInputSpec,
    File,
    InputMultiObject,
    SimpleInterface,
    Str,
    TraitedSpec,
    isdefined,
    traits,
)

SUBJECT_TEMPLATE = """\
\t<ul class="elem-desc">
\t\t<li>Subject ID: {subject_id}</li>
\t\t<li>BOLD series: {num_bold_files:d}</li>
\t</ul>
"""

QC_TEMPLATE = """\t\t<h3 class="elem-title">Summary</h3>
\t\t<ul class="elem-desc">
\t\t\t<li>BOLD volume space: {space}s</li>
\t\t\t<li>Repetition Time (TR): {TR:.03g}s</li>
\t\t\t<li>Mean Framewise Displacement: {meanFD}</li>
\t\t\t<li>Mean Relative RMS Motion: {meanRMS}</li>
\t\t\t<li>Max Relative RMS Motion: {maxRMS}</li>
\t\t\t<li>DVARS Before and After Processing : {dvars_before_after}</li>
\t\t\t<li>Correlation between DVARS and FD  Before and After Processing : {corrfddv}</li>
\t\t\t<li>Number of Volumes Censored : {volcensored}</li>
\t\t</ul>
"""

ABOUT_TEMPLATE = """\t<ul>
\t\t<li>xcp_d version: {version}</li>
\t\t<li>xcp_d: <code>{command}</code></li>
\t\t<li>xcp_d preprocessed: {date}</li>
\t</ul>
</div>
"""


class _SummaryInterfaceOutputSpec(TraitedSpec):
    """Output specification for SummaryInterface."""

    out_report = File(exists=True, desc='HTML segment containing summary')


class SummaryInterface(SimpleInterface):
    """A summary interface.

    This is used as a base class for other summary interfaces.
    """

    output_spec = _SummaryInterfaceOutputSpec

    def _run_interface(self, runtime):
        # Open a file to write information to
        segment = self._generate_segment()
        file_name = os.path.join(runtime.cwd, 'report.html')
        with open(file_name, 'w') as file_object:
            file_object.write(segment)
        self._results['out_report'] = file_name
        return runtime

    def _generate_segment(self):
        raise NotImplementedError


class _SubjectSummaryInputSpec(BaseInterfaceInputSpec):
    """Input specification for SubjectSummaryInterface."""

    subject_id = Str(desc='Subject ID')
    bold = InputMultiObject(traits.Either(File(exists=True),
                                          traits.List(File(exists=True))),
                            desc='BOLD or CIFTI functional series')


class _SubjectSummaryOutputSpec(_SummaryInterfaceOutputSpec):
    """Output specification for SubjectSummaryInterface."""

    # This exists to ensure that the summary is run prior to the first ReconAll
    # call, allowing a determination whether there is a pre-existing directory
    subject_id = Str(desc='Subject ID')


class SubjectSummary(SummaryInterface):
    """A subject-level summary interface."""

    input_spec = _SubjectSummaryInputSpec
    output_spec = _SubjectSummaryOutputSpec

    def _run_interface(self, runtime):
        if isdefined(self.inputs.subject_id):
            self._results['subject_id'] = self.inputs.subject_id
        return super(SubjectSummary, self)._run_interface(runtime)

    def _generate_segment(self):
        # Add list of tasks with number of runs
        num_bold_files = len(self.inputs.bold)

        return SUBJECT_TEMPLATE.format(subject_id=self.inputs.subject_id,
                                       num_bold_files=num_bold_files)


class _FunctionalSummaryInputSpec(BaseInterfaceInputSpec):
    """Input specification for FunctionalSummary."""

    bold_file = traits.File(True, True, desc='cifti or bold File')
    qc_file = traits.File(exists=True, desc='qc file')
    TR = traits.Float(
        mandatory=True,
        desc='Repetition time',
    )


class FunctionalSummary(SummaryInterface):
    """A functional MRI summary interface."""

    input_spec = _FunctionalSummaryInputSpec
    #   Get information from the QC file and return it

    def _generate_segment(self):
        space = get_space(self.inputs.bold_file)
        TR = self.inputs.TR
        qcfile = pd.read_csv(self.inputs.qc_file)
        meanFD = f"{round(qcfile['meanFD'][0], 4)} "
        meanRMS = f" {round(qcfile['relMeansRMSMotion'][0], 4)} "
        maxRMS = f" {round(qcfile['relMaxRMSMotion'][0], 4)} "
        dvars = f"  {round(qcfile['meanDVInit'][0], 4)},{round(qcfile['meanDVFinal'][0], 4)} "
        fd_dvars_correlation = (
            f" {round(qcfile['motionDVCorrInit'][0], 4)},  "
            f"{round(qcfile['motionDVCorrFinal'][0], 4)} "
        )
        num_vols_censored = f" {round(qcfile['num_censored_volumes'][0], 4)} "

        return QC_TEMPLATE.format(space=space,
                                  TR=TR,
                                  meanFD=meanFD,
                                  meanRMS=meanRMS,
                                  maxRMS=maxRMS,
                                  dvars_before_after=dvars,
                                  corrfddv=fd_dvars_correlation,
                                  volcensored=num_vols_censored)


class _AboutSummaryInputSpec(BaseInterfaceInputSpec):
    """Input specification for AboutSummary."""

    version = Str(desc='xcp_d version')
    command = Str(desc='xcp_d command')
    # Date not included - update timestamp only if version or command changes


class AboutSummary(SummaryInterface):
    """A summary of the xcp_d software used."""

    input_spec = _AboutSummaryInputSpec

    def _generate_segment(self):
        return ABOUT_TEMPLATE.format(
            version=self.inputs.version,
            command=self.inputs.command,
            date=time.strftime("%Y-%m-%d %H:%M:%S %z"))


def get_space(bold_file):
    """Extract space from bold/cifti via string manipulation.

    Parameters
    ----------
    bold_file : str
        Path to the BOLD file.

    Returns
    -------
    space : str
        The BOLD file's space.
    """
    bold_file = os.path.basename(bold_file)
    if bold_file.endswith('.dtseries.nii'):
        return 'fsLR'
    else:
        if 'space' not in bold_file:
            return 'native'
        elif 'space' in bold_file:
            bold_file_space = bold_file.split('_')

            for bold_file_name_component in bold_file_space:
                if 'space' in bold_file_name_component:
                    return bold_file_name_component.split('-')[1]
