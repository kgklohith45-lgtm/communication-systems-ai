from flask import Flask, render_template, request, jsonify

import fitz
import os
import re
import requests

from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)


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
    return render_template("index.html")


# =========================================================
# UPLOAD PDF
# =========================================================

@app.route("/upload_pdf", methods=["POST"])
def upload_pdf():

    global pdf_text
    global pdf_filename

    if "pdf" not in request.files:
        return jsonify({
            "success": False,
            "message": "No PDF file selected."
        })

    file = request.files["pdf"]

    if file.filename == "":
        return jsonify({
            "success": False,
            "message": "No PDF file selected."
        })

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({
            "success": False,
            "message": "Please upload a PDF file."
        })

    pdf_filename = file.filename

    os.makedirs("pdfs", exist_ok=True)

    pdf_path = os.path.join(
        "pdfs",
        pdf_filename
    )

    file.save(pdf_path)

    try:

        document = fitz.open(pdf_path)

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
                "message": "Could not extract text from this PDF."
            })

        return jsonify({
            "success": True,
            "message":
                "PDF uploaded successfully: "
                + pdf_filename
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message":
                "Error reading PDF: "
                + str(e)
        })


# =========================================================
# CLEAN PDF TEXT
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
# FIND DIRECT ANSWER FROM PDF
# =========================================================

def find_direct_answer(question):

    global pdf_text

    if not pdf_text:
        return None

    text = clean_text(pdf_text)

    question = clean_text(question)

    # -----------------------------------------------------
    # Normalize text
    # -----------------------------------------------------

    def normalize(value):

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

    normalized_text = normalize(text)

    normalized_question = normalize(question)

    # -----------------------------------------------------
    # Remove common question words
    # -----------------------------------------------------

    search_question = re.sub(
        r"^(please\s+)?"
        r"(define|explain|describe|state|write|"
        r"what\s+is|what\s+are|how\s+does|"
        r"how\s+do|give|list)\s+",
        "",
        normalized_question
    )

    # -----------------------------------------------------
    # Possible search phrases
    # -----------------------------------------------------

    possible_phrases = [
        normalized_question,
        search_question
    ]

    possible_phrases = list(
        dict.fromkeys(
            [
                p for p in possible_phrases
                if len(p) > 3
            ]
        )
    )

    question_position = -1
    matched_phrase = ""

    # -----------------------------------------------------
    # Search question inside PDF
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Text after question
    # -----------------------------------------------------

    start_position = (
        question_position
        +
        len(matched_phrase)
    )

    remaining_text = text[
        start_position:
    ].strip()

    # -----------------------------------------------------
    # Find next numbered question
    # -----------------------------------------------------

    next_question_pattern = re.compile(
        r"\s+\d{1,3}\.\s+"
    )

    next_match = next_question_pattern.search(
        remaining_text
    )

    if next_match:

        answer = remaining_text[
            :next_match.start()
        ].strip()

    else:

        answer = remaining_text.strip()

    # -----------------------------------------------------
    # Remove unwanted headings
    # -----------------------------------------------------

    answer = re.sub(
        r"\s+Unit[- ]?\d+.*$",
        "",
        answer,
        flags=re.IGNORECASE
    )

    # -----------------------------------------------------
    # Remove image captions
    # -----------------------------------------------------

    answer = re.sub(
        r"\s+(Electrical Network|"
        r"Loop of a Network|"
        r"Ideal Voltage source|"
        r"Practical Voltage Sources)"
        r"\s*$",
        "",
        answer,
        flags=re.IGNORECASE
    )

    # -----------------------------------------------------
    # Clean answer
    # -----------------------------------------------------

    answer = clean_text(answer)

    # -----------------------------------------------------
    # Reject if another question
    # -----------------------------------------------------

    if re.match(
        r"^\d+\.\s*",
        answer
    ):
        return None

    if len(answer) < 10:
        return None

    return answer


# =========================================================
# TF-IDF PDF FALLBACK
# =========================================================

def get_tfidf_answer(question):

    global pdf_text

    if not pdf_text:
        return None

    text = clean_text(pdf_text)

    # -----------------------------------------------------
    # Split into sentences
    # -----------------------------------------------------

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
            [question] + sentences
        )

        question_vector = vectors[0]

        sentence_vectors = vectors[1:]

        similarities = cosine_similarity(
            question_vector,
            sentence_vectors
        )[0]

        ranked = sorted(
            range(len(sentences)),
            key=lambda i: similarities[i],
            reverse=True
        )

        best_index = ranked[0]

        best_score = similarities[
            best_index
        ]

        if best_score < 0.18:
            return None

        answer = sentences[
            best_index
        ]

        return answer.strip()

    except Exception:

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

    # -----------------------------------------------------
    # FIRST: Direct question-answer matching
    # -----------------------------------------------------

    direct_answer = find_direct_answer(
        question
    )

    if direct_answer:

        return direct_answer

    # -----------------------------------------------------
    # SECOND: TF-IDF
    # -----------------------------------------------------

    fallback_answer = get_tfidf_answer(
        question
    )

    if fallback_answer:

        return fallback_answer

    # -----------------------------------------------------
    # NOTHING FOUND
    # -----------------------------------------------------

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

        return jsonify({
            "answer":
                "❌ Error: "
                + str(e)
        })


# =========================================================
# INTERNET SEARCH
# =========================================================

def search_internet(query):

    headers = {

        "User-Agent":
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36",

        "Accept-Language":
            "en-US,en;q=0.9",

        "Accept":
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
    }

    # =====================================================
    # METHOD 1
    # DuckDuckGo Instant Answer API
    # =====================================================

    try:

        api_url = (
            "https://api.duckduckgo.com/?q="
            + quote(query)
            + "&format=json"
            + "&no_html=1"
            + "&skip_disambig=0"
        )

        response = requests.get(
            api_url,
            headers=headers,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        results = []

        # -------------------------------------------------
        # Main result
        # -------------------------------------------------

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
            ""
        )

        if (
            abstract
            and
            abstract_url
            and
            "wikipedia.org"
            not in
            abstract_url.lower()
        ):

            results.append({
                "title":
                    heading
                    if heading
                    else "DuckDuckGo Result",

                "snippet":
                    abstract,

                "url":
                    abstract_url
            })

        # -------------------------------------------------
        # Related Topics
        # -------------------------------------------------

        def extract_topics(topics):

            for topic in topics:

                if not isinstance(
                    topic,
                    dict
                ):
                    continue

                # Nested topics

                if "Topics" in topic:

                    extract_topics(
                        topic.get(
                            "Topics",
                            []
                        )
                    )

                    continue

                text = topic.get(
                    "Text",
                    ""
                )

                first_url = topic.get(
                    "FirstURL",
                    ""
                )

                if not text:
                    continue

                if not first_url:
                    continue

                # Never include Wikipedia

                if (
                    "wikipedia.org"
                    in
                    first_url.lower()
                ):
                    continue

                results.append({
                    "title":
                        text.split(
                            " - "
                        )[0],

                    "snippet":
                        text,

                    "url":
                        first_url
                })

        extract_topics(
            data.get(
                "RelatedTopics",
                []
            )
        )

        if results:

            return results[:8]

    except Exception as e:

        print(
            "DuckDuckGo API error:",
            str(e)
        )


    # =====================================================
    # METHOD 2
    # DuckDuckGo Lite
    # =====================================================

    search_urls = [

        "https://lite.duckduckgo.com/lite/?q=",

        "https://html.duckduckgo.com/html/?q="
    ]

    queries = [

        query,

        query
        +
        " communication systems"
    ]

    for search_base in search_urls:

        for search_query in queries:

            try:

                url = (
                    search_base
                    +
                    quote(search_query)
                )

                response = requests.get(
                    url,
                    headers=headers,
                    timeout=20
                )

                response.raise_for_status()

                soup = BeautifulSoup(
                    response.text,
                    "html.parser"
                )

                results = []

                # =================================================
                # DuckDuckGo Lite
                # =================================================

                links = soup.select(
                    "a.result-link"
                )

                for link_element in links:

                    title = link_element.get_text(
                        " ",
                        strip=True
                    )

                    link = link_element.get(
                        "href",
                        ""
                    )

                    if not title:
                        continue

                    if not link:
                        continue

                    # Never include Wikipedia

                    if (
                        "wikipedia.org"
                        in
                        link.lower()
                    ):
                        continue

                    # Convert relative URL

                    if link.startswith("/"):

                        link = urljoin(
                            "https://lite.duckduckgo.com",
                            link
                        )

                    snippet = ""

                    # Find result row

                    container = (
                        link_element.find_parent(
                            "tr"
                        )
                    )

                    if container:

                        snippet_element = (
                            container.select_one(
                                ".result-snippet"
                            )
                        )

                        if snippet_element:

                            snippet = (
                                snippet_element.get_text(
                                    " ",
                                    strip=True
                                )
                            )

                    # Fallback text

                    if (
                        not snippet
                        and
                        container
                    ):

                        text = container.get_text(
                            " ",
                            strip=True
                        )

                        text = re.sub(
                            r"\s+",
                            " ",
                            text
                        )

                        if title in text:

                            snippet = text.replace(
                                title,
                                "",
                                1
                            ).strip()

                    if not snippet:
                        continue

                    results.append({
                        "title": title,
                        "snippet": snippet,
                        "url": link
                    })

                    if len(results) >= 8:
                        break

                if results:

                    return results[:8]

                # =================================================
                # Normal DuckDuckGo HTML fallback
                # =================================================

                for result in soup.select(
                    ".result"
                ):

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

                    link = link_element.get(
                        "href",
                        ""
                    )

                    if not link:
                        continue

                    snippet = ""

                    if snippet_element:

                        snippet = (
                            snippet_element.get_text(
                                " ",
                                strip=True
                            )
                        )

                    if (
                        "wikipedia.org"
                        in
                        link.lower()
                    ):
                        continue

                    if link.startswith("/"):

                        link = urljoin(
                            search_base,
                            link
                        )

                    if not snippet:
                        continue

                    results.append({
                        "title": title,
                        "snippet": snippet,
                        "url": link
                    })

                    if len(results) >= 8:
                        break

                if results:

                    return results[:8]

            except Exception as e:

                print(
                    "DuckDuckGo search attempt failed:",
                    str(e)
                )

                continue

    # =====================================================
    # NO RESULTS
    # =====================================================

    print(
        "All Internet search attempts failed."
    )

    return []


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
            result["title"]
            +
            " "
            +
            result["snippet"]
        )

    try:

        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2)
        )

        vectors = vectorizer.fit_transform(
            [question] + documents
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

        for index in ranked_indexes[:3]:

            selected.append(
                results[index]
            )

        return selected

    except Exception:

        return results[:3]


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

        if not results:

            return jsonify({
                "answer":
                    "❌ I could not find suitable "
                    "information on the Internet."
            })

        # -------------------------------------------------
        # Select essential results
        # -------------------------------------------------

        selected_results = (
            get_essential_information(
                question,
                results
            )
        )

        answer_parts = []

        for result in selected_results:

            snippet = result[
                "snippet"
            ].strip()

            if snippet:

                answer_parts.append(
                    snippet
                )

        if not answer_parts:

            return jsonify({
                "answer":
                    "❌ No useful information was found."
            })

        # -------------------------------------------------
        # Remove duplicate answers
        # -------------------------------------------------

        unique_parts = []

        for part in answer_parts:

            if part not in unique_parts:

                unique_parts.append(
                    part
                )

        # -------------------------------------------------
        # Create answer
        # -------------------------------------------------

        answer = (
            "📌 <b>Essential information:</b>"
            "<br><br>"
            +
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

            title = result[
                "title"
            ]

            url = result[
                "url"
            ]

            answer += (
                f'<br>• '
                f'<a href="{url}" '
                f'target="_blank">'
                f'{title}'
                f'</a>'
            )

        return jsonify({
            "answer": answer
        })

    except Exception as e:

        print(
            "Internet endpoint error:",
            str(e)
        )

        return jsonify({
            "answer":
                "❌ Internet search error: "
                +
                str(e)
        })


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=False
    )