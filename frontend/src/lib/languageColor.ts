const KNOWN: Record<string, string> = {
  Python: "#4b8bbe",
  TypeScript: "#3b82c4",
  JavaScript: "#d7b83c",
  TSX: "#3b82c4",
  JSX: "#d7b83c",
  Markdown: "#7c8878",
  JSON: "#8a8f84",
  YAML: "#b06a6a",
  TOML: "#9a6f5d",
  HTML: "#c96a4b",
  CSS: "#7d6bb0",
  SCSS: "#c47f9c",
  Shell: "#6f9e63",
  Bash: "#6f9e63",
  Go: "#48a9b8",
  Rust: "#c47b55",
  Java: "#b0724a",
  Kotlin: "#9b6ac4",
  "C++": "#9b5d84",
  C: "#788aa8",
  "C#": "#4e8a6c",
  Ruby: "#b5534e",
  PHP: "#767bb3",
  Swift: "#d0764d",
  Dart: "#3b9a9a",
  Vue: "#4d9a76",
  Svelte: "#d0703d",
  SQL: "#9b7a4e",
  Dockerfile: "#4d8ab5",
  Makefile: "#8b8b78",
  Objective: "#7d8da8",
  "Jupyter Notebook": "#c07a4d",
  XML: "#7d9a6b",
  Configuration: "#8d8a7c",
  License: "#9a9a8f",
  Text: "#9a9a8f",
  "Plain Text": "#9a9a8f",
  Unknown: "#9a9a8f",
};

const PALETTE = [
  "#4b8bbe",
  "#48a9b8",
  "#6f9e63",
  "#c47b55",
  "#9b6ac4",
  "#c47f9c",
  "#d7b83c",
  "#7d6bb0",
  "#b06a6a",
  "#5b8d7a",
];

function hash(value: string): number {
  let result = 0;
  for (let index = 0; index < value.length; index += 1) {
    result = (result * 31 + value.charCodeAt(index)) % 1_000_003;
  }
  return result;
}

export function languageColor(name: string): string {
  return KNOWN[name] ?? PALETTE[hash(name) % PALETTE.length];
}
