// ===== RENDER ROOT LAYOUT =====
export function renderLayout() {
    const app = document.getElementById("app");
    app.innerHTML = `
        <div class="screen">
            <div class="top-bar">
                <button class="btn-outline" id="homeBtn">الرئيسية</button>
            </div>
            <div id="content"></div>
            <div class="mic-indicator" id="micIndicator">
                <i class="fas fa-microphone"></i>
            </div>
        </div>
    `;
    const homeBtn = document.getElementById('homeBtn');
    if (homeBtn) {
        // Use the globally exposed function from app.js
        homeBtn.onclick = () => {
            if (window.resetToInitial) window.resetToInitial();
        };
    }
}

// ===== INITIAL SCREEN =====
export function renderInitialScreen() {
    const content = document.getElementById("content");
    content.innerHTML = `
        <div class="initial-screen" style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; text-align: center;">
            <h2 style="color: #ff7849;">تحدث مع عنّاق</h2>
            <p style="margin-top: 20px; opacity: 0.7;">الميكروفون يعمل تلقائياً. تحدث وسيقوم عنّاق بالرد.</p>
        </div>
    `;
}

// ===== CAROUSEL VIEW =====
export function renderCarousel(recommendations) {
    const content = document.getElementById("content");
    content.innerHTML = `
        <div class="carousel-view">
            <div class="carousel" id="carousel">
                ${recommendations.map((rec, i) => `
                    <div class="card ${i === 1 ? "active" : ""}" data-id="${rec.id}">
                        <img src="${rec.image || 'https://via.placeholder.com/300'}" />
                        <div class="card-text">
                            <h2>${rec.name}</h2>
                        </div>
                    </div>
                `).join("")}
            </div>
            <button class="btn-outline center-btn" id="showAllBtn">جميع الاقتراحات</button>
        </div>
    `;
}

// ===== DETAILS VIEW =====
export function renderDetails(rec) {
    const content = document.getElementById("content");
    content.innerHTML = `
        <div class="details-view">
            <div class="details-card">
                <div class="images">
                    ${rec.images ? rec.images.map(img => `<img src="${img}" />`).join("") : ''}
                </div>
                <div class="text">
                    <h1>${rec.title}</h1>
                    <p>${rec.description}</p>
                    <button class="btn-outline">فتح في الخريطة</button>
                </div>
            </div>
            <button class="btn-outline center-btn" id="backBtn">رجوع</button>
        </div>
    `;
}

// ===== LIST VIEW =====
export function renderList(recommendations) {
    const content = document.getElementById("content");
    content.innerHTML = `
        <div class="list-view">
            <h1 class="title">جميع الاقتراحات</h1>
            ${recommendations.map(rec => `
                <div class="list-card" data-id="${rec.id}">
                    <div class="qr">QR</div>
                    <div class="text">
                        <h2>${rec.name}</h2>
                        <span>${rec.type || ""}</span>
                    </div>
                    <img src="${rec.image || 'https://via.placeholder.com/80'}" />
                </div>
            `).join("")}
        </div>
    `;
}