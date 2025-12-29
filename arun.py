import pandas as pd
from collections import defaultdict
import re
import numpy as np

# -----------------------------
# 1. Define LOS Bins
# -----------------------------
bin_edges = [-np.inf, 1, 2, 3, 5, 10, 20, 30, 40, 50, 75, np.inf]
bin_labels = [
    '0-1', '1-2', '2-3', '3-5', '5-10',
    '10-20', '20-30', '30-40', '40-50', '50-75', '75+'
]

# Add LOS_Bin to df_apr
df_apr['LOS'] = pd.to_numeric(df_apr['LOS'], errors='coerce')
df_apr['LOS_Bin'] = pd.cut(
    df_apr['LOS'],
    bins=bin_edges,
    labels=bin_labels,
    right=True,
    include_lowest=True
)

# -----------------------------
# 2. Helper function to extract diagnosis code and type (MCC/CC)
# -----------------------------
def parse_sdx(code):
    code = str(code).strip().upper()
    if code in ['NAN', '', 'NONE', 'NULL']:
        return (None, None)
    mcc_match = re.search(r'-\s*MCC\s*$', code)
    if mcc_match:
        return (code[:mcc_match.start()].strip(), 'MCC')
    cc_match = re.search(r'-\s*CC\s*$', code)
    if cc_match:
        return (code[:cc_match.start()].strip(), 'CC')
    if code in mccandcclist:
        return (code, mccandcclist[code])
    return (None, None)

# -----------------------------
# 3. Load MCC/CC List
# -----------------------------
mccandcclist_df = pd.read_excel('MCCCCList.xlsx')
mccandcclist_df['ICDCode'] = mccandcclist_df['ICDCode'].str.strip().str.upper()
mccandcclist = dict(zip(mccandcclist_df['ICDCode'], mccandcclist_df['MCCorCC']))

# -----------------------------
# 4. Define A-side SDX columns
# -----------------------------
a_sdx_columns = [f'A_DX{i}' for i in range(2, 25)]

# -----------------------------
# 5. Initialize stats dictionary
# -----------------------------
# Key: (DRG, PRIM_DX, SDX_Set, LOS_Bin)
stats = defaultdict(lambda: {
    'Total_Claims': 0,
    'Approved': 0,
    'Denied': 0,
    'Total_Savings': 0.0
})

# -----------------------------
# 6. Loop through df_apr
# -----------------------------
for idx, row in df_apr.iterrows():
    # Skip if LOS_Bin is missing
    if pd.isna(row['LOS_Bin']):
        continue
        
    drg = row['DRG']
    pdx = str(row['PRIM_DX']).strip().upper()
    los_bin = row['LOS_Bin']
    audit_result = row['IDSavings']
    status = 'APPROVED' if audit_result == 0 else 'DENIED'

    # --- Extract A-side SDX codes ---
    sdx_mcc = []
    sdx_cc = []
    for col in a_sdx_columns:
        if col not in row.index:
            continue
        code = row[col]
        if pd.isna(code):
            continue
        base_code, sdx_type = parse_sdx(code)
        if not base_code:
            continue
        if sdx_type == 'MCC':
            sdx_mcc.append(base_code)
        elif sdx_type == 'CC':
            sdx_cc.append(base_code)

    # Build SDX_Set: prioritize MCC > CC
    if sdx_mcc:
        sdx_set = tuple(sorted(set(sdx_mcc)))
    elif sdx_cc:
        sdx_set = tuple(sorted(set(sdx_cc)))
    else:
        sdx_set = tuple()

    # Group key includes LOS_Bin
    group_key = (drg, pdx, sdx_set, los_bin)

    # Update stats
    stats[group_key]['Total_Claims'] += 1

    if status == 'APPROVED':
        stats[group_key]['Approved'] += 1
    else:
        stats[group_key]['Denied'] += 1
        if audit_result > 0:
            stats[group_key]['Total_Savings'] += float(audit_result)

# -----------------------------
# 7. Build Final DataFrame
# -----------------------------
final_data = []

for key, data in stats.items():
    drg, pdx, sdx_set, los_bin = key
    total_claims = data['Total_Claims']
    approved = data['Approved']
    denied = data['Denied']
    total_savings = round(data['Total_Savings'], 2)

    denial_percent = round(denied / total_claims * 100, 2) if total_claims else 0
    avg_saving_per_claim = round(total_savings / total_claims, 2) if total_claims else 0

    final_data.append({
        'DRG': drg,
        'PRIM_DX': pdx,
        'SDX_Set': ', '.join(sdx_set) if sdx_set else '',
        'LOS_Bin': los_bin,
        'Total_Claims': total_claims,
        'Approved': approved,
        'Denied': denied,
        'Denial_Percent': denial_percent,
        'Total_Savings': total_savings,
        'Avg_Saving_Per_Claim': avg_saving_per_claim
    })

# -----------------------------
# 8. Export to Excel
# -----------------------------
output_df = pd.DataFrame(final_data)
output_df = output_df.sort_values(
    by=['Total_Claims', 'DRG', 'LOS_Bin'],
    ascending=[False, True, True]
)

# output_file = "DRG_PDX_SDXSet_LOSBin_Simplified_Analysis.xlsx"
# output_df.to_excel(output_file, index=False)

print(f"\n✅ Simplified LOS-Bin analysis completed for {len(output_df)} groups.")
# print(f"📊 Results saved to '{output_file}'")