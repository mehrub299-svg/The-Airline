export default function Tip({ label, align = "left", children }) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className={`pointer-events-none absolute top-full z-50 mt-2 whitespace-nowrap rounded-md bg-ink px-2 py-1 text-xs font-semibold text-page opacity-0 shadow transition-opacity delay-100 group-focus-within:opacity-100 group-hover:opacity-100 ${
          align === "right" ? "right-0" : "left-0"
        }`}
      >
        {label}
      </span>
    </span>
  );
}