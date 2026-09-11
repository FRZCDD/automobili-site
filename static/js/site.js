// Витрина: модалка заявки, маска телефона (IMask), калькулятор (Chart.js). Ванильный
// JS без сборки — этот файл раздаётся как есть, минификации не требует (в отличие
// от CSS, которую собирает Tailwind).
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

  function annuityMonthlyPayment(principal, annualRatePercent, termMonths) {
    if (principal <= 0 || termMonths <= 0) return 0;
    const monthlyRate = annualRatePercent / 100 / 12;
    if (monthlyRate === 0) return principal / termMonths;
    const factor = Math.pow(1 + monthlyRate, termMonths);
    return (principal * monthlyRate * factor) / (factor - 1);
  }

  function formatRub(value) {
    return Math.round(value).toLocaleString("ru-RU");
  }

  function initCalculator() {
    const root = document.querySelector("[data-calculator]");
    if (!root) return;

    const config = {
      annualRate: parseFloat(root.dataset.annualRate),
      price: { min: +root.dataset.priceMin, max: +root.dataset.priceMax, step: +root.dataset.priceStep, def: +root.dataset.priceDefault },
      down: { min: +root.dataset.downMin, max: +root.dataset.downMax, step: +root.dataset.downStep, def: +root.dataset.downDefault },
      term: { min: +root.dataset.termMin, max: +root.dataset.termMax, step: +root.dataset.termStep, def: +root.dataset.termDefault },
    };

    const priceInput = root.querySelector("[data-calc-price]");
    const downInput = root.querySelector("[data-calc-down]");
    const termInput = root.querySelector("[data-calc-term]");
    [
      [priceInput, config.price],
      [downInput, config.down],
      [termInput, config.term],
    ].forEach(([input, range]) => {
      input.min = range.min;
      input.max = range.max;
      input.step = range.step;
      input.value = range.def;
    });

    const priceValueEl = root.querySelector("[data-calc-price-value]");
    const downValueEl = root.querySelector("[data-calc-down-value]");
    const termValueEl = root.querySelector("[data-calc-term-value]");
    const monthlyEl = root.querySelector("[data-calc-monthly]");
    const principalEl = root.querySelector("[data-calc-principal]");
    const overpayEl = root.querySelector("[data-calc-overpay]");
    const canvas = root.querySelector("[data-calc-chart]");

    let chart = null;
    if (canvas && window.Chart) {
      chart = new window.Chart(canvas, {
        type: "doughnut",
        data: {
          labels: ["Сумма кредита", "Переплата"],
          datasets: [{ data: [1, 0], backgroundColor: ["#3B82F6", "#1E293B"], borderWidth: 0 }],
        },
        options: { cutout: "72%", plugins: { legend: { display: false }, tooltip: { enabled: false } } },
      });
    }

    function recalc() {
      const price = +priceInput.value;
      const downPct = +downInput.value;
      const term = +termInput.value;
      const downAmount = Math.round((price * downPct) / 100);
      const principal = Math.max(price - downAmount, 0);
      const monthly = annuityMonthlyPayment(principal, config.annualRate, term);
      const totalPaid = monthly * term;
      const overpay = Math.max(totalPaid - principal, 0);

      priceValueEl.textContent = `${formatRub(price)} ₽`;
      downValueEl.textContent = `${downPct}% (${formatRub(downAmount)} ₽)`;
      termValueEl.textContent = `${term} мес.`;
      monthlyEl.textContent = `${formatRub(monthly)} ₽`;
      principalEl.textContent = `${formatRub(principal)} ₽`;
      overpayEl.textContent = `${formatRub(overpay)} ₽`;

      if (chart) {
        chart.data.datasets[0].data = [principal, overpay];
        chart.update();
      }
    }

    [priceInput, downInput, termInput].forEach((input) => input.addEventListener("input", recalc));
    recalc();
  }

  document.addEventListener("DOMContentLoaded", () => {
    readAndStoreUtm();
    initLeadModal();
    initCalculator();
  });
})();
