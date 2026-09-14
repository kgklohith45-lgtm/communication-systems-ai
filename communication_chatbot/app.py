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

    try:

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

        # Open PDF
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
                "message":
                    "Could not extract text from this PDF."
            })

        return jsonify({
            "success": True,
            "message":
                "PDF uploaded successfully: "
                + pdf_filename
        })

    except Exception as e:

        print(
            "PDF upload error:",
            str(e)
        )

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

    text = clean_text(
        pdf_text
    )

    question = clean_text(
        question
    )

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

    normalized_text = normalize(
        text
    )

    normalized_question = normalize(
        question
    )

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
    # Create possible search phrases
    # -----------------------------------------------------

    possible_phrases = [
        normalized_question,
        search_question
    ]

    possible_phrases = list(
        dict.fromkeys(
            [
                phrase
                for phrase in possible_phrases
                if len(phrase) > 3
            ]
        )
    )

    question_position = -1
    matched_phrase = ""

    # -----------------------------------------------------
    # Find question in PDF
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

    # -----------------------------------------------------
    # Remove unwanted trailing headings
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

    answer = clean_text(
        answer
    )

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

    text = clean_text(
        pdf_text
    )

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

        answer = sentences[
            best_index
        ]

        return answer.strip()

    except Exception as e:

        print(
            "TF-IDF error:",
            str(e)
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

    # -----------------------------------------------------
    # FIRST - Direct answer
    # -----------------------------------------------------

    direct_answer = find_direct_answer(
        question
    )

    if direct_answer:

        return direct_answer

    # -----------------------------------------------------
    # SECOND - TF-IDF
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

        data = request.get_json(
            silent=True
        )

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
            str(e)
        )

        return jsonify({
            "answer":
                "❌ Error: "
                + str(e)
        })


# =========================================================
# INTERNET SEARCH
# =========================================================

def search_internet(query):

    # -----------------------------------------------------
    # Browser headers
    # -----------------------------------------------------

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

        print(
            "Trying DuckDuckGo API for:",
            query
        )

        api_url = (
            "https://api.duckduckgo.com/"
            "?q="
            + quote(query)
            + "&format=json"
            + "&no_html=1"
            + "&skip_disambig=0"
        )

        response = requests.get(
            api_url,
            headers=headers,
            timeout=6
        )

        print(
            "DuckDuckGo API status:",
            response.status_code
        )

        # -------------------------------------------------
        # Check that response is JSON
        # -------------------------------------------------

        content_type = (
            response.headers.get(
                "Content-Type",
                ""
            ).lower()
        )

        if "json" in content_type:

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
                and abstract_url
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
            # Related topics
            # -------------------------------------------------

            def collect_topics(topics):

                for topic in topics:

                    if not isinstance(
                        topic,
                        dict
                    ):
                        continue

                    # Nested topic group

                    if "Topics" in topic:

                        collect_topics(
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

            collect_topics(
                data.get(
                    "RelatedTopics",
                    []
                )
            )

            # -------------------------------------------------
            # Remove duplicate URLs
            # -------------------------------------------------

            unique_results = []

            seen_urls = set()

            for result in results:

                url = result["url"]

                if url in seen_urls:

                    continue

                seen_urls.add(url)

                unique_results.append(
                    result
                )

            if unique_results:

                print(
                    "DuckDuckGo API found",
                    len(unique_results),
                    "results"
                )

                return unique_results[:8]

        else:

            print(
                "DuckDuckGo API returned non-JSON."
            )

    except requests.exceptions.Timeout:

        print(
            "DuckDuckGo API timed out."
        )

    except requests.exceptions.RequestException as e:

        print(
            "DuckDuckGo API request error:",
            str(e)
        )

    except Exception as e:

        print(
            "DuckDuckGo API error:",
            str(e)
        )


    # =====================================================
    # METHOD 2
    # DuckDuckGo Lite
    # =====================================================

    try:

        print(
            "Trying DuckDuckGo Lite..."
        )

        search_query = (
            query
            +
            " communication systems"
        )

        lite_url = (
            "https://lite.duckduckgo.com/lite/?q="
            +
            quote(search_query)
        )

        response = requests.get(
            lite_url,
            headers=headers,
            timeout=6
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

        results = []

        # -------------------------------------------------
        # Search result links
        # -------------------------------------------------

        for link_element in soup.select(
            "a.result-link"
        ):

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

            # Convert relative URLs

            if link.startswith("/"):

                link = urljoin(
                    "https://lite.duckduckgo.com",
                    link
                )

            snippet = ""

            # -------------------------------------------------
            # Find result row
            # -------------------------------------------------

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

            # -------------------------------------------------
            # Fallback snippet extraction
            # -------------------------------------------------

            if (
                not snippet
                and
                container
            ):

                row_text = (
                    container.get_text(
                        " ",
                        strip=True
                    )
                )

                row_text = re.sub(
                    r"\s+",
                    " ",
                    row_text
                )

                if title in row_text:

                    snippet = row_text.replace(
                        title,
                        "",
                        1
                    ).strip()

            if not snippet:

                continue

            results.append({

                "title":
                    title,

                "snippet":
                    snippet,

                "url":
                    link
            })

            if len(results) >= 8:

                break

        if results:

            print(
                "DuckDuckGo Lite found",
                len(results),
                "results"
            )

            return results[:8]

    except requests.exceptions.Timeout:

        print(
            "DuckDuckGo Lite timed out."
        )

    except requests.exceptions.RequestException as e:

        print(
            "DuckDuckGo Lite request error:",
            str(e)
        )

    except Exception as e:

        print(
            "DuckDuckGo Lite error:",
            str(e)
        )


    # =====================================================
    # METHOD 3
    # DuckDuckGo HTML
    # =====================================================

    try:

        print(
            "Trying DuckDuckGo HTML fallback..."
        )

        search_query = (
            query
            +
            " communication systems engineering"
        )

        html_url = (
            "https://html.duckduckgo.com/html/?q="
            +
            quote(search_query)
        )

        response = requests.get(
            html_url,
            headers=headers,
            timeout=6
        )

        print(
            "DuckDuckGo HTML status:",
            response.status_code
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        results = []

        # -------------------------------------------------
        # Standard DuckDuckGo results
        # -------------------------------------------------

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

            if not snippet_element:

                continue

            if not link_element:

                continue

            title = (
                title_element.get_text(
                    " ",
                    strip=True
                )
            )

            snippet = (
                snippet_element.get_text(
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

            # Never include Wikipedia

            if (
                "wikipedia.org"
                in
                link.lower()
            ):

                continue

            if link.startswith("/"):

                link = urljoin(
                    "https://html.duckduckgo.com",
                    link
                )

            results.append({

                "title":
                    title,

                "snippet":
                    snippet,

                "url":
                    link
            })

            if len(results) >= 8:

                break

        if results:

            print(
                "DuckDuckGo HTML found",
                len(results),
                "results"
            )

            return results[:8]

    except requests.exceptions.Timeout:

        print(
            "DuckDuckGo HTML timed out."
        )

    except requests.exceptions.RequestException as e:

        print(
            "DuckDuckGo HTML request error:",
            str(e)
        )

    except Exception as e:

        print(
            "DuckDuckGo HTML error:",
            str(e)
        )


    # =====================================================
    # ALL METHODS FAILED
    # =====================================================

    print(
        "All DuckDuckGo search methods failed."
    )

    return []


# =========================================================
# SELECT ESSENTIAL INFORMATION
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

    except Exception as e:

        print(
            "Essential information error:",
            str(e)
        )

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

        data = request.get_json(
            silent=True
        )

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

        print(
            "Internet question:",
            question
        )

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

        if not selected_results:

            return jsonify({
                "answer":
                    "❌ No useful information was found."
            })

        # -------------------------------------------------
        # Build answer
        # -------------------------------------------------

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
        # Remove duplicate snippets
        # -------------------------------------------------

        unique_parts = []

        for part in answer_parts:

            if part not in unique_parts:

                unique_parts.append(
                    part
                )

        # -------------------------------------------------
        # Essential information
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
        # Sources
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

            # Basic HTML escaping
            safe_title = (
                title
                .replace(
                    "&",
                    "&amp;"
                )
                .replace(
                    "<",
                    "&lt;"
                )
                .replace(
                    ">",
                    "&gt;"
                )
                .replace(
                    '"',
                    "&quot;"
                )
            )

            answer += (
                f'<br>• '
                f'<a href="{url}" '
                f'target="_blank">'
                f'{safe_title}'
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