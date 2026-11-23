export function markdownToHtml(markdown: string) {
    const normalizedMarkdown = markdown.replace(/\r\n/g, "\n").trim()
    if (!normalizedMarkdown) {
        return ""
    }

    const htmlParts: string[] = []
    const paragraphLines: string[] = []
    const codeBlockLines: string[] = []
    const listItems: string[] = []
    let listType: "ol" | "ul" | null = null
    let insideCodeBlock = false

    const flushParagraph = () => {
        if (!paragraphLines.length) {
            return
        }
        const paragraphHtml = renderInlineMarkdown(paragraphLines.join("\n")).replace(/\n/g, "<br />")
        htmlParts.push(`<p>${paragraphHtml}</p>`)
        paragraphLines.length = 0
    }

    const flushList = () => {
        if (!listType || !listItems.length) {
            return
        }
        htmlParts.push(`<${listType}>${listItems.join("")}</${listType}>`)
        listItems.length = 0
        listType = null
    }

    const flushCodeBlock = () => {
        if (!insideCodeBlock) {
            return
        }
        const codeHtml = escapeHtml(codeBlockLines.join("\n"))
        htmlParts.push(`<pre><code>${codeHtml}</code></pre>`)
        codeBlockLines.length = 0
        insideCodeBlock = false
    }

    for (const line of normalizedMarkdown.split("\n")) {
        const trimmedLine = line.trim()

        if (trimmedLine.startsWith("```")) {
            flushParagraph()
            flushList()
            if (insideCodeBlock) {
                flushCodeBlock()
            } else {
                insideCodeBlock = true
                codeBlockLines.length = 0
            }
            continue
        }

        if (insideCodeBlock) {
            codeBlockLines.push(line)
            continue
        }

        if (!trimmedLine) {
            flushParagraph()
            flushList()
            continue
        }

        const headingMatch = trimmedLine.match(/^(#{1,6})\s+(.*)$/)
        if (headingMatch) {
            flushParagraph()
            flushList()
            const headingLevel = headingMatch[1].length
            htmlParts.push(`<h${headingLevel}>${renderInlineMarkdown(headingMatch[2])}</h${headingLevel}>`)
            continue
        }

        const orderedItemMatch = trimmedLine.match(/^\d+\.\s+(.*)$/)
        if (orderedItemMatch) {
            flushParagraph()
            if (listType && listType !== "ol") {
                flushList()
            }
            listType = "ol"
            listItems.push(`<li>${renderInlineMarkdown(orderedItemMatch[1])}</li>`)
            continue
        }

        const unorderedItemMatch = trimmedLine.match(/^[-*]\s+(.*)$/)
        if (unorderedItemMatch) {
            flushParagraph()
            if (listType && listType !== "ul") {
                flushList()
            }
            listType = "ul"
            listItems.push(`<li>${renderInlineMarkdown(unorderedItemMatch[1])}</li>`)
            continue
        }

        const quoteMatch = trimmedLine.match(/^>\s?(.*)$/)
        if (quoteMatch) {
            flushParagraph()
            flushList()
            htmlParts.push(`<blockquote><p>${renderInlineMarkdown(quoteMatch[1])}</p></blockquote>`)
            continue
        }

        paragraphLines.push(line)
    }

    flushParagraph()
    flushList()
    flushCodeBlock()

    return htmlParts.join("")
}

function renderInlineMarkdown(text: string) {
    const codeFragments: string[] = []
    let html = escapeHtml(text)

    html = html.replace(/`([^`\n]+)`/g, (_match, code) => {
        const token = `__CHAT_CODE_${codeFragments.length}__`
        codeFragments.push(`<code>${code}</code>`)
        return token
    })

    html = html.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_match, label, href) => {
        const escapedLabel = label.trim() ? label.trim() : href
        const safeHref = escapeHtml(href)
        return `<a href="${safeHref}">${escapedLabel}</a>`
    })

    html = html.replace(/\*\*\*([^*]+)\*\*\*/g, "<strong><em>$1</em></strong>")
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    html = html.replace(/__([^_]+)__/g, "<strong>$1</strong>")
    html = html.replace(/~~([^~]+)~~/g, "<s>$1</s>")
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>")
    html = html.replace(/_([^_]+)_/g, "<em>$1</em>")

    for (let codeIndex = 0; codeIndex < codeFragments.length; codeIndex += 1) {
        html = html.split(`__CHAT_CODE_${codeIndex}__`).join(codeFragments[codeIndex])
    }

    return html
}

function escapeHtml(value: string) {
    return value
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;")
}
