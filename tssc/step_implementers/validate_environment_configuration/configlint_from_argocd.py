"""Step Implementer for the 'validate-environment-config' step for ConfiglintFromArgocd.
The ConfiglintFromArogcd step takes the output of the Deploy (argocd) step and prepares
it as input for the Configlint step.

Step Configuration
------------------
Step configuration expected as input to this step.  Could come from either
configuration file or from runtime configuration.

| Configuration Key     | Required | Default                   | Description
|-----------------------|----------|---------------------------|---------------------------
|                       |          |                           |
.. Note:: No required keys

Expected Previous Step Results
-----------------------------
Results expected from previous steps that this step requires.

| Step Name | Key                   | Required | Description
|-----------|-----------------------|----------|------------
|  deploiy  | `argocd-result-set`   | True     | Yml file to be linted; generated by the deploy step

Results
-------
Results output by this step.

| Result Key            | Description
|-----------------------|------------
| `configlint-yml-file` | Yml file to be linted; eg: file://folder/file.yml

"""

import os
from urllib.parse import urlparse
from tssc.step_result import StepResult

from tssc import StepImplementer

DEFAULT_CONFIG = {
}

REQUIRED_CONFIG_KEYS = [
]

AUTHENTICATION_CONFIG = {
}


class ConfiglintFromArgocd(StepImplementer):
    """
    StepImplementer for the validate-environment-configuration sub-step ConfiglintFromArgocd
    """

    @staticmethod
    def step_implementer_config_defaults():
        """
        Getter for the StepImplementer's configuration defaults.

        Returns
        -------
        dict
            Default values to use for step configuration values.

        Notes
        -----
        These are the lowest precedence configuration values.
        """
        return DEFAULT_CONFIG

    @staticmethod
    def required_runtime_step_config_keys():
        """
        Getter for step configuration keys that are required before running the step.

        Returns
        -------
        array_list
            Array of configuration keys that are required before running the step.

        See Also
        --------
        _validate_runtime_step_config
        """
        return REQUIRED_CONFIG_KEYS

    def _run_step(self):
        """
        Runs the TSSC step implemented by this StepImplementer.
        Parameters
        ----------
        runtime_step_config : dict
            Step configuration to use when the StepImplementer runs the step with all of the
            various static, runtime, defaults, and environment configuration munged together.
        Returns
        -------
        dict
            Results of running this step.
        """
        step_result = StepResult.from_step_implementer(self)

        argocd_result_set = self.get_result_value(artifact_name='argocd-result-set')
        if argocd_result_set is None:
            step_result.success = False
            step_result.message = 'Missing argocd-result-set from previous step results'
            return step_result

        # The yml_path expected format:  file:///folder/file.yml
        yml_path = urlparse(argocd_result_set).path
        if not os.path.exists(yml_path):
            step_result.success = False
            step_result.message = f'File specified in argocd-result-set {yml_path} not found'
            return step_result

        step_result.add_artifact(
            name='configlint-yml-path',
            value=f'file://{yml_path}',
            value_type='file')
        return step_result
