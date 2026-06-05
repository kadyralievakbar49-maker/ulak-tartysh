      let activeModalType = null;

      function t(key) {
        return window.siteI18n?.t(key) || key;
      }

      const modal = document.querySelector("#modal");
      const modalCard = document.querySelector("#modalCard");
      const modalTitle = document.querySelector("#modalTitle");
      const modalBody = document.querySelector("#modalBody");
      const toast = document.querySelector("#toast");
      const header = document.querySelector(".header");
      const nav = document.querySelector("#nav");
      const drawerOverlay = document.querySelector("#drawerOverlay");
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

      function applyTheme(theme) {
        const normalized = theme === "dark" ? "dark" : "light";
        if (normalized === "dark") {
          document.documentElement.setAttribute("data-theme", "dark");
        } else {
          document.documentElement.removeAttribute("data-theme");
        }
        localStorage.setItem("siteTheme", normalized);
        document.querySelectorAll("[data-theme-toggle], #themeToggle").forEach((toggle) => {
          toggle.textContent = normalized === "dark" ? "☀️" : "🌙";
          toggle.setAttribute("aria-label", normalized === "dark" ? "Жарык темага өтүү" : "Караңгы темага өтүү");
        });
      }

      applyTheme(localStorage.getItem("siteTheme") || "light");

      function showToast(message) {
        if (!toast) return;
        toast.textContent = message;
        toast.classList.add("show");
        window.clearTimeout(showToast.timer);
        showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2600);
      }

      async function normalizeImageFile(file, maxWidth = 1920, maxHeight = 1080, quality = 0.85) {
        if (!file || !file.type.startsWith("image/")) return file;
        if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) return file;

        const bitmap = await createImageBitmap(file);
        const targetRatio = maxWidth / maxHeight;
        const sourceRatio = bitmap.width / bitmap.height;
        let sx = 0;
        let sy = 0;
        let sw = bitmap.width;
        let sh = bitmap.height;

        if (sourceRatio > targetRatio) {
          sw = Math.round(bitmap.height * targetRatio);
          sx = Math.round((bitmap.width - sw) / 2);
        } else if (sourceRatio < targetRatio) {
          sh = Math.round(bitmap.width / targetRatio);
          sy = Math.round((bitmap.height - sh) / 2);
        }

        const scale = Math.min(maxWidth / sw, maxHeight / sh, 1);
        const canvas = document.createElement("canvas");
        canvas.width = Math.round(sw * scale);
        canvas.height = Math.round(sh * scale);
        const context = canvas.getContext("2d");
        context.drawImage(bitmap, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);

        const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
        bitmap.close?.();
        if (!blob) return file;

        const normalizedName = file.name.replace(/\.[^.]+$/, "") + ".jpg";
        return new File([blob], normalizedName, { type: "image/jpeg", lastModified: Date.now() });
      }

      async function normalizeImageInput(input) {
        const file = input.files?.[0];
        if (!file) return;
        try {
          const normalized = await normalizeImageFile(file);
          if (normalized === file) return;
          const transfer = new DataTransfer();
          transfer.items.add(normalized);
          input.files = transfer.files;
          input.dataset.normalized = "true";
        } catch (error) {
          console.error("Image normalization failed:", error);
        }
      }

      window.normalizeImageFile = normalizeImageFile;
      window.normalizeImageInput = normalizeImageInput;

      document.querySelectorAll('input[type="file"][accept*="image"]').forEach((input) => {
        input.addEventListener("change", () => normalizeImageInput(input));
      });

      document.querySelectorAll('input[name="img_url"], input[name="photo_url"], input[name="thumbnail"], input[name="cover_url"]').forEach((input) => {
        input.addEventListener("change", () => {
          input.setCustomValidity("");
        });
      });

      function openModal(title, body, media = false) {
        if (!modal || !modalTitle || !modalBody || !modalCard) return;
        modalTitle.textContent = title;
        modalBody.innerHTML = body;
        modalCard.classList.toggle("modal-media", media);
        modal.classList.add("show");
        document.body.classList.add("locked");
      }

      function closeModal() {
        if (!modal) return;
        modal.classList.remove("show");
        document.body.classList.remove("locked");
        activeModalType = null;
      }

      window.showLoginModal = function showLoginModal() {
        activeModalType = "login";
        openModal(t("loginTitle"), formMarkup("login"));
      };

      window.showRegisterModal = function showRegisterModal() {
        activeModalType = "register";
        openModal(t("registerTitle"), formMarkup("register"));
      };
function formMarkup(type) {
  // === ВХОД ===
  if (type === "login") {
    return `
      <form class="form-grid" data-submit="login">
        <div class="form-field">
          <label for="loginEmail">${t("emailOrPhone")}</label>
          <input id="loginEmail" name="email" type="text" required placeholder="email@example.com" autocomplete="username" />
        </div>
        <div class="form-field">
          <label for="loginPassword">${t("password")}</label>
          <input id="loginPassword" name="password" type="password" required placeholder="••••••••" autocomplete="current-password" />
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin:-10px 0 10px;">
          <label style="font-size:13px;color:var(--muted);display:flex;align-items:center;gap:6px;">
            <input type="checkbox" name="remember" /> ${t("rememberMe")}
          </label>
          <a href="#" style="font-size:13px;color:var(--red);text-decoration:none;" data-action="forgot">${t("forgotPassword")}</a>
        </div>
        <a class="admin-login-link" href="/admin">${t("adminLogin")}</a>
        <div class="modal-actions">
          <button class="ghost" type="button" data-close>${t("close")}</button>
          <button class="primary" type="submit">${t("login")}</button>
        </div>
        <p style="text-align:center;margin-top:16px;font-size:14px;color:var(--muted)">
          ${t("noAccount")} <a href="#" style="color:var(--red);text-decoration:none;" data-open="register">${t("createAccount")}</a>
        </p>
      </form>`;
  }

  // === РЕГИСТРАЦИЯ ===
  if (type === "register") {
    return `
      <form class="form-grid" data-submit="register">
        <div class="form-field">
          <label for="regFullname">${t("fullName")}</label>
          <input id="regFullname" name="fullname" type="text" required placeholder="${t("fullNamePlaceholder")}" autocomplete="name" />
        </div>
        <div class="form-field">
          <label for="regEmail">${t("email")}</label>
          <input id="regEmail" name="email" type="email" required placeholder="email@example.com" autocomplete="email" />
        </div>
        <div class="form-field">
          <label for="regPassword">${t("password")} *</label>
          <input id="regPassword" name="password" type="password" required placeholder="${t("passwordMin")}" minlength="6" autocomplete="new-password" />
        </div>
        <div class="form-field">
          <label for="regConfirm">${t("confirmPassword")}</label>
          <input id="regConfirm" name="confirm_password" type="password" required placeholder="••••••••" autocomplete="new-password" />
        </div>
        <div style="font-size:12px;color:var(--muted);margin:-8px 0 8px">
          <input type="checkbox" id="regTerms" required style="vertical-align:middle;margin-right:4px" />
          <label for="regTerms" style="vertical-align:middle">
            ${t("acceptTermsPrefix")}
          </label>
        </div>
        <div class="modal-actions">
          <button class="ghost" type="button" data-close>${t("close")}</button>
          <button class="primary" type="submit">${t("register")}</button>
        </div>
        <p style="text-align:center;margin-top:16px;font-size:14px;color:var(--muted)">
          ${t("hasAccount")} <a href="#" style="color:var(--red);text-decoration:none;" data-open="login">${t("login")}</a>
        </p>
      </form>`;
  }

  // === БИЛЕТЫ ===
  if (type === "tickets") {
    return `
      <form class="form-grid" data-submit="tickets">
        <div class="form-field"><label>${t("match")}</label><select name="match"><option>Достук - Ынтымак</option><option>Сары-Өзөн - Мурас</option><option>Бакубат - Ак-Суу</option></select></div>
        <div class="form-field"><label>${t("ticketCount")}</label><input name="count" type="number" min="1" max="10" value="2" /></div>
        <div class="form-field"><label>${t("phone")}</label><input name="phone" required placeholder="+996 700 000 000" /></div>
        <div class="form-field"><label>Email</label><input name="email" type="email" placeholder="email@example.com" /></div>
        <div class="modal-actions"><button class="ghost" type="button" data-close>${t("close")}</button><button class="primary" type="submit">${t("booking")}</button></div>
      </form>`;
  }

  // === АНКЕТА ===
  return `
    <form class="form-grid" data-submit="questionnaire">
      <div class="form-field"><label>${t("fullName")}</label><input name="fullname" required placeholder="${t("fullNamePlaceholder")}" /></div>
      <div class="form-field"><label>${t("team")}</label><input name="team" required placeholder="${t("team")}" /></div>
      <div class="form-field"><label>${t("contact")}</label><input name="contact" required placeholder="+996 700 000 000" /></div>
      <div class="modal-actions"><button class="ghost" type="button" data-close>${t("close")}</button><button class="primary" type="submit">${t("send")}</button></div>
    </form>`;
}

      const menuToggle = document.querySelector("#menuToggle");
      function closeDrawer() {
        nav?.classList.remove("open");
        document.body.classList.remove("drawer-open");
      }

      function openDrawer() {
        header?.classList.remove("header-hidden");
        nav?.classList.add("open");
        document.body.classList.add("drawer-open");
      }

      if (menuToggle && nav) {
        menuToggle.addEventListener("click", () => {
          if (nav.classList.contains("open")) {
            closeDrawer();
          } else {
            openDrawer();
          }
        });
      }

      document.querySelectorAll("[data-theme-toggle], #themeToggle").forEach((toggle) => {
        toggle.addEventListener("click", () => {
          const currentTheme = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
          applyTheme(currentTheme === "dark" ? "light" : "dark");
        });
      });

      document.querySelectorAll("[data-close-menu]").forEach((button) => {
        button.addEventListener("click", closeDrawer);
      });
      drawerOverlay?.addEventListener("click", closeDrawer);

      if (header) {
        let lastScrollTop = window.scrollY || document.documentElement.scrollTop || 0;
        const mobileHeaderQuery = window.matchMedia("(max-width: 768px)");

        function syncMobileHeader() {
          const scrollTop = window.scrollY || document.documentElement.scrollTop || 0;

          if (!mobileHeaderQuery.matches || document.body.classList.contains("drawer-open")) {
            header.classList.remove("header-hidden");
            lastScrollTop = scrollTop;
            return;
          }

          if (scrollTop <= 0) {
            header.classList.remove("header-hidden");
          } else if (scrollTop > lastScrollTop && scrollTop > 100) {
            header.classList.add("header-hidden");
          } else if (scrollTop < lastScrollTop) {
            header.classList.remove("header-hidden");
          }

          lastScrollTop = Math.max(scrollTop, 0);
        }

        window.addEventListener("scroll", syncMobileHeader, { passive: true });
        mobileHeaderQuery.addEventListener?.("change", syncMobileHeader);
        syncMobileHeader();
      }

      document.querySelectorAll(".nav a").forEach((link) => {
        link.addEventListener("click", closeDrawer);
      });
      document.querySelectorAll(".dropdown button[data-open]").forEach((button) => {
        button.addEventListener("click", closeDrawer);
      });

      window.addEventListener("site:languagechange", () => {
        if (activeModalType) {
          const titles = {
            login: t("loginTitle"),
            register: t("registerTitle"),
            tickets: t("ticketsTitle"),
            questionnaire: t("questionnaire"),
          };
          openModal(titles[activeModalType], formMarkup(activeModalType));
        }
      });

      document.querySelectorAll("[data-filter]").forEach((button) => {
        button.addEventListener("click", () => {
          document.querySelectorAll("[data-filter]").forEach((item) => item.classList.remove("active"));
          button.classList.add("active");
          const filter = button.dataset.filter;
          document.querySelectorAll(".match").forEach((match) => {
            match.classList.toggle("hidden", filter !== "all" && match.dataset.league !== filter);
          });
        });
      });

      const searchForm = document.querySelector("#searchForm");
      if (searchForm) {
        searchForm.addEventListener("submit", (event) => {
          event.preventDefault();
          const query = document.querySelector("#searchInput").value.trim();
          window.location.href = `/search?q=${encodeURIComponent(query)}`;
        });
      }

      const newsRing = document.querySelector("[data-news-ring]");
      const newsTrack = document.querySelector(".news-carousel-track");
      let newsPosition = 0;
      let newsInterval = null;
      let newsTouchStartX = 0;
      let newsTouchEndX = 0;

      function getNewsCardsPerView() {
        if (window.innerWidth <= 600) return 1;
        if (window.innerWidth <= 1200) return 2;
        return 3;
      }

      function applyNewsRingTransform() {
        if (!newsTrack) return;
        const cards = newsTrack.querySelectorAll(".news-card-compact");
        if (!cards.length) return;
        const gap = Number.parseFloat(getComputedStyle(newsTrack).gap) || 20;
        const cardWidth = cards[0].getBoundingClientRect().width + gap;
        newsTrack.style.transform = `translateX(-${newsPosition * cardWidth}px)`;
      }

      function startNewsAutoPlay() {
        window.clearInterval(newsInterval);
        if (!newsTrack || newsTrack.querySelectorAll(".news-card-compact").length <= getNewsCardsPerView()) return;
        newsInterval = window.setInterval(() => window.moveNews(1), 4000);
      }

      function resetNewsAutoPlay() {
        window.clearInterval(newsInterval);
        startNewsAutoPlay();
      }

      window.moveNews = function moveNews(direction) {
        if (!newsTrack) return;
        const cards = newsTrack.querySelectorAll(".news-card-compact");
        const totalCards = Math.max(1, Math.floor(cards.length / 2));
        if (!cards.length) return;

        newsPosition += direction;
        if (newsPosition >= totalCards) newsPosition = 0;
        if (newsPosition < 0) newsPosition = totalCards - 1;

        applyNewsRingTransform();
        resetNewsAutoPlay();
      };

      if (newsRing && newsTrack) {
        newsRing.addEventListener("mouseenter", () => window.clearInterval(newsInterval));
        newsRing.addEventListener("mouseleave", startNewsAutoPlay);
        newsTrack.addEventListener("touchstart", (event) => {
          newsTouchStartX = event.changedTouches[0].screenX;
          window.clearInterval(newsInterval);
        }, { passive: true });
        newsTrack.addEventListener("touchend", (event) => {
          newsTouchEndX = event.changedTouches[0].screenX;
          if (newsTouchEndX < newsTouchStartX - 50) window.moveNews(1);
          if (newsTouchEndX > newsTouchStartX + 50) window.moveNews(-1);
          startNewsAutoPlay();
        }, { passive: true });
        window.addEventListener("resize", () => {
          newsPosition = 0;
          applyNewsRingTransform();
          resetNewsAutoPlay();
        });
        applyNewsRingTransform();
        startNewsAutoPlay();
      }

      document.addEventListener("click", (event) => {
        const target = event.target.closest("button, a");
        if (!target) return;

        if (target.dataset.open) {
  event.preventDefault();
  closeDrawer();
  const type = target.dataset.open;
  const titles = { 
    login: t("loginTitle"), 
    register: t("registerTitle"), 
    tickets: t("ticketsTitle"), 
    questionnaire: t("questionnaire") 
  };
  activeModalType = type;
  openModal(titles[type], formMarkup(type));
  return;
}
        if (target.dataset.match) {
          openModal(
            target.dataset.match,
            `<p><strong>${target.dataset.match}</strong> беттеши боюнча маалымат.</p>
             <p>Өтчү күнү: Календардан караңыз. Дареги: Бишкек Реалдуу убакытта билеттерди азыр брондосо болот.</p>
             <div class="modal-actions"><button class="primary" data-open="tickets">Билет алуу</button></div>`
          );
        }

        if (target.dataset.news) {
          openModal(
            target.dataset.news,
            `<p>Бул бөлүм жаңылыктын толук текстин көрсөтөт. Бэкендге кошулгандан кийин маалыматтар ушул жерде жаңыртылат.</p>`
          );
        }

        if (target.dataset.image) {
          openModal("Галерея", `<img src="${target.dataset.image}" alt="Галерея" />`, true);
        }

        if (target.dataset.action) {
          if (target.dataset.action === "subscribe") {
            openModal(
              "Жаңылыктарга жазылуу",
              `<form class="form-grid" data-submit="subscribe">
                <div class="form-field"><label>Email</label><input name="email" type="email" required placeholder="you@example.com" /></div>
                <div class="modal-actions"><button class="ghost" type="button" data-close>Жабуу</button><button class="primary" type="submit">Жазылуу</button></div>
              </form>`
            );
          } else {
            const messages = {
              calendar: "Календарь жүктөө даяр.",
              gallery: "Галерея үчүн сүрөттү басыңыз.",
              rating: "Рейтинг бөлүмү көрсөтүлдү.",
            };
            showToast(messages[target.dataset.action]);
          }
        }

        if (target.hasAttribute("data-close")) closeModal();
      });

      modal?.addEventListener("click", (event) => { if (event.target === modal) closeModal(); });
      document.querySelector("#modalClose")?.addEventListener("click", closeModal);
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
          closeModal();
          closeDrawer();
        }
      });

      // ПЕРЕДАЧА ДАННЫХ НА PYTHON FLASK ЧЕРЕЗ FETCH API
      document.addEventListener("submit", (event) => {
        const form = event.target.closest("[data-submit]");
        if (!form) return;
        event.preventDefault();

        const formType = form.dataset.submit;
        const formData = new FormData(form);
        const payload = Object.fromEntries(formData.entries());

        const endpoint = formType === "register" ? "/api/register" : "/api/submit";

        fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
          body: JSON.stringify({ form_type: formType, payload: payload })
        })
        .then(response => response.json().then(data => ({ ok: response.ok, data })))
        .then(({ ok, data }) => {
          if (!ok || data.status === "error") {
            showToast(data.message || "Ката кетти.");
            return;
          }

          if (data.reload) {
            showToast(data.message);
            window.setTimeout(() => window.location.reload(), 700);
            return;
          }

          closeModal();
          showToast(data.message);
        })
        .catch(error => {
          console.error("Ката кетти:", error);
          showToast("Байланыш катасы келип чыкты.");
        });
      });
      /* ===== HERO SLIDER AUTO-ROTATION ===== */
document.addEventListener('DOMContentLoaded', () => {
  const slides = document.querySelectorAll('.hero-slider .slide');
  if (slides.length <= 1) return;

  let current = 0;
  let intervalId = setInterval(nextSlide, 5000);

  function nextSlide() {
    slides[current].classList.remove('active');
    current = (current + 1) % slides.length;
    slides[current].classList.add('active');
  }

  // Пауза при наведении мыши
  const heroSlider = document.querySelector('.hero-slider');
  if (heroSlider) {
    heroSlider.addEventListener('mouseenter', () => clearInterval(intervalId));
    heroSlider.addEventListener('mouseleave', () => {
      intervalId = setInterval(nextSlide, 5000);
    });
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const animatedSections = document.querySelectorAll("main > section, .footer");
  const observerOptions = {
    threshold: 0.1,
    rootMargin: "0px 0px -100px 0px",
  };

  const revealObserver = "IntersectionObserver" in window
    ? new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            revealObserver.unobserve(entry.target);
          }
        });
      }, observerOptions)
    : null;

  animatedSections.forEach((section) => {
    section.classList.add("fade-in");
    if (revealObserver && !reduceMotion) {
      revealObserver.observe(section);
    } else {
      section.classList.add("visible");
    }
  });

  const hero = document.querySelector(".hero-slider");
  const heroSlides = document.querySelector(".slides-container");
  if (hero && heroSlides && !reduceMotion) {
    window.addEventListener("scroll", () => {
      const offset = Math.min(window.pageYOffset * 0.18, 120);
      heroSlides.style.transform = `translate3d(0, ${offset}px, 0)`;
    }, { passive: true });
  }

  document.querySelectorAll(".primary, .secondary, .btn-primary, .btn-outline, .ghost").forEach((button) => {
    button.classList.add("magnetic-btn");
  });

  if (!reduceMotion) {
    document.querySelectorAll(".magnetic-btn").forEach((button) => {
      button.addEventListener("mousemove", (event) => {
        const rect = button.getBoundingClientRect();
        const x = event.clientX - rect.left - rect.width / 2;
        const y = event.clientY - rect.top - rect.height / 2;
        button.style.transform = `translate(${x * 0.18}px, ${y * 0.18}px)`;
      });

      button.addEventListener("mouseleave", () => {
        button.style.transform = "";
      });
    });
  }

  function animateCounter(element, target, duration = 2000) {
    let start = 0;
    const increment = target / (duration / 16);
    const timer = window.setInterval(() => {
      start += increment;
      if (start >= target) {
        element.textContent = target;
        window.clearInterval(timer);
      } else {
        element.textContent = Math.floor(start);
      }
    }, 16);
  }

  if ("IntersectionObserver" in window && !reduceMotion) {
    document.querySelectorAll(".stat-number").forEach((stat) => {
      const target = Number(stat.dataset.target || stat.textContent);
      if (!Number.isFinite(target)) return;
      stat.textContent = "0";
      const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            animateCounter(entry.target, target);
            counterObserver.unobserve(entry.target);
          }
        });
      }, { threshold: 0.5 });
      counterObserver.observe(stat);
    });
  }

  if (hero && !reduceMotion && !hero.querySelector(".particles")) {
    const particlesContainer = document.createElement("div");
    particlesContainer.className = "particles";
    hero.appendChild(particlesContainer);

    for (let index = 0; index < 20; index += 1) {
      const particle = document.createElement("span");
      particle.className = "particle";
      particle.style.left = `${Math.random() * 100}%`;
      particle.style.animationDelay = `${Math.random() * 20}s`;
      particle.style.animationDuration = `${Math.random() * 20 + 10}s`;
      particlesContainer.appendChild(particle);
    }
  }

  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", (event) => {
      const target = document.querySelector(anchor.getAttribute("href"));
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    });
  });

  const profileForm = document.querySelector("#profileUpdateForm");
  profileForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(profileForm);
    const payload = Object.fromEntries(formData.entries());
    try {
      const response = await fetch("/api/profile/update", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      alert(data.message || "Жооп алынды.");
      if (response.ok && data.status === "success") {
        window.location.reload();
      }
    } catch (error) {
      console.error(error);
      alert("Байланыш катасы.");
    }
  });

  const passwordForm = document.querySelector("#passwordChangeForm");
  passwordForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(passwordForm);
    const payload = Object.fromEntries(formData.entries());
    try {
      const response = await fetch("/api/profile/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      alert(data.message || "Жооп алынды.");
      if (response.ok && data.status === "success") {
        passwordForm.reset();
      }
    } catch (error) {
      console.error(error);
      alert("Байланыш катасы.");
    }
  });

  let deferredInstallPrompt = null;
  const installButton = document.querySelector("#installAppBtn");

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    installButton?.classList.add("show");
  });

  installButton?.addEventListener("click", async () => {
    if (!deferredInstallPrompt) return;
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    installButton.classList.remove("show");
  });

  window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    installButton?.classList.remove("show");
  });

  document.querySelectorAll(".copy-contact").forEach((button) => {
    button.addEventListener("click", async () => {
      const value = button.dataset.copy || "";
      try {
        await navigator.clipboard.writeText(value);
        button.textContent = "Көчүрүлдү";
        window.setTimeout(() => {
          button.textContent = "Көчүрүү";
        }, 1600);
      } catch (error) {
        console.error(error);
        alert(value);
      }
    });
  });
});
