/** Linguist-inspired palette tuned to stay legible on both themes. */
const KNOWN: Record<string, string> = {
  Python: "#4f9fe8",
  TypeScript: "#5b9be6",
  JavaScript: "#e8c451",
  TSX: "#5b9be6",
  JSX: "#e8c451",
  Markdown: "#93a4b3",
  JSON: "#9aabb8",
  YAML: "#e08a78",
  TOML: "#d19070",
  HTML: "#e88063",
  CSS: "#9a86d8",
  SCSS: "#e094bc",
  Shell: "#86c46f",
  Bash: "#86c46f",
  Go: "#54c9d8",
  Rust: "#e09366",
  Java: "#dd9c60",
  Kotlin: "#b195e8",
  "C++": "#d183b0",
  C: "#92a9cc",
  "C#": "#63b98e",
  Ruby: "#e0736a",
  PHP: "#949bdd",
  Swift: "#e8965f",
  Dart: "#53c2c2",
  Vue: "#66c795",
  Svelte: "#e88454",
  SQL: "#cfaa60",
  Dockerfile: "#66aee0",
  Makefile: "#aeae98",
  Objective: "#9cb0cf",
  "Jupyter Notebook": "#e4965f",
  XML: "#9dc487",
  Configuration: "#aca795",
  License: "#b2b2a4",
  Text: "#b2b2a4",
  "Plain Text": "#b2b2a4",
  Lean: "#c96a4b",
  Cuda: "#76b74f",
  Typst: "#6aa9c4",
  MDX: "#93a4b3",
  GLSL: "#8f9ad6",
  Metal: "#a48fd0",
  CMake: "#d16a6a",
  Unknown: "#b2b2a4",
};

const PALETTE = [
  "#4f9fe8",
  "#54c9d8",
  "#86c46f",
  "#e09366",
  "#b195e8",
  "#e094bc",
  "#e8c451",
  "#9a86d8",
  "#e08a78",
  "#6cc4a1",
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
