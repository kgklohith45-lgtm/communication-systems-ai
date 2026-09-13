// =========================================================
// CURRENT MODE
// =========================================================

let currentMode = "pdf";


// =========================================================
// HISTORY
// =========================================================

let searchHistory =
    JSON.parse(
        localStorage.getItem("communicationHistory")
    ) || [];


// =========================================================
// PAGE LOAD
// =========================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        loadHistory();

        updateModeDisplay();

    }
);



// =========================================================
// ADD MESSAGE
// =========================================================

function addMessage(message, sender) {

    const chatBox =
        document.getElementById("chat-box");


    const messageDiv =
        document.createElement("div");


    if (sender === "user") {

        messageDiv.className =
            "user-message";


        messageDiv.innerHTML = `
            <strong>You</strong>
            <p>${escapeHTML(message)}</p>
        `;

    } else {

        messageDiv.className =
            "bot-message";


        messageDiv.innerHTML = `
            <strong>🤖 AI Assistant</strong>
            <p>${message}</p>
        `;

    }


    chatBox.appendChild(
        messageDiv
    );


    chatBox.scrollTop =
        chatBox.scrollHeight;
}



// =========================================================
// ESCAPE HTML
// =========================================================

function escapeHTML(text) {

    const div =
        document.createElement("div");

    div.textContent = text;

    return div.innerHTML;
}



// =========================================================
// SAVE HISTORY
// =========================================================

function saveToHistory(question) {

    question =
        question.trim();


    if (!question) {

        return;
    }


    // Remove duplicate question
    searchHistory =
        searchHistory.filter(
            item => item !== question
        );


    // Put newest question first
    searchHistory.unshift(
        question
    );


    // Keep last 50 questions
    searchHistory =
        searchHistory.slice(
            0,
            50
        );


    localStorage.setItem(
        "communicationHistory",
        JSON.stringify(searchHistory)
    );


    loadHistory();
}



// =========================================================
// LOAD HISTORY
// =========================================================

function loadHistory() {

    const historyList =
        document.getElementById(
            "history-list"
        );


    if (!historyList) {

        return;
    }


    historyList.innerHTML = "";


    if (searchHistory.length === 0) {

        historyList.innerHTML = `
            <div class="history-empty">
                No questions yet.
            </div>
        `;

        return;
    }


    searchHistory.forEach(
        function (question) {

            const button =
                document.createElement(
                    "button"
                );


            button.className =
                "history-item";


            button.textContent =
                "💬 " + question;


            button.onclick =
                function () {

                    reuseHistoryQuestion(
                        question
                    );

                };


            historyList.appendChild(
                button
            );

        }
    );
}



// =========================================================
// REUSE HISTORY QUESTION
// =========================================================

function reuseHistoryQuestion(question) {

    const input =
        document.getElementById(
            "user-input"
        );


    input.value =
        question;


    input.focus();

}



// =========================================================
// CLEAR HISTORY
// =========================================================

function clearHistory() {

    const confirmed =
        confirm(
            "Clear all search history?"
        );


    if (!confirmed) {

        return;
    }


    searchHistory = [];


    localStorage.removeItem(
        "communicationHistory"
    );


    loadHistory();

}



// =========================================================
// NEW CHAT
// =========================================================

function newChat() {

    const chatBox =
        document.getElementById(
            "chat-box"
        );


    chatBox.innerHTML = `

        <div class="welcome-card">

            <div class="welcome-icon">
                📡
            </div>

            <h2>
                New Chat
            </h2>

            <p>
                Ask a Communication Systems question.
            </p>

        </div>

    `;


    document.getElementById(
        "user-input"
    ).value = "";

}



// =========================================================
// INTERNET MODE
// =========================================================

function selectInternetMode() {

    currentMode =
        "internet";


    updateModeDisplay();


    document.getElementById(
        "user-input"
    ).placeholder =
        "Ask a Communication Systems question...";


    setStatus(
        "🌐 Internet Q&A selected"
    );

}



// =========================================================
// PDF MODE
// =========================================================

function selectPDFMode() {

    currentMode =
        "pdf";


    updateModeDisplay();


    document.getElementById(
        "user-input"
    ).placeholder =
        "Ask a question from the uploaded PDF...";


    setStatus(
        "📄 PDF Q&A selected"
    );

}



// =========================================================
// UPDATE MODE
// =========================================================

function updateModeDisplay() {

    const badge =
        document.getElementById(
            "mode-badge"
        );


    if (!badge) {

        return;
    }


    if (currentMode === "internet") {

        badge.innerHTML =
            "🌐 Internet Q&A";

    } else {

        badge.innerHTML =
            "📄 PDF Q&A";

    }

}



// =========================================================
// STATUS
// =========================================================

function setStatus(message) {

    const status =
        document.getElementById(
            "status-message"
        );


    if (status) {

        status.textContent =
            message;

    }

}



// =========================================================
// SEND MESSAGE
// =========================================================

function sendMessage() {

    const input =
        document.getElementById(
            "user-input"
        );


    const question =
        input.value.trim();


    if (!question) {

        return;
    }


    // Save question
    saveToHistory(
        question
    );


    // Display question
    addMessage(
        question,
        "user"
    );


    input.value = "";


    // Select mode
    if (
        currentMode === "internet"
    ) {

        askInternet(
            question
        );

    } else {

        askPDF(
            question
        );

    }

}



// =========================================================
// UPLOAD PDF
// =========================================================

function uploadPDF() {

    const fileInput =
        document.getElementById(
            "pdf-input"
        );


    const file =
        fileInput.files[0];


    if (!file) {

        return;
    }


    if (
        !file.name
            .toLowerCase()
            .endsWith(".pdf")
    ) {

        addMessage(
            "❌ Please select a PDF file.",
            "bot"
        );

        return;
    }


    const formData =
        new FormData();


    formData.append(
        "pdf",
        file
    );


    addMessage(
        "📄 Uploading <b>" +
        escapeHTML(file.name) +
        "</b>...",
        "bot"
    );


    setStatus(
        "Uploading PDF..."
    );


    fetch(
        "/upload_pdf",
        {

            method: "POST",

            body: formData

        }
    )

    .then(
        response =>
            response.json()
    )

    .then(
        data => {

            if (data.success) {

                addMessage(

                    "✅ " +
                    escapeHTML(
                        data.message
                    ) +
                    "<br><br>" +
                    "Now click <b>📄 PDF Q&A</b> and ask your question.",

                    "bot"

                );


                selectPDFMode();


                setStatus(
                    "PDF ready for questions"
                );

            } else {

                addMessage(
                    "❌ " +
                    escapeHTML(
                        data.message
                    ),
                    "bot"
                );


                setStatus(
                    "PDF upload failed"
                );

            }

        }
    )

    .catch(
        error => {

            addMessage(
                "❌ Error uploading PDF: " +
                escapeHTML(
                    error.toString()
                ),
                "bot"
            );


            setStatus(
                "Upload error"
            );

        }
    );


    fileInput.value = "";

}



// =========================================================
// ASK PDF
// =========================================================

function askPDF(question) {

    addMessage(
        "🔎 Searching the uploaded PDF...",
        "bot"
    );


    setStatus(
        "Searching PDF..."
    );


    fetch(
        "/ask_pdf",
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
    )

    .then(
        response =>
            response.json()
    )

    .then(
        data => {

            removeSearchingMessage(
                "Searching the uploaded PDF"
            );


            addMessage(
                data.answer,
                "bot"
            );


            setStatus(
                "Ready"
            );

        }
    )

    .catch(
        error => {

            removeSearchingMessage(
                "Searching the uploaded PDF"
            );


            addMessage(
                "❌ PDF error: " +
                escapeHTML(
                    error.toString()
                ),
                "bot"
            );


            setStatus(
                "Error"
            );

        }
    );

}



// =========================================================
// ASK INTERNET
// =========================================================

function askInternet(question) {

    addMessage(
        "🌐 Searching the Internet...",
        "bot"
    );


    setStatus(
        "Searching Internet..."
    );


    fetch(
        "/ask_internet",
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
    )

    .then(
        response =>
            response.json()
    )

    .then(
        data => {

            removeSearchingMessage(
                "Searching the Internet"
            );


            addMessage(
                data.answer,
                "bot"
            );


            setStatus(
                "Ready"
            );

        }
    )

    .catch(
        error => {

            removeSearchingMessage(
                "Searching the Internet"
            );


            addMessage(
                "❌ Internet error: " +
                escapeHTML(
                    error.toString()
                ),
                "bot"
            );


            setStatus(
                "Internet search error"
            );

        }
    );

}



// =========================================================
// REMOVE SEARCH MESSAGE
// =========================================================

function removeSearchingMessage(
    text
) {

    const messages =
        document.querySelectorAll(
            ".bot-message"
        );


    messages.forEach(
        function (message) {

            if (
                message.innerText.includes(
                    text
                )
            ) {

                message.remove();

            }

        }
    );

}



// =========================================================
// CHATGPT
// =========================================================

function openChatGPT() {

    const input =
        document.getElementById(
            "user-input"
        );


    const question =
        input.value.trim();


    if (question) {

        copyToClipboard(
            question
        );

        alert(
            "Your question has been copied.\n\n" +
            "ChatGPT will open in a new tab.\n" +
            "Paste the question there."
        );

    }


    window.open(
        "https://chatgpt.com/",
        "_blank"
    );

}



// =========================================================
// GEMINI
// =========================================================

function openGemini() {

    const input =
        document.getElementById(
            "user-input"
        );


    const question =
        input.value.trim();


    if (question) {

        copyToClipboard(
            question
        );

        alert(
            "Your question has been copied.\n\n" +
            "Gemini will open in a new tab.\n" +
            "Paste the question there."
        );

    }


    window.open(
        "https://gemini.google.com/",
        "_blank"
    );

}



// =========================================================
// COPY TO CLIPBOARD
// =========================================================

function copyToClipboard(text) {

    if (
        navigator.clipboard &&
        navigator.clipboard.writeText
    ) {

        navigator.clipboard.writeText(
            text
        );

    }

}



// =========================================================
// ENTER KEY
// =========================================================

document
    .getElementById("user-input")
    .addEventListener(
        "keypress",
        function(event) {

            if (
                event.key === "Enter"
            ) {

                sendMessage();

            }

        }
    );