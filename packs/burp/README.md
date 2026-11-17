# burp — first-party dogfood pack (not shipped)

**Status (NEX-17 / P3.12):** checkout-only example. This pack is
**not** included in the PyPI/wheel install and is **not** on the
default load path (`~/.nexusrecon/packs/`).

## What it is

Bidirectional Burp Suite XML handoff used to dogfood the Recon Pack
format in an editable checkout:

- import Burp site-map XML into the Living Graph
- export campaign in-scope domains as Burp-importable scope XML

## How to try it (editable checkout only)

```bash
# From the repo root — symlink into the operator pack dir:
mkdir -p ~/.nexusrecon/packs
ln -sfn "$(pwd)/packs/burp" ~/.nexusrecon/packs/burp
nexusrecon packs list
```

Or pass an explicit root:

```bash
nexusrecon packs list --pack-dir ./packs
```

## What we decided not to do

Including `packs/burp` in the wheel was rejected for 1.0: there is
no curated marketplace, the default load path is still
`~/.nexusrecon/packs`, and advertising an in-wheel “stable” pack
would overclaim. Loader + install CLI remain experimental; see
ARCHITECTURE.md §17.
