// ============================================================
// COMMUNICATION SYSTEMS AI - SCRIPT.JS
// ============================================================

document.addEventListener("DOMContentLoaded", () => {

    const questionInput = document.getElementById("questionInput");
    const sendButton = document.getElementById("sendButton");
    const answerBox = document.getElementById("answerBox");

    const uploadInput = document.getElementById("pdfInput");
    const uploadButton = document.getElementById("uploadPdfButton");

    const internetButton = document.getElementById("internetButton");
    const pdfButton = document.getElementById("pdfButton");

    const newChatButton = document.getElementById("newChatButton");
    const clearHistoryButton =
        document.getElementById("clearHistoryButton");

    const historyList = document.getElementById("historyList");
    const statusText = document.getElementById("statusText");
    const modeBadge = document.getElementById("modeBadge");

    const pdfUploadArea =
        document.getElementById("pdfUploadArea");

    const pdfFileName =
        document.getElementById("pdfFileName");

    let currentMode = "internet";
    let pdfUploaded = false;

    let searchHistory = JSON.parse(
        localStorage.getItem(
            "communicationSearchHistory"
        ) || "[]"
    );


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
            function(match) {

                const id =
                    `MATHBLOCK${mathBlocks.length}END`;

                mathBlocks.push(match);

                return `\n${id}\n`;
            }
        );


        text = text.replace(
            /\\\[([\s\S]*?)\\\]/g,
            function(match) {

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
            function(match) {

                const id =
                    `MATHINLINE${inlineMath.length}END`;

                inlineMath.push(match);

                return id;
            }
        );


        text = text.replace(
            /\\\((.*?)\\\)/g,
            function(match) {

                const id =
                    `MATHINLINE${inlineMath.length}END`;

                inlineMath.push(match);

                return id;
            }
        );


        // ----------------------------------------------------
        // Separate headings
        // ----------------------------------------------------

        text = text.replace(
            /\s+(#{1,6})\s+/g,
            "\n$1 "
        );


        // ----------------------------------------------------
        // Separate bullets
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
            "Principle"

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

        text = escapeHTML(text);


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

        const lines = text.split("\n");

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

            const line = rawLine.trim();


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
                    listType = "unordered";
                }


                let item = line.substring(2);


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
                    listType = "ordered";
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
        }
    }


    // ========================================================
    // SHOW ANSWER
    // ========================================================

    function showAnswer(answer) {

        answerBox.innerHTML =
            formatAIAnswer(answer);


        setTimeout(() => {

            renderMath();

        }, 20);
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
            searchHistory.slice(0, 20);


        localStorage.setItem(
            "communicationSearchHistory",
            JSON.stringify(searchHistory)
        );


        renderHistory();
    }


    function renderHistory() {

        historyList.innerHTML = "";


        if (searchHistory.length === 0) {

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


                item.type = "button";


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

        currentMode = mode;


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


        if (mode === "internet") {

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


        addToHistory(question);

        showLoading();

        sendButton.disabled = true;


        const endpoint =
            currentMode === "pdf"
                ? "/ask_pdf"
                : "/ask_internet";


        try {

            const response =
                await fetch(
                    endpoint,
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({
                            question:
                                question
                        })
                    }
                );


            if (!response.ok) {

                throw new Error(
                    `Server error: ${response.status}`
                );
            }


            const data =
                await response.json();


            if (data.answer) {

                showAnswer(
                    data.answer
                );

            } else {

                showError(
                    "No answer was returned."
                );
            }


        } catch (error) {

            console.error(
                error
            );


            showError(
                "Unable to connect to the server."
            );


        } finally {

            sendButton.disabled = false;
        }
    }


    // ========================================================
    // OPEN FILE PICKER
    // ========================================================

    uploadButton.addEventListener(
        "click",
        () => {

            // IMPORTANT:
            // Open Windows file picker

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

                uploadInput.value = "";

                return;
            }


            pdfFileName.textContent =
                "Selected: " + file.name;


            const formData =
                new FormData();


            formData.append(
                "pdf",
                file
            );


            uploadButton.disabled = true;


            statusText.textContent =
                "Uploading PDF...";


            try {

                const response =
                    await fetch(
                        "/upload_pdf",
                        {
                            method: "POST",
                            body: formData
                        }
                    );


                const data =
                    await response.json();


                if (data.success) {

                    pdfUploaded = true;

                    setMode("pdf");


                    statusText.textContent =
                        "PDF ready for questions";


                    showAnswer(`

### PDF Uploaded Successfully

**File:** ${file.name}

You can now ask questions about this PDF.

The PDF Q&A mode answers questions using the uploaded document.

                    `);

                } else {

                    showError(
                        data.message ||
                        "PDF upload failed."
                    );

                }


            } catch (error) {

                console.error(
                    error
                );


                showError(
                    "Unable to upload PDF."
                );

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

            questionInput.value = "";

            pdfUploaded = false;

            uploadInput.value = "";

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


            setMode("internet");

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

            setMode("internet");

        }
    );


    pdfButton.addEventListener(
        "click",
        () => {

            setMode("pdf");

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

    setMode("internet");

});