// Experimental adapter. No conversion or layout is allowed outside Actions.
if (process.env.GITHUB_ACTIONS !== "true" || !process.env.GITHUB_RUN_ID) {
    console.error("CLOUD_ONLY: template generation and layout run in GitHub Actions.");
    process.exit(2);
}

const fs = await import("node:fs/promises");
const path = await import("node:path");
const { patchDocument, PatchType, ImportedXmlComponent, Document, Packer, Paragraph } = await import("docx");
const { estimatePageNumbersWith } = await import("docx/layout");
const { Math: WordMath, latexToMath } = await import("docx/math");
const directory = path.resolve(process.argv[2]);
const request = JSON.parse(await fs.readFile(path.join(directory, "template-input.json"), "utf8"));
const components = request.blocks.map((xml) => ImportedXmlComponent.fromXmlString(xml));
const fontFiles = await Promise.all(request.fonts.map(async (font) => ({ name: font.name, data: await fs.readFile(font.path) })));
const strictEstimator = estimatePageNumbersWith({ fonts: fontFiles, guess: false });
const guessingEstimator = estimatePageNumbersWith({ fonts: fontFiles, guess: true });
let layout;
const pageNumbers = (template, context) => {
    const strict = strictEstimator(template, context);
    const guessed = guessingEstimator(template, context);
    // A partial/guessed result is diagnostic information, never acceptance.
    layout = {
        strict: { ...strict, bookmarks: Object.fromEntries(strict.bookmarks ?? []) },
        guessed: { ...guessed, bookmarks: Object.fromEntries(guessed.bookmarks ?? []) },
        role: "diagnostic_only",
        authority: "LibreOffice cloud proof plus page-by-page human review",
    };
    return strict;
};
const output = await patchDocument({
    outputType: "nodebuffer",
    data: await fs.readFile(path.join(directory, "master.docx")),
    patches: { RPS_BODY: { type: PatchType.DOCUMENT, children: components } },
    pageNumbers,
});
await fs.writeFile(path.join(directory, "node-template.docx"), output);
await fs.writeFile(path.join(directory, "node-layout.json"), JSON.stringify(layout, null, 2));

// Probe the new native LaTeX converter separately; do not replace the proven
// Pandoc converter until all supported expressions survive semantic readback.
const formulaResults = [];
const paragraphs = [];
for (const equation of request.equations) {
    try {
        const math = latexToMath(equation.source);
        paragraphs.push(new Paragraph({ children: [new WordMath({ children: math })] }));
        formulaResults.push({ id: equation.id, conversion: "built", semantic_validation: "pending" });
    } catch (error) {
        formulaResults.push({ id: equation.id, conversion: "unsupported", error: String(error.message) });
    }
}
let unknownCommandRejected = false;
try { latexToMath("\\unsupportedstudio{x}"); } catch { unknownCommandRejected = true; }
await fs.writeFile(path.join(directory, "direct-math-probe.docx"), await Packer.toBuffer(new Document({ sections: [{ children: paragraphs }] })));
await fs.writeFile(path.join(directory, "direct-math-probe.json"), JSON.stringify({
    equations: formulaResults,
    unknown_command_rejected: unknownCommandRejected,
    adoption: "probe_only; final outputs retain original Pandoc OMML",
}, null, 2));
