# Containers and image locks

Use one OCI image per tool. Docker runs those images locally and on AWS Batch; Apptainer converts the same digest-pinned references on Slurm. All selected images are required to have `@sha256:<64 hex digits>` in the local JSON passed to `--image_manifest`.

`assets/image_sources.json` records upstream starting points. Some upstream sources use `latest`; these are **discovery inputs only**, not production locks. `bin/lock_images.py` resolves their actual registry manifest digests, failing if any lookup fails. Review and version the resulting lock for each release. The repository does not contain invented digests for unavailable images.

Two small custom images are needed:

The source inventory includes `preprocess` and `nasvar` as `null` because those
custom images have not been published. Supply their actual registry references
using the required `--preprocess` and `--nasvar` arguments to `bin/lock_images.py`;
these replace the null entries before resolution. The source inventory is not a
runnable `--image_manifest`: the generated lock must contain real digest-pinned
references. There are 13 image entries in the complete inventory. Dorado,
samtools, and pysam share the preprocessing image; methylation processing uses
the Classy image, so these do not require separate entries.

1. `docker/preprocess/Dockerfile`: build on oncoseq's Rocky Linux 9 Dorado image,
   installing dependencies with `dnf`, compiling samtools 1.21 from its release
   archive, and installing the pysam 0.23.3 wheel for BAM/reference checks.
2. `docker/nasvar/Dockerfile`: build NASVAR with `cargo build --release --locked` from the pinned submodule, with its full non-commercial notice in the runtime layer.

Build from the repository root after bootstrapping. Resolve the base references first with `docker buildx imagetools inspect`; use their real digests below:

```bash
# Set these to actual digest-pinned image references, not these variable names.
# DORADO_IMAGE starts from ghcr.io/chusj-pigu/dorado:851b0a37ecbff6b3b952c811b31dad48ca6bf995
# RUST_IMAGE should be a Rust >=1.85 Debian bookworm builder.
# RUNTIME_IMAGE should be Debian bookworm-slim, compatible with the builder.
docker buildx build --platform linux/amd64 --load \
  --build-arg DORADO_IMAGE="$DORADO_IMAGE" \
  -f docker/preprocess/Dockerfile -t "$PREPROCESS_IMAGE" .
docker buildx build --platform linux/amd64 --load \
  --build-arg RUST_IMAGE="$RUST_IMAGE" --build-arg RUNTIME_IMAGE="$RUNTIME_IMAGE" \
  -f docker/nasvar/Dockerfile -t "$NASVAR_IMAGE" .
```

After testing, publish the images in a registry your users can access, retaining applicable licenses. To create a lock against those published images:

```bash
python3 bin/lock_images.py --preprocess "$PREPROCESS_IMAGE" \
  --nasvar "$NASVAR_IMAGE" --output images.lock.json
```

The utility reads registry metadata only; it does not build, run or publish images. Override the source JSON for private mirrors or ECR. Classifier weights inside an upstream image still retain their own terms: verify redistribution rights before mirroring. For restricted weights, use an appropriately licensed private Classy image with the model layout expected by oncoseq's Classy module.

## GitHub Actions publishing to GHCR

The manually triggered `Build custom analysis images` workflow publishes both
custom images to `ghcr.io/<owner>/<repository>` (lowercase), which is
`ghcr.io/dbuckleychla/frankontstein` for this repository. Tags are
`preprocess-<git commit>` and `nasvar-<git commit>`. It does not run on pull
requests or ordinary pushes.

The image-build job initializes only the pinned NASVAR source submodule. It does
not clone oncoseq or its nested caller modules. Preprocessing pulls its Dorado
base image; generating the final image lock queries upstream caller registry
metadata without downloading their container layers.

Authentication uses the built-in `GITHUB_TOKEN` with `packages: write`; no custom
registry secrets are needed. Both images are labeled with their source repository
so the package can inherit repository access. After the first successful push,
set the GHCR package visibility to **Public** in its package settings to allow
unauthenticated pulls. A public source repository does not automatically make
its container package public. If a package already exists without repository
access, grant this repository Actions access in the package settings.

After pushing the workflow changes, dispatch without any inputs. The job reads
`assets/container_bases.json`, resolves all three references to immutable digests,
and builds using only those resolved digests. Dorado uses the recorded oncoseq
image tag; Rust uses version 1.90.0 on bookworm; Debian uses bookworm-slim.
These source tags are not immutable pins across runs. The job saves the exact
references as the `container-base-lock` artifact before building. To freeze bases
across future runs, replace the source references in that JSON with the recorded
digest references.

```bash
gh workflow run containers.yml --repo dbuckleychla/FrankONTstein
gh run list --repo dbuckleychla/FrankONTstein --workflow containers.yml
```

Download the successful run's `candidate-image-lock` artifact for its generated
`images.lock.json`. The lock includes both custom images and the upstream caller
images. Test those images before declaring the lock release-ready. If upstream
digest resolution fails after the builds, the custom images may already have
been pushed; inspect the run log before retrying.

The task scripts under `bin/` are staged by Nextflow. The preprocessing image supplies Python/pysam; the NASVAR image supplies Python. CPU-only execution is the default. Native ARM64 support has not been validated across upstream images.

Optional `--clair3_gpu` adds Clair3's GPU flag and requests GPU access in the selected backend: Docker `--gpus all`, Apptainer `--nv`, Slurm `--gres=gpu:1` with optional `--gpu_queue`, or an AWS GPU queue. The selected image and host driver must be compatible. Other callers remain on CPU.

## POD5 basecalling compatibility

Optional basecalling reuses the digest-pinned `preprocess` image. It requires NVIDIA/CUDA, `nvidia-smi`, and Dorado basecaller options `--device`, `--no-trim`, and `--modified-bases-models`. A runtime preflight checks the installed CLI and supplied offline model assets. No vendor gitlink, image digest or dependency version changes are required. See [model compatibility and execution settings](../documentation/basecalling.md). Container/GPU integration must be validated on NVIDIA hardware; stub tests do not establish model compatibility.
