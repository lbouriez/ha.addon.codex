/* The public window.term API is provided by the pinned ttyd 1.7.7 client. */
(() => {
  'use strict';
  const french = navigator.language.toLowerCase().startsWith('fr');
  const text = french ? {
    copy: 'Copier', paste: 'Coller', history: 'Historique', latest: 'En bas',
    hint: 'Sélectionnez le texte (Maj + glisser si nécessaire). Ctrl/Cmd + C et V ; Ctrl + C sans sélection interrompt la commande.',
    select: 'Sélectionnez du texte ou ouvrez l’historique.', copied: 'Texte copié.',
    manualCopy: 'Copiez le texte sélectionné avec Ctrl/Cmd + C ou le menu de votre appareil.',
    manualPaste: 'Collez ici avec Ctrl/Cmd + V ou le menu de votre appareil, puis cliquez sur Insérer. Aucun Entrée n’est ajouté.',
    insert: 'Insérer', close: 'Fermer', download: 'Télécharger',
    historyHint: 'Historique disponible dans ce navigateur. Vous pouvez sélectionner, copier ou télécharger le texte.',
    historyTitle: 'Historique du terminal', empty: 'Aucun texte à insérer.',
    inserted: 'Texte inséré dans le terminal.', latestHint: 'Retour au bas du terminal.',
    dictate: 'Dicter', stop: 'Arrêter', stopDictation: 'Arrêter la dictée',
    dictationStarting: 'Activation du micro…', dictationListening: 'Écoute en cours. Cliquez sur Arrêter pour terminer.',
    dictationFinishing: 'Transcription en cours…', dictationEmpty: 'Aucune parole détectée. Réessayez.',
    dictationCancelled: 'Dictée annulée.', dictationInserted: 'Dictée insérée. Relisez le texte, puis appuyez sur Entrée pour l’envoyer.',
    dictationHttps: 'Ouvrez Home Assistant en HTTPS pour utiliser le micro du navigateur.',
    dictationBlocked: 'Accès au micro refusé. Vérifiez les permissions de Home Assistant et du navigateur.',
    dictationUnavailable: 'La dictée intégrée est indisponible dans cette vue.',
    dictationFailed: 'Le service de dictée n’a pas pu transcrire votre voix.',
    dictationKeyboard: 'Si votre clavier propose un micro, touchez le champ et utilisez-le, puis cliquez sur Insérer.',
    image: 'Image', uploading: 'Envoi de l’image…', imageReady: 'Image enregistrée, chemin inséré. Ajoutez votre demande puis appuyez sur Entrée.',
    imageFailed: 'Impossible d’envoyer l’image. Réessayez ou utilisez le bouton Image.',
    imageSize: 'Choisissez une image PNG, JPEG, GIF ou WebP de moins de 10 Mo.',
    imageSaved: 'Image enregistrée : ', imageBusy: 'Une image est déjà en cours d’envoi.',
  } : {
    copy: 'Copy', paste: 'Paste', history: 'History', latest: 'Latest',
    hint: 'Select text (Shift + drag if needed). Ctrl/Cmd + C and V; Ctrl + C without a selection interrupts the command.',
    select: 'Select text or open History.', copied: 'Text copied.',
    manualCopy: 'Copy the selected text with Ctrl/Cmd + C or your device’s menu.',
    manualPaste: 'Paste here with Ctrl/Cmd + V or your device’s menu, then choose Insert. No Enter is added.',
    insert: 'Insert', close: 'Close', download: 'Download',
    historyHint: 'History available in this browser. Select, copy or download the text.',
    historyTitle: 'Terminal history', empty: 'No text to insert.',
    inserted: 'Text inserted into the terminal.', latestHint: 'Returned to the latest output.',
    dictate: 'Dictate', stop: 'Stop', stopDictation: 'Stop dictation',
    dictationStarting: 'Starting microphone…', dictationListening: 'Listening. Select Stop when you’re done.',
    dictationFinishing: 'Transcribing…', dictationEmpty: 'No speech detected. Try again.',
    dictationCancelled: 'Dictation canceled.', dictationInserted: 'Dictation inserted. Review the text, then press Enter to send it.',
    dictationHttps: 'Open Home Assistant over HTTPS to use the browser microphone.',
    dictationBlocked: 'Microphone access denied. Check the Home Assistant and browser permissions.',
    dictationUnavailable: 'Built-in dictation is unavailable in this view.',
    dictationFailed: 'The dictation service could not transcribe your voice.',
    dictationKeyboard: 'If your keyboard has a microphone, tap the field and use it, then select Insert.',
    image: 'Image', uploading: 'Uploading image…', imageReady: 'Image saved, path inserted. Add your request, then press Enter.',
    imageFailed: 'Image upload failed. Try again or use the Image button.',
    imageSize: 'Choose a PNG, JPEG, GIF or WebP image smaller than 10 MB.',
    imageSaved: 'Image saved: ', imageBusy: 'An image is already uploading.',
  };

  function attach(term) {
    document.body.classList.add('codex-terminal');
    const toolbar = document.createElement('section');
    toolbar.id = 'codex-toolbar';
    toolbar.setAttribute('aria-label', 'Codex terminal');
    toolbar.innerHTML = `<div class="actions"><strong>Codex</strong><button id="copy">${text.copy}</button><button id="paste">${text.paste}</button><button id="dictate">${text.dictate}</button><button id="image">${text.image}</button><button id="history">${text.history}</button><button id="latest">${text.latest}</button></div><p role="status" aria-live="polite"></p>`;
    document.body.append(toolbar);
    const status = toolbar.querySelector('[role=status]');
    status.textContent = text.hint;
    const dialog = document.createElement('dialog');
    dialog.id = 'codex-dialog';
    dialog.setAttribute('aria-labelledby', 'codex-dialog-title');
    dialog.innerHTML = `<h2 id="codex-dialog-title"></h2><p id="codex-dialog-help"></p><textarea aria-labelledby="codex-dialog-title" aria-describedby="codex-dialog-help" spellcheck="false"></textarea><footer><button id="dialog-close">${text.close}</button><button id="dialog-download">${text.download}</button><button id="dialog-action" class="primary"></button></footer>`;
    document.body.append(dialog);
    const field = dialog.querySelector('textarea');
    const action = dialog.querySelector('#dialog-action');
    let dialogMode;
    let selection = '';
    const imagePicker = document.createElement('input');
    imagePicker.type = 'file';
    imagePicker.accept = 'image/png,image/jpeg,image/gif,image/webp';
    imagePicker.hidden = true;
    toolbar.append(imagePicker);
    term.onSelectionChange(() => { selection = term.getSelection(); });
    // Buttons must not steal a terminal selection before a click can copy it.
    toolbar.addEventListener('mousedown', event => {
      if (event.target.closest('button')) event.preventDefault();
    });

    // Ingress uses a same-origin iframe. The Android keyboard can shrink the
    // host's visual viewport while leaving the iframe's layout size unchanged.
    const views = [];
    for (let view = window; ; view = view.parent) {
      const frame = view.frameElement;
      views.push({ view, frame });
      if (!frame) break;
    }
    const fit = () => {
      let top = 0;
      let bottom = window.innerHeight;
      let frameTop = 0;
      for (const { view, frame } of views) {
        const viewport = view.visualViewport;
        // Keep the layout stable during pinch zoom.
        if (viewport?.height > 0 && viewport.scale === 1) {
          top = Math.max(top, viewport.offsetTop - frameTop);
          bottom = Math.min(bottom, viewport.offsetTop + viewport.height - frameTop);
        }
        if (frame) {
          const padding = view.parent.getComputedStyle(frame).paddingTop;
          frameTop += frame.getBoundingClientRect().top + frame.clientTop + parseFloat(padding);
        }
      }
      const style = document.documentElement.style;
      style.setProperty('--viewport-top', `${Math.ceil(top)}px`);
      style.setProperty('--viewport-bottom', `${Math.ceil(window.innerHeight - bottom)}px`);
      style.setProperty('--toolbar-height', `${toolbar.offsetHeight}px`);
      term.fit();
    };
    const listeners = new AbortController();
    const options = { passive: true, signal: listeners.signal };
    let pendingFit = 0;
    const scheduleFit = () => {
      if (pendingFit) return;
      pendingFit = requestAnimationFrame(() => { pendingFit = 0; fit(); });
    };
    const observer = new ResizeObserver(scheduleFit);
    observer.observe(toolbar);
    for (const { view, frame } of views) {
      view.addEventListener('resize', scheduleFit, options);
      view.visualViewport?.addEventListener('resize', scheduleFit, options);
      view.visualViewport?.addEventListener('scroll', scheduleFit, options);
      if (frame) observer.observe(frame);
    }
    window.addEventListener('pagehide', event => {
      if (event.persisted) return;
      listeners.abort();
      observer.disconnect();
      cancelAnimationFrame(pendingFit);
    });
    term.options.macOptionClickForcesSelection = true;

    // xterm 5.4 skips touch scrolling while application mouse reporting is on.
    // A finger drag should browse local scrollback, not send mouse/key input to
    // Codex. Keep taps, long-press selection and multi-touch available to the OS.
    let touchScroll;
    const resetTouch = () => { touchScroll = undefined; };
    term.element.addEventListener('touchstart', event => {
      resetTouch();
      if (event.touches.length !== 1 || term.buffer.active.type !== 'normal') return;
      const touch = event.touches[0];
      touchScroll = { id: touch.identifier, x: touch.clientX, y: touch.clientY,
        previousY: touch.clientY, remainder: 0, started: performance.now(), dragging: false };
    }, { capture: true, passive: true });
    term.element.addEventListener('touchmove', event => {
      if (!touchScroll) return;
      if (event.touches.length !== 1 || term.buffer.active.type !== 'normal') {
        resetTouch(); return;
      }
      const touch = Array.from(event.touches).find(item => item.identifier === touchScroll.id);
      if (!touch) { resetTouch(); return; }
      if (!touchScroll.dragging) {
        const dx = Math.abs(touch.clientX - touchScroll.x);
        const dy = Math.abs(touch.clientY - touchScroll.y);
        if (Math.max(dx, dy) < 8) return;
        if (dx > dy || performance.now() - touchScroll.started > 500 || term.hasSelection()) {
          resetTouch(); return;
        }
        touchScroll.dragging = true;
      }
      // Stop xterm's own handler as well, otherwise mouse-reporting-off sessions
      // scroll twice. At boundaries don't scroll the enclosing HA page instead.
      event.preventDefault();
      event.stopImmediatePropagation();
      const height = term.element.querySelector('.xterm-screen').getBoundingClientRect().height / term.rows;
      if (!height) return;
      touchScroll.remainder += (touchScroll.previousY - touch.clientY) / height;
      touchScroll.previousY = touch.clientY;
      const lines = Math.trunc(touchScroll.remainder);
      touchScroll.remainder -= lines;
      if (lines) term.scrollLines(lines);
    }, { capture: true, passive: false });
    term.element.addEventListener('touchend', event => {
      if (touchScroll?.dragging) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
      resetTouch();
    }, { capture: true, passive: false });
    term.element.addEventListener('touchcancel', resetTouch, { capture: true, passive: true });
    let lastBackground;
    term.onRender(() => {
      const background = term.options.theme?.background;
      if (!background || background === lastBackground) return;
      lastBackground = background;
      const light = background === '#eff1f5';
      for (const [name, value] of Object.entries(light
        ? { bg: '#eff1f5', fg: '#4c4f69', border: '#bcc0cc', button: '#e6e9ef', accent: '#1e66f5' }
        : { bg: '#181825', fg: '#cdd6f4', border: '#45475a', button: '#313244', accent: '#89b4fa' })) {
        document.documentElement.style.setProperty(`--bar-${name}`, value);
      }
    });

    function show(mode, value = '', help) {
      cancelDictation();
      dialogMode = mode;
      const editable = mode === 'paste' || mode === 'dictate';
      dialog.querySelector('h2').textContent = mode === 'history' ? text.historyTitle : text[mode];
      dialog.querySelector('p').textContent = help ?? (mode === 'paste' ? text.manualPaste : mode === 'history' ? text.historyHint : text.manualCopy);
      field.readOnly = !editable;
      field.value = value;
      action.textContent = editable ? text.insert : text.copy;
      dialog.querySelector('#dialog-download').hidden = mode !== 'history';
      if (!dialog.open) dialog.showModal();
      field.focus();
      // Selecting the whole history on touch devices makes swipes manipulate
      // selection handles instead of scrolling. Copy still selects on demand.
      if (mode === 'copy' || (mode === 'history' && !matchMedia('(pointer: coarse)').matches)) field.select();
      else if (mode === 'history') {
        field.setSelectionRange(0, 0);
        field.scrollTop = 0;
      }
    }
    async function copy(value, fallback = true) {
      if (!value) { status.textContent = text.select; return; }
      try {
        await navigator.clipboard.writeText(value);
        status.textContent = text.copied;
      } catch {
        // HTTP HA and iframe permissions can block the asynchronous API.
        // A visible, selected textarea keeps native copy available everywhere.
        if (fallback) show('copy', value);
        field.focus();
        field.select();
        try {
          if (document.execCommand('copy')) {
            status.textContent = text.copied;
            dialog.querySelector('p').textContent = text.copied;
          }
        } catch { /* Native menu / keyboard copy remains available. */ }
      }
    }
    function insert(value, message = text.inserted) {
      if (!value) { status.textContent = text.empty; return; }
      // xterm handles bracketed paste; never send text as synthetic key events.
      term.paste(value);
      status.textContent = message;
      term.focus();
    }

    const dictateButton = toolbar.querySelector('#dictate');
    let dictation;

    function insertDictation(value) {
      // Keep line breaks and terminal control characters out of dictated input.
      const transcript = value.replace(/[\t\r\n\u0085\u2028\u2029]+/g, ' ')
        .replace(/[\u0000-\u001f\u007f-\u009f]/g, '').trim();
      if (transcript) insert(transcript, text.dictationInserted);
      return Boolean(transcript);
    }

    function resetDictation(session) {
      if (dictation !== session) return false;
      clearTimeout(session.timeout);
      dictation = undefined;
      dictateButton.disabled = false;
      dictateButton.textContent = text.dictate;
      dictateButton.removeAttribute('aria-label');
      dictateButton.removeAttribute('data-listening');
      return true;
    }

    function cancelDictation() {
      if (!dictation) return;
      const session = dictation;
      resetDictation(session);
      session.recognition.abort();
      status.textContent = text.dictationCancelled;
    }

    function dictationFallback(reason) {
      status.textContent = reason;
      show('dictate', '', `${reason} ${text.dictationKeyboard}`);
    }

    function finishDictation(session, failure) {
      if (!resetDictation(session)) return;
      if (window.term !== term || term.options.disableStdin) {
        status.textContent = text.dictationCancelled;
        return;
      }
      if (insertDictation(session.results.filter(Boolean).join(' '))) return;
      if (failure) dictationFallback(failure);
      else status.textContent = text.dictationEmpty;
    }

    function watchDictation(session, timeout) {
      clearTimeout(session.timeout);
      session.timeout = setTimeout(() => {
        finishDictation(session, text.dictationFailed);
        session.recognition.abort();
      }, timeout);
    }

    function transcribing(session) {
      if (dictation !== session || dictateButton.disabled) return;
      dictateButton.disabled = true;
      dictateButton.removeAttribute('data-listening');
      status.textContent = text.dictationFinishing;
      watchDictation(session, 15000);
    }

    dictateButton.onclick = () => {
      if (dictation) {
        const session = dictation;
        transcribing(session);
        try { session.recognition.stop(); }
        catch { finishDictation(session, text.dictationFailed); }
        return;
      }
      if (!window.isSecureContext) { dictationFallback(text.dictationHttps); return; }
      const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!Recognition) { dictationFallback(text.dictationUnavailable); return; }
      const policy = document.permissionsPolicy || document.featurePolicy;
      if (policy && !policy.allowsFeature('microphone')) { dictationFallback(text.dictationBlocked); return; }

      const recognition = new Recognition();
      const session = { recognition, results: [] };
      recognition.lang = navigator.language;
      // Android's speech service can finish on a pause, even in continuous mode.
      recognition.continuous = !/Android/i.test(navigator.userAgent);
      recognition.onaudiostart = () => {
        if (dictation !== session || dictateButton.disabled) return;
        clearTimeout(session.timeout);
        dictateButton.setAttribute('data-listening', '');
        status.textContent = text.dictationListening;
      };
      recognition.onaudioend = () => transcribing(session);
      recognition.onresult = event => {
        if (dictation !== session) return;
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) session.results[i] = result[0].transcript.trim();
        }
      };
      recognition.onerror = event => {
        const blocked = ['not-allowed', 'service-not-allowed', 'audio-capture'].includes(event.error);
        const failure = blocked ? text.dictationBlocked : text.dictationFailed;
        finishDictation(session, event.error === 'no-speech' ? undefined : failure);
      };
      recognition.onend = () => finishDictation(session);

      dictation = session;
      dictateButton.textContent = text.stop;
      dictateButton.setAttribute('aria-label', text.stopDictation);
      status.textContent = text.dictationStarting;
      watchDictation(session, 30000);
      try { recognition.start(); }
      catch { finishDictation(session, text.dictationFailed); }
    };
    // A submitted or interrupted prompt is no longer the draft we were dictating.
    term.onData(value => { if (dictation && /[\r\n\u0003\u0004]/.test(value)) cancelDictation(); });
    window.addEventListener('pagehide', cancelDictation);

    let uploading = false;
    const imageTypes = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];
    const uploadUrl = kind => new URL(`${location.pathname.replace(/\/?$/, '/')}codex-upload-${kind}`, location.origin);
    async function uploadImage(file, target = null) {
      if (uploading) { status.textContent = text.imageBusy; return; }
      if (!imageTypes.includes(file.type) || !file.size || file.size >= 10 * 1024 * 1024) {
        status.textContent = text.imageSize; return;
      }
      uploading = true;
      status.textContent = text.uploading;
      toolbar.querySelector('#image').disabled = true;
      try {
        const signal = AbortSignal.timeout(45000);
        const session = await fetch(uploadUrl('token'), { cache: 'no-store', signal });
        if (!session.ok) throw new Error('token');
        const { token } = await session.json();
        const response = await fetch(uploadUrl('image'), { method: 'POST', signal,
          headers: { 'Content-Type': file.type, 'X-Codex-Upload-Token': token }, body: file });
        if (!response.ok) throw new Error('upload');
        const { path } = await response.json();
        if (!/^\/homeassistant\/tmp\/codex\/[a-f0-9]{32}\.(png|jpg|gif|webp)$/.test(path)) throw new Error('path');
        const value = ` ${path} `;
        if (target === field && dialog.open && dialogMode === 'paste') {
          field.setRangeText(value, field.selectionStart, field.selectionEnd, 'end');
          field.focus();
        } else if (!target && window.term === term && !term.options.disableStdin) {
          insert(value);
        } else {
          // A disconnected terminal or closed dialog must not receive late input.
          status.textContent = text.imageSaved + path;
          return;
        }
        status.textContent = text.imageReady;
      } catch {
        status.textContent = text.imageFailed;
      } finally {
        uploading = false;
        toolbar.querySelector('#image').disabled = false;
      }
    }
    // Capture images before xterm interprets a paste as text. Leave text-only
    // events untouched, including bracketed paste and the manual paste dialog.
    document.addEventListener('paste', event => {
      const target = event.target;
      const inField = target === field && dialogMode === 'paste';
      if (!term.element.contains(target) && !inField) return;
      const file = Array.from(event.clipboardData?.files || []).find(item => item.type.startsWith('image/'));
      if (!file) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      void uploadImage(file, inField ? field : null);
    }, true);
    async function paste() {
      try {
        if (navigator.clipboard.read) {
          const items = await navigator.clipboard.read();
          for (const item of items) {
            const type = item.types.find(type => imageTypes.includes(type));
            if (type) { await uploadImage(await item.getType(type)); return; }
          }
        }
        insert(await navigator.clipboard.readText());
      } catch { show('paste'); }
    }
    toolbar.querySelector('#image').onclick = () => imagePicker.click();
    imagePicker.onchange = () => {
      const file = imagePicker.files[0];
      imagePicker.value = '';
      if (file) void uploadImage(file);
    };
    function history() {
      const buffer = term.buffer.active;
      const lines = [];
      for (let i = 0; i < buffer.length; i++) {
        const line = buffer.getLine(i);
        const rendered = line?.translateToString(!buffer.getLine(i + 1)?.isWrapped) || '';
        // Rejoin terminal-width wrapping without changing actual line breaks.
        if (line?.isWrapped && lines.length) lines[lines.length - 1] += rendered;
        else lines.push(rendered);
      }
      show('history', lines.join('\n').trimEnd());
    }
    toolbar.querySelector('#copy').onclick = () => copy(selection);
    toolbar.querySelector('#paste').onclick = paste;
    toolbar.querySelector('#history').onclick = history;
    toolbar.querySelector('#latest').onclick = () => {
      term.scrollToBottom(); term.focus(); status.textContent = text.latestHint;
    };
    dialog.querySelector('#dialog-close').onclick = () => dialog.close();
    dialog.addEventListener('close', () => { field.value = ''; term.focus(); });
    action.onclick = () => {
      if (dialogMode === 'dictate') {
        if (insertDictation(field.value)) dialog.close();
        else status.textContent = text.empty;
      } else if (dialogMode === 'paste') {
        const value = field.value;
        dialog.close();
        insert(value);
      } else copy(field.value, false);
    };
    dialog.querySelector('#dialog-download').onclick = () => {
      const url = URL.createObjectURL(new Blob([field.value], { type: 'text/plain;charset=utf-8' }));
      const link = document.createElement('a');
      link.href = url; link.download = 'codex-terminal.txt'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
    term.attachCustomKeyEventHandler(event => {
      if (event.type !== 'keydown' || !(event.ctrlKey || event.metaKey)) return true;
      const key = event.key.toLowerCase();
      if (key === 'c' && (term.hasSelection() || event.shiftKey)) {
        event.preventDefault(); copy(term.getSelection() || selection); return false;
      }
      if (key === 'v') {
        if (event.shiftKey) { event.preventDefault(); paste(); }
        // For ordinary Ctrl/Cmd+V let the browser deliver its native paste event.
        return false;
      }
      return true;
    });
    fit();
  }
  // ttyd mounts after its token request; no arbitrary startup delay is assumed.
  const timer = setInterval(() => {
    if (!window.term?.element) return;
    clearInterval(timer);
    attach(window.term);
  }, 50);
})();
