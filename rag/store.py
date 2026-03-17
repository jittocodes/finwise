"""
rag/store.py
------------
ChromaDB vector store helpers using open-source sentence-transformer embeddings.
"""
from __future__ import annotations
from typing import List, Optional
import chromadb
from chromadb.config import Settings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from loguru import logger
from config.settings import CHROMA_DIR, EMBEDDING_MODEL

_embedding_model: Optional[HuggingFaceEmbeddings] = None

def get_embeddings() -> HuggingFaceEmbeddings:
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _embedding_model = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embedding_model

_chroma_client: Optional[chromadb.PersistentClient] = None

def get_chroma_client(chroma_dir: Optional[str] = None) -> chromadb.PersistentClient:
    global _chroma_client
    path = chroma_dir or str(CHROMA_DIR)
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=path, settings=Settings(anonymized_telemetry=False)
        )
    return _chroma_client

def get_chroma_collection(collection_name: str, chroma_dir: Optional[str] = None):
    client = get_chroma_client(chroma_dir)
    return client.get_or_create_collection(
        name=collection_name, metadata={"hnsw:space": "cosine"}
    )

def upsert_documents(collection, documents: List[str], ids: List[str], metadatas=None):
    embeddings_fn = get_embeddings()
    embeddings = embeddings_fn.embed_documents(documents)
    collection.upsert(
        ids=ids, documents=documents, embeddings=embeddings,
        metadatas=metadatas or [{} for _ in documents],
    )

def get_langchain_vectorstore(collection_name: str) -> Chroma:
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
        client_settings=Settings(anonymized_telemetry=False),
    )

def add_texts_to_store(collection_name: str, texts: List[str], metadatas=None) -> Chroma:
    store = get_langchain_vectorstore(collection_name)
    store.add_texts(texts=texts, metadatas=metadatas or [{} for _ in texts])
    return store
