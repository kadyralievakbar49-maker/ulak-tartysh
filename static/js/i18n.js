(() => {
  const supportedLangs = ["kg", "ru", "en"];
  const dictionary = typeof translations === "undefined" ? { kg: {} } : translations;

  function getInitialLang() {
    const urlLang = new URLSearchParams(window.location.search).get("lang");
    const savedLang = localStorage.getItem("siteLang");
    if (supportedLangs.includes(urlLang)) return urlLang;
    if (supportedLangs.includes(savedLang)) return savedLang;
    return supportedLangs.includes(document.documentElement.lang) ? document.documentElement.lang : "kg";
  }

  let currentLang = getInitialLang();

  function t(key) {
    return dictionary[currentLang]?.[key] || dictionary.kg?.[key] || key;
  }

  function applyTranslations(lang = currentLang) {
    if (!supportedLangs.includes(lang)) return;
    currentLang = lang;
    document.documentElement.lang = lang;
    localStorage.setItem("siteLang", lang);

    document.querySelectorAll(".lang-btn").forEach((item) => {
      const itemLang = item.dataset.lang || new URL(item.href, window.location.href).searchParams.get("lang");
      item.dataset.lang = itemLang;
      item.classList.toggle("active", itemLang === lang);
    });

    Object.entries(dictionary[lang] || {}).forEach(([key, value]) => {
      document.querySelectorAll(`[data-i18n="${key}"]`).forEach((el) => {
        el.textContent = value;
      });
      document.querySelectorAll(`[data-i18n-placeholder="${key}"]`).forEach((el) => {
        el.setAttribute("placeholder", value);
      });
      document.querySelectorAll(`[data-i18n-title="${key}"]`).forEach((el) => {
        el.setAttribute("title", value);
      });
      document.querySelectorAll(`[data-i18n-aria-label="${key}"]`).forEach((el) => {
        el.setAttribute("aria-label", value);
      });
    });

    window.dispatchEvent(new CustomEvent("site:languagechange", { detail: { lang } }));
  }

  function bindLanguageButtons() {
    document.querySelectorAll(".lang-btn").forEach((button) => {
      const lang = button.dataset.lang || new URL(button.href, window.location.href).searchParams.get("lang");
      button.dataset.lang = lang;
      button.addEventListener("click", (event) => {
        event.preventDefault();
        applyTranslations(lang);
        const url = new URL(window.location.href);
        url.searchParams.set("lang", lang);
        window.history.replaceState({}, "", url);
      });
    });
  }

  window.siteI18n = {
    applyTranslations,
    getCurrentLang: () => currentLang,
    t,
  };

  bindLanguageButtons();
  applyTranslations(currentLang);
})();
