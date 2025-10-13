import json, os
from pathlib import Path
import requests

GRAPHQL_URL = "http://localhost:3000/graphql"
OUT = Path("site/site_data/elements.json")

QUERY = """
query AssetDocs {
  assetNodes {
    assetKey { path }
    groupName
    description
    dependencies { asset { assetKey { path } } }
    metadataEntries {
      ... on TableSchemaMetadataEntry { schema { columns { name type description } } }
    }
  }
}
""".strip()

def slug(path):  # "/".join + spaces->_
    return "/".join(path).replace(" ", "_")

# 1) Fetch
r = requests.post(
    GRAPHQL_URL,
    json={"query": QUERY},
    headers={"Content-Type":"application/json","Accept":"application/json"},
    timeout=60,
)
nodes = r.json()["data"]["assetNodes"]

# 2) Collect groups (stable order of first appearance)
groups_order = []
for n in nodes:
    g = n.get("groupName") or "ungrouped"
    if g not in groups_order:
        groups_order.append(g)

# simple fixed palette
PALETTE = [
    "#2563eb","#16a34a","#f59e0b","#ef4444","#8b5cf6",
    "#14b8a6","#f43f5e","#f97316","#22c55e","#06b6d4",
    "#eab308","#64748b"
]
group_color = {g: PALETTE[i % len(PALETTE)] for i, g in enumerate(groups_order)}

def group_id(g):
    return "group__" + g.replace(" ", "_").replace(":", "_")


elements = []
id_to_group = {}

# 3) Add compound parent nodes (one per group)
for g in groups_order:
    elements.append({
        "data": { "id": group_id(g), "label": g, "type": "group" }
    })

# 4) Add asset nodes
for n in nodes:
    path = n["assetKey"]["path"]
    _id = slug(path)
    g = n.get("groupName") or "ungrouped"
    id_to_group[_id] = g

    # first table schema, if any
    columns = []
    for me in n.get("metadataEntries", []):
        s = me.get("schema")
        if s and s.get("columns"):
            columns = s["columns"]
            break
    
    description = n.get("description")
    if description is None:
        description = ""
    else:
        if description == "None":
            description = ""
        if "#### Raw SQL:" in description:
            description = description.split("#### Raw SQL:")[0]

    
    description = description.replace("```sql\n", "```sql\n    ")
    elements.append({
        "data": {
            "id": _id,
            "label": path[-1],
            "description": description,
            "url": f"assets/{_id}.html",
            "columns": columns,
            "group": g,
            "color": group_color[g],
            "parent": group_id(g)   # ⟵ puts node inside its group box
        }
    })

# 5) Add edges (mark cross-group edges)
seen = set()
for n in nodes:
    tgt = slug(n["assetKey"]["path"])
    for d in n.get("dependencies", []):
        src = slug(d["asset"]["assetKey"]["path"])
        eid = f"{src}->{tgt}"
        if eid in seen: 
            continue
        seen.add(eid)
        cross = 1 if id_to_group.get(src) != id_to_group.get(tgt) else 0
        elements.append({ "data": { "id": eid, "source": src, "target": tgt, "cross": cross } })

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"elements": elements}, indent=2), encoding="utf-8")
print(f"elements.json -> {OUT}")
