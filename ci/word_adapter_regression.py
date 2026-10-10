"""W5 consumer uses a pinned external engine, never copies its layout code."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from studio.runtime import require_actions, write_json, StudioError
from studio.word_adapter import export_composition
from studio.composition import load_composition

require_actions()
root = Path(__file__).resolve().parents[1]
fonts = {'latin': 'Liberation Serif', 'cjk': 'Noto Serif CJK SC', 'math': 'TeX Gyre Pagella Math'}
results = []
for path in sorted((root / 'templates').glob('*/template.json')):
    descriptor = json.loads(path.read_text())
    definition, policy = load_composition(descriptor['id'], descriptor['version'])
    definition['policy'] = policy
    for variant in ('front', 'end'):
        folder = root / 'build/word-adapter' / descriptor['id'] / variant; folder.mkdir(parents=True, exist_ok=True)
        source = folder / 'source.md'
        source.write_text('# Shared engine composition\n\n中文与英文真实内容。\n\n'
            '$$x=\\frac{1+y}{1+z}\\tag{E1}$$\n\n| Key | Value |\n|---|---|\n| Retained | 123 |\n\nTable: Retained values', encoding='utf-8')
        result = export_composition(source, definition, fonts, folder / 'document.docx', variant=variant,
            metadata={key + '_' + language: 'Composition proof' for language in policy.get('metadata_languages', ['zh', 'en']) for key in policy['front_roles'] if key == 'title'})
        results.append({'template': descriptor['id'], 'variant': variant, 'automatic_pass': result['proof']['automatic_pass']})
model_descriptor = json.loads((root / 'templates/general-modeling/template.json').read_text())
definition, policy = load_composition('general-modeling', model_descriptor['version'])
policy['body_columns'] = 2; definition['policy'] = policy
result = export_composition(root / 'fixtures/model/model.md', definition, fonts, root / 'build/word-adapter/model/document.docx',
    metadata=json.loads((root / 'fixtures/model/metadata.json').read_text()))
if result['display_equations'] != 30 or {e['number'] for e in result['equations']} != {'M' + str(i) for i in range(1, 31)}:
    raise StudioError('WORD_ADAPTER_MODEL_IDENTITY_CHANGED')
results.append({'case': 'unmodified-model-M1-M30', 'automatic_pass': result['proof']['automatic_pass']})
write_json(root / 'build/word-adapter/summary.json', {'consumer_commit': os.environ['GITHUB_SHA'], 'cases': results,
    'word_engine': result['word_engine'], 'formal_paper_approval': False, 'md_structure_approval': 'pending'})
