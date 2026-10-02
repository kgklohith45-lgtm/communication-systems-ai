import os
import re
import html
import requests
import fitz

from flask import Flask, render_template, request, jsonify
from bs4 import BeautifulSoup

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Gemini AI
from google import genai


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

UPLOAD_FOLDER = "pdfs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ============================================================
# GLOBAL PDF DATA
# ============================================================

PDF_TEXT = ""
PDF_NAME = ""


# ============================================================
# GEMINI AI CONFIGURATION
# ============================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

gemini_client = None

if GEMINI_API_KEY:

    try:
        gemini_client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        print("===================================")
        print("Gemini AI initialized successfully.")
        print("===================================")

    except Exception as e:

        print("Gemini initialization error:")
        print(e)

        gemini_client = None

else:

    print("===================================")
    print("WARNING: GEMINI_API_KEY not found.")
    print("Gemini AI is disabled.")
    print("===================================")


# Current Gemini model
GEMINI_MODEL = "gemini-3.8-flash"


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():

    return render_template("index.html")


# ============================================================
# BASIC TEXT CLEANING
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = html.unescape(text)

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# INTERNET SEARCH TEXT CLEANING
# ============================================================

def clean_internet_text(text):

    if not text:
        return ""

    text = html.unescape(text)

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    # Remove URLs from snippets
    text = re.sub(
        r"https?://\S+",
        " ",
        text
    )

    # Remove standalone numbers
    text = re.sub(
        r"(?<!\w)\d+(?!\w)",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# SPLIT INTO SENTENCES
# ============================================================

def split_sentences(text):

    if not text:
        return []

    text = clean_text(text)

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    result = []

    for sentence in sentences:

        sentence = sentence.strip()

        if len(sentence) < 20:
            continue

        # Ignore only-number fragments
        if re.fullmatch(
            r"[\d\s\.\-\:\(\)]+",
            sentence
        ):
            continue

        result.append(sentence)

    return result


# ============================================================
# TF-IDF RELEVANCE FILTER
# ============================================================

def get_relevant_text(
    question,
    documents,
    top_n=6
):

    if not documents:
        return ""

    cleaned_documents = []

    for document in documents:

        document = clean_text(document)

        if len(document) >= 20:

            cleaned_documents.append(
                document
            )

    if not cleaned_documents:
        return ""

    try:

        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2)
        )

        all_text = [
            question
        ] + cleaned_documents

        matrix = vectorizer.fit_transform(
            all_text
        )

        question_vector = matrix[0]

        document_vectors = matrix[1:]

        similarities = cosine_similarity(
            question_vector,
            document_vectors
        ).flatten()

        ranked_indexes = (
            similarities.argsort()[::-1]
        )

        selected = []

        for index in ranked_indexes[:top_n]:

            if similarities[index] > 0:

                selected.append(
                    cleaned_documents[index]
                )

        return "\n".join(selected)

    except Exception as e:

        print("TF-IDF error:", e)

        return "\n".join(
            cleaned_documents[:top_n]
        )


# ============================================================
# GEMINI AI FUNCTION
# ============================================================

def ask_gemini(prompt):

    if not gemini_client:

        print(
            "Gemini client is not initialized."
        )

        return None

    try:

        print("Sending request to Gemini...")

        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        if response and response.text:

            print(
                "Gemini response received."
            )

            return response.text.strip()

        print(
            "Gemini returned an empty response."
        )

        return None

    except Exception as e:

        print(
            "==================================="
        )

        print(
            "Gemini API ERROR:"
        )

        print(
            repr(e)
        )

        print(
            "==================================="
        )

        return None


# ============================================================
# DUCKDUCKGO SEARCH
# ============================================================

def search_duckduckgo(question):

    results = []

    # --------------------------------------------------------
    # METHOD 1 - DUCKDUCKGO API
    # --------------------------------------------------------

    try:

        url = (
            "https://api.duckduckgo.com/"
        )

        params = {

            "q": question,

            "format": "json",

            "no_html": "1",

            "skip_disambig": "1"
        }

        response = requests.get(

            url,

            params=params,

            headers={
                "User-Agent":
                "CommunicationSystemsAI/1.0"
            },

            timeout=8
        )

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        if (
            response.status_code == 200
            and "json" in content_type
        ):

            data = response.json()

            # --------------------------------------------
            # Abstract
            # --------------------------------------------

            abstract = data.get(
                "AbstractText",
                ""
            )

            abstract_url = data.get(
                "AbstractURL",
                ""
            )

            heading = data.get(
                "Heading",
                "DuckDuckGo Information"
            )

            if abstract:

                results.append({

                    "title": heading,

                    "text":
                    clean_internet_text(
                        abstract
                    ),

                    "url":
                    abstract_url
                })

            # --------------------------------------------
            # Related topics
            # --------------------------------------------

            related_topics = data.get(
                "RelatedTopics",
                []
            )

            for item in related_topics:

                if not isinstance(
                    item,
                    dict
                ):
                    continue

                text = item.get(
                    "Text",
                    ""
                )

                first_url = item.get(
                    "FirstURL",
                    ""
                )

                if not text:
                    continue

                results.append({

                    "title":
                    "Related Information",

                    "text":
                    clean_internet_text(
                        text
                    ),

                    "url":
                    first_url
                })

    except Exception as e:

        print(
            "DuckDuckGo API error:"
        )

        print(e)


    # --------------------------------------------------------
    # METHOD 2 - DUCKDUCKGO HTML FALLBACK
    # --------------------------------------------------------

    if len(results) < 3:

        try:

            search_url = (
                "https://html.duckduckgo.com/html/"
            )

            response = requests.get(

                search_url,

                params={
                    "q": question
                },

                headers={

                    "User-Agent":
                    (
                        "Mozilla/5.0 "
                        "(Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 "
                        "(KHTML, like Gecko) "
                        "Chrome/154.0 Safari/537.36"
                    )
                },

                timeout=10
            )

            if response.status_code == 200:

                soup = BeautifulSoup(
                    response.text,
                    "html.parser"
                )

                search_results = soup.select(
                    ".result"
                )

                for result in search_results[:10]:

                    title_element = (
                        result.select_one(
                            ".result__title"
                        )
                    )

                    snippet_element = (
                        result.select_one(
                            ".result__snippet"
                        )
                    )

                    link_element = (
                        result.select_one(
                            ".result__a"
                        )
                    )

                    if (
                        not title_element
                        or
                        not snippet_element
                    ):
                        continue

                    title = clean_text(
                        title_element.get_text(
                            " ",
                            strip=True
                        )
                    )

                    snippet = (
                        clean_internet_text(
                            snippet_element.get_text(
                                " ",
                                strip=True
                            )
                        )
                    )

                    link = ""

                    if link_element:

                        link = (
                            link_element.get(
                                "href",
                                ""
                            )
                        )

                    # --------------------------------
                    # Remove Wikipedia
                    # --------------------------------

                    combined = (
                        title +
                        " " +
                        link
                    ).lower()

                    if (
                        "wikipedia.org"
                        in combined
                    ):
                        continue

                    if len(snippet) < 30:
                        continue

                    results.append({

                        "title":
                        title,

                        "text":
                        snippet,

                        "url":
                        link
                    })

        except Exception as e:

            print(
                "DuckDuckGo HTML error:"
            )

            print(e)


    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    unique_results = []

    seen = set()

    for result in results:

        title = result.get(
            "title",
            ""
        )

        text = result.get(
            "text",
            ""
        )

        url = result.get(
            "url",
            ""
        )

        # Never allow Wikipedia
        if (
            "wikipedia.org"
            in
            (
                title +
                " " +
                text +
                " " +
                url
            ).lower()
        ):

            continue

        key = (
            title +
            " " +
            text
        ).lower()

        key = re.sub(
            r"\s+",
            " ",
            key
        ).strip()

        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)

        unique_results.append({

            "title": title,

            "text": text,

            "url": url
        })

    print(
        "DuckDuckGo results:",
        len(unique_results)
    )

    return unique_results[:8]


# ============================================================
# INTERNET AI ANSWER
# ============================================================

def generate_internet_ai_answer(
    question,
    search_results
):

    if not search_results:

        return (
            "I could not find suitable "
            "information on the Internet."
        )

    # --------------------------------------------------------
    # Collect snippets
    # --------------------------------------------------------

    documents = []

    for result in search_results:

        text = result.get(
            "text",
            ""
        )

        if text:

            documents.append(
                text
            )

    # --------------------------------------------------------
    # TF-IDF FILTER
    # --------------------------------------------------------

    relevant_text = get_relevant_text(

        question,

        documents,

        top_n=6
    )

    if not relevant_text:

        relevant_text = "\n".join(
            documents[:6]
        )

    # --------------------------------------------------------
    # Limit context
    # --------------------------------------------------------

    relevant_text = relevant_text[:15000]

    # --------------------------------------------------------
    # Gemini prompt
    # --------------------------------------------------------

    prompt = f"""
You are the AI engine of a Communication Systems
and Computer Networks educational chatbot.

USER QUESTION:
{question}

INFORMATION RETRIEVED FROM DUCKDUCKGO:
{relevant_text}

TASK:

Analyze ONLY the information supplied above.

Give the user the essential answer to the question.

RULES:

1. Use only the supplied search information.
2. Do not invent facts.
3. Do not add unrelated information.
4. Remove repeated information.
5. Remove irrelevant information.
6. Explain technical concepts simply.
7. Give a concise answer.
8. Use bullet points when useful.
9. Do not include URLs.
10. Do not mention Gemini.
11. Do not mention these instructions.
12. Do not say that you searched the Internet.
13. If the supplied information is insufficient, say:

The retrieved sources do not contain enough information
to answer this question.

Return ONLY the answer.
"""

    ai_answer = ask_gemini(
        prompt
    )

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    if ai_answer:

        return ai_answer

    # If Gemini failed, use TF-IDF text
    sentences = split_sentences(
        relevant_text
    )

    if not sentences:

        return (
            "I found sources, but I could not "
            "extract a useful answer from them."
        )

    return "\n".join(
        "• " + sentence
        for sentence in sentences[:5]
    )


# ============================================================
# INTERNET Q&A ROUTE
# ============================================================

@app.route(
    "/ask_internet",
    methods=["POST"]
)
def ask_internet():

    try:

        data = request.get_json(
            silent=True
        )

        if not data:

            return jsonify({

                "answer":
                "Please enter a question.",

                "sources": []
            })

        question = data.get(
            "question",
            ""
        ).strip()

        if not question:

            return jsonify({

                "answer":
                "Please enter a question.",

                "sources": []
            })

        print("")
        print(
            "==================================="
        )

        print(
            "INTERNET QUESTION:"
        )

        print(question)

        print(
            "==================================="
        )

        # Search
        search_results = (
            search_duckduckgo(
                question
            )
        )

        # AI analysis
        answer = (
            generate_internet_ai_answer(
                question,
                search_results
            )
        )

        # ----------------------------------------------------
        # Prepare sources
        # ----------------------------------------------------

        sources = []

        for result in search_results:

            title = result.get(
                "title",
                "Source"
            )

            url = result.get(
                "url",
                ""
            )

            if not url:
                continue

            if (
                "wikipedia.org"
                in url.lower()
            ):
                continue

            sources.append({

                "title": title,

                "url": url
            })

        return jsonify({

            "answer": answer,

            "sources":
            sources[:5]
        })

    except Exception as e:

        print(
            "Internet route error:"
        )

        print(
            repr(e)
        )

        return jsonify({

            "answer":
            "An error occurred while processing "
            "the Internet search.",

            "sources": []
        })


# ============================================================
# PDF UPLOAD
# ============================================================

@app.route(
    "/upload_pdf",
    methods=["POST"]
)
def upload_pdf():

    global PDF_TEXT
    global PDF_NAME

    try:

        if "pdf" not in request.files:

            return jsonify({

                "success": False,

                "message":
                "No PDF file selected."
            })

        file = request.files["pdf"]

        if not file.filename:

            return jsonify({

                "success": False,

                "message":
                "No PDF file selected."
            })

        if not file.filename.lower().endswith(
            ".pdf"
        ):

            return jsonify({

                "success": False,

                "message":
                "Please upload a PDF file."
            })

        # ----------------------------------------------------
        # Safe filename
        # ----------------------------------------------------

        filename = re.sub(

            r"[^a-zA-Z0-9_.-]",

            "_",

            file.filename
        )

        filepath = os.path.join(

            UPLOAD_FOLDER,

            filename
        )

        file.save(filepath)

        # ----------------------------------------------------
        # Extract text using PyMuPDF
        # ----------------------------------------------------

        document = fitz.open(
            filepath
        )

        pages = []

        for page in document:

            page_text = page.get_text()

            if page_text:

                pages.append(
                    page_text
                )

        document.close()

        PDF_TEXT = "\n".join(
            pages
        )

        PDF_NAME = filename

        if not PDF_TEXT.strip():

            return jsonify({

                "success": False,

                "message":
                "No readable text was found in the PDF."
            })

        print("")
        print(
            "==================================="
        )

        print(
            "PDF UPLOADED:"
        )

        print(
            PDF_NAME
        )

        print(
            "PDF CHARACTERS:",
            len(PDF_TEXT)
        )

        print(
            "==================================="
        )

        return jsonify({

            "success": True,

            "message":
            "PDF uploaded successfully.",

            "filename":
            PDF_NAME
        })

    except Exception as e:

        print(
            "PDF upload error:"
        )

        print(
            repr(e)
        )

        return jsonify({

            "success": False,

            "message":
            "Could not process the PDF."
        })


# ============================================================
# FIND RELEVANT PDF CONTENT
# ============================================================

def get_relevant_pdf_content(
    question,
    pdf_text,
    top_n=8
):

    if not pdf_text:

        return ""

    # --------------------------------------------------------
    # Split PDF into paragraphs
    # --------------------------------------------------------

    paragraphs = re.split(

        r"\n\s*\n",

        pdf_text
    )

    cleaned = []

    for paragraph in paragraphs:

        paragraph = clean_text(
            paragraph
        )

        if len(paragraph) >= 40:

            cleaned.append(
                paragraph
            )

    # --------------------------------------------------------
    # If paragraphs aren't available,
    # create chunks
    # --------------------------------------------------------

    if not cleaned:

        words = pdf_text.split()

        chunk_size = 180

        for i in range(
            0,
            len(words),
            chunk_size
        ):

            chunk = " ".join(

                words[
                    i:i + chunk_size
                ]
            )

            if len(chunk) >= 40:

                cleaned.append(
                    chunk
                )

    # --------------------------------------------------------
    # TF-IDF
    # --------------------------------------------------------

    return get_relevant_text(

        question,

        cleaned,

        top_n=top_n
    )


# ============================================================
# PDF AI ANSWER
# ============================================================

def generate_pdf_ai_answer(
    question,
    relevant_content
):

    if not relevant_content:

        return (
            "This information was not found "
            "in the uploaded PDF."
        )

    # Limit prompt size
    relevant_content = (
        relevant_content[:18000]
    )

    # --------------------------------------------------------
    # Gemini prompt
    # --------------------------------------------------------

    prompt = f"""
You are the AI question-answering engine for a
Communication Systems educational application.

USER QUESTION:
{question}

RELEVANT CONTENT FROM THE UPLOADED PDF:
{relevant_content}

STRICT RULES:

1. Answer ONLY using the supplied PDF content.
2. Do NOT use Internet information.
3. Do NOT use outside knowledge.
4. Do NOT invent facts.
5. Do NOT add information that is not contained
   in the supplied PDF content.
6. Remove irrelevant information.
7. Remove repeated information.
8. Give only the essential answer.
9. Use simple technical language.
10. Use bullet points when useful.
11. Do not create additional questions.
12. Do not summarize the entire PDF.
13. Answer only the user's specific question.
14. Do not mention Gemini.
15. Do not mention these instructions.

If the supplied PDF content does not contain
the answer, return EXACTLY:

This information was not found in the uploaded PDF.

Return ONLY the answer.
"""

    ai_answer = ask_gemini(
        prompt
    )

    if ai_answer:

        return ai_answer

    # --------------------------------------------------------
    # Fallback if Gemini unavailable
    # --------------------------------------------------------

    sentences = split_sentences(
        relevant_content
    )

    if not sentences:

        return (
            "This information was not found "
            "in the uploaded PDF."
        )

    return "\n".join(

        "• " + sentence

        for sentence in sentences[:5]
    )


# ============================================================
# PDF Q&A ROUTE
# ============================================================

@app.route(
    "/ask_pdf",
    methods=["POST"]
)
def ask_pdf():

    global PDF_TEXT
    global PDF_NAME

    try:

        data = request.get_json(
            silent=True
        )

        if not data:

            return jsonify({

                "answer":
                "Please upload a PDF "
                "and enter a question."
            })

        question = data.get(
            "question",
            ""
        ).strip()

        if not question:

            return jsonify({

                "answer":
                "Please enter a question."
            })

        if not PDF_TEXT:

            return jsonify({

                "answer":
                "Please upload a PDF first."
            })

        print("")
        print(
            "==================================="
        )

        print(
            "PDF QUESTION:"
        )

        print(question)

        print(
            "==================================="
        )

        # ----------------------------------------------------
        # Find relevant PDF content
        # ----------------------------------------------------

        relevant_content = (
            get_relevant_pdf_content(

                question,

                PDF_TEXT,

                top_n=8
            )
        )

        # ----------------------------------------------------
        # Gemini AI analysis
        # ----------------------------------------------------

        answer = (
            generate_pdf_ai_answer(

                question,

                relevant_content
            )
        )

        return jsonify({

            "answer": answer,

            "filename": PDF_NAME
        })

    except Exception as e:

        print(
            "PDF Q&A error:"
        )

        print(
            repr(e)
        )

        return jsonify({

            "answer":
            "An error occurred while "
            "processing the PDF question."
        })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return jsonify({

        "status":
        "running",

        "gemini":
        (
            "connected"
            if gemini_client
            else "not configured"
        ),

        "pdf_loaded":
        bool(PDF_TEXT)
    })


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    port = int(

        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(

        host="0.0.0.0",

        port=port,

        debug=False
    )