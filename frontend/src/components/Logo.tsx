export function LogoMark({ size = 34 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      aria-hidden="true"
      focusable="false"
    >
      <rect width="64" height="64" rx="15" fill="#233028" />
      <path
        d="M20 22h18a6 6 0 0 1 6 6v20"
        fill="none"
        stroke="#7bd49c"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <path
        d="M20 22v20a6 6 0 0 0 6 6h12"
        fill="none"
        stroke="#eef2e9"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <circle cx="20" cy="18" r="4" fill="#eef2e9" />
      <circle cx="20" cy="48" r="4" fill="#7bd49c" />
      <circle cx="44" cy="48" r="4" fill="#eef2e9" />
    </svg>
  );
}
