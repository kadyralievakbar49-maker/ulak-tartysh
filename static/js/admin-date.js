(() => {
  const nativeInputs = document.querySelectorAll('input[type="date"]');
  if (!nativeInputs.length) return;

  function isIsoDate(value) {
    return /^\d{4}-\d{2}-\d{2}$/.test(value);
  }

  function isoToDisplay(value) {
    if (!isIsoDate(value)) return value || "";
    const [year, month, day] = value.split("-");
    return `${day}.${month}.${year}`;
  }

  function normalizeDisplayValue(value) {
    const trimmed = value.trim();
    if (/^\d{8}$/.test(trimmed)) {
      return `${trimmed.slice(0, 2)}.${trimmed.slice(2, 4)}.${trimmed.slice(4)}`;
    }
    return trimmed;
  }

  function displayToIso(value) {
    const normalized = normalizeDisplayValue(value);
    if (!normalized) return "";
    if (isIsoDate(normalized)) return normalized;

    const match = normalized.match(/^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$/);
    if (!match) return null;

    const day = Number(match[1]);
    const month = Number(match[2]);
    const year = Number(match[3]);
    if (year < 1900 || year > 2100) return null;

    const date = new Date(year, month - 1, day);
    const isValid =
      date.getFullYear() === year &&
      date.getMonth() === month - 1 &&
      date.getDate() === day;

    if (!isValid) return null;
    return `${year.toString().padStart(4, "0")}-${month.toString().padStart(2, "0")}-${day.toString().padStart(2, "0")}`;
  }

  nativeInputs.forEach((nativeInput) => {
    const displayInput = document.createElement("input");
    const originalValue = nativeInput.value;

    displayInput.type = "text";
    displayInput.className = nativeInput.className;
    displayInput.value = isoToDisplay(originalValue);
    displayInput.placeholder = "дд.мм.гггг";
    displayInput.inputMode = "numeric";
    displayInput.autocomplete = "off";
    displayInput.required = nativeInput.required;
    displayInput.disabled = nativeInput.disabled;
    displayInput.readOnly = nativeInput.readOnly;
    displayInput.setAttribute("aria-label", nativeInput.getAttribute("aria-label") || "Дата");

    nativeInput.type = "hidden";
    nativeInput.required = false;
    nativeInput.after(displayInput);

    function syncDate() {
      const isoValue = displayToIso(displayInput.value);
      if (isoValue === null) {
        displayInput.setCustomValidity("Введите дату в формате дд.мм.гггг");
        return false;
      }
      displayInput.setCustomValidity("");
      nativeInput.value = isoValue;
      return true;
    }

    displayInput.addEventListener("input", syncDate);
    displayInput.addEventListener("blur", () => {
      const isoValue = displayToIso(displayInput.value);
      if (isoValue) displayInput.value = isoToDisplay(isoValue);
      syncDate();
    });

    displayInput.form?.addEventListener("submit", (event) => {
      if (!syncDate()) {
        event.preventDefault();
        displayInput.reportValidity();
      }
    });
  });
})();
