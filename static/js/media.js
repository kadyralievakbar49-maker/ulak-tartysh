(() => {
  const tabs = [...document.querySelectorAll("[data-media-tab]")];
  const panels = [...document.querySelectorAll("[data-media-panel]")];
  const searchForm = document.getElementById("mediaSearchForm");
  const searchInput = document.getElementById("mediaSearchInput");
  const searchEmpty = document.getElementById("mediaSearchEmpty");
  const breadcrumbCurrent = document.getElementById("mediaBreadcrumbCurrent");

  if (!tabs.length || !panels.length || !searchInput) return;

  const validTabs = tabs.map((tab) => tab.dataset.mediaTab);

  function translatedTabName(tabName) {
    const tab = tabs.find((item) => item.dataset.mediaTab === tabName);
    return tab?.textContent.trim() || tabName;
  }

  function filterActivePanel() {
    const activePanel = panels.find((panel) => !panel.hidden);
    if (!activePanel) return;

    const query = searchInput.value.trim().toLocaleLowerCase();
    const items = [...activePanel.querySelectorAll("[data-media-item]")];
    let visibleCount = 0;

    items.forEach((item) => {
      const searchableText = (item.dataset.searchText || item.textContent).toLocaleLowerCase();
      const visible = !query || searchableText.includes(query);
      item.hidden = !visible;
      if (visible) visibleCount += 1;
    });

    searchEmpty.hidden = !query || visibleCount > 0 || items.length === 0;
  }

  function activateTab(tabName, updateHash = true) {
    const nextTab = validTabs.includes(tabName) ? tabName : "photo";

    tabs.forEach((tab) => {
      const active = tab.dataset.mediaTab === nextTab;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });

    panels.forEach((panel) => {
      const active = panel.dataset.mediaPanel === nextTab;
      panel.hidden = !active;
      panel.classList.toggle("active", active);
    });

    if (breadcrumbCurrent) {
      breadcrumbCurrent.textContent = translatedTabName(nextTab);
      breadcrumbCurrent.href = `#${nextTab}`;
      breadcrumbCurrent.setAttribute("aria-current", "page");
    }
    if (updateHash) window.history.replaceState({}, "", `${window.location.pathname}${window.location.search}#${nextTab}`);
    filterActivePanel();
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.mediaTab));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      const direction = event.key === "ArrowRight" ? 1 : -1;
      const nextIndex = (index + direction + tabs.length) % tabs.length;
      tabs[nextIndex].focus();
      activateTab(tabs[nextIndex].dataset.mediaTab);
    });
  });

  searchInput.addEventListener("input", filterActivePanel);
  searchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    filterActivePanel();
  });

  window.addEventListener("hashchange", () => activateTab(window.location.hash.slice(1), false));
  window.addEventListener("site:languagechange", () => {
    const activeTab = tabs.find((tab) => tab.classList.contains("active"));
    if (breadcrumbCurrent && activeTab) breadcrumbCurrent.textContent = activeTab.textContent.trim();
  });

  activateTab(window.location.hash.slice(1), false);
})();
