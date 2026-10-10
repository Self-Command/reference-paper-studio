"""Consumer approval checks plus a separately pinned public Word runtime."""
import importlib
import json
import os
from pathlib import Path
import sys
from contextlib import contextmanager
from .runtime import require_actions, StudioError, run, write_json, digest, confined
from .contracts import ROOT


def load_runtime():
    require_actions()
    pin = json.loads((ROOT / 'catalog/word-engine.json').read_text())
    directory = Path(os.environ.get('WMS_ENGINE_ROOT', '')).resolve()
    if not (directory / 'src/word_module_studio').is_dir(): raise StudioError('WORD_ENGINE_CHECKOUT_MISSING')
    commit = run(['git', '-C', directory, 'rev-parse', 'HEAD']).strip()
    if commit != pin['commit']: raise StudioError('WORD_ENGINE_COMMIT_MISMATCH')
    sys.path.insert(0, str(directory / 'src'))
    sys.path.insert(0, str(directory))
    runtime = importlib.import_module('word_module_studio')
    if Path(runtime.__file__).resolve().parent != directory / 'src/word_module_studio': raise StudioError('WORD_ENGINE_IMPORT_MISMATCH')
    if runtime.__version__ != pin['version']: raise StudioError('WORD_ENGINE_VERSION_MISMATCH')
    return directory, pin


@contextmanager
def engine_directory(directory):
    previous = Path.cwd()
    try:
        os.chdir(directory)
        yield
    finally: os.chdir(previous)


def export_composition(source, definition, fonts, output, *, metadata, variant='front', resources=()):
    """Technical composition API; caller owns scientific and publication gates."""
    require_actions()
    directory, pin = load_runtime()
    source, output = Path(source).resolve(), Path(output).resolve()
    resources = [Path(resource).resolve() for resource in resources]
    adapter = importlib.import_module('consumers.reference_paper')
    from word_module_studio.render import render
    with engine_directory(directory):
        result = adapter.export(source, definition, fonts, output, metadata=metadata, variant=variant, resources=resources)
        proof = render(output, output.parent / 'proof')
    result.update(word_engine=pin, proof=proof)
    write_json(output.with_suffix('.consumer.json'), result)
    if not proof['automatic_pass']: raise StudioError('WORD_ENGINE_PROOF_FAILED: ' + str(proof['issues']))
    return result


def export(root, request, output):
    """Word-only application entry retains real consumer approval boundaries."""
    require_actions()
    root, output = Path(root).resolve(), Path(output).resolve()
    _, pin = load_runtime()
    if pin['state'] != 'released' and os.environ.get('RPS_CANDIDATE_BUILD') != 'true': raise StudioError('WORD_ENGINE_CANDIDATE_NOT_RELEASED')
    if set(request.get('outputs', [])) - {'docx', 'docx-proof-pdf', 'previews'}:
        raise StudioError('WORD_ONLY_OUTPUTS_REQUIRED: LaTeX remains in the dual-export consumer')
    from .registry import resolve
    from .approvals import check_export
    from .composition import load_composition
    from .manuscript import parse, model_gate
    from .components import check_content, check_metadata
    _, policy, identity = resolve(request)
    approval = check_export(root, request, identity)
    source = confined(root, request['manuscript'])
    ast, equations = parse(source, output / 'content-check')
    check_content(ast, policy)
    from .frontmatter import extract
    metadata = extract(ast)
    if request.get('metadata'):
        supplied = json.loads(confined(root, request['metadata']).read_text())
        if any(key in metadata and metadata[key] != value for key, value in supplied.items()): raise StudioError('METADATA_CONFLICT')
        metadata.update(supplied)
    metadata = check_metadata(metadata, policy)
    gate = model_gate(root, request['manuscript'], request.get('model_evidence'), request.get('document_kind') == 'paper')
    if request.get('expected_equations') is not None and len(equations) != request['expected_equations']: raise StudioError('EQUATION_COUNT_CHANGED')
    definition, _ = load_composition(identity['id'], identity['version'])
    definition['policy'] = policy
    resources = [confined(root, entry['path']) for entry in request['files'] if entry['role'] in ('image', 'bibliography')]
    result = export_composition(source, definition, policy['fonts'], output / 'manuscript.docx', metadata=metadata,
        variant=identity['variant'], resources=resources)
    result.update(approval_binding=approval, model_gate=gate, template_request=identity, input_sha256=digest(source))
    write_json(output / 'word-engine-acceptance.json', result)
    return result
