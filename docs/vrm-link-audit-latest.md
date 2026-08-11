# VRM link audit

Generated: `2026-08-11T20:25:11Z`
Catalog snapshot: `vrmcat-v1-2075d3173cece90b0e59bd0b`
Commit: `670179eda96ff6b1b08c6d31f9bb28afcbec4b1c`

## Outcome

- Unique concrete VRM links: **197**
- Raw references across DB and JSON artifacts: **1004**
- Valid VRM binaries: **189**
- Broken or unverified links: **8**
- Invalid URI references: **0**
- Full validated bytes: **1,095,987,636**

## Classification

| Classification | Links |
|---|---:|
| `healthy` | 158 |
| `healthy_with_transport_degradation` | 31 |
| `non_vrm_glb` | 3 |
| `not_glb` | 1 |
| `transient_transport_failure` | 4 |

## Collection coverage

| Collection | Links | Healthy | Problems |
|---|---:|---:|---:|
| `<unbound>` | 1 | 1 | 0 |
| `NeonGlitch86 Collection (Shape side)` | 1 | 1 | 0 |
| `NeonGlitch86-collection` | 12 | 9 | 3 |
| `a3ac-0x14c447` | 1 | 0 | 1 |
| `a3ac-0xc49a9a` | 1 | 0 | 1 |
| `avastars` | 1 | 1 | 0 |
| `boomboxheads-v2` | 1 | 1 | 0 |
| `chuddie` | 1 | 1 | 0 |
| `cyberbrokers` | 1 | 0 | 1 |
| `forgottenruneswizardscult` | 1 | 1 | 0 |
| `frutiger-anons` | 1 | 1 | 0 |
| `halloween-rising` | 67 | 67 | 0 |
| `meebits` | 1 | 1 | 0 |
| `metaanigen` | 1 | 1 | 0 |
| `misfitpixels` | 1 | 1 | 0 |
| `neonglitch86-collection-polygon-side` | 1 | 1 | 0 |
| `phettaverse-editions` | 1 | 1 | 0 |
| `pixelbeasts` | 1 | 0 | 1 |
| `voltz` | 1 | 0 | 1 |
| `xmas-chibis` | 103 | 103 | 0 |

## Links requiring attention

| Severity | Classification | Collection | Canonical URL | Primary error or note |
|---|---|---|---|---|
| error | `non_vrm_glb` | `voltz` | `https://assets.voltz.me/avatar/3d/bc88a9db815485d94a580a6d960265ab9d2325` | GLB has no extensions object |
| error | `non_vrm_glb` | `a3ac-0xc49a9a` | `https://cdn.chibilabs.dev/apes/GLBs/1.glb` | GLB has no extensions object |
| warning | `transient_transport_failure` | `cyberbrokers` | `https://m.cyberbrokers.com/eth/mech/1/files/mech_1k.0.vrm` | timeout fetching https://m.cyberbrokers.com/eth/mech/1/files/mech_1k.0.vrm |
| error | `not_glb` | `pixelbeasts` | `https://pixelbeasts3d.replit.app/beast/3064.vrm` | asset is not a GLB 2.0 file with a JSON first chunk |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://QmSpb8jZRtwDhpp7zjpfvU47GZyapmh8GvQApmzTxFcaLz/Avatar02_Warm.vrm` | Keep the canonical content URI and rely on multiple gateways; at least one transport is degrade… |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://QmSpb8jZRtwDhpp7zjpfvU47GZyapmh8GvQApmzTxFcaLz/Avatar05_Xmas.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://QmSpb8jZRtwDhpp7zjpfvU47GZyapmh8GvQApmzTxFcaLz/Avatar06_Cold.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://QmSpb8jZRtwDhpp7zjpfvU47GZyapmh8GvQApmzTxFcaLz/Avatar06_Neutral.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://QmSpb8jZRtwDhpp7zjpfvU47GZyapmh8GvQApmzTxFcaLz/Avatar06_Warm.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://QmSpb8jZRtwDhpp7zjpfvU47GZyapmh8GvQApmzTxFcaLz/Avatar07_Neutral.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://QmSpb8jZRtwDhpp7zjpfvU47GZyapmh8GvQApmzTxFcaLz/Avatar07_Warm.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://QmSpb8jZRtwDhpp7zjpfvU47GZyapmh8GvQApmzTxFcaLz/Avatar09_Neutral.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://QmSpb8jZRtwDhpp7zjpfvU47GZyapmh8GvQApmzTxFcaLz/Avatar09_Pastel.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://QmSpb8jZRtwDhpp7zjpfvU47GZyapmh8GvQApmzTxFcaLz/Avatar12_Xmas.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://QmSpb8jZRtwDhpp7zjpfvU47GZyapmh8GvQApmzTxFcaLz/Avatar13_Neutral.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://QmSpb8jZRtwDhpp7zjpfvU47GZyapmh8GvQApmzTxFcaLz/Avatar13_Pastel.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://QmSpb8jZRtwDhpp7zjpfvU47GZyapmh8GvQApmzTxFcaLz/Avatar13_Warm.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://QmSpb8jZRtwDhpp7zjpfvU47GZyapmh8GvQApmzTxFcaLz/Avatar14_Warm.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `boomboxheads-v2` | `ipfs://QmURAuSRmFFAyragN3h6M6thhMhBPQmNgoNJApDSvob3D5/30.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `halloween-rising` | `ipfs://QmXyEuwbgUfMG7WzRZys6JnS6DJvxqkPGDseZmHM8wLJm1/Avatar01_v1_Cute_Green.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `halloween-rising` | `ipfs://QmXyEuwbgUfMG7WzRZys6JnS6DJvxqkPGDseZmHM8wLJm1/Avatar01_v2_Stylized_Green.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `halloween-rising` | `ipfs://QmXyEuwbgUfMG7WzRZys6JnS6DJvxqkPGDseZmHM8wLJm1/Avatar04_v2_Stylized_Brown.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `halloween-rising` | `ipfs://QmXyEuwbgUfMG7WzRZys6JnS6DJvxqkPGDseZmHM8wLJm1/Avatar05_v1_Cute_Black.vrm` | ipfs.io: timeout |
| error | `non_vrm_glb` | `a3ac-0x14c447` | `ipfs://QmbAEjyVKPv6848vk1UK8zMoR86sJXpkkazRp4tYSc6hjU/1.glb` | GLB has no extensions object |
| warning | `healthy_with_transport_degradation` | `chuddie` | `ipfs://bafybeiaplpkifduvx7ma7d2x7zrhdszhubf7lj3jmb5wxujkxedxxpziiq/127.vrm` | ipfs.io: timeout |
| warning | `transient_transport_failure` | `NeonGlitch86-collection` | `ipfs://bafybeibeegcbxo3itcucdjrbrvum5f3y7pb3rbhsvkx5c2crevtn2nwore/gothamYellowNycss.vrm` | timeout fetching https://bafybeibeegcbxo3itcucdjrbrvum5f3y7pb3rbhsvkx5c2crevtn2nwore.ipfs.dweb.… |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://bafybeiccs333rwnme2sjioeg4gzntw3rd7wt2l6y3yv3lqhcmaufqom44m/Avatar02_Warm.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://bafybeiccs333rwnme2sjioeg4gzntw3rd7wt2l6y3yv3lqhcmaufqom44m/Avatar03_Neutral.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://bafybeiccs333rwnme2sjioeg4gzntw3rd7wt2l6y3yv3lqhcmaufqom44m/Avatar06_Neutral.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://bafybeiccs333rwnme2sjioeg4gzntw3rd7wt2l6y3yv3lqhcmaufqom44m/Avatar06_Warm.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://bafybeiccs333rwnme2sjioeg4gzntw3rd7wt2l6y3yv3lqhcmaufqom44m/Avatar07_Neutral.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://bafybeiccs333rwnme2sjioeg4gzntw3rd7wt2l6y3yv3lqhcmaufqom44m/Avatar09_Neutral.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://bafybeiccs333rwnme2sjioeg4gzntw3rd7wt2l6y3yv3lqhcmaufqom44m/Avatar09_Pastel.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://bafybeiccs333rwnme2sjioeg4gzntw3rd7wt2l6y3yv3lqhcmaufqom44m/Avatar13_Pastel.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `xmas-chibis` | `ipfs://bafybeiccs333rwnme2sjioeg4gzntw3rd7wt2l6y3yv3lqhcmaufqom44m/Avatar15_Warm.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `halloween-rising` | `ipfs://bafybeiepddccawiq5awdejukaa3h2knrlv7anjp4fprxfxhrlaycsknicq/Avatar01_v2_Stylized_Green.vrm` | ipfs.io: timeout |
| warning | `healthy_with_transport_degradation` | `halloween-rising` | `ipfs://bafybeiepddccawiq5awdejukaa3h2knrlv7anjp4fprxfxhrlaycsknicq/Avatar04_v2_Stylized_Brown.vrm` | ipfs.io: timeout |
| warning | `transient_transport_failure` | `NeonGlitch86-collection` | `ipfs://bafybeig4dmkps7kxuacwnw2v5ygas55bondtyzt73y4hqtev425ojgfjfi/Pepe_TrashCan.vrm` | timeout fetching https://bafybeig4dmkps7kxuacwnw2v5ygas55bondtyzt73y4hqtev425ojgfjfi.ipfs.dweb.… |
| warning | `transient_transport_failure` | `NeonGlitch86-collection` | `ipfs://bafybeigazr4q4mkbmu5vrkshznqyb7vp4u4q2tcjscstr3dnw4yfeyzm3q/ROCKETMAN.vrm` | timeout fetching https://bafybeigazr4q4mkbmu5vrkshznqyb7vp4u4q2tcjscstr3dnw4yfeyzm3q.ipfs.dweb.… |

## Templates not directly audited

Templates require concrete token IDs. They are listed here so they are not mistaken for tested links.

| Collection | Origin | Template |
|---|---|---|
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[10].resolution.template` | `api.meebits.app/v2/3d/larvalabs_vrm/{id}` |
| `` | `json:static/data/collections.261dc5d177bb.json:$.collections[30].vrm_url_pattern` | `api.meebits.app/v2/3d/larvalabs_vrm/{id}` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[0].resolution.metadata_u…` | `https://allstarz.world/api/metadata/{token_id}.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[24].resolution.metadata_…` | `https://api.cryptoavatars.io/v1/opensea/assets/1/0xc1def47cf1e15ee8c2a92f4e0e968372880d18d1/{token_id}/metada…` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[20].resolution.metadata_…` | `https://avastars.io/metadata/{token_id}/metadata.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[21].resolution.metadata_…` | `https://cdn-api.niftykit.com/reveal/clk12ewde0001l70fazx72b9v/{token_id}/metadata.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[26].resolution.metadata_…` | `https://connect.omnimorphs.com/api/v1/external/omnimorphs/{token_id}/metadata.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[32].resolution.metadata_…` | `https://connect.omnimorphs.com/api/v1/external/omnimorphs/{token_id}/metadata.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[8].resolution.metadata_u…` | `https://d1kgk9u8ytew77.cloudfront.net/ipfs/QmT64bM8LTCwtNGmj5mrh7V9oHmzKwwVyygTD1mjNqaGGX/{token_id}/metadata…` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[5].resolution.metadata_u…` | `https://dickbuttverse.sfo3.digitaloceanspaces.com/json/{token_id}.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[38].resolution.metadata_…` | `https://ipfs.io/ipfs/QmRWhj1Gnv2LLJiLpCMGbdi3PPe9VTp5VHzsTpmSg4iCRy/{token_id}/metadata.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[6].resolution.metadata_u…` | `https://ipfs.io/ipfs/QmRdNB3Q6Q5gVWnduBmxNZb4p9zKFmM3Qx3tohBb8B2KRK/{token_id}/metadata.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[11].resolution.metadata_…` | `https://ipfs.io/ipfs/QmTiW6V5AG3tVJuewTV2NX1yqFJzLb28MpS7ctTHnPzKXT/{token_id}/metadata.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[12].resolution.metadata_…` | `https://ipfs.io/ipfs/QmarCNTJJYahzZKFjFfZVcpLAhMNV5VwWN8bsqiKsCVAc7/{token_id}/metadata.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[15].resolution.metadata_…` | `https://ipfs.io/ipfs/bafybeib6ii2hpiknnyyinrbywmulnjnznwxpwsubigneip54tzdus66xpi/{token_id}/metadata.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[2].resolution.metadata_u…` | `https://ipfs.io/ipfs/bafybeiebycjasqhzuomax77otu7koswj5p4awgmw3hrgjk2vh4xiriv5a4/{token_id}/metadata.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[4].resolution.metadata_u…` | `https://ipfs.io/ipfs/bafybeih5g36ula4wzw6dmoso6tbimzh2dbfurcqzvv5mbosl5jdjhkzkxu/{token_id}/metadata.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[3].resolution.metadata_u…` | `https://m.cyberbrokers.com/eth/mech/{token_id}/metadata.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[33].resolution.metadata_…` | `https://rstlss-content.xyz/claire/metadata/{token_id}.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[34].resolution.metadata_…` | `https://theklubrises.mypinata.cloud/ipfs/QmXQMrhqwJ2vJFbxCjJfZBZ7GTfrCwUJzJhJcPnQv9fdRf/{token_id}/metadata.j…` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[35].resolution.metadata_…` | `https://tsc.nftapi.art/meta/{token_id}/metadata.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[27].resolution.metadata_…` | `https://void-explorer.netlify.app/void_metadata/{token_id}/metadata.json` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[1].resolution.template` | `ipfs://bafybeibe4axqsukdfeuy4fnrtti4dko7ph3fopl6xkr3tsdyp3zhhl5eyu/{id}.vrm` |
| `` | `json:static/data/collections.261dc5d177bb.json:$.collections[6].vrm_url_pattern` | `ipfs://bafybeibe4axqsukdfeuy4fnrtti4dko7ph3fopl6xkr3tsdyp3zhhl5eyu/{id}.vrm` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[7].resolution.template` | `nftz.forgottenrunes.com/dev/3d/wizards/{id}/wizard_{id}.vrm` |
| `` | `json:static/data/collections.261dc5d177bb.json:$.collections[22].vrm_url_pattern` | `nftz.forgottenrunes.com/dev/3d/wizards/{id}/wizard_{id}.vrm` |
| `` | `json:static/data/avatar-manifest-v1.json:$.collections[17].resolution.template` | `pixelbeasts3d.replit.app/beast/{id}.vrm` |
| `` | `json:static/data/collections.261dc5d177bb.json:$.collections[48].vrm_url_pattern` | `pixelbeasts3d.replit.app/beast/{id}.vrm` |
| `boomboxheads-v2` | `db:collections.vrm_url_pattern` | `ipfs://bafybeibe4axqsukdfeuy4fnrtti4dko7ph3fopl6xkr3tsdyp3zhhl5eyu/{id}.vrm` |
| `forgottenruneswizardscult` | `db:collections.vrm_url_pattern` | `nftz.forgottenrunes.com/dev/3d/wizards/{id}/wizard_{id}.vrm` |
| `meebits` | `db:collections.vrm_url_pattern` | `api.meebits.app/v2/3d/larvalabs_vrm/{id}` |
| `pixelbeasts` | `db:collections.vrm_url_pattern` | `pixelbeasts3d.replit.app/beast/{id}.vrm` |

## Interpretation

- `healthy` means the complete binary was fetched, its declared and observed lengths matched, and a VRM 0.x or VRM 1.0 extension was present.
- `healthy_with_transport_degradation` means the content is valid but one or more gateway transports failed. The canonical content URI should be retained.
- HTTP reachability alone is not treated as VRM proof.
- This report is read-only. Canonical identity changes and link replacements require a separate reviewed patch.
