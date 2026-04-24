/* =========================================
   CRAFTD — MAIN SCRIPT
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
  const TOTAL_STEPS = 5;
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
      updateDots(5); // all filled
      return;
    }

    if (step === 'generating') {
      document.querySelector('.quiz-step[data-step="generating"]').classList.add('active');
      progressBar.style.width = '100%';
      stepLabel.textContent = 'Building your playbook…';
      backBtn.style.visibility = 'hidden';
      quizNav.style.display = 'none';
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
    stepLabel.textContent = `Question ${step} of ${TOTAL_STEPS}`;
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

  // Quiz option selection — auto-advance
  document.querySelectorAll('.quiz-options').forEach(optGroup => {
    optGroup.addEventListener('click', (e) => {
      const option = e.target.closest('.quiz-option');
      if (!option) return;
      optGroup.querySelectorAll('.quiz-option').forEach(o => o.classList.remove('selected'));
      option.classList.add('selected');
      const name = optGroup.dataset.name;
      answers[name] = option.dataset.value;

      setTimeout(() => {
        if (currentStep < TOTAL_STEPS) {
          currentStep++;
          showStep(currentStep);
        } else {
          // All 5 questions done — show email capture
          showStep('email');
        }
      }, 350);
    });
  });

  // Back button
  if (backBtn) {
    backBtn.addEventListener('click', () => {
      if (currentStep > 1) {
        currentStep--;
        showStep(currentStep);
      } else if (currentStep === 1) {
        // already at first
      }
    });
  }

  // Email form submit
  const emailForm = document.getElementById('quiz-email-form');
  if (emailForm) {
    emailForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const emailInput = document.getElementById('quiz-email-input');
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
            goal: answers.goal || null,
            role: answers.role || null,
            pain: answers.pain || null,
            time_drain: answers['time-drain'] || null,
            experience: answers.experience || null,
            tried: answers.tried || null,
            usecase: answers.usecase || null,
            time: answers.time || null,
            success: answers.success || null,
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
              // Always show checkout step with button — lets user click to open Stripe
              // (iframe environments block automatic window.location redirects to external domains)
              showStep('checkout');
              const btn = document.getElementById('checkout-btn');
              if (btn) {
                btn.href = status.checkout_url;
                btn.target = '_blank'; // open in new tab to escape iframe restrictions
                btn.rel = 'noopener noreferrer';
                if (status.checkout_url.startsWith('/') || status.checkout_url.startsWith('playbook')) {
                  btn.textContent = 'View My Playbook →';
                  btn.target = '_self';
                } else {
                  btn.textContent = 'Unlock My Playbook — $37 →';
                }
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

  // Animate generating step labels progressively
  function animateGenSteps() {
    const steps = ['gen-step-1','gen-step-2','gen-step-3','gen-step-4'];
    let i = 0;
    // Reset all
    steps.forEach(id => {
      const el = document.getElementById(id);
      if (el) { el.classList.remove('active','done'); }
    });
    if (steps[0]) document.getElementById(steps[0])?.classList.add('active');

    const interval = setInterval(() => {
      if (i < steps.length - 1) {
        document.getElementById(steps[i])?.classList.replace('active','done');
        i++;
        document.getElementById(steps[i])?.classList.add('active');
      } else {
        clearInterval(interval);
      }
    }, 6000);
  }

  // Initialize
  showStep(1);
})();
