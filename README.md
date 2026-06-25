# 🛡️ Privacy Shield AI

An AI-powered Privacy Protection and Sensitive Data Redaction System that automatically detects and masks Personally Identifiable Information (PII) from documents and images.

Developed as part of my AI Internship at **Jethur Innovations**.

---

## 📌 Overview

Privacy Shield AI is designed to help organizations protect sensitive information by automatically detecting and redacting confidential data from various document formats.

The system supports:

- 📄 PDF Documents
- 📝 DOCX Documents
- 📃 TXT Files
- 🖼️ Images (PNG, JPG, JPEG, WEBP, TIFF, BMP)

Using a hybrid AI approach, the application combines OCR, Natural Language Processing (NLP), custom pattern recognizers, and rule-based detection to achieve accurate redaction.

---

# ✨ Features

- 🔍 Automatic PII Detection
- 📄 PDF Redaction
- 🖼️ Image Redaction
- 📝 DOCX & TXT Support
- 👤 Face Detection & Blurring
- 📷 OCR using Tesseract
- 🧠 Hybrid Detection Engine
- 🇮🇳 Indian Identity Detection
- 📊 Confidence Scores
- 📥 Download Redacted Documents

---

# 🏗️ System Architecture

The processing pipeline follows this workflow:

```
User
   │
Upload File
   │
Frontend
   │
FastAPI Backend
   │
Document Processing
   │
Text Extraction
   │
Hybrid Detection Engine
   │
Entity Processing
   │
Anonymization
   │
Redaction Engine
   │
Frontend Results
```

---

# 🧠 Hybrid Detection Engine

Privacy Shield AI uses **four complementary detection techniques**:

### 1️⃣ Microsoft Presidio

Detects common Personally Identifiable Information such as:

- Email Addresses
- Phone Numbers
- URLs
- IP Addresses
- Credit Cards
- Date & Time

---

### 2️⃣ spaCy Named Entity Recognition (NER)

Detects contextual entities including:

- Person
- Organization
- Location
- Nationalities

---

### 3️⃣ Custom Pattern Recognizers

Developed specifically for Indian documents.

Supports detection of:

- Aadhaar Number
- PAN Number
- Passport Number
- IFSC Code
- Bank Account Number
- Employee ID
- Indian Phone Numbers

---

### 4️⃣ Rule-Based Detection

Identifies structured fields such as:

- Name
- Address
- Organization
- Location
- Employee ID
- Labels inside forms

---

# 📂 Supported File Formats

| Type | Supported |
|------|-----------|
| PDF | ✅ |
| DOCX | ✅ |
| TXT | ✅ |
| PNG | ✅ |
| JPG | ✅ |
| JPEG | ✅ |
| WEBP | ✅ |
| TIFF | ✅ |
| BMP | ✅ |

---

# ⚙️ Technology Stack

## Frontend

- HTML5
- CSS3
- JavaScript

## Backend

- FastAPI
- Python

## OCR

- Tesseract OCR

## NLP

- Microsoft Presidio
- spaCy

## Computer Vision

- OpenCV
- Pillow

## PDF Processing

- PyMuPDF

## Document Processing

- python-docx

---

# 📁 Project Structure

```
Privacy-Shield-AI/

├── app.py
├── detector.py
├── extractor.py
├── recognizers.py
├── redactor.py
├── rules.py
├── spacy_engine.py
├── spacy_config.yaml
├── requirements.txt
├── tests/
└── README.md
```

---

# 🚀 Installation

Clone the repository

```bash
git clone https://github.com/yourusername/Privacy-Shield-AI.git
```

Navigate into the project

```bash
cd Privacy-Shield-AI
```

Create a virtual environment

```bash
python -m venv venv
```

Activate it

Windows

```bash
venv\Scripts\activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Download the spaCy model

```bash
python -m spacy download en_core_web_sm
```

Run the application

```bash
uvicorn app:app --reload
```

Open

```
http://127.0.0.1:8000
```

---

# 📸 Screenshots

> Add screenshots here after deployment.

Example:

- Home Page
- Upload Screen
- Entity Detection
- Redacted PDF
- Redacted Image
- Architecture Diagram

---

# 🔮 Future Enhancements

- Multi-language OCR
- Handwritten Text Recognition
- Batch Processing
- Cloud Deployment
- Audit Logs
- Role-Based Access
- Transformer-based NER Models

---

# 👨‍💻 Author

**Adwaith K A**

AI Intern – Jethur Innovations

Computer Science Engineering Student

---

# 📜 License

This project is licensed under the MIT License.
