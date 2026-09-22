# Containers and image locks

Use one OCI image per tool. Docker runs those images locally and on AWS Batch; Apptainer converts the same digest-pinned references on Slurm. All selected images are required to have `@sha256:<64 hex digits>` in the local JSON passed to `--image_manifest`.

`assets/image_sources.json` records upstream starting points. Some upstream sources use `latest`; these are **discovery inputs only**, not production locks. `bin/lock_images.py` resolves their actual registry manifest digests, failing if any lookup fails. Review and version the resulting lock for each release. The repository does not contain invented digests for unavailable images.

Two small custom images are needed:

1. `docker/preprocess/Dockerfile`: build on oncoseq's Dorado image, adding samtools and Python/pysam for BAM/reference checks.
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

The task scripts under `bin/` are staged by Nextflow. The preprocessing image supplies Python/pysam; the NASVAR image supplies Python. CPU-only execution is the default. Native ARM64 support has not been validated across upstream images.

Optional `--clair3_gpu` adds Clair3's GPU flag and requests GPU access in the selected backend: Docker `--gpus all`, Apptainer `--nv`, Slurm `--gres=gpu:1` with optional `--gpu_queue`, or an AWS GPU queue. The selected image and host driver must be compatible. Other callers remain on CPU.
