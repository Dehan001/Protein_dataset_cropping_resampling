# resample_only_from_normalized.py
# Run:
# & "C:\Users\fd02629\AppData\Local\Programs\ChimeraX 1.11.1\bin\ChimeraX-console.exe" --nogui --script resample_only_from_normalized.py
#
# Input:
#   normalized_output/**/**_normalized.mrc
# Output (mirrored structure):
#   resampled_output/**/**_resampled.mrc
#
# Only does: open -> volume resample spacing 1.0 -> save

from pathlib import Path
from chimerax.core.commands import run
from chimerax.map import Volume

# ================= CONFIG =================
INPUT_ROOT = Path("normalized_output")
OUTPUT_ROOT = Path("resampled_output")
PATTERN = "**/*_normalized.mrc"
SPACING = 1.0
SKIP_IF_EXISTS = True
# =========================================


def get_new_volume(session, before_ids):
    """Return the newly created *Volume* model after a command (ignores #N.1 surfaces)."""
    after = session.models.list()
    new_models = [m for m in after if id(m) not in before_ids]
    new_vols = [m for m in new_models if isinstance(m, Volume)]
    return new_vols[-1] if new_vols else None


def resample_one(session, in_path: Path):
    # Mirror folder structure under OUTPUT_ROOT
    rel = in_path.relative_to(INPUT_ROOT)     # e.g., 6L62_EMD-0838_A/6L62_EMD-0838_A_mask_r5_normalized.mrc
    out_dir = OUTPUT_ROOT / rel.parent        # e.g., resampled_output/6L62_EMD-0838_A/
    out_dir.mkdir(parents=True, exist_ok=True)

    # Output name: keep prefix, replace only suffix
    if not in_path.name.endswith("_normalized.mrc"):
        raise RuntimeError(f"Unexpected input name (must end with _normalized.mrc): {in_path.name}")

    out_name = in_path.name[:-len("_normalized.mrc")] + "_resampled.mrc"
    out_path = out_dir / out_name

    if SKIP_IF_EXISTS and out_path.exists():
        print(f"SKIP exists: {out_path}")
        return

    run(session, "close all")

    # Open normalized map as #1 (volume) (+ possible #1.1 surface)
    run(session, f"open {in_path}")

    # Resample spacing -> creates a NEW volume model (usually #2)
    before = set(id(m) for m in session.models.list())
    run(session, f"volume resample #1 onGrid #1 spacing {SPACING}")
    # run(session, f"volume resample #2 onGrid #1") # creates #3

    resampled_vol = get_new_volume(session, before)
    if resampled_vol is None:
        raise RuntimeError("volume resample did not create a new Volume model")

    resampled_id = resampled_vol.id_string  # e.g., "2"

    # Save the resampled volume
    run(session, f"save {out_path} #{resampled_id}")

    run(session, "close all")
    print(f"OK   {in_path} -> {out_path}")


def main(session):
    if not INPUT_ROOT.exists():
        print(f"[ERROR] Input folder not found: {INPUT_ROOT}")
        return

    files = sorted(INPUT_ROOT.glob(PATTERN))
    if not files:
        print(f"[ERROR] No files matched: {INPUT_ROOT}/{PATTERN}")
        return

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"Found {len(files)} normalized maps to resample.")

    for in_path in files:
        try:
            resample_one(session, in_path)
        except Exception as ex:
            try:
                run(session, "close all")
            except Exception:
                pass
            print(f"FAIL {in_path} | {ex}")


main(session)