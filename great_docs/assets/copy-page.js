/**
 * Copy Page Widget for Great Docs
 *
 * Provides two actions:
 * - "Copy as Markdown" — copies the page's .md content to clipboard
 * - "View as Markdown" — navigates to the .md version of the page
 *
 * The .md files are generated alongside .html files by the post-render script.
 */

(function() {
    'use strict';

    /**
     * Derive the .md URL from the current page URL.
     * e.g., /reference/GreatDocs.html -> /reference/GreatDocs.md
     *       /user-guide/quickstart.html -> /user-guide/quickstart.md
     */
    function getMdUrl() {
        var path = window.location.pathname;
        // Replace .html with .md
        if (path.endsWith('.html')) {
            return path.slice(0, -5) + '.md';
        }
        // For paths ending in / (index pages), try index.md
        if (path.endsWith('/')) {
            return path + 'index.md';
        }
        return path + '.md';
    }

    /**
     * Create and inject the copy-page widget.
     */
    function initCopyPage() {
        // Find the title block header to position the button
        var titleBlock = document.getElementById('title-block-header');
        if (!titleBlock) return;

        // Create the widget container
        var widget = document.createElement('div');
        widget.className = 'gd-copy-page';
        widget.setAttribute('role', 'group');
        widget.setAttribute('aria-label', 'Page actions');

        // Copy as Markdown button
        var copyBtn = document.createElement('button');
        copyBtn.className = 'gd-copy-page-btn gd-copy-md-btn';
        copyBtn.setAttribute('title', 'Copy page as Markdown');
        copyBtn.setAttribute('aria-label', 'Copy page as Markdown');
        copyBtn.innerHTML =
            '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>' +
            '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>' +
            '</svg>' +
            '<span class="gd-copy-page-label">Copy page</span>';

        // View as Markdown link
        var viewLink = document.createElement('a');
        viewLink.className = 'gd-copy-page-btn gd-view-md-btn';
        viewLink.href = getMdUrl();
        viewLink.setAttribute('title', 'View as Markdown');
        viewLink.setAttribute('aria-label', 'View page as Markdown');
        viewLink.innerHTML =
            '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 208 128" fill="currentColor" aria-hidden="true">' +
            '<rect width="198" height="118" x="5" y="5" ry="10" stroke="currentColor" stroke-width="10" fill="none"/>' +
            '<path d="M30 98V30h20l20 25 20-25h20v68H90V59L70 84 50 59v39zm125 0l-30-33h20V30h20v35h20z"/>' +
            '</svg>';

        widget.appendChild(copyBtn);
        widget.appendChild(viewLink);

        // Insert before the title block
        titleBlock.parentNode.insertBefore(widget, titleBlock);

        // Clipboard helper with fallback for when the async Clipboard API
        // is unavailable or the user-activation has expired (common after
        // an async fetch in strict browsers).
        function copyToClipboard(text) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                return navigator.clipboard.writeText(text).catch(function() {
                    return fallbackCopy(text);
                });
            }
            return fallbackCopy(text);
        }

        function fallbackCopy(text) {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            try {
                document.execCommand('copy');
            } catch (e) {
                document.body.removeChild(ta);
                return Promise.reject(e);
            }
            document.body.removeChild(ta);
            return Promise.resolve();
        }

        // Copy handler
        copyBtn.addEventListener('click', function() {
            var mdUrl = getMdUrl();

            fetch(mdUrl)
                .then(function(response) {
                    if (!response.ok) {
                        throw new Error('Markdown file not found');
                    }
                    return response.text();
                })
                .then(function(text) {
                    return copyToClipboard(text);
                })
                .then(function() {
                    // Show success feedback
                    var label = copyBtn.querySelector('.gd-copy-page-label');
                    var origText = label.textContent;
                    label.textContent = 'Copied!';
                    copyBtn.classList.add('gd-copy-success');
                    setTimeout(function() {
                        label.textContent = origText;
                        copyBtn.classList.remove('gd-copy-success');
                    }, 2000);
                })
                .catch(function(err) {
                    console.warn('Copy page failed:', err);
                    var label = copyBtn.querySelector('.gd-copy-page-label');
                    var origText = label.textContent;
                    label.textContent = 'Error';
                    setTimeout(function() {
                        label.textContent = origText;
                    }, 2000);
                });
        });
        });
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCopyPage);
    } else {
        initCopyPage();
    }
})();
