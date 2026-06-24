/* ══════════════════════════════════════════════════════════════════
   main.js — Основной JavaScript сайта Иван Гуничев
   ══════════════════════════════════════════════════════════════════ */

'use strict';

/* ── Глобальные ссылки ── */
const header      = document.querySelector('.header');
const burger      = document.querySelector('.burger');
const mobileMenu  = document.querySelector('.mobile-menu');
const backToTop   = document.querySelector('.back-to-top');
const faqItems    = document.querySelectorAll('.faq-item');
const revealItems = document.querySelectorAll('.reveal');

/* ════════════════════════════════════════════════════════════════
   1. Шапка: scrolled-состояние (header всегда закреплён, не скрывается)
   ════════════════════════════════════════════════════════════════ */
let _scrollTicking = false;

function syncHeader() {
  if (!header) return;
  // Только добавляем фон при скролле — никогда не скрываем
  header.classList.toggle('scrolled', window.scrollY > 12);
}

function onScroll() {
  if (!_scrollTicking) {
    requestAnimationFrame(() => {
      syncHeader();
      syncBackToTop();
      _scrollTicking = false;
    });
    _scrollTicking = true;
  }
}

/* ════════════════════════════════════════════════════════════════
   2. Кнопка "Наверх"
   ════════════════════════════════════════════════════════════════ */
function syncBackToTop() {
  if (!backToTop) return;
  const isMobile = window.matchMedia('(max-width: 1023px)').matches;
  backToTop.classList.toggle('visible', isMobile && window.scrollY > 300);
}

/* ════════════════════════════════════════════════════════════════
   3. Бургер-меню
   ════════════════════════════════════════════════════════════════ */
function setupBurger() {
  if (!burger || !mobileMenu) return;

  burger.addEventListener('click', () => {
    const isOpen = burger.classList.toggle('open');
    mobileMenu.classList.toggle('open', isOpen);
    mobileMenu.setAttribute('aria-hidden', String(!isOpen));
    burger.setAttribute('aria-expanded', String(isOpen));
  });

  mobileMenu.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      burger.classList.remove('open');
      mobileMenu.classList.remove('open');
      mobileMenu.setAttribute('aria-hidden', 'true');
    });
  });

  document.addEventListener('click', (e) => {
    if (!header?.contains(e.target) && mobileMenu.classList.contains('open')) {
      burger.classList.remove('open');
      mobileMenu.classList.remove('open');
      mobileMenu.setAttribute('aria-hidden', 'true');
    }
  });
}

/* ════════════════════════════════════════════════════════════════
   4. Анимации появления (IntersectionObserver)
   Фикс мобайльного: threshold=0, принудительное visible через 800ms
   ════════════════════════════════════════════════════════════════ */
function setupReveal() {
  if (!revealItems.length) return;

  // Принудительно показываем все элементы через 800ms —
  // страховка от бага IntersectionObserver на iOS Safari
  const forceVisible = setTimeout(() => {
    revealItems.forEach(el => el.classList.add('visible'));
  }, 800);

  if (!('IntersectionObserver' in window)) {
    revealItems.forEach(el => el.classList.add('visible'));
    clearTimeout(forceVisible);
    return;
  }

  const observer = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      requestAnimationFrame(() => entry.target.classList.add('visible'));
      obs.unobserve(entry.target);
    });
  }, {
    // threshold 0 = срабатывает как только хоть пиксель в зоне видимости
    threshold: 0,
    rootMargin: '0px 0px -30px 0px',
  });

  revealItems.forEach(el => observer.observe(el));
}

/* ════════════════════════════════════════════════════════════════
   5. FAQ-аккордеон
   ════════════════════════════════════════════════════════════════ */
function setupFaq() {
  faqItems.forEach(item => {
    const btn    = item.querySelector('.faq-question');
    const answer = item.querySelector('.faq-answer');
    if (!btn || !answer) return;

    btn.addEventListener('click', () => {
      const isOpen = item.classList.contains('open');

      faqItems.forEach(other => {
        if (other !== item && other.classList.contains('open')) {
          other.classList.remove('open');
          other.querySelector('.faq-question')?.setAttribute('aria-expanded', 'false');
          const a = other.querySelector('.faq-answer');
          if (a) a.style.maxHeight = '0';
        }
      });

      item.classList.toggle('open', !isOpen);
      btn.setAttribute('aria-expanded', String(!isOpen));
      requestAnimationFrame(() => {
        answer.style.maxHeight = !isOpen ? `${answer.scrollHeight}px` : '0';
      });
    });
  });
}

/* ════════════════════════════════════════════════════════════════
   6. Маска телефона +7 (9XX) XXX-XX-XX
   Улучшенная версия: автозаполнение при фокусе,
   защита от удаления префикса, правильная позиция курсора
   ════════════════════════════════════════════════════════════════ */
const PHONE_PREFIX = '+7 (';

function formatPhone(raw) {
  // Вытаскиваем все цифры
  let digits = raw.replace(/\D/g, '');

  // Нормализуем: 8 → 7, убираем ведущую 7
  if (digits.startsWith('8')) digits = '7' + digits.slice(1);
  if (digits.startsWith('7')) digits = digits.slice(1);
  digits = digits.slice(0, 10);

  // Форматируем: +7 (XXX) XXX-XX-XX
  let out = '+7 (';
  if (digits.length > 0) out += digits.slice(0, 3);
  if (digits.length >= 3) out += ') ';
  if (digits.length > 3) out += digits.slice(3, 6);
  if (digits.length >= 6) out += '-';
  if (digits.length > 6) out += digits.slice(6, 8);
  if (digits.length >= 8) out += '-';
  if (digits.length > 8) out += digits.slice(8, 10);

  return out;
}

function setupPhoneMask(input) {
  if (!input) return;

  // При фокусе — предзаполняем префикс
  input.addEventListener('focus', function () {
    if (!this.value || this.value.length < PHONE_PREFIX.length) {
      this.value = PHONE_PREFIX;
    }
    const pos = this.value.length;
    setTimeout(() => {
      try { this.setSelectionRange(pos, pos); } catch (_) {}
    }, 0);
  });

  // Защита от удаления префикса
  input.addEventListener('keydown', function (e) {
    const minPos = PHONE_PREFIX.length;
    if ((e.key === 'Backspace' || e.key === 'Delete')
        && this.selectionStart <= minPos
        && this.selectionEnd <= minPos) {
      e.preventDefault();
    }
  });

  // Форматирование при вводе
  input.addEventListener('input', function () {
    const prevLen = this.value.length;
    const prevPos = this.selectionStart;

    const formatted = formatPhone(this.value);
    this.value = formatted;

    // Плавное движение курсора
    const diff = formatted.length - prevLen;
    const newPos = Math.max(PHONE_PREFIX.length, Math.min(prevPos + diff, formatted.length));
    try { this.setSelectionRange(newPos, newPos); } catch (_) {}
  });

  // При потере фокуса — очищаем если только префикс
  input.addEventListener('blur', function () {
    if (this.value === PHONE_PREFIX || this.value.replace(/\D/g, '').length < 2) {
      this.value = '';
    }
  });
}

function setupAllPhoneMasks() {
  document.querySelectorAll('.phone-mask, input[type="tel"]').forEach(setupPhoneMask);
}

/* ════════════════════════════════════════════════════════════════
   7. Плавный скролл к якорям
   ════════════════════════════════════════════════════════════════ */
function setupSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', e => {
      const href = anchor.getAttribute('href');
      if (!href || href === '#') return;
      const target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      const headerH = header ? header.offsetHeight : 72;
      const top = target.getBoundingClientRect().top + window.scrollY - headerH - 24;
      window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
    });
  });
}

/* ════════════════════════════════════════════════════════════════
   8. BookingCalendar — страница записи и страница переноса
   ════════════════════════════════════════════════════════════════ */

const CALENDAR_MONTHS = [
  'Январь','Февраль','Март','Апрель','Май','Июнь',
  'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь',
];
const CALENDAR_MONTHS_GEN = [
  'января','февраля','марта','апреля','мая','июня',
  'июля','августа','сентября','октября','ноября','декабря',
];

class BookingCalendar {
  constructor(opts = {}) {
    this.calGrid     = document.getElementById('cal-grid');
    this.monthLabel  = document.getElementById('cal-month-label');
    this.prevBtn     = document.getElementById('prev-month');
    this.nextBtn     = document.getElementById('next-month');
    this.slotsWrap   = document.getElementById('time-slots-wrap');
    this.slotDisplay = document.getElementById('selected-slot-display');
    this.slotIdInput = document.getElementById('slot-id-input');
    this.submitBtn   = document.getElementById('submit-btn');
    this.formStatus  = document.getElementById('form-status');
    this.formCard    = document.getElementById('booking-form-card');
    this.form        = document.getElementById('booking-form') || document.getElementById('reschedule-form');

    if (!this.calGrid) return;

    this.isReschedule = opts.isReschedule || false;
    this.today    = new Date();
    this.today.setHours(0, 0, 0, 0);
    this.availMap = {};
    this.selDate  = null;
    this.selSlot  = null;
    this.csrf     = document.querySelector('[name=csrfmiddlewaretoken]')?.value
                 || document.querySelector('meta[name="csrf-token"]')?.content || '';

    // Отслеживаем согласие через event listener (надёжно на мобильных)
    this._consentChecked = false;
    const consentInput = document.getElementById('consent-input');
    if (consentInput) {
      // Восстанавливаем состояние на случай prefill
      this._consentChecked = consentInput.checked;
      consentInput.addEventListener('change', e => {
        this._consentChecked = e.target.checked;
      });
    }

    // Форма скрыта до выбора слота
    this._lockForm();

    // ВСЕГДА используем бесшовный режим (6 недель)
    if (this.prevBtn) this.prevBtn.style.display = 'none';
    if (this.nextBtn) this.nextBtn.style.display = 'none';
    if (this.monthLabel) this.monthLabel.textContent = 'Ближайшие 6 недель';

    this._loadSeamless();
    if (!this.isReschedule) this._bindForm();
    this._bindPhoneMask();
  }

  /* Блокируем форму до выбора слота */
  _lockForm() {
    if (!this.formCard) return;
    this.formCard.classList.add('form-locked');
    this.formCard.classList.remove('form-ready');

    // Показываем подсказку внутри формы
    const existingPrompt = this.formCard.querySelector('.form-slot-prompt');
    if (!existingPrompt) {
      const prompt = document.createElement('div');
      prompt.className = 'form-slot-prompt';
      prompt.id = 'form-slot-prompt';
      prompt.innerHTML = `
        <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="3" y="4" width="18" height="18" rx="2"/>
          <line x1="16" y1="2" x2="16" y2="6"/>
          <line x1="8" y1="2" x2="8" y2="6"/>
          <line x1="3" y1="10" x2="21" y2="10"/>
        </svg>
        <p><strong>Выберите дату и время</strong><br>в календаре слева</p>`;
      this.formCard.insertBefore(prompt, this.formCard.firstChild);
    }
  }

  /* Разблокируем форму и фокусируем имя */
  _unlockForm() {
    if (!this.formCard) return;
    const prompt = document.getElementById('form-slot-prompt');
    if (prompt) prompt.remove();

    this.formCard.classList.remove('form-locked');
    this.formCard.classList.add('form-ready');

    // Фокус на имени через 450ms (после анимации)
    setTimeout(() => {
      document.getElementById('name-input')?.focus();
    }, 450);
  }

  async _loadSeamless() {
    this.calGrid.innerHTML = `
      <div class="cal-loading" style="grid-column:1/-1">
        <div class="cal-spinner"></div><span>Загрузка...</span>
      </div>`;
    try {
      const r = await fetch(`/api/available-dates/?weeks=6`);
      if (!r.ok) throw new Error();
      this.availMap = await r.json();
    } catch (_) { this.availMap = {}; }
    this._renderSeamlessGrid();
  }

  _renderSeamlessGrid() {
    // Рендерим 6 недель (42 дня) начиная с сегодня
    this.calGrid.innerHTML = '';

    const startDate = new Date(this.today);
    const endDate = new Date(this.today);
    endDate.setDate(endDate.getDate() + 42);

    // Находим начало недели (понедельник)
    let currentDate = new Date(startDate);
    let dayOfWeek = currentDate.getDay();
    if (dayOfWeek === 0) dayOfWeek = 7; // Воскресенье = 7
    currentDate.setDate(currentDate.getDate() - (dayOfWeek - 1));

    // Рендерим 6 недель (42 дня)
    for (let i = 0; i < 42; i++) {
      const el = document.createElement('button');
      el.type = 'button';
      el.className = 'cal-day';
      el.textContent = currentDate.getDate();
      el.setAttribute('role', 'gridcell');

      const dateStr = this._fmt(currentDate);
      const isPast = currentDate < this.today;
      const isCurrentMonth = currentDate.getMonth() === this.today.getMonth();

      // Прошедшие дни или дни до сегодня
      if (isPast) {
        el.classList.add('past');
        el.disabled = true;
      }
      // Дни с доступными слотами
      else if (this.availMap[dateStr]) {
        el.classList.add('has-slots');
        el.setAttribute('aria-label', `${currentDate.getDate()} — ${this.availMap[dateStr]} слот(ов)`);
        el.addEventListener('click', () => this._selectDate(dateStr, currentDate.getDate(), el));
      }
      // Дни без слотов
      else {
        el.classList.add('no-slots');
        el.disabled = true;
      }

      // Сегодня
      if (dateStr === this._fmt(this.today)) el.classList.add('today');

      // Выбранная дата
      if (dateStr === this.selDate) el.classList.add('selected');

      // Дни другого месяца (приглушаем)
      if (!isCurrentMonth && currentDate < this.today) {
        el.classList.add('other-month');
      }

      this.calGrid.appendChild(el);
      currentDate.setDate(currentDate.getDate() + 1);
    }
  }

  async _selectDate(dateStr, dayNum, clickedEl) {
    if (this.selDate === dateStr) return;
    this.selDate = dateStr;
    this.selSlot = null;
    this._clearSlot();

    this.calGrid.querySelectorAll('.cal-day.selected').forEach(e => e.classList.remove('selected'));
    clickedEl.classList.add('selected');

    this.slotsWrap.innerHTML = `
      <div class="cal-loading"><div class="cal-spinner"></div><span>Загружаем слоты...</span></div>`;

    try {
      const r = await fetch(`/api/slots/?date=${dateStr}`);
      if (!r.ok) throw new Error();
      const slots = await r.json();
      this._renderSlots(slots, dateStr, dayNum);
    } catch (_) {
      this.slotsWrap.innerHTML = `<div class="slots-empty">Ошибка загрузки. Попробуйте ещё раз.</div>`;
    }
  }

  _renderSlots(slots, dateStr, dayNum) {
    if (!slots.length) {
      this.slotsWrap.innerHTML = `<div class="slots-empty">На эту дату слотов нет.</div>`;
      return;
    }

    const d     = new Date(dateStr);
    const label = `${dayNum} ${CALENDAR_MONTHS_GEN[d.getMonth()]}`;

    const wrap = document.createElement('div');
    wrap.innerHTML = `<p class="time-slots-date">📅 ${label}</p>`;
    const grid = document.createElement('div');
    grid.className = 'slots-list';

    slots.forEach(slot => {
      const pill = document.createElement('button');
      pill.type = 'button';
      pill.className = 'slot-pill';
      pill.innerHTML = `${slot.time}<span>${slot.available ? 'Свободно' : 'Занято'}</span>`;
      pill.dataset.id   = slot.id;
      pill.dataset.time = slot.time;

      if (!slot.available) {
        pill.classList.add('slot-unavailable');
        pill.disabled = true;
      } else {
        pill.addEventListener('click', () => this._selectSlot(slot, pill));
      }
      grid.appendChild(pill);
    });

    wrap.appendChild(grid);
    this.slotsWrap.innerHTML = '';
    this.slotsWrap.appendChild(wrap);

    // На мобиле прокручиваем к блоку со слотами
    this._scrollTo(this.slotsWrap);
  }

  /* Плавный скролл к элементу с учётом фиксированного хедера (только мобиль) */
  _scrollTo(el, delay = 0) {
    if (!el || window.innerWidth >= 768) return;
    const run = () => {
      const top = el.getBoundingClientRect().top + window.scrollY - 84;
      window.scrollTo({ top, behavior: 'smooth' });
    };
    delay ? setTimeout(run, delay) : requestAnimationFrame(run);
  }

  _selectSlot(slot, pill) {
    this.selSlot = slot;
    this.slotsWrap.querySelectorAll('.slot-pill').forEach(p => p.classList.remove('selected'));
    pill.classList.add('selected');

    if (this.slotIdInput) this.slotIdInput.value = slot.id;

    if (this.slotDisplay) {
      const d = new Date(this.selDate);
      this.slotDisplay.textContent = `📅 ${d.getDate()} ${CALENDAR_MONTHS_GEN[d.getMonth()]} — ${slot.time}`;
      this.slotDisplay.classList.add('active');
    }

    if (this.submitBtn) this.submitBtn.disabled = false;

    // Разблокируем форму (появляется с анимацией)
    this._unlockForm();

    // На мобиле прокручиваем к форме после того, как она разблокировалась
    this._scrollTo(this.formCard, 220);
  }

  _clearSlot() {
    if (this.slotIdInput) this.slotIdInput.value = '';
    if (this.slotDisplay) {
      this.slotDisplay.textContent = 'Слот не выбран';
      this.slotDisplay.classList.remove('active');
    }
    if (this.submitBtn) this.submitBtn.disabled = true;
  }

  _bindPhoneMask() {
    const phone = document.getElementById('phone-input');
    if (phone) setupPhoneMask(phone);
  }

  _bindForm() {
    if (!this.form) return;

    this.form.addEventListener('submit', async e => {
      e.preventDefault();
      if (!this.selSlot) return;

      const btn     = this.submitBtn;
      const btnText = btn?.querySelector('.btn-text');
      const btnLoad = btn?.querySelector('.btn-loader');
      const name    = document.getElementById('name-input')?.value.trim();
      const phone   = document.getElementById('phone-input')?.value.trim();
      const comment = document.getElementById('comment-input')?.value.trim() || '';
      const slotId  = this.slotIdInput?.value;
      if (!name) { this._status('Введите ваше имя.', 'error'); return; }
      if ((phone || '').replace(/\D/g, '').length < 11) {
        this._status('Введите корректный номер телефона.', 'error'); return;
      }
      if (!comment) {
        this._status('Расскажите, что хотите отработать.', 'error');
        document.getElementById('comment-input')?.focus();
        return;
      }
      if (!this._consentChecked) {
        this._status('Необходимо согласие на обработку персональных данных.', 'error');
        // Подсвечиваем чекбокс, не фокусируем (мобильный фокус может тоггнуть)
        const consentWrap = document.querySelector('.form-consent');
        if (consentWrap) {
          consentWrap.classList.add('form-consent--error');
          setTimeout(() => consentWrap.classList.remove('form-consent--error'), 2500);
        }
        return;
      }
      if (!slotId) { this._status('Выберите дату и время.', 'error'); return; }

      if (btn) btn.disabled = true;
      if (btnText) btnText.style.display = 'none';
      if (btnLoad) btnLoad.style.display = 'flex';
      this._hideStatus();

      try {
        const r = await fetch('/api/book/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrf },
          body: JSON.stringify({ name, phone, comment, slot_id: parseInt(slotId), consent: this._consentChecked }),
        });
        const data = await r.json();
        if (data.success && data.redirect) {
          window.location.href = data.redirect;
        } else {
          throw new Error(data.error || 'Ошибка при записи.');
        }
      } catch (err) {
        this._status(err.message || 'Ошибка. Позвоните: +7 (905) 560-96-96', 'error');
      } finally {
        if (btn) btn.disabled = false;
        if (btnText) btnText.style.display = 'flex';
        if (btnLoad) btnLoad.style.display = 'none';
      }
    });
  }

  _status(msg, type) {
    if (!this.formStatus) return;
    this.formStatus.textContent = msg;
    this.formStatus.className = `form-status form-status-${type}`;
    this.formStatus.style.display = 'block';
    this.formStatus.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  _hideStatus() {
    if (this.formStatus) this.formStatus.style.display = 'none';
  }

  _fmt(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }
}

/* ════════════════════════════════════════════════════════════════
   9. Cookie-баннер
   ════════════════════════════════════════════════════════════════ */
function setupCookieBanner() {
  const banner = document.getElementById('cookie-banner');
  if (!banner) return;
  try {
    if (!localStorage.getItem('cookie_ok')) {
      banner.removeAttribute('hidden');
    }
  } catch (_) {
    // localStorage недоступен (приватный режим) — не показываем
    return;
  }
  document.getElementById('cookie-ok')?.addEventListener('click', () => {
    try { localStorage.setItem('cookie_ok', '1'); } catch (_) {}
    banner.setAttribute('hidden', '');
  });
}

/* ════════════════════════════════════════════════════════════════
   10. DOMContentLoaded — инициализация
   ════════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  // Убираем хэш из URL (предотвращаем прыжок страницы)
  if (window.location.hash) {
    window.history.replaceState(null, null, ' ');
  }

  // Единый обработчик скролла через rAF
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', () => {
    syncHeader();
    syncBackToTop();
  });

  syncHeader();
  syncBackToTop();

  setupBurger();
  setupReveal();
  setupFaq();
  setupAllPhoneMasks();
  setupSmoothScroll();
  setupCookieBanner();

  // Кнопка "Наверх"
  backToTop?.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

  // Страница записи / переноса — запускаем календарь
  if (document.getElementById('cal-grid')) {
    const isReschedule = !!document.getElementById('reschedule-form');
    new BookingCalendar({ isReschedule });
  }
});
