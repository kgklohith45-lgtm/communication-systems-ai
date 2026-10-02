```python
from flask import Flask, render_template, request, jsonify
import fitz
import os
import re
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin, unquote

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)


# ============================================================
# GEMINI CONFIGURATION
# ============================================================

try:
    from google import genai
except ImportError:
    genai = None


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.8-flash"

gemini_client = None

if genai and GEMINI_API_KEY:

    try:
        gemini_client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        print("===================================")
        print("Gemini client initialized.")
        print("===================================")

    except Exception as e:

        print("Gemini initialization error:", repr(e))

else:

    print("===================================")
    print("Gemini client NOT initialized.")
    print("Check GEMINI_API_KEY.")
    print("===================================")


# ============================================================
# GLOBAL PDF VARIABLES
# ============================================================

pdf_text = ""
pdf_filename = ""


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template("index.html")


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "ok",
        "gemini": bool(gemini_client)
    })


# ============================================================
# GEMINI FUNCTION
# ============================================================

def ask_gemini(prompt):

    if not gemini_client:

        print("Gemini client is not initialized.")

        return None

    try:

        print("Sending request to Gemini...")

        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        if response and response.text:

            print("Gemini response received.")

            return response.text.strip()

        print("Gemini returned an empty response.")

        return None

    except Exception as e:

        print("GEMINI API ERROR:")
        print(repr(e))

        return None


# ============================================================
# REMOVE WIKIPEDIA
# ============================================================

def is_wikipedia(url):

    if not url:
        return False

    return "wikipedia.org" in url.lower()


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# DUCKDUCKGO REDIRECT URL DECODER
# ============================================================

def decode_ddg_url(url):

    if not url:
        return ""

    try:

        if url.startswith("//"):
            url = "https:" + url

        if "uddg=" in url:

            part = url.split("uddg=", 1)[1]

            if "&" in part:
                part = part.split("&", 1)[0]

            return unquote(part)

        return url

    except Exception:

        return url


# ============================================================
# DUCKDUCKGO INSTANT ANSWER API
#
# NOTE:
# This is a fallback.
# It does NOT provide the complete DuckDuckGo search engine.
# It provides instant-answer/topic information.
# ============================================================

def search_duckduckgo_api(query):

    print("-----------------------------------")
    print("DuckDuckGo API search:", query)

    try:

        api_url = "https://api.duckduckgo.com/"

        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "0",
            "no_redirect": "1"
        }

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json"
        }

        response = requests.get(
            api_url,
            params=params,
            headers=headers,
            timeout=20
        )

        print(
            "DuckDuckGo API HTTP status:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                "DuckDuckGo API failed:",
                response.text[:300]
            )

            return []

        data = response.json()

        results = []

        # ----------------------------------------------------
        # Main abstract
        # ----------------------------------------------------

        abstract = clean_text(
            data.get("AbstractText", "")
        )

        abstract_url = data.get(
            "AbstractURL",
            ""
        )

        heading = clean_text(
            data.get("Heading", "")
        )

        if abstract:

            if abstract_url and not is_wikipedia(
                abstract_url
            ):

                results.append({
                    "title": heading or query,
                    "snippet": abstract,
                    "link": abstract_url,
                    "source": "DuckDuckGo"
                })

            elif not abstract_url:

                results.append({
                    "title": heading or query,
                    "snippet": abstract,
                    "link": "",
                    "source": "DuckDuckGo"
                })

        # ----------------------------------------------------
        # Related topics
        # ----------------------------------------------------

        def extract_related_topics(topics):

            extracted = []

            for item in topics:

                if not isinstance(item, dict):
                    continue

                # Nested topic group
                if "Topics" in item:

                    extracted.extend(
                        extract_related_topics(
                            item.get("Topics", [])
                        )
                    )

                    continue

                text = clean_text(
                    item.get("Text", "")
                )

                first_url = item.get(
                    "FirstURL",
                    ""
                )

                if not text:
                    continue

                if first_url and is_wikipedia(
                    first_url
                ):
                    continue

                extracted.append({
                    "title": text[:120],
                    "snippet": text,
                    "link": first_url,
                    "source": "DuckDuckGo"
                })

            return extracted

        related = extract_related_topics(
            data.get("RelatedTopics", [])
        )

        for item in related:

            duplicate = False

            for existing in results:

                if (
                    existing["snippet"].lower()
                    == item["snippet"].lower()
                ):

                    duplicate = True
                    break

            if not duplicate:

                results.append(item)

            if len(results) >= 8:
                break

        print(
            "DuckDuckGo API results:",
            len(results)
        )

        return results[:8]

    except Exception as e:

        print(
            "DuckDuckGo API ERROR:",
            repr(e)
        )

        return []


# ============================================================
# DUCKDUCKGO HTML SEARCH
# ============================================================

def search_duckduckgo_html(query):

    print("-----------------------------------")
    print("DuckDuckGo HTML search:", query)

    urls = [

        "https://html.duckduckgo.com/html/?q="
        + quote(query),

        "https://lite.duckduckgo.com/lite/?q="
        + quote(query)

    ]

    headers_list = [

        {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://duckduckgo.com/"
        },

        {
            "User-Agent":
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36",
            "Accept": "text/html"
        }

    ]

    results = []

    for index, url in enumerate(urls):

        try:

            headers = headers_list[
                min(index, len(headers_list) - 1)
            ]

            response = requests.get(
                url,
                headers=headers,
                timeout=20,
                allow_redirects=True
            )

            print(
                "DuckDuckGo HTML status:",
                response.status_code
            )

            # ------------------------------------------------
            # DuckDuckGo may return 202.
            # Wait briefly and try once more.
            # ------------------------------------------------

            if response.status_code == 202:

                print(
                    "DuckDuckGo returned 202."
                )

                time.sleep(2)

                response = requests.get(
                    url,
                    headers=headers,
                    timeout=20,
                    allow_redirects=True
                )

                print(
                    "DuckDuckGo retry status:",
                    response.status_code
                )

            if response.status_code != 200:

                continue

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            # ------------------------------------------------
            # Standard DDG result blocks
            # ------------------------------------------------

            blocks = soup.select(
                ".result"
            )

            print(
                "DuckDuckGo result blocks:",
                len(blocks)
            )

            for result in blocks:

                title_element = result.select_one(
                    ".result__title"
                )

                link_element = result.select_one(
                    ".result__a"
                )

                snippet_element = result.select_one(
                    ".result__snippet"
                )

                if not title_element:
                    continue

                title = clean_text(
                    title_element.get_text(
                        " ",
                        strip=True
                    )
                )

                link = ""

                if link_element:

                    link = link_element.get(
                        "href",
                        ""
                    )

                    link = decode_ddg_url(
                        link
                    )

                snippet = ""

                if snippet_element:

                    snippet = clean_text(
                        snippet_element.get_text(
                            " ",
                            strip=True
                        )
                    )

                if not title and not snippet:
                    continue

                if is_wikipedia(link):
                    continue

                results.append({
                    "title": title,
                    "snippet": snippet,
                    "link": link,
                    "source": "DuckDuckGo"
                })

                if len(results) >= 8:
                    break

            # ------------------------------------------------
            # Alternative selector
            # ------------------------------------------------

            if not results:

                links = soup.select(
                    "a.result__a"
                )

                print(
                    "Alternative DDG links:",
                    len(links)
                )

                for link_element in links:

                    title = clean_text(
                        link_element.get_text(
                            " ",
                            strip=True
                        )
                    )

                    link = decode_ddg_url(
                        link_element.get(
                            "href",
                            ""
                        )
                    )

                    if not title:
                        continue

                    if is_wikipedia(link):
                        continue

                    results.append({
                        "title": title,
                        "snippet": title,
                        "link": link,
                        "source": "DuckDuckGo"
                    })

                    if len(results) >= 8:
                        break

            if results:

                break

        except Exception as e:

            print(
                "DuckDuckGo HTML error:",
                repr(e)
            )

    return results[:8]


# ============================================================
# MAIN DUCKDUCKGO SEARCH
# ============================================================

def search_internet(query):

    query = clean_text(query)

    if not query:

        return []

    print("")
    print("===================================")
    print("SEARCHING DUCKDUCKGO")
    print("Question:", query)
    print("===================================")

    all_results = []

    # --------------------------------------------------------
    # Search queries
    # --------------------------------------------------------

    search_queries = [

        query,

        query + " communication systems",

        query + " engineering"

    ]

    # --------------------------------------------------------
    # First attempt: DuckDuckGo HTML
    # --------------------------------------------------------

    for search_query in search_queries:

        html_results = search_duckduckgo_html(
            search_query
        )

        for result in html_results:

            if not is_wikipedia(
                result.get("link", "")
            ):

                all_results.append(result)

        if len(all_results) >= 8:
            break

    # --------------------------------------------------------
    # Remove duplicate HTML results
    # --------------------------------------------------------

    unique_results = []

    seen_links = set()
    seen_text = set()

    for result in all_results:

        link = result.get(
            "link",
            ""
        )

        text = result.get(
            "snippet",
            ""
        )

        key = (
            link.lower().strip()
            if link
            else text.lower().strip()
        )

        if not key:
            continue

        if key in seen_links or key in seen_text:
            continue

        seen_links.add(key)
        seen_text.add(key)

        unique_results.append(result)

    all_results = unique_results

    print(
        "HTML search total:",
        len(all_results)
    )

    # --------------------------------------------------------
    # FALLBACK:
    # DuckDuckGo Instant Answer API
    # --------------------------------------------------------

    if len(all_results) == 0:

        print("")
        print(
            "HTML search returned no results."
        )

        print(
            "Trying DuckDuckGo Instant Answer API..."
        )

        for search_query in search_queries:

            api_results = search_duckduckgo_api(
                search_query
            )

            for result in api_results:

                link = result.get(
                    "link",
                    ""
                )

                snippet = result.get(
                    "snippet",
                    ""
                )

                if is_wikipedia(link):
                    continue

                duplicate = False

                for existing in all_results:

                    if (
                        existing.get(
                            "snippet",
                            ""
                        ).lower()
                        == snippet.lower()
                    ):

                        duplicate = True
                        break

                if not duplicate:

                    all_results.append(
                        result
                    )

                if len(all_results) >= 8:
                    break

            if len(all_results) >= 8:
                break

    # --------------------------------------------------------
    # Final cleanup
    # --------------------------------------------------------

    final_results = []

    seen = set()

    for result in all_results:

        title = clean_text(
            result.get("title", "")
        )

        snippet = clean_text(
            result.get("snippet", "")
        )

        link = result.get(
            "link",
            ""
        )

        if is_wikipedia(link):
            continue

        if not title and not snippet:
            continue

        key = (
            title.lower()
            + "|"
            + snippet.lower()
        )

        if key in seen:
            continue

        seen.add(key)

        final_results.append({
            "title": title or query,
            "snippet": snippet,
            "link": link,
            "source": "DuckDuckGo"
        })

        if len(final_results) >= 8:
            break

    print("")
    print(
        "FINAL DUCKDUCKGO RESULTS:",
        len(final_results)
    )

    for number, result in enumerate(
        final_results,
        start=1
    ):

        print(
            number,
            "-",
            result["title"]
        )

    print("===================================")
    print("")

    return final_results


# ============================================================
# RANK SEARCH RESULTS
# ============================================================

def rank_search_results(
    query,
    results
):

    if not results:

        return []

    documents = []

    for result in results:

        text = (
            result.get("title", "")
            + " "
            + result.get("snippet", "")
        )

        documents.append(text)

    try:

        vectorizer = TfidfVectorizer(
            stop_words="english"
        )

        matrix = vectorizer.fit_transform(
            [query] + documents
        )

        scores = cosine_similarity(
            matrix[0:1],
            matrix[1:]
        )[0]

        ranked = []

        for index, score in enumerate(scores):

            item = dict(
                results[index]
            )

            item["score"] = float(score)

            ranked.append(item)

        ranked.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        return ranked

    except Exception as e:

        print(
            "Ranking error:",
            repr(e)
        )

        return results


# ============================================================
# FORMAT SEARCH INFORMATION FOR GEMINI
# ============================================================

def build_search_context(
    results
):

    context_parts = []

    for index, result in enumerate(
        results,
        start=1
    ):

        title = result.get(
            "title",
            ""
        )

        snippet = result.get(
            "snippet",
            ""
        )

        link = result.get(
            "link",
            ""
        )

        context_parts.append(
            f"""
SOURCE {index}
Title: {title}
Information: {snippet}
URL: {link}
""".strip()
        )

    return "\n\n".join(
        context_parts
    )


# ============================================================
# GEMINI INTERNET ANSWER
# ============================================================

def generate_internet_answer(
    question,
    results
):

    if not results:

        return None

    context = build_search_context(
        results
    )

    prompt = f"""
You are an AI assistant for a Communication Systems
and Computer Networks educational application.

User question:
{question}

Use ONLY the information provided in the search results
below.

SEARCH RESULTS:
{context}

Instructions:

1. Answer the user's question directly.
2. Keep the answer concise but useful.
3. Focus only on information relevant to the question.
4. Do not mention information that is not supported by
   the supplied search results.
5. Do not use Wikipedia.
6. Break the answer into clear subdivisions.
7. Use headings where useful.
8. Use bullet points for explanations.
9. If a formula is relevant, write it clearly.
10. Do not write one large paragraph.
11. Do not invent facts.
12. Do not say that you searched Google.
13. Do not include a separate bibliography.
14. Do not include raw URLs in the answer.
15. The application will display the source links separately.

Answer:
"""

    return ask_gemini(
        prompt
    )


# ============================================================
# PDF TEXT EXTRACTION
# ============================================================

def extract_pdf_text(
    filepath
):

    try:

        document = fitz.open(
            filepath
        )

        pages = []

        for page in document:

            text = page.get_text(
                "text"
            )

            if text:

                pages.append(
                    text
                )

        document.close()

        return "\n".join(
            pages
        ).strip()

    except Exception as e:

        print(
            "PDF extraction error:",
            repr(e)
        )

        return ""


# ============================================================
# PDF ANSWER
# ============================================================

def answer_from_pdf(
    question,
    text
):

    if not text.strip():

        return (
            "This information was not found "
            "in the uploaded PDF."
        )

    # --------------------------------------------------------
    # Split PDF into chunks
    # --------------------------------------------------------

    paragraphs = re.split(
        r"\n\s*\n",
        text
    )

    paragraphs = [
        clean_text(p)
        for p in paragraphs
        if clean_text(p)
    ]

    if not paragraphs:

        paragraphs = [
            clean_text(text)
        ]

    # --------------------------------------------------------
    # Exact keyword matching first
    # --------------------------------------------------------

    question_words = re.findall(
        r"\b[a-zA-Z0-9]{3,}\b",
        question.lower()
    )

    stop_words = {
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "how",
        "does",
        "can",
        "are",
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "about",
        "explain",
        "define",
        "give",
        "tell"
    }

    keywords = [
        word
        for word in question_words
        if word not in stop_words
    ]

    direct_matches = []

    for paragraph in paragraphs:

        lower = paragraph.lower()

        matches = sum(
            1
            for keyword in keywords
            if keyword in lower
        )

        if matches > 0:

            direct_matches.append(
                (
                    matches,
                    paragraph
                )
            )

    direct_matches.sort(
        key=lambda x: x[0],
        reverse=True
    )

    # --------------------------------------------------------
    # TF-IDF fallback
    # --------------------------------------------------------

    selected = []

    if direct_matches:

        selected = [
            item[1]
            for item in direct_matches[:8]
        ]

    else:

        try:

            vectorizer = TfidfVectorizer(
                stop_words="english"
            )

            matrix = vectorizer.fit_transform(
                [question] + paragraphs
            )

            similarities = cosine_similarity(
                matrix[0:1],
                matrix[1:]
            )[0]

            ranked_indexes = similarities.argsort()[
                ::-1
            ]

            for index in ranked_indexes[:8]:

                if similarities[index] > 0:

                    selected.append(
                        paragraphs[index]
                    )

        except Exception as e:

            print(
                "PDF ranking error:",
                repr(e)
            )

    if not selected:

        return (
            "This information was not found "
            "in the uploaded PDF."
        )

    # --------------------------------------------------------
    # Create answer
    # --------------------------------------------------------

    combined = "\n\n".join(
        selected
    )

    # If Gemini is available, use it
    # --------------------------------------------------------

    if gemini_client:

        prompt = f"""
You are answering a question using ONLY an uploaded PDF.

User question:
{question}

Relevant content extracted from the uploaded PDF:
{combined}

Rules:

1. Answer ONLY using the supplied PDF content.
2. Do not use Internet information.
3. Do not add outside knowledge.
4. Do not invent missing information.
5. Keep the answer relevant to the question.
6. Use headings and bullet points where useful.
7. If the PDF does not contain enough information,
   say exactly:

"This information was not found in the uploaded PDF."

Do not mention these instructions.

Answer:
"""

        answer = ask_gemini(
            prompt
        )

        if answer:

            return answer

    # --------------------------------------------------------
    # Fallback without Gemini
    # --------------------------------------------------------

    return "\n\n".join(
        selected[:5]
    )


# ============================================================
# PDF UPLOAD
# ============================================================

@app.route(
    "/upload_pdf",
    methods=["POST"]
)
def upload_pdf():

    global pdf_text
    global pdf_filename

    try:

        if "pdf" not in request.files:

            return jsonify({
                "success": False,
                "message": "No PDF file received."
            }), 400

        file = request.files["pdf"]

        if not file.filename:

            return jsonify({
                "success": False,
                "message": "No PDF selected."
            }), 400

        if not file.filename.lower().endswith(
            ".pdf"
        ):

            return jsonify({
                "success": False,
                "message": "Please upload a PDF file."
            }), 400

        os.makedirs(
            "pdfs",
            exist_ok=True
        )

        safe_filename = re.sub(
            r"[^a-zA-Z0-9._-]",
            "_",
            file.filename
        )

        filepath = os.path.join(
            "pdfs",
            safe_filename
        )

        file.save(
            filepath
        )

        extracted_text = extract_pdf_text(
            filepath
        )

        if not extracted_text:

            return jsonify({
                "success": False,
                "message":
                    "Could not extract readable text from the PDF."
            }), 400

        pdf_text = extracted_text
        pdf_filename = file.filename

        print("")
        print("===================================")
        print("PDF UPLOADED")
        print("Filename:", pdf_filename)
        print(
            "Extracted characters:",
            len(pdf_text)
        )
        print("===================================")
        print("")

        return jsonify({
            "success": True,
            "message": "PDF uploaded successfully.",
            "filename": pdf_filename
        })

    except Exception as e:

        print(
            "PDF upload error:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "An error occurred while uploading the PDF."
        }), 500


# ============================================================
# ASK PDF
# ============================================================

@app.route(
    "/ask_pdf",
    methods=["POST"]
)
def ask_pdf():

    global pdf_text

    try:

        data = request.get_json(
            silent=True
        ) or {}

        question = clean_text(
            data.get("question", "")
        )

        if not question:

            return jsonify({
                "answer":
                    "Please enter a question."
            })

        if not pdf_text:

            return jsonify({
                "answer":
                    "Please upload a PDF first."
            })

        print("")
        print("===================================")
        print("PDF QUESTION:")
        print(question)
        print("===================================")

        answer = answer_from_pdf(
            question,
            pdf_text
        )

        return jsonify({
            "answer": answer,
            "filename": pdf_filename
        })

    except Exception as e:

        print(
            "PDF question error:",
            repr(e)
        )

        return jsonify({
            "answer":
                "An error occurred while processing the PDF question."
        }), 500


# ============================================================
# ASK INTERNET
# ============================================================

@app.route(
    "/ask_internet",
    methods=["POST"]
)
def ask_internet():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        question = clean_text(
            data.get("question", "")
        )

        if not question:

            return jsonify({
                "answer":
                    "Please enter a question.",
                "sources": []
            })

        print("")
        print("===================================")
        print("INTERNET QUESTION:")
        print(question)
        print("===================================")

        # ----------------------------------------------------
        # Search DuckDuckGo
        # ----------------------------------------------------

        results = search_internet(
            question
        )

        print(
            "Total Internet results:",
            len(results)
        )

        # ----------------------------------------------------
        # No results
        # ----------------------------------------------------

        if not results:

            print(
                "DuckDuckGo results: 0"
            )

            return jsonify({
                "answer":
                    "❌ Internet search did not return any results. "
                    "Please try another question.",
                "sources": []
            })

        # ----------------------------------------------------
        # Rank results
        # ----------------------------------------------------

        ranked_results = rank_search_results(
            question,
            results
        )

        # ----------------------------------------------------
        # Keep relevant results
        # ----------------------------------------------------

        selected_results = ranked_results[:6]

        print(
            "Selected results:",
            len(selected_results)
        )

        # ----------------------------------------------------
        # Gemini answer
        # ----------------------------------------------------

        answer = generate_internet_answer(
            question,
            selected_results
        )

        # ----------------------------------------------------
        # Gemini unavailable
        # ----------------------------------------------------

        if not answer:

            print(
                "Gemini did not return an answer."
            )

            # Build a simple fallback answer
            fallback_parts = []

            for result in selected_results:

                title = result.get(
                    "title",
                    ""
                )

                snippet = result.get(
                    "snippet",
                    ""
                )

                if snippet:

                    fallback_parts.append(
                        f"### {title}\n\n"
                        f"{snippet}"
                    )

            answer = "\n\n".join(
                fallback_parts
            )

        # ----------------------------------------------------
        # Sources
        # ----------------------------------------------------

        sources = []

        for result in selected_results:

            link = result.get(
                "link",
                ""
            )

            title = result.get(
                "title",
                "Source"
            )

            if not link:
                continue

            if is_wikipedia(link):
                continue

            sources.append({
                "title": title,
                "url": link
            })

        print(
            "Sources returned:",
            len(sources)
        )

        print("===================================")
        print("")

        return jsonify({
            "answer": answer,
            "sources": sources
        })

    except Exception as e:

        print(
            "Internet question error:",
            repr(e)
        )

        return jsonify({
            "answer":
                "❌ An error occurred while searching the Internet.",
            "sources": []
        }), 500


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return jsonify({
        "error": "Page not found."
    }), 404


@app.errorhandler(500)
def internal_server_error(error):

    return jsonify({
        "error": "Internal server error."
    }), 500


# ============================================================
# RUN APPLICATION
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
```
