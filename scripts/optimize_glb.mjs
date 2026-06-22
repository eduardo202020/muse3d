import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

function readArgs(argv) {
  const args = {
    input: argv[2],
    output: argv[3],
    textureSize: "1024",
    textureCompress: "webp",
    compress: "draco",
    simplify: false,
    simplifyRatio: "0.75",
  };

  for (let index = 4; index < argv.length; index += 1) {
    const current = argv[index];
    const next = argv[index + 1];
    if (current === "--texture-size") {
      args.textureSize = next;
      index += 1;
    } else if (current === "--texture-compress") {
      args.textureCompress = next;
      index += 1;
    } else if (current === "--compress") {
      args.compress = next;
      index += 1;
    } else if (current === "--simplify") {
      args.simplify = true;
    } else if (current === "--simplify-ratio") {
      args.simplifyRatio = next;
      index += 1;
    }
  }
  return args;
}

const args = readArgs(process.argv);
if (!args.input || !args.output) {
  console.error("Usage: node scripts/optimize_glb.mjs input.glb output.glb [options]");
  process.exit(2);
}

if (!fs.existsSync(args.input)) {
  console.error(`Input GLB not found: ${args.input}`);
  process.exit(1);
}

fs.mkdirSync(path.dirname(args.output), { recursive: true });

const npx = "npx";
const commandArgs = [
  "gltf-transform",
  "optimize",
  args.input,
  args.output,
];

if (args.compress && args.compress !== "none") {
  commandArgs.push("--compress", args.compress);
}

if (args.textureCompress && args.textureCompress !== "false") {
  commandArgs.push("--texture-compress", args.textureCompress);
}

if (args.textureSize && args.textureSize !== "0") {
  commandArgs.push("--texture-size", args.textureSize);
}

if (args.simplify) {
  commandArgs.push("--simplify", "true", "--simplify-ratio", args.simplifyRatio);
}

const result = spawnSync(npx, commandArgs, {
  stdio: "inherit",
  shell: process.platform === "win32",
});
if (result.error) {
  console.error(result.error.message);
}
process.exit(result.status ?? 1);
