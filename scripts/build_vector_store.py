#!/usr/bin/env python3
"""
Build FAISS vector stores for entities and template intents.

Usage:
    python scripts/build_vector_store.py

Environment variables:
    RETRIEVAL_EMBEDDING_MODEL - override embedding model
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm.auto import tqdm


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARTIFACT_DIR = ROOT / "artifacts" / "vector_store"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

ENTITIES_JSON = DATA_DIR / "entities.json"
TEMPLATES_JSON = DATA_DIR / "template_intents.json"

ENTITY_INDEX_PATH = ARTIFACT_DIR / "entities.index"
ENTITY_METADATA_PATH = ARTIFACT_DIR / "entities_metadata.json"

TEMPLATE_INDEX_PATH = ARTIFACT_DIR / "templates.index"
TEMPLATE_METADATA_PATH = ARTIFACT_DIR / "templates_metadata.json"

MANIFEST_PATH = ARTIFACT_DIR / "manifest.json"

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Required file missing: {path}")
    return json.loads(path.read_text())


def normalize_embeddings(vectors: np.ndarray) -> np.ndarray:
    vectors = vectors.astype("float32")
    faiss.normalize_L2(vectors)
    return vectors


def build_index(vectors: np.ndarray, index_path: Path) -> None:
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    faiss.write_index(index, str(index_path))


def encode_texts(model: SentenceTransformer, texts: List[str]) -> np.ndarray:
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=False,
    )
    return normalize_embeddings(embeddings)


def build_entity_records(data: List[Dict[str, Any]]) -> tuple[List[str], List[Dict[str, Any]]]:
    texts: List[str] = []
    metadata: List[Dict[str, Any]] = []
    for entry in data:
        base = {
            "id": entry["id"],
            "slot": entry["slot"],
            "canonical": entry["canonical"],
        }
        surfaces = [entry["canonical"]] + entry.get("synonyms", [])
        for surface in surfaces:
            surface_text = surface.strip()
            if not surface_text:
                continue
            texts.append(surface_text)
            metadata.append({**base, "surface": surface_text})
    return texts, metadata


def build_template_records(data: List[Dict[str, Any]]) -> tuple[List[str], List[Dict[str, Any]]]:
    texts: List[str] = []
    metadata: List[Dict[str, Any]] = []
    for entry in data:
        template_id = entry["template_id"]
        intent_text = entry.get("intent_text", "").strip()
        pattern = entry.get("pattern", "").strip()
        examples = entry.get("example_questions") or []

        candidates = [intent_text, pattern] + examples
        for text in candidates:
            cleaned = (text or "").strip()
            if not cleaned:
                continue
            texts.append(cleaned)
            metadata.append(
                {
                    "template_id": template_id,
                    "text": cleaned,
                    "metadata": entry.get("metadata", {}),
                }
            )
    return texts, metadata


def write_metadata(path: Path, data: List[Dict[str, Any]]) -> None:
    path.write_text(json.dumps(data, indent=2))


def write_manifest(model_name: str, entity_count: int, template_count: int) -> None:
    manifest = {
        "model": model_name,
        "entity_vectors": entity_count,
        "template_vectors": template_count,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))


def main() -> None:
    model_name = os.getenv("RETRIEVAL_EMBEDDING_MODEL", DEFAULT_MODEL)
    print(f"Loading embedding model: {model_name}")
    model = SentenceTransformer(model_name)

    entity_data = load_json(ENTITIES_JSON)
    template_data = load_json(TEMPLATES_JSON)

    entity_texts, entity_metadata = build_entity_records(entity_data)
    template_texts, template_metadata = build_template_records(template_data)

    print(f"Encoding {len(entity_texts)} entity phrases...")
    entity_vectors = encode_texts(model, entity_texts)
    print(f"Encoding {len(template_texts)} template phrases...")
    template_vectors = encode_texts(model, template_texts)

    print("Writing FAISS indexes...")
    build_index(entity_vectors, ENTITY_INDEX_PATH)
    build_index(template_vectors, TEMPLATE_INDEX_PATH)

    print("Writing metadata...")
    write_metadata(ENTITY_METADATA_PATH, entity_metadata)
    write_metadata(TEMPLATE_METADATA_PATH, template_metadata)
    write_manifest(model_name, len(entity_texts), len(template_texts))

    print("Vector store build complete.")


if __name__ == "__main__":
    main()
