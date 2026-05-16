# 📄 AskYourPDF — Private Multi-Language Document AI

**AskYourPDF** is a 100% local, private AI application that lets you upload PDF documents, ask natural language questions, get instant answers with page citations, and even summarize or translate your documents into 10 different languages. It runs completely on your computer — no data is ever sent to the cloud.

---

## 🎯 Features

- 📄 **Document Q&A** — Ask anything about your PDFs and get answers with source page numbers.
- 📝 **Smart Summarization** — Generate a concise summary of any document.
- 🖨️ **Printable Summary** — Download the summary as a clean PDF.
- 🌐 **10 Languages** — Translate answers or detect document language automatically.
- 🔒 **100% Private** — Everything runs locally, powered by Llama 3.2 via Ollama.
- 🗂️ **Multi-Document Support** — Save, load, and delete several documents easily.
- 💬 **Professional Web Interface** — Tooltips, a help modal, and a clean dark theme.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or newer
- Ollama

### One-Command Setup
1. Clone the repository or unzip the folder.
2. Double-click `INSTALL_ME.bat` (Windows) to set up everything automatically.
3. Once setup finishes, double-click `start_askyourpdf.bat` to launch.
4. Open your browser and go to `http://127.0.0.1:5000`.

### Manual Setup
```bash
# Launch Ollama and pull the model
ollama serve
ollama pull llama3.2:latest

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py

User Browser → Flask App → RAG Engine (LangChain + ChromaDB + Ollama)
               ↓
       Translation Engine (10 languages)

askyourpdf/
├── app.py                    # Flask web application
├── rag_engine.py             # Document processing and Q&A pipeline
├── translation_engine.py     # Language detection and translation
├── requirements.txt          # Python dependencies
├── .env.example              # Environment configuration template
├── Dockerfile                # Docker build instructions
├── start_askyourpdf.bat      # One-click launcher (Windows)
├── INSTALL_ME.bat            # Automated setup script (Windows)
├── templates/
│   └── index.html            # Web interface
├── data/                     # Uploaded PDFs
├── chroma_db/                # Vector databases (one per document)
└── logs/                     # Application logs


### Step 3: Paste into Notepad
- Click inside the blank Notepad window.
- Press `Ctrl+V` to paste everything.

### Step 4: Replace the placeholders
In the text, you'll see several placeholders in brackets `[ ]`. You need to replace these with your own information.

**FIND and REPLACE these lines:**

| Find this | Replace with |
|-----------|--------------|
| `[Your Name]` | Your full name (e.g., Jean Dupont) |
| `[your.email@example.com]` | Your email address (or delete the whole line if you don't want to show it) |
| `[https://github.com/yourusername]` | Your GitHub profile URL (or delete the line) |
| `[https://linkedin.com/in/yourname]` | Your LinkedIn profile URL (or delete the line) |
| `[Your Name]` in the license section | Your full name again (same as above) |

**Example:**  

After: `**Moustapha L. Diop** 

Before: `Copyright (c) 2026 Moustapha L. Diop`  


Just click at the end of each placeholder, delete it, and type your own info.

### Step 5: Save the file correctly
This is the most important part — if not saved with the right name and extension, it won't work.

1. In Notepad, click **File** → **Save As…**.
2. In the "Save in" dropdown at the top, navigate to your project folder:  
   `C:\Users\User\Desktop\askyourpdf`
3. At the bottom, find the field **"Save as type"** (it usually says "Text Documents (*.txt)").  
   Change it to **"All Files (*.*)"**.
4. In the **"File name"** field, type exactly:  
   **`README.md`**  
   (Yes, the extension is `.md`)
5. Click **Save**.

If Windows warns "If you change a file name extension, the file might become unusable", click **Yes**.

### Step 6: Verify it exists
Open File Explorer and go to `C:\Users\User\Desktop\askyourpdf`.  
You should now see a file named `README.md`.  
Double-click it to open — it will display as formatted Markdown if you have a Markdown viewer, or as plain text in Notepad.

---

## 🎉 What you just created

You now have a professional `README.md` that:
- Explains your project clearly.
- States your copyright and ownership.
- Tells users how to install and run it.
- Looks great on GitHub, LinkedIn, or anywhere you share your code.

If you later push to GitHub, this file will automatically be displayed as the front page of your repository.

---

Now you can continue with the other steps (license, GitHub push, etc.). Let me know if you'd like to adjust any section of the README, and I'll help you edit it.
