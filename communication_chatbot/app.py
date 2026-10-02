from flask import Flask, render_template, request, jsonify
import fitz
import os
import re
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import quote, unquote

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ============================================================
# FLASK APPLICATION
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

# Keep your configured Gemini model here.
# If your API account uses a different available model,
# change this value.
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

        print("Gemini initialization error:")
        print(repr(e))

else:

    print("===================================")
    print("Gemini client NOT initialized.")
    print("Check GEMINI_API_KEY.")
    print("===================================")


# ============================================================
# PDF GLOBAL VARIABLES
# ============================================================

pdf_text = ""
pdf_filename = ""


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


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
            "Gemini returned an empty response."
        )

        return None

    except Exception as e:

        print(
            "GEMINI API ERROR:"
        )

        print(
            repr(e)
        )

        return None


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):

    if not text:

        return ""

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# WIKIPEDIA FILTER
# ============================================================

def is_wikipedia(url):

    if not url:

        return False

    return (
        "wikipedia.org"
        in url.lower()
    )


# ============================================================
# DUCKDUCKGO URL DECODER
# ============================================================

def decode_ddg_url(url):

    if not url:

        return ""

    try:

        if url.startswith("//"):

            url = "https:" + url

        if "uddg=" in url:

            value = url.split(
                "uddg=",
                1
            )[1]

            if "&" in value:

                value = value.split(
                    "&",
                    1
                )[0]

            return unquote(
                value
            )

        return url

    except Exception:

        return url


# ============================================================
# DUCKDUCKGO HTML SEARCH
# ============================================================

def search_duckduckgo_html(query):

    print("-----------------------------------")
    print(
        "Searching DuckDuckGo:",
        query
    )

    search_urls = [

        "https://html.duckduckgo.com/html/?q="
        + quote(query),

        "https://lite.duckduckgo.com/lite/?q="
        + quote(query)

    ]

    headers = {

        "User-Agent":
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/154.0.0.0 "
            "Safari/537.36",

        "Accept":
            "text/html,"
            "application/xhtml+xml,"
            "application/xml;q=0.9,"
            "*/*;q=0.8",

        "Accept-Language":
            "en-US,en;q=0.9",

        "Referer":
            "https://duckduckgo.com/"

    }

    results = []

    for url in search_urls:

        try:

            response = requests.get(
                url,
                headers=headers,
                timeout=20,
                allow_redirects=True
            )

            print(
                "DuckDuckGo HTTP status:",
                response.status_code
            )

            # ------------------------------------------------
            # HTTP 202 retry
            # ------------------------------------------------

            if response.status_code == 202:

                print(
                    "DuckDuckGo returned HTTP 202."
                )

                print(
                    "Retrying after short delay..."
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

            blocks = soup.select(
                ".result"
            )

            print(
                "DuckDuckGo HTML blocks:",
                len(blocks)
            )

            # ------------------------------------------------
            # Standard DuckDuckGo results
            # ------------------------------------------------

            for block in blocks:

                title_element = (
                    block.select_one(
                        ".result__title"
                    )
                )

                link_element = (
                    block.select_one(
                        ".result__a"
                    )
                )

                snippet_element = (
                    block.select_one(
                        ".result__snippet"
                    )
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

                if is_wikipedia(link):

                    continue

                if not title and not snippet:

                    continue

                results.append({

                    "title":
                        title,

                    "snippet":
                        snippet,

                    "link":
                        link,

                    "source":
                        "DuckDuckGo"

                })

                if len(results) >= 8:

                    break

            if results:

                break

            # ------------------------------------------------
            # Alternative selector
            # ------------------------------------------------

            alternative_links = soup.select(
                "a.result__a"
            )

            print(
                "DuckDuckGo alternative links:",
                len(alternative_links)
            )

            for link_element in alternative_links:

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

                    "title":
                        title,

                    "snippet":
                        title,

                    "link":
                        link,

                    "source":
                        "DuckDuckGo"

                })

                if len(results) >= 8:

                    break

            if results:

                break

        except Exception as e:

            print(
                "DuckDuckGo HTML error:"
            )

            print(
                repr(e)
            )

    return results[:8]


# ============================================================
# DUCKDUCKGO INSTANT ANSWER API
# FALLBACK
# ============================================================

def search_duckduckgo_api(query):

    print("-----------------------------------")

    print(
        "Trying DuckDuckGo API:",
        query
    )

    try:

        api_url = (
            "https://api.duckduckgo.com/"
        )

        params = {

            "q":
                query,

            "format":
                "json",

            "no_html":
                "1",

            "skip_disambig":
                "0",

            "no_redirect":
                "1"

        }

        headers = {

            "User-Agent":
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/154.0.0.0 "
                "Safari/537.36",

            "Accept":
                "application/json"

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
                "DuckDuckGo API failed."
            )

            return []

        data = response.json()

        results = []

        # ----------------------------------------------------
        # Main abstract
        # ----------------------------------------------------

        abstract = clean_text(
            data.get(
                "AbstractText",
                ""
            )
        )

        abstract_url = data.get(
            "AbstractURL",
            ""
        )

        heading = clean_text(
            data.get(
                "Heading",
                ""
            )
        )

        if abstract:

            if not is_wikipedia(
                abstract_url
            ):

                results.append({

                    "title":
                        heading or query,

                    "snippet":
                        abstract,

                    "link":
                        abstract_url,

                    "source":
                        "DuckDuckGo"

                })

        # ----------------------------------------------------
        # Related topics
        # ----------------------------------------------------

        def extract_topics(
            topics
        ):

            output = []

            for topic in topics:

                if not isinstance(
                    topic,
                    dict
                ):

                    continue

                if "Topics" in topic:

                    output.extend(
                        extract_topics(
                            topic.get(
                                "Topics",
                                []
                            )
                        )
                    )

                    continue

                text = clean_text(
                    topic.get(
                        "Text",
                        ""
                    )
                )

                link = topic.get(
                    "FirstURL",
                    ""
                )

                if not text:

                    continue

                if is_wikipedia(
                    link
                ):

                    continue

                output.append({

                    "title":
                        text[:120],

                    "snippet":
                        text,

                    "link":
                        link,

                    "source":
                        "DuckDuckGo"

                })

            return output

        related_topics = extract_topics(
            data.get(
                "RelatedTopics",
                []
            )
        )

        for item in related_topics:

            duplicate = False

            for existing in results:

                if (
                    existing.get(
                        "snippet",
                        ""
                    ).lower()
                    ==
                    item.get(
                        "snippet",
                        ""
                    ).lower()
                ):

                    duplicate = True

                    break

            if not duplicate:

                results.append(
                    item
                )

            if len(results) >= 8:

                break

        print(
            "DuckDuckGo API results:",
            len(results)
        )

        return results[:8]

    except Exception as e:

        print(
            "DuckDuckGo API error:"
        )

        print(
            repr(e)
        )

        return []


# ============================================================
# MAIN INTERNET SEARCH
# ============================================================

def search_internet(query):

    query = clean_text(
        query
    )

    if not query:

        return []

    print("")
    print("===================================")
    print(
        "INTERNET SEARCH:",
        query
    )
    print("===================================")

    search_queries = [

        query,

        query
        + " communication systems",

        query
        + " engineering"

    ]

    all_results = []

    # --------------------------------------------------------
    # STEP 1: HTML SEARCH
    # --------------------------------------------------------

    for search_query in search_queries:

        results = search_duckduckgo_html(
            search_query
        )

        for result in results:

            if not is_wikipedia(
                result.get(
                    "link",
                    ""
                )
            ):

                all_results.append(
                    result
                )

        if len(all_results) >= 8:

            break

    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    unique_results = []

    seen = set()

    for result in all_results:

        link = result.get(
            "link",
            ""
        )

        snippet = result.get(
            "snippet",
            ""
        )

        key = (
            link.lower().strip()
            if link
            else snippet.lower().strip()
        )

        if not key:

            continue

        if key in seen:

            continue

        seen.add(
            key
        )

        unique_results.append(
            result
        )

    all_results = unique_results

    print(
        "HTML search total:",
        len(all_results)
    )

    # --------------------------------------------------------
    # STEP 2: API FALLBACK
    # --------------------------------------------------------

    if not all_results:

        print(
            "HTML search returned no results."
        )

        print(
            "Trying DuckDuckGo API fallback..."
        )

        for search_query in search_queries:

            api_results = (
                search_duckduckgo_api(
                    search_query
                )
            )

            for result in api_results:

                link = result.get(
                    "link",
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
                        ==
                        result.get(
                            "snippet",
                            ""
                        ).lower()
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
    # FINAL CLEANUP
    # --------------------------------------------------------

    final_results = []

    seen = set()

    for result in all_results:

        title = clean_text(
            result.get(
                "title",
                ""
            )
        )

        snippet = clean_text(
            result.get(
                "snippet",
                ""
            )
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

        seen.add(
            key
        )

        final_results.append({

            "title":
                title or query,

            "snippet":
                snippet,

            "link":
                link,

            "source":
                "DuckDuckGo"

        })

        if len(final_results) >= 8:

            break

    print(
        "Final DuckDuckGo results:",
        len(final_results)
    )

    print("===================================")
    print("")

    return final_results


# ============================================================
# RANK INTERNET RESULTS
# ============================================================

def rank_search_results(
    query,
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
            stop_words="english"
        )

        matrix = vectorizer.fit_transform(

            [
                query
            ]
            +
            documents

        )

        scores = cosine_similarity(

            matrix[0:1],

            matrix[1:]

        )[0]

        ranked = []

        for i, score in enumerate(
            scores
        ):

            item = dict(
                results[i]
            )

            item["score"] = float(
                score
            )

            ranked.append(
                item
            )

        ranked.sort(

            key=lambda x:
                x["score"],

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
# BUILD GEMINI SEARCH CONTEXT
# ============================================================

def build_search_context(
    results
):

    parts = []

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

        url = result.get(
            "link",
            ""
        )

        parts.append(

            f"""
SOURCE {index}

Title:
{title}

Information:
{snippet}

URL:
{url}
""".strip()

        )

    return "\n\n".join(
        parts
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
You are an educational AI assistant specializing in:

- Communication Systems
- Electronics
- Electrical Engineering
- Computer Networks
- Signal Processing
- Wireless Communication
- Digital Communication

USER QUESTION:
{question}

INFORMATION FOUND FROM DUCKDUCKGO:
{context}

Your job is to create ONE clean educational answer.

IMPORTANT:

1. Do NOT copy search-result snippets directly.
2. Do NOT show a list of search results as the answer.
3. Combine relevant information from the sources.
4. Remove duplicate information.
5. Ignore irrelevant sources.
6. Do not use Wikipedia.
7. Do not invent facts.
8. Use only information supported by the supplied sources.
9. Answer exactly what the user asked.
10. Keep the answer easy to understand.
11. Do not make the answer unnecessarily long.
12. Do not include raw URLs.
13. Sources will be displayed separately by the application.

STRUCTURE THE ANSWER INTELLIGENTLY.

For a definition/concept question, use sections such as:

### [Topic]

**Definition**
Give a clear definition.

**Symbol**
Include this only if a standard symbol exists.

**Formula**
Include this only when applicable.

**Unit**
Include this only when applicable.

**Explanation**
Explain the concept simply.

**Examples**
- Example 1
- Example 2

**Applications**
- Application 1
- Application 2

IMPORTANT:
Do NOT include sections that are not relevant.

For a comparison question:
Use a clear comparison table.

For a question asking for steps:
Use numbered steps.

For advantages/disadvantages:
Use separate bullet lists.

For a formula question:
Show the formula and explain each variable.

For a "what is" question:
Start with a short definition and then explain it.

For a "why" question:
Explain the reason clearly.

For a "how" question:
Explain the process step-by-step.

For a numerical problem:
Show:
1. Given
2. Formula
3. Substitution
4. Calculation
5. Final answer

Do NOT return raw search snippets.

Return only the final educational answer.

ANSWER:
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

    paragraphs = re.split(
        r"\n\s*\n",
        text
    )

    paragraphs = [

        clean_text(
            paragraph
        )

        for paragraph in paragraphs

        if clean_text(
            paragraph
        )

    ]

    if not paragraphs:

        paragraphs = [
            clean_text(text)
        ]

    # --------------------------------------------------------
    # Keyword matching
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

    matches = []

    for paragraph in paragraphs:

        lower = paragraph.lower()

        count = sum(

            1

            for keyword in keywords

            if keyword in lower

        )

        if count > 0:

            matches.append(
                (
                    count,
                    paragraph
                )
            )

    matches.sort(
        key=lambda x:
            x[0],
        reverse=True
    )

    selected = []

    if matches:

        selected = [

            item[1]

            for item in matches[:8]

        ]

    else:

        # ----------------------------------------------------
        # TF-IDF fallback
        # ----------------------------------------------------

        try:

            vectorizer = TfidfVectorizer(
                stop_words="english"
            )

            matrix = vectorizer.fit_transform(

                [
                    question
                ]
                +
                paragraphs

            )

            scores = cosine_similarity(

                matrix[0:1],

                matrix[1:]

            )[0]

            indexes = scores.argsort()[
                ::-1
            ]

            for index in indexes[:8]:

                if scores[index] > 0:

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

    relevant_text = "\n\n".join(
        selected
    )

    # --------------------------------------------------------
    # Gemini PDF answer
    # --------------------------------------------------------

    if gemini_client:

        prompt = f"""
You are answering a question using ONLY the uploaded PDF.

USER QUESTION:
{question}

RELEVANT PDF CONTENT:
{relevant_text}

IMPORTANT RULES:

1. Use ONLY the supplied PDF content.
2. Do NOT use Internet information.
3. Do NOT use outside knowledge.
4. Do NOT invent information.
5. Answer only what the user asks.
6. Do not copy unrelated PDF content.
7. Remove duplicate information.
8. Use headings and bullet points where appropriate.
9. Keep the answer concise.
10. If the requested information is not present,
respond exactly:

This information was not found in the uploaded PDF.

ANSWER:
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

                "success":
                    False,

                "message":
                    "No PDF file received."

            }), 400

        file = request.files[
            "pdf"
        ]

        if not file.filename:

            return jsonify({

                "success":
                    False,

                "message":
                    "No PDF selected."

            }), 400

        if not file.filename.lower().endswith(
            ".pdf"
        ):

            return jsonify({

                "success":
                    False,

                "message":
                    "Please upload a PDF file."

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

                "success":
                    False,

                "message":
                    "Could not extract readable text from the PDF."

            }), 400

        pdf_text = extracted_text

        pdf_filename = file.filename

        print("")
        print("===================================")
        print(
            "PDF UPLOADED:",
            pdf_filename
        )
        print(
            "Extracted characters:",
            len(pdf_text)
        )
        print("===================================")
        print("")

        return jsonify({

            "success":
                True,

            "message":
                "PDF uploaded successfully.",

            "filename":
                pdf_filename

        })

    except Exception as e:

        print(
            "PDF upload error:",
            repr(e)
        )

        return jsonify({

            "success":
                False,

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
            data.get(
                "question",
                ""
            )
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
        print(
            "PDF QUESTION:",
            question
        )
        print("===================================")

        answer = answer_from_pdf(

            question,

            pdf_text

        )

        return jsonify({

            "answer":
                answer,

            "filename":
                pdf_filename

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
            data.get(
                "question",
                ""
            )
        )

        if not question:

            return jsonify({

                "answer":
                    "Please enter a question.",

                "sources":
                    []

            })

        print("")
        print("===================================")
        print(
            "INTERNET QUESTION:",
            question
        )
        print("===================================")

        # ----------------------------------------------------
        # SEARCH
        # ----------------------------------------------------

        results = search_internet(
            question
        )

        print(
            "Total Internet results:",
            len(results)
        )

        # ----------------------------------------------------
        # NO RESULTS
        # ----------------------------------------------------

        if not results:

            print(
                "DuckDuckGo results: 0"
            )

            return jsonify({

                "answer":
                    "❌ Internet search did not return any results. "
                    "Please try another question.",

                "sources":
                    []

            })

        # ----------------------------------------------------
        # RANK RESULTS
        # ----------------------------------------------------

        ranked_results = rank_search_results(

            question,

            results

        )

        # Use only the most relevant sources
        selected_results = ranked_results[:6]

        print(
            "Selected relevant sources:",
            len(selected_results)
        )

        # ----------------------------------------------------
        # GEMINI GENERATES CLEAN ANSWER
        # ----------------------------------------------------

        answer = generate_internet_answer(

            question,

            selected_results

        )

        # ----------------------------------------------------
        # DO NOT DISPLAY RAW SEARCH SNIPPETS
        # ----------------------------------------------------

        if not answer:

            print(
                "Gemini failed to generate a clean answer."
            )

            return jsonify({

                "answer":
                    "❌ AI could not generate a clean answer "
                    "from the Internet sources. Please try "
                    "the question again.",

                "sources": [

                    {
                        "title":
                            result.get(
                                "title",
                                "Source"
                            ),

                        "url":
                            result.get(
                                "link",
                                ""
                            )

                    }

                    for result in selected_results

                    if result.get(
                        "link",
                        ""
                    )

                    and not is_wikipedia(
                        result.get(
                            "link",
                            ""
                        )
                    )

                ]

            })

        # ----------------------------------------------------
        # SOURCES ONLY
        # ----------------------------------------------------

        sources = []

        for result in selected_results:

            url = result.get(
                "link",
                ""
            )

            title = result.get(
                "title",
                "Source"
            )

            if not url:

                continue

            if is_wikipedia(url):

                continue

            sources.append({

                "title":
                    title,

                "url":
                    url

            })

        print(
            "Sources returned:",
            len(sources)
        )

        print("===================================")
        print("")

        return jsonify({

            "answer":
                answer,

            "sources":
                sources

        })

    except Exception as e:

        print(
            "Internet question error:"
        )

        print(
            repr(e)
        )

        return jsonify({

            "answer":
                "❌ An error occurred while searching the Internet.",

            "sources":
                []

        }), 500


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return jsonify({

        "error":
            "Page not found."

    }), 404


@app.errorhandler(500)
def internal_server_error(error):

    return jsonify({

        "error":
            "Internal server error."

    }), 500


# ============================================================
# LOCAL HTTP SERVER
# ============================================================

if __name__ == "__main__":

    port = int(

        os.environ.get(
            "PORT",
            5000
        )

    )

    print("")
    print("===================================")
    print("Communication Systems AI")
    print("LOCAL HTTP SERVER")
    print(
        "http://127.0.0.1:"
        + str(port)
    )
    print("===================================")
    print("")

    app.run(

        host="0.0.0.0",

        port=port,

        debug=False

    )