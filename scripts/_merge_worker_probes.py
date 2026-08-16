import json, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
probe_path = root / 'data' / 'avatar_inventory_probe.json'
existing = json.loads(probe_path.read_text())
probes_by_url = {p.get('url'): p for p in existing.get('probes', [])}
cols = {c.get('catalogId'): c for c in existing.get('collections', [])}

for wf in sorted((root / '.worker').glob('*-probes.json')):
    d = json.loads(wf.read_text())
    cid = d.get('catalogId') or d.get('collectionId')
    if not cid:
        continue
    merged = []
    seen = set()
    for p in d.get('probes', []):
        u = p.get('url')
        if u not in seen:
            seen.add(u)
            merged.append(p)
    probes_by_url.update({p.get('url'): p for p in merged})
    summary = {k: d.get(k) for k in ('catalogId', 'name', 'metadataComplete', 'avatarReadyComplete', 'structurallyComplete', 'urls', 'validAssetUrls', 'validVrmUrls', 'validRiggedGlbUrls', 'validRiggedFbxUrls') if k in d}
    cols[cid] = summary
    print(f'merged {cid}: {len(merged)} probes')

all_probes = list(probes_by_url.values())
payload = {
    'schema': existing.get('schema'),
    'generatedAt': existing.get('generatedAt'),
    'summary': {
        'collections': len(cols),
        'avatarReadyCompleteCollections': sum(bool(c.get('avatarReadyComplete')) for c in cols.values()),
        'urls': len(all_probes),
        'validAvatarUrls': sum(bool(p.get('validAvatar')) for p in all_probes),
        'validVrmUrls': sum(p.get('actualFormat') == 'vrm' and p.get('validAvatar') for p in all_probes),
        'validRiggedGlbUrls': sum(p.get('actualFormat') == 'glb' and p.get('validAvatar') for p in all_probes),
        'validRiggedFbxUrls': sum(p.get('actualFormat') == 'fbx' and p.get('validAvatar') for p in all_probes),
    },
    'collections': list(cols.values()),
    'probes': all_probes,
}
probe_path.write_text(json.dumps(payload, indent=2) + '\n')
print('probe file:', len(all_probes), 'probes,', len(cols), 'collections')
