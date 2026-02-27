# cropping.py
# Run:
# "C:\Users\fd02629\AppData\Local\Programs\ChimeraX 1.11.1\bin\ChimeraX-console.exe" --nogui --script cropping.py

import re
import os
import json
import requests
from chimerax.core.commands import run

# ============== CONFIGURATION ==============
INPUT_FILE = "final_selected_chains.txt"
PDB_DIR = "pdb_models"
MRC_DIR = "em_maps"
OUTPUT_DIR = "output"
RESULTS_FILE = "correlation_results.csv"
PADDING = 0

# ===========================================


def find_file(folder, basename, extensions):
    variations = [
        basename,
        basename.lower(),
        basename.upper(),
        basename.replace('-', '_'),
        basename.replace('_', '-'),
        basename.lower().replace('-', '_'),
        basename.lower().replace('_', '-'),
        basename.upper().replace('-', '_'),
        basename.upper().replace('_', '-'),
    ]
    for var in variations:
        for ext in extensions:
            filepath = os.path.join(folder, f"{var}{ext}")
            if os.path.exists(filepath):
                return f"{folder}/{var}{ext}"
    return None


def normalize_emd(emd: str) -> str:
    return emd.strip().upper().replace("EMD_", "EMD-")


def parse_input(input_file):
    with open(input_file, "r") as f:
        input_data = f.read()

    entries = []
    for entry in input_data.split():
        match = re.match(r'^([A-Za-z0-9]{4})_(EMD[-_]\d+)_([A-Za-z0-9]+)$', entry.strip())
        if match:
            entries.append({
                "pdb": match.group(1).upper(),
                "emd": normalize_emd(match.group(2)),
                "chain": match.group(3)
            })
    return entries


def get_emdb_resolution(emd_id):
    emd_num = emd_id.replace("EMD-", "")
    url = f"https://www.ebi.ac.uk/emdb/api/entry/{emd_num}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    resolution = data["structure_determination_list"]["structure_determination"][0]["image_processing"][0] \
        ["final_reconstruction"]["resolution"]["valueOf_"]
    return float(resolution)


def process_entry(session, pdb_file, mrc_file, resolution, pdb, emd, chain, padding):
    """
    Saves:
      output/{PDB}_{EMD}_{CHAIN}/{PDB}_{EMD}_{CHAIN}_chain.pdb
      output/{PDB}_{EMD}_{CHAIN}/{PDB}_{EMD}_{CHAIN}_cropped.mrc
    """
    tag = f"{pdb}_{emd}_{chain}"
    out_dir = os.path.join(OUTPUT_DIR, tag)
    os.makedirs(out_dir, exist_ok=True)

    try:
        run(session, "close all")

        # Open files -> structure #1, map #2
        run(session, f"open {pdb_file}")
        run(session, f"open {mrc_file}")

        # Initial fit
        run(session, "fitmap #1 inMap #2")

        # Keep only selected chain
        run(session, f"select #1/{chain}")
        run(session, "del ~sel")

        # Crop map around chain -> #3
        run(session, f"volume cover #2 atomBox #1/{chain} pad {padding}")

        # Fit into cropped map
        run(session, "fitmap #1 inMap #3")

        # Correlation
        fit_results = run(session, f"fitmap #1 inMap #3 resolution {resolution} metric correlation")
        correlation = fit_results[0].correlation()

        

        # Save outputs inside folder
        chain_out = os.path.join(out_dir, f"{tag}_chain.pdb")
        cropped_out = os.path.join(out_dir, f"{tag}_cropped.mrc")

        run(session, f"save {chain_out} #1/{chain}")
        run(session, f"save {cropped_out} #3")

        run(session, "close all")
        return correlation, "success"

    except Exception as e:
        try:
            run(session, "close all")
        except Exception:
            pass
        return None, str(e).replace(",", ";")


def main(session):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    entries = parse_input(INPUT_FILE)

    # Fetch resolutions
    for e in entries:
        try:
            e["resolution"] = get_emdb_resolution(e["emd"])
            print(f"EMD {e['emd']} resolution: {e['resolution']}")
        except Exception:
            e["resolution"] = 5.0
            print(f"EMD {e['emd']} resolution: defaulting to 5.0")

    # Init results file
    with open(RESULTS_FILE, "w") as out:
        out.write("pdb,emd,chain,correlation,status\n")

    results = []

    for e in entries:
        pdb, emd, chain, resolution = e["pdb"], e["emd"], e["chain"], e["resolution"]

        pdb_file = find_file(PDB_DIR, pdb, [".pdb", ".cif"])
        if not pdb_file:
            print(f"\nWARNING: PDB file not found for {pdb}")
            results.append({"pdb": pdb, "emd": emd, "chain": chain, "correlation": None, "status": "pdb not found"})
            continue

        mrc_base = f"{pdb}_{emd}"
        mrc_file = find_file(MRC_DIR, mrc_base, [".mrc", ".map"])
        if not mrc_file:
            print(f"\nWARNING: MRC/MAP file not found for {mrc_base}")
            results.append({"pdb": pdb, "emd": emd, "chain": chain, "correlation": None, "status": "mrc not found"})
            continue

        print(f"\nProcessing {pdb} - {emd} - Chain {chain}...")
        print(f"  PDB: {pdb_file}")
        print(f"  MRC: {mrc_file}")

        corr, status = process_entry(session, pdb_file, mrc_file, resolution, pdb, emd, chain, PADDING)

        results.append({"pdb": pdb, "emd": emd, "chain": chain, "correlation": corr, "status": status})

        with open(RESULTS_FILE, "a") as out:
            out.write(f"{pdb},{emd},{chain},{corr},{status}\n")

        with open(RESULTS_FILE.replace(".csv", ".json"), "w") as out_json:
            json.dump(results, out_json, indent=4)

        print(f"  Correlation: {corr} | Status: {status}")

    print(f"\nResults saved to: {RESULTS_FILE}")
    print(f"Outputs saved under: {OUTPUT_DIR}/{{PDB}}_{{EMD}}_{{CHAIN}}/")


main(session)