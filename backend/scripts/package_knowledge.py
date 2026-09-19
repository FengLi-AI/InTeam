"""Bundle company knowledge into a backend-only deployment without runtime data."""
from pathlib import Path
import shutil

backend = Path(__file__).resolve().parents[1]
source = backend.parent / 'dify/knowledge-source'
target = backend / 'data/agent-knowledge/company'
for category in ('company-common', 'role-collaboration', 'project'):
    documents = sorted(p for p in (source / category).glob('*.md') if not p.name.startswith('._'))
    if not documents:
        raise SystemExit(f'Missing company knowledge: {category}')
    destination = target / category
    destination.mkdir(parents=True, exist_ok=True)
    for path in documents:
        shutil.copy2(path, destination / path.name)
print('Bundled company knowledge into backend/data/agent-knowledge/company')
