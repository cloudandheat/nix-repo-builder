# nix-repo-builder

Simple script to build and upload all versions of a specific Flake output package inside a repository.

The following variables need to be set:

`REPO_URL` The URL to the Flake repository which should be built
`TARGET_PACKAGE` The package that should be built
`NIX_CACHE_PRIVATE_KEY_FILE` The path to the private key that should sign
`NIX_CACHE_UPLOAD_URI` URI of the Nix cache to which packages should be uploaded

Optional:
`STATE_DIR` Where nix-repo-builder should keep track of which commits were already built. If left empty, it will build all references.
