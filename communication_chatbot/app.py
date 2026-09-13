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
# FIND ANSWER FROM QUESTION
# =========================================================

def find_direct_answer(question):

    global pdf_text

    if not pdf_text:
        return None

    text = clean_text(pdf_text)

    question = clean_text(question)

    # -----------------------------------------------------
    # Normalize text for comparison
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
    # Create possible search phrases
    # -----------------------------------------------------

    possible_phrases = [
        normalized_question,
        search_question
    ]

    # Remove duplicates
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

    # -----------------------------------------------------
    # If exact search didn't work,
    # use TF-IDF to find relevant area.
    # -----------------------------------------------------

    if question_position == -1:

        return None

    # -----------------------------------------------------
    # Text after the question
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
    #
    # Examples:
    # 4. Draw...
    # 5. What is...
    # 10. Define...
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

    answer = clean_text(answer)

    # -----------------------------------------------------
    # Reject if it is actually another question
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
# TF-IDF FALLBACK
# =========================================================

def get_tfidf_answer(question):

    global pdf_text

    if not pdf_text:
        return None

    text = clean_text(pdf_text)

    # Split into sentences
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
    # FIRST:
    # Find direct Question → Answer
    # -----------------------------------------------------

    direct_answer = find_direct_answer(
        question
    )

    if direct_answer:

        return direct_answer

    # -----------------------------------------------------
    # SECOND:
    # TF-IDF fallback
    # -----------------------------------------------------

    fallback_answer = get_tfidf_answer(
        question
    )

    if fallback_answer:

        return fallback_answer

    # -----------------------------------------------------
    # Nothing found
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

    try:

        search_query = (
            query
            +
            " communication systems engineering"
        )

        url = (
            "https://html.duckduckgo.com/html/?q="
            +
            quote(search_query)
        )

        headers = {
            "User-Agent":
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        results = []

        for result in soup.select(
            ".result"
        ):

            title_element = result.select_one(
                ".result__title"
            )

            snippet_element = result.select_one(
                ".result__snippet"
            )

            link_element = result.select_one(
                ".result__a"
            )

            if not title_element:
                continue

            if not snippet_element:
                continue

            if not link_element:
                continue

            title = title_element.get_text(
                " ",
                strip=True
            )

            snippet = snippet_element.get_text(
                " ",
                strip=True
            )

            link = link_element.get(
                "href",
                ""
            )

            if not link:
                continue

            if link.startswith("/"):

                link = urljoin(
                    "https://html.duckduckgo.com",
                    link
                )

            # Never include Wikipedia
            if "wikipedia.org" in link.lower():
                continue

            results.append({
                "title": title,
                "snippet": snippet,
                "url": link
            })

            if len(results) >= 8:
                break

        return results

    except Exception as e:

        print(
            "Internet search error:",
            str(e)
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

        results = search_internet(
            question
        )

        if not results:

            return jsonify({
                "answer":
                    "❌ I could not find suitable "
                    "information on the Internet."
            })

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

        unique_parts = []

        for part in answer_parts:

            if part not in unique_parts:

                unique_parts.append(
                    part
                )

        answer = (
            "📌 <b>Essential information:</b>"
            "<br><br>"
            +
            "<br><br>".join(
                unique_parts
            )
        )

        answer += (
            "<br><br>"
            "<b>🔗 Sources:</b>"
            "<br>"
        )

        for result in selected_results:

            title = result["title"]

            url = result["url"]

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
        debug=True
    )