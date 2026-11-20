// Parses AI Markdown into plain block objects (rendered by components/ai/RichText).

const LIST_RE = /^\s*(?:[*\-•]|\d+[.)])\s+/;

export function parseBlocks(text = "") {
  const lines = text.replace(/\r/g, "").split("\n");
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const h = line.match(/^\s*(#{1,6})\s+(.*)$/);
    if (!line.trim()) {
      i += 1;
    } else if (h) {
      blocks.push({ type: "h", level: h[1].length, text: h[2].replace(/:$/, "").trim() });
      i += 1;
    } else if (line.trim().startsWith("|")) {
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        const cells = lines[i].trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        if (!cells.every((c) => /^:?-{2,}:?$/.test(c))) rows.push(cells);
        i += 1;
      }
      blocks.push({ type: "table", rows });
    } else if (LIST_RE.test(line)) {
      const ordered = /^\s*\d+[.)]/.test(line);
      const items = [];
      while (i < lines.length && LIST_RE.test(lines[i])) {
        items.push(lines[i].replace(LIST_RE, "").trim());
        i += 1;
      }
      blocks.push({ type: ordered ? "ol" : "ul", items });
    } else {
      const para = [];
      while (i < lines.length && lines[i].trim() && !LIST_RE.test(lines[i]) && !/^\s*#{1,6}\s/.test(lines[i]) && !lines[i].trim().startsWith("|")) {
        para.push(lines[i].trim());
        i += 1;
      }
      blocks.push({ type: "p", text: para.join(" ") });
    }
  }
  return blocks;
}

/** Split blocks into sections at headings (level >= 2). The first h1/h2 title is dropped. */
export function toSections(blocks) {
  const sections = [];
  let current = null;
  blocks.forEach((b, idx) => {
    if (b.type === "h" && idx === 0 && b.level <= 2) return;
    if (b.type === "h") {
      current = { title: b.text, blocks: [] };
      sections.push(current);
    } else {
      if (!current) {
        current = { title: null, blocks: [] };
        sections.push(current);
      }
      current.blocks.push(b);
    }
  });
  return sections.filter((s) => s.blocks.length);
}
