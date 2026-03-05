const defaultBaseUrl = "https://compliance-bot-production.up.railway.app";

const el = (id) => document.getElementById(id);
const statusEl = el("status");

// =======================
// Basic Auth (Method 3)
// =======================
let basicUser = "";
let basicPass = "";

function getAuthHeader() {
    if (!basicUser || !basicPass) {
        basicUser = prompt("API Username:") || "";
        basicPass = prompt("API Password:") || "";
    }
    const token = btoa(`${basicUser}:${basicPass}`);
    return `Basic ${token}`;
}

// Initialization
el("baseUrl").value = defaultBaseUrl;
el("baseUrlText").textContent = defaultBaseUrl;

// Event Listeners
el("baseUrl").addEventListener("input", () => {
    el("baseUrlText").textContent = el("baseUrl").value.trim() || defaultBaseUrl;
});

// Chat UI Event Listeners
const uploadBtn = el("uploadTriggerBtn");
const adImage = el("adImage");
const imagePreviewContainer = el("imagePreviewContainer");
const imagePreview = el("imagePreview");
const removeImageBtn = el("removeImageBtn");

if (uploadBtn && adImage) {
    uploadBtn.addEventListener("click", () => {
        adImage.click();
    });
    adImage.addEventListener("change", () => {
        if (adImage.files && adImage.files.length > 0) {
            uploadBtn.classList.add("primary");

            const file = adImage.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    if (imagePreview) imagePreview.src = e.target.result;
                    if (imagePreviewContainer) imagePreviewContainer.style.display = "block";
                };
                reader.readAsDataURL(file);
            }
        } else {
            uploadBtn.classList.remove("primary");
            if (imagePreviewContainer) imagePreviewContainer.style.display = "none";
            if (imagePreview) imagePreview.src = "";
        }
    });
}

if (removeImageBtn) {
    removeImageBtn.addEventListener("click", () => {
        if (adImage) adImage.value = "";
        if (imagePreviewContainer) imagePreviewContainer.style.display = "none";
        if (imagePreview) imagePreview.src = "";
        if (uploadBtn) uploadBtn.classList.remove("primary");
    });
}

const adText = el("adText");
if (adText) {
    adText.addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = (this.scrollHeight) + "px";
    });

    adText.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            el("analyzeBtn").click();
        }
    });
}

el("fillCase1Btn").addEventListener("click", () => {
    el("adText").value = "Everything is cheap. Limited time offer. No conditions apply.";
});

el("clearBtn").addEventListener("click", () => {
    el("adText").value = "";
    el("adImage").value = "";
    if (el("uploadTriggerBtn")) el("uploadTriggerBtn").classList.remove("primary");

    const previewCont = el("imagePreviewContainer");
    if (previewCont) previewCont.style.display = "none";
    const previewImg = el("imagePreview");
    if (previewImg) previewImg.src = "";

    statusEl.textContent = "";
    el("resultArea").style.display = "none";
    const ws = el("welcomeScreen");
    if (ws) ws.style.display = "flex";
});

const newChatBtn = el("newChatBtn");
if (newChatBtn) {
    newChatBtn.addEventListener("click", () => el("clearBtn").click());
}

el("analyzeBtn").addEventListener("click", async () => {

    const baseUrl = (el("baseUrl").value.trim() || defaultBaseUrl).replace(/\/+$/, "");
    const adText = el("adText").value || "";
    const file = el("adImage").files && el("adImage").files[0];

    el("adText").value = "";
    el("adText").style.height = "auto";
    el("adImage").value = "";
    if (el("uploadTriggerBtn")) el("uploadTriggerBtn").classList.remove("primary");

    const previewCont = el("imagePreviewContainer");
    if (previewCont) previewCont.style.display = "none";
    const previewImg = el("imagePreview");
    if (previewImg) previewImg.src = "";

    setStatus("Analyzing...", "");
    el("resultArea").style.display = "none";
    const ws = el("welcomeScreen");
    if (ws) ws.style.display = "none";

    try {

        let data;

        if (file) {
            const form = new FormData();
            form.append("ad_text", adText);
            form.append("image", file);
            data = await postForm(`${baseUrl}/analyze_multimodal`, form);
        } else {
            if (!adText.trim()) {
                throw new Error("Please provide at least ad text or an image.");
            }
            data = await postJson(`${baseUrl}/analyze`, {
                ad_text: adText
            });
        }

        const result = data.result;

        el("overallScore").textContent = result.overall_score ?? "--";
        riskToPill(result.risk_level || "");

        //  flag issue 
        const issueCount = (result.flagged_issues || []).length;

        if (issueCount > 0) {
            el("summaryNote").textContent = `⚠ ${issueCount} issues detected across compliance categories.`;
        } else {
            el("summaryNote").textContent = "✓ No compliance issues detected.";
        }

        renderCategories(result.category_breakdown);
        renderIssues(result.flagged_issues);
        renderRewrite(result.rewrite_suggestions);
        renderImageSummary(data.image_summary);

        const resArea = el("resultArea");
        resArea.style.display = "block";
        resArea.classList.add("fade-in");

        setStatus("Done.", "ok");

    } catch (err) {
        console.error(err);
        setStatus(`Error: ${err.message}`, "err");
    }
});

function setStatus(msg, type = "") {
    statusEl.className = "muted " + (type === "err" ? "danger" : type === "ok" ? "success" : "");
    statusEl.textContent = msg;
}

function riskToPill(riskLevel) {
    const pill = el("riskPill");
    pill.textContent = riskLevel || "Risk";
    pill.className = "pill";
    if (!riskLevel) {
        pill.classList.add("default");
        return;
    }
    const r = riskLevel.toLowerCase();
    if (r.includes("low")) pill.classList.add("low");
    else if (r.includes("medium")) pill.classList.add("med");
    else if (r.includes("high")) pill.classList.add("high");
    else pill.classList.add("default");
}

function renderCategories(breakdown) {
    const wrap = el("categories");
    wrap.innerHTML = "";
    (breakdown || []).forEach(item => {
        const score = Number(item.score ?? 0);
        const pct = Math.max(0, Math.min(100, (score / 25) * 100));
        const div = document.createElement("div");
        div.style.marginTop = "14px";
        div.innerHTML = `
          <div style="display:flex; justify-content:space-between; gap:10px; font-size:14px; margin-bottom:6px;">
            <div style="font-weight:500;">${item.category}</div>
            <div class="muted">${score} / 25</div>
          </div>
          <div class="bar-bg"><div class="bar-fill" style="width:${pct}%"></div></div>
        `;
        wrap.appendChild(div);
    });
}

function renderIssues(issues) {

    const wrap = el("issues");
    wrap.innerHTML = "";

    if (!issues || issues.length === 0) {
        el("noIssues").style.display = "block";
        return;
    }

    el("noIssues").style.display = "none";

    const severityRank = {
        HIGH: 3,
        MEDIUM: 2,
        LOW: 1
    };

    issues.sort((a, b) => {
        return (severityRank[b.severity?.toUpperCase()] || 0) -
               (severityRank[a.severity?.toUpperCase()] || 0);
    });

    issues.forEach(it => {

        const d = document.createElement("div");
        d.className = "card";

        d.innerHTML = `
          <h4 style="font-size:15px; margin-bottom:8px;">
          ${it.issue_id || "ISSUE"} — ${it.category || ""}
          </h4>

          <div class="muted" style="margin-bottom:8px; display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
            <span class="pill danger" style="font-size:11px;">
            ${(it.severity || "").toUpperCase()}
            </span>

            <span><b>Law:</b> ${it.law || ""}</span>

            <span style="color:#cbd5e1;">|</span>

            <span><b>Section:</b> ${it.section || ""}</span>
          </div>

          <div style="font-size:14px; margin-bottom:6px;">
          <b>Explanation:</b> ${it.explanation || ""}
          </div>

          <div style="font-size:14px; color:var(--text-muted);">
          <b>Evidence:</b> <i>${it.evidence || ""}</i>
          </div>
        `;

        wrap.appendChild(d);

    });

}

function renderRewrite(rewrite) {

    const ul = el("saferAlternatives");
    ul.innerHTML = "";

    (rewrite?.safer_alternatives || []).forEach(x => {

        const li = document.createElement("li");
        li.textContent = x;
        li.style.marginBottom = "6px";
        ul.appendChild(li);

    });

    el("rewriteExplanation").textContent = rewrite?.rewrite_explanation || "";

    el("copyRewriteBtn").onclick = async () => {

        const bullets = rewrite?.safer_alternatives || [];
        if (!bullets.length) return;

        const txt = bullets.map(b => "- " + b).join("\n");

        await navigator.clipboard.writeText(txt);

        setStatus("Copied rewrite suggestions.", "ok");

    };

}

function renderImageSummary(img) {

    const hasImg = img && (img.extracted_text || (img.potential_risk_signals && img.potential_risk_signals.length));

    el("imageCard").style.display = hasImg ? "block" : "none";

    if (!hasImg) return;

    el("imgExtractedText").textContent = img.extracted_text || "";

    const ul = el("imgRiskSignals");
    ul.innerHTML = "";

    (img.potential_risk_signals || []).forEach(s => {

        const li = document.createElement("li");
        li.textContent = s;
        li.style.marginBottom = "4px";
        ul.appendChild(li);

    });

}

async function postJson(url, payload) {

    const res = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": getAuthHeader()
        },
        body: JSON.stringify(payload)
    });

    const text = await res.text();

    if (!res.ok) throw new Error(text || `HTTP ${res.status}`);

    return JSON.parse(text);

}

async function postForm(url, formData) {

    const res = await fetch(url, {
        method: "POST",
        headers: {
            "Authorization": getAuthHeader()
        },
        body: formData
    });

    const text = await res.text();

    if (!res.ok) throw new Error(text || `HTTP ${res.status}`);

    return JSON.parse(text);

}
