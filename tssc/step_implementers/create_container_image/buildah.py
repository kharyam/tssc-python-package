"""Step Implementer for the create-container-image step for Buildah.

Step Configuration
------------------

Step configuration expected as input to this step.
Could come from either configuration file or
from runtime configuration.

| Configuration Key | Required? | Default        | Description
|-------------------|-----------|----------------|-----------
| `imagespecfile`   | True      | `'Dockerfile'` | File defining the container image
| `context`         | True      | `'.'`          | Context to build the container image in
| `tlsverify`       | True      | `'true'`       | Whether to verify TLS when pulling parent images
| `format`          | True      | `'oci'`        | format of the built image's manifest and metadata
| `containers-config-auth-file` | True | `'~/.buildah-auth.json'` | \
    Path to the container registry authentication file \
    to use for container registry authentication.

Expected Previous Step Results
------------------------------

Results expected from previous steps that this step requires.

| Step Name           | Result Key                    | Description
|---------------------|-------------------------------|------------
| `generate-metadata` | `container-image-version`     | Version to use when building the image

Results
-------

Results output by this step.

| Result Key                | Description
|---------------------------|------------
| `container-image-version` | Container version to tag built image with
| `image-tar-file`          | Path to the built container image as a tar file

"""
import os
from pathlib import Path
import sys
import sh

from tssc import StepImplementer, StepResult
from tssc.utils.containers import container_registries_login

DEFAULT_CONFIG = {
    # Path to the container registry authentication file to read and write to/from.
    'containers-config-auth-file': os.path.join(Path.home(), '.buildah-auth.json'),

    # Image specification file name
    'imagespecfile': 'Dockerfile',

    # Parent path to the image specification file
    'context': '.',

    # Verify TLS Certs?
    'tlsverify': 'true',

    # Format of the produced image
    'format': 'oci'
}

REQUIRED_CONFIG_KEYS = [
    'containers-config-auth-file',
    'imagespecfile',
    'context',
    'tlsverify',
    'format',
    'service-name',
    'application-name'
]


class Buildah(StepImplementer):
    """
    StepImplementer for the create-container-image step for Buildah.

    Raises
    ------
    ValueError
        If image specification file does not exist
        If destination is not specified (not defaulted)
    RuntimeError
        buildah command fails for any reason
    """

    @staticmethod
    def step_implementer_config_defaults():
        """
        Getter for the StepImplementer's configuration defaults.

        Notes
        -----
        These are the lowest precedence configuration values.

        Returns
        -------
        dict
            Default values to use for step configuration values.
        """
        return DEFAULT_CONFIG

    @staticmethod
    def required_runtime_step_config_keys():
        """
        Getter for step configuration keys that are required before running the step.

        See Also
        --------
        _validate_runtime_step_config

        Returns
        -------
        array_list
            Array of configuration keys that are required before running the step.
        """
        return REQUIRED_CONFIG_KEYS

    def _run_step(self):
        """Runs the TSSC step implemented by this StepImplementer.

        Returns
        -------
        StepResult
            Results of running this step.
        """

        step_result = StepResult.from_step_implementer(self)

        context = self.get_config_value('context')
        image_spec_file = self.get_config_value('imagespecfile')
        image_spec_file_location = context + '/' + image_spec_file
        application_name = self.get_config_value('application-name')
        service_name = self.get_config_value('service-name')

        if not os.path.exists(image_spec_file_location):
            step_result.success = False
            step_result.message = 'Image specification file does not exist in location: ' \
                                  f'{image_spec_file_location}'
            return step_result

        image_tag_version = self.get_result_value(artifact_name='container-image-version')
        if image_tag_version is None:
            image_tag_version = 'latest'
            print('No image tag version found in metadata. Using latest')

        destination = "localhost/{application_name}/{service_name}".format(
            application_name=application_name,
            service_name=service_name
        )
        tag = "{destination}:{version}".format(
            destination=destination,
            version=image_tag_version
        )

        try:
            # login to any provider container registries
            # NOTE: important to specify the auth file because depending on the context this is
            #       being run in python process may not have permissions to default location
            containers_config_auth_file = self.get_config_value('containers-config-auth-file')
            container_registries_login(
                registries=self.get_config_value('container-registries'),
                containers_config_auth_file=containers_config_auth_file
            )

            # perform build
            #
            # NOTE: using --storage-driver=vfs so that container does not need escalated privileges
            #       vfs is less efficient then fuse (which would require host mounts),
            #       but such is the price we pay for security.
            sh.buildah.bud(  # pylint: disable=no-member
                '--storage-driver=vfs',
                '--format=' + self.get_config_value('format'),
                '--tls-verify=' + str(self.get_config_value('tlsverify')),
                '--layers', '-f', image_spec_file,
                '-t', tag,
                '--authfile', containers_config_auth_file,
                context,
                _out=sys.stdout,
                _err=sys.stderr,
                _tee='err'
            )
        except sh.ErrorReturnCode as error:  # pylint: disable=undefined-variable
            raise RuntimeError('Issue invoking buildah bud with given image '
                               'specification file (' + image_spec_file + ')') from error

        image_tar_file = f'image-{application_name}-{service_name}-{image_tag_version}.tar'

        image_tar_path = os.path.join(self.work_dir_path_step, image_tar_file)

        try:
            # Check to see if the tar docker-archive file already exists
            #   this needs to be run as buildah does not support overwritting
            #   existing files.
            #
            # NOTE: using --storage-driver=vfs so that container does not need escalated privileges
            #       vfs is less efficient then fuse (which would require host mounts),
            #       but such is the price we pay for security.
            if os.path.exists(image_tar_path):
                os.remove(image_tar_path)
            sh.buildah.push(  # pylint: disable=no-member
                '--storage-driver=vfs',
                tag,
                "docker-archive:" + image_tar_path,
                _out=sys.stdout,
                _err=sys.stderr,
                _tee='err'
            )
        except sh.ErrorReturnCode as error:  # pylint: disable=undefined-variable
            raise RuntimeError(
                'Issue invoking buildah push to tar file ' + image_tar_path) from error

        step_result.add_artifact(
            name='container-image-version',
            value=tag
        )

        step_result.add_artifact(
            name='image-tar-file',
            value=image_tar_path,
            value_type='file'
        )

        return step_result
