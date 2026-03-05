# ingest_laws.py
import os
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

# ======== IMPORTANT: lock embedding model ========
EMBEDDING_MODEL = "text-embedding-3-small"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
VECTOR_DIR = BASE_DIR / "vectordb" / "laws_faiss"

LAW_FILES = [
    ("CASL", "CASL.pdf"),
    ("CCAS", "CCAS.pdf"),
    ("Competition Act", "Competition Act.pdf"),
    ("Cosmetic Regulations", "Cosmetic Regulations.pdf"),
    ("PIPEDA", "PIPEDA.pdf"),
]

def require_api_key():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set. Example: export OPENAI_API_KEY='your_key'")

def load_all_pdfs():
    all_docs = []
    for law_name, fname in LAW_FILES:
        pdf_path = DATA_DIR / fname
        if not pdf_path.exists():
            raise FileNotFoundError(f"Missing PDF: {pdf_path}")
        loader = PyPDFLoader(str(pdf_path))
        docs = loader.load()
        for d in docs:
            d.metadata = d.metadata or {}
            d.metadata["law"] = law_name
            d.metadata["source_file"] = fname
        all_docs.extend(docs)
    return all_docs

def main():
    require_api_key()

    print("Step 0/4: Cleaning old vector store...")
    if VECTOR_DIR.exists():
        # delete folder contents
        for p in VECTOR_DIR.rglob("*"):
            if p.is_file():
                p.unlink()
        for p in sorted([p for p in VECTOR_DIR.rglob("*") if p.is_dir()], reverse=True):
            p.rmdir()
        VECTOR_DIR.rmdir()

    print("Step 1/4: Loading legal PDFs...")
    docs = load_all_pdfs()
    print(f"Loaded {len(docs)} page-docs in total.")

    print("Step 2/4: Splitting documents into chunks...")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(docs)
    print(f"Created {len(chunks)} chunks.")

    print("Step 3/4: Creating embeddings (OpenAI)...")
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    print("Step 4/4: Building FAISS vector store and saving locally...")
    VECTOR_DIR.parent.mkdir(parents=True, exist_ok=True)
    vs = FAISS.from_documents(chunks, embeddings)
    vs.save_local(str(VECTOR_DIR))

    # sanity print: index dimension
    print("✅ Done!")
    print(f"Saved to: {VECTOR_DIR}")
    print(f"Embedding model locked to: {EMBEDDING_MODEL}")
    print(f"FAISS index dim (d): {vs.index.d}")

if __name__ == "__main__":
    main()