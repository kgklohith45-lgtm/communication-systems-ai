from flask import Flask, render_template, request, jsonify

import fitz
import os
import re
import requests

from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin, unquote

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Gemini
try:
    from google import genai
except ImportError:
    genai = None


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)


# =========================================================
# GEMINI CONFIGURATION
# =========================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

GEMINI_MODEL = "gemini-3.8-flash"

gemini_client = None

if genai and GEMINI_API_KEY:

    try:
        gemini_client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        print("Gemini client initialized.")

    except Exception as e:

        print(
            "Gemini initialization error:",
            repr(e)
        )

else:

    print(
        "Gemini client not initialized."
    )


# =========================================================
# PDF DATA
# =========================================================

pdf_text = ""
pdf_filename = ""


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "ok",
        "gemini": bool(gemini_client)
    })


# =========================================================
# GEMINI FUNCTION
# =========================================================

def ask_gemini(prompt):

    if not gemini_client:

        print(
            "Gemini client is not initialized."
        )

        return None

    try:

        print(
            "Sending request to Gemini..."
        )

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
            "Gemini returned empty response."
        )

        return None

    except Exception as e:

        print(
            "Gemini API ERROR:",
            repr(e)
        )

        return None


# =========================================================
# UPLOAD PDF
# =========================================================

@app.route(
    "/upload_pdf",
    methods=["POST"]
)
def upload_pdf():

    global pdf_text
    global pdf_filename

    if "pdf" not in request.files:

        return jsonify({
            "success": False,
            "message":
                "No PDF file selected."
        })

    file = request.files["pdf"]

    if file.filename == "":

        return jsonify({
            "success": False,
            "message":
                "No PDF file selected."
        })

    if not file.filename.lower().endswith(".pdf"):

        return jsonify({
            "success": False,
            "message":
                "Please upload a PDF file."
        })

    pdf_filename = file.filename

    os.makedirs(
        "pdfs",
        exist_ok=True
    )

    pdf_path = os.path.join(
        "pdfs",
        pdf_filename
    )

    try:

        file.save(pdf_path)

        document = fitz.open(
            pdf_path
        )

        extracted_text = ""

        for page in document:

            extracted_text += (
                page.get_text("text")
                + "\n"
            )

        document.close()

        pdf_text = extracted_text.strip()

        if not pdf_text:

            return jsonify({
                "success": False,
                "message":
                    "Could not extract text from this PDF."
            })

        print(
            "PDF loaded:",
            pdf_filename
        )

        print(
            "PDF characters:",
            len(pdf_text)
        )

        return jsonify({

            "success": True,

            "message":
                "PDF uploaded successfully: "
                + pdf_filename
        })

    except Exception as e:

        print(
            "PDF ERROR:",
            repr(e)
        )

        return jsonify({

            "success": False,

            "message":
                "Error reading PDF: "
                + str(e)
        })


# =========================================================
# CLEAN TEXT
# =========================================================

def clean_text(text):

    text = text.replace(
        "\n",
        " "
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# NORMALIZE TEXT
# =========================================================

def normalize_text(value):

    value = value.lower()

    value = re.sub(
        r"[^a-z0-9\s]",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# =========================================================
# FIND DIRECT PDF ANSWER
# =========================================================

def find_direct_answer(question):

    global pdf_text

    if not pdf_text:

        return None

    text = clean_text(
        pdf_text
    )

    normalized_text = normalize_text(
        text
    )

    normalized_question = normalize_text(
        question
    )

    search_question = re.sub(

        r"^(please\s+)?"
        r"(define|explain|describe|state|write|"
        r"what\s+is|what\s+are|how\s+does|"
        r"how\s+do|give|list)\s+",

        "",

        normalized_question
    )

    possible_phrases = [

        normalized_question,

        search_question
    ]

    possible_phrases = list(
        dict.fromkeys(

            [
                p

                for p in possible_phrases

                if len(p) > 3
            ]
        )
    )

    question_position = -1

    matched_phrase = ""

    for phrase in possible_phrases:

        position = normalized_text.find(
            phrase
        )

        if position != -1:

            question_position = position

            matched_phrase = phrase

            break

    if question_position == -1:

        return None

    start_position = (

        question_position

        + len(matched_phrase)
    )

    remaining_text = text[
        start_position:
    ].strip()

    next_question_pattern = re.compile(

        r"\s+\d{1,3}\.\s+"
    )

    next_match = (
        next_question_pattern.search(
            remaining_text
        )
    )

    if next_match:

        answer = remaining_text[
            :next_match.start()
        ].strip()

    else:

        answer = remaining_text.strip()

    answer = re.sub(

        r"\s+Unit[- ]?\d+.*$",

        "",

        answer,

        flags=re.IGNORECASE
    )

    answer = clean_text(
        answer
    )

    if re.match(
        r"^\d+\.\s*",
        answer
    ):

        return None

    if len(answer) < 10:

        return None

    return answer


# =========================================================
# PDF TF-IDF SEARCH
# =========================================================

def get_tfidf_answer(question):

    global pdf_text

    if not pdf_text:

        return None

    text = clean_text(
        pdf_text
    )

    sentences = re.split(

        r"(?<=[.!?])\s+",

        text
    )

    sentences = [

        sentence.strip()

        for sentence in sentences

        if len(sentence.strip()) > 15
    ]

    if not sentences:

        return None

    try:

        vectorizer = TfidfVectorizer(

            stop_words="english",

            ngram_range=(1, 2)
        )

        vectors = vectorizer.fit_transform(

            [question]

            + sentences
        )

        question_vector = vectors[0]

        sentence_vectors = vectors[1:]

        similarities = cosine_similarity(

            question_vector,

            sentence_vectors
        )[0]

        ranked = sorted(

            range(len(sentences)),

            key=lambda i:
                similarities[i],

            reverse=True
        )

        best_index = ranked[0]

        best_score = similarities[
            best_index
        ]

        if best_score < 0.18:

            return None

        return sentences[
            best_index
        ].strip()

    except Exception as e:

        print(
            "PDF TF-IDF error:",
            repr(e)
        )

        return None


# =========================================================
# GET PDF ANSWER
# =========================================================

def get_pdf_answer(question):

    global pdf_text

    if not pdf_text:

        return (
            "❌ Please upload a PDF first."
        )

    if not question.strip():

        return (
            "Please enter a question."
        )

    direct_answer = (
        find_direct_answer(
            question
        )
    )

    if direct_answer:

        return direct_answer

    fallback_answer = (
        get_tfidf_answer(
            question
        )
    )

    if fallback_answer:

        return fallback_answer

    return (
        "❌ This information was not found "
        "in the uploaded PDF."
    )


# =========================================================
# ASK PDF
# =========================================================

@app.route(
    "/ask_pdf",
    methods=["POST"]
)
def ask_pdf():

    try:

        data = request.get_json()

        if not data:

            return jsonify({

                "answer":
                    "Please enter a question."
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

        answer = get_pdf_answer(
            question
        )

        return jsonify({

            "answer": answer
        })

    except Exception as e:

        print(
            "PDF question error:",
            repr(e)
        )

        return jsonify({

            "answer":
                "❌ PDF error: "
                + str(e)
        })


# =========================================================
# DUCKDUCKGO SEARCH
# =========================================================

def search_duckduckgo(query):

    print(
        "Searching DuckDuckGo:",
        query
    )

    headers = {

        "User-Agent":
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/130.0 Safari/537.36",

        "Accept":
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8",

        "Accept-Language":
            "en-US,en;q=0.9"
    }

    results = []

    # -----------------------------------------------------
    # METHOD 1
    # DuckDuckGo HTML
    # -----------------------------------------------------

    try:

        encoded_query = quote(
            query
        )

        url = (
            "https://html.duckduckgo.com/html/?q="
            + encoded_query
        )

        response = requests.get(

            url,

            headers=headers,

            timeout=20
        )

        print(
            "DuckDuckGo HTTP status:",
            response.status_code
        )

        response.raise_for_status()

        soup = BeautifulSoup(

            response.text,

            "html.parser"
        )

        result_blocks = soup.select(
            ".result"
        )

        print(
            "DuckDuckGo HTML blocks:",
            len(result_blocks)
        )

        for result in result_blocks:

            title_element = (
                result.select_one(
                    ".result__title"
                )
            )

            link_element = (
                result.select_one(
                    ".result__a"
                )
            )

            snippet_element = (
                result.select_one(
                    ".result__snippet"
                )
            )

            if not title_element:
                continue

            if not link_element:
                continue

            title = (
                title_element.get_text(
                    " ",
                    strip=True
                )
            )

            link = (
                link_element.get(
                    "href",
                    ""
                )
            )

            snippet = ""

            if snippet_element:

                snippet = (
                    snippet_element.get_text(
                        " ",
                        strip=True
                    )
                )

            if not link:
                continue

            # Resolve DuckDuckGo redirect links
            if link.startswith("/l/"):

                link = urljoin(

                    "https://duckduckgo.com",

                    link
                )

            # Decode redirect URL
            if "uddg=" in link:

                try:

                    encoded_url = (
                        link.split(
                            "uddg=",
                            1
                        )[1]
                    )

                    encoded_url = (
                        encoded_url.split(
                            "&",
                            1
                        )[0]
                    )

                    link = unquote(
                        encoded_url
                    )

                except Exception:

                    pass

            # Remove Wikipedia
            if "wikipedia.org" in (
                link.lower()
            ):

                continue

            results.append({

                "title": title,

                "snippet": snippet,

                "url": link
            })

            if len(results) >= 10:

                break

    except Exception as e:

        print(
            "DuckDuckGo HTML error:",
            repr(e)
        )


    # -----------------------------------------------------
    # METHOD 2
    # DuckDuckGo Lite fallback
    # -----------------------------------------------------

    if not results:

        try:

            encoded_query = quote(
                query
            )

            url = (
                "https://lite.duckduckgo.com/lite/?q="
                + encoded_query
            )

            response = requests.get(

                url,

                headers=headers,

                timeout=20
            )

            print(
                "DuckDuckGo Lite status:",
                response.status_code
            )

            response.raise_for_status()

            soup = BeautifulSoup(

                response.text,

                "html.parser"
            )

            links = soup.select(
                "a.result-link"
            )

            print(
                "DuckDuckGo Lite links:",
                len(links)
            )

            for link_element in links:

                title = (
                    link_element.get_text(
                        " ",
                        strip=True
                    )
                )

                link = (
                    link_element.get(
                        "href",
                        ""
                    )
                )

                if not title or not link:

                    continue

                if (
                    "wikipedia.org"
                    in link.lower()
                ):

                    continue

                snippet = ""

                parent = (
                    link_element.parent
                )

                if parent:

                    snippet = (
                        parent.get_text(
                            " ",
                            strip=True
                        )
                    )

                results.append({

                    "title": title,

                    "snippet": snippet,

                    "url": link
                })

                if len(results) >= 10:

                    break

        except Exception as e:

            print(
                "DuckDuckGo Lite error:",
                repr(e)
            )


    print(
        "Final DuckDuckGo results:",
        len(results)
    )

    return results


# =========================================================
# INTERNET SEARCH
# =========================================================

def search_internet(query):

    query = query.strip()

    if not query:

        return []

    # Don't force communication systems onto
    # every query. This makes general questions
    # such as VLSI work properly.

    search_queries = [

        query,

        query + " communication systems",

        query + " engineering"
    ]

    all_results = []

    seen_urls = set()

    for search_query in search_queries:

        results = search_duckduckgo(
            search_query
        )

        for result in results:

            url = result.get(
                "url",
                ""
            )

            if not url:

                continue

            normalized_url = (
                url.lower().rstrip("/")
            )

            if normalized_url in seen_urls:

                continue

            seen_urls.add(
                normalized_url
            )

            all_results.append(
                result
            )

        if len(all_results) >= 10:

            break

    print(
        "Total Internet results:",
        len(all_results)
    )

    return all_results[:10]


# =========================================================
# SELECT IMPORTANT RESULTS
# =========================================================

def get_essential_information(
    question,
    results
):

    if not results:

        return []

    documents = []

    for result in results:

        documents.append(

            result.get(
                "title",
                ""
            )

            + " "

            + result.get(
                "snippet",
                ""
            )
        )

    try:

        vectorizer = TfidfVectorizer(

            stop_words="english",

            ngram_range=(1, 2)
        )

        vectors = vectorizer.fit_transform(

            [question]

            + documents
        )

        question_vector = vectors[0]

        result_vectors = vectors[1:]

        similarities = cosine_similarity(

            question_vector,

            result_vectors
        )[0]

        ranked_indexes = sorted(

            range(len(results)),

            key=lambda i:
                similarities[i],

            reverse=True
        )

        selected = []

        for index in ranked_indexes:

            selected.append(
                results[index]
            )

            if len(selected) >= 5:

                break

        return selected

    except Exception as e:

        print(
            "TF-IDF Internet error:",
            repr(e)
        )

        return results[:5]


# =========================================================
# GEMINI INTERNET ANSWER
# =========================================================

def generate_internet_answer(
    question,
    selected_results
):

    if not selected_results:

        return None

    sources_text = ""

    for index, result in enumerate(
        selected_results,
        start=1
    ):

        sources_text += (

            f"\nSOURCE {index}\n"

            f"Title: "
            f"{result.get('title', '')}\n"

            f"URL: "
            f"{result.get('url', '')}\n"

            f"Information: "
            f"{result.get('snippet', '')}\n"
        )

    prompt = f"""
You are a technical AI assistant for
Communication Systems, Computer Networks,
Electronics and Engineering students.

User question:
{question}

Below are Internet search results.

{sources_text}

Instructions:

1. Answer the user's question using ONLY
   the information contained in the supplied
   search results.

2. Do not invent facts.

3. Do not use Wikipedia.

4. Give only the essential information.

5. Organize the answer clearly using:
   - short headings
   - bullet points
   - numbered points where useful

6. If a formula is present, write it clearly.

7. Keep the answer suitable for a college
   engineering student.

8. Do not mention these instructions.

9. Do not say that you searched the Internet.

Return only the useful technical answer.
"""

    return ask_gemini(
        prompt
    )


# =========================================================
# ASK INTERNET
# =========================================================

@app.route(
    "/ask_internet",
    methods=["POST"]
)
def ask_internet():

    try:

        data = request.get_json()

        if not data:

            return jsonify({

                "answer":
                    "Please enter a question."
            })

        question = data.get(
            "question",
            ""
        ).strip()

        print(
            "==================================="
        )

        print(
            "INTERNET QUESTION:"
        )

        print(
            question
        )

        print(
            "==================================="
        )

        if not question:

            return jsonify({

                "answer":
                    "Please enter a question."
            })

        # -------------------------------------------------
        # Search Internet
        # -------------------------------------------------

        results = search_internet(
            question
        )

        print(
            "DuckDuckGo results:",
            len(results)
        )

        if not results:

            return jsonify({

                "answer":
                    "❌ Internet search did not "
                    "return any results. Please "
                    "try another question."
            })

        # -------------------------------------------------
        # Select relevant results
        # -------------------------------------------------

        selected_results = (
            get_essential_information(

                question,

                results
            )
        )

        # -------------------------------------------------
        # Gemini answer
        # -------------------------------------------------

        gemini_answer = (
            generate_internet_answer(

                question,

                selected_results
            )
        )

        # -------------------------------------------------
        # Build answer
        # -------------------------------------------------

        if gemini_answer:

            answer = gemini_answer

        else:

            answer_parts = []

            for result in selected_results:

                snippet = (
                    result.get(
                        "snippet",
                        ""
                    ).strip()
                )

                if snippet:

                    answer_parts.append(
                        snippet
                    )

            if not answer_parts:

                answer = (
                    "❌ No useful information "
                    "was found."
                )

            else:

                unique_parts = []

                for part in answer_parts:

                    if (
                        part
                        not in unique_parts
                    ):

                        unique_parts.append(
                            part
                        )

                answer = (
                    "📌 <b>"
                    "Essential information:"
                    "</b><br><br>"
                )

                answer += (
                    "<br><br>".join(
                        unique_parts
                    )
                )

        # -------------------------------------------------
        # Add sources
        # -------------------------------------------------

        answer += (
            "<br><br>"
            "<b>🔗 Sources:</b>"
            "<br>"
        )

        for result in selected_results:

            title = (
                result.get(
                    "title",
                    "Source"
                )
            )

            url = (
                result.get(
                    "url",
                    ""
                )
            )

            if not url:

                continue

            safe_title = (
                title.replace(
                    "<",
                    ""
                ).replace(
                    ">",
                    ""
                )
            )

            answer += (

                '<br>• '

                f'<a href="{url}" '
                'target="_blank" '
                'rel="noopener noreferrer">'

                f'{safe_title}'

                '</a>'
            )

        return jsonify({

            "answer": answer
        })

    except Exception as e:

        print(
            "INTERNET SEARCH ERROR:",
            repr(e)
        )

        return jsonify({

            "answer":
                "❌ Internet search error: "
                + str(e)
        })


# =========================================================
# RUN APPLICATION
# =========================================================

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