# ChimeraX Python Script
# Run with: chimerax --nogui --script batch_process.py

import re
import os
from chimerax.core.commands import run
from chimerax.map_fit.fitcmd import fitmap
import requests
import json
# ============== CONFIGURATION ==============
INPUT_FILE = "final_selected_chains.txt"
PDB_DIR = "pdb_models"
MRC_DIR = "em_maps"
OUTPUT_DIR = "output"
RESULTS_FILE = "correlation_results.csv"
PADDING = 0
# ===========================================

def find_file(folder, basename, extensions):
    """Find file with correct extension, trying all naming variations."""
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


def parse_input(input_file):
    """Parse input file into list of entries."""
    with open(input_file, 'r') as f:
        input_data = f.read()
    
    entries = []
    for entry in input_data.split():
        match = re.match(r'^([A-Za-z0-9]{4})_(EMD[-_]\d+)_([A-Za-z0-9]+)$', entry.strip())
        if match:
            entries.append({
                'pdb': match.group(1).upper(),
                'emd': match.group(2),
                'chain': match.group(3)
            })
    return entries


def process_entry(session, pdb_file, mrc_file, resolution, output_dir, pdb, emd, chain, padding):
    """Process one entry and return correlation value."""
    try:
        # Open files
        models = run(session, f"open {pdb_file}")
        structure = models[0]
        
        maps = run(session, f"open {mrc_file}")
        density_map = maps[0]
        
        # Initial fit
        run(session, "fitmap #1 inMap #2")
        
        # Select chain and delete rest
        run(session, f"select #1/{chain}")
        run(session, "del ~sel")
        
        # Crop map
        run(session, f"volume cover #2 atomBox #1/{chain} pad {padding}")

        run(session, "fitmap #1 inMap #3")
        
        # # Get cropped map (last model)
        cropped_map = session.models.list()[-1]

        # Fit with resolution and correlation metric
        fit_results = run(session, f"fitmap #1 inMap #3 resolution {resolution} metric correlation")

        # Get correlation from results
        correlation = fit_results[0].correlation()

        # Resample to voxel 1A
        run(session, f"volume resample #3 spacing 1.0")
        run(session, "volume resample #3 onGrid #4")

        
        # Save outputs
        run(session, f"save {output_dir}/{pdb}_{emd}_{chain}_chain.pdb #1/{chain}")
        run(session, f"save {output_dir}/{pdb}_{emd}_{chain}_cropped.mrc #5")
        
        run(session, "close all")
        return correlation, "success"
    
    except Exception as e:
        run(session, "close all")
        return None, str(e).replace(",", ";")


def get_emdb_resolution(emd_id):
    emd_num = emd_id.replace("EMD-", "")
    url = f"https://www.ebi.ac.uk/emdb/api/entry/{emd_num}"
    response = requests.get(url)
    data = response.json()
    
    # Correct path to resolution
    resolution = data["structure_determination_list"]["structure_determination"][0]["image_processing"][0]["final_reconstruction"]["resolution"]["valueOf_"]
    return float(resolution)

def main(session):
    """Main processing function."""
    
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Parse input
    entries = parse_input(INPUT_FILE)
    for e in entries:
        emd_num = e['emd'].replace("EMD-", "")
        if emd_num is None:
            e['resolution'] = 5.0  # Default resolution
        else:
            e['resolution'] = get_emdb_resolution(emd_num)
            print(f"EMD {e['emd']} resolution: {e['resolution']}")
    print(f"\nParsed {len(entries)} entries:")
    for e in entries:
        print(f"  PDB: {e['pdb']}, DensityMap: {e['emd']}, Chain: {e['chain']}, Resolution: {e['resolution']}")
    
    # Initialize results file
    with open(RESULTS_FILE, "w") as out:
        out.write("pdb,emd,chain,correlation,status\n")
    
    # Store results for summary
    results = []
    
    # Process each entry
    for e in entries:
        pdb, emd, chain, resolution = e['pdb'], e['emd'], e['chain'], e['resolution']
        
        # Find files
        pdb_file = find_file(PDB_DIR, pdb, ['.pdb', '.cif'])
        
        if not pdb_file:
            print(f"\nWARNING: PDB file not found for {pdb}")
            results.append({'pdb': pdb, 'emd': emd, 'chain': chain, 'correlation': None, 'status': 'pdb not found'})
            continue
        
        # File name style: pdb_mrc
        mrc_with_pdb_file_name = pdb+ "_"+ emd
        session.logger.info(f"Looking for MRC file with base name: {mrc_with_pdb_file_name}")
        mrc_file = find_file(MRC_DIR, mrc_with_pdb_file_name, ['.mrc', '.map'])
        
        if not mrc_file:
            print(f"\nWARNING: MRC/MAP file not found for {emd}")
            results.append({'pdb': pdb, 'emd': emd, 'chain': chain, 'correlation': None, 'status': 'mrc not found'})
            continue
        
        print(f"\nProcessing {pdb} - {emd} - Chain {chain}...")
        print(f"  PDB: {pdb_file}")
        print(f"  MRC: {mrc_file}")
        
        # Process
        corr, _ = process_entry(session, pdb_file, mrc_file, resolution, OUTPUT_DIR, pdb, emd, chain, PADDING)
        
        # Save result
        results.append({'pdb': pdb, 'emd': emd, 'chain': chain, 'correlation': corr})
        
        # Append to CSV
        with open(RESULTS_FILE, "a") as out:
            out.write(f"{pdb},{emd},{chain},{corr}\n")

        # Add to Json
        with open(RESULTS_FILE.replace('.csv', '.json'), "w") as out_json:
            json.dump(results, out_json, indent=4)
        
        print(f"  Correlation: {corr}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Entry':<30} {'Correlation':<12} {'Status'}")
    print("-" * 60)
    
    for r in results:
        name = f"{r['pdb']}_{r['emd']}_{r['chain']}"
        corr = f"{r['correlation']:.4f}" if r['correlation'] else "N/A"
    
    # Statistics
    valid = [r['correlation'] for r in results if r['correlation'] is not None]
    if valid:
        print("\n" + "=" * 60)
        print("STATISTICS")
        print("=" * 60)
        print(f"Total entries:       {len(results)}")
        print(f"Successful:          {len(valid)}")
        print(f"Failed:              {len(results) - len(valid)}")
        print(f"Average correlation: {sum(valid)/len(valid):.4f}")
        print(f"Min correlation:     {min(valid):.4f}")
        print(f"Max correlation:     {max(valid):.4f}")
    
    print(f"\nResults saved to: {RESULTS_FILE}")
    print(f"Output files saved to: {OUTPUT_DIR}/")


# Run main function
main(session)
