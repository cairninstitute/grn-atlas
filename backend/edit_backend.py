import sys

def replace_between(lines, start_marker, end_marker_exclusive, new_lines):
    """Replace lines between start_marker (inclusive) and end_marker_exclusive (exclusive) with new_lines."""
    new_content = []
    i = 0
    n = len(lines)
    while i < n:
        if lines[i].strip() == start_marker.strip():
            # found start
            new_content.extend(new_lines)
            # skip until end_marker_exclusive
            i += 1
            while i < n and not lines[i].strip().startswith(end_marker_exclusive.strip()):
                i += 1
            # now i points to the line that starts with end_marker_exclusive (we keep it)
            continue
        else:
            new_content.append(lines[i])
            i += 1
    return new_content

with open('main.py', 'r') as f:
    lines = f.readlines()

# 1. Insert Pydantic model after Intervention class
# Find line index of "class Intervention(BaseModel):"
for idx, line in enumerate(lines):
    if line.strip().startswith('class Intervention(BaseModel):'):
        insert_idx = idx + 1
        # find the line after the class definition (look for a line that starts with '#')
        # We'll just insert after the class block; we can assume class ends before a line that starts with '#'
        while insert_idx < len(lines) and not lines[insert_idx].strip().startswith('#'):
            insert_idx += 1
        # insert at insert_idx
        model_lines = [
            '\n',
            'class PathFindingRequest(BaseModel):\n',
            '    source_gene_id: str\n',
            '    target_symbol: str\n',
            '    max_depth: int = 3\n',
            '    limit: int = 20\n',
            '    min_confidence: float = 0.3\n',
            '    regulation_type: List[str] = ["activation", "repression"]\n',
            '\n'
        ]
        lines = lines[:insert_idx] + model_lines + lines[insert_idx:]
        break

# 2. Replace the find_paths function
# Find the line with "@app.post(\"/api/v1/pathways/pathfinding\""
for idx, line in enumerate(lines):
    if line.strip().startswith('@app.post(\"/api/v1/pathways/pathfinding\"'):
        start_idx = idx
        # find the line before the next @app.post (for predict-cascade)
        end_idx = idx + 1
        while end_idx < len(lines) and not lines[end_idx].strip().startswith('@app.post'):
            end_idx += 1
        # end_idx is the line of the next @app.post; we want to replace [start_idx, end_idx)
        new_func_lines = [
            '@app.post(\"/api/v1/pathways/pathfinding\", response_model=Dict[str, List[Point]])\n',
            'async def find_orders(request: PathFindingRequest):\n',
            '    \"\"\"\n',
            '    Find regulatory paths between two genes using BFS algorithm\n',
            '    \"\"\"\n',
            '    source = db.get_gene(request.source_gene_id)\n',
            '    target_results = db.search_genes(request.target_symbol, limit=1)\n',
            '    \n',
            '    if not source or not target_results:\n',
            '        raise HTTPException(status_code=404, detail=\"Gene not found\")\n',
            '    \n',
            '    target_gene = target_results[0]\n',
            '    \n',
            '    # Simple BFS pathfinding (in production, use more sophisticated algorithm)\n',
            '    paths = []\n',
            '    visited = set()\n',
            '    queue = [(request.source_gene_id, [source], [], [])]\n',
            '    \n',
            '    while queue and len(paths) < request.limit:\n',
            '        current_id, current_path, regulations, confidences = queue.pop(0)\n',
            '        \n',
            '        if current_id == target_gene.id:\n',
            '            path_genes = [PathGene(id=g.id, symbol=g.symbol, name=g.name) for g in current_path]\n',
            '            sources = [[\"TRRUST\"] for _ in regulations]\n',
            '            paths.append(Path(\n',
            '                genes=path_genes,\n',
            '                regulation_types=regulations,\n',
            '                confidences=confidences,\n',
            '                sources=sources,\n',
            '                overall_confidence=sum(confidences) / len(confidences) if confidences else 0.0\n',
            '            ))\n',
            '            continue\n',
            '        \n',
            '        if len(current_path) < request.max_depth:\n',
            '            targets = db.get_targets(current_id, request.min_confidence)\n',
            '            for target in targets:\n',
            '                if target.id not in visited and target.regulation_type in request.regulation_type:\n',
            '                    visited.add(target.id)\n',
            '                    target_gene_obj = db.get_gene(target.id)\n',
            '                    if target_gene_obj:\n',
            '                        queue.append((\n',
            '                            target.id,\n',
            '                            current_path + [target_gene_obj],\n',
            '                            regulations + [target.regulation_type],\n',
            '                            confidences + [target.confidence]\n',
            '                        ))\n',
            '    \n',
            '    return {\"paths\": paths}\n',
            '\n'
        ]
        # Note: we need to keep the same indentation (4 spaces) but we already have them.
        # Replace
        lines = lines[:start_idx] + new_func_lines + lines[end_idx:]
        break

with open('main.py', 'w') as f:
    f.writelines(lines)
