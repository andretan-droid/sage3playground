# Copyright 2026 Anthropic, PBC
# SPDX-License-Identifier: Apache-2.0
"""
Offline data pipeline skeleton — populates the data/ directory the frontend reads.

Run this once (or periodically) against your model and dataset. The frontend is
fully static once data/ exists; the backend (server.py) only handles runtime
operations like live attribution compute.

Nothing here is model- or framework-specific. Each function's docstring is the
data-format contract — produce JSON matching that shape and the frontend works.
The function bodies show the compute flow but contain no real implementation.

    python data_pipeline.py --output-dir ./data

Gotchas:

  - Position 0: the frontend's max-reductions unconditionally skip row 0 and
    column 0 of the attention matrix. Compute max_activation the same way or
    your decile bucketing won't match what the frontend displays.

  - File size: target ~5–15 MB per head JSON. With ~200 sequences per head and
    seq_len ~512, top-8 per row with a ~0.005 threshold lands there. Dense
    attention blows up fast.

  - JSON float precision: json.dumps writes full binary precision. Round to ~4
    decimals before serializing. If rounding numpy arrays, cast to float64 first
    — float32-rounded values don't land on short decimals (0.1235f32 serializes
    as 0.123499996…).
"""

import argparse
import json
from pathlib import Path
from typing import Any


# --- Configuration --------------------------------------------------------

# Which (layer, head) pairs to expose. The frontend presents these as a flat
# list — these are the coordinates the frontend displays.
HEADS_TO_STUDY: list[tuple[int, int]] = [
    # (layer, head)
]

# How many sequences to walk from your dataset. More sequences → better decile
# estimates and a wider pool to sample from.
N_SEQUENCES = 20_000

# Activation deciles. interval=10 is the highest-activation bucket, interval=1
# the lowest. The frontend's sequences-tab dropdown shows these.
N_INTERVALS = 10
SAMPLES_PER_INTERVAL = 20


# --- Per-head metrics (data/scatter_data.json) ----------------------------


def compute_head_metrics(layer: int, head: int, attention_samples: Any) -> dict[str, float]:
    """Scalar metrics placing one head on the scatter plot.

    `attention_samples` is whatever your model produces — a stack of attention
    matrices over many sequences. Each metric is a closed-form reduction over
    that stack. The frontend treats these purely as scatter-plot axes; you can
    define any subset.

    Output:
        {
            "self_attention_score": float,   # mean of the diagonal — 1.0 = always self-attends
            "previous_token_score": float,   # mean of the first subdiagonal
            "pattern_entropy": float,        # mean per-query Shannon entropy; high = dispersed
            "qk_distance": float,            # mean |q - k| weighted by attention mass
            "qk_distance_variance": float,   # variance of the same
            "induction_score": float,        # for each q, find {j: token[j]==token[q]},
                                             #   sum A[q, j+1]; average over positions
            "logit_std": float,              # std of pre-softmax scores per query (needs QK logits, not just softmax)
            "top_logit_margin": float,       # top-1 − top-2 pre-softmax gap
            "logit_z_score": float,          # (max − mean) / std of pre-softmax scores
            "query_token_entropy": float,    # entropy over token IDs at high-attention query positions
            "key_token_entropy": float,      # same for key positions
        }

    The three logit_* metrics need pre-softmax QK scores, not the final
    attention weights — hook your attention module or recompute Q @ K.T.
    """
    raise NotImplementedError


def write_scatter_data(output_dir: Path, metrics_by_head: dict[tuple[int, int], dict[str, float]]) -> None:
    """data/scatter_data.json — one flat row per head.

        [
            {"layer": 0, "head": 0, "induction_score": 0.42, "self_attention_score": 0.01, ...},
            {"layer": 0, "head": 1, ...},
        ]
    """
    rows = [{"layer": l, "head": h, **m} for (l, h), m in metrics_by_head.items()]
    (output_dir / "scatter_data.json").write_text(json.dumps(rows))


# --- Per-head sequences (data/heads/L{l}H{h}.json) ------------------------


def sample_by_decile(layer: int, head: int, sequences: Any) -> list[dict[str, Any]]:
    """Representative sequences at each activation level.

    For each sequence compute max(attention) for this head (ignoring the
    diagonal and position 0). Sort, partition into N_INTERVALS equal buckets,
    reservoir-sample SAMPLES_PER_INTERVAL from each. interval=10 is the
    highest-activation bucket.

    Each sampled sequence:
        {
            "sequence_id": int,             # any stable identifier
            "interval": int,                # 1..N_INTERVALS, 10 = highest
            "tokens": [str],                # display strings (post-tokenizer-decode)
            "attention_indices": [int],     # COO sparse: flat index = q * seq_len + k
            "attention_values": [float],    # same length as attention_indices
            "seq_len": int,
            "max_activation": float,
        }

    Attention is stored sparse — top-K per row, or above a threshold. Dense
    256×256 matrices would make head JSONs tens of MB each.
    """
    raise NotImplementedError


def compute_qk_distance_histogram(sequences: list[dict[str, Any]]) -> dict[str, Any]:
    """Histogram of |q − k| over the top attention pairs in sampled sequences.

        {"bin_edges": [0, 1, 2, 4, 8, 16, ...], "bin_values": [int, ...]}

    The edges are typically log-spaced. bin_values has len(bin_edges)-1 entries.
    This powers the distance-histogram panel in the metrics tab.
    """
    raise NotImplementedError


def compute_top_tokens(sequences: list[dict[str, Any]], side: str) -> list[dict[str, Any]]:
    """Rank tokens by marginal attention mass on the query or key side.

    Sum attention over all sampled sequences grouped by token string, rank.

        [{"token": "the", "weight": 0.34}, ...]
    """
    raise NotImplementedError


def write_head_json(output_dir: Path, layer: int, head: int, sequences: list[dict[str, Any]]) -> None:
    """data/heads/L{layer}H{head}.json — the main per-head payload."""
    payload = {
        "sequences": sequences,
        "qk_distance_histogram": compute_qk_distance_histogram(sequences),
        "top_query_tokens": compute_top_tokens(sequences, side="query"),
        "top_key_tokens": compute_top_tokens(sequences, side="key"),
        "histogram": {},    # optional: activation distribution across all sequences — {"bin_edges": [...], "bin_values": [...]}
        "statistics": {},   # optional: free-form summary stats for the metrics tab
    }
    (output_dir / "heads" / f"L{layer}H{head}.json").write_text(json.dumps(payload))


# --- UMAP/PCA cloud (data/umap/L{l}H{h}.json) -----------------------------


def compute_projection_cloud(layer: int, head: int, sequences: Any, n_points: int = 5000) -> dict[str, Any]:
    """3D PCA + UMAP over Q/K/O/V vectors at high-attention positions.

    Find ~n_points (sequence, q_pos, k_pos) triples where this head attends
    strongly. Extract the Q vector at q_pos, K at k_pos, O at q_pos, V at
    k_pos. Fit PCA(n_components=3) on each stack separately. Optionally also
    fit umap.UMAP — the frontend supports both and lets the user toggle.

        {
            "seq_idx": [int] * n_points,      # index back into your dataset
            "top_q": [int] * n_points,        # q position per point
            "top_k": [int] * n_points,        # k position per point
            "norms": [float] * n_points,      # ||Q|| or similar — colors the scatter
            "pca": {
                "Q": {"d0": [float]*n, "d1": [...], "d2": [...]},
                "K": {...}, "O": {...}, "V": {...},
            },
            "views": [                        # omit this key entirely if PCA-only
                {"n_neighbors": 15, "min_dist": 0.1,
                 "embeddings": {"Q": {"d0":[...], "d1":[...], "d2":[...]}, ...}},
            ],
            "clusters": [],                   # populated by the user via save_umap_clusters
        }

    Save the fitted PCA rotation somewhere the backend can load it — the
    project_to_umap endpoint applies it to new points.
    """
    raise NotImplementedError


def write_umap_sequences(output_dir: Path, token_lookup: dict[int, list[str]]) -> None:
    """data/umap/sequences.json — shared token lookup for hover text.

    Maps sequence index → token list. All heads share this one file since
    the underlying sequences are the same.

        {"0": ["The", " cat", " sat"], "1": [...], ...}
    """
    (output_dir / "umap" / "sequences.json").write_text(json.dumps(token_lookup))


# --- Config (data/config.json) --------------------------------------------


def write_config(output_dir: Path, model_name: str, metric_names: list[str]) -> None:
    """data/config.json — the frontend reads this first.

        {
            "model_name": str,
            "heads": [[layer, head], ...],         # which heads exist
            "n_layers": int,                       # for display only
            "n_heads": int,                        # per layer, display only
            "n_intervals": int,                    # matches N_INTERVALS
            "metrics": [str],                      # scatter-axis metric names
            "metric_descriptions": {str: str},     # shown as axis-label tooltips
            "head_data_pattern": "L{layer}H{head}.json",
            "has_umap": bool,
            "umap_heads": [[layer, head], ...],    # subset with UMAP data
            "custom_plots": [                      # optional: extra plots in the metrics tab
                {"key": "qk_distance_histogram", "label": "Q-K distance"},
            ],
            "custom_tables": [                     # optional: extra tables in the metrics tab
                {"key": "top_query_tokens", "label": "Top query tokens"},
            ],
            "statistics_display": {                # optional: labels/formats for the "statistics" dict in head JSONs
                "mean_max_activation": {"label": "Mean max activation", "format": "default"},
            },
        }

    custom_plots/custom_tables entries reference fields in the head JSON by key.
    Plots need {bin_edges, bin_values} shape; tables need [{token, weight}].
    """
    raise NotImplementedError


# --- Driver ---------------------------------------------------------------


def main(output_dir: Path) -> None:
    (output_dir / "heads").mkdir(parents=True, exist_ok=True)
    (output_dir / "umap").mkdir(exist_ok=True)
    (output_dir / "attributions" / "qk").mkdir(parents=True, exist_ok=True)
    (output_dir / "attributions" / "ov").mkdir(exist_ok=True)
    (output_dir / "custom_sequences").mkdir(exist_ok=True)

    # Stage 1: stream the dataset once. For each head accumulate metric running
    # stats, stash high-attention sequences for decile sampling, and stash
    # (seq, q_pos, k_pos) triples with their Q/K/O/V vectors for the projection.
    # Single-pass if you keep per-head state small; two passes if memory is tight.

    metrics_by_head: dict[tuple[int, int], dict[str, float]] = {}
    for layer, head in HEADS_TO_STUDY:
        attention_samples = ...
        metrics_by_head[(layer, head)] = compute_head_metrics(layer, head, attention_samples)

        sequences = sample_by_decile(layer, head, ...)
        write_head_json(output_dir, layer, head, sequences)

        cloud = compute_projection_cloud(layer, head, ...)
        (output_dir / "umap" / f"L{layer}H{head}.json").write_text(json.dumps(cloud))

    write_scatter_data(output_dir, metrics_by_head)
    token_lookup: dict[int, list[str]] = {}  # seq_idx -> tokens, populated in stage 1
    write_umap_sequences(output_dir, token_lookup)
    write_config(output_dir, model_name="your-model", metric_names=list(next(iter(metrics_by_head.values())).keys()))

    # Bootstrap empty backend config — the frontend runs static-only with this.
    (output_dir / "server_config.json").write_text("{}")
    (output_dir / "attributions" / "manifest.json").write_text("{}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", type=Path, default=Path("data"))
    args = p.parse_args()
    main(args.output_dir)
