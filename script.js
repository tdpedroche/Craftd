/* =========================================
   PLAAX — MAIN SCRIPT
   Dark mode + Nav + Scroll reveal + Quiz
   ========================================= */

// ---- API BASE ----
const _raw = '__PORT_8000__';
const API = (_raw.startsWith('__') || _raw.includes('localhost')) ? '' : _raw;
// Empty string means same-origin relative URLs — works both locally and deployed

// ---- DARK MODE TOGGLE ----
(function () {
  const toggle = document.querySelector('[data-theme-toggle]');
  const root = document.documentElement;
  let theme = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  root.setAttribute('data-theme', theme);

  function setIcon(t) {
    if (!toggle) return;
    toggle.innerHTML = t === 'dark'
      ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
      : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
    toggle.setAttribute('aria-label', 'Switch to ' + (t === 'dark' ? 'light' : 'dark') + ' mode');
  }

  setIcon(theme);
  if (toggle) {
    toggle.addEventListener('click', () => {
      theme = theme === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', theme);
      setIcon(theme);
    });
  }
})();

// ---- MOBILE NAV ----
(function () {
  const btn = document.getElementById('mobile-menu-btn');
  const drawer = document.getElementById('mobile-drawer');
  if (!btn || !drawer) return;
  btn.addEventListener('click', () => {
    const isOpen = drawer.classList.toggle('open');
    btn.setAttribute('aria-expanded', isOpen);
  });
  drawer.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => drawer.classList.remove('open'));
  });
})();

// ---- SCROLL REVEAL ----
(function () {
  const revealEls = document.querySelectorAll('.reveal');
  if (!revealEls.length) return;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('in-view');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
  revealEls.forEach(el => observer.observe(el));
})();

// ---- SMOOTH SCROLL ----
document.querySelectorAll('a[href^="#"]').forEach(link => {
  link.addEventListener('click', (e) => {
    const target = document.querySelector(link.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

// ---- QUIZ ----
(function () {
  const TOTAL_STEPS = 10;
  let currentStep = 1;
  const answers = {};

  const progressBar    = document.getElementById('quiz-progress-bar');
  const stepLabel      = document.getElementById('quiz-step-label');
  const backBtn        = document.getElementById('quiz-back');
  const dotsContainer  = document.getElementById('quiz-dots');
  const quizNav        = document.getElementById('quiz-nav');

  function showStep(step) {
    document.querySelectorAll('.quiz-step').forEach(el => el.classList.remove('active'));

    if (step === 'email') {
      document.querySelector('.quiz-step[data-step="email"]').classList.add('active');
      progressBar.style.width = '100%';
      stepLabel.textContent = 'One last thing…';
      backBtn.style.visibility = 'visible';
      quizNav.style.display = 'flex';
      updateDots(TOTAL_STEPS - 1); // all filled (highlight last dot)
      return;
    }

    if (step === 'generating') {
      document.querySelector('.quiz-step[data-step="generating"]').classList.add('active');
      progressBar.style.width = '100%';
      stepLabel.textContent = 'Building your playbook…';
      backBtn.style.visibility = 'hidden';
      quizNav.style.display = 'none';
      startGeneratingAnimation();
      return;
    }

    if (step === 'checkout') {
      document.querySelector('.quiz-step[data-step="checkout"]').classList.add('active');
      progressBar.style.width = '100%';
      stepLabel.textContent = 'Your playbook is ready!';
      backBtn.style.visibility = 'hidden';
      quizNav.style.display = 'none';
      return;
    }

    if (step === 'error') {
      document.querySelector('.quiz-step[data-step="error"]').classList.add('active');
      progressBar.style.width = '100%';
      stepLabel.textContent = 'Something went wrong';
      backBtn.style.visibility = 'hidden';
      quizNav.style.display = 'none';
      return;
    }

    const el = document.querySelector(`.quiz-step[data-step="${step}"]`);
    if (el) el.classList.add('active');

    const pct = (step / TOTAL_STEPS) * 100;
    progressBar.style.width = pct + '%';
    stepLabel.textContent = 'Question ' + step + ' of ' + TOTAL_STEPS;
    updateDots(step - 1);

    backBtn.style.visibility = step > 1 ? 'visible' : 'hidden';
    quizNav.style.display = 'flex';
  }

  function updateDots(activeIndex) {
    const dots = dotsContainer.querySelectorAll('.quiz-dot');
    dots.forEach((dot, i) => {
      dot.classList.toggle('active', i === activeIndex);
    });
  }

  // Quiz option selection — auto-advance (supports both .quiz-option and .quiz-option-card)
  document.querySelectorAll('.quiz-options').forEach(optGroup => {
    optGroup.addEventListener('click', (e) => {
      const option = e.target.closest('.quiz-option, .quiz-option-card');
      if (!option) return;
      optGroup.querySelectorAll('.quiz-option, .quiz-option-card').forEach(o => o.classList.remove('selected'));
      option.classList.add('selected');
      const name = optGroup.dataset.name;
      answers[name] = option.dataset.value;

      setTimeout(() => {
        if (currentStep < TOTAL_STEPS) {
          currentStep++;
          showStep(currentStep);
        } else {
          // All 10 questions done — show email capture
          onEmailStep = true;
          showStep('email');
        }
      }, 350);
    });
  });

  // Back button
  let onEmailStep = false;
  if (backBtn) {
    backBtn.addEventListener('click', () => {
      if (onEmailStep) {
        onEmailStep = false;
        showStep(currentStep);
      } else if (currentStep > 1) {
        currentStep--;
        showStep(currentStep);
      }
    });
  }

  // Email form submit
  const emailForm = document.getElementById('quiz-email-form');
  if (emailForm) {
    emailForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const emailInput = document.getElementById('quiz-email-input');
      const nameInput  = document.getElementById('quiz-name');
      const firstName  = nameInput ? nameInput.value.trim() : '';
      const email = emailInput.value.trim();
      if (!email) return;

      // Show generating state
      showStep('generating');

      try {
        // Step 1: Submit — returns immediately with a pending_id
        const res = await fetch(`${API}/api/submit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email,
            first_name: firstName || null,
            goal: answers.goal || null,
            role: answers.role || null,
            pain: answers.pain || null,
            time_drain: answers['time-drain'] || null,
            experience: answers.experience || null,
            tried: answers.tried || null,
            usecase: answers.usecase || null,
            time: answers.time || null,
            success: answers.success || null,
            learning_style: answers['learning-style'] || null,
          }),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || 'Server error');
        }

        const { pending_id } = await res.json();

        // Step 2: Poll /api/status until ready (every 2 seconds, max 2 minutes)
        animateGenSteps();
        let attempts = 0;
        const maxAttempts = 90; // 90 × 2s = 3 minutes max wait

        const poll = setInterval(async () => {
          attempts++;
          try {
            const statusRes = await fetch(`${API}/api/status?pending_id=${pending_id}`);
            const status = await statusRes.json();

            if (status.error) {
              clearInterval(poll);
              throw new Error(status.error);
            }

            if (status.ready && status.checkout_url) {
              clearInterval(poll);
              // Dev mode — already paid, go straight to playbook
              if (status.checkout_url.startsWith('/') || status.checkout_url.startsWith('playbook')) {
                window.location.href = status.checkout_url;
                return;
              }
              // Show checkout step with Stripe button
              showStep('checkout');
              const btn = document.getElementById('checkout-btn');
              if (btn) {
                btn.href = status.checkout_url;
                btn.target = '_blank';
                btn.rel = 'noopener noreferrer';
              }
            }

            if (attempts >= maxAttempts) {
              clearInterval(poll);
              throw new Error('Timed out. Please try again.');
            }
          } catch (pollErr) {
            clearInterval(poll);
            showStep('error');
            const errorMsg = document.getElementById('quiz-error-msg');
            if (errorMsg) errorMsg.textContent = pollErr.message || 'Something went wrong.';
          }
        }, 2000);

      } catch (err) {
        console.error(err);
        showStep('error');
        const errorMsg = document.getElementById('quiz-error-msg');
        if (errorMsg) errorMsg.textContent = err.message || 'Something went wrong. Please try again.';
      }
    });
  }

  // Animate generating step labels progressively (legacy — kept for safety)
  function animateGenSteps() {
    // Delegate to the new premium animation
    startGeneratingAnimation();
  }

  // Interval IDs for generating animation — stored so they can be cleared
  let _genProgressInterval = null;
  let _genStepInterval = null;
  let _genTitleInterval = null;

  function startGeneratingAnimation() {
    // Clear any previous animation intervals
    if (_genProgressInterval) clearInterval(_genProgressInterval);
    if (_genStepInterval) clearInterval(_genStepInterval);
    if (_genTitleInterval) clearInterval(_genTitleInterval);

    const progressFill = document.getElementById('gen-progress-fill');
    const cyclingTitle = document.getElementById('gen-cycling-title');
    const rowIds = ['gsr-1', 'gsr-2', 'gsr-3', 'gsr-4', 'gsr-5'];

    // Reset progress bar
    if (progressFill) progressFill.style.width = '0%';

    // Reset all step rows to pending
    rowIds.forEach(id => {
      const el = document.getElementById(id);
      if (el) { el.classList.remove('active', 'done'); el.classList.add('pending'); }
    });

    // Activate first row immediately
    const firstRow = document.getElementById(rowIds[0]);
    if (firstRow) { firstRow.classList.remove('pending'); firstRow.classList.add('active'); }

    // Progress bar: animate 0→85% over 75 seconds (real gen time ~60-90s)
    const totalDuration = 75000; // 75s
    const targetPct = 85;
    const tickMs = 200;
    const totalTicks = totalDuration / tickMs;
    let tick = 0;
    _genProgressInterval = setInterval(() => {
      tick++;
      const pct = Math.min((tick / totalTicks) * targetPct, targetPct);
      if (progressFill) progressFill.style.width = pct + '%';
      if (tick >= totalTicks) clearInterval(_genProgressInterval);
    }, tickMs);

    // Step rows: advance every 15 seconds (5 steps × 15s = 75s)
    let rowIndex = 0;
    _genStepInterval = setInterval(() => {
      const currentRow = document.getElementById(rowIds[rowIndex]);
      if (currentRow) { currentRow.classList.remove('active'); currentRow.classList.add('done'); }
      rowIndex++;
      if (rowIndex < rowIds.length) {
        const nextRow = document.getElementById(rowIds[rowIndex]);
        if (nextRow) { nextRow.classList.remove('pending'); nextRow.classList.add('active'); }
      } else {
        clearInterval(_genStepInterval);
      }
    }, 15000);

    // Cycling title messages every 15 seconds
    const titles = [
      'Analyzing your answers…',
      'Building your workflow…',
      'Writing your prompts…',
      'Crafting your 30-day plan…',
      'Putting it all together…',
    ];
    let titleIndex = 0;
    _genTitleInterval = setInterval(() => {
      titleIndex = (titleIndex + 1) % titles.length;
      if (cyclingTitle) cyclingTitle.textContent = titles[titleIndex];
      if (titleIndex === titles.length - 1) clearInterval(_genTitleInterval);
    }, 15000);
  }

  // Initialize
  showStep(1);
})();
