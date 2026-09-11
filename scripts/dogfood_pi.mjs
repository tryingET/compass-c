#!/usr/bin/env node
// Model-free host probe. The caller supplies a reviewed installed Pi SDK and
// disposable cwd/agentDir. Run under a network namespace; never prompts a model.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const [packageDir, cwd, agentDir, expectedPath, trusted = "true"] = process.argv.slice(2);
assert(packageDir && cwd && agentDir && expectedPath,
  "usage: dogfood_pi.mjs <pi-package> <cwd> <agent-dir> <SKILL.md|absent> [trusted]");
const { DefaultResourceLoader, SettingsManager, createReadTool } = await import(
  pathToFileURL(join(resolve(packageDir), "dist/index.js")).href
);
const loader = new DefaultResourceLoader({
  cwd, agentDir,
  settingsManager: SettingsManager.inMemory({ packages: [] }),
  noExtensions: true, noPromptTemplates: true, noThemes: true, noContextFiles: true,
});
await loader.reload({ resolveProjectTrust: async () => trusted === "true" });
const { skills, diagnostics } = loader.getSkills();
assert.deepEqual(diagnostics, []);
const found = skills.filter((skill) => skill.name === "compass");
if (expectedPath === "absent") {
  assert.equal(found.length, 0);
} else {
  assert.equal(found.length, 1);
  assert.equal(found[0].filePath, expectedPath);
  assert.match(found[0].description, /decision brief/);
  const read = createReadTool(cwd);
  for (const path of [expectedPath, join(found[0].baseDir, "references/calculators.md")]) {
    const result = await read.execute("compass-local-dogfood", { path });
    const text = result.content.filter((item) => item.type === "text")
      .map((item) => item.text).join("\n");
    assert(text.includes(readFileSync(path, "utf8").trim()));
  }
}
console.log(JSON.stringify({
  host: "pi", version: JSON.parse(readFileSync(join(packageDir, "package.json"))).version,
  proof: "resource-discovery-and-host-read-only", modelInvoked: false,
  trusted: trusted === "true", compassCount: found.length,
}));
