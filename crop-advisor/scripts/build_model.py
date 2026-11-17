"""Execute the user's notebook unchanged, then export its functions and reports.

Run from the project root: python scripts/build_model.py
This deliberately preserves the notebook's model selection and calibration logic.
"""
import json
import os
from pathlib import Path
import sys
import ast

ROOT = Path(__file__).resolve().parents[1]
os.environ['CROP_PROJECT_DIR'] = str(ROOT)
os.environ['MPLBACKEND'] = 'Agg'
sys.path.insert(0, str(ROOT))
import matplotlib.pyplot as plt
from IPython.display import display
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix

(ROOT / 'reports').mkdir(exist_ok=True)
(ROOT / 'reports/plots').mkdir(exist_ok=True)
notebook = json.loads((ROOT / 'model/model_train_v2.ipynb').read_text(encoding='utf-8'))
scope = {'display': display, '__name__': '__main__'}
plot_names = iter(['confusion-matrix', 'feature-importance', 'reliability'])
def save_plot():
    name = next(plot_names, 'notebook-plot')
    plt.savefig(ROOT / f'reports/plots/{name}.png', dpi=150, bbox_inches='tight')
    plt.close('all')
plt.show = save_plot
for index, cell in enumerate(notebook['cells']):
    if cell['cell_type'] == 'code':
        print(f'Executing notebook cell {index}', flush=True)
        exec(compile(''.join(cell['source']), f'notebook-cell-{index}', 'exec'), scope)

# Export the exact input policy used by the notebook, without importing training code.
functions = []
for cell in notebook['cells']:
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        for node in ast.parse(source).body:
            if isinstance(node, ast.FunctionDef) and node.name in ('validate_input', 'assess_input'):
                functions.append(ast.get_source_segment(source, node))
(ROOT / 'backend/notebook_policy.py').write_text(
    '# Extracted unchanged from model_train_v2.ipynb.\nimport numpy as np\nimport pandas as pd\n\n' + '\n\n'.join(functions), encoding='utf-8')

model, X_test, y_test = (scope[k] for k in ('final_model', 'X_test', 'y_test'))
pred = model.predict(X_test)
classes = list(model.classes_)
baseline = pred.copy()
rng = np.random.default_rng(42)
robustness = []
for fraction in (0.01, 0.05, 0.10):
    for feature in ['all'] + scope['FEATURES']:
        noisy = X_test.copy()
        selected = scope['FEATURES'] if feature == 'all' else [feature]
        for f in selected:
            noisy[f] += rng.normal(0, fraction * scope['X_train'][f].std(), len(noisy))
        robustness.append({'noise_std_fraction': fraction, 'feature': feature,
            'prediction_flip_rate': float(np.mean(model.predict(noisy) != baseline))})
report = {'training': scope['metadata']['training'],
    'classwise': classification_report(y_test, pred, output_dict=True, zero_division=0),
    'confusion_matrix': {'labels': classes, 'matrix': confusion_matrix(y_test, pred, labels=classes).tolist()},
    'comparison': scope['results_df'].to_dict(orient='records'),
    'calibration': scope['cal_table'].reset_index().to_dict(orient='records'),
    'robustness': robustness,
    'unsupported_experiments': ['State, season and soil-type changes: not model inputs'],
    'provenance': 'Re-executed supplied notebook with the supplied CSV; no additional dataset.'}
(ROOT / 'reports/metrics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
for name, values in [('classwise', {c: report['classwise'][c]['f1-score'] for c in classes}),
                     ('model-comparison', {r['Model']: r['Macro-F1 mean'] for r in report['comparison']}),
                     ('robustness', {str(r['noise_std_fraction']): r['prediction_flip_rate'] for r in robustness if r['feature']=='all'})]:
    plt.figure(figsize=(10, 5)); plt.bar(values.keys(), values.values(), color='#28765b')
    plt.xticks(rotation=60, ha='right'); plt.title(name.replace('-', ' ').title()); plt.tight_layout()
    plt.savefig(ROOT / f'reports/plots/{name}.png', dpi=150); plt.close()
print('Model and reports exported successfully.', flush=True)
