# QueryBee — GECK Admission Chatbot

QueryBee is a simple multilingual admission-support chatbot for Government Engineering College Kozhikode (GECK), Kerala.

## Features
- English + Malayalam responses
- Admission-focused knowledge base derived from the supplied GECK Q&A PDF
- Flexible matching for differently worded questions using token overlap, synonyms, keywords, character n-grams and fuzzy string similarity
- gTTS voice response endpoint
- Browser speech-synthesis fallback if gTTS cannot connect
- Responsive web interface
- Quick questions for documents, admission date, fees and hostel

## Run locally

1. Open a terminal inside this folder.
2. Create a virtual environment (optional):
   python -m venv venv

3. Activate it:
   Windows:
   venv\Scripts\activate

   macOS/Linux:
   source venv/bin/activate

4. Install dependencies:
   pip install -r requirements.txt

5. Start the app:
   python app.py

6. Open:
   http://127.0.0.1:5000

## How the "intelligent" matching works
The project deliberately avoids requiring a large AI model. It compares each student question against:
- multiple alternative questions,
- topic keywords,
- normalized words,
- common admission aliases,
- fuzzy text similarity.

So questions such as:
- "what papers should I bring"
- "documents needed for joining"
- "admission certificates list"

can map to the same admission-document answer.

## gTTS note
gTTS sends text to Google's speech service, so voice generation needs internet access at runtime. If it fails, the frontend tries the browser's built-in speech synthesis.

## Knowledge base
Edit:
data/knowledge_base.json

Each item contains:
- category
- alternative questions
- English answer
- Malayalam answer
- keywords

You can add more question variations without changing the Python code.

## Important
The chatbot answers from the supplied admission dataset. Admission dates and fees can change in future academic years, so update `data/knowledge_base.json` whenever the college publishes new information.
