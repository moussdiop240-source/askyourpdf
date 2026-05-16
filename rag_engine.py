#!/usr/bin/env python3
"""
AskYourPDF v4.0 — RAG Processing Engine
Multi-document safe: each PDF gets its own folder inside chroma_db.
"""
import os
import shutil
import time
import requests
import json
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA, LLMChain
from langchain.prompts import PromptTemplate

load_dotenv()

# ---------- SETTINGS ----------
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50))
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./chroma_db")
PDF_FOLDER = os.getenv("PDF_FOLDER", "./data")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")
RETRIEVER_K = int(os.getenv("RETRIEVER_K", 4))
LLM_NUM_PREDICT = int(os.getenv("LLM_NUM_PREDICT", 1024))
DOC_REGISTRY = os.path.join(PDF_FOLDER, "documents.json")


def verify_ollama():
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            if OLLAMA_MODEL in models:
                print(f"✅ Ollama running with model: {OLLAMA_MODEL}")
                return True
            print(f"⚠️  Model '{OLLAMA_MODEL}' not found")
            return False
    except Exception as e:
        print(f"❌ Cannot reach Ollama: {e}")
    return False


def _load_registry():
    if not os.path.exists(DOC_REGISTRY):
        return {}
    with open(DOC_REGISTRY, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_registry(reg):
    with open(DOC_REGISTRY, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)


def process_pdf(pdf_filename, doc_id=None):
    if doc_id is None:
        doc_id = os.path.splitext(pdf_filename)[0]
    pdf_path = os.path.join(PDF_FOLDER, pdf_filename)

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    print(f"📄 Loading: {pdf_filename}")
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    if not documents:
        raise ValueError("PDF has no text.")

    print(f"   Loaded {len(documents)} pages")

    print("✂️  Splitting...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    chunks = text_splitter.split_documents(documents)
    if not chunks:
        raise ValueError("Could not create any text chunks.")
    print(f"   Created {len(chunks)} chunks")

    store_path = os.path.join(VECTOR_DB_PATH, doc_id)
    # Retry up to 3 times if locked (extremely rare now)
    for attempt in range(3):
        if os.path.exists(store_path):
            try:
                shutil.rmtree(store_path)
                break
            except PermissionError:
                time.sleep(1)
        else:
            break

    print("🧠 Creating embeddings...")
    embeddings = OllamaEmbeddings(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=store_path,
    )
    vectorstore.persist()
    print(f"   Database saved to {store_path}")

    reg = _load_registry()
    reg[doc_id] = {
        "filename": pdf_filename,
        "page_count": len(documents),
        "chunk_count": len(chunks),
    }
    _save_registry(reg)

    return vectorstore, doc_id


def load_existing_db(doc_id):
    store_path = os.path.join(VECTOR_DB_PATH, doc_id)
    if not os.path.exists(store_path) or not os.listdir(store_path):
        return None

    print(f"📂 Loading database for '{doc_id}'...")
    embeddings = OllamaEmbeddings(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)
    vectorstore = Chroma(
        persist_directory=store_path,
        embedding_function=embeddings,
    )
    count = vectorstore._collection.count()
    print(f"   Loaded {count} chunks")
    return vectorstore


def list_documents():
    reg = _load_registry()
    docs = []
    for doc_id, info in reg.items():
        docs.append({
            "id": doc_id,
            "filename": info.get("filename"),
            "pages": info.get("page_count"),
            "chunks": info.get("chunk_count"),
        })
    return docs


def delete_document(doc_id):
    store_path = os.path.join(VECTOR_DB_PATH, doc_id)
    if os.path.exists(store_path):
        # Retry removal in case of temporary lock
        for attempt in range(3):
            try:
                shutil.rmtree(store_path)
                break
            except PermissionError:
                time.sleep(1)
    reg = _load_registry()
    if doc_id in reg:
        del reg[doc_id]
        _save_registry(reg)
        return True
    return False


def get_qa_chain(vectorstore):
    retriever = vectorstore.as_retriever(search_kwargs={"k": RETRIEVER_K})
    custom_prompt = PromptTemplate(
        template="""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a document assistant. Answer ONLY using the context provided. 
If the answer is not in the context, say "I cannot find this in the document."
Never make up information.<|eot_id|><|start_header_id|>user<|end_header_id|>
Document context:
{context}

Question: {question}

Answer using ONLY the context:<|eot_id|><|start_header_id|>assistant<|end_header_id|>""",
        input_variables=["context", "question"]
    )
    llm = ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0,
        num_predict=LLM_NUM_PREDICT,
    )
    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": custom_prompt},
    )
    return chain


def ask_question(qa_chain, question):
    question = question.strip()
    if not question:
        return {"answer": "Please ask a question.", "source_pages": []}

    result = qa_chain.invoke({"query": question})
    answer = result.get("result", "No answer generated.")
    source_docs = result.get("source_documents", [])

    pages = set()
    for doc in source_docs:
        page = doc.metadata.get("page")
        if page is not None:
            pages.add(page + 1)

    return {
        "answer": answer.strip(),
        "source_pages": sorted(list(pages)),
    }


def summarize_document(vectorstore):
    results = vectorstore._collection.get(include=['documents', 'metadatas'])
    if not results['documents']:
        return "No document chunks found."

    page_texts = []
    for doc_text, metadata in zip(results['documents'], results['metadatas']):
        page = metadata.get('page', 0)
        page_texts.append((page, doc_text))
    page_texts.sort(key=lambda x: x[0])

    full_text = "\n\n".join(text for _, text in page_texts)
    max_chars = 8000
    if len(full_text) > max_chars:
        full_text = full_text[:max_chars] + "\n... [truncated for length]"

    llm = ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0,
        num_predict=LLM_NUM_PREDICT,
    )
    prompt = PromptTemplate(
        input_variables=["text"],
        template="""Write a concise summary of the following document text. Include only key points, main topics, and important details.

TEXT:
{text}

SUMMARY:"""
    )
    chain = LLMChain(llm=llm, prompt=prompt)
    summary = chain.run(full_text)
    return summary.strip()