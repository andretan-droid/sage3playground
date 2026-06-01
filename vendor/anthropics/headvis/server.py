# Copyright 2026 Anthropic, PBC
# SPDX-License-Identifier: Apache-2.0
"""
Reference backend for headvis — implements the 6 endpoints the frontend calls.

The frontend works fully static (no backend) if data/server_config.json is {}
or missing. With a backend, you unlock live attribution compute, custom-prompt
ingestion, and UMAP point projection.

Every request body includes a `context` field forwarded verbatim from
data/server_config.json. The frontend never interprets it — you decide what
goes in it (model path, head-coordinate mapping, cache dir, whatever your
implementation needs).

Side-effect contract: endpoints that produce durable results should also write
them into the data/ tree so subsequent loads hit the static cache instead of
recomputing. The frontend always tries cache first.

    pip install fastapi uvicorn
    uvicorn server:app --host 0.0.0.0 --port 8080
"""

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="headvis backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)

DATA_DIR = Path("data")


# --- Request/response schemas ---------------------------------------------


class AttributionRequest(BaseModel):
    layer: int
    head: int
    seq_idx: str
    query_pos: int
    key_pos: int
    context: dict[str, Any] = {}


class FeaturePair(BaseModel):
    # query_feature / key_feature are opaque to the frontend — carry whatever
    # identifier your feature space uses
    query_feature: Any
    key_feature: Any
    attribution: float
    query_description: str
    key_description: str
    # snippets: [{"tokens": [str], "activations": [float], "interval": int}]
    query_snippets: list[dict[str, Any]] = []
    key_snippets: list[dict[str, Any]] = []


class AttributionResponse(BaseModel):
    pairs: list[FeaturePair]


class CustomSequenceRequest(BaseModel):
    layer: int
    head: int
    text: str
    context: dict[str, Any] = {}


class CustomSequence(BaseModel):
    sequence_id: str  # convention: "c" + short hash
    tokens: list[str]
    # Sparse COO attention: flat index = q * seq_len + k
    attention_indices: list[int]
    attention_values: list[float]
    seq_len: int
    max_activation: float


class DeleteSequenceRequest(BaseModel):
    layer: int
    head: int
    sequence_id: str
    context: dict[str, Any] = {}


class SaveClustersRequest(BaseModel):
    layer: int
    head: int
    clusters: list[dict[str, Any]]  # [{name: str, point_indices: [int]}]
    context: dict[str, Any] = {}


class ProjectRequest(BaseModel):
    layer: int
    head: int
    seq_idx: str
    query_pos: int
    key_pos: int
    context: dict[str, Any] = {}


# --- Endpoints ------------------------------------------------------------


@app.post("/api/head_vis/public/qk_attributions/v0")
def qk_attributions(req: AttributionRequest) -> AttributionResponse:
    """Decompose one attention edge into contributing (q_feature, k_feature) pairs.

    Requires a trained sparse dictionary (SAE / transcoder). For each pair,
    contribution to the pre-softmax score is the bilinear form:
        (q_act * q_decoder) @ W_Q.T @ W_K @ (k_decoder * k_act)
    where q_act/k_act are the feature activations at query_pos/key_pos.

    Side-effect: write the response JSON to
        data/attributions/qk/L{layer}H{head}S{seq_idx}Q{query_pos}K{key_pos}.json
    and add an entry to data/attributions/manifest.json so the frontend finds
    it in cache on the next load.
    """
    raise HTTPException(501, "QK attribution requires a sparse feature dictionary — not implemented")


@app.post("/api/head_vis/public/ov_attributions/v0")
def ov_attributions(req: AttributionRequest) -> AttributionResponse:
    """Decompose the OV circuit at (query_pos, key_pos) into feature pairs.

    Same machinery as QK but through W_V @ W_O instead of W_Q.T @ W_K.
    Same cache path pattern under data/attributions/ov/.
    """
    raise HTTPException(501, "OV attribution requires a sparse feature dictionary — not implemented")


@app.post("/api/head_vis/public/add_custom_sequence/v0")
def add_custom_sequence(req: CustomSequenceRequest) -> CustomSequence:
    """Tokenize raw text, run a forward pass, extract this head's attention.

    SAE-free — just needs your model + tokenizer.

    Side-effect: append the returned object to
        data/custom_sequences/L{layer}H{head}.json
    (shape: {"sequences": [...]}). Create the file if it doesn't exist.

    HuggingFace sketch:
        ids = tokenizer(req.text, return_tensors="pt").input_ids
        attn = model(ids, output_attentions=True).attentions[req.layer][0, req.head]
        vals, idx = attn.flatten().topk(min(500, attn.numel()))
        # return CustomSequence(...)
    """
    raise HTTPException(501, "Custom sequence ingestion not implemented — needs model + tokenizer")


@app.post("/api/head_vis/public/delete_custom_sequence/v0")
def delete_custom_sequence(req: DeleteSequenceRequest) -> dict[str, bool]:
    """Remove a sequence from data/custom_sequences/L{layer}H{head}.json.

    Pure file I/O — no model needed. Implementable out of the box.
    """
    raise HTTPException(501, "Not implemented")


@app.post("/api/head_vis/public/save_umap_clusters/v0")
def save_umap_clusters(req: SaveClustersRequest) -> dict[str, bool]:
    """Persist user-lassoed cluster labels into data/umap/L{layer}H{head}.json.

    Pure file I/O — merge req.clusters into the existing JSON's clusters key.
    """
    raise HTTPException(501, "Not implemented")


@app.post("/api/head_vis/public/project_to_umap/v0")
def project_to_umap(req: ProjectRequest) -> dict[str, Any]:
    """Place a new (seq, q_pos, k_pos) triple onto the existing PCA/UMAP cloud.

    Run a forward pass, extract the Q/K/O/V vectors at the positions, apply the
    saved PCA rotation. If UMAP is used, transform() via the fitted reducer.

    Three valid response shapes (the frontend branches on them):
        {"found_in_cloud": true, "existing_index": int}
        {"found_in_cloud": false, "found_in_projected": true, "projected_index": int}
        {"found_in_cloud": false, "found_in_projected": false,
         "point": {"seq_idx": str, "top_q": int, "top_k": int, "norm": float,
                   "pca": {"Q": [x,y,z], "K": [...], "O": [...], "V": [...]},
                   "umap_views": [...], "tokens": [str]}}
    """
    raise HTTPException(501, "UMAP projection not implemented — needs model + saved PCA rotation")
