// ============================================================
// COMMUNICATION SYSTEMS AI
// FRONTEND-ONLY GITHUB PAGES VERSION
// ============================================================
//
// No Flask
// No Render
// No Python backend
//
// Uses:
// 1. Gemini API directly from browser
// 2. DuckDuckGo Instant Answer API
// 3. PDF.js for browser-side PDF extraction
// 4. LocalStorage for history and PDF text
//
// ============================================================

document.addEventListener("DOMContentLoaded", () => {

    // ========================================================
    // CONFIGURATION
    // ========================================================

    const GEMINI_MODEL = "gemini-2.5-flash";

    const GEMINI_API_URL =
        "https://generativelanguage.googleapis.com/v1beta/models/" +
        GEMINI_MODEL +
        ":generateContent";

    const DUCKDUCKGO_URL =
        "https://api.duckduckgo.com/";


    // ========================================================
    // ELEMENTS
    // ========================================================

    const questionInput =
        document.getElementById("questionInput");

    const sendButton =
        document.getElementById("sendButton");

    const answerBox =
        document.getElementById("answerBox");

    const uploadInput =
        document.getElementById("pdfInput");

    const uploadButton =
        document.getElementById("uploadPdfButton");

    const internetButton =
        document.getElementById("internetButton");

    const pdfButton =
        document.getElementById("pdfButton");

    const newChatButton =
        document.getElementById("newChatButton");

    const clearHistoryButton =
        document.getElementById("clearHistoryButton");

    const historyList =
        document.getElementById("historyList");

    const statusText =
        document.getElementById("statusText");

    const modeBadge =
        document.getElementById("modeBadge");

    const pdfUploadArea =
        document.getElementById("pdfUploadArea");

    const pdfFileName =
        document.getElementById("pdfFileName");


    // ========================================================
    // STATE
    // ========================================================

    let currentMode = "internet";

    let pdfUploaded = false;

    let currentPDFText = "";

    let currentPDFName = "";


    let searchHistory = JSON.parse(
        localStorage.getItem(
            "communicationSearchHistory"
        ) || "[]"
    );


    // ========================================================
    // GEMINI API KEY
    // ========================================================

    function getGeminiAPIKey() {

        let apiKey =
            localStorage.getItem(
                "communicationGeminiAPIKey"
            );


        if (apiKey) {
            return apiKey;
        }


        apiKey = prompt(
            "Enter your Gemini API key.\n\n" +
            "The key will be stored only in this browser's localStorage."
        );


        if (!apiKey || !apiKey.trim()) {

            return null;
        }


        apiKey =
            apiKey.trim();


        localStorage.setItem(
            "communicationGeminiAPIKey",
            apiKey
        );


        return apiKey;
    }


    // ========================================================
    // ESCAPE HTML
    // ========================================================

    function escapeHTML(text) {

        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }


    // ========================================================
    // INLINE MARKDOWN
    // ========================================================

    function formatInlineMarkdown(text) {

        text = text.replace(
            /\*\*(.*?)\*\*/g,
            "<strong>$1</strong>"
        );


        text = text.replace(
            /(?<!\*)\*([^*]+)\*(?!\*)/g,
            "<em>$1</em>"
        );


        text = text.replace(
            /`([^`]+)`/g,
            "<code>$1</code>"
        );


        return text;
    }


    // ========================================================
    // FORMAT AI ANSWER
    // ========================================================

    function formatAIAnswer(text) {

        if (!text) {
            return "";
        }


        text = String(text)
            .replace(/\r\n/g, "\n")
            .replace(/\r/g, "\n");


        // ----------------------------------------------------
        // Protect display math
        // ----------------------------------------------------

        const mathBlocks = [];


        text = text.replace(
            /\$\$([\s\S]*?)\$\$/g,
            function (match) {

                const id =
                    `MATHBLOCK${mathBlocks.length}END`;

                mathBlocks.push(match);

                return `\n${id}\n`;
            }
        );


        text = text.replace(
            /\\\[([\s\S]*?)\\\]/g,
            function (match) {

                const id =
                    `MATHBLOCK${mathBlocks.length}END`;

                mathBlocks.push(match);

                return `\n${id}\n`;
            }
        );


        // ----------------------------------------------------
        // Protect inline math
        // ----------------------------------------------------

        const inlineMath = [];


        text = text.replace(
            /\$([^\n$]+?)\$/g,
            function (match) {

                const id =
                    `MATHINLINE${inlineMath.length}END`;

                inlineMath.push(match);

                return id;
            }
        );


        text = text.replace(
            /\\\((.*?)\\\)/g,
            function (match) {

                const id =
                    `MATHINLINE${inlineMath.length}END`;

                inlineMath.push(match);

                return id;
            }
        );


        // ----------------------------------------------------
        // Headings
        // ----------------------------------------------------

        text = text.replace(
            /\s+(#{1,6})\s+/g,
            "\n$1 "
        );


        // ----------------------------------------------------
        // Bullets
        // ----------------------------------------------------

        text = text.replace(
            /\s+\*\s+(?=\*\*)/g,
            "\n* "
        );


        text = text.replace(
            /\s+-\s+(?=\*\*)/g,
            "\n- "
        );


        text = text.replace(
            /\s+•\s+/g,
            "\n• "
        );


        // ----------------------------------------------------
        // Numbered lists
        // ----------------------------------------------------

        text = text.replace(
            /\s+(\d+\.)\s+/g,
            "\n$1 "
        );


        // ----------------------------------------------------
        // Common sections
        // ----------------------------------------------------

        const sections = [

            "Key Components",
            "Primary Objectives",
            "Main Components",
            "Components",
            "How It Works",
            "Working",
            "Advantages",
            "Applications",
            "Features",
            "Important Points",
            "Conclusion",
            "Summary",
            "Types",
            "Examples",
            "Characteristics",
            "Functions",
            "Formula",
            "Formulas",
            "Definition",
            "Principle",
            "Sources"

        ];


        sections.forEach(section => {

            const escaped =
                section.replace(
                    /[.*+?^${}()|[\]\\]/g,
                    "\\$&"
                );


            const regex =
                new RegExp(
                    "\\s+(" +
                    escaped +
                    ")\\s*:?\\s*",
                    "gi"
                );


            text = text.replace(
                regex,
                "\n### $1\n"
            );

        });


        text = text.replace(
            /\n{3,}/g,
            "\n\n"
        );


        // ----------------------------------------------------
        // Escape HTML
        // ----------------------------------------------------

        text =
            escapeHTML(text);


        // ----------------------------------------------------
        // Restore formulas
        // ----------------------------------------------------

        mathBlocks.forEach(
            (formula, index) => {

                text = text.replace(
                    `MATHBLOCK${index}END`,
                    formula
                );

            }
        );


        inlineMath.forEach(
            (formula, index) => {

                text = text.replace(
                    `MATHINLINE${index}END`,
                    formula
                );

            }
        );


        // ----------------------------------------------------
        // Convert lines
        // ----------------------------------------------------

        const lines =
            text.split("\n");


        let html = "";

        let inList = false;

        let listType = null;


        function closeList() {

            if (inList) {

                html +=
                    listType === "ordered"
                        ? "</ol>"
                        : "</ul>";

                inList = false;

                listType = null;
            }
        }


        for (let rawLine of lines) {

            const line =
                rawLine.trim();


            if (!line) {
                continue;
            }


            // Heading
            if (line.startsWith("### ")) {

                closeList();

                html +=
                    `<h3>${formatInlineMarkdown(
                        line.substring(4)
                    )}</h3>`;

                continue;
            }


            if (line.startsWith("## ")) {

                closeList();

                html +=
                    `<h2>${formatInlineMarkdown(
                        line.substring(3)
                    )}</h2>`;

                continue;
            }


            if (line.startsWith("# ")) {

                closeList();

                html +=
                    `<h2>${formatInlineMarkdown(
                        line.substring(2)
                    )}</h2>`;

                continue;
            }


            // Bullet
            if (
                line.startsWith("- ") ||
                line.startsWith("* ") ||
                line.startsWith("• ")
            ) {

                if (
                    !inList ||
                    listType !== "unordered"
                ) {

                    closeList();

                    html += "<ul>";

                    inList = true;

                    listType =
                        "unordered";
                }


                const item =
                    line.substring(2);


                html +=
                    `<li>${formatInlineMarkdown(
                        item
                    )}</li>`;

                continue;
            }


            // Numbered list
            const numberMatch =
                line.match(
                    /^(\d+)\.\s+(.*)$/
                );


            if (numberMatch) {

                if (
                    !inList ||
                    listType !== "ordered"
                ) {

                    closeList();

                    html += "<ol>";

                    inList = true;

                    listType =
                        "ordered";
                }


                html +=
                    `<li>${formatInlineMarkdown(
                        numberMatch[2]
                    )}</li>`;

                continue;
            }


            // Normal paragraph
            closeList();


            html +=
                `<p>${formatInlineMarkdown(
                    line
                )}</p>`;
        }


        closeList();


        return html;
    }


    // ========================================================
    // MATHJAX
    // ========================================================

    function renderMath() {

        if (
            window.MathJax &&
            answerBox
        ) {

            try {

                MathJax.typesetClear(
                    [answerBox]
                );


                MathJax.typesetPromise(
                    [answerBox]
                ).catch(error => {

                    console.error(
                        "MathJax error:",
                        error
                    );

                });

            } catch (error) {

                console.error(
                    "MathJax rendering error:",
                    error
                );
            }
        }
    }


    // ========================================================
    // SHOW ANSWER
    // ========================================================

    function showAnswer(answer) {

        answerBox.innerHTML =
            formatAIAnswer(answer);


        setTimeout(
            renderMath,
            20
        );
    }


    // ========================================================
    // LOADING
    // ========================================================

    function showLoading() {

        answerBox.innerHTML = `

            <div class="loading-answer">

                <div class="loading-spinner"></div>

                <div>

                    <strong>
                        AI is thinking...
                    </strong>

                    <span>
                        Finding the most relevant information.
                    </span>

                </div>

            </div>

        `;
    }


    // ========================================================
    // ERROR
    // ========================================================

    function showError(message) {

        answerBox.innerHTML = `

            <div class="answer-error">

                <strong>
                    ⚠️ Error
                </strong>

                <p>
                    ${escapeHTML(message)}
                </p>

            </div>

        `;
    }


    // ========================================================
    // HISTORY
    // ========================================================

    function addToHistory(question) {

        if (!question.trim()) {
            return;
        }


        searchHistory =
            searchHistory.filter(
                item => item !== question
            );


        searchHistory.unshift(
            question
        );


        searchHistory =
            searchHistory.slice(
                0,
                20
            );


        localStorage.setItem(
            "communicationSearchHistory",
            JSON.stringify(searchHistory)
        );


        renderHistory();
    }


    function renderHistory() {

        historyList.innerHTML = "";


        if (
            searchHistory.length === 0
        ) {

            historyList.innerHTML = `

                <div class="empty-history">
                    No search history
                </div>

            `;

            return;
        }


        searchHistory.forEach(
            question => {

                const item =
                    document.createElement(
                        "button"
                    );


                item.className =
                    "history-item";


                item.type =
                    "button";


                item.textContent =
                    question;


                item.addEventListener(
                    "click",
                    () => {

                        questionInput.value =
                            question;

                        sendQuestion();

                    }
                );


                historyList.appendChild(
                    item
                );

            }
        );
    }


    function clearHistory() {

        searchHistory = [];


        localStorage.removeItem(
            "communicationSearchHistory"
        );


        renderHistory();
    }


    // ========================================================
    // MODE
    // ========================================================

    function setMode(mode) {

        currentMode =
            mode;


        internetButton.classList.toggle(
            "active-mode",
            mode === "internet"
        );


        pdfButton.classList.toggle(
            "active-mode",
            mode === "pdf"
        );


        if (modeBadge) {

            modeBadge.innerHTML =
                mode === "internet"
                    ? "🌐 Internet Q&amp;A"
                    : "📄 PDF Q&amp;A";
        }


        if (
            mode === "internet"
        ) {

            statusText.textContent =
                "Internet Q&A mode";


            pdfUploadArea.style.display =
                "none";

        } else {

            statusText.textContent =
                pdfUploaded
                    ? "PDF Q&A mode"
                    : "Select a PDF file";


            pdfUploadArea.style.display =
                "flex";
        }
    }


    // ========================================================
    // LOAD PDF.JS
    // ========================================================

    async function loadPDFJS() {

        if (
            window.pdfjsLib
        ) {

            return;
        }


        await new Promise(
            (resolve, reject) => {

                const script =
                    document.createElement(
                        "script"
                    );


                script.src =
                    "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.min.mjs";


                script.type =
                    "module";


                script.onload =
                    resolve;


                script.onerror =
                    reject;


                document.head.appendChild(
                    script
                );

            }
        );


        // The module build exposes differently
        // depending on browser/CDN behavior.
        //
        // We therefore load the legacy build below
        // if pdfjsLib is unavailable.

        if (!window.pdfjsLib) {

            await new Promise(
                (resolve, reject) => {

                    const script =
                        document.createElement(
                            "script"
                        );


                    script.src =
                        "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js";


                    script.onload =
                        resolve;


                    script.onerror =
                        reject;


                    document.head.appendChild(
                        script
                    );

                }
            );
        }


        if (
            window.pdfjsLib &&
            window.pdfjsLib.GlobalWorkerOptions
        ) {

            window.pdfjsLib
                .GlobalWorkerOptions
                .workerSrc =
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
        }
    }


    // ========================================================
    // EXTRACT PDF TEXT
    // ========================================================

    async function extractPDFText(file) {

        await loadPDFJS();


        if (!window.pdfjsLib) {

            throw new Error(
                "PDF.js could not be loaded."
            );
        }


        const arrayBuffer =
            await file.arrayBuffer();


        const pdf =
            await window.pdfjsLib.getDocument({
                data: arrayBuffer
            }).promise;


        let fullText = "";


        for (
            let pageNumber = 1;
            pageNumber <= pdf.numPages;
            pageNumber++
        ) {

            const page =
                await pdf.getPage(
                    pageNumber
                );


            const content =
                await page.getTextContent();


            const pageText =
                content.items
                    .map(
                        item =>
                            item.str
                    )
                    .join(" ");


            fullText +=
                `\n\n--- Page ${pageNumber} ---\n\n` +
                pageText;
        }


        return fullText.trim();
    }


    // ========================================================
    // GEMINI REQUEST
    // ========================================================

    async function askGemini(
        prompt,
        systemInstruction = ""
    ) {

        const apiKey =
            getGeminiAPIKey();


        if (!apiKey) {

            throw new Error(
                "Gemini API key was not provided."
            );
        }


        const requestBody = {

            contents: [

                {

                    role: "user",

                    parts: [

                        {
                            text:
                                systemInstruction +
                                "\n\n" +
                                prompt
                        }

                    ]

                }

            ],

            generationConfig: {

                temperature: 0.2,

                maxOutputTokens: 2048

            }

        };


        const response =
            await fetch(
                GEMINI_API_URL +
                "?key=" +
                encodeURIComponent(
                    apiKey
                ),
                {

                    method: "POST",

                    headers: {

                        "Content-Type":
                            "application/json"

                    },

                    body:
                        JSON.stringify(
                            requestBody
                        )

                }
            );


        if (!response.ok) {

            const errorText =
                await response.text();


            console.error(
                "Gemini API error:",
                errorText
            );


            throw new Error(
                "Gemini API request failed."
            );
        }


        const data =
            await response.json();


        const answer =
            data
                ?.candidates?.[0]
                ?.content
                ?.parts
                ?.map(
                    part =>
                        part.text || ""
                )
                .join("");


        if (!answer) {

            throw new Error(
                "Gemini returned an empty answer."
            );
        }


        return answer;
    }


    // ========================================================
    // DUCKDUCKGO SEARCH
    // ========================================================

    async function searchDuckDuckGo(
        query
    ) {

        const url =
            DUCKDUCKGO_URL +
            "?q=" +
            encodeURIComponent(query) +
            "&format=json" +
            "&no_html=1" +
            "&skip_disambig=1";


        try {

            const response =
                await fetch(
                    url
                );


            if (!response.ok) {

                throw new Error(
                    "DuckDuckGo search failed."
                );
            }


            const data =
                await response.json();


            const results = [];


            // ------------------------------------------------
            // Abstract
            // ------------------------------------------------

            if (
                data.AbstractText &&
                data.AbstractText.trim()
            ) {

                results.push({

                    title:
                        data.Heading ||
                        "DuckDuckGo Result",

                    text:
                        data.AbstractText,

                    url:
                        data.AbstractURL ||
                        ""

                });
            }


            // ------------------------------------------------
            // Related Topics
            // ------------------------------------------------

            if (
                Array.isArray(
                    data.RelatedTopics
                )
            ) {

                function collectTopics(
                    topics
                ) {

                    for (
                        const topic
                        of topics
                    ) {

                        if (
                            topic.Text &&
                            topic.FirstURL
                        ) {

                            results.push({

                                title:
                                    topic.Text,

                                text:
                                    topic.Text,

                                url:
                                    topic.FirstURL

                            });
                        }


                        if (
                            Array.isArray(
                                topic.Topics
                            )
                        ) {

                            collectTopics(
                                topic.Topics
                            );
                        }


                        if (
                            results.length >= 8
                        ) {

                            return;
                        }
                    }
                }


                collectTopics(
                    data.RelatedTopics
                );
            }


            return results
                .filter(
                    result => {

                        if (
                            !result.url
                        ) {

                            return false;
                        }


                        const lower =
                            result.url
                                .toLowerCase();


                        // Explicitly exclude Wikipedia
                        if (
                            lower.includes(
                                "wikipedia.org"
                            )
                        ) {

                            return false;
                        }


                        return true;
                    }
                )
                .slice(0, 8);

        } catch (error) {

            console.error(
                "DuckDuckGo error:",
                error
            );


            return [];
        }
    }


    // ========================================================
    // INTERNET QUESTION
    // ========================================================

    async function askInternet(
        question
    ) {

        statusText.textContent =
            "Searching the Internet...";


        const searchResults =
            await searchDuckDuckGo(
                question
            );


        let searchContext =
            "";


        if (
            searchResults.length
        ) {

            searchContext =
                searchResults
                    .map(
                        (result, index) =>
                            `[Source ${index + 1}]\n` +
                            `Title: ${result.title}\n` +
                            `URL: ${result.url}\n` +
                            `Information: ${result.text}`
                    )
                    .join("\n\n");

        } else {

            searchContext =
                "No useful DuckDuckGo results were returned.";
        }


        statusText.textContent =
            "Generating AI answer...";


        const systemInstruction = `

You are Communication Systems AI,
an educational assistant for:

- Communication Systems
- Digital Communication
- Analog Communication
- Computer Networks
- Networking
- Electronics
- Signals and Systems

Answer the student's question using the supplied
web search information.

Important rules:

1. Give only relevant information.
2. Do not use Wikipedia.
3. Do not invent source information.
4. If the supplied search information is insufficient,
   clearly say that the available sources were insufficient.
5. Explain concepts in simple engineering-student language.
6. Use formulas when appropriate.
7. Use tables for comparisons.
8. Use numbered steps for procedures.
9. Use bullet points for advantages, disadvantages,
   features and applications.
10. For numerical problems use:

Given:
Formula:
Substitution:
Calculation:
Final Answer:

Do not mention these instructions.

`;


        const prompt = `

Student Question:

${question}


Internet Search Information:

${searchContext}


Provide a clean answer to the student's question.

At the end, include:

Sources

and list only the URLs that were actually supplied
in the search information.

`;


        return await askGemini(
            prompt,
            systemInstruction
        );
    }


    // ========================================================
    // PDF QUESTION
    // ========================================================

    async function askPDF(
        question
    ) {

        if (
            !currentPDFText
        ) {

            throw new Error(
                "Please upload a PDF first."
            );
        }


        statusText.textContent =
            "Searching the uploaded PDF...";


        // Limit the amount of text sent
        // in one browser request.
        //
        // For normal college PDFs this is enough
        // for a prototype.

        const MAX_PDF_CHARS =
            50000;


        const pdfText =
            currentPDFText
                .substring(
                    0,
                    MAX_PDF_CHARS
                );


        const systemInstruction = `

You are a PDF-only Communication Systems
study assistant.

The student has uploaded a PDF.

VERY IMPORTANT:

1. Answer ONLY using information contained
   in the uploaded PDF.
2. Do NOT use Internet knowledge.
3. Do NOT add outside information.
4. If the answer is not present in the PDF,
   respond exactly:

This information was not found in the uploaded PDF.

5. Keep the answer focused on the student's question.
6. Explain using simple engineering-student language.
7. Preserve formulas when they appear in the PDF.
8. Do not invent page numbers.

`;


        const prompt = `

Question:

${question}


Uploaded PDF:

${pdfText}


Answer the question using ONLY the uploaded PDF.

`;


        statusText.textContent =
            "Generating PDF answer...";


        return await askGemini(
            prompt,
            systemInstruction
        );
    }


    // ========================================================
    // SEND QUESTION
    // ========================================================

    async function sendQuestion() {

        const question =
            questionInput.value.trim();


        if (!question) {

            showError(
                "Please enter a question."
            );

            return;
        }


        if (
            currentMode === "pdf" &&
            !pdfUploaded
        ) {

            showError(
                "Please upload a PDF first."
            );

            return;
        }


        addToHistory(
            question
        );


        showLoading();


        sendButton.disabled =
            true;


        try {

            let answer;


            if (
                currentMode === "internet"
            ) {

                answer =
                    await askInternet(
                        question
                    );

            } else {

                answer =
                    await askPDF(
                        question
                    );
            }


            showAnswer(
                answer
            );


            statusText.textContent =
                currentMode === "internet"
                    ? "Internet Q&A complete"
                    : "PDF Q&A complete";


        } catch (error) {

            console.error(
                error
            );


            let message =
                "Unable to process your question.";


            if (
                error.message
            ) {

                message =
                    error.message;
            }


            showError(
                message
            );


            statusText.textContent =
                "Error";


        } finally {

            sendButton.disabled =
                false;
        }
    }


    // ========================================================
    // OPEN PDF FILE PICKER
    // ========================================================

    uploadButton.addEventListener(
        "click",
        () => {

            uploadInput.click();

        }
    );


    // ========================================================
    // PDF SELECTED
    // ========================================================

    uploadInput.addEventListener(
        "change",
        async () => {

            const file =
                uploadInput.files[0];


            if (!file) {
                return;
            }


            if (
                !file.name
                    .toLowerCase()
                    .endsWith(".pdf")
            ) {

                showError(
                    "Please select a PDF file."
                );


                uploadInput.value =
                    "";


                return;
            }


            pdfFileName.textContent =
                "Selected: " +
                file.name;


            uploadButton.disabled =
                true;


            statusText.textContent =
                "Reading PDF in browser...";


            try {

                const text =
                    await extractPDFText(
                        file
                    );


                if (
                    !text ||
                    text.trim().length < 20
                ) {

                    throw new Error(
                        "No readable text was found in this PDF. Scanned/image-only PDFs need OCR."
                    );
                }


                currentPDFText =
                    text;


                currentPDFName =
                    file.name;


                pdfUploaded =
                    true;


                setMode(
                    "pdf"
                );


                statusText.textContent =
                    "PDF ready for questions";


                showAnswer(`

### PDF Uploaded Successfully

**File:** ${file.name}

The PDF was read directly in your browser.

You can now ask questions about the document.

PDF Q&A will use only the uploaded PDF content.

                `);


            } catch (error) {

                console.error(
                    "PDF error:",
                    error
                );


                currentPDFText =
                    "";


                currentPDFName =
                    "";


                pdfUploaded =
                    false;


                showError(
                    error.message ||
                    "Unable to read the PDF."
                );


                statusText.textContent =
                    "PDF reading failed";


            } finally {

                uploadButton.disabled =
                    false;
            }
        }
    );


    // ========================================================
    // NEW CHAT
    // ========================================================

    newChatButton.addEventListener(
        "click",
        () => {

            questionInput.value =
                "";


            pdfUploaded =
                false;


            currentPDFText =
                "";


            currentPDFName =
                "";


            uploadInput.value =
                "";


            pdfFileName.textContent =
                "No PDF selected";


            answerBox.innerHTML = `

                <div class="welcome-answer">

                    <div class="welcome-icon">
                        🤖
                    </div>

                    <h3>
                        AI Assistant
                    </h3>

                    <p>
                        Ask a Communication Systems
                        or Computer Networks question.
                    </p>

                    <p>
                        Use Internet Q&A or upload
                        a PDF and ask questions from
                        the document.
                    </p>

                </div>

            `;


            setMode(
                "internet"
            );

        }
    );


    // ========================================================
    // BUTTONS
    // ========================================================

    sendButton.addEventListener(
        "click",
        sendQuestion
    );


    internetButton.addEventListener(
        "click",
        () => {

            setMode(
                "internet"
            );

        }
    );


    pdfButton.addEventListener(
        "click",
        () => {

            setMode(
                "pdf"
            );

        }
    );


    clearHistoryButton.addEventListener(
        "click",
        clearHistory
    );


    // ========================================================
    // ENTER KEY
    // ========================================================

    questionInput.addEventListener(
        "keydown",
        event => {

            if (
                event.key === "Enter"
            ) {

                event.preventDefault();

                sendQuestion();

            }

        }
    );


    // ========================================================
    // INITIALIZATION
    // ========================================================

    renderHistory();

    setMode(
        "internet"
    );

});