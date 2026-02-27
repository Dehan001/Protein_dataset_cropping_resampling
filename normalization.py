import numpy as np
import mrcfile
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================
INPUT_FOLDER = "masked_output"
PATTERN = "**/*_mask_r*.mrc"   # expects: masked_output/{tag}/{tag}_mask_r5.mrc ...

OUTPUT_ROOT = Path("normalized_output")  # saves mirrored folders here

# Choose normalization(s):
# - Only 1–99% min-max:        USE_MINMAX=True,  USE_P95=False
# - Only paper method (p95+):  USE_MINMAX=False, USE_P95=True
# - Both (min-max then p95+):  USE_MINMAX=True,  USE_P95=True
USE_MINMAX = False
USE_P95 = True

# Percentiles
P1, P99 = 1, 99
P95 = 95
# ============================================================


# =========================
# NORMALIZATION METHODS
# =========================
def normalize_minmax_p1_p99(data: np.ndarray, p1=1, p99=99) -> np.ndarray:
    lo = np.percentile(data, p1)
    hi = np.percentile(data, p99)
    if hi <= lo:
        raise ValueError(f"Invalid percentile range: p{p99} ({hi}) <= p{p1} ({lo})")
    norm = (data - lo) / (hi - lo)
    return np.clip(norm, 0.0, 1.0).astype(np.float32)


def normalize_p95_positive(data: np.ndarray, p=95):
    pos = data[data > 0]
    if pos.size == 0:
        raise ValueError("No positive voxels found (data[data>0] is empty)")
    p_val = np.percentile(pos, p)
    if p_val < 1e-8:
        raise ValueError(f"p{p} too small ({p_val}); cannot normalize safely")
    norm = np.clip(data / p_val, 0.0, 1.0).astype(np.float32)
    return norm, float(p_val)


# =========================
# MRC IO HELPERS
# =========================
def read_mrc(in_path: Path):
    with mrcfile.open(in_path, permissive=True) as mrc:
        data = mrc.data.astype(np.float32, copy=True)

        voxel_size = None
        origin = None

        try:
            voxel_size = mrc.voxel_size
        except Exception:
            pass

        try:
            origin = mrc.header.origin
        except Exception:
            pass

    return data, voxel_size, origin


def write_mrc(out_path: Path, data: np.ndarray, voxel_size=None, origin=None):
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with mrcfile.new(out_path, overwrite=True) as out_mrc:
        out_mrc.set_data(data.astype(np.float32, copy=False))

        if voxel_size is not None:
            try:
                out_mrc.voxel_size = voxel_size
            except Exception:
                pass

        if origin is not None:
            try:
                out_mrc.header.origin = origin
            except Exception:
                pass

        out_mrc.update_header_from_data()
        out_mrc.flush()


# =========================
# NORMALIZE ONE FILE
# =========================
def normalize_one(in_path: Path, use_minmax: bool, use_p95: bool):
    """
    Input:  masked_output/{tag}/{tag}_mask_r5.mrc
    Output: normalized_output/{tag}/{tag}_mask_r5_normalized.mrc
            normalized_output/{tag}/{tag}_mask_r5_normalization_meta.txt
    """
    data, voxel_size, origin = read_mrc(in_path)

    meta_lines = []
    meta_lines.append(f"input_file: {in_path.as_posix()}")
    meta_lines.append(f"use_minmax_1_99: {use_minmax}")
    meta_lines.append(f"use_p95_positive: {use_p95}")

    if use_minmax:
        data = normalize_minmax_p1_p99(data, P1, P99)
        meta_lines.append(f"minmax_percentiles: p{P1} to p{P99}")

    p95_value = None
    if use_p95:
        data, p95_value = normalize_p95_positive(data, P95)
        meta_lines.append(f"positive_percentile_used: p{P95}")
        meta_lines.append(f"p{P95}_value: {p95_value}")

    # Mirror folder structure: masked_output/{tag}/... -> normalized_output/{tag}/...
    rel = in_path.relative_to(Path(INPUT_FOLDER))  # {tag}/{tag}_mask_r5.mrc
    out_dir = OUTPUT_ROOT / rel.parent             # normalized_output/{tag}/

    # Keep your prefix naming; just add suffixes
    out_map = out_dir / f"{in_path.stem}_normalized.mrc"
    out_meta = out_dir / f"{in_path.stem}_normalization_meta.txt"

    write_mrc(out_map, data, voxel_size=voxel_size, origin=origin)
    out_meta.write_text("\n".join(meta_lines) + "\n", encoding="utf-8")

    return out_map, p95_value


# =========================
# BATCH DRIVER
# =========================
def batch_normalize(input_folder: str, pattern: str, use_minmax: bool, use_p95: bool):
    in_folder = Path(input_folder)
    files = sorted(in_folder.glob(pattern))

    if not files:
        print(f"No files matched: {in_folder}/{pattern}")
        return

    print(f"Found {len(files)} files. Normalization: minmax={use_minmax}, p95={use_p95}")

    for in_path in files:
        try:
            out_map, p95_val = normalize_one(in_path, use_minmax, use_p95)
            extra = f" | p95={p95_val:.6g}" if p95_val is not None else ""
            print(f"OK   {in_path} -> {out_map}{extra}")
        except Exception as e:
            print(f"FAIL {in_path} | {e}")


if __name__ == "__main__":
    batch_normalize(
        input_folder=INPUT_FOLDER,
        pattern=PATTERN,
        use_minmax=USE_MINMAX,
        use_p95=USE_P95
    )