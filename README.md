# ignition-project
Project that runs the kernel context inside Ignition.

# Overview

There are three folders:
- `resources` contains all the source for the project in Ignition
- `build` is an intermediate folder containing the files Ignition uses
- `dist` contains the packed exports, either straight from Ignition or build from the repo.

Two scripts are included to aid this:
- `pack_project.py` copies, renames, and organizes the repo source for use in Ignition, generating `resource.json` as it runs.
- `unpack_project.py` unpacks the zip exports, renaming the files to look like a normal Python module.

By default unpack will use the most recent semver tag for packing the project. This is determined by [git_semver_tags](https://pypi.org/project/git-semver-tags/)