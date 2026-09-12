// Калькулятор (Chart.js) — только на лендинге (templates/index.html, extra_scripts):
// вынесен из site.js, чтобы на карточке авто, где калькулятора нет, не грузился ни
// Chart.js с CDN, ни этот код.
(function () {
  "use strict";

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

  document.addEventListener("DOMContentLoaded", initCalculator);
})();
