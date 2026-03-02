# masking_cropped_structured.py
# Run:
# & "C:\Users\fd02629\AppData\Local\Programs\ChimeraX 1.11.1\bin\ChimeraX-console.exe" --nogui --script masking_cropped_structured.py

from pathlib import Path
from chimerax.core.commands import run
from chimerax.map import Volume

# ================= CONFIG =================
IN_DIR = Path("output")           # contains subfolders {TAG}/
OUT_BASE = Path("masked_output")  # will create {TAG}/ inside
MASK_RADII = [5, 7, 10]           # Å
SKIP_IF_EXISTS = True
# ==========================================


def get_new_volume(session, before_ids):
    """Return the newly created Volume model after a command."""
    after = session.models.list()
    new_models = [m for m in after if id(m) not in before_ids]
    new_vols = [m for m in new_models if isinstance(m, Volume)]
    return new_vols[-1] if new_vols else None


def find_pairs(in_dir: Path):
    """
    Find pairs in:
      output/{tag}/{tag}_chain.pdb
      output/{tag}/{tag}_cropped.mrc
    """
    pairs = []
    for entry_dir in sorted([p for p in in_dir.iterdir() if p.is_dir()]):
        tag = entry_dir.name
        chain_pdb = entry_dir / f"{tag}_chain.pdb"
        cropped_mrc = entry_dir / f"{tag}_cropped.mrc"

        if chain_pdb.exists() and cropped_mrc.exists():
            pairs.append((tag, chain_pdb, cropped_mrc))
        else:
            missing = []
            if not chain_pdb.exists():
                missing.append(chain_pdb.name)
            if not cropped_mrc.exists():
                missing.append(cropped_mrc.name)
            print(f"SKIP {tag} (missing: {', '.join(missing)})")

    return pairs


def mask_one(session, tag: str, chain_pdb: Path, cropped_mrc: Path):
    chain_id = tag.split("_")[-1]  # A / B / etc.

    out_dir = OUT_BASE / tag
    out_dir.mkdir(parents=True, exist_ok=True)

    run(session, "close all")
    run(session, f"open {chain_pdb}")     # #1 structure
    run(session, f"open {cropped_mrc}")   # #2 volume

    for r in MASK_RADII:
        out_mask = out_dir / f"{tag}_mask_r{r}.mrc"
        if SKIP_IF_EXISTS and out_mask.exists():
            print(f"SKIP exists: {out_mask}")
            continue

        # zone around atoms AND create a NEW masked volume (this is the one we must save)
        before = set(id(m) for m in session.models.list())
        run(session, f"volume zone #2 nearAtoms #1/{chain_id} range {r} newMap true")

        masked_vol = get_new_volume(session, before)
        if masked_vol is None:
            raise RuntimeError("volume zone newMap failed (no new Volume model created)")

        masked_id = masked_vol.id_string  # e.g., "3" (without '#')

        # Save the NEW masked map (not #2)
        run(session, f"save {out_mask} models #{masked_id}")

        # Close only the generated masked map, keep #1 and #2 for next radius
        run(session, f"close #{masked_id}")

    run(session, "close all")
    print(f"OK: {tag}")


def main(session):
    if not IN_DIR.exists():
        print(f"[ERROR] Input folder not found: {IN_DIR}")
        return

    OUT_BASE.mkdir(parents=True, exist_ok=True)

    pairs = find_pairs(IN_DIR)
    if not pairs:
        print(f"[ERROR] No valid pairs found under: {IN_DIR}/{{tag}}/")
        return

    print(f"Found {len(pairs)} entries.")

    for tag, chain_pdb, cropped_mrc in pairs:
        try:
            mask_one(session, tag, chain_pdb, cropped_mrc)
        except Exception as ex:
            try:
                run(session, "close all")
            except Exception:
                pass
            print(f"FAIL: {tag} | {ex}")


main(session)