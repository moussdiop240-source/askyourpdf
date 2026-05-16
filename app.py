#!/usr/bin/env python3
"""
AskYourPDF v4.0 — Main Web Application
Multi-document management: list, load, delete, summarize, print.
"""
import os
import uuid
import logging
import traceback
from datetime import datetime
from pathlib import Path
from io import BytesIO

from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv

# reportlab for print-summary (import once, not inside route)
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

load_dotenv()

from rag_engine import (
    verify_ollama,
    process_pdf,
    load_existing_db,
    get_qa_chain,
    ask_question,
    summarize_document,
    list_documents,
    delete_document,
    _load_registry,
    OLLAMA_MODEL,
)
from translation_engine import (
    translate_text,
    detect_language,
    get_supported_languages,
    get_language_name,
    get_language_flag,
    SUPPORTED_LANGUAGES,
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 64 * 1024 * 1024))
app.config["UPLOAD_FOLDER"] = "data"

for folder in ["data", "logs", "chroma_db"]:
    Path(folder).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

app.config["VECTORSTORE"] = None
app.config["QA_CHAIN"] = None
app.config["CURRENT_DOC_ID"] = None
app.config["CURRENT_PDF"] = None
app.config["OLLAMA_READY"] = False
app.config["USER_LANGUAGE"] = "en"
app.config["START_TIME"] = datetime.now().isoformat()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy" if app.config["OLLAMA_READY"] else "degraded",
        "version": "4.0.0",
        "ollama": app.config["OLLAMA_READY"],
        "pdf_loaded": app.config["CURRENT_PDF"] is not None,
        "languages": len(SUPPORTED_LANGUAGES),
    })


@app.route("/upload", methods=["POST"])
def upload():
    if not app.config["OLLAMA_READY"]:
        return jsonify({"error": "Ollama is not running. Please start Ollama first."}), 503

    if "pdf_file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    file = request.files["pdf_file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are accepted."}), 400

    safe_name = f"uploaded_{uuid.uuid4().hex[:8]}.pdf"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)

    try:
        file.save(filepath)
        logger.info(f"File saved: {filepath}")

        doc_id = os.path.splitext(safe_name)[0]

        start_time = datetime.now()
        vectorstore, doc_id = process_pdf(safe_name, doc_id=doc_id)
        processing_time = (datetime.now() - start_time).total_seconds()

        qa_chain = get_qa_chain(vectorstore)

        app.config["VECTORSTORE"] = vectorstore
        app.config["QA_CHAIN"] = qa_chain
        app.config["CURRENT_DOC_ID"] = doc_id
        app.config["CURRENT_PDF"] = file.filename

        return jsonify({
            "success": True,
            "message": f"PDF processed in {processing_time:.1f} seconds!",
            "filename": file.filename,
            "doc_id": doc_id,
            "processing_time": round(processing_time, 1),
        })

    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Upload error: {traceback.format_exc()}")
        return jsonify({"error": "Failed to process PDF."}), 500


@app.route("/documents", methods=["GET"])
def documents_list():
    try:
        docs = list_documents()
        return jsonify({"documents": docs, "current": app.config.get("CURRENT_DOC_ID")})
    except Exception as e:
        logger.error(f"List error: {e}")
        return jsonify({"error": "Failed to list documents."}), 500


@app.route("/load", methods=["POST"])
def load():
    if not app.config["OLLAMA_READY"]:
        return jsonify({"error": "Ollama is not running."}), 503

    data = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id")

    if not doc_id:
        return jsonify({"error": "No document ID provided."}), 400

    try:
        vectorstore = load_existing_db(doc_id)
        if vectorstore is None:
            return jsonify({"error": f"Document '{doc_id}' not found."}), 404

        qa_chain = get_qa_chain(vectorstore)
        app.config["VECTORSTORE"] = vectorstore
        app.config["QA_CHAIN"] = qa_chain
        app.config["CURRENT_DOC_ID"] = doc_id

        reg = _load_registry()
        filename = reg.get(doc_id, {}).get("filename", "Unknown")
        app.config["CURRENT_PDF"] = filename
        logger.info(f"Loaded document '{filename}' (id: {doc_id})")
        return jsonify({"success": True, "message": f"Loaded '{filename}'", "doc_id": doc_id})
    except Exception as e:
        logger.error(f"Load error: {e}")
        return jsonify({"error": "Failed to load document."}), 500


@app.route("/delete", methods=["POST"])
def delete():
    data = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id")
    if not doc_id:
        return jsonify({"error": "No document ID provided."}), 400

    try:
        success = delete_document(doc_id)
        if not success:
            return jsonify({"error": "Document not found."}), 404

        if app.config.get("CURRENT_DOC_ID") == doc_id:
            app.config["VECTORSTORE"] = None
            app.config["QA_CHAIN"] = None
            app.config["CURRENT_DOC_ID"] = None
            app.config["CURRENT_PDF"] = None
        return jsonify({"success": True, "message": "Document deleted."})
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return jsonify({"error": "Failed to delete document."}), 500


@app.route("/ask", methods=["POST"])
def ask():
    qa_chain = app.config.get("QA_CHAIN")
    if qa_chain is None:
        return jsonify({"error": "Please upload or load a PDF first."}), 400

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request."}), 400

    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Please enter a question."}), 400
    if len(question) > 2000:
        return jsonify({"error": "Question too long."}), 400

    try:
        result = ask_question(qa_chain, question)
        return jsonify({
            "answer": result["answer"],
            "source_pages": result["source_pages"],
            "model": OLLAMA_MODEL,
        })
    except Exception as e:
        logger.error(f"Ask error: {e}")
        return jsonify({"error": "Failed to get answer."}), 500


@app.route("/summarize", methods=["POST"])
def summarize():
    vectorstore = app.config.get("VECTORSTORE")
    if vectorstore is None:
        return jsonify({"error": "No document loaded."}), 400

    try:
        summary = summarize_document(vectorstore)
        return jsonify({"summary": summary})
    except Exception as e:
        logger.error(f"Summarize error: {e}")
        return jsonify({"error": "Failed to generate summary."}), 500


@app.route("/print-summary", methods=["POST"])
def print_summary():
    vectorstore = app.config.get("VECTORSTORE")
    if vectorstore is None:
        return jsonify({"error": "No document loaded."}), 400

    try:
        summary = summarize_document(vectorstore)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=18)
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph("Document Summary", styles['Heading1']))
        story.append(Spacer(1, 12))
        for para in summary.split('\n\n'):
            story.append(Paragraph(para.strip(), styles['Normal']))
            story.append(Spacer(1, 6))
        doc.build(story)
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name="summary.pdf",
            mimetype="application/pdf"
        )
    except Exception as e:
        logger.error(f"Print summary error: {e}")
        return jsonify({"error": "Failed to generate print."}), 500


# Translation routes (unchanged)
@app.route("/languages", methods=["GET"])
def languages():
    return jsonify({
        "languages": get_supported_languages(),
        "current": app.config["USER_LANGUAGE"],
    })


@app.route("/language", methods=["POST"])
def set_language():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request"}), 400
    lang_code = data.get("language", "en")
    if lang_code not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"Language '{lang_code}' not supported"}), 400
    app.config["USER_LANGUAGE"] = lang_code
    return jsonify({
        "success": True,
        "language": lang_code,
        "language_name": get_language_name(lang_code),
        "flag": get_language_flag(lang_code),
    })


@app.route("/detect", methods=["POST"])
def detect():
    data = request.get_json(silent=True)
    if not data or "text" not in data:
        return jsonify({"error": "No text provided"}), 400
    detected = detect_language(data["text"])
    return jsonify({
        "detected": detected,
        "language_name": get_language_name(detected),
        "flag": get_language_flag(detected),
    })


@app.route("/translate", methods=["POST"])
def translate():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request"}), 400
    text = data.get("text", "").strip()
    target = data.get("target", "en")
    source = data.get("source", None)
    if not text:
        return jsonify({"error": "No text provided"}), 400
    if target not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"Language '{target}' not supported"}), 400
    result = translate_text(text, target_language=target, source_language=source)
    return jsonify({
        "original": result.original_text,
        "translated": result.translated_text,
        "source_language": result.source_language,
        "source_language_name": get_language_name(result.source_language),
        "target_language": result.target_language,
        "target_language_name": get_language_name(result.target_language),
    })


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "File too large. Maximum is 64MB."}), 413


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Page not found."}), 404


if __name__ == "__main__":
    print("=" * 50)
    print("  📄 AskYourPDF v4.0 – Multi‑Document")
    print("=" * 50)

    app.config["OLLAMA_READY"] = verify_ollama()

    if app.config["OLLAMA_READY"]:
        print("  ✅ Ready! Open: http://127.0.0.1:5000")
    else:
        print("  ⚠️  Ollama not running. Start with: ollama serve")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)