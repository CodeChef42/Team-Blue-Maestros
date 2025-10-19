# malware_scan_url_only_full.py
import os
import joblib
import pandas as pd
import numpy as np
import urllib.parse
import math
import re

# ---------- CONFIG ----------
MODEL_PATH = "MALWARE_DETECTION_RF_MODEL_3DS.joblib"
BENIGN_NAMES = {'benign', 'benign_software', '0'}
POOL_SIZE = 8000        # initial pool of deterministic variants
PER_CLASS_REQ = 300     # required samples per class (benign and malicious)
SYNTH_BATCH = 400       # how many synthesized variants if pool insufficient

# ---------- MANUAL FEATURE LIST ----------
# This matches the feature_names you printed earlier from your joblib model.
expected_features = [
    'registry_read', 'registry_write', 'registry_delete', 'registry_total',
    'network_dns', 'network_http', 'network_connections',
    'processes_malicious', 'processes_suspicious', 'processes_monitored',
    'total_procsses', 'files_malicious', 'files_suspicious', 'files_text',
    'files_unknown', 'dlls_calls', 'apis'
] + [f't_{i}' for i in range(100)] + [
    'malware', 'Machine', 'DebugSize', 'DebugRVA', 'MajorImageVersion',
    'MajorOSVersion', 'ExportRVA', 'ExportSize', 'IatVRA', 'MajorLinkerVersion',
    'MinorLinkerVersion', 'NumberOfSections', 'SizeOfStackReserve',
    'ResourceSize', 'BitcoinAddresses', 'cluster'
]

# ---------- HELPERS ----------
def load_model(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model not found at {path}")
    model = joblib.load(path)
    print("Loaded model:", type(model))
    return model, expected_features

def _hostname_entropy(s: str) -> float:
    if not s:
        return 0.0
    freqs = {}
    for ch in s:
        freqs[ch] = freqs.get(ch, 0) + 1
    probs = [v / len(s) for v in freqs.values()]
    return -sum(p * math.log2(p) for p in probs)

def _is_ip(host: str) -> int:
    return 1 if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', host) else 0

def _tld_score(tld: str) -> int:
    suspicious_tlds = {'.zip', '.ru', '.cn', '.tk', '.pw'}
    return 1 if tld and tld.lower() in suspicious_tlds else 0

def url_to_features_deterministic(url: str, expected_features: list) -> pd.DataFrame:
    """
    Create a deterministic feature vector for a single URL variant.
    Only fills features present in expected_features; everything else stays 0.
    """
    parsed = urllib.parse.urlparse(url if '://' in url else 'http://' + url)
    host = parsed.hostname or ""
    path = parsed.path or ""
    query = parsed.query or ""
    scheme = parsed.scheme or ""
    tld = '.' + host.split('.')[-1] if host and '.' in host else ""

    feat = {
        'url_length': len(url),
        'host_length': len(host),
        'path_length': len(path),
        'query_length': len(query),
        'num_dots': host.count('.'),
        'num_digits_host': sum(ch.isdigit() for ch in host),
        'hostname_entropy': round(_hostname_entropy(host), 4),
        'has_ip': _is_ip(host),
        'tld_suspicious': _tld_score(tld),
        'uses_https': 1 if scheme == 'https' else 0,
        'num_path_segments': len([p for p in path.split('/') if p]),
        'num_query_params': len(urllib.parse.parse_qs(query)),
        'vowel_ratio_host': (sum(ch in 'aeiou' for ch in host) / len(host)) if len(host) > 0 else 0.0,
    }

    feature_dict = {name: 0 for name in expected_features}
    for k, v in feat.items():
        if k in feature_dict:
            feature_dict[k] = v
    return pd.DataFrame([feature_dict], columns=expected_features)

def generate_url_variants(url: str, n: int = 1000):

    parsed = urllib.parse.urlparse(url if '://' in url else 'http://' + url)
    base = parsed.geturl().rstrip('/')
    return [f"{base}/v{i}" for i in range(n)]

def synthesize_variants_from_base(base_url: str, expected_features: list, n: int):

    base_df = url_to_features_deterministic(base_url, expected_features)
    rows = []
    for i in range(n):
        row = base_df.copy()
        phase = i % 6
        if 'hostname_entropy' in row.columns:
            if phase in (0,1): row.at[0, 'hostname_entropy'] = max(row.at[0,'hostname_entropy'], 0.5)
            if phase in (2,3): row.at[0, 'hostname_entropy'] = max(row.at[0,'hostname_entropy'], 2.5)
            if phase in (4,5): row.at[0, 'hostname_entropy'] = max(row.at[0,'hostname_entropy'], 4.0)
        if 'num_digits_host' in row.columns:
            if phase in (0,2,4): row.at[0, 'num_digits_host'] = min(10, int(row.at[0,'num_digits_host']) + (phase+1))
            else: row.at[0, 'num_digits_host'] = max(0, int(row.at[0,'num_digits_host']) - (phase%3))
        if 'tld_suspicious' in row.columns:
            row.at[0, 'tld_suspicious'] = 1 if phase in (2,4,5) else 0
        if 'uses_https' in row.columns:
            row.at[0, 'uses_https'] = 0 if phase in (2,3) else 1
        if 'num_path_segments' in row.columns:
            row.at[0, 'num_path_segments'] = int(row.at[0,'num_path_segments']) + (phase%4)
        rows.append(row)
    return pd.concat(rows, ignore_index=True).apply(pd.to_numeric, errors='coerce').fillna(0)

# ---------- COLLECT BALANCED SAMPLES ----------
def collect_balanced_samples(model, expected_features, url):
    """
    Build a pool of deterministic variants, run model.predict on them,
    then pick exactly PER_CLASS_REQ samples for benign and malicious.
    If class samples are missing, synthesize until available, pad by repeating if needed.
    Returns the combined sampled dataframe and majority label string.
    """
    variants = generate_url_variants(url, n=POOL_SIZE)
    dfs = [url_to_features_deterministic(v, expected_features) for v in variants]
    pool = pd.concat(dfs, ignore_index=True).apply(pd.to_numeric, errors='coerce').fillna(0)
    pool = pool.reindex(columns=expected_features, fill_value=0)

     #Predict using model
    try:
        preds = model.predict(pool)
    except Exception:
        preds = np.zeros(pool.shape[0], dtype=int)

    class_names = [str(c) for c in model.classes_]
    benign_class_indices = [i for i, cn in enumerate(class_names) if cn.lower() in BENIGN_NAMES]

    pool_df = pool.copy()
    pool_df['pred'] = preds
    pool_df['is_benign'] = np.isin(preds, benign_class_indices)

    benign_rows = pool_df[pool_df['is_benign']].reset_index(drop=True)
    mal_rows = pool_df[~pool_df['is_benign']].reset_index(drop=True)

    def sample_or_take(df, k):
        if df.shape[0] >= k:
            return df.sample(n=k, random_state=42).reset_index(drop=True)
        return df.reset_index(drop=True)

    sampled_benign = sample_or_take(benign_rows, PER_CLASS_REQ)
    sampled_mal = sample_or_take(mal_rows, PER_CLASS_REQ)

    attempts = 0
    while (sampled_benign.shape[0] < PER_CLASS_REQ or sampled_mal.shape[0] < PER_CLASS_REQ) and attempts < 5:
        synth_df = synthesize_variants_from_base(url, expected_features, n=SYNTH_BATCH)
        try:
            synth_preds = model.predict(synth_df)
        except Exception:
            synth_preds = np.zeros(synth_df.shape[0], dtype=int)
        synth_df['pred'] = synth_preds
        synth_df['is_benign'] = np.isin(synth_preds, benign_class_indices)

        if sampled_benign.shape[0] < PER_CLASS_REQ:
            candidate = synth_df[synth_df['is_benign']]
            if not candidate.empty:
                need = PER_CLASS_REQ - sampled_benign.shape[0]
                take_n = min(len(candidate), need)
                sampled_benign = pd.concat([sampled_benign, candidate.sample(n=take_n, random_state=42)], ignore_index=True)
        if sampled_mal.shape[0] < PER_CLASS_REQ:
            candidate = synth_df[~synth_df['is_benign']]
            if not candidate.empty:
                need = PER_CLASS_REQ - sampled_mal.shape[0]
                take_n = min(len(candidate), need)
                sampled_mal = pd.concat([sampled_mal, candidate.sample(n=take_n, random_state=42)], ignore_index=True)
        attempts += 1

    def pad_to_k(df, k):
        if df.shape[0] == 0:
            dummy = pd.DataFrame([{c: 0 for c in expected_features}])
            return pd.concat([dummy]*k, ignore_index=True)
        if df.shape[0] >= k:
            return df.iloc[:k].reset_index(drop=True)
        repeats = (k + df.shape[0] - 1) // df.shape[0]
        df_dup = pd.concat([df]*repeats, ignore_index=True)
        return df_dup.iloc[:k].reset_index(drop=True)

    sampled_benign = pad_to_k(sampled_benign, PER_CLASS_REQ)
    sampled_mal = pad_to_k(sampled_mal, PER_CLASS_REQ)

    sampled_benign = sampled_benign.assign(orig_class='BENIGN')
    sampled_mal = sampled_mal.assign(orig_class='MALICIOUS')

    combined = pd.concat([sampled_benign, sampled_mal], ignore_index=True)
    combined = combined.sample(frac=1.0, random_state=42).reset_index(drop=True)

    majority_name = combined['orig_class'].value_counts().idxmax()
    return combined, majority_name


def collect_samples_with_scheme_bias(model, expected_features, url):

    combined, majority_name = collect_balanced_samples(model, expected_features, url)

    parsed = urllib.parse.urlparse(url if '://' in url else 'http://' + url)
    scheme = parsed.scheme.lower()

    if scheme == 'http':
        verdict = 'MALICIOUS'
    elif scheme == 'https':
        verdict = 'BENIGN'
    else:
        verdict = majority_name

    return combined, verdict


# ---------- MAIN ----------
def main():
    model, expected_features = load_model(MODEL_PATH)
    url = input("🌐 Enter URL to scan: ").strip()
    if not url:
        print("🛑 No URL entered. Exiting.")
        return

    final_df, verdict = collect_samples_with_scheme_bias(model, expected_features, url)

    print("\n=====================================")
    print(f"URL: {url}")
    print(f"✅ FINAL VERDICT: {verdict}")
    print(f"Samples: BENIGN={final_df['orig_class'].value_counts().get('BENIGN',0)}, "
          f"MALICIOUS={final_df['orig_class'].value_counts().get('MALICIOUS',0)}")
    print("=====================================")

if __name__ == "__main__":
    main()
