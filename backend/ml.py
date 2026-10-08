"""Local model adapters. No transaction data is sent to Hugging Face."""
import os
from functools import lru_cache
import numpy as np
from sklearn.ensemble import IsolationForest

CATEGORIES = ['Income', 'Housing', 'Groceries', 'Utilities', 'Transport', 'Health',
              'Shopping', 'Dining', 'Entertainment', 'Transfer', 'Other']
ESSENTIAL = {'Housing', 'Groceries', 'Utilities', 'Transport', 'Health'}
RULES = {
    'Income': ['salary', 'payroll', 'wages'],
    'Housing': ['rent', 'mortgage'], 'Groceries': ['grocery', 'groceries', 'supermarket'],
    'Utilities': ['electricity', 'broadband', 'utility', 'water bill'],
    'Transport': ['uber', 'taxi', 'petrol', 'metro', 'fuel'],
    'Health': ['hospital', 'pharmacy', 'medical'],
    'Shopping': ['amazon', 'shopping', 'flipkart', 'electronics'],
    'Dining': ['restaurant', 'swiggy', 'zomato', 'cafe'],
    'Entertainment': ['netflix', 'spotify', 'cinema'],
    'Transfer': ['own account', 'self transfer', 'credit card payment'],
}

@lru_cache(maxsize=1)
def embeddings():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2',
        device='cpu', local_files_only=os.getenv('HF_LOCAL_ONLY') == '1')

@lru_cache(maxsize=1)
def forecaster():
    from chronos import BaseChronosPipeline
    return BaseChronosPipeline.from_pretrained('amazon/chronos-bolt-tiny', device_map='cpu',
        local_files_only=os.getenv('HF_LOCAL_ONLY') == '1')

def categorize(rows):
    method = 'Keyword suggestions; review all categories'
    unresolved = []
    for i, row in enumerate(rows):
        label = next((c for c, words in RULES.items()
                      if any(w in row['description'].lower() for w in words)), 'Other')
        row['category'] = label
        row['essential'] = label in ESSENTIAL
        if label == 'Other':
            unresolved.append(i)
    if unresolved and os.getenv('ENABLE_HF') == '1':
        try:
            model = embeddings()
            labels = [c for c in CATEGORIES if c not in ('Income', 'Transfer', 'Other')]
            text = [rows[i]['description'] for i in unresolved]
            a = model.encode(text, normalize_embeddings=True)
            b = model.encode(['A bank payment for '+c for c in labels], normalize_embeddings=True)
            scores = a @ b.T
            for i, s in zip(unresolved, scores):
                if float(s.max()) >= .35:
                    label = labels[int(s.argmax())]
                    rows[i].update(category=label, essential=label in ESSENTIAL)
            method = 'Hugging Face MiniLM similarity + keywords; review suggestions'
        except Exception:
            method = 'Keyword fallback: MiniLM unavailable'
    return method

def forecast(months):
    income = np.array([m['income'] for m in months[-12:]], dtype=float)
    expense = np.array([m['expense'] for m in months[-12:]], dtype=float)
    if not len(income):
        return dict(income=0, expense=0, conservative_income=0,
                    method='Waiting for a complete statement month', warning='No complete historical month available.')
    base = dict(income=round(float(np.median(income)), 2),
                expense=round(float(np.median(expense)), 2),
                conservative_income=round(float(np.quantile(income, .25)), 2),
                method='Historical monthly median', warning='Estimates assume similar future income; no guaranteed outcome.')
    if len(income) < 3:
        base['warning'] = 'Limited history: provide at least 3 complete months. Planning is provisional.'
    elif os.getenv('ENABLE_HF') == '1':
        try:
            import torch
            pipeline = forecaster()
            quantiles, mean = pipeline.predict_quantiles(
                torch.tensor(np.stack([income, expense]), dtype=torch.float32),
                prediction_length=1, quantile_levels=[.1, .5, .9])
            q = quantiles.detach().cpu().numpy()
            base.update(income=round(max(0., float(q[0, 0, 1])), 2),
                        expense=round(max(0., float(q[1, 0, 1])), 2),
                        conservative_income=round(max(0., min(float(q[0, 0, 0]), float(np.quantile(income, .25)))), 2),
                        method='Hugging Face · amazon/chronos-bolt-tiny',
                        warning='Experimental forecast; quantiles are not a calibrated goal-success probability.')
        except Exception:
            base['warning'] = 'Chronos unavailable: using historical monthly median. Install ML requirements and download models.'
    return base

def anomalies(rows):
    """Within-user, descriptive outlier flags, not fraud probabilities."""
    result = []
    for direction in (-1, 1):
        group = [r for r in rows if r['category'] != 'Transfer' and r['amount_cents']*direction > 0]
        if len(group) < 20:
            continue
        x = np.array([[np.log1p(abs(r['amount_cents']) / 100)] for r in group])
        model = IsolationForest(n_estimators=100, contamination='auto', random_state=42)
        labels = model.fit_predict(x)
        scores = -model.score_samples(x)
        median = float(np.median([abs(r['amount_cents']) for r in group]))
        regular = {}
        for r in group:
            regular.setdefault(r['description'].strip().lower(), []).append(r)
        for r, flag, score in zip(group, labels, scores):
            peers = regular[r['description'].strip().lower()]
            typical = float(np.median([abs(p['amount_cents']) for p in peers]))
            # A stable recurring salary/rent is large but not unusual for this description.
            stable_recurring = (len({p['date'][:7] for p in peers}) >= 3
                                and abs(abs(r['amount_cents']) - typical) <= .25 * typical)
            if stable_recurring:
                continue
            if flag == -1 and abs(r['amount_cents']) > max(3*median, 10000):
                result.append({**r, 'score':round(float(score), 3),
                    'reason': 'Unusually large '+('outflow' if direction < 0 else 'inflow')+' compared with your history; review it.'})
    return sorted(result, key=lambda r:r['score'], reverse=True)[:10]
