(function (window, document, BX) {
    'use strict';

    if (!window || !document || !BX) {
        return;
    }

    var INSTANCE_KEY = '__AIChatWrapperInstance';
    var POLL_INTERVAL_MS = 3000;

    function extractErrorMessage(error) {
        if (error && error.errors && error.errors.length && error.errors[0].message) {
            return error.errors[0].message;
        }
        if (error && error.statusText) {
            return error.statusText;
        }
        return 'Не удалось выполнить запрос. Попробуйте еще раз.';
    }

    function escapeHtml(text) {
        return String(text || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function storeToken(bucket, html, prefix) {
        bucket.push(html);
        return '\u0000' + prefix + bucket.length + '\u0000';
    }

    function restoreTokens(text, bucket, prefix) {
        return text.replace(new RegExp('\\u0000' + prefix + '(\\d+)\\u0000', 'g'), function (_, index) {
            var item = bucket[Number(index) - 1];
            return item || '';
        });
    }

    function normalizeHref(url) {
        var value = String(url || '').trim();
        if (!value) {
            return '';
        }
        if (/^(https?:\/\/|mailto:|tel:)/i.test(value)) {
            return value;
        }
        if (/^www\./i.test(value)) {
            return 'https://' + value;
        }
        if (value.charAt(0) === '/') {
            return value;
        }
        return '';
    }

    function buildAnchorHtml(label, url) {
        var href = normalizeHref(url);
        var text = String(label || url || '');
        var origin = window.location && window.location.origin ? window.location.origin : '';
        var isExternal = /^(https?:)?\/\//i.test(href) && origin && href.indexOf(origin) !== 0;

        if (!href) {
            return escapeHtml(text);
        }

        return '<a class="ai-chat-widget__link" href="' + escapeHtml(href) + '"' + (isExternal ? ' target="_blank" rel="noopener noreferrer"' : '') + '>' + escapeHtml(text) + '</a>';
    }

    function splitTrailingLinkPunctuation(candidate) {
        var url = String(candidate || '');
        var trailing = '';

        while (/[),.!?:;]$/.test(url)) {
            trailing = url.slice(-1) + trailing;
            url = url.slice(0, -1);
        }

        return {
            url: url,
            trailing: trailing
        };
    }

    function linkifyText(html, linkTokens) {
        var pattern = /(^|[\s(>])((?:https?:\/\/|www\.)[^\s<]+|(?:mailto:|tel:)[^\s<]+|\/[A-Za-z0-9А-Яа-я._~%+\-\/?#=&]+)/g;

        return html.replace(pattern, function (_, prefix, candidate) {
            var parts = splitTrailingLinkPunctuation(candidate);

            if (!normalizeHref(parts.url)) {
                return prefix + candidate;
            }

            return prefix + storeToken(linkTokens, buildAnchorHtml(parts.url, parts.url), 'LINK') + parts.trailing;
        });
    }

    function applyEmphasis(html) {
        html = html.replace(/~~([^~\n][\s\S]*?[^~\n]|[^~\n])~~/g, '<s>$1</s>');
        html = html.replace(/\*\*\*([^*\n][\s\S]*?[^*\n]|[^*\n])\*\*\*/g, '<strong><em>$1</em></strong>');
        html = html.replace(/\*\*([^*\n][\s\S]*?[^*\n]|[^*\n])\*\*/g, '<strong>$1</strong>');
        html = html.replace(/__([^_\n][\s\S]*?[^_\n]|[^_\n])__/g, '<strong>$1</strong>');
        html = html.replace(/(^|[^\w*])\*([^*\n][\s\S]*?[^*\n]|[^*\n])\*(?![\w*])/g, '$1<em>$2</em>');
        html = html.replace(/(^|[^\w_])_([^_\n][\s\S]*?[^_\n]|[^_\n])_(?![\w_])/g, '$1<em>$2</em>');
        return html;
    }

    function renderInline(text) {
        var html = escapeHtml(text || '');
        var linkTokens = [];
        var codeTokens = [];

        html = html.replace(/`([^`]+)`/g, function (_, code) {
            return storeToken(codeTokens, '<code>' + code + '</code>', 'CODE');
        });

        html = html.replace(/\[([^\]]+)\]\(((?:https?:\/\/|www\.|mailto:|tel:|\/)[^\s)]+)\)/g, function (_, label, url) {
            return storeToken(linkTokens, buildAnchorHtml(label, url), 'LINK');
        });

        html = linkifyText(html, linkTokens);
        html = applyEmphasis(html);
        html = restoreTokens(html, linkTokens, 'LINK');
        html = restoreTokens(html, codeTokens, 'CODE');

        return html;
    }

    function renderCodeBlock(code) {
        return '<pre><code>' + escapeHtml(code).replace(/\n$/, '') + '</code></pre>';
    }

    function renderParagraph(lines) {
        return '<p>' + lines.map(function (line) {
            return renderInline(line);
        }).join('<br>') + '</p>';
    }

    function renderList(lines, ordered) {
        var tag = ordered ? 'ol' : 'ul';
        var pattern = ordered ? /^\s*\d+\.\s+/ : /^\s*[-*]\s+/;

        return '<' + tag + '>' + lines.map(function (line) {
            return '<li>' + renderInline(line.replace(pattern, '')) + '</li>';
        }).join('') + '</' + tag + '>';
    }

    function renderBlockquote(lines) {
        return '<blockquote>' + renderParagraph(lines.map(function (line) {
            return line.replace(/^\s*>\s?/, '');
        })) + '</blockquote>';
    }

    function renderHeading(line) {
        var match = line.match(/^\s*(#{1,3})\s+(.+)\s*$/);
        if (!match) {
            return '';
        }

        return '<h' + match[1].length + '>' + renderInline(match[2]) + '</h' + match[1].length + '>';
    }

    function renderMarkdown(text) {
        var source = String(text || '').replace(/\r\n?/g, '\n');
        var blockTokens = [];
        var blocks;

        source = source.replace(/```([\s\S]*?)```/g, function (_, code) {
            return storeToken(blockTokens, renderCodeBlock(code), 'BLOCK');
        });

        blocks = source.split(/\n{2,}/);

        return restoreTokens(blocks.map(function (block) {
            var trimmed = block.trim();
            var lines;
            var ordered;

            if (!trimmed) {
                return '';
            }

            if (/^\u0000BLOCK\d+\u0000$/.test(trimmed)) {
                return trimmed;
            }

            lines = trimmed.split('\n');
            ordered = lines.every(function (line) {
                return /^\s*\d+\.\s+/.test(line);
            });

            if (/^\s*(#{1,3})\s+/.test(trimmed) && lines.length === 1) {
                return renderHeading(trimmed);
            }

            if (/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(trimmed)) {
                return '<hr>';
            }

            if (lines.every(function (line) { return /^\s*>\s?/.test(line); })) {
                return renderBlockquote(lines);
            }

            if (lines.every(function (line) { return /^\s*[-*]\s+/.test(line); })) {
                return renderList(lines, false);
            }

            if (ordered) {
                return renderList(lines, true);
            }

            return renderParagraph(lines);
        }).join(''), blockTokens, 'BLOCK');
    }

    function isObject(value) {
        return !!value && typeof value === 'object' && !Array.isArray(value);
    }

    function ensureArray(value) {
        return Array.isArray(value) ? value : [];
    }

    function safeInteger(value) {
        var parsed = parseInt(value, 10);
        return isNaN(parsed) ? null : parsed;
    }

    function safeNumber(value) {
        var parsed = Number(value);
        return isNaN(parsed) ? null : parsed;
    }

    function formatPrice(price, currency) {
        var amount = safeNumber(price);
        if (amount === null) {
            return '';
        }

        if (currency) {
            try {
                return new Intl.NumberFormat('ru-RU', {
                    style: 'currency',
                    currency: String(currency)
                }).format(amount);
            } catch (error) {}
        }

        return String(amount.toFixed(2)) + (currency ? ' ' + String(currency) : '');
    }

    function formatMessageTime(value) {
        var date = value ? new Date(value) : new Date();

        if (isNaN(date.getTime())) {
            date = new Date();
        }

        try {
            return new Intl.DateTimeFormat('ru-RU', {
                hour: '2-digit',
                minute: '2-digit'
            }).format(date);
        } catch (error) {
            return String(date.getHours()).padStart(2, '0') + ':' + String(date.getMinutes()).padStart(2, '0');
        }
    }

    function normalizeInteractiveAction(action) {
        if (!isObject(action)) {
            return null;
        }

        return {
            id: String(action.id || ''),
            type: String(action.type || ''),
            label: String(action.label || ''),
            style: String(action.style || 'secondary'),
            offer_id: safeInteger(action.offer_id),
            quantity: safeInteger(action.quantity),
            url: action.url ? String(action.url) : '',
            prompt: action.prompt ? String(action.prompt) : '',
            action_token: action.action_token ? String(action.action_token) : '',
            disabled: !!action.disabled,
            completed: !!action.completed
        };
    }

    function normalizeInteractivePayload(interactive) {
        var cards;
        var messageActions;

        if (!isObject(interactive)) {
            return null;
        }

        cards = ensureArray(interactive.cards).map(function (card) {
            if (!isObject(card)) {
                return null;
            }

            return {
                id: String(card.id || ''),
                product_id: safeInteger(card.product_id),
                offer_id: safeInteger(card.offer_id),
                intent: String(card.intent || 'recommend'),
                title: String(card.title || ''),
                reason: card.reason ? String(card.reason) : '',
                detail_page_url: card.detail_page_url ? String(card.detail_page_url) : '',
                price: safeNumber(card.price),
                currency: card.currency ? String(card.currency) : '',
                in_stock: typeof card.in_stock === 'boolean' ? card.in_stock : null,
                availability_text: card.availability_text ? String(card.availability_text) : '',
                actions: ensureArray(card.actions).map(normalizeInteractiveAction).filter(Boolean)
            };
        }).filter(Boolean);

        messageActions = ensureArray(interactive.message_actions).map(normalizeInteractiveAction).filter(Boolean);

        if (!cards.length && !messageActions.length) {
            return null;
        }

        return {
            cards: cards,
            message_actions: messageActions
        };
    }

    function normalizeMessage(message) {
        var interactive;

        if (!isObject(message)) {
            return null;
        }

        interactive = normalizeInteractivePayload(message.interactive);

        if (!message.text && !interactive) {
            return null;
        }

        return {
            id: safeInteger(message.id),
            role: String(message.role || 'assistant'),
            text: message.text ? String(message.text) : '',
            created_at: message.created_at ? String(message.created_at) : '',
            interactive: interactive
        };
    }

    function renderInteractiveAction(action, messageId, isLocked) {
        var classes = ['ai-chat-widget__interactive-action', 'ai-chat-widget__interactive-action--' + escapeHtml(action.style || 'secondary')];
        var label = escapeHtml(action.label || '');
        var disabled = !!action.disabled || !label || (action.type === 'cart_add' && (!action.action_token || !action.offer_id));
        var lockedDisabled = !!isLocked && action.type !== 'open_url' && !action.completed;
        var actionType = escapeHtml(action.type || '');
        var actionId = escapeHtml(action.id || '');
        var prompt = escapeHtml(action.prompt || '');
        var url = escapeHtml(action.url || '');
        var token = escapeHtml(action.action_token || '');

        if (action.completed) {
            classes.push('is-completed');
        }
        if (disabled || lockedDisabled) {
            classes.push('is-disabled');
        }

        return '<button type="button" class="' + classes.join(' ') + '"' +
            ' data-interactive-action="1"' +
            ' data-message-id="' + escapeHtml(String(messageId || '')) + '"' +
            ' data-action-id="' + actionId + '"' +
            ' data-action-type="' + actionType + '"' +
            ' data-action-url="' + url + '"' +
            ' data-action-prompt="' + prompt + '"' +
            ' data-action-token="' + token + '"' +
            (disabled || lockedDisabled ? ' disabled' : '') +
            '>' + label + '</button>';
    }

    function renderInteractiveCards(cards, messageId, isLocked) {
        return cards.map(function (card) {
            var meta = [];
            var priceText = formatPrice(card.price, card.currency);
            var reasonHtml = card.reason ? '<div class="ai-chat-widget__card-reason">' + renderMarkdown(card.reason) + '</div>' : '';
            var actionsHtml = card.actions.length
                ? '<div class="ai-chat-widget__interactive-actions">' + card.actions.map(function (action) {
                    return renderInteractiveAction(action, messageId, isLocked);
                }).join('') + '</div>'
                : '';

            if (priceText) {
                meta.push('<span class="ai-chat-widget__card-chip">' + escapeHtml(priceText) + '</span>');
            }
            if (card.availability_text) {
                meta.push('<span class="ai-chat-widget__card-chip' + (card.in_stock === false ? ' is-muted' : '') + '">' + escapeHtml(card.availability_text) + '</span>');
            }

            return '<section class="ai-chat-widget__card">' +
                '<div class="ai-chat-widget__card-title">' + escapeHtml(card.title || '') + '</div>' +
                reasonHtml +
                (meta.length ? '<div class="ai-chat-widget__card-meta">' + meta.join('') + '</div>' : '') +
                actionsHtml +
                '</section>';
        }).join('');
    }

    function renderInteractivePayload(interactive, messageId, isLocked) {
        var html = '';

        if (!interactive) {
            return html;
        }

        if (interactive.cards.length) {
            html += '<div class="ai-chat-widget__interactive-cards">' + renderInteractiveCards(interactive.cards, messageId, isLocked) + '</div>';
        }

        if (interactive.message_actions.length) {
            html += '<div class="ai-chat-widget__interactive-footer">' +
                '<div class="ai-chat-widget__interactive-actions">' + interactive.message_actions.map(function (action) {
                    return renderInteractiveAction(action, messageId, isLocked);
                }).join('') + '</div>' +
                '</div>';
        }

        return html;
    }

    function ChatWrapper(root, config) {
        this.root = root;
        this.config = config || {};
        this.launcher = root.querySelector('[data-role="launcher"]');
        this.backdrop = root.querySelector('[data-role="backdrop"]');
        this.panel = root.querySelector('[data-role="panel"]');
        this.closeButton = root.querySelector('[data-role="close"]');
        this.history = root.querySelector('[data-role="history"]');
        this.emptyState = root.querySelector('[data-role="empty-state"]');
        this.launcherBadge = root.querySelector('[data-role="launcher-badge"]');
        this.textarea = root.querySelector('[data-role="textarea"]');
        this.sendButton = root.querySelector('[data-role="send"]');
        this.resetButton = root.querySelector('[data-role="reset"]');
        this.otpBox = root.querySelector('[data-role="otp"]');
        this.otpInput = root.querySelector('[data-role="otp-input"]');
        this.otpVerifyButton = root.querySelector('[data-role="otp-verify"]');
        this.otpResendButton = root.querySelector('[data-role="otp-resend"]');
        this.otpMessage = root.querySelector('[data-role="otp-message"]');
        this.modeSwitch = root.querySelector('[data-role="mode-switch"]');
        this.resizeHandle = null;
        this.sessionId = safeInteger(this.config.session_id);
        this.messages = [];
        this.activeJob = null;
        this.isRequestInFlight = false;
        this.pollTimer = null;
        this.resizeState = null;
        this.hasUnreadMessages = false;
        this.hasHistorySnapshot = false;
        this.lastAssistantMessageId = 0;
        this.isPhoneVerified = false;
        this.pendingMessage = '';
        this.boundSyncLayout = this.syncLayout.bind(this);
        this.boundOnResizeMove = this.onResizeMove.bind(this);
        this.boundStopResize = this.stopResize.bind(this);
    }

    ChatWrapper.prototype.init = function () {
        var self = this;

        this.ensureResizeHandle();
        if (this.launcher) {
            this.launcher.addEventListener('click', function () {
                self.togglePanel();
            });
        }
        if (this.backdrop) {
            this.backdrop.addEventListener('click', function () {
                self.closePanel();
            });
        }
        if (this.closeButton) {
            this.closeButton.addEventListener('click', function () {
                self.closePanel();
            });
        }
        if (this.sendButton) {
            this.sendButton.addEventListener('click', function () {
                self.sendMessage();
            });
        }
        if (this.resetButton) {
            this.resetButton.addEventListener('click', function () {
                self.resetConversation();
            });
        }
        if (this.otpVerifyButton) {
            this.otpVerifyButton.addEventListener('click', function () {
                self.verifyOtp();
            });
        }
        if (this.otpResendButton) {
            this.otpResendButton.addEventListener('click', function () {
                self.requestOtp();
            });
        }
        if (this.otpInput) {
            this.otpInput.addEventListener('input', function () {
                this.value = this.value.replace(/\D/g, '').slice(0, 6);
            });
            this.otpInput.addEventListener('keydown', function (event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    self.verifyOtp();
                }
            });
        }
        if (this.textarea) {
            this.textarea.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    self.sendMessage();
                }
            });
        }
        if (this.resizeHandle) {
            this.resizeHandle.addEventListener('pointerdown', function (event) {
                self.startResize(event);
            });
        }
        if (this.history) {
            this.history.addEventListener('click', function (event) {
                self.handleInteractiveClick(event);
            });
        }
        if (this.modeSwitch) {
            this.modeSwitch.addEventListener('click', function (event) {
                var button = event.target.closest('[data-mode]');
                if (!button || self.isLocked()) {
                    return;
                }
                self.setMode(button.getAttribute('data-mode'));
            });
        }

        window.addEventListener('resize', this.boundSyncLayout);
        window.addEventListener('orientationchange', this.boundSyncLayout);
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                self.closePanel();
            }
        });

        this.syncLayout();
        this.updateModeButtons();
        this.updateLauncherUnreadState(false);
        this.updateControls();
        this.renderEmptyState();
    };

    ChatWrapper.prototype.isPanelOpen = function () {
        return !!this.panel && !this.panel.hidden;
    };

    ChatWrapper.prototype.updateLauncherUnreadState = function (hasUnreadMessages) {
        this.hasUnreadMessages = !!hasUnreadMessages;
        this.root.classList.toggle('has-unread', this.hasUnreadMessages);
        if (this.launcherBadge) {
            this.launcherBadge.hidden = !this.hasUnreadMessages;
        }
    };

    ChatWrapper.prototype.ensureResizeHandle = function () {
        if (!this.panel) {
            return;
        }
        this.resizeHandle = this.panel.querySelector('[data-role="resize-handle"]');
        if (this.resizeHandle) {
            return;
        }
        this.resizeHandle = document.createElement('div');
        this.resizeHandle.className = 'ai-chat-widget__resize-handle';
        this.resizeHandle.setAttribute('data-role', 'resize-handle');
        this.resizeHandle.setAttribute('aria-hidden', 'true');
        this.panel.appendChild(this.resizeHandle);
    };

    ChatWrapper.prototype.syncLayout = function () {
        var isMobile = window.matchMedia && window.matchMedia('(max-width: 640px)').matches;

        this.root.style.setProperty('display', 'flex', 'important');
        this.root.style.setProperty('flex-direction', 'column', 'important');
        this.root.style.setProperty('align-items', 'flex-end', 'important');
        this.root.style.setProperty('left', 'auto', 'important');
        this.root.style.setProperty('width', 'auto', 'important');

        if (isMobile) {
            this.root.style.setProperty('right', 'max(12px, var(--side-base, 12px))', 'important');
            this.root.style.setProperty(
                'bottom',
                'max(12px, calc(var(--bottom-bar-height, 0px) + var(--bottom-catalog-bar-height, 0px) + var(--compare-list-offset, 0px) + var(--toolbar-devices-offset, 0px) + 12px))',
                'important'
            );
            if (this.panel) {
                this.panel.style.setProperty('width', 'calc(100vw - 16px)', 'important');
                this.panel.style.setProperty('min-width', '0', 'important');
                this.panel.style.setProperty('max-width', '420px', 'important');
                this.panel.style.setProperty('height', 'min(82svh, calc(100dvh - env(safe-area-inset-top, 0px) - 16px))', 'important');
                this.panel.style.setProperty('max-height', 'calc(100dvh - env(safe-area-inset-top, 0px) - 16px)', 'important');
                this.panel.style.setProperty('min-height', '0', 'important');
            }
            return;
        }

        this.root.style.setProperty('right', '24px', 'important');
        this.root.style.setProperty('bottom', '24px', 'important');
        if (this.panel) {
            this.panel.style.removeProperty('width');
            this.panel.style.removeProperty('min-width');
            this.panel.style.removeProperty('max-width');
            this.panel.style.removeProperty('height');
            this.panel.style.removeProperty('max-height');
            this.panel.style.removeProperty('min-height');
        }
    };

    ChatWrapper.prototype.getDesktopPanelMinWidth = function () {
        return Math.max(320, Math.min(390, window.innerWidth - 32));
    };

    ChatWrapper.prototype.getDesktopPanelMinHeight = function () {
        return Math.max(420, Math.min(640, window.innerHeight - 110));
    };

    ChatWrapper.prototype.startResize = function (event) {
        var rect;
        var pointerId;

        if (!this.panel || window.matchMedia('(max-width: 640px)').matches) {
            return;
        }
        if (event.button !== undefined && event.button !== 0) {
            return;
        }

        rect = this.panel.getBoundingClientRect();
        pointerId = typeof event.pointerId === 'number' ? event.pointerId : null;
        this.resizeState = {
            pointerId: pointerId,
            startX: event.clientX,
            startY: event.clientY,
            startWidth: rect.width,
            startHeight: rect.height
        };

        if (this.resizeHandle && this.resizeHandle.setPointerCapture && pointerId !== null) {
            this.resizeHandle.setPointerCapture(pointerId);
        }
        document.documentElement.classList.add('ai-chat-resizing');
        window.addEventListener('pointermove', this.boundOnResizeMove);
        window.addEventListener('pointerup', this.boundStopResize);
        window.addEventListener('pointercancel', this.boundStopResize);
        event.preventDefault();
    };

    ChatWrapper.prototype.onResizeMove = function (event) {
        var minWidth;
        var minHeight;
        var maxWidth;
        var maxHeight;
        var newWidth;
        var newHeight;

        if (!this.panel || !this.resizeState) {
            return;
        }

        minWidth = this.getDesktopPanelMinWidth();
        minHeight = this.getDesktopPanelMinHeight();
        maxWidth = Math.max(minWidth, window.innerWidth - 32);
        maxHeight = Math.max(minHeight, window.innerHeight - 32);
        newWidth = this.resizeState.startWidth - (event.clientX - this.resizeState.startX);
        newHeight = this.resizeState.startHeight - (event.clientY - this.resizeState.startY);
        newWidth = Math.min(maxWidth, Math.max(minWidth, newWidth));
        newHeight = Math.min(maxHeight, Math.max(minHeight, newHeight));

        this.panel.style.width = String(Math.round(newWidth)) + 'px';
        this.panel.style.height = String(Math.round(newHeight)) + 'px';
        this.panel.style.minWidth = String(Math.round(minWidth)) + 'px';
        this.panel.style.minHeight = String(Math.round(minHeight)) + 'px';
        event.preventDefault();
    };

    ChatWrapper.prototype.stopResize = function (event) {
        if (this.resizeHandle && this.resizeState && this.resizeHandle.releasePointerCapture && this.resizeState.pointerId !== null) {
            try {
                this.resizeHandle.releasePointerCapture(this.resizeState.pointerId);
            } catch (error) {}
        }
        this.resizeState = null;
        document.documentElement.classList.remove('ai-chat-resizing');
        window.removeEventListener('pointermove', this.boundOnResizeMove);
        window.removeEventListener('pointerup', this.boundStopResize);
        window.removeEventListener('pointercancel', this.boundStopResize);
        if (event && typeof event.preventDefault === 'function') {
            event.preventDefault();
        }
    };

    ChatWrapper.prototype.togglePanel = function () {
        if (!this.panel) {
            return;
        }
        if (this.panel.hidden) {
            this.openPanel();
            return;
        }
        this.closePanel();
    };

    ChatWrapper.prototype.openPanel = function () {
        if (!this.panel) {
            return;
        }
        this.updateLauncherUnreadState(false);
        if (this.backdrop) {
            this.backdrop.hidden = false;
            this.backdrop.style.display = 'block';
        }
        this.panel.hidden = false;
        this.panel.style.display = 'flex';
        this.root.classList.add('is-open');
        document.documentElement.classList.add('ai-chat-open');
        document.body.classList.add('ai-chat-open');
        if (this.launcher) {
            this.launcher.setAttribute('aria-expanded', 'true');
        }
        if (this.config.isAuthorized) {
            this.loadHistory(false);
        }
        if (this.textarea && !this.textarea.disabled) {
            window.setTimeout(function () {
                try {
                    this.textarea.focus();
                } catch (error) {}
            }.bind(this), 120);
        }
    };

    ChatWrapper.prototype.closePanel = function () {
        if (!this.panel) {
            return;
        }
        if (this.backdrop) {
            this.backdrop.hidden = true;
            this.backdrop.style.display = 'none';
        }
        this.panel.hidden = true;
        this.panel.style.display = 'none';
        this.root.classList.remove('is-open');
        document.documentElement.classList.remove('ai-chat-open');
        document.body.classList.remove('ai-chat-open');
        if (this.launcher) {
            this.launcher.setAttribute('aria-expanded', 'false');
        }
    };

    ChatWrapper.prototype.runAction = function (action, data) {
        var payload = Object.assign({}, data || {});
        payload.sessid = BX.bitrix_sessid();

        return BX.ajax.runComponentAction(this.config.componentName, action, {
            mode: 'class',
            data: payload,
            signedParameters: this.config.signedParameters || ''
        });
    };

    ChatWrapper.prototype.normalizeActiveJob = function (activeJob) {
        var status;

        if (!activeJob || typeof activeJob !== 'object') {
            return null;
        }

        status = String(activeJob.status || '').toLowerCase();
        if (status !== 'queued' && status !== 'processing') {
            return null;
        }

        return activeJob;
    };

    ChatWrapper.prototype.isLocked = function () {
        return this.isRequestInFlight || !!this.normalizeActiveJob(this.activeJob);
    };

    ChatWrapper.prototype.setRequestInFlight = function (state) {
        this.isRequestInFlight = !!state;
        this.updateControls();
    };

    ChatWrapper.prototype.updateControls = function () {
        var locked = this.isLocked();

        this.root.classList.toggle('is-busy', locked);
        if (this.sendButton) {
            this.sendButton.disabled = locked;
        }
        if (this.textarea) {
            this.textarea.disabled = locked;
        }
        if (this.resetButton) {
            this.resetButton.disabled = this.isRequestInFlight;
        }
        if (this.otpVerifyButton) {
            this.otpVerifyButton.disabled = locked;
        }
        if (this.otpResendButton) {
            this.otpResendButton.disabled = locked;
        }

        Array.prototype.forEach.call(this.root.querySelectorAll('[data-interactive-action]'), function (button) {
            var isCompleted = button.classList.contains('is-completed');
            if (!button.hasAttribute('data-action-type') || button.getAttribute('data-action-type') === 'open_url') {
                return;
            }
            button.disabled = locked || isCompleted || button.classList.contains('is-disabled');
        });

        Array.prototype.forEach.call(this.modeSwitch ? this.modeSwitch.querySelectorAll('[data-mode]') : [], function (button) {
            button.disabled = locked;
        });
    };

    ChatWrapper.prototype.startPolling = function () {
        var self = this;

        if (this.pollTimer) {
            return;
        }
        this.pollTimer = window.setInterval(function () {
            self.loadHistory(true);
        }, POLL_INTERVAL_MS);
    };

    ChatWrapper.prototype.stopPolling = function () {
        if (!this.pollTimer) {
            return;
        }
        window.clearInterval(this.pollTimer);
        this.pollTimer = null;
    };

    ChatWrapper.prototype.loadHistory = function (silent) {
        var self = this;

        this.runAction('loadHistory').then(function (response) {
            var data = response && response.data ? response.data : {};

            self.applyHistoryPayload(data, {
                preserveScroll: !!silent
            });
            if (self.activeJob) {
                self.startPolling();
            } else {
                self.stopPolling();
            }
        }).catch(function (error) {
            self.stopPolling();
            self.activeJob = null;
            self.updateControls();
            if (!silent) {
                self.appendMessage('system', extractErrorMessage(error), null);
            }
        });
    };

    ChatWrapper.prototype.applyHistoryPayload = function (data, renderOptions) {
        var normalizedMessages = ensureArray(data.messages).map(normalizeMessage).filter(Boolean);

        this.config.mode = data.mode || this.config.mode || 'expert';
        this.sessionId = safeInteger(data.session_id) || this.sessionId;
        this.activeJob = this.normalizeActiveJob(data.active_job || null);
        this.updateUnreadFromMessages(normalizedMessages);
        this.messages = normalizedMessages;
        this.updateModeButtons();
        this.renderHistory(this.messages, this.activeJob, renderOptions);
        this.updateControls();
    };

    ChatWrapper.prototype.updateUnreadFromMessages = function (messages) {
        var maxAssistantMessageId = this.lastAssistantMessageId;
        var hasNewAssistantMessage = false;
        var i;
        var message;

        for (i = 0; i < messages.length; i += 1) {
            message = messages[i];
            if (!message || message.role !== 'assistant' || !message.id) {
                continue;
            }
            if (this.hasHistorySnapshot && message.id > this.lastAssistantMessageId) {
                hasNewAssistantMessage = true;
            }
            if (message.id > maxAssistantMessageId) {
                maxAssistantMessageId = message.id;
            }
        }

        this.lastAssistantMessageId = maxAssistantMessageId;
        if (!this.hasHistorySnapshot) {
            this.hasHistorySnapshot = true;
        }

        if (this.isPanelOpen()) {
            this.updateLauncherUnreadState(false);
            return;
        }

        if (hasNewAssistantMessage) {
            this.updateLauncherUnreadState(true);
        }
    };

    ChatWrapper.prototype.buildClientContext = function () {
        return {
            url: window.location.href,
            path: window.location.pathname,
            title: document.title,
            referrer: document.referrer
        };
    };

    ChatWrapper.prototype.submitMessage = function (text, restoreOnError) {
        var self = this;

        if (!this.config.isAuthorized || this.isLocked() || !text) {
            return;
        }

        this.setRequestInFlight(true);
        this.runAction('sendMessage', {
            message: text,
            clientContext: this.buildClientContext()
        }).then(function (response) {
            var data = response && response.data ? response.data : {};

            self.applyHistoryPayload(data);
            if (self.activeJob) {
                self.startPolling();
            } else {
                self.stopPolling();
            }
            self.setRequestInFlight(false);
        }, function (error) {
            if (restoreOnError && self.textarea) {
                self.textarea.value = text;
            }
            self.appendMessage('system', extractErrorMessage(error), null);
            self.setRequestInFlight(false);
        });
    };

    ChatWrapper.prototype.showOtp = function (data) {
        if (this.otpBox) {
            this.otpBox.hidden = false;
        }
        if (this.otpMessage) {
            this.otpMessage.textContent = (data && data.message ? data.message + ' ' : '') +
                (data && data.phone_masked ? 'Номер: ' + data.phone_masked + '. ' : '') +
                (data && typeof data.resends_remaining === 'number'
                    ? 'Повторных отправок осталось: ' + data.resends_remaining + '.'
                    : '');
        }
        if (this.otpInput) {
            this.otpInput.value = '';
            this.otpInput.focus();
        }
    };

    ChatWrapper.prototype.hideOtp = function () {
        if (this.otpBox) {
            this.otpBox.hidden = true;
        }
    };

    ChatWrapper.prototype.requestOtp = function () {
        var self = this;

        if (!this.config.isAuthorized || this.isLocked()) {
            return;
        }
        this.setRequestInFlight(true);
        this.runAction('requestOtp').then(function (response) {
            var data = response && response.data ? response.data : {};
            self.isPhoneVerified = !!data.verified;
            if (self.isPhoneVerified) {
                self.hideOtp();
                self.setRequestInFlight(false);
                if (self.pendingMessage) {
                    var text = self.pendingMessage;
                    self.pendingMessage = '';
                    if (self.textarea) {
                        self.textarea.value = '';
                    }
                    self.submitMessage(text, true);
                }
                return;
            }
            self.showOtp(data);
            self.setRequestInFlight(false);
        }, function (error) {
            self.appendMessage('system', extractErrorMessage(error), null);
            self.setRequestInFlight(false);
        });
    };

    ChatWrapper.prototype.verifyOtp = function () {
        var self = this;
        var code = this.otpInput ? this.otpInput.value.trim() : '';

        if (!/^\d{6}$/.test(code) || this.isLocked()) {
            if (this.otpMessage) {
                this.otpMessage.textContent = 'Введите шестизначный код из SMS.';
            }
            return;
        }
        this.setRequestInFlight(true);
        this.runAction('verifyOtp', { code: code }).then(function (response) {
            var data = response && response.data ? response.data : {};
            self.isPhoneVerified = !!data.verified;
            self.hideOtp();
            self.setRequestInFlight(false);
            if (self.pendingMessage) {
                var text = self.pendingMessage;
                self.pendingMessage = '';
                if (self.textarea) {
                    self.textarea.value = '';
                }
                self.submitMessage(text, true);
            }
        }, function (error) {
            if (self.otpMessage) {
                self.otpMessage.textContent = extractErrorMessage(error);
            }
            self.setRequestInFlight(false);
        });
    };

    ChatWrapper.prototype.sendMessage = function () {
        var text = this.textarea ? this.textarea.value.trim() : '';

        if (!text) {
            return;
        }
        if (!this.isPhoneVerified) {
            this.pendingMessage = text;
            this.requestOtp();
            return;
        }
        if (this.textarea) {
            this.textarea.value = '';
        }
        this.submitMessage(text, true);
    };

    ChatWrapper.prototype.resetConversation = function () {
        var self = this;

        if (!this.config.isAuthorized || this.isRequestInFlight) {
            return;
        }

        this.setRequestInFlight(true);
        this.runAction('resetConversation').then(function () {
            self.stopPolling();
            self.activeJob = null;
            self.sessionId = null;
            self.messages = [];
            self.renderHistory([], null);
            self.setRequestInFlight(false);
        }, function (error) {
            self.appendMessage('system', extractErrorMessage(error), null);
            self.setRequestInFlight(false);
        });
    };

    ChatWrapper.prototype.setMode = function (mode) {
        var self = this;

        if (!mode || !this.config.isAuthorized || this.isLocked()) {
            return;
        }

        this.setRequestInFlight(true);
        this.runAction('setMode', { mode: mode }).then(function (response) {
            var data = response && response.data ? response.data : {};

            self.config.mode = data.mode || mode;
            self.updateModeButtons();
            self.setRequestInFlight(false);
        }, function (error) {
            self.appendMessage('system', extractErrorMessage(error), null);
            self.setRequestInFlight(false);
        });
    };

    ChatWrapper.prototype.updateModeButtons = function () {
        var activeMode = this.config.mode || 'expert';

        Array.prototype.forEach.call(this.modeSwitch ? this.modeSwitch.querySelectorAll('[data-mode]') : [], function (button) {
            button.classList.toggle('is-active', button.getAttribute('data-mode') === activeMode);
        });
    };

    ChatWrapper.prototype.clearMessages = function () {
        if (this.history) {
            this.history.innerHTML = '';
        }
    };

    ChatWrapper.prototype.isHistoryNearBottom = function (threshold) {
        var distance;

        if (!this.history) {
            return true;
        }

        distance = this.history.scrollHeight - this.history.clientHeight - this.history.scrollTop;
        return distance <= (typeof threshold === 'number' ? threshold : 24);
    };

    ChatWrapper.prototype.renderHistory = function (messages, activeJob, options) {
        var i;
        var preserveScroll = !!(options && options.preserveScroll);
        var previousScrollTop = this.history ? this.history.scrollTop : 0;
        var wasNearBottom = this.isHistoryNearBottom(24);

        this.clearMessages();
        for (i = 0; i < messages.length; i += 1) {
            this.appendMessage(messages[i].role || 'assistant', messages[i].text || '', messages[i], {
                scrollToBottom: false
            });
        }
        if (activeJob) {
            this.appendPendingMessage(activeJob, {
                scrollToBottom: false
            });
        }
        if (this.history) {
            if (!preserveScroll || wasNearBottom) {
                this.history.scrollTop = this.history.scrollHeight;
            } else {
                this.history.scrollTop = previousScrollTop;
            }
        }
        this.renderEmptyState();
    };

    ChatWrapper.prototype.appendPendingMessage = function (activeJob, options) {
        var text = activeJob && activeJob.status === 'queued'
            ? 'Запрос в очереди. Готовлю ответ...'
            : 'Формирую ответ...';

        this.appendMessage('pending', text, null, options);
    };

    ChatWrapper.prototype.appendMessage = function (role, text, message, options) {
        var interactive = message && message.interactive ? message.interactive : null;
        var messageId = message && message.id ? message.id : '';
        var createdAt = message && message.created_at ? message.created_at : '';
        var shouldScrollToBottom = !options || options.scrollToBottom !== false;
        var node;
        var bodyNode;
        var interactiveNode;
        var metaNode;

        if (!this.history || (!text && !interactive)) {
            return;
        }

        node = document.createElement('div');
        node.className = 'ai-chat-widget__message ai-chat-widget__message--' + role;
        if (messageId) {
            node.setAttribute('data-message-id', String(messageId));
        }

        if (text) {
            bodyNode = document.createElement('div');
            bodyNode.className = 'ai-chat-widget__message-body';
            bodyNode.innerHTML = renderMarkdown(text);
            node.appendChild(bodyNode);
        }

        if (interactive && role === 'assistant') {
            interactiveNode = document.createElement('div');
            interactiveNode.className = 'ai-chat-widget__interactive';
            interactiveNode.innerHTML = renderInteractivePayload(interactive, messageId, this.isLocked());
            node.appendChild(interactiveNode);
        }

        if (role === 'assistant' || role === 'user') {
            metaNode = document.createElement('div');
            metaNode.className = 'ai-chat-widget__message-meta';
            metaNode.textContent = formatMessageTime(createdAt);
            node.appendChild(metaNode);
        }

        this.history.appendChild(node);
        if (shouldScrollToBottom) {
            this.history.scrollTop = this.history.scrollHeight;
        }
    };

    ChatWrapper.prototype.renderEmptyState = function () {
        if (!this.emptyState || !this.history) {
            return;
        }
        this.emptyState.classList.toggle('is-hidden', this.history.children.length > 0);
    };

    ChatWrapper.prototype.findMessageById = function (messageId) {
        var i;

        for (i = 0; i < this.messages.length; i += 1) {
            if (this.messages[i].id === messageId) {
                return this.messages[i];
            }
        }
        return null;
    };

    ChatWrapper.prototype.findActionById = function (message, actionId) {
        var i;
        var j;
        var cards;
        var actions;

        if (!message || !message.interactive) {
            return null;
        }

        cards = ensureArray(message.interactive.cards);
        for (i = 0; i < cards.length; i += 1) {
            actions = ensureArray(cards[i].actions);
            for (j = 0; j < actions.length; j += 1) {
                if (actions[j].id === actionId) {
                    return actions[j];
                }
            }
        }

        actions = ensureArray(message.interactive.message_actions);
        for (i = 0; i < actions.length; i += 1) {
            if (actions[i].id === actionId) {
                return actions[i];
            }
        }

        return null;
    };

    ChatWrapper.prototype.upsertMessage = function (message) {
        var normalized = normalizeMessage(message);
        var i;

        if (!normalized || !normalized.id) {
            return;
        }

        for (i = 0; i < this.messages.length; i += 1) {
            if (this.messages[i].id === normalized.id) {
                this.messages[i] = normalized;
                return;
            }
        }

        this.messages.push(normalized);
    };

    ChatWrapper.prototype.handleInteractiveClick = function (event) {
        var button = event.target.closest('[data-interactive-action]');
        var messageId;
        var actionId;
        var message;
        var action;
        var href;

        if (!button) {
            return;
        }

        event.preventDefault();
        messageId = safeInteger(button.getAttribute('data-message-id'));
        actionId = String(button.getAttribute('data-action-id') || '');
        message = this.findMessageById(messageId);
        action = this.findActionById(message, actionId);

        if (!action) {
            return;
        }

        if (action.type === 'open_url') {
            href = normalizeHref(action.url);
            if (href) {
                if (/^\/personal\/cart\/?$/i.test(href)) {
                    window.location.href = href;
                } else {
                    window.open(href, '_blank', 'noopener');
                }
            }
            return;
        }

        if (action.type === 'ask_ai') {
            if (!action.prompt || this.isLocked()) {
                return;
            }
            this.submitMessage(action.prompt, false);
            return;
        }

        if (action.type === 'cart_add') {
            this.performCartAdd(message, action, button);
        }
    };

    ChatWrapper.prototype.performCartAdd = function (message, action, button) {
        var self = this;
        var wasDisabled;

        if (!message || !message.id || !this.sessionId || this.isLocked() || !action.action_token) {
            return;
        }

        wasDisabled = !!button.disabled;
        button.disabled = true;
        button.classList.add('is-loading');
        this.setRequestInFlight(true);

        this.runAction('performAction', {
            sessionId: this.sessionId,
            messageId: message.id,
            actionId: action.id,
            actionToken: action.action_token
        }).then(function (response) {
            var data = response && response.data ? response.data : {};

            if (data.message) {
                self.upsertMessage(data.message);
                self.renderHistory(self.messages, self.activeJob);
            } else {
                self.loadHistory(true);
            }
            self.setRequestInFlight(false);
        }, function (error) {
            button.classList.remove('is-loading');
            button.disabled = wasDisabled;
            self.appendMessage('system', extractErrorMessage(error), null);
            self.setRequestInFlight(false);
        });
    };

    window.AIChatWrapper = {
        init: function (config) {
            if (window[INSTANCE_KEY]) {
                return window[INSTANCE_KEY];
            }
            if (!config || !config.rootId) {
                return null;
            }
            var root = document.getElementById(config.rootId);
            if (!root) {
                return null;
            }
            window[INSTANCE_KEY] = new ChatWrapper(root, config);
            window[INSTANCE_KEY].init();
            return window[INSTANCE_KEY];
        }
    };
})(window, document, window.BX);
