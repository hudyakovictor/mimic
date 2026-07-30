from pathlib import Path
root=Path(__file__).resolve().parents[1]
hits=[]
for p in root.rglob('*'):
    if p.is_file() and any(part not in {'.git'} for part in p.parts):
        try: text=p.read_text(encoding='utf-8')
        except UnicodeDecodeError: continue
        if 'MG-STUB' in text: hits.append(str(p.relative_to(root)))
print('Explicit MG-STUB inventory:')
for path in sorted(set(hits)): print('-',path)
print(f'Total files with explicit stubs: {len(set(hits))}')
