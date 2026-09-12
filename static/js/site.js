// Витрина: модалка заявки, маска телефона (IMask), UTM-метки. Загружается на каждой
// странице (templates/base.html) — калькулятор (Chart.js) вынесен в отдельный
// static/js/calculator.js, который грузит только лендинг (templates/index.html,
// extra_scripts): на карточке авто калькулятора нет, и незачем тянуть туда Chart.js.
// Ванильный JS без сборки — этот файл раздаётся как есть, минификации не требует (в
// отличие от CSS, которую собирает Tailwind).
(function () {
  "use strict";

  const LEAD_SUBMIT_URL = "/leads/submit/";
  const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign"];

  function readAndStoreUtm() {
    const params = new URLSearchParams(window.location.search);
    UTM_KEYS.forEach((key) => {
      const value = params.get(key);
      if (value) {
        try {
          sessionStorage.setItem(key, value);
        } catch {
          /* приватный режим / хранилище недоступно — просто не запоминаем между страницами */
        }
      }
    });
  }

  function storedUtm(key) {
    try {
      return sessionStorage.getItem(key) || "";
    } catch {
      return "";
    }
  }

  function initLeadModal() {
    const modal = document.querySelector("[data-lead-modal]");
    if (!modal) return;

    const form = modal.querySelector("[data-lead-form]");
    const carNameField = modal.querySelector("[data-lead-car-name]");
    const resultEl = modal.querySelector("[data-lead-result]");
    const submitBtn = modal.querySelector("[data-lead-submit]");
    const titleEl = modal.querySelector("[data-lead-title]");
    const defaultTitle = titleEl ? titleEl.textContent : "";

    function open(carName) {
      carNameField.value = carName || "";
      // textContent, не innerHTML: carName приходит из data-атрибута карточки
      // авто (в конечном счёте — из CRM), не должен трактоваться как разметка.
      if (titleEl) titleEl.textContent = carName ? `Заявка на ${carName}` : defaultTitle;
      modal.querySelectorAll("[data-lead-utm]").forEach((input) => {
        input.value = storedUtm(input.dataset.leadUtm);
      });
      resultEl.classList.add("hidden");
      modal.classList.remove("hidden");
      modal.classList.add("flex");
      document.body.style.overflow = "hidden";
      const nameInput = form.querySelector("#lead-name");
      if (nameInput) nameInput.focus();
    }

    function close() {
      modal.classList.add("hidden");
      modal.classList.remove("flex");
      document.body.style.overflow = "";
    }

    document.querySelectorAll("[data-open-lead-modal]").forEach((trigger) => {
      trigger.addEventListener("click", () => open(trigger.dataset.carName || ""));
    });
    modal.querySelectorAll("[data-close-lead-modal]").forEach((el) => {
      el.addEventListener("click", close);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.classList.contains("hidden")) close();
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      submitBtn.disabled = true;
      resultEl.classList.add("hidden");
      try {
        const response = await fetch(LEAD_SUBMIT_URL, { method: "POST", body: new FormData(form) });
        const data = await response.json();
        resultEl.textContent = data.message || (response.ok ? "Заявка отправлена." : "Не получилось отправить заявку.");
        resultEl.classList.remove("hidden", "bg-emerald-400/10", "text-emerald-400", "bg-red-500/10", "text-red-400");
        resultEl.classList.add(...(response.ok ? ["bg-emerald-400/10", "text-emerald-400"] : ["bg-red-500/10", "text-red-400"]));
        if (response.ok) form.reset();
      } catch {
        resultEl.textContent = "Не получилось связаться с сервером. Проверьте соединение и попробуйте ещё раз.";
        resultEl.classList.remove("hidden");
        resultEl.classList.add("bg-red-500/10", "text-red-400");
      } finally {
        submitBtn.disabled = false;
      }
    });

    const phoneInput = form.querySelector("[data-phone-input]");
    if (phoneInput && window.IMask) {
      window.IMask(phoneInput, { mask: "+{7} 000 000-00-00" });
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    readAndStoreUtm();
    initLeadModal();
  });
})();
