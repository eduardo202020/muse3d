import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const validator = require("gltf-validator");

function readArgs(argv) {
  const args = {
    input: argv[2],
    report: null,
  };
  for (let index = 3; index < argv.length; index += 1) {
    if (argv[index] === "--report") {
      args.report = argv[index + 1];
      index += 1;
    }
  }
  return args;
}

const args = readArgs(process.argv);
if (!args.input) {
  console.error("Usage: node scripts/validate_glb.mjs input.glb --report report.json");
  process.exit(2);
}

if (!fs.existsSync(args.input)) {
  console.error(`Input GLB not found: ${args.input}`);
  process.exit(1);
}

const bytes = fs.readFileSync(args.input);
const report = await validator.validateBytes(new Uint8Array(bytes));

if (args.report) {
  fs.mkdirSync(path.dirname(args.report), { recursive: true });
  fs.writeFileSync(args.report, JSON.stringify(report, null, 2));
}

const issues = report.issues || {};
const errors = issues.numErrors ?? 0;
const warnings = issues.numWarnings ?? 0;
const infos = issues.numInfos ?? 0;

console.log(`glTF validation: ${errors} error(s), ${warnings} warning(s), ${infos} info message(s)`);
process.exit(errors > 0 ? 1 : 0);
