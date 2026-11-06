// Render URLs in agent replies as links (e.g. issue links, the "Connect Gmail" link).
export default function Linkify({ text }) {
  return text.split(/(https?:\/\/[^\s)<>"*]+)/g).map((part, i) =>
    i % 2 ? <a key={i} href={part} target="_blank" rel="noreferrer">{part}</a> : part
  );
}
