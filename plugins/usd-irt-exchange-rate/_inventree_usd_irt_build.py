"""Build helpers for installing the early currency bootstrap hook."""

from distutils.command.install_data import install_data


class InstallDataToPurelib(install_data):
    """Install distribution data into Python's pure-library directory."""

    def finalize_options(self):
        """Place the bootstrap ``.pth`` file beside installed packages."""
        self.set_undefined_options(
            "install",
            ("install_purelib", "install_dir"),
            ("root", "root"),
            ("force", "force"),
        )
