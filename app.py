
from flask import Flask, render_template, request, jsonify, send_from_directory
from pathlib import Path
import json, re, uuid, os
from difflib import SequenceMatcher

try:
    from gtts import gTTS
except Exception:
    gTTS = None

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "static" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

with open(BASE_DIR / "data" / "knowledge_base.json", encoding="utf-8") as f:
    KB = json.load(f)

MALAYALAM_RE = re.compile(r"[\u0D00-\u0D7F]")

# Malayalam -> English topic hints. These are only used for retrieval; answers remain
# exactly the curated English/Malayalam answers in knowledge_base.json.
ML_HINTS = {
    "ഫീസ്":"fee", "ഫീസ":"fee", "പണം":"fee", "തുക":"amount", "അടയ്ക്ക":"payment",
    "രേഖ":"document", "രേഖകൾ":"documents", "സർട്ടിഫിക്കറ്റ്":"certificate",
    "അഡ്മിഷൻ":"admission", "പ്രവേശനം":"admission", "തീയതി":"date",
    "എപ്പോൾ":"when", "സമയം":"time", "എത്ര":"how much", "എന്താണ്":"what",
    "ഹോസ്റ്റൽ":"hostel", "ഹോസ്റ്റല്":"hostel", "പെൺകുട്ടികൾ":"girls",
    "കോഴ്സ്":"course", "ബ്രാഞ്ച്":"branch", "വിഭാഗം":"branch",
    "യൂണിവേഴ്സിറ്റി":"university", "സർവകലാശാല":"university",
    "സ്കോളർഷിപ്പ്":"scholarship", "സഹായം":"help", "പ്ലേസ്മെന്റ്":"placement",
    "ഫണ്ട്":"fund", "ഫീസ്":"fee", "കോളേജ്":"college"
}

# Common shorthand/synonyms students may use.
SYNONYMS = {
    "papers":"documents", "paper":"document", "docs":"documents",
    "certs":"certificates", "cert":"certificate",
    "joining":"admission", "join":"admission", "enrolment":"admission",
    "enrollment":"admission", "seat":"intake", "seats":"intake",
    "branch":"branch", "department":"branch",
    "cost":"fee", "price":"fee", "charge":"fee", "charges":"fee",
    "amount":"fee", "pay":"payment", "paid":"payment",
    "placement":"career guidance placement", "cgpc":"career guidance placement",
    "career":"career guidance placement", "guidance":"career guidance placement",
    "fund":"fund", "funds":"fund",
    "girls":"ladies hostel", "girl":"ladies hostel",
    "uni":"university", "ktu":"university",
    "photo":"photograph", "pics":"photograph",
    "tc":"transfer certificate",
    "dob":"date of birth",
    "plus2":"plus two", "12th":"plus two",
}

def normalize(text):
    text = (text or "").lower().strip()
    for ml, en in ML_HINTS.items():
        text = text.replace(ml, " " + en + " ")
    # Preserve numbers because dates, fees and counts are important retrieval signals.
    text = re.sub(r"[^a-z0-9\u0D00-\u0D7F₹.\-\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def token_list(text):
    raw = normalize(text).split()
    out = []
    for t in raw:
        out.append(SYNONYMS.get(t, t))
    return out

def token_set(text):
    return set(token_list(text))

def char_ngrams(text, n=3):
    s = normalize(text).replace(" ", "")
    if len(s) <= n:
        return {s} if s else set()
    return {s[i:i+n] for i in range(len(s)-n+1)}

def similarity(query, candidate):
    qn, cn = normalize(query), normalize(candidate)
    qt, ct = token_set(query), token_set(candidate)

    if not qn or not cn:
        return 0.0

    # Token overlap
    inter = len(qt & ct)
    union = len(qt | ct)
    jaccard = inter / union if union else 0.0

    # Containment helps short questions such as "placement fund?"
    containment = inter / min(len(qt), len(ct)) if min(len(qt), len(ct)) else 0.0

    # Fuzzy sequence and character n-gram similarity handle word-order differences/typos.
    seq = SequenceMatcher(None, qn, cn).ratio()
    qg, cg = char_ngrams(qn), char_ngrams(cn)
    ng = len(qg & cg) / len(qg | cg) if qg and cg else 0.0

    return 0.28*jaccard + 0.28*containment + 0.22*seq + 0.22*ng

def score_item(query, item):
    candidates = list(item.get("questions", []))
    candidates += item.get("keywords", [])
    candidates.append(item.get("answer_en", ""))
    candidates.append(item.get("answer_ml", ""))

    best = max((similarity(query, c) for c in candidates), default=0.0)

    q_tokens = token_set(query)
    key_tokens = token_set(" ".join(item.get("keywords", [])))
    hits = len(q_tokens & key_tokens)
    keyword_bonus = min(hits * 0.045, 0.18)

    # Strong exact signals for amounts, dates, and named entities.
    q_norm = normalize(query)
    answer_blob = normalize(item.get("answer_en", "") + " " + item.get("answer_ml", ""))
    number_bonus = 0.08 if re.findall(r"\d+", q_norm) and any(n in answer_blob for n in re.findall(r"\d+", q_norm)) else 0.0

    return min(1.0, best + keyword_bonus + number_bonus)

def detect_language(text, requested):
    if requested in ("en", "ml"):
        return requested
    return "ml" if MALAYALAM_RE.search(text or "") else "en"

def find_answer(query, lang):
    ranked = sorted(
        ((score_item(query, item), item) for item in KB),
        key=lambda x: x[0],
        reverse=True
    )
    best_score, best = ranked[0]

    # A lower threshold than the previous version allows natural paraphrases,
    # while the fallback still prevents unrelated questions from receiving a random answer.
    if best_score < 0.24:
        fallback = (
            "I couldn't confidently find that in the GECK admission information I have. "
            "Try asking about admission dates, documents, fees, courses, university, hostel, scholarships, or student support."
            if lang == "en" else
            "എന്റെ കൈവശമുള്ള GECK admission വിവരങ്ങളിൽ ഈ ചോദ്യത്തിന് വ്യക്തമായ ഉത്തരം കണ്ടെത്താനായില്ല. "
            "Admission dates, documents, fees, courses, university, hostel, scholarship, student support എന്നിവയെക്കുറിച്ച് ചോദിക്കാം."
        )
        return fallback, "Not matched", best_score, []

    answer = best["answer_ml"] if lang == "ml" else best["answer_en"]
    suggestions = [item["questions"][0] for s, item in ranked[1:4] if s >= 0.18]
    return answer, best["category"], best_score, suggestions

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    requested_lang = data.get("language", "auto")

    if not message:
        return jsonify({"error":"Please enter a question."}), 400

    lang = detect_language(message, requested_lang)
    answer, category, confidence, suggestions = find_answer(message, lang)

    return jsonify({
        "answer": answer,
        "language": lang,
        "category": category,
        "confidence": round(confidence, 3),
        "suggestions": suggestions
    })

@app.route("/api/tts", methods=["POST"])
def tts():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    lang = data.get("language", "en")

    if not text:
        return jsonify({"error":"No text supplied."}), 400

    if gTTS is None:
        return jsonify({"error":"gTTS is not installed. Run: pip install -r requirements.txt"}), 500

    # gTTS uses 'ml' for Malayalam and 'en' for English.
    filename = f"{uuid.uuid4().hex}.mp3"
    path = AUDIO_DIR / filename

    try:
        gTTS(text=text, lang="ml" if lang == "ml" else "en").save(str(path))
        return jsonify({"audio_url": f"/static/audio/{filename}"})
    except Exception as exc:
        return jsonify({
            "error":"Voice generation failed. gTTS requires an internet connection.",
            "details": str(exc)
        }), 500

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
