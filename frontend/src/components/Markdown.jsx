import ReactMarkdown from "react-markdown";

// Each element gets explicit styles because Tailwind's reset removes the browser defaults.
// `node` is stripped so it never reaches the DOM element.
const tag = (Tag, className) =>
  function Styled({ node, ...props }) {
    return <Tag className={className} {...props} />;
  };

const components = {
  h1: tag("h3", "mb-2 mt-5 font-display text-xl font-bold first:mt-0"),
  h2: tag("h3", "mb-2 mt-5 font-display text-lg font-bold first:mt-0"),
  h3: tag("h4", "mb-1 mt-4 font-semibold first:mt-0"),
  h4: tag("h4", "mb-1 mt-4 font-semibold first:mt-0"),
  p: tag("p", "my-3 leading-relaxed first:mt-0 last:mb-0"),
  ul: tag("ul", "my-3 list-disc space-y-1 pl-6"),
  ol: tag("ol", "my-3 list-decimal space-y-1 pl-6"),
  li: tag("li", "leading-relaxed"),
  strong: tag("strong", "font-semibold"),
  blockquote: tag("blockquote", "my-3 border-l-4 border-line pl-4 text-muted"),
  hr: tag("hr", "my-4 border-line"),
  pre: tag(
    "pre",
    "my-3 overflow-x-auto rounded-xl bg-page p-4 text-sm [&_code]:bg-transparent [&_code]:p-0 [&_code]:text-[1em]"
  ),
  code: function Code({ node, className, ...props }) {
    return (
      <code
        className={`rounded bg-page px-1.5 py-0.5 font-mono text-[0.9em] ${className || ""}`}
        {...props}
      />
    );
  },
  a: function Link({ node, href, children }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="font-semibold underline">
        {children}
      </a>
    );
  },
};

export default function Markdown({ text }) {
  return <ReactMarkdown components={components}>{text}</ReactMarkdown>;
}